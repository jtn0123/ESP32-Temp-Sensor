#pragma once

// Display rendering module - core drawing functions
// Handles full refresh, static chrome, and complex rendering operations

#include <Arduino.h>
#include "common_types.h"
#include "config.h"
#include "display_layout.h"
#include "icons.h"

#if USE_DISPLAY

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

// Drawing function types
typedef void (*DrawFnLambda)(int16_t x, int16_t y, int16_t w, int16_t h);
typedef void (*DrawFnPtr)(int16_t x, int16_t y, int16_t w, int16_t h, void* ctx);
typedef void (*DrawFnFwd)();

// Core rendering functions
void full_refresh();
void smoke_full_window_test();

#if USE_UI_SPEC
// UI spec functions
void draw_from_spec_full(uint8_t variantId);
const int* rect_ptr_by_id(uint8_t rid);
#endif

// Component drawing functions
void draw_header_time(const char* time_str);
void draw_status_line(const BatteryStatus& bs, const char* ip_cstr);
void draw_weather_icon_region_at(int16_t x, int16_t y, int16_t w, int16_t h,
                                 const char* condition);
void draw_weather_icon_region_at_from_outside(int16_t x, int16_t y, int16_t w, int16_t h,
                                              const OutsideReadings& outh);

// Weather icon determination
IconId map_weather_to_icon(const char* w);
IconId map_openweather_to_icon(const OutsideReadings& o);

// Helper functions for region drawing
void draw_in_region(const int rect[4], DrawFnLambda drawFn);
void draw_in_region(const int rect[4], DrawFnFwd drawFn);

// Template version for lambda functions with captures
template <typename DrawFn>
inline void draw_in_region(const int rect[4], DrawFn drawFn);

// Text drawing helpers
void draw_temp_number_and_units(const int r[4], const char* t);
void draw_temp_number_and_units_direct(int16_t x, int16_t y, int16_t w, int16_t h,
                                       const char* t);
void draw_right_aligned_text_in_rect(const int rect[4], const char* text,
                                     int16_t text_width);

// Value drawing functions
void draw_values(const char* in_temp_f, const char* in_rh, const char* out_temp_f,
                const char* out_rh, const char* time_str, const char* status);

// Development/debug functions
void dev_display_tick();

#endif // USE_DISPLAY