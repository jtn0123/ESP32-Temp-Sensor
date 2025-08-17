#include <Arduino.h>
#include <Preferences.h>
#include "config.h"
#include <esp_timer.h>
#include <esp_system.h>
#if USE_DISPLAY
#include <GxEPD2_BW.h>
#include "icons.h"
#include "display_layout.h"
#endif
#include "sensors.h"
#include "generated_config.h"
#include "net.h"
#include "power.h"
#if USE_STATUS_PIXEL
#include <Adafruit_NeoPixel.h>
#endif

// Forward declaration for status pixel tick used in pump_network_ms
#if USE_STATUS_PIXEL
static inline void status_pixel_tick();
#endif

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
#if USE_DISPLAY
GxEPD2_BW<GxEPD2_213_B74, GxEPD2_213_B74::HEIGHT> display(GxEPD2_213_B74(EINK_CS, EINK_DC, EINK_RST, EINK_BUSY));
#endif

RTC_DATA_ATTR static uint16_t partial_counter = 0;
RTC_DATA_ATTR static float last_inside_f = NAN;
RTC_DATA_ATTR static float last_outside_f = NAN;
RTC_DATA_ATTR static float last_outside_rh = NAN;
RTC_DATA_ATTR static int32_t last_icon_id = -1;
RTC_DATA_ATTR static float last_published_inside_tempC = NAN;
RTC_DATA_ATTR static float last_published_inside_rh = NAN;
RTC_DATA_ATTR static uint32_t last_status_crc = 0;
RTC_DATA_ATTR static float last_inside_rh = NAN;

static Preferences g_prefs;

static inline void nvs_begin_cache() { g_prefs.begin("cache", false); }
static inline void nvs_end_cache() { g_prefs.end(); }
static inline void nvs_load_cache_if_unset() {
    if (!isfinite(last_inside_f)) last_inside_f = g_prefs.getFloat("li_f", NAN);
    if (!isfinite(last_inside_rh)) last_inside_rh = g_prefs.getFloat("li_rh", NAN);
    if (!isfinite(last_outside_f)) last_outside_f = g_prefs.getFloat("lo_f", NAN);
    if (!isfinite(last_outside_rh)) last_outside_rh = g_prefs.getFloat("lo_rh", NAN);
    if (last_icon_id < 0) last_icon_id = (int32_t)g_prefs.getInt("icon", -1);
    if (last_status_crc == 0) last_status_crc = g_prefs.getUInt("st_crc", 0);
    if (!isfinite(last_published_inside_tempC)) last_published_inside_tempC = g_prefs.getFloat("pi_t", NAN);
    if (!isfinite(last_published_inside_rh)) last_published_inside_rh = g_prefs.getFloat("pi_rh", NAN);
    uint16_t pc = g_prefs.getUShort("pcount", 0);
    if (pc > 0) partial_counter = pc;
}
static inline void nvs_store_float(const char* key, float v) { g_prefs.putFloat(key, v); }
static inline void nvs_store_int(const char* key, int32_t v) { g_prefs.putInt(key, v); }
static inline void nvs_store_uint(const char* key, uint32_t v) { g_prefs.putUInt(key, v); }

static constexpr float THRESH_TEMP_F = 0.2f; // redraw/publish threshold in F
static constexpr float THRESH_TEMP_C_FROM_F = THRESH_TEMP_F / 1.8f; // ~0.111C
static constexpr float THRESH_RH = 1.0f; // percent

static void pump_network_ms(uint32_t duration_ms)
{
    unsigned long start = millis();
    while (millis() - start < duration_ms) {
        net_loop();
        #if USE_STATUS_PIXEL
        status_pixel_tick();
        #endif
        delay(10);
    }
}

#if USE_STATUS_PIXEL
// Status NeoPixel heartbeat
#ifndef STATUS_PIXEL_PIN
#ifdef PIN_NEOPIXEL
#define STATUS_PIXEL_PIN PIN_NEOPIXEL
#else
#define STATUS_PIXEL_PIN 18
#endif
#endif

static Adafruit_NeoPixel s_statusPixel(1, STATUS_PIXEL_PIN, NEO_GRB + NEO_KHZ800);
static uint32_t s_lastPixelMs = 0;
static uint8_t s_hue = 0;
static uint8_t s_breath = 0; // brightness phase for subtle breathing

static uint32_t color_wheel(uint8_t pos)
{
    pos = 255 - pos;
    if (pos < 85) {
        return s_statusPixel.Color(255 - pos * 3, 0, pos * 3);
    }
    if (pos < 170) {
        pos -= 85;
        return s_statusPixel.Color(0, pos * 3, 255 - pos * 3);
    }
    pos -= 170;
    return s_statusPixel.Color(pos * 3, 255 - pos * 3, 0);
}

static inline void status_pixel_begin()
{
    s_statusPixel.begin();
    s_statusPixel.setBrightness(8);
    s_statusPixel.show();
}

static inline void status_pixel_off()
{
    s_statusPixel.clear();
    s_statusPixel.show();
}

static inline void status_pixel_tick()
{
    uint32_t now = millis();
    if (now - s_lastPixelMs < 40) return; // slower update for smooth, slow cycle
    s_lastPixelMs = now;
    s_hue++;
    s_breath++;
    // Triangle wave 0..127..0 mapped to brightness range
    uint8_t amp = (s_breath < 128) ? s_breath : (uint8_t)(255 - s_breath);
    const uint8_t minB = 8;
    const uint8_t maxB = 64;
    uint8_t level = (uint8_t)(minB + ((uint16_t)amp * (maxB - minB) / 127));
    // Occasional brief flash for a bit of flair
    if ((s_hue & 0x3F) == 0) level = maxB;
    s_statusPixel.setBrightness(level);
    s_statusPixel.setPixelColor(0, color_wheel(s_hue));
    s_statusPixel.show();
}
#endif

