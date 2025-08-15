#pragma once

#include <Arduino.h>
#include <esp_sleep.h>

struct BatteryStatus {
    float voltage = NAN;
    int percent = -1;
    int estimatedDays = -1;
};

inline BatteryStatus read_battery_status() {
    BatteryStatus b;
    // If Feather exposes VBAT via ADC, read here (placeholder values)
    // Real implementation would configure ADC pin and calibration.
    b.voltage = 4.00f;
    b.percent = 76;
    b.estimatedDays = 128;
    return b;
}

inline void go_deep_sleep_seconds(uint32_t seconds) {
    esp_sleep_enable_timer_wakeup((uint64_t)seconds * 1000000ULL);
    esp_deep_sleep_start();
}


