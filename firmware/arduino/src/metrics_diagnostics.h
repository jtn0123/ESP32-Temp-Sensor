#pragma once

// Metrics and diagnostics module
// Handles telemetry, debugging, and diagnostic mode operations

#include <Arduino.h>
#include "common_types.h"

// Diagnostic mode management
bool is_diagnostic_mode_active();
void set_diagnostic_mode(bool active);
bool check_rapid_reset_diagnostic_trigger();

// Metrics publishing
void emit_metrics_json(float tempC, float rhPct, float pressHPa);
void publish_layout_identity();

// Network pumping for MQTT message reception
void pump_network_ms(uint32_t duration_ms);

// Time utilities
void net_time_hhmm(char* out, size_t out_size);

// Status pixel operations (if enabled)
#if USE_STATUS_PIXEL
void status_pixel_begin();
void status_pixel_off();
void status_pixel_tick();
#endif