static void emit_metrics_json(float tempC, float rhPct)
{
    BatteryStatus bs = read_battery_status();
    char ip_c[32];
    net_ip_cstr(ip_c, sizeof(ip_c));
    Serial.print('{');
    Serial.print("\"event\":\"metrics\",");
    Serial.print("\"ip\":\""); Serial.print(ip_c); Serial.print("\",");
    Serial.print("\"tempF\":"); Serial.print(isfinite(tempC) ? (tempC * 9.0/5.0 + 32.0) : NAN); Serial.print(',');
    Serial.print("\"rhPct\":"); Serial.print(isfinite(rhPct) ? rhPct : NAN); Serial.print(',');
    Serial.print("\"wifi\":"); Serial.print(net_wifi_is_connected() ? "true" : "false"); Serial.print(',');
    Serial.print("\"mqtt\":"); Serial.print(net_mqtt_is_connected() ? "true" : "false"); Serial.print(',');
    Serial.print("\"v\":"); Serial.print(bs.voltage, 2); Serial.print(',');
    Serial.print("\"pct\":"); Serial.print(bs.percent);
    Serial.println('}');
}

// Map reset reason and wakeup cause to short strings for debug publishing
static const char* reset_reason_str(esp_reset_reason_t r)
{
    switch (r) {
        case ESP_RST_POWERON: return "ESP_RST_POWERON";
        case ESP_RST_EXT: return "ESP_RST_EXT";
        case ESP_RST_SW: return "ESP_RST_SW";
        case ESP_RST_PANIC: return "ESP_RST_PANIC";
        case ESP_RST_INT_WDT: return "ESP_RST_INT_WDT";
        case ESP_RST_TASK_WDT: return "ESP_RST_TASK_WDT";
        case ESP_RST_WDT: return "ESP_RST_WDT";
        case ESP_RST_BROWNOUT: return "ESP_RST_BROWNOUT";
        case ESP_RST_DEEPSLEEP: return "ESP_RST_DEEPSLEEP";
        case ESP_RST_SDIO: return "ESP_RST_SDIO";
        default: return "ESP_RST_UNKNOWN";
    }
}

static const char* wakeup_cause_str(esp_sleep_wakeup_cause_t c)
{
    switch (c) {
        case ESP_SLEEP_WAKEUP_UNDEFINED: return "UNDEFINED";
        case ESP_SLEEP_WAKEUP_EXT0: return "EXT0";
        case ESP_SLEEP_WAKEUP_EXT1: return "EXT1";
        case ESP_SLEEP_WAKEUP_TIMER: return "TIMER";
        case ESP_SLEEP_WAKEUP_TOUCHPAD: return "TOUCHPAD";
        case ESP_SLEEP_WAKEUP_ULP: return "ULP";
        #ifdef ESP_SLEEP_WAKEUP_GPIO
        case ESP_SLEEP_WAKEUP_GPIO: return "GPIO";
        #endif
        #ifdef ESP_SLEEP_WAKEUP_UART
        case ESP_SLEEP_WAKEUP_UART: return "UART";
        #endif
        default: return "OTHER";
    }
}

static void handle_serial_command_line(const String& line)
{
    String cmd = line;
    cmd.trim();
    if (cmd.length() == 0) return;
    // Split first token
    int sp = cmd.indexOf(' ');
    String op = sp >= 0 ? cmd.substring(0, sp) : cmd;
    String args = sp >= 0 ? cmd.substring(sp + 1) : String();
    op.toLowerCase();
    if (op == "help" || op == "h" || op == "?") {
        Serial.println(F("Commands: help | status | metrics | sleep <sec> | reboot | wifi | mqtt | pub <tempF> <rh%>"));
        return;
    }
    if (op == "status") {
        char ip_c[32];
        net_ip_cstr(ip_c, sizeof(ip_c));
        BatteryStatus bs = read_battery_status();
        Serial.printf("status ip=%s wifi=%s mqtt=%s v=%.2f pct=%d partial=%u\n",
                      ip_c,
                      net_wifi_is_connected() ? "up" : "down",
                      net_mqtt_is_connected() ? "up" : "down",
                      bs.voltage, bs.percent, (unsigned)partial_counter);
        return;
    }
    if (op == "metrics") {
        InsideReadings latest = read_inside_sensors();
        emit_metrics_json(latest.temperatureC, latest.humidityPct);
        return;
    }
    if (op == "sleep") {
        uint32_t sec = args.toInt();
        if (sec == 0) { Serial.println(F("ERR sleep: provide seconds > 0")); return; }
        Serial.printf("Sleeping for %us\n", (unsigned)sec);
        nvs_end_cache();
#if USE_STATUS_PIXEL
        status_pixel_off();
#endif
        // Optionally gate off display/sensor rails if defined
#if defined(EINK_EN_PIN)
        pinMode(EINK_EN_PIN, OUTPUT);
        digitalWrite(EINK_EN_PIN, LOW);
#endif
#ifdef SENSORS_EN_PIN
        pinMode(SENSORS_EN_PIN, OUTPUT);
        digitalWrite(SENSORS_EN_PIN, LOW);
#endif
        // Cleanly disconnect and power down radios before sleeping
        net_prepare_for_sleep();
        go_deep_sleep_seconds(sec);
        return;
    }
    if (op == "reboot" || op == "reset") {
        Serial.println(F("Rebooting..."));
        delay(50);
        ESP.restart();
        return;
    }
    if (op == "wifi") {
        Serial.println(F("WiFi: reconnecting..."));
        WiFi.disconnect(true, true);
        delay(100);
        ensure_wifi_connected();
        return;
    }
    if (op == "wificlear") {
        Serial.println(F("WiFi: clearing provisioned credentials and rebooting..."));
        bool ok = net_wifi_clear_provisioning();
        Serial.printf("WiFi: clear %s\n", ok ? "ok" : "failed");
        delay(50);
        ESP.restart();
        return;
    }
    if (op == "mqtt") {
        Serial.println(F("MQTT: reconnecting..."));
        ensure_mqtt_connected();
        return;
    }
    if (op == "pub") {
        // pub <tempF> <rh%>
        float tf = NAN, rh = NAN;
        int sp2 = args.indexOf(' ');
        if (sp2 > 0) {
            tf = args.substring(0, sp2).toFloat();
            rh = args.substring(sp2 + 1).toFloat();
        }
        if (!isfinite(tf) || !isfinite(rh)) { Serial.println(F("ERR pub: usage pub <tempF> <rh%>")); return; }
        float tc = (tf - 32.0f) * (5.0f/9.0f);
        net_publish_inside(tc, rh);
        Serial.printf("Published inside tempC=%.2f rh=%.0f\n", tc, rh);
        return;
    }
    Serial.println(F("ERR: unknown command (try 'help')"));
}

