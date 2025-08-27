// full_refresh_v2 moved below includes and constants
#include <esp_system.h>
#include <esp_timer.h>
#include <esp_heap_caps.h>
#include <cstdio>

// Copyright 2024 Justin

#include <Arduino.h>
#include <Preferences.h>

#include "config.h"
#if USE_STATUS_PIXEL
#include <Adafruit_NeoPixel.h>
#endif
#if USE_DISPLAY
#include <GxEPD2_BW.h>
#endif

#if USE_DISPLAY
#include "display_layout.h"
#include "icons.h"
#include "ui_ops_generated.h"
#include "ui_generated.h"
#endif
#include "generated_config.h"
#include "net.h"
#include "power.h"
#include "sensors.h"
#include "system_manager.h"
#if USE_DISPLAY
#include "display_manager.h"
#endif

// Constant aliases for backward compatibility
// Map old names to new arrays from display_layout.h with RECT_ prefix
#define HEADER_TIME RECT_HEADER_TIME_CENTER
#define HEADER_CENTER RECT_HEADER_TIME_CENTER
#define HEADER_TIME_CENTER RECT_HEADER_TIME_CENTER
#define INSIDE_TEMP RECT_INSIDE_TEMP
#define INSIDE_RH RECT_INSIDE_HUMIDITY
#define INSIDE_HUMIDITY RECT_INSIDE_HUMIDITY
#define INSIDE_PRESSURE RECT_INSIDE_PRESSURE
#define INSIDE_ROW2_L RECT_INSIDE_PRESSURE
#define OUT_TEMP RECT_OUT_TEMP
#define OUT_WEATHER RECT_OUT_WEATHER
#define OUT_ROW1_L RECT_OUT_WEATHER
#define OUT_PRESSURE RECT_OUT_PRESSURE
#define OUT_ROW1_R RECT_OUT_PRESSURE
#define OUT_ICON RECT_WEATHER_ICON
#define WEATHER_ICON RECT_WEATHER_ICON
#define OUT_HUMIDITY RECT_OUT_HUMIDITY
#define OUT_ROW2_L RECT_OUT_HUMIDITY
#define OUT_WIND RECT_OUT_WIND
#define OUT_ROW2_R RECT_OUT_WIND
#define FOOTER_L RECT_FOOTER_STATUS
#define FOOTER_STATUS RECT_FOOTER_STATUS
#define STATUS_ RECT_FOOTER_STATUS
#define FOOTER_WEATHER RECT_FOOTER_WEATHER

// Forward declaration for status pixel tick used in pump_network_ms
#if USE_STATUS_PIXEL
static inline void status_pixel_tick();
#endif

#if USE_DISPLAY && DEV_NO_SLEEP
// In always-on display builds, tick the UI when outside MQTT values change
static void dev_display_tick();
#endif

// Most display functions are now declared in display_manager.h
// No need to redeclare them here since they're implemented in this file
#if USE_DISPLAY
// Accessor to avoid forward reference ordering issues
// Implemented below, declared in display_manager.h
static bool maybe_redraw_status(const BatteryStatus& bs, const char* ip_cstr, const int rect[4]);
template <typename DrawFnFwd>
static inline void draw_in_region(const int rect[4], DrawFnFwd drawFn);
// Forward decls used by spec renderer implemented earlier in the file
static inline void draw_temp_number_and_units(const int r[4], const char* t);
#if USE_UI_SPEC
// Minimal spec interpreter (full-window only) for variant rendering
static void draw_from_spec_full(uint8_t variantId);

// Utility to map RectId->rect pointer
static inline const int* rect_ptr_by_id(uint8_t rid) {
  switch (rid) {
    case ui::RECT_HEADER_NAME:
      return HEADER_NAME;
    case ui::RECT_HEADER_TIME:
      return HEADER_TIME;
    case ui::RECT_HEADER_CENTER:
      return HEADER_CENTER;
    case ui::RECT_INSIDE_TEMP:
      return INSIDE_TEMP;
    case ui::RECT_INSIDE_RH:
      return INSIDE_RH;
    case ui::RECT_INSIDE_TIME:
      return INSIDE_TIME;
    case ui::RECT_OUT_TEMP:
      return OUT_TEMP;
    case ui::RECT_OUT_ICON:
      return OUT_ICON;
    case ui::RECT_OUT_ROW1_L:
      return OUT_ROW1_L;
    case ui::RECT_OUT_ROW1_R:
      return OUT_ROW1_R;
    case ui::RECT_OUT_ROW2_L:
      return OUT_ROW2_L;
    case ui::RECT_OUT_ROW2_R:
      return OUT_ROW2_R;
    case ui::RECT_FOOTER_STATUS:
      return FOOTER_STATUS;
    case ui::RECT_FOOTER_WEATHER:
      return FOOTER_WEATHER;
    case ui::RECT_STATUS:
      return STATUS_;
    default:
      return nullptr;
  }
}

// Forward to implementation placed after display declaration
static void draw_from_spec_full_impl(uint8_t variantId);
static void draw_from_spec_full(uint8_t variantId) { draw_from_spec_full_impl(variantId); }
#endif
#endif

// Feather ESP32-S2 + 2.13" FeatherWing (adjust if needed)
#ifndef EINK_CS
#define EINK_CS 9  // D9
#endif
#ifndef EINK_DC
#define EINK_DC 10  // D10
#endif
#ifndef EINK_RST
#define EINK_RST -1  // FeatherWing ties panel reset to Feather RESET
#endif
#ifndef EINK_BUSY
#define EINK_BUSY \
  -1  // FeatherWing BUSY not connected; use -1 so library times
      // waits
#endif

// 2.13" b/w class; choose the one matching your panel
// B74 works for SSD1680/UC8151 variants used by many 2.13" panels
// Alternative: DEPG0213BN (also SSD1680 family). Select via
// -DEINK_PANEL_DEPG0213BN=1
#if USE_DISPLAY
#ifndef EINK_PANEL_DEPG0213BN
#define EINK_PANEL_DEPG0213BN 0
#endif
#if EINK_PANEL_DEPG0213BN
GxEPD2_BW<GxEPD2_213_DEPG0213BN, GxEPD2_213_DEPG0213BN::HEIGHT> display(
    GxEPD2_213_DEPG0213BN(EINK_CS, EINK_DC, EINK_RST, EINK_BUSY));
#else
// Prefer the explicit GDEY0213B74 class name for clarity on SSD1680 FeatherWing
GxEPD2_BW<GxEPD2_213_GDEY0213B74, GxEPD2_213_GDEY0213B74::HEIGHT> display(
    GxEPD2_213_GDEY0213B74(EINK_CS, EINK_DC, EINK_RST, EINK_BUSY));
#endif

