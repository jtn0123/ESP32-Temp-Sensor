#pragma once

// Copyright 2024 Justin

// C system headers
#include <esp_sleep.h>

// Other headers
#include <Arduino.h>

// Project headers
#include "config.h"
#include "generated_config.h"

#if USE_MAX17048
#include <Adafruit_MAX1704X.h>
#include <Wire.h>
#endif
#if USE_LC709203F
#include <Adafruit_LC709203F.h>
#include <Wire.h>
#endif

struct BatteryStatus {
  float voltage = NAN;
  int percent = -1;
  int estimatedDays = -1;
};

#if USE_MAX17048
static Adafruit_MAX17048 g_maxfg;
static bool g_maxfg_initialized = false;

inline void fuelgauge_wake_if_asleep() {
  if (!g_maxfg_initialized)
    return;
  g_maxfg.sleep(false);
}

inline void fuelgauge_quickstart_if_cold_boot(esp_reset_reason_t reason) {
  if (!g_maxfg_initialized)
    return;
  if (reason == ESP_RST_POWERON) {
    g_maxfg.quickStart();
  }
}

inline void fuelgauge_sleep_between_wakes() {
  if (!g_maxfg_initialized)
    return;
  g_maxfg.sleep(true);
}
#endif

#if USE_LC709203F
static Adafruit_LC709203F g_lcfg;
static bool g_lcfg_initialized = false;

inline void lc_wake_if_asleep() { /* LC709203F has no sleep API */ }

inline void lc_quickstart_if_cold_boot(esp_reset_reason_t reason) {
  (void)reason;
  // LC709203F does not expose quickstart; ensure it is configured
}

inline void lc_sleep_between_wakes() { /* no-op */ }
#endif