#if USE_DISPLAY
static void draw_static_chrome()
{
    // Frame and header linework
    display.fillScreen(GxEPD_WHITE);
    display.drawRect(0, 0, EINK_WIDTH, EINK_HEIGHT, GxEPD_BLACK);
    display.drawLine(1, 18, EINK_WIDTH-2, 18, GxEPD_BLACK);
    // Extend the center divider to the bottom frame to match the simulator
    display.drawLine(125, 18, 125, EINK_HEIGHT-2, GxEPD_BLACK);
    // Draw a thin horizontal rule above the bottom status/weather rows (aligned with sim)
    display.drawLine(1, STATUS_[1] - 20, EINK_WIDTH-2, STATUS_[1] - 20, GxEPD_BLACK);

    // Header: room name left, time will be drawn separately
    display.setTextColor(GxEPD_BLACK);
    display.setTextSize(1);
    display.setCursor(6, 13);
    display.print(ROOM_NAME);

    // Section labels
    display.setCursor(6, 22);
    display.print(F("INSIDE"));
    display.setCursor(131, 22);
    display.print(F("OUTSIDE"));
}

static inline int16_t text_width_default_font(const char* s, uint8_t size)
{
    // Default 5x7 font is 6 px advance per char at size 1
    int16_t count = 0;
    for (const char* p = s; *p; ++p) count++;
    return count * 6 * size;
}

// Forward declaration for status drawing used by maybe_redraw_status
static void draw_status_line(const BatteryStatus& bs, const char* ip_cstr);

template<typename DrawFn>
static inline void draw_in_region(const int rect[4], DrawFn drawFn)
{
    const int16_t x = rect[0];
    const int16_t y = rect[1];
    const int16_t w = rect[2];
    const int16_t h = rect[3];
    display.setPartialWindow(x, y, w, h);
    display.firstPage();
    do {
        display.fillScreen(GxEPD_WHITE);
        drawFn(x, y, w, h);
        #if USE_STATUS_PIXEL
        status_pixel_tick();
        #endif
    } while (display.nextPage());
}

static inline void draw_right_aligned_text_in_rect(const int rect[4], const char* text, uint8_t textSize, int16_t paddingRight, int16_t baselineOffset)
{
    draw_in_region(rect, [&](int16_t x, int16_t y, int16_t w, int16_t h){
        display.setTextColor(GxEPD_BLACK);
        display.setTextSize(textSize);
        int16_t tw = text_width_default_font(text, textSize);
        int16_t rx = x + w - paddingRight - tw;
        int16_t by = y + h - baselineOffset;
        display.setCursor(rx, by);
        display.print(text);
    });
}

static inline void draw_temp_number_and_units(const int rect[4], const char* temp_f)
{
    // Reserve a small units strip on the right so units do not shift as number width changes
    const int16_t units_w = 14; // pixels
    int num_rect[4] = { rect[0], rect[1], rect[2] - units_w, rect[3] };
    int units_rect[4] = { rect[0] + rect[2] - units_w, rect[1], units_w, rect[3] };

    // Center numeric in its sub-rect
    draw_in_region(num_rect, [&](int16_t x, int16_t y, int16_t w, int16_t h){
        display.setTextColor(GxEPD_BLACK);
        display.setTextSize(2);
        int16_t tw = text_width_default_font(temp_f, 2);
        int16_t rx = x + (w - tw) / 2;
        int16_t by = y + h - 4;
        display.setCursor(rx, by);
        display.print(temp_f);
    });

    // Draw degree symbol and F in small font inside the units sub-rect
    draw_in_region(units_rect, [&](int16_t x, int16_t y, int16_t w, int16_t h){
        display.setTextColor(GxEPD_BLACK);
        display.setTextSize(1);
        int16_t by = y + h - 4;
        display.setCursor(x + 1, by);
        display.print("\xF8");
        display.setCursor(x + 7, by);
        display.print("F");
    });
}

static inline uint32_t fast_crc32(const uint8_t* data, size_t len)
{
    // Tiny CRC32 (polynomial 0xEDB88320), suitable for short status strings
    uint32_t crc = 0xFFFFFFFFu;
    for (size_t i = 0; i < len; ++i) {
        uint32_t byte = data[i];
        crc ^= byte;
        for (int k = 0; k < 8; ++k) {
            uint32_t mask = -(crc & 1u);
            crc = (crc >> 1) ^ (0xEDB88320u & mask);
        }
    }
    return ~crc;
}

