#pragma once

// State management module - RTC state persistence
// Manages all RTC_DATA_ATTR variables that persist across deep sleep

#include <Arduino.h>
#include <esp_system.h>
#include "common_types.h"

// Display state tracking
uint16_t get_partial_counter();
void set_partial_counter(uint16_t count);
void increment_partial_counter();
void reset_partial_counter();

// Temperature state tracking
float get_last_inside_f();
void set_last_inside_f(float temp);
float get_last_outside_f();
void set_last_outside_f(float temp);
float get_last_outside_rh();
void set_last_outside_rh(float rh);
float get_last_inside_rh();
void set_last_inside_rh(float rh);

// Published sensor state
float get_last_published_inside_tempC();
void set_last_published_inside_tempC(float temp);
float get_last_published_inside_rh();
void set_last_published_inside_rh(float rh);
float get_last_published_inside_pressureHPa();
void set_last_published_inside_pressureHPa(float pressure);

// Weather icon state
int32_t get_last_icon_id();
void set_last_icon_id(int32_t id);

// CRC state for change detection
uint32_t get_last_footer_weather_crc();
void set_last_footer_weather_crc(uint32_t crc);
uint32_t get_last_status_crc();
void set_last_status_crc(uint32_t crc);

// Display refresh state
bool needs_full_refresh_on_boot();
void set_needs_full_refresh_on_boot(bool needs);

// Initialize all RTC state to defaults
void init_rtc_state();

// Load cached values from NVS if not already set
void nvs_load_cache_if_unset();

// Full-only mode management
bool get_full_only_mode();
void set_full_only_mode(bool mode);