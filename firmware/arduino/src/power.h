#pragma once
// Power management module
// Copyright 2024 Justin

#include <Arduino.h>
#include <esp_sleep.h>
#include "config.h"
#include "generated_config.h"

// Battery status structure
struct BatteryStatus {
  float voltage = NAN;
  int percent = -1;
  int estimatedDays = -1;
};

// Adaptive sleep configuration
struct SleepConfig {
    uint32_t normal_interval_sec;      // Default: 300 (5 min)
    uint32_t low_battery_interval_sec; // Default: 600 (10 min) for <20% battery
    uint32_t critical_interval_sec;    // Default: 1800 (30 min) for <5% battery
    uint32_t rapid_update_interval_sec; // Default: 60 (1 min) when data changing
    uint8_t low_battery_threshold;     // Default: 20%
    uint8_t critical_battery_threshold; // Default: 5%
};

// Core power functions
BatteryStatus read_battery_status();
int estimate_battery_percent(float voltage);
int estimate_battery_days(int percent, float mah_capacity = 3000, float ma_average = 50);

// Adaptive sleep scheduling
SleepConfig get_default_sleep_config();
uint32_t calculate_optimal_sleep_interval(const SleepConfig& config);
bool is_temperature_changing_rapidly();

// Custom sleep interval (set via MQTT command)
void set_custom_sleep_interval(uint32_t sec);
uint32_t get_custom_sleep_interval();

// Device mode (dev vs production)
void set_device_mode(const char* mode);
bool is_dev_mode();
uint32_t get_dev_mode_remaining_sec();
const char* get_device_mode_str();

// Power management
void power_init();
void power_prepare_sleep();
void power_wake_from_sleep();

// Fuel gauge specific functions
#if USE_MAX17048
void fuelgauge_wake_if_asleep();
void fuelgauge_quickstart_if_cold_boot(esp_reset_reason_t reason);
void fuelgauge_sleep_between_wakes();
#endif

#if USE_LC709203F
void lc_wake_if_asleep();
void lc_quickstart_if_cold_boot(esp_reset_reason_t reason);
void lc_sleep_between_wakes();
#endif