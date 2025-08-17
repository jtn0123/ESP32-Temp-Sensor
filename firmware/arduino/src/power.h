#pragma once

#include <Arduino.h>
#include <esp_sleep.h>
#include "generated_config.h"
#include "config.h"
#if USE_MAX17048
#include <Wire.h>
#include <Adafruit_MAX1704X.h>
#endif

struct BatteryStatus {
    float voltage = NAN;
    int percent = -1;
    int estimatedDays = -1;
};

inline BatteryStatus read_battery_status() {
    BatteryStatus b;
#if USE_MAX17048
    static Adafruit_MAX17048 maxfg;
    static bool fg_init = false;
    if (!fg_init) {
        Wire.begin();
        #ifdef I2C_TIMEOUT_MS
        Wire.setTimeOut(I2C_TIMEOUT_MS);
        #endif
        fg_init = maxfg.begin();
    }
    if (fg_init) {
        b.voltage = maxfg.cellVoltage();
        b.percent = (int)(maxfg.cellPercent() + 0.5f);
    }
#endif
    if (!isfinite(b.voltage) && VBAT_ADC_PIN >= 0) {
        // Configure ADC once per wake (simple mode)
        analogReadResolution(12);
        uint16_t raw = analogRead(VBAT_ADC_PIN);
        float v = (raw / (float)ADC_MAX_COUNTS) * ADC_REF_V * VBAT_DIVIDER;
        b.voltage = v;
    }
    // Rough SOC estimate from voltage (linear placeholder 3.3V→0%, 4.2V→100%)
    if (b.percent < 0 && isfinite(b.voltage)) {
        float pct = (b.voltage - 3.3f) / (4.2f - 3.3f);
        if (pct < 0) pct = 0; if (pct > 1) pct = 1;
        b.percent = (int)(pct * 100.0f + 0.5f);
    }
    // Days estimate from duty cycle
    // Average current ~ (active_current * active_fraction + sleep_current * sleep_fraction)
    float active_fraction = (float)ACTIVE_SECONDS / (float)WAKE_INTERVAL_SEC;
    if (active_fraction < 0) active_fraction = 0; if (active_fraction > 1) active_fraction = 1;
    float avg_mA = ACTIVE_CURRENT_MA * active_fraction + SLEEP_CURRENT_MA * (1.0f - active_fraction);
    if (avg_mA > 0) {
        float hours = BATTERY_CAPACITY_MAH / avg_mA;
        b.estimatedDays = (int)(hours / 24.0f + 0.5f);
    } else {
        b.estimatedDays = -1;
    }
    return b;
}

inline void go_deep_sleep_seconds(uint32_t seconds) {
    esp_sleep_enable_timer_wakeup((uint64_t)seconds * 1000000ULL);
    esp_deep_sleep_start();
}