template<typename DrawFn>
static inline bool maybe_redraw_numeric(const int rect[4], float currentValue, float& lastValue, float threshold, DrawFn drawFn)
{
    bool should = false;
    if (!isnan(currentValue) && (!isfinite(lastValue) || fabsf(currentValue - lastValue) >= threshold)) should = true;
    if (should) { drawFn(); lastValue = currentValue; return true; }
    return false;
}

template<typename T, typename DrawFn>
static inline bool maybe_redraw_value(const int rect[4], const T& currentValue, T& lastValue, DrawFn drawFn)
{
    if (currentValue != lastValue) { drawFn(); lastValue = currentValue; return true; }
    return false;
}

static inline bool maybe_redraw_status(const BatteryStatus& bs, const char* ip_cstr, const int rect[4])
{
    char buf[96];
    snprintf(buf, sizeof(buf), "IP %s  Batt %.2fV %d%%  ~%dd",
             ip_cstr, bs.voltage, bs.percent, bs.estimatedDays);
    uint32_t crc = fast_crc32((const uint8_t*)buf, strlen(buf));
    if (crc != last_status_crc) {
        draw_status_line(bs, ip_cstr);
        last_status_crc = crc;
        return true;
    }
    return false;
}

static void make_short_condition_cstr(const char* weather, char* out, size_t out_size)
{
    if (!out || out_size == 0) return;
    out[0] = '\0';
    if (!weather) return;
    // Skip leading spaces
    const char* p = weather;
    while (*p == ' ' || *p == '\t') p++;
    // Copy until next separator or end
    size_t i = 0;
    while (*p && i < out_size - 1) {
        char c = *p;
        if (c == ' ' || c == '\t' || c == ',' || c == ';' || c == ':' || c == '/') break;
        out[i++] = c;
        p++;
    }
    out[i] = '\0';
}

static void draw_header_time(const char* time_str)
{
    const int16_t x = HEADER_TIME[0];
    const int16_t y = HEADER_TIME[1];
    const int16_t w = HEADER_TIME[2];
    const int16_t h = HEADER_TIME[3];
    draw_in_region(HEADER_TIME, [&](int16_t xx, int16_t yy, int16_t ww, int16_t hh){
        display.setTextColor(GxEPD_BLACK);
        display.setTextSize(1);
        int16_t tw = text_width_default_font(time_str, 1);
        int16_t rx = xx + ww - 2 - tw;
        int16_t by = yy + hh - 2; // baseline
        display.setCursor(rx, by);
        display.print(time_str);
    });
}

static void draw_status_line(const BatteryStatus& bs, const char* ip_cstr)
{
    const int16_t x = STATUS_[0];
    const int16_t y = STATUS_[1];
    const int16_t w = STATUS_[2];
    const int16_t h = STATUS_[3];
    draw_in_region(STATUS_, [&](int16_t xx, int16_t yy, int16_t ww, int16_t hh){
        display.setTextColor(GxEPD_BLACK);
        display.setTextSize(1);
        int16_t cx = xx + 2;
        int16_t cy = yy + hh - 4;
        // Low battery cue: draw battery if percent known
        if (bs.percent >= 0) {
            int16_t bx = cx;
            int16_t by = yy + 1; // nudge up 1px to center
            int16_t bw = 13;
            int16_t bh = 7;
            display.drawRect(bx, by, bw, bh, GxEPD_BLACK);
            display.fillRect(bx + bw, by + 2, 2, 3, GxEPD_BLACK);
            int16_t fillw = (int16_t)((bw - 2) * (bs.percent / 100.0f) + 0.5f);
            if (fillw > 0) display.fillRect(bx + 1, by + 1, fillw, bh - 2, GxEPD_BLACK);
            cx += bw + 6;
        }
        // Right-aligned IP using bounds for exact fitting
        char right[48];
        snprintf(right, sizeof(right), "IP %s", ip_cstr);
        int16_t bx, by; uint16_t bw, bh;
        display.getTextBounds(right, 0, 0, &bx, &by, &bw, &bh);
        int16_t rx = xx + ww - 2 - (int16_t)bw;
        // Choose, using bounds, which left label to print based on available width
        char left_full[64];
        char left_nobatt[64];
        char left_tail[32];
        snprintf(left_full, sizeof(left_full), "Batt %.2fV %d%% | ~%dd", bs.voltage, bs.percent, bs.estimatedDays);
        snprintf(left_nobatt, sizeof(left_nobatt), "%.2fV %d%% | ~%dd", bs.voltage, bs.percent, bs.estimatedDays);
        snprintf(left_tail, sizeof(left_tail), "%d%% | ~%dd", bs.percent, bs.estimatedDays);
        int16_t available = rx - cx - 2;
        const char* to_print = left_full;
        display.getTextBounds(to_print, 0, 0, &bx, &by, &bw, &bh);
        if ((int16_t)bw > available) {
            to_print = left_nobatt;
            display.getTextBounds(to_print, 0, 0, &bx, &by, &bw, &bh);
        }
        if ((int16_t)bw > available) {
            display.getTextBounds(left_tail, 0, 0, &bx, &by, &bw, &bh);
            if ((int16_t)bw <= available) {
                to_print = left_tail;
            } else {
                to_print = "";
            }
        }
        display.setCursor(cx, cy);
        display.print(to_print);
        display.setCursor(rx, cy);
        display.print(right);
    });
}

