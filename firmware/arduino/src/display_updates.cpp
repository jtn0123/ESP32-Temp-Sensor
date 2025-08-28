// Display partial updates implementation
#include "display_updates.h"

#if USE_DISPLAY

#include <GxEPD2_BW.h>
#include "display_layout.h"
#include "display_renderer.h"
#include "icons.h"
#include "generated_config.h"

// External display object
#if EINK_PANEL_DEPG0213BN
extern GxEPD2_BW<GxEPD2_213_DEPG0213BN, GxEPD2_213_DEPG0213BN::HEIGHT> display;
#else
extern GxEPD2_BW<GxEPD2_213_GDEY0213B74, GxEPD2_213_GDEY0213B74::HEIGHT> display;
#endif

// External variables
extern uint16_t partial_counter;
extern bool g_full_only_mode;

// Constants
#define TOP_Y_OFFSET 4
#define TEMP_DOWN_ADJ 20
#define MAX_PARTIAL_UPDATES 10

// Rectangle aliases
#define INSIDE_TEMP RECT_INSIDE_TEMP
#define INSIDE_HUMIDITY RECT_INSIDE_HUMIDITY
#define OUT_TEMP RECT_OUT_TEMP
#define OUT_RH RECT_OUT_HUMIDITY
#define OUT_WEATHER RECT_OUT_WEATHER
#define OUT_WIND RECT_OUT_WIND
#define WEATHER_ICON RECT_WEATHER_ICON
#define FOOTER_R RECT_FOOTER_WEATHER

// Helper to check if partial update should be done
bool should_partial_update(uint16_t counter, bool full_only_mode) {
  return !full_only_mode && counter < MAX_PARTIAL_UPDATES;
}

// Helper to increment partial counter
void increment_partial_counter() {
  partial_counter++;
}

// Partial update for inside temperature
void partial_update_inside_temp(const char* in_temp_f, char trend) {
  if (!should_partial_update(partial_counter, g_full_only_mode)) {
    return;
  }
  
  int rect[4] = {INSIDE_TEMP[0], static_cast<int16_t>(INSIDE_TEMP[1] + TOP_Y_OFFSET),
                 INSIDE_TEMP[2], INSIDE_TEMP[3]};
  
  draw_in_region(rect, [&](int16_t x, int16_t y, int16_t w, int16_t h) {
    display.setTextColor(GxEPD_BLACK);
    display.setTextSize(2);
    
    // Draw temperature value
    char buf[16];
    snprintf(buf, sizeof(buf), "%s", in_temp_f);
    
    int16_t x1, y1;
    uint16_t bw, bh;
    display.getTextBounds(buf, 0, 0, &x1, &y1, &bw, &bh);
    
    int16_t targetX = x + (w - static_cast<int16_t>(bw)) / 2;
    int16_t targetY = y + (h - static_cast<int16_t>(bh)) / 2;
    int16_t baseX = targetX - x1;
    int16_t baseY = targetY - y1 + TEMP_DOWN_ADJ;
    
    display.setCursor(baseX, baseY);
    display.print(buf);
    
    // Draw degree symbol and F
    display.setTextSize(1);
    display.setCursor(baseX + static_cast<int16_t>(bw) + 2, baseY - 8);
    display.print("\xF8");
    display.setCursor(baseX + static_cast<int16_t>(bw) + 8, baseY - 8);
    display.print("F");
    
    // Draw trend indicator if present
    if (trend == '+' || trend == '-') {
      display.setCursor(baseX + static_cast<int16_t>(bw) + 16, baseY - 8);
      display.print(trend);
    }
  });
  
  increment_partial_counter();
}

// Partial update for outside temperature
void partial_update_outside_temp(const char* out_temp_f, char trend) {
  if (!should_partial_update(partial_counter, g_full_only_mode)) {
    return;
  }
  
  int rect[4] = {OUT_TEMP[0], static_cast<int16_t>(OUT_TEMP[1] + TOP_Y_OFFSET), 
                 OUT_TEMP[2], OUT_TEMP[3]};
  
  draw_in_region(rect, [&](int16_t x, int16_t y, int16_t w, int16_t h) {
    display.setTextColor(GxEPD_BLACK);
    display.setTextSize(2);
    
    char buf[16];
    snprintf(buf, sizeof(buf), "%s", out_temp_f);
    
    int16_t x1, y1;
    uint16_t bw, bh;
    display.getTextBounds(buf, 0, 0, &x1, &y1, &bw, &bh);
    
    int16_t targetX = x + (w - static_cast<int16_t>(bw)) / 2;
    int16_t targetY = y + (h - static_cast<int16_t>(bh)) / 2;
    int16_t baseX = targetX - x1;
    int16_t baseY = targetY - y1 + TEMP_DOWN_ADJ;
    
    display.setCursor(baseX, baseY);
    display.print(buf);
    
    // Draw units
    display.setTextSize(1);
    display.setCursor(baseX + static_cast<int16_t>(bw) + 2, baseY - 8);
    display.print("\xF8");
    display.setCursor(baseX + static_cast<int16_t>(bw) + 8, baseY - 8);
    display.print("F");
  });
  
  increment_partial_counter();
}

