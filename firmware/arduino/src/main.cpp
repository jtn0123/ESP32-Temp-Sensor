#include <Arduino.h>
#include <GxEPD2_BW.h>
#include "icons.h"
#include "display_layout.h"
#include "sensors.h"
#include "generated_config.h"
#include "net.h"
#include "power.h"

// Feather ESP32-S2 + 2.13" FeatherWing (adjust if needed)
#ifndef EINK_CS
#define EINK_CS   9   // D9
#endif
#ifndef EINK_DC
#define EINK_DC   10  // D10
#endif
#ifndef EINK_RST
#define EINK_RST  -1  // not used; Wing auto-reset ties to Feather RESET
#endif
#ifndef EINK_BUSY
#define EINK_BUSY 7   // D7
#endif

// 2.13" b/w class; choose the one matching your panel
// B74 works for SSD1680/UC8151 variants used by many 2.13" panels
GxEPD2_BW<GxEPD2_213_B74, GxEPD2_213_B74::HEIGHT> display(GxEPD2_213_B74(EINK_CS, EINK_DC, EINK_RST, EINK_BUSY));

RTC_DATA_ATTR static uint16_t partial_counter = 0;

static void pump_network_ms(uint32_t duration_ms)
{
    unsigned long start = millis();
    while (millis() - start < duration_ms) {
        net_loop();
        delay(10);
    }
}

static void draw_static_chrome()
{
    // Frame and header linework
    display.fillScreen(GxEPD_WHITE);
    display.drawRect(0, 0, EINK_WIDTH, EINK_HEIGHT, GxEPD_BLACK);
    display.drawLine(1, 18, EINK_WIDTH-2, 18, GxEPD_BLACK);
    display.drawLine(125, 18, 125, 95, GxEPD_BLACK);

    // Header "Room"
    display.setTextColor(GxEPD_BLACK);
    display.setTextSize(1);
    display.setCursor(4, 13);
    display.print(ROOM_NAME);

    // Section labels
    display.setCursor(6, 22);
    display.print("INSIDE");
    display.setCursor(131, 22);
    display.print("OUTSIDE");
}

static void draw_values(const char* in_temp_f, const char* in_rh,
                        const char* out_temp_f, const char* out_rh,
                        const char* time_str,
                        const char* status)
{
    display.setTextColor(GxEPD_BLACK);
    // Inside temp big
    display.setTextSize(2);
    display.setCursor(INSIDE_TEMP[0], INSIDE_TEMP[1]);
    display.print(in_temp_f);
    display.print("\xF8 F");

    // Inside RH
    display.setTextSize(1);
    display.setCursor(INSIDE_RH[0], INSIDE_RH[1]);
    display.print(in_rh);
    display.print("% RH");

    // Time
    display.setCursor(INSIDE_TIME[0], INSIDE_TIME[1]);
    display.print(time_str);

    // Outside temp big
    display.setTextSize(2);
    display.setCursor(OUT_TEMP[0], OUT_TEMP[1]);
    display.print(out_temp_f);
    display.print("\xF8 F");

    // Outside RH
    display.setTextSize(1);
    display.setCursor(OUT_RH[0], OUT_RH[1]);
    display.print(out_rh);
    display.print("% RH");

    // Status line
    display.setCursor(STATUS_[0], STATUS_[1]);
    display.print(status);
}

static IconId map_weather_to_icon(const String& w)
{
    String s = w;
    s.toLowerCase();
    if (s.indexOf("storm") >= 0 || s.indexOf("thunder") >= 0 || s.indexOf("lightning") >= 0) return ICON_WEATHER_LIGHTNING;
    if (s.indexOf("pour") >= 0 || s.indexOf("rain") >= 0 || s.indexOf("shower") >= 0) return ICON_WEATHER_POURING;
    if (s.indexOf("snow") >= 0) return ICON_WEATHER_SNOWY;
    if (s.indexOf("fog") >= 0 || s.indexOf("mist") >= 0 || s.indexOf("haze") >= 0) return ICON_WEATHER_FOG;
    if (s.indexOf("part") >= 0) return ICON_WEATHER_PARTLY_CLOUDY;
    if (s.indexOf("cloud") >= 0 || s.indexOf("overcast") >= 0) return ICON_WEATHER_CLOUDY;
    if (s.indexOf("night") >= 0) return ICON_WEATHER_NIGHT;
    return ICON_WEATHER_SUNNY;
}

static void draw_weather_icon_region(const String& weather)
{
    const int16_t x = OUT_ICON[0];
    const int16_t y = OUT_ICON[1];
    // Clear region background and draw icon
    display.fillRect(x, y, OUT_ICON[2]-OUT_ICON[0], OUT_ICON[3]-OUT_ICON[1], GxEPD_WHITE);
    draw_icon(display, x, y, map_weather_to_icon(weather), GxEPD_BLACK);
}

