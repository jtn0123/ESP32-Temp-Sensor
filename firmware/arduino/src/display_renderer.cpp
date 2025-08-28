// Display rendering implementation
#include "display_renderer.h"

#if USE_DISPLAY

#include <GxEPD2_BW.h>
#include "display_layout.h"
#include "display_manager.h"
#include "icons.h"
#include "generated_config.h"
#include "ui_ops_generated.h"
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
#define INSIDE_TEMP RECT_INSIDE_TEMP
#define INSIDE_HUMIDITY RECT_INSIDE_HUMIDITY
#define OUT_TEMP RECT_OUT_TEMP
#define OUT_RH RECT_OUT_HUMIDITY
#define OUT_WEATHER RECT_OUT_WEATHER
#define WEATHER_ICON RECT_WEATHER_ICON
#define FOOTER_R RECT_FOOTER_WEATHER
#define STATUS_ RECT_FOOTER_STATUS

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
  // This will call the generated UI drawing functions
  // Implementation to be moved from main.cpp
  
  #ifdef UI_DRAW_FULL_VARIANT
  UI_DRAW_FULL_VARIANT(variantId);
  #endif
}

#endif // USE_DISPLAY