// Now that display exists, provide the implementation using it
#if USE_UI_SPEC
static void draw_from_spec_full_impl(uint8_t variantId) {
  // Ensure TOP_Y_OFFSET is available; if not yet defined, use default 4
#ifndef TOP_Y_OFFSET
#define TOP_Y_OFFSET 4
#endif
  using ui::ALIGN_CENTER;
  using ui::ALIGN_LEFT;
  using ui::ALIGN_RIGHT;
  using ui::ComponentOps;
  using ui::OP_LABELCENTERED;
  using ui::OP_LINE;
  using ui::OP_TEMPGROUPCENTERED;
  using ui::OP_TEXT;
  using ui::OP_TIMERIGHT;
  using ui::UiOpHeader;
  int comp_count = 0;
  const ComponentOps* comps = get_variant_ops(variantId, &comp_count);
  display.drawRect(0, 0, EINK_WIDTH, EINK_HEIGHT, GxEPD_BLACK);
  display.drawLine(1,
                    16 + TOP_Y_OFFSET,
                    EINK_WIDTH - 2,
                    16 + TOP_Y_OFFSET,
  display.drawLine(125, 18 + TOP_Y_OFFSET, 125, EINK_HEIGHT - 2, GxEPD_BLACK);
  for (int ci = 0; ci < comp_count; ++ci) {
    const ComponentOps& co = comps[ci];
    for (int i = 0; i < co.count; ++i) {
      const UiOpHeader& op = co.ops[i];
      switch (op.kind) {
        case ui::OP_LINE: {
          int16_t x0 = op.p0, y0 = op.p1, x1 = op.p2, y1 = op.p3;
          if (y0 == y1) {
            for (int16_t x = x0; x <= x1; ++x) display.drawPixel(x, y0, GxEPD_BLACK);
          } else if (x0 == x1) {
            for (int16_t y = y0; y <= y1; ++y) display.drawPixel(x0, y, GxEPD_BLACK);
          }
          break;
        }
        case ui::OP_TEXT: {
          const int* r = rect_ptr_by_id(op.rect);
          int16_t tx = op.p0;
          int16_t ty = op.p1 + TOP_Y_OFFSET;
          auto fmt_field = [&](const String& key) -> String {
            if (key == "room_name")
              return String(ROOM_NAME);
            if (key == "ip") {
              char ip_c[32];
              net_ip_cstr(ip_c, sizeof(ip_c));
              return String("IP ") + ip_c;
            }
            if (key == "fw_version")
              return String(FW_VERSION);
            return String("");
          };
          String templ = op.s0 ? op.s0 : "";
          String out;
          out.reserve(templ.length() + 8);
          int start = 0;
          while (true) {
            int lb = templ.indexOf('{', start);
            if (lb < 0) {
              out += templ.substring(start);
              break;
            }
            int rb = templ.indexOf('}', lb + 1);
            if (rb < 0) {
              out += templ.substring(start);
              break;
            }
            out += templ.substring(start, lb);
            String key = templ.substring(lb + 1, rb);
            out += fmt_field(key);
            start = rb + 1;
          }
          display.setTextColor(GxEPD_BLACK);
          display.setTextSize(1);
          if (r && tx == 0 && (op.align == ALIGN_RIGHT || op.align == ALIGN_CENTER)) {
            int16_t tw = text_width_default_font(out.c_str(), 1);
            tx = r[0] + 1;
            if (op.align == ALIGN_RIGHT)
              tx = r[0] + r[2] - 2 - tw;
            else if (op.align == ALIGN_CENTER)
              tx = r[0] + (r[2] - tw) / 2;
            ty = r[1] + TOP_Y_OFFSET + 1;
          }
          display.setCursor(tx, ty);
          display.print(out.c_str());
          break;
        }
        case OP_TIMERIGHT: {
          char hhmm[8];
          net_time_hhmm(hhmm, sizeof(hhmm));
          int16_t tw = text_width_default_font(hhmm, 1);
          int16_t rx = static_cast<int16_t>(HEADER_TIME[0] + HEADER_TIME[2] - 2 - tw) int16_t by =
              static_cast<int16_t>(HEADER_TIME[1] + TOP_Y_OFFSET + HEADER_TIME[3] - 2)
                  display.setTextColor(GxEPD_BLACK);
          display.setTextSize(1);
          display.setCursor(rx, by);
          display.print(hhmm);
          break;
        }
        case OP_LABELCENTERED: {
          const int* r = rect_ptr_by_id(op.rect);
          if (!r)
            break;
          display.setTextColor(GxEPD_BLACK);
          display.setTextSize(1);
          int16_t tw = text_width_default_font(op.s0 ? op.s0 : "", 1);
          int16_t tx = r[0] + (r[2] - tw) / 2;
          int16_t ty = r[1] + TOP_Y_OFFSET - 14 + op.p0;
          display.setCursor(tx, ty);
          display.print(op.s0 ? op.s0 : "");
          break;
        }
        case OP_TEMPGROUPCENTERED: {
          const int* r = rect_ptr_by_id(op.rect);
          if (!r)
            break;
          char temp_buf[16];
          temp_buf[0] = 0;
          if (r == INSIDE_TEMP) {
            InsideReadings ir = read_inside_sensors();
            if (isfinite(ir.temperatureC)) {
            snprintf(temp_buf,
                      sizeof(temp_buf),
                      "%.1f",
            } else {
              snprintf(temp_buf, sizeof(temp_buf), "--");
            }
          } else if (r == OUT_TEMP) {
            OutsideReadings orr = net_get_outside();
            if (orr.validTemp && isfinite(orr.temperatureC)) {
              float tempF = orr.temperatureC * 9.0f / 5.0f + 32.0f;
              snprintf(temp_buf, sizeof(temp_buf), "%.1f", tempF);
            } else if (isfinite(get_last_outside_f())) {
              snprintf(temp_buf, sizeof(temp_buf), "%.1f", get_last_outside_f());
            } else {
              snprintf(temp_buf, sizeof(temp_buf), "--");
            }
          }
          draw_temp_number_and_units(r, temp_buf);
          break;
        }
        case OP_ICONIN: {
          const int* r = rect_ptr_by_id(op.rect);
          if (!r)
            break;
          OutsideReadings o = net_get_outside();
          if (o.validWeather) {
          draw_weather_icon_region_at_from_outside(r[0],
                                                    r[1] + TOP_Y_OFFSET,
                                                    r[2],
                                                    r[3],
          } else {
            const char* weather = o.validWeather ? o.weather : "";
          draw_weather_icon_region_at(r[0],
                                       r[1] + TOP_Y_OFFSET,
                                       r[2],
                                       r[3],
          }
          break;
        }
        case OP_SHORTCONDITION: {
          const int* r = rect_ptr_by_id(op.rect);
          if (!r)
            break;
          OutsideReadings o = net_get_outside();
          if (o.validWeather) {
            char sc[24];
            if (o.validWeather && o.weather[0]) {
              make_short_condition_cstr(o.weather, sc, sizeof(sc));
            } else {
              make_short_condition_cstr(o.weather, sc, sizeof(sc));
            }
            display.setTextColor(GxEPD_BLACK);
            display.setTextSize(1);
            display.setCursor(r[0] + op.p0, r[1] + TOP_Y_OFFSET + r[3] / 2 + 2);
            display.print(sc);
          }
          break;
        }
        case OP_TEXTCENTEREDIN: {
          const int* r = rect_ptr_by_id(op.rect);
          if (!r)
            break;
          String templ = op.s0 ? op.s0 : "";
          char ip_c[32];
          net_ip_cstr(ip_c, sizeof(ip_c));
          templ.replace("{ip}", ip_c);
          display.setTextColor(GxEPD_BLACK);
          display.setTextSize(1);
          int16_t tw = text_width_default_font(templ.c_str(), 1);
          int16_t tx = r[0] + (r[2] - tw) / 2;
          int16_t ty = r[1] + op.p0;
          display.setCursor(tx, ty);
          display.print(templ.c_str());
          break;
        }
        case OP_BATTERYGLYPH: {
          BatteryStatus bs = read_battery_status();
          int16_t bx = op.p0, by = op.p1, bw = op.p2, bh = op.p3;
          display.drawRect(bx, by, bw, bh, GxEPD_BLACK);
          display.fillRect(static_cast<int16_t>(bx + bw), static_cast<int16_t>(by + 2), 2, 3,
                           GxEPD_BLACK);
          int16_t fillw = static_cast<int16_t>(((bw - 2) * (bs.percent / 100.0f) + 0.5f));
          if (fillw > 0)
            display.fillRect(static_cast<int16_t>(bx + 1), static_cast<int16_t>(by + 1), fillw,
                             static_cast<int16_t>(bh - 2), GxEPD_BLACK);
          break;
        }
        default:
          break;
      }
    }
  }  // USE_UI_SPEC
}
#endif  // USE_UI_SPEC
#endif  // USE_DISPLAY

RTC_DATA_ATTR static uint16_t partial_counter = 0;
// Wake count now managed by system_manager
RTC_DATA_ATTR static float last_inside_f = NAN;
RTC_DATA_ATTR static float last_outside_f = NAN;
float get_last_outside_f() { return last_outside_f; }
RTC_DATA_ATTR static float last_outside_rh = NAN;
RTC_DATA_ATTR static int32_t last_icon_id = -1;
// Track last rendered footer weather (icon + short text) to avoid
// redundant redraws
RTC_DATA_ATTR static uint32_t last_footer_weather_crc = 0;
RTC_DATA_ATTR static float last_published_inside_tempC = NAN;
RTC_DATA_ATTR static float last_published_inside_rh = NAN;
RTC_DATA_ATTR static float last_published_inside_pressureHPa = NAN;
RTC_DATA_ATTR static uint32_t last_status_crc = 0;
RTC_DATA_ATTR static float last_inside_rh = NAN;

// Diagnostic counters (persist across deep sleep)
RTC_DATA_ATTR static uint32_t rtc_boot_count = 0;           // Total boots since power-on
RTC_DATA_ATTR static uint32_t rtc_crash_count = 0;          // Count of abnormal resets
RTC_DATA_ATTR static uint32_t rtc_cumulative_uptime_sec = 0; // Total awake time in seconds
RTC_DATA_ATTR static uint32_t rtc_last_boot_timestamp = 0;   // Timestamp of last boot
RTC_DATA_ATTR static esp_reset_reason_t rtc_last_reset_reason = ESP_RST_UNKNOWN;

// Diagnostic mode state
static bool g_diagnostic_mode = false;
static uint32_t g_diagnostic_last_publish_ms = 0;
static const uint32_t DIAGNOSTIC_PUBLISH_INTERVAL_MS = 10000; // 10 seconds

// Memory monitoring structure
// MemoryDiagnostics struct moved to system_manager.h

// Timeout tracking
static uint32_t s_timeouts_mask = 0;

// Timeout bit constants
#define TIMEOUT_BIT_SENSOR 1
#define TIMEOUT_BIT_FETCH 2
#define TIMEOUT_BIT_DISPLAY 4
#define TIMEOUT_BIT_PUBLISH 8

// Layout version for device identity
#ifndef LAYOUT_VERSION
#define LAYOUT_VERSION 1
#endif
#ifndef LAYOUT_CRC
#define LAYOUT_CRC 0x08C0813Au
#endif

// Threshold constants for change detection
#ifndef THRESH_TEMP_C_FROM_F
#define THRESH_TEMP_C_FROM_F 0.5f
#endif
#ifndef THRESH_RH
#define THRESH_RH 1.0f
#endif
#ifndef THRESH_PRESS_HPA
#define THRESH_PRESS_HPA 1.0f
#endif

// Missing function implementations
// Moved to system_manager

// Forward declarations for functions used by print_boot_diagnostics
float get_last_outside_f();  // Forward declaration
static const char* reset_reason_str(esp_reset_reason_t r);
static const char* wakeup_cause_str(esp_sleep_wakeup_cause_t c);

static inline void net_time_hhmm(char* out, size_t out_size) {
  if (!out || out_size == 0)
    return;
  time_t now = time(nullptr);
  struct tm tm_now;
  localtime_r(&now, &tm_now);
  snprintf(out, out_size, "%02d:%02d", tm_now.tm_hour, tm_now.tm_min);
}

static inline void net_publish_layout_identity() {
  if (!mqtt_is_connected())
    return;
  char topic[128];
  snprintf(topic, sizeof(topic), "%s/layout", MQTT_PUB_BASE);
  char payload[96];
  snprintf(payload, sizeof(payload), "{\"layout_version\":%u,\"layout_crc\":\"0x%08X\"}",
           static_cast<unsigned>(LAYOUT_VERSION), static_cast<unsigned>(LAYOUT_CRC));
  mqtt_publish_raw(topic, payload, true);
}
#if USE_DISPLAY
// Ensure the very first wake after flashing or power-on does a full render
RTC_DATA_ATTR static bool needs_full_on_boot = true;
#endif
#ifdef FORCE_FULL_ONLY
static bool g_full_only_mode = true;  // compile-time force full refresh only
#else
static bool g_full_only_mode = false;  // when true, always do full refresh
                                       // (debug)
#endif

// Preferences object now managed in system_manager

// Implementation of NVS cache loading - uses RTC variables local to main.cpp
void nvs_load_cache_if_unset() {
  nvs_begin_cache();
  
  if (!isfinite(last_inside_f))
    last_inside_f = nvs_load_float("li_f", NAN);
  if (!isfinite(last_inside_rh))
    last_inside_rh = nvs_load_float("li_rh", NAN);
  if (!isfinite(last_outside_f))
    last_outside_f = nvs_load_float("lo_f", NAN);
  if (!isfinite(last_outside_rh))
    last_outside_rh = nvs_load_float("lo_rh", NAN);
  if (last_icon_id < 0)
    last_icon_id = static_cast<int32_t>(nvs_load_uint("icon", -1));
  if (last_status_crc == 0)
    last_status_crc = nvs_load_uint("st_crc", 0);
  if (!isfinite(last_published_inside_tempC))
    last_published_inside_tempC = nvs_load_float("pi_t", NAN);
  if (!isfinite(last_published_inside_rh))
    last_published_inside_rh = nvs_load_float("pi_rh", NAN);
  if (!isfinite(last_published_inside_pressureHPa))
    last_published_inside_pressureHPa = nvs_load_float("pi_p", NAN);
  uint16_t pc = nvs_load_ushort("pcount", 0);
  if (pc > 0)
    partial_counter = pc;
  // Load render mode (0=partial, 1=full-only)
  g_full_only_mode = nvs_load_uchar("full_only", 0) != 0;
  
  nvs_end_cache();
  // Remove legacy ui_variant preference; single UI variant remains
}
// print_boot_diagnostics now in system_manager

#if USE_DISPLAY
// Shared soft deadline used by display drawing helpers to avoid long loops
static uint32_t g_display_deadline_ms = 0;
#ifndef TOP_Y_OFFSET
#define TOP_Y_OFFSET 4
#endif
#ifndef HEADER_NAME_Y_ADJ
#define HEADER_NAME_Y_ADJ -6
#endif
#ifndef TEMP_Y_ADJ
#define TEMP_Y_ADJ -40
#endif
#ifndef TEMP_UNITS_Y_ADJ
#define TEMP_UNITS_Y_ADJ 20
#endif
#ifndef TEMP_DOWN_ADJ
#define TEMP_DOWN_ADJ 20
#endif
#ifndef STATUS_Y_ADJ
#define STATUS_Y_ADJ -4
#endif
#endif

static void pump_network_ms(uint32_t duration_ms) {
  uint32_t start = millis();
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
static uint8_t s_breath = 0;  // brightness phase for subtle breathing

static uint32_t color_wheel(uint8_t pos) {
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

static inline void status_pixel_begin() {
  s_statusPixel.begin();
  s_statusPixel.setBrightness(8);
  s_statusPixel.show();
}

static inline void status_pixel_off() {
  s_statusPixel.clear();
  s_statusPixel.show();
}

static inline void status_pixel_tick() {
  uint32_t now = millis();
  if (now - s_lastPixelMs < 40)
    return;  // slower update for smooth, slow cycle
  s_lastPixelMs = now;
  s_hue++;
  s_breath++;
  // Triangle wave 0..127..0 mapped to brightness range
  uint8_t amp = (s_breath < 128) ? s_breath : static_cast<uint8_t>(255 - s_breath);
  const uint8_t minB = 8;
  const uint8_t maxB = 64;
  uint8_t level = static_cast<uint8_t>(minB + (static_cast<uint16_t>(amp) * (maxB - minB) / 127));
  // Occasional brief flash for a bit of flair
  if ((s_hue & 0x3F) == 0)
    level = maxB;
  s_statusPixel.setBrightness(level);
  s_statusPixel.setPixelColor(0, color_wheel(s_hue));
  s_statusPixel.show();
}
#endif

static void emit_metrics_json(float tempC, float rhPct, float pressHPa) {
  BatteryStatus bs = read_battery_status();
  char ip_c[32];
  net_ip_cstr(ip_c, sizeof(ip_c));
  Serial.print('{');
  Serial.print("\"layout_version\":");
  Serial.print(LAYOUT_VERSION);
  Serial.print(',');
  Serial.print("\"layout_crc\":\"");
  {
    char crcbuf[12];
    snprintf(crcbuf, sizeof(crcbuf), "0x%08X", static_cast<unsigned>(LAYOUT_CRC));
    Serial.print(crcbuf);
  }
  Serial.print("\"");
  Serial.print(',');
  Serial.print("\"event\":\"metrics\",");
  Serial.print("\"ip\":\"");
  Serial.print(ip_c);
  Serial.print("\",");
  Serial.print("\"tempF\":");
  Serial.print(isfinite(tempC) ? (tempC * 9.0 / 5.0 + 32.0) : NAN);
  Serial.print(',');
  Serial.print("\"rhPct\":");
  Serial.print(isfinite(rhPct) ? rhPct : NAN);
  Serial.print(',');
  Serial.print("\"pressHPa\":");
  Serial.print(isfinite(pressHPa) ? pressHPa : NAN);
  Serial.print(',');
  Serial.print("\"wifi\":");
  Serial.print(net_wifi_is_connected() ? "true" : "false");
  Serial.print(',');
  Serial.print("\"mqtt\":");
  Serial.print(net_mqtt_is_connected() ? "true" : "false");
  Serial.print(',');
  Serial.print("\"v\":");
  Serial.print(bs.voltage, 2);
  Serial.print(',');
  Serial.print("\"pct\":");
  Serial.print(bs.percent);
  Serial.println('}');
}

// Map reset reason and wakeup cause to short strings for debug publishing
static const char* reset_reason_str(esp_reset_reason_t r) {
  switch (r) {
    case ESP_RST_POWERON:
      return "ESP_RST_POWERON";
    case ESP_RST_EXT:
      return "ESP_RST_EXT";
    case ESP_RST_SW:
      return "ESP_RST_SW";
    case ESP_RST_PANIC:
      return "ESP_RST_PANIC";
    case ESP_RST_INT_WDT:
      return "ESP_RST_INT_WDT";
    case ESP_RST_TASK_WDT:
      return "ESP_RST_TASK_WDT";
    case ESP_RST_WDT:
      return "ESP_RST_WDT";
    case ESP_RST_BROWNOUT:
      return "ESP_RST_BROWNOUT";
    case ESP_RST_DEEPSLEEP:
      return "ESP_RST_DEEPSLEEP";
    case ESP_RST_SDIO:
      return "ESP_RST_SDIO";
    default:
      return "ESP_RST_UNKNOWN";
  }
}



// Check if diagnostic mode should be activated based on rapid resets
static bool check_rapid_reset_diagnostic_trigger() {
  // Check if we've had 3+ resets within 10 seconds
  uint32_t now = static_cast<uint32_t>(time(nullptr));
  
  // If time is not synced, use millis-based detection
  if (now < 1609459200UL) {  // Before 2021
    return false;  // Can't detect rapid resets without proper time
  }
  
  if (rtc_boot_count >= 3 && rtc_last_boot_timestamp > 0) {
    uint32_t time_since_last_boot = now - rtc_last_boot_timestamp;
    if (time_since_last_boot <= 10) {
      return true;  // 3+ boots within 10 seconds
    }
  }
  return false;
}


static const char* wakeup_cause_str(esp_sleep_wakeup_cause_t c) {
  switch (c) {
    case ESP_SLEEP_WAKEUP_UNDEFINED:
      return "UNDEFINED";
    case ESP_SLEEP_WAKEUP_EXT0:
      return "EXT0";
    case ESP_SLEEP_WAKEUP_EXT1:
      return "EXT1";
    case ESP_SLEEP_WAKEUP_TIMER:
      return "TIMER";
    case ESP_SLEEP_WAKEUP_TOUCHPAD:
      return "TOUCHPAD";
    case ESP_SLEEP_WAKEUP_ULP:
      return "ULP";
#ifdef ESP_SLEEP_WAKEUP_GPIO
    case ESP_SLEEP_WAKEUP_GPIO:
      return "GPIO";
#endif
#ifdef ESP_SLEEP_WAKEUP_UART
    case ESP_SLEEP_WAKEUP_UART:
      return "UART";
#endif
    default:
      return "OTHER";
  }
}


// Moved to display_manager.cpp

// Moved to display_manager.cpp

#if USE_DISPLAY
// Forward declaration for status drawing used by maybe_redraw_status
void draw_status_line(const BatteryStatus& bs, const char* ip_cstr);

template <typename DrawFn>
static inline void draw_in_region(const int rect[4],

                                  DrawFn drawFn) {
  const int16_t x = rect[0];
  const int16_t y = rect[1];
  const int16_t w = rect[2];
  const int16_t h = rect[3];
  // Align partial window to 8-pixel byte boundaries on X for SSD1680-class
  // panels
  // to avoid controller rejects or missing updates on unaligned windows.
  int16_t ax = x & ~0x07;
  int16_t ar = x + w;  // right edge (exclusive)
  int16_t aw = static_cast<int16_t>(((ar - ax) + 7) & ~0x07);
  display.setPartialWindow(ax, y, aw, h);
  display.firstPage();
  do {
    display.fillScreen(GxEPD_WHITE);
    drawFn(x, y, w, h);
#if USE_STATUS_PIXEL
    status_pixel_tick();
#endif
    yield();
  } while (display.nextPage());
}

static inline void draw_right_aligned_text_in_rect(const int rect[4], const char* text,
                                                   uint8_t textSize, int16_t paddingRight,
                                                   int16_t baselineOffset) {
  draw_in_region(rect, [&](int16_t x, int16_t y, int16_t w, int16_t h) {
    display.setTextColor(GxEPD_BLACK);
    display.setTextSize(textSize);
    int16_t tw = text_width_default_font(text, textSize);
    int16_t rx = x + w - paddingRight - tw;
    int16_t by = y + h - baselineOffset;
    display.setCursor(rx, by);
    display.print(text);
  });
}

static inline void draw_temp_number_and_units(const int r[4], const char* t) {
  const int* units_rect = r;  // For now, use same rect for units
  draw_in_region(r, [&](int16_t x, int16_t y, int16_t w, int16_t h) {
    display.setTextColor(GxEPD_BLACK);
    display.setTextSize(2);
    int16_t tw = text_width_default_font(t, 2);
    int16_t rx = x + (w - tw) / 2;
    int16_t by = y + h - 4;
    display.setCursor(rx, by);
    display.print(t);
  });

  // Draw degree symbol and F in small font
  // inside the units sub-rect
  draw_in_region(units_rect, [&](int16_t x, int16_t y, int16_t w, int16_t h) {
    display.setTextColor(GxEPD_BLACK);
    display.setTextSize(1);
    int16_t by = y + h - 4;
    display.setCursor(x + 1, by);
    display.print("\xF8");
    display.setCursor(x + 7, by);
    display.print("F");
  });
}

// Direct draw variant for full-window paged
// renders (no nested partial pages)
static inline void draw_temp_number_and_units_direct(int16_t x, int16_t y, int16_t w, int16_t h,
                                                     const char* temp_f) {
  const int16_t units_w = 14;
  display.setTextColor(GxEPD_BLACK);
  display.setTextSize(2);
  int16_t x1, y1;
  uint16_t bw, bh;
  display.getTextBounds(temp_f, 0, 0, &x1, &y1, &bw, &bh);
  int16_t targetX = static_cast<int16_t>(x + (w - units_w - static_cast<int16_t>(bw)) / 2);
  int16_t targetY = static_cast<int16_t>(y + (h - static_cast<int16_t>(bh)) / 2);
  int16_t baseX = static_cast<int16_t>(targetX - x1);
  int16_t baseY = static_cast<int16_t>(targetY - y1);
  display.setCursor(baseX, baseY);
  display.print(temp_f);
  display.setTextSize(1);
  int16_t ux = static_cast<int16_t>(x + w - units_w + 2);
  int16_t uy = static_cast<int16_t>(baseY - 2);
  display.setCursor(ux, uy);
  display.print("\xF8");
  display.setCursor(static_cast<int16_t>(ux + 6), uy);
  display.print("F");
}

static inline uint32_t fast_crc32(const uint8_t* data, size_t len) {
  // Tiny CRC32 (polynomial 0xEDB88320),
  // suitable for short status strings
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

template <typename DrawFn>
static inline bool maybe_redraw_numeric(const int rect[4], float currentValue, float& lastValue,
                                        float threshold, DrawFn drawFn) {
  bool should = false;
  if (!isnan(currentValue) &&
      (!isfinite(lastValue) || fabsf(currentValue - lastValue) >= threshold))
    should = true;
  if (should) {
    drawFn();
    lastValue = currentValue;
    return true;
  }
  return false;
}

template <typename T, typename DrawFn>
static inline bool maybe_redraw_value(const int rect[4], const T& currentValue, T& lastValue,
                                      DrawFn drawFn) {
  if (currentValue != lastValue) {
    drawFn();
    lastValue = currentValue;
    return true;
  }
  return false;
}

static inline bool maybe_redraw_status(const BatteryStatus& bs, const char* ip_cstr,
                                       const int rect[4]) {
  char buf[96];
  // Stacked footer signature (3-row status)
  snprintf(buf, sizeof(buf), "B%.2f|%d|D%d|IP%s", bs.voltage, bs.percent, bs.estimatedDays,
           ip_cstr);
  uint32_t crc = fast_crc32((const uint8_t*)buf, strlen(buf));
  if (crc != last_status_crc) {
    draw_status_line(bs, ip_cstr);
    last_status_crc = crc;
    return true;
  }
  return false;
}

// Moved to display_manager.cpp

void draw_header_time(const char* time_str) {
  // Draw centered time within HEADER_CENTER box
  // to avoid overlapping the version
  int rect2[4] = {HEADER_CENTER[0], static_cast<int16_t>(HEADER_CENTER[1] + TOP_Y_OFFSET),
                  HEADER_CENTER[2], HEADER_CENTER[3]};
  draw_in_region(rect2, [&](int16_t xx, int16_t yy, int16_t ww, int16_t hh) {
    display.setTextColor(GxEPD_BLACK);  // comment spacing fix
    display.setTextSize(1);
    int16_t tw = text_width_default_font(time_str, 1);
    int16_t rx = static_cast<int16_t>(xx + (ww - tw) / 2);
    int16_t by = yy + hh - 3;  // baseline nudge up to align with room name
    display.setCursor(rx, by);
    display.print(time_str);
  });
}

// Moved to display_manager.cpp

void draw_status_line(const BatteryStatus& bs, const char* ip_cstr) {
  // Render stacked footer content inside
  // FOOTER_L (battery lines + centered IP)
  draw_in_region(FOOTER_L, [&](int16_t x, int16_t y, int16_t w, int16_t h) {
    display.fillRect(x, y, w, h, GxEPD_WHITE);
    display.setTextColor(GxEPD_BLACK);
    display.setTextSize(1);
    int16_t cx = static_cast<int16_t>(x + 2);
    // Battery glyph to the left of text when
    // percent available
    if (bs.percent >= 0) {
      int16_t bx = cx;
      int16_t by = static_cast<int16_t>(y + 2);
      int16_t bw = 13;
      int16_t bh = 7;
      display.drawRect(bx, by, bw, bh, GxEPD_BLACK);
      display.fillRect(static_cast<int16_t>(bx + bw), static_cast<int16_t>(by + 2), 2, 3,
                       GxEPD_BLACK);
      int16_t fillw = static_cast<int16_t>(((bw - 2) * (bs.percent / 100.0f) + 0.5f));
      if (fillw > 0)
        display.fillRect(static_cast<int16_t>(bx + 1), static_cast<int16_t>(by + 1), fillw,
                         static_cast<int16_t>(bh - 2), GxEPD_BLACK);
      cx = static_cast<int16_t>(cx + bw + 6);
    }
    int16_t line = static_cast<int16_t>(y + 10);
    char l1[48];
    snprintf(l1, sizeof(l1), "Batt %.2fV %d%%", bs.voltage, bs.percent);
    display.setCursor(cx, line);
    display.print(l1);
    line = static_cast<int16_t>(line + 10);
    char l2[48];
    snprintf(l2, sizeof(l2), "~%dd", bs.estimatedDays);
    display.setCursor(cx, line);
    display.print(l2);
    line = static_cast<int16_t>(line + 10);
    char l3[56];
    snprintf(l3, sizeof(l3), "IP %s", ip_cstr);
    int16_t bx, by;
    uint16_t bw, bh;
    display.getTextBounds(l3, 0, 0, &bx, &by, &bw, &bh);
    int16_t ipx = static_cast<int16_t>(x + (w - static_cast<int16_t>(bw)) / 2);
    display.setCursor(ipx, line);
    display.print(l3);
  });
}

// Moved to display_manager.cpp
#endif // USE_DISPLAY guard for draw_in_region template and related functions

#if USE_DISPLAY
static void draw_values(const char* in_temp_f, const char* in_rh, const char* out_temp_f,
                        const char* out_rh, const char* time_str, const char* status) {
  display.setTextColor(GxEPD_BLACK);
  // Inside temp: numeric right-aligned, units drawn separately
  {
    int rect[4] = {INSIDE_TEMP[0], static_cast<int16_t>(INSIDE_TEMP[1] + TOP_Y_OFFSET),
                   INSIDE_TEMP[2], INSIDE_TEMP[3]};
    draw_temp_number_and_units(rect, in_temp_f);
  }

  // Inside RH
  display.setTextSize(1);
  display.setCursor(INSIDE_HUMIDITY[0], INSIDE_HUMIDITY[1] + TOP_Y_OFFSET);
  display.print(in_rh);
  display.print("% RH");

  // No duplicate inside time; header time is drawn by draw_header_time

  // Outside temp: numeric right-aligned, units drawn separately
  {
    int rect[4] = {OUT_TEMP[0], static_cast<int16_t>(OUT_TEMP[1] + TOP_Y_OFFSET), OUT_TEMP[2],
                   OUT_TEMP[3]};
    draw_temp_number_and_units(rect, out_temp_f);
  }

  // Other fields (condition, RH, wind) drawn with their partial updaters

  // Status line drawn separately by partial
}

static IconId map_weather_to_icon(const char* w) {
  String s(w);
  s.toLowerCase();
  // First handle Home Assistant recommended values exactly

  //
  // https://developers.home-assistant.io/docs/core/entity/weather/#recommended-values-for-state-and-condition
  if (s == "clear-night")
    return ICON_WEATHER_NIGHT;
  if (s == "cloudy")
    return ICON_WEATHER_CLOUDY;
  if (s == "exceptional")
    return ICON_WEATHER_CLOUDY;  // generic fallback
  if (s == "fog")
    return ICON_WEATHER_FOG;
  if (s == "hail")
    return ICON_WEATHER_SNOWY;  // approximate
  if (s == "lightning")
    return ICON_WEATHER_LIGHTNING;
  if (s == "lightning-rainy")
    return ICON_WEATHER_LIGHTNING;  // prefer lightning cue
  if (s == "partlycloudy")
    return ICON_WEATHER_PARTLY_CLOUDY;
  if (s == "pouring")
    return ICON_WEATHER_POURING;
  if (s == "rainy")
    return ICON_WEATHER_POURING;
  if (s == "snowy")
    return ICON_WEATHER_SNOWY;
  if (s == "snowy-rainy")
    return ICON_WEATHER_SNOWY;  // approximate
  if (s == "sunny")
    return ICON_WEATHER_SUNNY;
  if (s == "windy" || s == "windy-variant")
    return ICON_WEATHER_CLOUDY;  // approximate
  // Also accept explicit MDI icon names if passed through
  if (s == "weather-sunny")
    return ICON_WEATHER_SUNNY;
  if (s == "weather-partly-cloudy")
    return ICON_WEATHER_PARTLY_CLOUDY;
  if (s == "weather-cloudy")
    return ICON_WEATHER_CLOUDY;
  if (s == "weather-fog")
    return ICON_WEATHER_FOG;
  if (s == "weather-pouring" || s == "weather-rainy")
    return ICON_WEATHER_POURING;
  if (s == "weather-snowy")
    return ICON_WEATHER_SNOWY;
  if (s == "weather-lightning")
    return ICON_WEATHER_LIGHTNING;
  if (s == "weather-night")
    return ICON_WEATHER_NIGHT;
  if (s == "weather-night-partly-cloudy")
    return ICON_WEATHER_NIGHT_PARTLY_CLOUDY;
  if (s.indexOf("storm") >= 0 || s.indexOf("thunder") >= 0 || s.indexOf("lightning") >= 0) {
    return ICON_WEATHER_LIGHTNING;
  }
  if (s.indexOf("pour") >= 0 || s.indexOf("rain") >= 0 || s.indexOf("shower") >= 0) {
    return ICON_WEATHER_POURING;
  }
  if (s.indexOf("snow") >= 0)
    return ICON_WEATHER_SNOWY;
  if (s.indexOf("fog") >= 0 || s.indexOf("mist") >= 0 || s.indexOf("haze") >= 0)
    return ICON_WEATHER_FOG;
  if (s.indexOf("part") >= 0)
    return ICON_WEATHER_PARTLY_CLOUDY;
  if (s.indexOf("cloud") >= 0 || s.indexOf("overcast") >= 0)
    return ICON_WEATHER_CLOUDY;
  if (s.indexOf("night") >= 0)
    return ICON_WEATHER_NIGHT;
  return ICON_WEATHER_SUNNY;
}

// Map OpenWeather primary item (id/icon) to our icon set; fallback to string
// mapping
static IconId map_openweather_to_icon(const OutsideReadings& o) {
  // Prefer explicit icon code when provided (e.g., "10n") for day/night
  if (o.validWeather && o.weather[0]) {
    const char* ic = o.weather;
    // Normalize length
    if (strlen(ic) >= 2) {
      if (strncmp(ic, "01", 2) == 0)
        return (strchr(ic, 'n') ? ICON_WEATHER_NIGHT : ICON_WEATHER_SUNNY);
      if (strncmp(ic, "02", 2) == 0)
        return (strchr(ic, 'n') ? ICON_WEATHER_NIGHT_PARTLY_CLOUDY : ICON_WEATHER_PARTLY_CLOUDY);
      if (strncmp(ic, "03", 2) == 0)
        return ICON_WEATHER_CLOUDY;
      if (strncmp(ic, "04", 2) == 0)
        return ICON_WEATHER_CLOUDY;
      if (strncmp(ic, "09", 2) == 0)
        return ICON_WEATHER_POURING;
      if (strncmp(ic, "10", 2) == 0)
        return ICON_WEATHER_POURING;
      if (strncmp(ic, "11", 2) == 0)
        return ICON_WEATHER_LIGHTNING;
      if (strncmp(ic, "13", 2) == 0)
        return ICON_WEATHER_SNOWY;
      if (strncmp(ic, "50", 2) == 0)
        return ICON_WEATHER_FOG;
    }
  }
  // Fallback: heuristics from free-form string
  return map_weather_to_icon(o.weather);
}
#endif // USE_DISPLAY

// Draw weather icon region using OutsideReadings object (prefer OpenWeather
// hints)
#if USE_DISPLAY
void draw_weather_icon_region_at_from_outside(int16_t x, int16_t y, int16_t w, int16_t h,
                                                     const OutsideReadings& o) {
  display.fillRect(x, y, w, h, GxEPD_WHITE);
  int16_t ix = static_cast<int16_t>(x + (w - ICON_W) / 2);
  int16_t iy = static_cast<int16_t>(y + (h - ICON_H) / 2);
  IconId icon_id = map_openweather_to_icon(o);
  draw_icon(display, ix, iy, icon_id, GxEPD_BLACK);
}

void draw_weather_icon_region_at(int16_t x, int16_t y, int16_t w, int16_t h,
                                        const char* weather) {
  display.fillRect(x, y, w, h, GxEPD_WHITE);
  int16_t ix = x + (w - ICON_W) / 2;
  int16_t iy = y + (h - ICON_H) / 2;
  draw_icon(display, ix, iy, map_weather_to_icon(weather), GxEPD_BLACK);
}

void full_refresh() {
  // If UI spec is enabled, render using generated ops for variant v1
#if USE_UI_SPEC
  display.setFullWindow();
  display.firstPage();
  do {
    display.fillScreen(GxEPD_WHITE);
    draw_from_spec_full(static_cast<uint8_t>(ui::UIVAR_V1));
  } while (display.nextPage());
  return;
#endif
  // Snapshot values to ensure identical draw across pages
  InsideReadings r = read_inside_sensors();
  OutsideReadings o = net_get_outside();
  BatteryStatus bs = read_battery_status();
  String ip_s = net_ip();
  char ip_c[32];
  strncpy(ip_c, ip_s.c_str(), sizeof(ip_c));
  ip_c[sizeof(ip_c) - 1] = '\0';

  char in_temp[16];
  char in_rh[16];
  snprintf(in_temp, sizeof(in_temp), isfinite(r.temperatureC) ? "%.1f" : "--",
           r.temperatureC * 9.0 / 5.0 + 32.0);
  snprintf(in_rh, sizeof(in_rh), isfinite(r.humidityPct) ? "%.0f" : "--", r.humidityPct);
  char out_temp[16];
  if (o.validTemp && isfinite(o.temperatureC)) {
    snprintf(out_temp, sizeof(out_temp), "%.1f", o.temperatureC * 9.0 / 5.0 + 32.0);
  } else if (isfinite(last_outside_f)) {
    snprintf(out_temp, sizeof(out_temp), "%.1f", last_outside_f);
  } else {
    snprintf(out_temp, sizeof(out_temp), "--");
  }
  char out_rh[16];
  bool have_out_rh = false;
  if (o.validHum && isfinite(o.humidityPct)) {
    snprintf(out_rh, sizeof(out_rh), "%.0f", o.humidityPct);
    have_out_rh = true;
  } else if (isfinite(last_outside_rh)) {
    snprintf(out_rh, sizeof(out_rh), "%.0f", last_outside_rh);
    have_out_rh = true;
  }
  char ws[24];
  bool have_ws = false;
  if (o.validWind && isfinite(o.windMps)) {
    float mph = o.windMps * 2.237f;
    snprintf(ws, sizeof(ws), "%.1f mph", mph);
    have_ws = true;
  }

  display.setFullWindow();
  display.firstPage();
  do {
    draw_static_chrome();
    // Inside temp
    draw_temp_number_and_units_direct(INSIDE_TEMP[0],
                                      static_cast<int16_t>(INSIDE_TEMP[1] + TOP_Y_OFFSET),
                                      INSIDE_TEMP[2], INSIDE_TEMP[3], in_temp);
    // Inside RH
    display.setTextSize(1);
    display.setTextColor(GxEPD_BLACK);
    display.setCursor(INSIDE_HUMIDITY[0], INSIDE_HUMIDITY[1] + TOP_Y_OFFSET);
    display.print(in_rh);
    display.print("% RH");

    // Clear the legacy top-right icon region; the icon is now footer-only
    display.fillRect(WEATHER_ICON[0], WEATHER_ICON[1] + TOP_Y_OFFSET, WEATHER_ICON[2], WEATHER_ICON[3],
                     GxEPD_WHITE);
    // Track last icon id using OpenWeather hints when available for consistency
    if (o.validWeather) {
      last_icon_id = static_cast<int32_t>(map_openweather_to_icon(o));
    } else if (o.validWeather) {
      last_icon_id = static_cast<int32_t>(map_weather_to_icon(o.weather));
    }
    // Outside condition text removed from middle; only show condition in footer
    // Outside temp
    draw_temp_number_and_units_direct(OUT_TEMP[0], static_cast<int16_t>(OUT_TEMP[1] + TOP_Y_OFFSET),
                                      OUT_TEMP[2], OUT_TEMP[3], out_temp);
    // Outside RH and wind
    if (have_out_rh) {
      display.setTextSize(1);
      display.setTextColor(GxEPD_BLACK);
      display.setCursor(OUT_HUMIDITY[0], OUT_HUMIDITY[1] + TOP_Y_OFFSET);
      display.print(out_rh);
      display.print("% RH");
    }
    if (have_ws) {
      display.setTextSize(1);
      display.setTextColor(GxEPD_BLACK);
      display.setCursor(OUT_WIND[0], OUT_WIND[1] + TOP_Y_OFFSET);
      display.print(ws);
    }

    // Inside pressure (barometer) - now using INSIDE_PRESSURE region
    if (isfinite(r.pressureHPa)) {
      char pstr[24];
      snprintf(pstr, sizeof(pstr), "%.1f hPa", r.pressureHPa);
      display.setTextSize(1);
      display.setTextColor(GxEPD_BLACK);
      display.setCursor(INSIDE_PRESSURE[0], INSIDE_PRESSURE[1] + TOP_Y_OFFSET);
      display.print(pstr);
    }

    // Header time (prefer MQTT/RTC rather than fixed string)
    char hhmm[8];
    net_time_hhmm(hhmm, sizeof(hhmm));
    draw_header_time_direct(hhmm);
    // Footer left: multi-line battery/IP stacked
    {
      int16_t x = FOOTER_L[0];
      int16_t y = FOOTER_L[1];
      int16_t w = FOOTER_L[2];
      int16_t h = FOOTER_L[3];
      display.setTextColor(GxEPD_BLACK);
      display.setTextSize(1);
      int16_t line = static_cast<int16_t>(y + 10);
      char l1[48];
      snprintf(l1, sizeof(l1), "Batt %.2fV %d%%", bs.voltage, bs.percent);
      display.setCursor(x + 2, line);
      display.print(l1);
      line = static_cast<int16_t>(line + 10);
      char l2[48];
      snprintf(l2, sizeof(l2), "~%dd", bs.estimatedDays);
      display.setCursor(x + 2, line);
      display.print(l2);
      line = static_cast<int16_t>(line + 10);
      char l3[56];
      snprintf(l3, sizeof(l3), "IP %s", ip_c);
      display.setCursor(x + 2, line);
      display.print(l3);
    }
    // Footer right: icon + weather word (only location for icon)
    {
      int16_t x = FOOTER_WEATHER[0];
      int16_t y = FOOTER_WEATHER[1];
      int16_t w = FOOTER_WEATHER[2];
      int16_t h = FOOTER_WEATHER[3];
      if (o.validWeather || last_icon_id >= 0) {
        char sc[24];
        if (o.validWeather && o.weather[0])
          make_short_condition_cstr(o.weather, sc, sizeof(sc));
        else
          make_short_condition_cstr(o.weather, sc, sizeof(sc));
        // small icon on the left, word to the right
        int16_t ix = x + 2;
        int16_t iy = static_cast<int16_t>(y + (h - ICON_H) / 2);
        IconId icon_id = (o.validWeather) ? map_openweather_to_icon(o)
                                          : (o.validWeather ? map_weather_to_icon(o.weather)
                                                            : (IconId)last_icon_id);
        draw_icon(display, ix, iy, icon_id, GxEPD_BLACK);
        display.setTextColor(GxEPD_BLACK);
        display.setTextSize(1);
        display.setCursor(static_cast<int16_t>(x + 2 + ICON_W + 4),
                          static_cast<int16_t>(y + h / 2 + 2));
        if (o.validWeather)
          display.print(sc);
        // Update footer weather CRC cache for always-on parity immediately
        // after a full render
        char sig[64];
        snprintf(sig, sizeof(sig), "I%d|%s", static_cast<int>(icon_id), (o.validWeather) ? sc : "");
        last_footer_weather_crc = fast_crc32(reinterpret_cast<const uint8_t*>(sig), strlen(sig));
      }
    }
  } while (display.nextPage());
}

void smoke_full_window_test() {
  display.setFullWindow();
  uint32_t page_count = 0;
  display.firstPage();
  do {
    page_count++;
    display.fillScreen(GxEPD_WHITE);
    // 1px border to validate geometry and orientation visually
    display.drawRect(0, 0, display.width() - 1, display.height() - 1, GxEPD_BLACK);
    display.setTextColor(GxEPD_BLACK);
    display.setTextSize(1);
    display.setCursor(4, 14);
    display.print(display.width());
    display.print("x");
    display.print(display.height());
  } while (display.nextPage());
  Serial.printf("Pages drawn: %u\n", static_cast<uint32_t>(page_count));
}

// Removed minimal debug full_refresh

void partial_update_inside_temp(const char* in_temp_f, char trend) {
  int rect[4] = {INSIDE_TEMP[0], static_cast<int16_t>(INSIDE_TEMP[1] + TOP_Y_OFFSET),
                 INSIDE_TEMP[2], INSIDE_TEMP[3]};
  draw_in_region(rect, [&](int16_t x, int16_t y, int16_t w, int16_t h) {
    display.setTextColor(GxEPD_BLACK);
    // Compose "72.0°F" centered vertically using text bounds
    char buf[16];
    snprintf(buf, sizeof(buf), "%s", in_temp_f);
    display.setTextSize(2);
    int16_t x1, y1;
    uint16_t bw, bh;
    display.getTextBounds(buf, 0, 0, &x1, &y1, &bw, &bh);
    int16_t targetX = x + (w - static_cast<int16_t>(bw)) / 2;
    int16_t targetY = y + (h - static_cast<int16_t>(bh)) / 2;
    int16_t baseX = targetX - x1;
    int16_t baseY = targetY - y1 + TEMP_DOWN_ADJ;
    display.setCursor(baseX, baseY);
    display.print(buf);
    // Degree F units to the right (small font), align near numeric baseline
    display.setTextSize(1);
    display.setCursor(baseX + static_cast<int16_t>(bw) + 2, baseY - 8);
    display.print("\xF8");
    display.setCursor(baseX + static_cast<int16_t>(bw) + 8, baseY - 8);
    display.print("F");
  });
}

void partial_update_outside_temp(const char* out_temp_f, char trend) {
  int rect[4] = {OUT_TEMP[0], static_cast<int16_t>(OUT_TEMP[1] + TOP_Y_OFFSET), OUT_TEMP[2],
                 OUT_TEMP[3]};
  draw_in_region(rect, [&](int16_t x, int16_t y, int16_t w, int16_t h) {
    display.setTextColor(GxEPD_BLACK);
    char buf[16];
    snprintf(buf, sizeof(buf), "%s", out_temp_f);
    display.setTextSize(2);
    int16_t x1, y1;
    uint16_t bw, bh;
    display.getTextBounds(buf, 0, 0, &x1, &y1, &bw, &bh);
    int16_t targetX = x + (w - static_cast<int16_t>(bw)) / 2;
    int16_t targetY = y + (h - static_cast<int16_t>(bh)) / 2;
    int16_t baseX = targetX - x1;
    int16_t baseY = targetY - y1 + TEMP_DOWN_ADJ;
    display.setCursor(baseX, baseY);
    display.print(buf);
    display.setTextSize(1);
    display.setCursor(baseX + static_cast<int16_t>(bw) + 2, baseY - 8);
    display.print("\xF8");
    display.setCursor(baseX + static_cast<int16_t>(bw) + 8, baseY - 8);
    display.print("F");
  });
}

void partial_update_outside_rh(const char* out_rh) {
  int rect[4] = {OUT_HUMIDITY[0], static_cast<int16_t>(OUT_HUMIDITY[1] + TOP_Y_OFFSET), OUT_HUMIDITY[2],
                 OUT_HUMIDITY[3]};
  draw_in_region(rect, [&](int16_t x, int16_t y, int16_t w, int16_t h) {
    display.setTextColor(GxEPD_BLACK);
    display.setTextSize(1);
    display.setCursor(x, y);
    display.print(out_rh);
    display.print("% RH");
  });
}

void partial_update_inside_rh(const char* in_rh) {
  int rect[4] = {INSIDE_RH[0], static_cast<int16_t>(INSIDE_RH[1] + TOP_Y_OFFSET), INSIDE_RH[2],
                 INSIDE_RH[3]};
  draw_in_region(rect, [&](int16_t x, int16_t y, int16_t w, int16_t h) {
    display.setTextColor(GxEPD_BLACK);
    display.setTextSize(1);
    display.setCursor(x, y);
    display.print(in_rh);
    display.print("% RH");
  });
}

void partial_update_weather_icon(const char* weather) {
  int rect[4] = {WEATHER_ICON[0], static_cast<int16_t>(WEATHER_ICON[1] + TOP_Y_OFFSET), WEATHER_ICON[2],
                 WEATHER_ICON[3]};
  draw_in_region(rect, [&](int16_t xx, int16_t yy, int16_t ww, int16_t hh) {
    draw_weather_icon_region_at(xx, yy, ww, hh, weather);
  });
}

void partial_update_outside_wind(const char* wind_str) {
  int rect[4] = {OUT_ROW2_R[0], static_cast<int16_t>(OUT_ROW2_R[1] + TOP_Y_OFFSET), OUT_ROW2_R[2],
                 OUT_ROW2_R[3]};
  draw_in_region(rect, [&](int16_t x, int16_t y, int16_t, int16_t) {
    display.setTextColor(GxEPD_BLACK);
    display.setTextSize(1);
    display.setCursor(x, y);
    display.print(wind_str);
  });
}

void partial_update_outside_condition(const char* short_condition) {
  int rect[4] = {OUT_ROW1_L[0], static_cast<int16_t>(OUT_ROW1_L[1] + TOP_Y_OFFSET), OUT_ROW1_L[2],
                 OUT_ROW1_L[3]};
  draw_in_region(rect, [&](int16_t x, int16_t y, int16_t, int16_t) {
    display.setTextColor(GxEPD_BLACK);
    display.setTextSize(1);
    display.setCursor(x, y);
    display.print(short_condition);
  });
}

void partial_update_outside_hilo(float highC, float lowC) {
  int rect[4] = {OUT_ROW2_R[0], static_cast<int16_t>(OUT_ROW2_R[1] + TOP_Y_OFFSET), OUT_ROW2_R[2],
                 OUT_ROW2_R[3]};
  draw_in_region(rect, [&](int16_t x, int16_t y, int16_t, int16_t) {
    display.setTextColor(GxEPD_BLACK);
    display.setTextSize(1);
    display.setCursor(x, y);
    if (isfinite(highC) && isfinite(lowC)) {
      char buf[40];
      float hf = highC * 9.0f / 5.0f + 32.0f;
      float lf = lowC * 9.0f / 5.0f + 32.0f;
      snprintf(buf, sizeof(buf), "H %.1f\xF8  L %.1f\xF8", hf, lf);
      display.print(buf);
    }
  });
}

// Footer-only weather updater using the same geometry as full renders
void partial_update_footer_weather_from_outside(const OutsideReadings& o) {
  draw_in_region(FOOTER_WEATHER, [&](int16_t x, int16_t y, int16_t w, int16_t h) {
    display.fillRect(x, y, w, h, GxEPD_WHITE);
    // Icon at left
    int16_t ix = static_cast<int16_t>(x + 2);
    int16_t iy = static_cast<int16_t>(y + (h - ICON_H) / 2);
    IconId icon_id;
    if (o.validWeather)
      icon_id = map_openweather_to_icon(o);
    else if (o.validWeather)
      icon_id = map_weather_to_icon(o.weather);
    else
      icon_id = (last_icon_id >= 0) ? static_cast<IconId>(last_icon_id) : ICON_WEATHER_SUNNY;
    draw_icon(display, ix, iy, icon_id, GxEPD_BLACK);
    // Short condition text to the right of the icon
    char sc[24];
    sc[0] = '\0';
    if (o.validWeather && o.weather[0])
      make_short_condition_cstr(o.weather, sc, sizeof(sc));
    else if (o.validWeather)
      make_short_condition_cstr(o.weather, sc, sizeof(sc));
    if (sc[0]) {
      display.setTextColor(GxEPD_BLACK);
      display.setTextSize(1);
      display.setCursor(static_cast<int16_t>(x + 2 + ICON_W + 4),
                        static_cast<int16_t>(y + h / 2 + 2));
      display.print(sc);
    }
  });
}
#endif // USE_DISPLAY

#if USE_DISPLAY && DEV_NO_SLEEP
// Periodic UI updater for always-on display build. Applies partial redraws when
// outside MQTT values change beyond thresholds. Also refreshes header time and
// status line opportunistically.
static void dev_display_tick() {
  // Full-screen refresh policy: if any outside MQTT value changed, redraw
  // entire screen
  if (net_consume_outside_dirty()) {
    full_refresh();
    return;
  }

  // Even with full-refresh-on-change, keep header time and status fresh
  // opportunistically
  {
    static char s_last_hhmm[8] = {0};
    char hhmm[8];
    net_time_hhmm(hhmm, sizeof(hhmm));
    if (strncmp(hhmm, s_last_hhmm, sizeof(hhmm)) != 0) {
      draw_header_time(hhmm);
      strncpy(s_last_hhmm, hhmm, sizeof(s_last_hhmm));
      s_last_hhmm[sizeof(s_last_hhmm) - 1] = '\0';
    }
  }
  {
    static uint32_t s_last_status_ms = 0;
    uint32_t now = millis();
    if (now - s_last_status_ms > 60000u) {
      BatteryStatus bs = read_battery_status();
      char ip_c[32];
      net_ip_cstr(ip_c, sizeof(ip_c));
      if (maybe_redraw_status(bs, ip_c, STATUS_)) {
        nvs_store_uint("st_crc", last_status_crc);
      }
      s_last_status_ms = now;
    }
  }
}
#endif  // USE_DISPLAY && DEV_NO_SLEEP

void setup() {
  int64_t t0_us = esp_timer_get_time();
  Serial.begin(115200);
  delay(100);
  Serial.println(F("ESP32 eInk Room Node boot"));
  print_boot_diagnostics();
  // Increment RTC wake counter on any reset except true power-on
  if (esp_reset_reason() == ESP_RST_DEEPSLEEP || esp_reset_reason() == ESP_RST_SW ||
      esp_reset_reason() == ESP_RST_WDT || esp_reset_reason() == ESP_RST_PANIC ||
      esp_reset_reason() == ESP_RST_BROWNOUT || esp_reset_reason() == ESP_RST_TASK_WDT ||
      esp_reset_reason() == ESP_RST_INT_WDT) {
    increment_wake_count();
  } else {
    // On power-on, reset counter to zero
    reset_wake_count();
  }

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
  digitalWrite(EINK_EN_PIN, HIGH);  // enable panel power if gated
  delay(10);
#endif
  display.init(0);
  display.setRotation(1);  // landscape 250x122 coordinate system
  Serial.printf("EINK %dx%d (rotation=%d)\n", display.width(), display.height(),
                display.getRotation());
#endif
  nvs_begin_cache();
  nvs_load_cache_if_unset();
  // Force a clean full refresh on the first boot after flash/power-on
#if USE_DISPLAY
  if (needs_full_on_boot) {
    g_full_only_mode = true;
    nvs_store_uchar("full_only", 1);
    nvs_store_ushort("pcount", 0);
  }
#endif

  // Connect Wi-Fi then MQTT while capturing timestamps
  ensure_wifi_connected();
  int64_t t1_us = esp_timer_get_time();
  ensure_mqtt_connected();
  int64_t t2_us = esp_timer_get_time();

  // Skip any pre-publish draw to avoid double full refresh. A single
  // full_refresh will be performed in the display phase below across all modes.
#if USE_DISPLAY
  Serial.println("DBG: skipping pre-publish full draw (single full later)");
#endif

  // Update diagnostic counters based on reset reason
  esp_reset_reason_t current_reset_reason = esp_reset_reason();
  rtc_last_reset_reason = current_reset_reason;
  
  // Update boot and crash counters
  if (current_reset_reason == ESP_RST_POWERON) {
    // Power-on reset: clear all counters
    rtc_boot_count = 1;
    rtc_crash_count = 0;
    rtc_cumulative_uptime_sec = 0;
  } else {
    // Any other reset: increment boot count
    rtc_boot_count++;
    
    // Increment crash count for abnormal resets
    if (reset_reason_is_crash(current_reset_reason)) {
      rtc_crash_count++;
    }
  }
  
  // Check for diagnostic mode triggers
  if (check_rapid_reset_diagnostic_trigger()) {
    g_diagnostic_mode = true;
    Serial.println("DIAG: Entering diagnostic mode (rapid reset detected)");
  }
  
  // Update boot timestamp for rapid reset detection
  rtc_last_boot_timestamp = static_cast<uint32_t>(time(nullptr));
  
  // Crash safety: on panic/WDT/brownout reboot, publish retained last_crash;
  // clear it on clean runs
  if (net_mqtt_is_connected()) {
    esp_reset_reason_t rr = esp_reset_reason();
    if (reset_reason_is_crash(rr)) {
      net_publish_last_crash(reset_reason_str(rr));
    } else {
      net_publish_last_crash(nullptr);  // clear retained key
    }
    
    // Publish diagnostic information
    net_publish_boot_reason(reset_reason_str(current_reset_reason));
    net_publish_boot_count(rtc_boot_count);
    net_publish_crash_count(rtc_crash_count);
    net_publish_wake_count(get_wake_count());
    net_publish_uptime(rtc_cumulative_uptime_sec);
    
    // Publish memory diagnostics
    MemoryDiagnostics mem_diag = get_memory_diagnostics();
    net_publish_memory_diagnostics(mem_diag.free_heap, mem_diag.min_free_heap,
                                   mem_diag.largest_free_block, mem_diag.fragmentation_pct);
    
    // Publish diagnostic mode status
    net_publish_diagnostic_mode(g_diagnostic_mode);
  }

  // Measure sensor read duration (first read post-boot)
  int64_t t_sense_start_us = esp_timer_get_time();
  InsideReadings _sensor_probe = read_inside_sensors();
  (void)_sensor_probe;
  int64_t t3_us = esp_timer_get_time();
  uint32_t dbg_ms_sensor = static_cast<uint32_t>((t3_us - t_sense_start_us) / 1000);
  if (dbg_ms_sensor > static_cast<uint32_t>(SENSOR_PHASE_TIMEOUT_MS)) {
    s_timeouts_mask |= TIMEOUT_BIT_SENSOR;
    Serial.printf("Timeout: sensor read exceeded budget ms=%u budget=%u\n",
                  static_cast<unsigned>(dbg_ms_sensor),
                  static_cast<unsigned>(SENSOR_PHASE_TIMEOUT_MS));
  }
  // Print concise boot phase timings on USB for quick inspection
  {
    uint32_t ms_boot_to_wifi = static_cast<uint32_t>((t1_us - t0_us) / 1000);
    uint32_t ms_wifi_to_mqtt = static_cast<uint32_t>((t2_us - t1_us) / 1000);
    Serial.printf("Boot timing: wifi=%u ms mqtt=%u ms sensor=%u ms\n",
                  static_cast<unsigned>(ms_boot_to_wifi), static_cast<unsigned>(ms_wifi_to_mqtt),
                  static_cast<unsigned>(dbg_ms_sensor));
    // Repeat reset/wake later so it shows even if early prints were missed
    Serial.printf("Reset: %s, Wake: %s\n", reset_reason_str(esp_reset_reason()),
                  wakeup_cause_str(esp_sleep_get_wakeup_cause()));
    Serial.println("DBG: after boot timing");
  }

  // Compute scheduled sleep based on build-time mode
  uint32_t sleep_scheduled_ms = 0;
#if DEV_CYCLE_MODE
  sleep_scheduled_ms = static_cast<uint32_t>(DEV_SLEEP_SEC) * 1000UL;
#else
  sleep_scheduled_ms = static_cast<uint32_t>(WAKE_INTERVAL_SEC) * 1000UL;
#endif

  // Build and publish debug JSON with wake metrics and causes
  if (net_mqtt_is_connected()) {
    char dbg[320];
    uint32_t ms_boot_to_wifi = static_cast<uint32_t>((t1_us - t0_us) / 1000);
    uint32_t ms_wifi_to_mqtt = static_cast<uint32_t>((t2_us - t1_us) / 1000);
    uint32_t ms_sensor_read = dbg_ms_sensor;
    // Measure publish time using a non-retained probe topic
    int64_t pub_probe_start_us = esp_timer_get_time();
    net_publish_debug_probe("1", false);
    uint32_t ms_publish = static_cast<uint32_t>((esp_timer_get_time() - pub_probe_start_us) / 1000);
    // Publish diagnostics: WiFi RSSI and publish latency
    net_publish_wifi_rssi(WiFi.RSSI());
    net_publish_publish_latency_ms(ms_publish);
    uint32_t deep_sleep_us = sleep_scheduled_ms * 1000UL;
    snprintf(dbg, sizeof(dbg),
             "{\"ms_boot_to_wifi\":%u,\"ms_wifi_to_mqtt\":%u,"
             "\"ms_sensor_read\":%u,\"ms_publish\":%u,"
             "\"sleep_scheduled_ms\":%u,\"deep_sleep_us\":%u,"
             "\"reset_reason\":\"%s\",\"wakeup_cause\":\"%s\","
             "\"rtc_wake_count\":%u}",
             ms_boot_to_wifi, ms_wifi_to_mqtt, ms_sensor_read, ms_publish, sleep_scheduled_ms,
             deep_sleep_us, reset_reason_str(esp_reset_reason()),
             wakeup_cause_str(esp_sleep_get_wakeup_cause()), get_wake_count());
    net_publish_debug_json(dbg, false);
    // Publish layout identity for quick visual parity checks in dashboards
    net_publish_layout_identity();
  }

  // Allow retained MQTT to arrive quickly for outside readings (bounded)
  static bool g_outside_warned = false;
  uint32_t fetch_start_ms = millis();
  bool outside_before = net_get_outside().validTemp || net_get_outside().validHum ||
                        net_get_outside().validWeather || net_get_outside().validWind;
  Serial.println("DBG: start fetch retained");
  // Actively wait until any outside retained value arrives or timeout
  {
    uint32_t deadline = millis() + static_cast<uint32_t>(FETCH_RETAINED_TIMEOUT_MS);
    while (!(net_get_outside().validTemp || net_get_outside().validHum ||
             net_get_outside().validWeather || net_get_outside().validWind) &&
           millis() < deadline) {
      net_loop();
      delay(10);
    }
  }
  uint32_t ms_fetch = static_cast<uint32_t>(millis() - fetch_start_ms);
  Serial.printf("DBG: after fetch retained ms=%u\n", ms_fetch);
  bool outside_after = net_get_outside().validTemp || net_get_outside().validHum ||
                       net_get_outside().validWeather || net_get_outside().validWind;
  if (ms_fetch >= static_cast<uint32_t>(FETCH_RETAINED_TIMEOUT_MS) && !outside_after &&
      !outside_before && !g_outside_warned) {
    s_timeouts_mask |= TIMEOUT_BIT_FETCH;
    g_outside_warned = true;  // only warn once until outside data later appears
    Serial.printf(
        "Note: no outside retained data yet (waited %u ms). "
        "Continuing...\n",
        ms_fetch);
  }

  // Publish a retained UI-debug snapshot so tests/diagnostics can assert what
  // the device believes
  // is displayed for the OUTSIDE and footer weather blocks.
  if (net_mqtt_is_connected()) {
    OutsideReadings o = net_get_outside();
    char buf[320];
    char hhmm_dbg[8];
    net_time_hhmm(hhmm_dbg, sizeof(hhmm_dbg));
    float tempF =
        (o.validTemp && isfinite(o.temperatureC)) ? (o.temperatureC * 9.0f / 5.0f + 32.0f) : NAN;
    const char* w = (o.validWeather && o.weather[0]) ? o.weather : NULL;
    const char* wd = (o.validWeather && o.weather[0]) ? o.weather : NULL;
    const char* wi = (o.validWeather && o.weather[0]) ? o.weather : NULL;
    // Include time used for header to aid troubleshooting
    snprintf(buf, sizeof(buf),
             "{\"event\":\"ui_debug\",\"time\":\"%s\","
             "\"outside\":{\"tempF\":%s,\"rhPct\":%s,\"windMps\":%s,"
             "\"weather\":%s,\"weatherId\":%d,\"weatherDesc\":%s,"
             "\"weatherIcon\":%s}}",
             hhmm_dbg, (isfinite(tempF) ? String(tempF, 1).c_str() : "null"),
             (o.validHum && isfinite(o.humidityPct) ? String(o.humidityPct, 0).c_str() : "null"),
             (o.validWind && isfinite(o.windMps) ? String(o.windMps, 1).c_str() : "null"),
             (w ? (String("\"") + w + "\"").c_str() : "null"), 0,
             (wd ? (String("\"") + wd + "\"").c_str() : "null"),
             (wi ? (String("\"") + wi + "\"").c_str() : "null"));
    net_publish_debug_json(buf, true);
  }

  // Publish HA discovery once we have MQTT so entities auto-register in Home
  // Assistant
  if (net_mqtt_is_connected()) {
    Serial.println("DBG: before HA discovery");
    net_publish_ha_discovery();
    Serial.println("DBG: after HA discovery");
  }

#if USE_DISPLAY
  bool do_full = false;
  static uint32_t g_fw_crc = 0;
  if (g_fw_crc == 0) {
    // Derive a simple firmware identity at runtime from constants to detect
    // reflash
    // This avoids a stale partial counter blocking any draw after flashing.
    g_fw_crc = 1469598103u;
    const char* id = FW_VERSION;
    for (const char* p = id; *p; ++p) {
      g_fw_crc ^= static_cast<uint32_t>(*p);
      g_fw_crc *= 16777619u;
    }
    uint32_t stored = nvs_load_uint("fw_crc", 0);
    if (stored != g_fw_crc) {
      do_full = true;  // force at least one full render after new firmware
      nvs_store_uint("fw_crc", g_fw_crc);
      partial_counter = 0;
    }
  }
  // Full-only policy: always perform full refresh in display phase
  do_full = true;

  uint32_t display_phase_start = millis();
// Establish a soft deadline visible to drawing helpers
#ifdef DISPLAY_PHASE_TIMEOUT_MS
  g_display_deadline_ms = display_phase_start + static_cast<uint32_t>(DISPLAY_PHASE_TIMEOUT_MS);
#endif
  if (do_full) {
    Serial.println("DBG: full_refresh start");
    full_refresh();
    Serial.println("DBG: full_refresh done");
    needs_full_on_boot = false;  // one clean full render completed
  } else {
    // For simplicity and stability, prefer full refreshes over partials
    Serial.println("DBG: full_only branch (no partial draw)");
    full_refresh();
    /* Previous partial update path retained for reference
    if (g_full_only_mode) {
      Serial.println("DBG: full_only_mode=1: overriding to full");
      full_refresh();
    } else {
    Serial.println("DBG: partial draw start");
    uint32_t sens2_start = millis();
    InsideReadings r = read_inside_sensors();
    uint32_t sens2_ms = static_cast<uint32_t>(millis() - sens2_start);
    if (sens2_ms > static_cast<uint32_t>(SENSOR_PHASE_TIMEOUT_MS)) {
      s_timeouts_mask |= TIMEOUT_BIT_SENSOR;

            Serial.printf("Timeout: sensor read (secondary) exceeded budget ms=%u budget=%u\n",
                     sens2_ms,
                    static_cast<unsigned>(SENSOR_PHASE_TIMEOUT_MS));
    }
    char in_temp[16];
    if (isfinite(r.temperatureC)) {
      snprintf(in_temp,
                sizeof(in_temp),
                "%.1f",
    } else {
      snprintf(in_temp, sizeof(in_temp), "--");
    }
    char trend_in = '0';
    float now_in_f =
        isfinite(r.temperatureC) ? (r.temperatureC * 9.0f / 5.0f + 32.0f) : NAN;
    if (isfinite(now_in_f) && isfinite(last_inside_f)) {
      float d = now_in_f - last_inside_f;
      if (d >= THRESH_TEMP_F)
        trend_in = '+';
      else if (d <= -THRESH_TEMP_F)
        trend_in = '-';
    }
    // Only redraw inside temp when changed beyond threshold
    maybe_redraw_numeric(INSIDE_TEMP, now_in_f, last_inside_f, THRESH_TEMP_F,
                         [&]() { partial_update_inside_temp(in_temp,
    if (isfinite(last_inside_f))
      nvs_store_float("li_f", last_inside_f);
    // Inside RH partial update + publish only when changed beyond thresholds
    if (isfinite(r.humidityPct)) {
      char in_rh_str[16];
      snprintf(in_rh_str, sizeof(in_rh_str), "%.0f", r.humidityPct);
      maybe_redraw_numeric(INSIDE_RH, r.humidityPct, last_inside_rh, THRESH_RH,
                           [&]() { partial_update_inside_rh(in_rh_str); });
      if (isfinite(last_inside_rh))
        nvs_store_float("li_rh", last_inside_rh);
    }
    uint32_t publish_phase_start = millis();
    bool publish_any = false;
    if (isfinite(r.temperatureC) && isfinite(r.humidityPct)) {
      bool temp_changed =
          (!isfinite(last_published_inside_tempC)) ||
          fabsf(r.temperatureC - last_published_inside_tempC) >= THRESH_TEMP_C_FROM_F;
      bool rh_changed = (!isfinite(last_published_inside_rh)) ||
                        fabsf(r.humidityPct - last_published_inside_rh) >= THRESH_RH;
      if (temp_changed || rh_changed) {
        net_publish_inside(r.temperatureC, r.humidityPct);
        publish_any = true;
        last_published_inside_tempC = r.temperatureC;
        last_published_inside_rh = r.humidityPct;
        nvs_store_float("pi_t", last_published_inside_tempC);
        nvs_store_float("pi_rh", last_published_inside_rh);
      }
    }
    if (isfinite(r.pressureHPa)) {
      bool p_changed = (!isfinite(last_published_inside_pressureHPa)) ||
                                              fabsf(r.pressureHPa -
                           last_published_inside_pressureHPa) >= THRESH_PRESS_HPA;
      if (p_changed) {
        net_publish_pressure(r.pressureHPa);
        publish_any = true;
        last_published_inside_pressureHPa = r.pressureHPa;
        nvs_store_float("pi_p", last_published_inside_pressureHPa);
      }
    }

    OutsideReadings o = net_get_outside();
    if (o.validTemp) {
      char out_temp[16];
      snprintf(out_temp,
                sizeof(out_temp),
                "%.1f",
      char trend_out = '0';
      float now_out_f = o.temperatureC * 9.0f / 5.0f + 32.0f;
      if (isfinite(last_outside_f)) {
        float d = now_out_f - last_outside_f;
        if (d >= THRESH_TEMP_F)
          trend_out = '+';
        else if (d <= -THRESH_TEMP_F)
          trend_out = '-';
      }
      bool temp_changed =
          !isfinite(last_outside_f) || fabsf(now_out_f - last_outside_f) >= THRESH_TEMP_F;
      if (temp_changed && o.validHum && isfinite(o.humidityPct)) {
        // Merge redraws: update temp and RH in same wake when both changed
        maybe_redraw_numeric(OUT_TEMP, now_out_f, last_outside_f, THRESH_TEMP_F,
                             [&]() { partial_update_outside_temp(out_temp,
        char out_rh2[16];
        snprintf(out_rh2, sizeof(out_rh2), "%.0f", o.humidityPct);
        maybe_redraw_numeric(OUT_ROW2_L, o.humidityPct, last_outside_rh, THRESH_RH,
                             [&]() { partial_update_outside_rh(out_rh2); });
      } else {
        maybe_redraw_numeric(OUT_TEMP, now_out_f, last_outside_f, THRESH_TEMP_F,
                             [&]() { partial_update_outside_temp(out_temp, 'F'); });
      }
      if (isfinite(last_outside_f))
        nvs_store_float("lo_f", last_outside_f);
    }
    if (o.validHum) {
      char out_rh[16];
      snprintf(out_rh, sizeof(out_rh), "%.0f", o.humidityPct);
      maybe_redraw_numeric(OUT_ROW2_L, o.humidityPct, last_outside_rh, THRESH_RH,
                           [&]() { partial_update_outside_rh(out_rh); });
      if (isfinite(last_outside_rh))
        nvs_store_float("lo_rh", last_outside_rh);
    }
    if (o.validWeather) {
      IconId id = (o.validWeather) ? map_openweather_to_icon(o) : map_weather_to_icon(o.weather);
      maybe_redraw_value<int32_t>(OUT_ICON, static_cast<int32_t>(id), last_icon_id,
                                  [&]() {
                                    if (o.validWeather) {
                                      int rect_tmp[4] = { OUT_ICON[0],
                                                         static_cast<int16_t>(OUT_ICON[1] +
    TOP_Y_OFFSET), OUT_ICON[2], OUT_ICON[3] }; draw_in_region(rect_tmp,
                                                     [&](int16_t xx, int16_t yy, int16_t ww, int16_t
    hh) { draw_weather_icon_region_at_from_outside(xx, yy, ww, hh, o);
                                                     });
                                    } else {
                                      partial_update_weather_icon(o.weather);
                                    }
                                  });
      nvs_store_int("icon", last_icon_id);
      char sc[24];
      if (o.validWeather && o.weather[0])
        make_short_condition_cstr(o.weather, sc, sizeof(sc));
      else
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
    char hhmm2[8];
    net_time_hhmm(hhmm2, sizeof(hhmm2));
    draw_header_time(hhmm2);
    BatteryStatus bs = read_battery_status();
    char ip_c[32];
    net_ip_cstr(ip_c, sizeof(ip_c));
    if (maybe_redraw_status(bs, ip_c, STATUS_)) {
      nvs_store_uint("st_crc", last_status_crc);
    }
    // Publish battery metrics once per wake
    if (isfinite(bs.voltage) && bs.percent >= 0) {
      net_publish_battery(bs.voltage, bs.percent);
      publish_any = true;
    }
    uint32_t ms_publish_phase =
        publish_any ? static_cast<uint32_t>(millis() - publish_phase_start) : 0;
    if (publish_any
        && ms_publish_phase > static_cast<uint32_t>(PUBLISH_PHASE_TIMEOUT_MS)) {
      s_timeouts_mask |= TIMEOUT_BIT_PUBLISH;
      Serial.printf("Timeout: publish exceeded budget ms=%u budget=%u\n",
                    static_cast<unsigned>(ms_publish_phase),
                    static_cast<unsigned>(PUBLISH_PHASE_TIMEOUT_MS));
    }
    }
    */
  }
// End of display phase, check duration and clear deadline
#ifdef DISPLAY_PHASE_TIMEOUT_MS
  uint32_t ms_display = static_cast<uint32_t>(millis() - display_phase_start);
  if (ms_display > static_cast<uint32_t>(DISPLAY_PHASE_TIMEOUT_MS)) {
    s_timeouts_mask |= TIMEOUT_BIT_DISPLAY;
    Serial.printf("Timeout: display phase exceeded budget ms=%u budget=%u\n",
                  static_cast<unsigned>(ms_display),
                  static_cast<unsigned>(DISPLAY_PHASE_TIMEOUT_MS));
  }
  g_display_deadline_ms = 0;
#endif
#else
  // Headless mode: no display; still connect, read sensors, publish,
  //     and sleep
  Serial.println("DBG: headless branch start");
  uint32_t sens2_start = millis();
  InsideReadings r = read_inside_sensors();
  uint32_t sens2_ms = static_cast<uint32_t>(millis() - sens2_start);
  if (sens2_ms > static_cast<uint32_t>(SENSOR_PHASE_TIMEOUT_MS)) {
    s_timeouts_mask |= TIMEOUT_BIT_SENSOR;
    Serial.printf("Timeout: sensor read exceeded budget ms=%u budget=%u\n",
                  static_cast<unsigned>(sens2_ms), static_cast<unsigned>(SENSOR_PHASE_TIMEOUT_MS));
  }
  uint32_t publish_phase_start = millis();
  bool publish_any = false;
  if (isfinite(r.temperatureC) && isfinite(r.humidityPct)) {
    bool temp_changed = (!isfinite(last_published_inside_tempC)) ||
                        fabsf(r.temperatureC - last_published_inside_tempC) >= THRESH_TEMP_C_FROM_F;
    bool rh_changed = (!isfinite(last_published_inside_rh)) ||
                      fabsf(r.humidityPct - last_published_inside_rh) >= THRESH_RH;
    if (temp_changed || rh_changed) {
      net_publish_inside(r.temperatureC, r.humidityPct);
      publish_any = true;
      last_published_inside_tempC = r.temperatureC;
      last_published_inside_rh = r.humidityPct;
      nvs_store_float("pi_t", last_published_inside_tempC);
      nvs_store_float("pi_rh", last_published_inside_rh);
    }
  }
  if (isfinite(r.pressureHPa)) {
    float diff = fabsf(r.pressureHPa - last_published_inside_pressureHPa);
    bool p_changed = (!isfinite(last_published_inside_pressureHPa)) || (diff >= THRESH_PRESS_HPA);
    if (p_changed) {
      net_publish_pressure(r.pressureHPa);
      publish_any = true;
      last_published_inside_pressureHPa = r.pressureHPa;
      nvs_store_float("pi_p", last_published_inside_pressureHPa);
    }
  }
  // Publish a headless status heartbeat to aid validation
  {
    String ip = net_ip();
    BatteryStatus bs = read_battery_status();
    char payload[96];
    snprintf(payload, sizeof(payload), "headless=1 ip=%s v=%.2f pct=%d", ip.c_str(), bs.voltage,
             bs.percent);
    net_publish_status(payload, true);
    if (isfinite(bs.voltage) && bs.percent >= 0) {
      net_publish_battery(bs.voltage, bs.percent);
      publish_any = true;
    }
  }
  uint32_t ms_publish_phase =
      publish_any ? static_cast<uint32_t>(millis() - publish_phase_start) : 0;
  if (publish_any && ms_publish_phase > static_cast<uint32_t>(PUBLISH_PHASE_TIMEOUT_MS)) {
    s_timeouts_mask |= TIMEOUT_BIT_PUBLISH;
    Serial.printf("Timeout: publish exceeded budget ms=%u budget=%u\n",
                  static_cast<unsigned>(ms_publish_phase),
                  static_cast<unsigned>(PUBLISH_PHASE_TIMEOUT_MS));
  }
#endif

  // Emit one metrics JSON line over USB for monitor scripts
  {
    Serial.println("DBG: before metrics json");
    InsideReadings latest = read_inside_sensors();
    emit_metrics_json(latest.temperatureC, latest.humidityPct, latest.pressureHPa);
    Serial.println("DBG: after metrics json");
    Serial.printf("RTC wake count: %u\n", static_cast<unsigned>(get_wake_count()));
  }

  // Publish a concise timeout summary JSON if MQTT is connected
  if (net_mqtt_is_connected()) {
    Serial.println("DBG: before timeout summary json");
    char dbg2[192];
    snprintf(dbg2, sizeof(dbg2),
             "{\"timeouts\":%u,\"notes\":\"bits:1=sensor,2=fetch,4=display,8="
             "publish\"}",
             static_cast<unsigned>(s_timeouts_mask));
    net_publish_debug_json(dbg2, false);
    Serial.println("DBG: after timeout summary json");
  }
  // Also emit a compact timeouts mask on USB
  Serial.printf("Timeouts mask: 0x%02X\n", static_cast<unsigned>(s_timeouts_mask));
  partial_counter++;
  // Persist partial refresh cadence so it survives reset
  nvs_store_ushort("pcount", partial_counter);
  // Log awake duration and planned sleep for diagnostics
  Serial.printf("Awake ms: %u\n", static_cast<unsigned>(millis()));
  Serial.println("DBG: end of setup (pre-sleep or stay-awake)");
#if DEV_NO_SLEEP
  Serial.println("DEV_NO_SLEEP=1: staying awake for debugging");
  while (true) {
    net_loop();
    // Aggregate outside MQTT changes: debounce full refresh to avoid cycling
#if USE_DISPLAY
    static bool pending_outside_refresh = false;
    static uint32_t changed_at_ms = 0;
    if (net_consume_outside_dirty()) {
      pending_outside_refresh = true;
      changed_at_ms = millis();
    }
    // Wait a short window to coalesce multiple retained/alias updates
    if (pending_outside_refresh && (millis() - changed_at_ms) > MQTT_OUTSIDE_DEBOUNCE_MS) {
      Serial.println("DBG: debounced MQTT outside change -> full_refresh");
      full_refresh();
      pending_outside_refresh = false;
      // Reset periodic full timer to avoid double refresh soon after
      // (variable declared below)
    }
#endif
    // Handle line-oriented serial commands
    static String buf;
    while (Serial.available() > 0) {
      int ch = Serial.read();
      if (ch == '\r')
        continue;
      if (ch == '\n') {
        handle_serial_command_line(buf);
        buf = "";
      } else if (buf.length() < 96) {
        buf += static_cast<char>(ch);
      }
    }
    // Periodic USB metrics while debugging
    static uint32_t last_metrics = 0;
    if (millis() - last_metrics > 2000) {
      InsideReadings latest = read_inside_sensors();
      emit_metrics_json(latest.temperatureC, latest.humidityPct, latest.pressureHPa);
      last_metrics = millis();
    }
#if USE_DISPLAY
    // Full-only: no partials in always-on mode. Just do periodic full
    // refreshes.
    static uint32_t last_full_ms = 0;
    // If a refresh just happened due to MQTT dirty flag above, align timer
#if USE_DISPLAY
    // Note: guard to satisfy duplicate macro checkers; same condition as block
    // Adjust last_full_ms if the time since last refresh is very small
    if (last_full_ms == 0)
      last_full_ms = millis();
#endif
    if (millis() - last_full_ms > 60000u) {  // every 60 seconds
      Serial.println("DBG: periodic full_refresh (DEV_NO_SLEEP, full-only)");
      full_refresh();
      last_full_ms = millis();
    }
#endif
#if USE_STATUS_PIXEL
    status_pixel_tick();
#endif
    delay(50);
  }
#else
  // Skip deep sleep if in diagnostic mode
  if (g_diagnostic_mode) {
    Serial.println("DIAG: Staying awake in diagnostic mode");
    return;  // Exit setup, continue to loop
  }
  
#if DEV_CYCLE_MODE
  Serial.printf("Dev cycle: sleeping for %us\n",
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
  delay(5);
#endif
  // Pre-sleep heartbeat for dev cycle
  {
    char hb[96];
    snprintf(hb, sizeof(hb), "sleeping=1 sec=%u", static_cast<unsigned>(DEV_SLEEP_SEC));
    net_publish_status(hb, true);
  }
  net_prepare_for_sleep();
  go_deep_sleep_with_tracking(DEV_SLEEP_SEC);
#else
  Serial.printf("Sleeping for %us\n", static_cast<unsigned>(WAKE_INTERVAL_SEC));
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
  delay(5);
#endif
  // Pre-sleep heartbeat for normal cycle
  {
    char hb[96];
    snprintf(hb, sizeof(hb), "sleeping=1 sec=%u", static_cast<unsigned>(WAKE_INTERVAL_SEC));
    net_publish_status(hb, true);
  }
  net_prepare_for_sleep();
  go_deep_sleep_with_tracking(WAKE_INTERVAL_SEC);
#endif
#endif
}

void loop() {
  // Check for MQTT diagnostic mode commands
  bool diag_mode_value;
  if (net_check_diagnostic_mode_request(diag_mode_value)) {
    g_diagnostic_mode = diag_mode_value;
    net_publish_diagnostic_mode(g_diagnostic_mode);
    Serial.printf("DIAG: Mode changed to %s via MQTT\n", g_diagnostic_mode ? "active" : "inactive");
  }
  
  // In diagnostic mode, stay awake and publish diagnostics periodically
  if (g_diagnostic_mode) {
    // Keep network alive
    net_loop();
    
    // Publish diagnostics every DIAGNOSTIC_PUBLISH_INTERVAL_MS
    if (millis() - g_diagnostic_last_publish_ms >= DIAGNOSTIC_PUBLISH_INTERVAL_MS) {
      g_diagnostic_last_publish_ms = millis();
      
      if (net_mqtt_is_connected()) {
        Serial.println("DIAG: Publishing diagnostic data");
        
        // Update and publish memory diagnostics
        MemoryDiagnostics mem_diag = get_memory_diagnostics();
        net_publish_memory_diagnostics(mem_diag.free_heap, mem_diag.min_free_heap,
                                       mem_diag.largest_free_block, mem_diag.fragmentation_pct);
        
        // Update uptime
        uint32_t current_uptime = rtc_cumulative_uptime_sec + (millis() / 1000);
        net_publish_uptime(current_uptime);
        
        // Publish other diagnostic info
        net_publish_wake_count(get_wake_count());
        net_publish_wifi_rssi(WiFi.RSSI());
        
        // Publish detailed diagnostic JSON
        char diag_json[512];
        snprintf(diag_json, sizeof(diag_json),
                 "{\"diag_mode\":true,\"free_heap\":%u,\"min_heap\":%u,"
                 "\"fragmentation\":%.1f,\"rssi\":%d,\"uptime\":%u,"
                 "\"boot_count\":%u,\"crash_count\":%u,\"wake_count\":%u}",
                 mem_diag.free_heap, mem_diag.min_free_heap, mem_diag.fragmentation_pct,
                 WiFi.RSSI(), current_uptime, rtc_boot_count, rtc_crash_count, get_wake_count());
        net_publish_debug_json(diag_json, false);
        
        // Log to serial
        Serial.printf("DIAG: Heap: free=%u min=%u frag=%.1f%%\n",
                      mem_diag.free_heap, mem_diag.min_free_heap, mem_diag.fragmentation_pct);
      }
    }
    
    // Handle serial commands for diagnostic mode
    if (Serial.available()) {
      String cmd = Serial.readStringUntil('\n');
      cmd.trim();
      
      if (cmd == "normal" || cmd == "exit") {
        Serial.println("DIAG: Exiting diagnostic mode");
        g_diagnostic_mode = false;
        net_publish_diagnostic_mode(false);
      } else if (cmd == "memtest") {
        Serial.println("DIAG: Running memory test");
        MemoryDiagnostics mem = get_memory_diagnostics();
        Serial.printf("  Free: %u bytes\n", mem.free_heap);
        Serial.printf("  Min:  %u bytes\n", mem.min_free_heap);
        Serial.printf("  Largest block: %u bytes\n", mem.largest_free_block);
        Serial.printf("  Fragmentation: %.1f%%\n", mem.fragmentation_pct);
      } else if (cmd == "sensortest") {
        Serial.println("DIAG: Testing sensors");
        InsideReadings ir = read_inside_sensors();
        Serial.printf("  Temp: %.2f°C\n", ir.temperatureC);
        Serial.printf("  Humidity: %.1f%%\n", ir.humidityPct);
        Serial.printf("  Pressure: %.1f hPa\n", ir.pressureHPa);
      } else if (cmd == "wifitest") {
        Serial.println("DIAG: WiFi scan");
        int n = WiFi.scanNetworks();
        Serial.printf("  Found %d networks\n", n);
        for (int i = 0; i < n && i < 10; i++) {
          Serial.printf("  %d: %s (%d dBm)\n", i+1, WiFi.SSID(i).c_str(), WiFi.RSSI(i));
        }
      }
    }
    
    delay(100);
  } else {
    // Normal mode: deep sleep from setup, shouldn't reach here
    delay(1000);
  }
}
