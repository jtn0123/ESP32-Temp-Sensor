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
RTC_DATA_ATTR static float last_inside_f = NAN;
RTC_DATA_ATTR static float last_outside_f = NAN;
RTC_DATA_ATTR static float last_outside_rh = NAN;

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

    // Header: room name left, time will be drawn separately
    display.setTextColor(GxEPD_BLACK);
    display.setTextSize(1);
    display.setCursor(6, 13);
    display.print(ROOM_NAME);

    // Section labels
    display.setCursor(6, 22);
    display.print("INSIDE");
    display.setCursor(131, 22);
    display.print("OUTSIDE");
}

static inline int16_t text_width_default_font(const char* s, uint8_t size)
{
    // Default 5x7 font is 6 px advance per char at size 1
    int16_t count = 0;
    for (const char* p = s; *p; ++p) count++;
    return count * 6 * size;
}

static void draw_header_time(const char* time_str)
{
    const int16_t x = HEADER_TIME[0];
    const int16_t y = HEADER_TIME[1];
    const int16_t w = HEADER_TIME[2];
    const int16_t h = HEADER_TIME[3];
    display.setPartialWindow(x, y, w, h);
    display.firstPage();
    do {
        display.fillScreen(GxEPD_WHITE);
        display.setTextColor(GxEPD_BLACK);
        display.setTextSize(1);
        int16_t tw = text_width_default_font(time_str, 1);
        int16_t rx = x + w - 2 - tw;
        int16_t by = y + h - 2; // baseline
        display.setCursor(rx, by);
        display.print(time_str);
    } while (display.nextPage());
}

static void draw_status_line(const BatteryStatus& bs, const String& ip)
{
    const int16_t x = STATUS_[0];
    const int16_t y = STATUS_[1];
    const int16_t w = STATUS_[2];
    const int16_t h = STATUS_[3];
    display.setPartialWindow(x, y, w, h);
    display.firstPage();
    do {
        display.fillScreen(GxEPD_WHITE);
        display.setTextColor(GxEPD_BLACK);
        display.setTextSize(1);
        int16_t cx = x + 2;
        int16_t cy = y + h - 4;
        // Low battery cue: draw battery if percent known
        if (bs.percent >= 0) {
            int16_t bx = cx;
            int16_t by = y + 2;
            int16_t bw = 14;
            int16_t bh = 8;
            display.drawRect(bx, by, bw, bh, GxEPD_BLACK);
            display.fillRect(bx + bw, by + 2, 2, 4, GxEPD_BLACK);
            int16_t fillw = (int16_t)((bw - 2) * (bs.percent / 100.0f) + 0.5f);
            if (fillw > 0) display.fillRect(bx + 1, by + 1, fillw, bh - 2, GxEPD_BLACK);
            cx += bw + 6;
        }
        char line[96];
        snprintf(line, sizeof(line), "IP %s  |  Batt %.2fV %d%%  |  ~%dd",
                 ip.c_str(), bs.voltage, bs.percent, bs.estimatedDays);
        display.setCursor(cx, cy);
        display.print(line);
    } while (display.nextPage());
}

