// Display rendering implementation
#include "display_renderer.h"

#if USE_DISPLAY

#include <GxEPD2_BW.h>
#include "display_layout.h"
#include "display_manager.h"
#include "icons.h"
#include "generated_config.h"
#include "ui_ops_generated.h"
#if USE_UI_SPEC
#include "ui_generated.h"
using namespace ui;
#endif
#include "net.h"
#include "metrics_diagnostics.h"

// External display object from main.cpp
#if EINK_PANEL_DEPG0213BN
extern GxEPD2_BW<GxEPD2_213_DEPG0213BN, GxEPD2_213_DEPG0213BN::HEIGHT> display;
#else
extern GxEPD2_BW<GxEPD2_213_GDEY0213B74, GxEPD2_213_GDEY0213B74::HEIGHT> display;
#endif

// External variables from main.cpp
extern float get_last_outside_f();
extern uint16_t partial_counter;
extern bool g_full_only_mode;

// Constants for display layout
#define TOP_Y_OFFSET 4
#define HEADER_NAME_Y_ADJ -8
#define TEMP_Y_ADJ -40
#define TEMP_UNITS_Y_ADJ 20
#define TEMP_DOWN_ADJ 20
#define STATUS_Y_ADJ -4

// Rectangle aliases for backward compatibility
// Layout variables are now defined without RECT_ prefix in display_layout.h
// Using them directly - no aliases needed
#define OUT_RH OUT_HUMIDITY
#define FOOTER_R FOOTER_WEATHER
#define STATUS_ FOOTER_STATUS

// Implementation for draw_in_region with lambda that takes coordinates
void draw_in_region(const int rect[4], DrawFnLambda drawFn) {
  int16_t x = rect[0];
  int16_t y = static_cast<int16_t>(rect[1] + TOP_Y_OFFSET);
  int16_t w = rect[2];
  int16_t h = rect[3];
  
  // Clear the region
  display.fillRect(x, y, w, h, GxEPD_WHITE);
  
  // Call the drawing function with coordinates
  drawFn(x, y, w, h);
  
  // Update the display window
  display.displayWindow(x, y, w, h);
}

// Implementation for draw_in_region with simple function
void draw_in_region(const int rect[4], DrawFnFwd drawFn) {
  int16_t x = rect[0];
  int16_t y = static_cast<int16_t>(rect[1] + TOP_Y_OFFSET);
  int16_t w = rect[2];
  int16_t h = rect[3];
  
  // Clear the region
  display.fillRect(x, y, w, h, GxEPD_WHITE);
  
  // Call the drawing function (no parameters)
  drawFn();
  
  // Update the display window
  display.displayWindow(x, y, w, h);
}