static void draw_values(const char* in_temp_f, const char* in_rh,
                        const char* out_temp_f, const char* out_rh,
                        const char* time_str,
                        const char* status)
{
    display.setTextColor(GxEPD_BLACK);
    // Inside temp: numeric right-aligned, units drawn separately
    draw_temp_number_and_units(INSIDE_TEMP, in_temp_f);

    // Inside RH
    display.setTextSize(1);
    display.setCursor(INSIDE_RH[0], INSIDE_RH[1]);
    display.print(in_rh);
    display.print("% RH");

    // No duplicate inside time; header time is drawn by draw_header_time

    // Outside temp: numeric right-aligned, units drawn separately
    draw_temp_number_and_units(OUT_TEMP, out_temp_f);

    // Other fields (condition, RH, wind) drawn with their partial updaters

    // Status line drawn separately by partial
}

static IconId map_weather_to_icon(const char* w)
{
    String s(w);
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

static void draw_weather_icon_region(const char* weather)
{
    const int16_t x = OUT_ICON[0];
    const int16_t y = OUT_ICON[1];
    const int16_t w = OUT_ICON[2];
    const int16_t h = OUT_ICON[3];
    display.fillRect(x, y, w, h, GxEPD_WHITE);
    int16_t ix = x + (w - ICON_W) / 2;
    int16_t iy = y + (h - ICON_H) / 2;
    draw_icon(display, ix, iy, map_weather_to_icon(weather), GxEPD_BLACK);
}

static void full_refresh()
{
    display.setFullWindow();
    display.firstPage();
    do {
        draw_static_chrome();
        InsideReadings r = read_inside_sensors();
        #if USE_STATUS_PIXEL
        status_pixel_tick();
        #endif
        char in_temp[16];
        char in_rh[16];
        snprintf(in_temp, sizeof(in_temp), isfinite(r.temperatureC) ? "%.1f" : "--", r.temperatureC * 9.0/5.0 + 32.0);
        snprintf(in_rh, sizeof(in_rh), isfinite(r.humidityPct) ? "%.0f" : "--", r.humidityPct);
        OutsideReadings o = net_get_outside();
        char out_temp[16];
        char out_rh[16];
        if (o.validTemp && isfinite(o.temperatureC)) {
            snprintf(out_temp, sizeof(out_temp), "%.1f", o.temperatureC * 9.0/5.0 + 32.0);
        } else if (isfinite(last_outside_f)) {
            snprintf(out_temp, sizeof(out_temp), "%.1f", last_outside_f);
        } else {
            snprintf(out_temp, sizeof(out_temp), "--");
        }
        if (o.validHum && isfinite(o.humidityPct)) {
            snprintf(out_rh, sizeof(out_rh), "%.0f", o.humidityPct);
        } else if (isfinite(last_outside_rh)) {
            snprintf(out_rh, sizeof(out_rh), "%.0f", last_outside_rh);
        } else {
            snprintf(out_rh, sizeof(out_rh), "--");
        }
        BatteryStatus bs = read_battery_status();
        char status[64];
        snprintf(status, sizeof(status), "IP %s  Batt %.2fV %d%%  ~%dd",
                 net_ip().c_str(), bs.voltage, bs.percent, bs.estimatedDays);
        draw_values(in_temp, in_rh, out_temp, out_rh, "", status);
        if (o.validWeather) {
            draw_weather_icon_region(o.weather);
            last_icon_id = (int32_t)map_weather_to_icon(o.weather);
        } else if (last_icon_id >= 0) {
            // Draw last known icon
            int16_t x = OUT_ICON[0];
            int16_t y = OUT_ICON[1];
            int16_t w = OUT_ICON[2];
            int16_t h = OUT_ICON[3];
            int16_t ix = x + (w - ICON_W) / 2;
            int16_t iy = y + (h - ICON_H) / 2;
            draw_icon(display, ix, iy, (IconId)last_icon_id, GxEPD_BLACK);
        }
        // Outside condition short token (left-top)
        if (o.validWeather) {
            char sc[24];
            make_short_condition_cstr(o.weather, sc, sizeof(sc));
            display.setTextColor(GxEPD_BLACK);
            display.setTextSize(1);
            display.setCursor(OUT_ROW1_L[0], OUT_ROW1_L[1]);
            display.print(sc);
        }
        // Outside RH (left-bottom)
        if (o.validHum || isfinite(last_outside_rh)) {
            display.setTextColor(GxEPD_BLACK);
            display.setTextSize(1);
            display.setCursor(OUT_ROW2_L[0], OUT_ROW2_L[1]);
            display.print(out_rh);
            display.print("% RH");
        }
        // Outside wind mph (right-bottom)
        if (o.validWind && isfinite(o.windMps)) {
            float mph = o.windMps * 2.237f;
            char ws[24];
            snprintf(ws, sizeof(ws), "%.1f mph", mph);
            display.setTextColor(GxEPD_BLACK);
            display.setTextSize(1);
            display.setCursor(OUT_ROW2_R[0], OUT_ROW2_R[1]);
            display.print(ws);
        }
    } while (display.nextPage());
}

static void partial_update_inside_temp(const char* in_temp_f, char trend)
{
    draw_in_region(INSIDE_TEMP, [&](int16_t x, int16_t y, int16_t w, int16_t h){
        // Numeric + units split: redraw both sub-rects from this region pass
        // Numeric
        const int16_t units_w = 14;
        int num_rect[4] = { x, y, w - units_w, h };
        int units_rect[4] = { x + w - units_w, y, units_w, h };
        // numeric
        display.setTextColor(GxEPD_BLACK);
        display.setTextSize(2);
        int16_t tw2 = text_width_default_font(in_temp_f, 2);
        int16_t rx = num_rect[0] + num_rect[2] - 2 - tw2;
        int16_t by = num_rect[1] + num_rect[3] - 4;
        display.setCursor(rx, by);
        display.print(in_temp_f);
        // units
        display.setTextSize(1);
        int16_t uby = units_rect[1] + units_rect[3] - 4;
        display.setCursor(units_rect[0] + 1, uby);
        display.print("\xF8");
        display.setCursor(units_rect[0] + 7, uby);
        display.print("F");
        // Trend arrow/simple indicator at left
        if (trend == '+') { display.setCursor(x + 2, y); display.print("^"); }
        else if (trend == '-') { display.setCursor(x + 2, y); display.print("v"); }
    });
}

static void partial_update_outside_temp(const char* out_temp_f, char trend)
{
    draw_in_region(OUT_TEMP, [&](int16_t x, int16_t y, int16_t w, int16_t h){
        const int16_t units_w = 14;
        int num_rect[4] = { x, y, w - units_w, h };
        int units_rect[4] = { x + w - units_w, y, units_w, h };
        display.setTextColor(GxEPD_BLACK);
        display.setTextSize(2);
        int16_t tw2b = text_width_default_font(out_temp_f, 2);
        int16_t rx = num_rect[0] + num_rect[2] - 2 - tw2b;
        int16_t by = num_rect[1] + num_rect[3] - 4;
        display.setCursor(rx, by);
        display.print(out_temp_f);
        display.setTextSize(1);
        int16_t uby = units_rect[1] + units_rect[3] - 4;
        display.setCursor(units_rect[0] + 1, uby);
        display.print("\xF8");
        display.setCursor(units_rect[0] + 7, uby);
        display.print("F");
        if (trend == '+') { display.setCursor(x + 2, y); display.print("^"); }
        else if (trend == '-') { display.setCursor(x + 2, y); display.print("v"); }
    });
}

static void partial_update_outside_rh(const char* out_rh)
{
    draw_in_region(OUT_ROW2_L, [&](int16_t x, int16_t y, int16_t w, int16_t h){
        display.setTextColor(GxEPD_BLACK);
        display.setTextSize(1);
        display.setCursor(x, y);
        display.print(out_rh);
        display.print("% RH");
    });
}

static void partial_update_inside_rh(const char* in_rh)
{
    draw_in_region(INSIDE_RH, [&](int16_t x, int16_t y, int16_t w, int16_t h){
        display.setTextColor(GxEPD_BLACK);
        display.setTextSize(1);
        display.setCursor(x, y);
        display.print(in_rh);
        display.print("% RH");
    });
}

static void partial_update_weather_icon(const char* weather)
{
    draw_in_region(OUT_ICON, [&](int16_t, int16_t, int16_t, int16_t){
        draw_weather_icon_region(weather);
    });
}

static void partial_update_outside_wind(const char* wind_str)
{
    draw_in_region(OUT_ROW2_R, [&](int16_t x, int16_t y, int16_t, int16_t){
        display.setTextColor(GxEPD_BLACK);
        display.setTextSize(1);
        display.setCursor(x, y);
        display.print(wind_str);
    });
}

static void partial_update_outside_condition(const char* short_condition)
{
    draw_in_region(OUT_ROW1_L, [&](int16_t x, int16_t y, int16_t, int16_t){
        display.setTextColor(GxEPD_BLACK);
        display.setTextSize(1);
        display.setCursor(x, y);
        display.print(short_condition);
    });
}

static void partial_update_outside_hilo(float highC, float lowC)
{
    const int16_t x = OUT_ROW2_R[0];
    const int16_t y = OUT_ROW2_R[1];
    const int16_t w = OUT_ROW2_R[2];
    const int16_t h = OUT_ROW2_R[3];
    display.setPartialWindow(x, y, w, h);
    display.firstPage();
    do {
        display.fillScreen(GxEPD_WHITE);
        display.setTextColor(GxEPD_BLACK);
        display.setTextSize(1);
        display.setCursor(x, y);
        if (isfinite(highC) && isfinite(lowC)) {
            char buf[40];
            float hf = highC * 9.0f/5.0f + 32.0f;
            float lf = lowC * 9.0f/5.0f + 32.0f;
            snprintf(buf, sizeof(buf), "H %.1f\xF8  L %.1f\xF8", hf, lf);
            display.print(buf);
        }
    } while (display.nextPage());
}
#endif // USE_DISPLAY

void setup() {
    int64_t t0_us = esp_timer_get_time();
    Serial.begin(115200);
    delay(100);
    Serial.println(F("ESP32 eInk Room Node boot"));

#if USE_STATUS_PIXEL
    status_pixel_begin();
    uint32_t t0 = millis();
    while (millis() - t0 < 200) {
        status_pixel_tick();
        delay(10);
    }
#endif

    #if USE_DISPLAY
    #ifdef EINK_EN_PIN
    pinMode(EINK_EN_PIN, OUTPUT);
    digitalWrite(EINK_EN_PIN, HIGH); // enable panel power if gated
    delay(5);
    #endif
    display.init(0);
    display.setRotation(1); // landscape 250x122 coordinate system
    #endif
    nvs_begin_cache();
    nvs_load_cache_if_unset();

    // Connect Wi-Fi then MQTT while capturing timestamps
    ensure_wifi_connected();
    int64_t t1_us = esp_timer_get_time();
    ensure_mqtt_connected();
    int64_t t2_us = esp_timer_get_time();

    // Measure sensor read duration (first read post-boot)
    int64_t t_sense_start_us = esp_timer_get_time();
    InsideReadings _sensor_probe = read_inside_sensors();
    (void)_sensor_probe;
    int64_t t3_us = esp_timer_get_time();

    // Compute scheduled sleep based on build-time mode
    uint32_t sleep_scheduled_ms = 0;
    #if DEV_CYCLE_MODE
    sleep_scheduled_ms = (uint32_t)DEV_SLEEP_SEC * 1000UL;
    #else
    sleep_scheduled_ms = (uint32_t)WAKE_INTERVAL_SEC * 1000UL;
    #endif

    // Build and publish debug JSON with wake metrics and causes
    if (net_mqtt_is_connected()) {
        char dbg[320];
        uint32_t ms_boot_to_wifi = (uint32_t)((t1_us - t0_us) / 1000);
        uint32_t ms_wifi_to_mqtt = (uint32_t)((t2_us - t1_us) / 1000);
        uint32_t ms_sensor_read = (uint32_t)((t3_us - t_sense_start_us) / 1000);
        // Measure publish time using a non-retained probe topic
        int64_t pub_probe_start_us = esp_timer_get_time();
        net_publish_debug_probe("1", false);
        uint32_t ms_publish = (uint32_t)((esp_timer_get_time() - pub_probe_start_us) / 1000);
        uint32_t deep_sleep_us = sleep_scheduled_ms * 1000UL;
        snprintf(dbg, sizeof(dbg),
                 "{\"ms_boot_to_wifi\":%u,\"ms_wifi_to_mqtt\":%u,\"ms_sensor_read\":%u,\"ms_publish\":%u,\"sleep_scheduled_ms\":%u,\"deep_sleep_us\":%u,\"reset_reason\":\"%s\",\"wakeup_cause\":\"%s\"}",
                 ms_boot_to_wifi,
                 ms_wifi_to_mqtt,
                 ms_sensor_read,
                 ms_publish,
                 sleep_scheduled_ms,
                 deep_sleep_us,
                 reset_reason_str(esp_reset_reason()),
                 wakeup_cause_str(esp_sleep_get_wakeup_cause()));
        net_publish_debug_json(dbg, false);
    }

    // Allow retained MQTT to arrive quickly for outside readings
    pump_network_ms(800);

    // Publish HA discovery once we have MQTT so entities auto-register in Home Assistant
    if (net_mqtt_is_connected()) {
        net_publish_ha_discovery();
    }

    #if USE_DISPLAY
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
            if (d >= THRESH_TEMP_F) trend_in = '+'; else if (d <= -THRESH_TEMP_F) trend_in = '-';
        }
        // Only redraw inside temp when changed beyond threshold
        maybe_redraw_numeric(INSIDE_TEMP, now_in_f, last_inside_f, THRESH_TEMP_F, [&](){
            partial_update_inside_temp(in_temp, trend_in);
        });
        if (isfinite(last_inside_f)) nvs_store_float("li_f", last_inside_f);
        // Inside RH partial update + publish only when changed beyond thresholds
        if (isfinite(r.humidityPct)) {
            char in_rh_str[16];
            snprintf(in_rh_str, sizeof(in_rh_str), "%.0f", r.humidityPct);
            maybe_redraw_numeric(INSIDE_RH, r.humidityPct, last_inside_rh, THRESH_RH, [&](){
                partial_update_inside_rh(in_rh_str);
            });
            if (isfinite(last_inside_rh)) nvs_store_float("li_rh", last_inside_rh);
        }
        if (isfinite(r.temperatureC) && isfinite(r.humidityPct)) {
            bool temp_changed = (!isfinite(last_published_inside_tempC)) || fabsf(r.temperatureC - last_published_inside_tempC) >= THRESH_TEMP_C_FROM_F;
            bool rh_changed = (!isfinite(last_published_inside_rh)) || fabsf(r.humidityPct - last_published_inside_rh) >= THRESH_RH;
            if (temp_changed || rh_changed) {
                net_publish_inside(r.temperatureC, r.humidityPct);
                last_published_inside_tempC = r.temperatureC;
                last_published_inside_rh = r.humidityPct;
                nvs_store_float("pi_t", last_published_inside_tempC);
                nvs_store_float("pi_rh", last_published_inside_rh);
            }
        }

        OutsideReadings o = net_get_outside();
        if (o.validTemp) {
            char out_temp[16];
            snprintf(out_temp, sizeof(out_temp), "%.1f", o.temperatureC * 9.0/5.0 + 32.0);
            char trend_out = '0';
            float now_out_f = o.temperatureC * 9.0f/5.0f + 32.0f;
            if (isfinite(last_outside_f)) {
                float d = now_out_f - last_outside_f;
                if (d >= THRESH_TEMP_F) trend_out = '+'; else if (d <= -THRESH_TEMP_F) trend_out = '-';
            }
            bool temp_changed = !isfinite(last_outside_f) || fabsf(now_out_f - last_outside_f) >= THRESH_TEMP_F;
            if (temp_changed && o.validHum && isfinite(o.humidityPct)) {
                // Merge redraws: update temp and RH in same wake when both changed
                maybe_redraw_numeric(OUT_TEMP, now_out_f, last_outside_f, THRESH_TEMP_F, [&](){
                    partial_update_outside_temp(out_temp, trend_out);
                });
                char out_rh2[16]; snprintf(out_rh2, sizeof(out_rh2), "%.0f", o.humidityPct);
                maybe_redraw_numeric(OUT_ROW2_L, o.humidityPct, last_outside_rh, THRESH_RH, [&](){
                    partial_update_outside_rh(out_rh2);
                });
            } else {
                maybe_redraw_numeric(OUT_TEMP, now_out_f, last_outside_f, THRESH_TEMP_F, [&](){
                    partial_update_outside_temp(out_temp, trend_out);
                });
            }
            if (isfinite(last_outside_f)) nvs_store_float("lo_f", last_outside_f);
        }
        if (o.validHum) {
            char out_rh[16];
            snprintf(out_rh, sizeof(out_rh), "%.0f", o.humidityPct);
            maybe_redraw_numeric(OUT_ROW2_L, o.humidityPct, last_outside_rh, THRESH_RH, [&](){
                partial_update_outside_rh(out_rh);
            });
            if (isfinite(last_outside_rh)) nvs_store_float("lo_rh", last_outside_rh);
        }
        if (o.validWeather) {
            IconId id = map_weather_to_icon(o.weather);
            maybe_redraw_value<int32_t>(OUT_ICON, (int32_t)id, last_icon_id, [&](){
                partial_update_weather_icon(o.weather);
            });
            nvs_store_int("icon", last_icon_id);
            char sc[24];
            make_short_condition_cstr(o.weather, sc, sizeof(sc));
            partial_update_outside_condition(sc);
        }
        if (o.validWind && isfinite(o.windMps)) {
            float mph = o.windMps * 2.237f;
            char ws[24];
            snprintf(ws, sizeof(ws), "%.1f mph", mph);
            partial_update_outside_wind(ws);
        }
        // H/L omitted to avoid overlap with wind in right-bottom
        // Update header time and status every wake (status only if changed)
        draw_header_time("10:32");
        BatteryStatus bs = read_battery_status();
        char ip_c[32];
        net_ip_cstr(ip_c, sizeof(ip_c));
        if (maybe_redraw_status(bs, ip_c, STATUS_)) {
            nvs_store_uint("st_crc", last_status_crc);
        }
        // Publish battery metrics once per wake
        if (isfinite(bs.voltage) && bs.percent >= 0) {
            net_publish_battery(bs.voltage, bs.percent);
        }
    }
    #else
    // Headless mode: no display; still connect, read sensors, publish, and sleep
    InsideReadings r = read_inside_sensors();
    if (isfinite(r.temperatureC) && isfinite(r.humidityPct)) {
        bool temp_changed = (!isfinite(last_published_inside_tempC)) || fabsf(r.temperatureC - last_published_inside_tempC) >= THRESH_TEMP_C_FROM_F;
        bool rh_changed = (!isfinite(last_published_inside_rh)) || fabsf(r.humidityPct - last_published_inside_rh) >= THRESH_RH;
        if (temp_changed || rh_changed) {
            net_publish_inside(r.temperatureC, r.humidityPct);
            last_published_inside_tempC = r.temperatureC;
            last_published_inside_rh = r.humidityPct;
            nvs_store_float("pi_t", last_published_inside_tempC);
            nvs_store_float("pi_rh", last_published_inside_rh);
        }
    }
    // Publish a headless status heartbeat to aid validation
    {
        String ip = net_ip();
        BatteryStatus bs = read_battery_status();
        char payload[96];
        snprintf(payload, sizeof(payload), "headless=1 ip=%s v=%.2f pct=%d", ip.c_str(), bs.voltage, bs.percent);
        net_publish_status(payload, true);
        if (isfinite(bs.voltage) && bs.percent >= 0) {
            net_publish_battery(bs.voltage, bs.percent);
        }
    }
    #endif

    // Emit one metrics JSON line over USB for monitor scripts
    {
        InsideReadings latest = read_inside_sensors();
        emit_metrics_json(latest.temperatureC, latest.humidityPct);
    }

    partial_counter++;
    // Persist partial refresh cadence so it survives reset
    g_prefs.putUShort("pcount", partial_counter);
    // Log awake duration and planned sleep for diagnostics
    Serial.printf("Awake ms: %lu\n", (unsigned long)millis());
    #if DEV_NO_SLEEP
    Serial.println("DEV_NO_SLEEP=1: staying awake for debugging");
    while (true) {
        net_loop();
        // Handle line-oriented serial commands
        static String buf;
        while (Serial.available() > 0) {
            int ch = Serial.read();
            if (ch == '\r') continue;
            if (ch == '\n') {
                handle_serial_command_line(buf);
                buf = "";
            } else if (buf.length() < 96) {
                buf += (char)ch;
            }
        }
        // Periodic USB metrics while debugging
        static uint32_t last_metrics = 0;
        if (millis() - last_metrics > 2000) {
            InsideReadings latest = read_inside_sensors();
            emit_metrics_json(latest.temperatureC, latest.humidityPct);
            last_metrics = millis();
        }
#if USE_STATUS_PIXEL
        status_pixel_tick();
#endif
        delay(50);
    }
    #else
    #if DEV_CYCLE_MODE
    Serial.printf("Dev cycle: sleeping for %us\n", (unsigned)DEV_SLEEP_SEC);
    nvs_end_cache();
