#pragma once

// Display partial updates module
// Handles incremental display updates for power efficiency

#include <Arduino.h>
#include "common_types.h"

#if USE_DISPLAY

// Partial update functions for individual UI elements
void partial_update_inside_temp(const char* in_temp_f, char trend = ' ');
void partial_update_outside_temp(const char* out_temp_f, char trend = ' ');
void partial_update_inside_rh(const char* in_rh);
void partial_update_outside_rh(const char* out_rh);
void partial_update_weather_icon(const char* weather);
void partial_update_outside_wind(const char* wind_str);
void partial_update_outside_condition(const char* short_condition);
void partial_update_outside_hilo(float highC, float lowC);
void partial_update_footer_weather_from_outside(const OutsideReadings& o);

// Helper to check if partial update is needed
bool should_partial_update(uint16_t counter, bool full_only_mode);

// Helper to increment partial counter
void increment_partial_counter();

#endif // USE_DISPLAY