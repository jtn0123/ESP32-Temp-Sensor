// Power management implementation
// Copyright 2024 Justin

#include "power.h"
#include <Wire.h>

#if USE_MAX17048
#include <Adafruit_MAX1704X.h>
static Adafruit_MAX17048 g_maxfg;
static bool g_maxfg_initialized = false;
#endif

#if USE_LC709203F
#include <Adafruit_LC709203F.h>
static Adafruit_LC709203F g_lcfg;
static bool g_lcfg_initialized = false;
#endif

// Power rail control pins (if defined)
static void enable_i2c_power() {
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
}

static void ensure_i2c_initialized() {
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
}

#if USE_MAX17048
void fuelgauge_wake_if_asleep() {
  if (!g_maxfg_initialized)
    return;
  g_maxfg.sleep(false);
}

void fuelgauge_quickstart_if_cold_boot(esp_reset_reason_t reason) {
  if (!g_maxfg_initialized)
    return;
  if (reason == ESP_RST_POWERON) {
    g_maxfg.quickStart();
  }
}

void fuelgauge_sleep_between_wakes() {
  if (!g_maxfg_initialized)
    return;
  g_maxfg.sleep(true);
}
#endif

#if USE_LC709203F
void lc_wake_if_asleep() { 
  /* LC709203F has no sleep API */ 
}

void lc_quickstart_if_cold_boot(esp_reset_reason_t reason) {
  (void)reason;
  // LC709203F does not expose quickstart; ensure it is configured
}

void lc_sleep_between_wakes() { 
  /* no-op */ 
}
#endif

BatteryStatus read_battery_status() {
  BatteryStatus b;
  
#if USE_MAX17048
  static bool s_maxfg_attempted = false;
  if (!g_maxfg_initialized && !s_maxfg_attempted) {
    enable_i2c_power();
    ensure_i2c_initialized();
    s_maxfg_attempted = true;
    
    if (g_maxfg.begin()) {
      g_maxfg_initialized = true;
      Serial.println("MAX17048 fuel gauge found");
      g_maxfg.setAlertVoltages(2.0, 4.2);
      uint8_t vers = g_maxfg.getChipID();
      Serial.printf("MAX17048 version: 0x%02X\n", vers);
    } else {
      Serial.println("MAX17048 not found");
    }
  }
  
  if (g_maxfg_initialized) {
    b.voltage = g_maxfg.cellVoltage();
    float pct = g_maxfg.cellPercent();
    b.percent = constrain(static_cast<int>(pct), 0, 100);
    
    // Simple day estimate: 3000mAh / 50mA average = 60 hours = 2.5 days
    if (b.percent >= 0) {
      b.estimatedDays = (b.percent * 2.5) / 100;
    }
  }
#endif

#if USE_LC709203F
  static bool s_lcfg_attempted = false;
  if (!g_lcfg_initialized && !s_lcfg_attempted) {
    enable_i2c_power();
    ensure_i2c_initialized();
    s_lcfg_attempted = true;
    
    if (g_lcfg.begin()) {
      g_lcfg_initialized = true;
      Serial.println("LC709203F fuel gauge found");
      g_lcfg.setPowerMode(LC709203F_POWER_OPERATE);
      g_lcfg.setPackSize(LC709203F_APA_3000MAH);
      g_lcfg.setAlarmVoltage(3.4);
    } else {
      Serial.println("LC709203F not found");
    }
  }
  
  if (g_lcfg_initialized && !g_maxfg_initialized) {
    b.voltage = g_lcfg.cellVoltage();
    float pct = g_lcfg.cellPercent();
    b.percent = constrain(static_cast<int>(pct), 0, 100);
    
    if (b.percent >= 0) {
      b.estimatedDays = (b.percent * 2.5) / 100;
    }
  }
#endif

  return b;
}

// Battery percentage from voltage
int estimate_battery_percent(float voltage) {
  if (!isfinite(voltage) || voltage < 3.0)
    return 0;
  if (voltage >= 4.2)
    return 100;
    
  // Simplified LiPo discharge curve
  const float v_min = 3.2;
  const float v_max = 4.2;
  float normalized = (voltage - v_min) / (v_max - v_min);
  return constrain(static_cast<int>(normalized * 100), 0, 100);
}

// Days remaining estimate
int estimate_battery_days(int percent, float mah_capacity, float ma_average) {
  if (percent < 0 || mah_capacity <= 0 || ma_average <= 0)
    return -1;
    
  float hours = (mah_capacity * percent / 100.0) / ma_average;
  return static_cast<int>(hours / 24.0);
}

// Initialize power management
void power_init() {
  Serial.println("Initializing power management...");
  
  // Enable power rails
  enable_i2c_power();
  
  // Initialize fuel gauge
  BatteryStatus initial = read_battery_status();
  if (initial.percent >= 0) {
    Serial.printf("Battery: %.2fV, %d%%, ~%d days\n", 
                  initial.voltage, initial.percent, initial.estimatedDays);
  } else {
    Serial.println("No battery gauge found");
  }
  
  // Configure wakeup sources if needed
  // Wake interval will be configured when going to sleep
}

// Prepare for deep sleep
void power_prepare_sleep() {
#if USE_MAX17048
  fuelgauge_sleep_between_wakes();
#endif
#if USE_LC709203F
  lc_sleep_between_wakes();
#endif
}

// Wake from deep sleep
void power_wake_from_sleep() {
#if USE_MAX17048
  fuelgauge_wake_if_asleep();
  fuelgauge_quickstart_if_cold_boot(esp_reset_reason());
#endif
#if USE_LC709203F
  lc_wake_if_asleep();
  lc_quickstart_if_cold_boot(esp_reset_reason());
#endif
}