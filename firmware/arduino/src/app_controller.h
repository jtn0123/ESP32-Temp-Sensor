#pragma once
// Application controller module
// Orchestrates setup and main loop

#include <Arduino.h>

// Application initialization
void app_setup();

// Main application loop
void app_loop();

// Phase management
void run_sensor_phase();
void run_network_phase();
void run_display_phase();
void run_sleep_phase();

// Application state
bool is_first_boot();
uint32_t get_wake_time_ms();