inline BatteryStatus read_battery_status() {
  BatteryStatus b;
#if USE_MAX17048
  static bool s_maxfg_attempted = false;
  if (!g_maxfg_initialized && !s_maxfg_attempted) {
// Ensure I2C is initialized on the configured pins and clock before
// talking to MAX17048
// Some ESP32-S2 Feather variants gate I2C power; turn it on if available
#ifdef PIN_I2C_POWER
    pinMode(PIN_I2C_POWER, OUTPUT);
    digitalWrite(PIN_I2C_POWER, HIGH);
#endif
#ifdef I2C_POWER
    pinMode(I2C_POWER, OUTPUT);
    digitalWrite(I2C_POWER, HIGH);
#endif
#ifdef TFT_I2C_POWER
    pinMode(TFT_I2C_POWER, OUTPUT);
    digitalWrite(TFT_I2C_POWER, HIGH);
#endif
#if defined(SDA) && defined(SCL)
    Wire.begin(SDA, SCL);
#else
    Wire.begin();
#endif
#ifdef I2C_TIMEOUT_MS
    Wire.setTimeOut(I2C_TIMEOUT_MS);
#endif
#ifdef I2C_CLOCK_HZ
    Wire.setClock(I2C_CLOCK_HZ);
#endif
    s_maxfg_attempted = true;
    g_maxfg_initialized = g_maxfg.begin(&Wire);
    if (g_maxfg_initialized) {
      fuelgauge_wake_if_asleep();
      g_maxfg.quickStart();
      fuelgauge_quickstart_if_cold_boot(esp_reset_reason());
    }
  }
  if (g_maxfg_initialized) {
    b.voltage = g_maxfg.cellVoltage();
    b.percent = static_cast<int>(g_maxfg.cellPercent() + 0.5f);
  }
#endif
#if USE_LC709203F
  static bool s_lcfg_attempted = false;
  if (!g_lcfg_initialized && !s_lcfg_attempted && !g_maxfg_initialized) {
#ifdef PIN_I2C_POWER
    pinMode(PIN_I2C_POWER, OUTPUT);
    digitalWrite(PIN_I2C_POWER, HIGH);
#endif
#ifdef I2C_POWER
    pinMode(I2C_POWER, OUTPUT);
    digitalWrite(I2C_POWER, HIGH);
#endif
#ifdef TFT_I2C_POWER
    pinMode(TFT_I2C_POWER, OUTPUT);
    digitalWrite(TFT_I2C_POWER, HIGH);
#endif
#if defined(SDA) && defined(SCL)
    Wire.begin(SDA, SCL);
#else
    Wire.begin();
#endif
#ifdef I2C_TIMEOUT_MS
    Wire.setTimeOut(I2C_TIMEOUT_MS);
#endif
#ifdef I2C_CLOCK_HZ
    Wire.setClock(I2C_CLOCK_HZ);
#endif
    s_lcfg_attempted = true;
    g_lcfg_initialized = g_lcfg.begin();
    if (g_lcfg_initialized) {
// Choose closest supported pack size near BATTERY_CAPACITY_MAH (3300 mAh)
#if defined(LC709203F_APA_3300MAH)
      g_lcfg.setPackSize(LC709203F_APA_3300MAH);
#elif defined(LC709203F_APA_3200MAH)
      g_lcfg.setPackSize(LC709203F_APA_3200MAH);
#elif defined(LC709203F_APA_3000MAH)
      g_lcfg.setPackSize(LC709203F_APA_3000MAH);
#else
      g_lcfg.setPackSize(LC709203F_APA_1000MAH);
#endif
      g_lcfg.setThermistorB(3950);
      lc_wake_if_asleep();
      lc_quickstart_if_cold_boot(esp_reset_reason());
    }
  }
  if (g_lcfg_initialized && !g_maxfg_initialized) {
    b.voltage = g_lcfg.cellVoltage();
    // LC709203F returns percentage as float
    b.percent = static_cast<int>(g_lcfg.cellPercent() + 0.5f);
  }
#endif
  if (!isfinite(b.voltage) && VBAT_ADC_PIN >= 0) {
    // Reduce IR drop influence: short idle, median-of-3 samples
    analogReadResolution(12);
#if defined(ARDUINO_ARCH_ESP32)
    // Extend input range so VBAT/div fits without saturating ADC
    analogSetPinAttenuation(VBAT_ADC_PIN, ADC_11db);
    adcAttachPin(VBAT_ADC_PIN);
#endif
    delay(200);
    uint16_t r0 = analogRead(VBAT_ADC_PIN);
    delay(10);
    uint16_t r1 = analogRead(VBAT_ADC_PIN);
    delay(10);
    uint16_t r2 = analogRead(VBAT_ADC_PIN);
    uint16_t a = r0, m = r1, c = r2;
    if (a > m) {
      uint16_t t = a;
      a = m;
      m = t;
    }
    if (m > c) {
      uint16_t t = m;
      m = c;
      c = t;
    }
    if (a > m) {
      uint16_t t = a;
      a = m;
      m = t;
    }
    float v = (m / static_cast<float>(ADC_MAX_COUNTS)) * ADC_REF_V *
               VBAT_DIVIDER;
    b.voltage = v;
  }
  // Rough SOC estimate from voltage (linear placeholder 3.3V→0%, 4.2V→100%)
  if (b.percent < 0 && isfinite(b.voltage)) {
    float pct = (b.voltage - 3.3f) / (4.2f - 3.3f);
    if (pct < 0)
      pct = 0;
    if (pct > 1)
      pct = 1;
    b.percent = static_cast<int>(pct * 100.0f + 0.5f);
  }
  // Days estimate based on current remaining charge (if percent known).
  // Prefer fuel-gauge time-to-empty when available; else use percent-based
  // average-current model.
  // Average current ~ (active_current * active_fraction +
  //                     sleep_current * sleep_fraction)
  float active_fraction =
      static_cast<float>(ACTIVE_SECONDS) /
      static_cast<float>(WAKE_INTERVAL_SEC);
  if (active_fraction < 0)
    active_fraction = 0;
  if (active_fraction > 1)
    active_fraction = 1;
  float avg_mA = ACTIVE_CURRENT_MA * active_fraction +
                  SLEEP_CURRENT_MA * (1.0f - active_fraction);

  // Attempt fuel-gauge TTE via MAX17048 charge rate (percent per hour).
  // When discharging, chargeRate() is negative. TTE_hours ≈ percent /
  // (-crate_pct_per_hr).
  bool used_tte = false;
#if USE_MAX17048
  if (g_maxfg_initialized) {
    float crate_pct_per_hr = g_maxfg.chargeRate();
    if (isfinite(crate_pct_per_hr) && crate_pct_per_hr < -0.01f &&
        b.percent >= 0 && b.percent <= 100) {
      float hours = static_cast<float>(b.percent) / (-crate_pct_per_hr);
      if (isfinite(hours) && hours > 0) {
        b.estimatedDays = static_cast<int>(hours / 24.0f + 0.5f);
        used_tte = true;
      }
    }
  }
#endif

  if (!used_tte) {
    if (avg_mA > 0) {
      // Percent-based remaining capacity
      float remaining_mAh = BATTERY_CAPACITY_MAH;
      if (b.percent >= 0 && b.percent <= 100) {
        remaining_mAh = BATTERY_CAPACITY_MAH *
                         (static_cast<float>(b.percent) / 100.0f);
      }
      float hours = remaining_mAh / avg_mA;
      b.estimatedDays = static_cast<int>(hours / 24.0f + 0.5f);
    } else {
      b.estimatedDays = -1;
    }
  }
  return b;
}

inline void go_deep_sleep_seconds(uint32_t seconds) {
#if USE_MAX17048
  if (g_maxfg_initialized) {
    fuelgauge_sleep_between_wakes();
  }
#endif
#if USE_LC709203F
  if (g_lcfg_initialized) {
    lc_sleep_between_wakes();
  }
#endif
  // Be defensive: clear any previous wake sources before configuring new one
  // Some cores retain wake bits across resets; this ensures a clean slate.
  esp_sleep_disable_wakeup_source(ESP_SLEEP_WAKEUP_ALL);
  // Timer wakeup for requested interval
  esp_sleep_enable_timer_wakeup(static_cast<uint64_t>(seconds) * 1000000ULL);
  // Give serial a brief chance to flush and MQTT/WiFi to quiesce completely
  Serial.flush();
  delay(10);
  // Enter deep sleep
  esp_deep_sleep_start();
}
