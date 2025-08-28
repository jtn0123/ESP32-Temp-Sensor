// full_refresh_v2 moved below includes and constants
#include <esp_system.h>
#include <esp_timer.h>
#include <esp_heap_caps.h>
#include <cstdio>

// Copyright 2024 Justin

#include <Arduino.h>
#include <Preferences.h>

#include "config.h"
#ifdef LOG_ENABLED
#include "logging/logger.h"
#include "logging/log_mqtt.h"
#endif
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
using namespace ui;
#endif
#include "generated_config.h"
#include "net.h"
#include "power.h"
#include "sensors.h"
#include "system_manager.h"
#include "state_manager.h"
#include "metrics_diagnostics.h"
#include "app_controller.h"
#if USE_DISPLAY
#include "display_manager.h"
#include "display_renderer.h"
#include "display_updates.h"
#endif

// Display constant aliases moved to display_renderer.h

// status_pixel functions moved to metrics_diagnostics module
#if USE_STATUS_PIXEL
// status_pixel functions moved to metrics_diagnostics module
#endif

#if USE_DISPLAY && DEV_NO_SLEEP
// In always-on display builds, tick the UI when outside MQTT values change
// dev_display_tick moved to display_updates module
#endif

// Most display functions are now declared in display_manager.h
// No need to redeclare them here since they're implemented in this file
#if USE_DISPLAY
// Accessor to avoid forward reference ordering issues
// Implemented below, declared in display_manager.h
static bool maybe_redraw_status(const BatteryStatus& bs, const char* ip_cstr, const int rect[4]);
template <typename DrawFnFwd>
static inline void draw_in_region(const int rect[4], DrawFnFwd drawFn);
// Forward decls used by spec renderer - function moved to display_renderer module
#if USE_UI_SPEC
// Minimal spec interpreter (full-window only) for variant rendering
static void draw_from_spec_full(uint8_t variantId);

// UI spec functions moved to display_renderer module

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

// partial_counter now managed by state_manager
// Wake count now managed by system_manager
// last_inside_f and last_outside_f moved to state_manager
// get_last_outside_f() now in state_manager
// last_outside_rh moved to state_manager
// State variables moved to state_manager module:
// - last_icon_id
// - last_footer_weather_crc  
// - last_published_inside_tempC
// - last_published_inside_rh
// - last_published_inside_pressureHPa
// - last_status_crc
// last_inside_rh moved to state_manager

// Diagnostic counters moved to metrics_diagnostics module
// Diagnostic mode state moved to metrics_diagnostics module

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
// get_last_outside_f() forward declaration now in state_manager
static const char* reset_reason_str(esp_reset_reason_t r);
static const char* wakeup_cause_str(esp_sleep_wakeup_cause_t c);

// Function moved to display_renderer module

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
// needs_full_on_boot now managed in state_manager module
// g_full_only_mode now managed in state_manager module
#ifdef FORCE_FULL_ONLY
// Initialize at startup to force full refresh mode
static bool init_full_mode_at_start = []() { 
  set_full_only_mode(true); 
  return true; 
}();
#endif

// Preferences object now managed in system_manager

// Implementation of NVS cache loading - uses RTC variables local to main.cpp
// Function moved to state_manager module
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

// Function moved to metrics_diagnostics module

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

// Function moved to metrics_diagnostics module

// Function moved to metrics_diagnostics module

// Function moved to metrics_diagnostics module
#endif

// Function moved to metrics_diagnostics module

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



// Function moved to metrics_diagnostics module


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
// draw_status_line moved to display_renderer module

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

// Function moved to display_renderer module

// Function moved to display_renderer module

// fast_crc32 function moved to system_manager module

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
  if (crc != get_last_status_crc()) {
    draw_status_line(bs, ip_cstr);
    set_last_status_crc(crc);
    return true;
  }
  return false;
}

// Moved to display_manager.cpp

// Function moved to display_renderer module

// Moved to display_manager.cpp

// Function moved to display_renderer module

// Moved to display_manager.cpp
#endif // USE_DISPLAY guard for draw_in_region template and related functions

#if USE_DISPLAY
// Function moved to display_renderer module

// map_weather_to_icon function moved to display_renderer module

// map_openweather_to_icon function moved to display_renderer module
#endif // USE_DISPLAY

// Draw weather icon region using OutsideReadings object (prefer OpenWeather
// hints)
#if USE_DISPLAY
// Functions moved to display_renderer module

// Function moved to display_renderer module

// Function moved to display_renderer module

// Removed minimal debug full_refresh

// All partial_update_* functions moved to display_updates module
#endif // USE_DISPLAY

#if USE_DISPLAY && DEV_NO_SLEEP
// Periodic UI updater for always-on display build. Applies partial redraws when
// outside MQTT values change beyond thresholds. Also refreshes header time and
// status line opportunistically.
// Function moved to display_updates module
#endif  // USE_DISPLAY && DEV_NO_SLEEP

// Module registration for logging
#ifdef LOG_ENABLED
LOG_MODULE("MAIN");
#endif

// Original setup has been moved to app_controller.cpp
// The full implementation is now in app_controller.cpp
// See git history for the original 721-line setup() function

// ============= MAIN ENTRY POINTS =============

// Simplified setup - delegates to app_controller
void setup() {
  app_setup();
}

void loop() {
  // Main loop logic moved to app_controller
  app_loop();
}