// Partial update for outside humidity
void partial_update_outside_rh(const char* out_rh) {
  if (!should_partial_update(partial_counter, g_full_only_mode)) {
    return;
  }
  
  int rect[4] = {OUT_RH[0], static_cast<int16_t>(OUT_RH[1] + TOP_Y_OFFSET),
                 OUT_RH[2], OUT_RH[3]};
  
  draw_in_region(rect, [&](int16_t x, int16_t y, int16_t w, int16_t h) {
    display.setTextColor(GxEPD_BLACK);
    display.setTextSize(1);
    display.setCursor(x + 2, y + h - 6);
    display.print(out_rh);
    display.print("%");
  });
  
  increment_partial_counter();
}

// Partial update for inside humidity
void partial_update_inside_rh(const char* in_rh) {
  if (!should_partial_update(partial_counter, g_full_only_mode)) {
    return;
  }
  
  int rect[4] = {INSIDE_HUMIDITY[0], static_cast<int16_t>(INSIDE_HUMIDITY[1] + TOP_Y_OFFSET),
                 INSIDE_HUMIDITY[2], INSIDE_HUMIDITY[3]};
  
  draw_in_region(rect, [&](int16_t x, int16_t y, int16_t w, int16_t h) {
    display.setTextColor(GxEPD_BLACK);
    display.setTextSize(1);
    display.setCursor(x + 2, y + h - 6);
    display.print(in_rh);
    display.print("%");
  });
  
  increment_partial_counter();
}

// Partial update for weather icon
void partial_update_weather_icon(const char* weather) {
  if (!should_partial_update(partial_counter, g_full_only_mode)) {
    return;
  }
  
  int rect[4] = {WEATHER_ICON[0], static_cast<int16_t>(WEATHER_ICON[1] + TOP_Y_OFFSET),
                 WEATHER_ICON[2], WEATHER_ICON[3]};
  
  draw_in_region(rect, [&](int16_t x, int16_t y, int16_t w, int16_t h) {
    draw_weather_icon_region_at(x, y, w, h, weather);
  });
  
  increment_partial_counter();
}

// Partial update for outside wind
void partial_update_outside_wind(const char* wind_str) {
  if (!should_partial_update(partial_counter, g_full_only_mode)) {
    return;
  }
  
  int rect[4] = {OUT_WIND[0], static_cast<int16_t>(OUT_WIND[1] + TOP_Y_OFFSET),
                 OUT_WIND[2], OUT_WIND[3]};
  
  draw_in_region(rect, [&](int16_t x, int16_t y, int16_t w, int16_t h) {
    display.setTextColor(GxEPD_BLACK);
    display.setTextSize(1);
    display.setCursor(x + 2, y + h - 6);
    display.print(wind_str);
  });
  
  increment_partial_counter();
}

// Partial update for outside weather condition
void partial_update_outside_condition(const char* short_condition) {
  if (!should_partial_update(partial_counter, g_full_only_mode)) {
    return;
  }
  
  int rect[4] = {OUT_WEATHER[0], static_cast<int16_t>(OUT_WEATHER[1] + TOP_Y_OFFSET),
                 OUT_WEATHER[2], OUT_WEATHER[3]};
  
  draw_in_region(rect, [&](int16_t x, int16_t y, int16_t w, int16_t h) {
    display.setTextColor(GxEPD_BLACK);
    display.setTextSize(1);
    display.setCursor(x + 2, y + h - 6);
    display.print(short_condition);
  });
  
  increment_partial_counter();
}

// Partial update for high/low temperatures
void partial_update_outside_hilo(float highC, float lowC) {
  if (!should_partial_update(partial_counter, g_full_only_mode)) {
    return;
  }
  
  // This would update a specific region for high/low temps
  // Implementation details to be moved from main.cpp
  
  char buf[32];
  if (isfinite(highC) && isfinite(lowC)) {
    float highF = highC * 9.0f / 5.0f + 32.0f;
    float lowF = lowC * 9.0f / 5.0f + 32.0f;
    snprintf(buf, sizeof(buf), "H:%.0f L:%.0f", highF, lowF);
    
    // Draw in appropriate region
    // TODO: Define proper region for high/low display
  }
  
  increment_partial_counter();
}

// Partial update footer weather from outside readings
void partial_update_footer_weather_from_outside(const OutsideReadings& o) {
  if (!should_partial_update(partial_counter, g_full_only_mode)) {
    return;
  }
  
  int rect[4] = {FOOTER_R[0], static_cast<int16_t>(FOOTER_R[1] + TOP_Y_OFFSET),
                 FOOTER_R[2], FOOTER_R[3]};
  
  draw_in_region(rect, [&](int16_t x, int16_t y, int16_t w, int16_t h) {
    display.setTextColor(GxEPD_BLACK);
    display.setTextSize(1);
    
    // Draw weather info in footer
    if (o.validWeather) {
      // Draw small weather icon
      int16_t iconSize = 16;
      draw_weather_icon_region_at(x + 2, y + 2, iconSize, iconSize, o.weather);
      
      // Draw temperature if valid
      if (o.validTemp) {
        char tempStr[8];
        float tempF = o.temperatureC * 9.0f / 5.0f + 32.0f;
        snprintf(tempStr, sizeof(tempStr), "%.0f°", tempF);
        display.setCursor(x + iconSize + 4, y + h - 6);
        display.print(tempStr);
      }
    }
  });
  
  increment_partial_counter();
}

#endif // USE_DISPLAY