static void full_refresh()
{
    display.setFullWindow();
    display.firstPage();
    do {
        draw_static_chrome();
        InsideReadings r = read_inside_sensors();
        char in_temp[16];
        char in_rh[16];
        snprintf(in_temp, sizeof(in_temp), isfinite(r.temperatureC) ? "%.1f" : "--", r.temperatureC * 9.0/5.0 + 32.0);
        snprintf(in_rh, sizeof(in_rh), isfinite(r.humidityPct) ? "%.0f" : "--", r.humidityPct);
        OutsideReadings o = net_get_outside();
        char out_temp[16];
        char out_rh[16];
        snprintf(out_temp, sizeof(out_temp), (o.validTemp && isfinite(o.temperatureC)) ? "%.1f" : "--", o.temperatureC * 9.0/5.0 + 32.0);
        snprintf(out_rh, sizeof(out_rh), (o.validHum && isfinite(o.humidityPct)) ? "%.0f" : "--", o.humidityPct);
        BatteryStatus bs = read_battery_status();
        char status[64];
        snprintf(status, sizeof(status), "IP %s  Batt %.2fV %d%%  ~%dd",
                 net_ip().c_str(), bs.voltage, bs.percent, bs.estimatedDays);
        draw_values(in_temp, in_rh, out_temp, out_rh, "10:32", status);
        draw_weather_icon_region(o.weather);
    } while (display.nextPage());
}

static void partial_update_inside_temp(const char* in_temp_f)
{
    const int16_t x = INSIDE_TEMP[0];
    const int16_t y = INSIDE_TEMP[1] - 14;
    const int16_t w = (INSIDE_TEMP[2] - INSIDE_TEMP[0]);
    const int16_t h = 22;
    display.setPartialWindow(x, y, w, h);
    display.firstPage();
    do {
        display.fillScreen(GxEPD_WHITE);
        display.setTextColor(GxEPD_BLACK);
        display.setTextSize(2);
        display.setCursor(INSIDE_TEMP[0], INSIDE_TEMP[1]);
        display.print(in_temp_f);
        display.print("\xF8 F");
    } while (display.nextPage());
}

static void partial_update_outside_temp(const char* out_temp_f)
{
    const int16_t x = OUT_TEMP[0];
    const int16_t y = OUT_TEMP[1] - 14;
    const int16_t w = (OUT_TEMP[2] - OUT_TEMP[0]);
    const int16_t h = 22;
    display.setPartialWindow(x, y, w, h);
    display.firstPage();
    do {
        display.fillScreen(GxEPD_WHITE);
        display.setTextColor(GxEPD_BLACK);
        display.setTextSize(2);
        display.setCursor(OUT_TEMP[0], OUT_TEMP[1]);
        display.print(out_temp_f);
        display.print("\xF8 F");
    } while (display.nextPage());
}

static void partial_update_outside_rh(const char* out_rh)
{
    const int16_t x = OUT_RH[0];
    const int16_t y = OUT_RH[1] - 10;
    const int16_t w = (OUT_RH[2] - OUT_RH[0]);
    const int16_t h = 16;
    display.setPartialWindow(x, y, w, h);
    display.firstPage();
    do {
        display.fillScreen(GxEPD_WHITE);
        display.setTextColor(GxEPD_BLACK);
        display.setTextSize(1);
        display.setCursor(OUT_RH[0], OUT_RH[1]);
        display.print(out_rh);
        display.print("% RH");
    } while (display.nextPage());
}

static void partial_update_weather_icon(const String& weather)
{
    const int16_t w = OUT_ICON[2]-OUT_ICON[0];
    const int16_t h = OUT_ICON[3]-OUT_ICON[1];
    display.setPartialWindow(OUT_ICON[0], OUT_ICON[1], w, h);
    display.firstPage();
    do {
        display.fillScreen(GxEPD_WHITE);
        draw_weather_icon_region(weather);
    } while (display.nextPage());
}

void setup() {
    Serial.begin(115200);
    delay(100);
    Serial.println("ESP32 eInk Room Node boot");

    display.init(0);
    display.setRotation(1); // landscape 250x122 coordinate system
    net_begin();
    pump_network_ms(800); // allow retained MQTT to arrive

    bool do_full = false;
    if (partial_counter == 0) {
        do_full = true; // first ever boot
    } else if ((partial_counter % FULL_REFRESH_EVERY) == 0) {
        do_full = true; // periodic full clears
    }

    if (do_full) {
        full_refresh();
    } else {
        InsideReadings r = read_inside_sensors();
        char in_temp[16];
        if (isfinite(r.temperatureC)) {
            snprintf(in_temp, sizeof(in_temp), "%.1f", r.temperatureC * 9.0/5.0 + 32.0);
        } else {
            snprintf(in_temp, sizeof(in_temp), "--");
        }
        partial_update_inside_temp(in_temp);
        if (isfinite(r.temperatureC) && isfinite(r.humidityPct)) {
            net_publish_inside(r.temperatureC, r.humidityPct);
        }

        OutsideReadings o = net_get_outside();
        if (o.validTemp) {
            char out_temp[16];
            snprintf(out_temp, sizeof(out_temp), "%.1f", o.temperatureC * 9.0/5.0 + 32.0);
            partial_update_outside_temp(out_temp);
        }
        if (o.validHum) {
            char out_rh[16];
            snprintf(out_rh, sizeof(out_rh), "%.0f", o.humidityPct);
            partial_update_outside_rh(out_rh);
        }
        if (o.validWeather) {
            partial_update_weather_icon(o.weather);
        }
    }

    partial_counter++;
    go_deep_sleep_seconds(WAKE_INTERVAL_SEC);
}

void loop() {
    // not used; we deep-sleep from setup
    delay(1000);
}