static void draw_values(const char* in_temp_f, const char* in_rh,
                        const char* out_temp_f, const char* out_rh,
                        const char* time_str,
                        const char* status)
{
    display.setTextColor(GxEPD_BLACK);
    // Inside temp big, right-aligned, degree+F small to the right
    {
        const int16_t x = INSIDE_TEMP[0];
        const int16_t y = INSIDE_TEMP[1];
        const int16_t w = INSIDE_TEMP[2];
        const int16_t h = INSIDE_TEMP[3];
        display.setTextSize(2);
        int16_t tw = text_width_default_font(in_temp_f, 2);
        int16_t rx = x + w - 2 - tw;
        display.setCursor(rx, y);
        display.print(in_temp_f);
        display.setTextSize(1);
        display.setCursor(x + w + 2, y + 4);
        display.print("\xF8");
        display.setCursor(x + w + 8, y + 4);
        display.print("F");
    }

    // Inside RH
    display.setTextSize(1);
    display.setCursor(INSIDE_RH[0], INSIDE_RH[1]);
    display.print(in_rh);
    display.print("% RH");

    // Time
    display.setCursor(INSIDE_TIME[0], INSIDE_TIME[1]);
    display.print(time_str);

    // Outside temp big, right-aligned, degree+F small to the right
    {
        const int16_t x = OUT_TEMP[0];
        const int16_t y = OUT_TEMP[1];
        const int16_t w = OUT_TEMP[2];
        const int16_t h = OUT_TEMP[3];
        display.setTextSize(2);
        int16_t tw = text_width_default_font(out_temp_f, 2);
        int16_t rx = x + w - 2 - tw;
        display.setCursor(rx, y);
        display.print(out_temp_f);
        display.setTextSize(1);
        display.setCursor(x + w + 2, y + 4);
        display.print("\xF8");
        display.setCursor(x + w + 8, y + 4);
        display.print("F");
    }

    // Outside RH
    display.setTextSize(1);
    display.setCursor(OUT_RH[0], OUT_RH[1]);
    display.print(out_rh);
    display.print("% RH");

    // Status line drawn separately by partial
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

static void partial_update_inside_temp(const char* in_temp_f, char trend)
{
    const int16_t x = INSIDE_TEMP[0];
    const int16_t y = INSIDE_TEMP[1];
    const int16_t w = INSIDE_TEMP[2];
    const int16_t h = INSIDE_TEMP[3];
    display.setPartialWindow(x, y, w, h);
    display.firstPage();
    do {
        display.fillScreen(GxEPD_WHITE);
        display.setTextColor(GxEPD_BLACK);
        display.setTextSize(2);
        int16_t tw = text_width_default_font(in_temp_f, 2);
        int16_t rx = x + w - 2 - tw;
        display.setCursor(rx, y);
        display.print(in_temp_f);
        display.setTextSize(1);
        display.setCursor(x + w + 2, y + 4);
        display.print("\xF8");
        display.setCursor(x + w + 8, y + 4);
        display.print("F");
        // Trend arrow/simple indicator at left
        if (trend == '+') { display.setCursor(x + 2, y); display.print("^"); }
        else if (trend == '-') { display.setCursor(x + 2, y); display.print("v"); }
    } while (display.nextPage());
}

static void partial_update_outside_temp(const char* out_temp_f, char trend)
{
    const int16_t x = OUT_TEMP[0];
    const int16_t y = OUT_TEMP[1];
    const int16_t w = OUT_TEMP[2];
    const int16_t h = OUT_TEMP[3];
    display.setPartialWindow(x, y, w, h);
    display.firstPage();
    do {
        display.fillScreen(GxEPD_WHITE);
        display.setTextColor(GxEPD_BLACK);
        display.setTextSize(2);
        int16_t tw = text_width_default_font(out_temp_f, 2);
        int16_t rx = x + w - 2 - tw;
        display.setCursor(rx, y);
        display.print(out_temp_f);
        display.setTextSize(1);
        display.setCursor(x + w + 2, y + 4);
        display.print("\xF8");
        display.setCursor(x + w + 8, y + 4);
        display.print("F");
        if (trend == '+') { display.setCursor(x + 2, y); display.print("^"); }
        else if (trend == '-') { display.setCursor(x + 2, y); display.print("v"); }
    } while (display.nextPage());
}

static void partial_update_outside_rh(const char* out_rh)
{
    const int16_t x = OUT_RH[0];
    const int16_t y = OUT_RH[1];
    const int16_t w = OUT_RH[2];
    const int16_t h = OUT_RH[3];
    display.setPartialWindow(x, y, w, h);
    display.firstPage();
    do {
        display.fillScreen(GxEPD_WHITE);
        display.setTextColor(GxEPD_BLACK);
        display.setTextSize(1);
        display.setCursor(x, y);
        display.print(out_rh);
        display.print("% RH");
    } while (display.nextPage());
}

static void partial_update_weather_icon(const String& weather)
{
    const int16_t w = OUT_ICON[2];
    const int16_t h = OUT_ICON[3];
    display.setPartialWindow(OUT_ICON[0], OUT_ICON[1], w, h);
    display.firstPage();
    do {
        display.fillScreen(GxEPD_WHITE);
        // draw icon at region origin (may clip if larger than region)
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
        char trend_in = '0';
        float now_in_f = isfinite(r.temperatureC) ? (r.temperatureC * 9.0f/5.0f + 32.0f) : NAN;
        if (isfinite(now_in_f) && isfinite(last_inside_f)) {
            float d = now_in_f - last_inside_f;
            if (d >= 0.3f) trend_in = '+'; else if (d <= -0.3f) trend_in = '-';
        }
        partial_update_inside_temp(in_temp, trend_in);
        if (isfinite(now_in_f)) last_inside_f = now_in_f;
        if (isfinite(r.temperatureC) && isfinite(r.humidityPct)) {
            net_publish_inside(r.temperatureC, r.humidityPct);
        }

        OutsideReadings o = net_get_outside();
        if (o.validTemp) {
            char out_temp[16];
            snprintf(out_temp, sizeof(out_temp), "%.1f", o.temperatureC * 9.0/5.0 + 32.0);
            char trend_out = '0';
            float now_out_f = o.temperatureC * 9.0f/5.0f + 32.0f;
            if (isfinite(last_outside_f)) {
                float d = now_out_f - last_outside_f;
                if (d >= 0.3f) trend_out = '+'; else if (d <= -0.3f) trend_out = '-';
            }
            if (!isfinite(last_outside_f) || fabs(now_out_f - last_outside_f) >= 0.2f) {
                partial_update_outside_temp(out_temp, trend_out);
                last_outside_f = now_out_f;
            }
        }
        if (o.validHum) {
            char out_rh[16];
            snprintf(out_rh, sizeof(out_rh), "%.0f", o.humidityPct);
            if (!isfinite(last_outside_rh) || fabs(o.humidityPct - last_outside_rh) >= 1.0f) {
                partial_update_outside_rh(out_rh);
                last_outside_rh = o.humidityPct;
            }
        }
        if (o.validWeather) {
            partial_update_weather_icon(o.weather);
        }
        // Update header time and status every wake
        draw_header_time("10:32");
        BatteryStatus bs = read_battery_status();
        draw_status_line(bs, net_ip());
    }

    partial_counter++;
    // Log awake duration and planned sleep for diagnostics
    Serial.printf("Awake ms: %lu\n", (unsigned long)millis());
    Serial.printf("Sleeping for %us\n", (unsigned)WAKE_INTERVAL_SEC);
    go_deep_sleep_seconds(WAKE_INTERVAL_SEC);
}

void loop() {
    // not used; we deep-sleep from setup
    delay(1000);
}



