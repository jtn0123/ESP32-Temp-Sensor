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

// Core power functions
BatteryStatus read_battery_status();
int estimate_battery_percent(float voltage);
int estimate_battery_days(int percent, float mah_capacity = 3000, float ma_average = 50);

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