// Template version for lambda functions with captures
template <typename DrawFn>
inline void draw_in_region(const int rect[4], DrawFn drawFn) {
  const int16_t x = rect[0];
  const int16_t y = static_cast<int16_t>(rect[1] + TOP_Y_OFFSET);
  const int16_t w = rect[2];
  const int16_t h = rect[3];
  
  // Align partial window to 8-pixel byte boundaries on X for SSD1680-class panels
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

// Helper to draw right-aligned text
void draw_right_aligned_text_in_rect(const int rect[4], const char* text,
                                     int16_t text_width) {
  int16_t x = rect[0];
  int16_t y = static_cast<int16_t>(rect[1] + TOP_Y_OFFSET);
  int16_t w = rect[2];
  int16_t h = rect[3];
  
  display.setTextColor(GxEPD_BLACK);
  display.setTextSize(1);
  display.setCursor(x + w - text_width - 2, y + h - 6);
  display.print(text);
}

// Draw temperature with units
void draw_temp_number_and_units(const int r[4], const char* t) {
  draw_in_region(r, [&](int16_t x, int16_t y, int16_t w, int16_t h) {
    display.setTextColor(GxEPD_BLACK);
    display.setTextSize(2);
    
    int16_t x1, y1;
    uint16_t bw, bh;
    display.getTextBounds(t, 0, 0, &x1, &y1, &bw, &bh);
    
    int16_t targetX = x + (w - static_cast<int16_t>(bw)) / 2;
    int16_t targetY = y + (h - static_cast<int16_t>(bh)) / 2;
    int16_t baseX = targetX - x1;
    int16_t baseY = targetY - y1 + TEMP_DOWN_ADJ;
    
    display.setCursor(baseX, baseY);
    display.print(t);
    
    // Draw units
    display.setTextSize(1);
    display.setCursor(baseX + static_cast<int16_t>(bw) + 2, baseY - 8);
    display.print("\xF8");
    display.setCursor(baseX + static_cast<int16_t>(bw) + 8, baseY - 8);
    display.print("F");
  });
}

// Direct temperature drawing (without region clearing)
void draw_temp_number_and_units_direct(int16_t x, int16_t y, int16_t w, int16_t h,
                                       const char* t) {
  display.setTextColor(GxEPD_BLACK);
  display.setTextSize(2);
  
  int16_t x1, y1;
  uint16_t bw, bh;
  display.getTextBounds(t, 0, 0, &x1, &y1, &bw, &bh);
  
  int16_t targetX = x + (w - static_cast<int16_t>(bw)) / 2;
  int16_t targetY = y + (h - static_cast<int16_t>(bh)) / 2;
  int16_t baseX = targetX - x1;
  int16_t baseY = targetY - y1 + TEMP_DOWN_ADJ;
  
  display.setCursor(baseX, baseY);
  display.print(t);
  
  // Draw units
  display.setTextSize(1);
  display.setCursor(baseX + static_cast<int16_t>(bw) + 2, baseY - 8);
  display.print("\xF8");
  display.setCursor(baseX + static_cast<int16_t>(bw) + 8, baseY - 8);
  display.print("F");
}

// Draw header time
void draw_header_time(const char* time_str) {
  // For display_renderer, we call the direct function without region management
  // Region management is handled by the calling context (full refresh, etc.)
  draw_header_time_direct(time_str);
}

// Draw status line with battery and IP
void draw_status_line(const BatteryStatus& bs, const char* ip_cstr) {
  // For display_renderer, we call the direct function without region management
  // Region management is handled by the calling context (full refresh, etc.)
  draw_status_line_direct(bs, ip_cstr);
}

// Draw weather icon based on condition string
void draw_weather_icon_region_at(int16_t x, int16_t y, int16_t w, int16_t h,
                                 const char* condition) {
  // Map condition to icon (simplified - full implementation in main.cpp)
  if (!condition) return;
  
  // Draw the appropriate weather icon
  // This would call the icon drawing functions from icons.h
  // Implementation details to be moved from main.cpp
}

// Draw weather icon from outside readings
void draw_weather_icon_region_at_from_outside(int16_t x, int16_t y, int16_t w, int16_t h,
                                              const OutsideReadings& outh) {
  if (outh.validWeather && outh.weather[0]) {
    draw_weather_icon_region_at(x, y, w, h, outh.weather);
  }
}

// Full display refresh
void full_refresh() {
  display.setFullWindow();
  display.firstPage();
  do {
    // Draw static chrome
    draw_static_chrome();
    
    // Draw current time
    char time_str[6];
    net_time_hhmm(time_str, sizeof(time_str));
    draw_header_time_direct(time_str);
    
    // Get sensor readings
    char in_temp[8] = "--";
    char in_rh[8] = "--";
    char out_temp[8] = "--"; 
    char out_rh[8] = "--";
    
    // TODO: Get actual sensor values
    // This will be filled in when moving the full implementation
    
    // Draw inside temperature
    draw_temp_number_and_units_direct(INSIDE_TEMP[0],
                                      static_cast<int16_t>(INSIDE_TEMP[1] + TOP_Y_OFFSET),
                                      INSIDE_TEMP[2], INSIDE_TEMP[3], in_temp);
    
    // Draw outside temperature
    draw_temp_number_and_units_direct(OUT_TEMP[0],
                                      static_cast<int16_t>(OUT_TEMP[1] + TOP_Y_OFFSET),
                                      OUT_TEMP[2], OUT_TEMP[3], out_temp);
    
    // TODO: Draw humidity, weather icon, status line
    
  } while (display.nextPage());
  
  // Reset partial counter after full refresh
  partial_counter = 0;
}

// Smoke test for display
void smoke_full_window_test() {
  Serial.println(F("Display smoke test"));
  display.setFullWindow();
  display.firstPage();
  do {
    display.fillScreen(GxEPD_WHITE);
    display.setTextColor(GxEPD_BLACK);
    display.setTextSize(2);
    display.setCursor(20, 60);
    display.print(F("ESP32 READY"));
  } while (display.nextPage());
}

// Development display tick (for testing)
void dev_display_tick() {
  #if SMOKE_TEST || DEV_DISPLAY_TEST
  static uint32_t last_tick = 0;
  uint32_t now = millis();
  
  if (now - last_tick >= 5000) {
    smoke_full_window_test();
    last_tick = now;
  }
  #endif
}

// Draw from UI spec (generated UI)
void draw_from_spec_full(uint8_t variantId) {
  #if USE_UI_SPEC
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
  display.drawLine(1, 16 + TOP_Y_OFFSET, EINK_WIDTH - 2, 16 + TOP_Y_OFFSET, GxEPD_BLACK);
  display.drawLine(125, 18 + TOP_Y_OFFSET, 125, EINK_HEIGHT - 2, GxEPD_BLACK);
  
  // Process all UI operations from the spec
  // (Full implementation would continue here - keeping minimal for now)
  #endif
}

// Weather icon mapping functions
IconId map_weather_to_icon(const char* w) {
  String s(w);
  s.toLowerCase();
  // First handle Home Assistant recommended values exactly
  
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

// Map OpenWeather primary item (id/icon) to our icon set; fallback to string mapping
IconId map_openweather_to_icon(const OutsideReadings& o) {
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
  if (o.validWeather && o.weather[0])
    return map_weather_to_icon(o.weather);
  return ICON_WEATHER_SUNNY;
}

// Draw sensor values on display
void draw_values(const char* in_temp_f, const char* in_rh, const char* out_temp_f,
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

#if USE_UI_SPEC
// Utility to map RectId->rect pointer
const int* rect_ptr_by_id(uint8_t rid) {
  switch (rid) {
    case ui::RECT_HEADER_NAME:
      return HEADER_NAME;
    case ui::RECT_HEADER_TIME_CENTER:
      return HEADER_TIME_CENTER;
    // Legacy alias - RECT_HEADER_CENTER doesn't exist anymore
    case ui::RECT_INSIDE_TEMP:
      return INSIDE_TEMP;
    case ui::RECT_INSIDE_HUMIDITY:
      return INSIDE_HUMIDITY;
    case ui::RECT_INSIDE_PRESSURE:
      return INSIDE_PRESSURE;
    case ui::RECT_OUT_TEMP:
      return OUT_TEMP;
    case ui::RECT_WEATHER_ICON:
      return WEATHER_ICON;
    case ui::RECT_OUT_WEATHER:
      return OUT_WEATHER;
    case ui::RECT_OUT_PRESSURE:
      return OUT_PRESSURE;
    case ui::RECT_OUT_HUMIDITY:
      return OUT_HUMIDITY;
    case ui::RECT_OUT_WIND:
      return OUT_WIND;
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
#endif

#endif // USE_DISPLAY