#if USE_STATUS_PIXEL
    status_pixel_off();
#endif
    // Power down any gated rails between wakes
#if USE_DISPLAY
#ifdef EINK_EN_PIN
    digitalWrite(EINK_EN_PIN, LOW);
#endif
#endif
#ifdef SENSORS_EN_PIN
    pinMode(SENSORS_EN_PIN, OUTPUT);
    digitalWrite(SENSORS_EN_PIN, LOW);
#endif
    net_prepare_for_sleep();
    go_deep_sleep_seconds(DEV_SLEEP_SEC);
    #else
    Serial.printf("Sleeping for %us\n", (unsigned)WAKE_INTERVAL_SEC);
    #if USE_DISPLAY
    #ifdef EINK_EN_PIN
    // Power down panel between wakes if gated to save sleep current
    digitalWrite(EINK_EN_PIN, LOW);
    #endif
    #endif
    nvs_end_cache();
#if USE_STATUS_PIXEL
    status_pixel_off();
#endif
    // Optionally gate off sensor rail if present
#ifdef SENSORS_EN_PIN
    pinMode(SENSORS_EN_PIN, OUTPUT);
    digitalWrite(SENSORS_EN_PIN, LOW);
#endif
    net_prepare_for_sleep();
    go_deep_sleep_seconds(WAKE_INTERVAL_SEC);
    #endif
    #endif
}

void loop() {
    // not used; we deep-sleep from setup
    delay(1000);
}



