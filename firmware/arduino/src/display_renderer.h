#pragma once

// Display rendering module - core drawing functions
// Handles full refresh, static chrome, and complex rendering operations

#include <Arduino.h>
#include "common_types.h"
#include "config.h"

#if USE_DISPLAY

// Drawing function types
typedef void (*DrawFnLambda)(int16_t x, int16_t y, int16_t w, int16_t h);
typedef void (*DrawFnPtr)(int16_t x, int16_t y, int16_t w, int16_t h, void* ctx);
typedef void (*DrawFnFwd)();

// Core rendering functions
void full_refresh();
void smoke_full_window_test();
void draw_from_spec_full(uint8_t variantId);

// Component drawing functions
void draw_header_time(const char* time_str);
void draw_status_line(const BatteryStatus& bs, const char* ip_cstr);
void draw_weather_icon_region_at(int16_t x, int16_t y, int16_t w, int16_t h,
                                 const char* condition);
void draw_weather_icon_region_at_from_outside(int16_t x, int16_t y, int16_t w, int16_t h,
                                              const OutsideReadings& outh);

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

// Development/debug functions
void dev_display_tick();

#endif // USE_DISPLAY