#pragma once
// Copyright 2024 Justin

#include "config.h"

#include <Arduino.h>
#include <Wire.h>

#if USE_BME280
#include <Adafruit_BME280.h>

#if I2C_DEBUG_SCAN
// Attempt to recover a stuck I2C bus by pulsing SCL when SDA is held low
static void i2c_bus_recover_if_stuck() {
#if defined(SDA) && defined(SCL)
  pinMode(SDA, INPUT_PULLUP);
  pinMode(SCL, INPUT_PULLUP);
  if (digitalRead(SDA) == LOW) {
    Serial.println("I2C: SDA low, attempting bus recovery...");
    for (int i = 0; i < 9 && digitalRead(SDA) == LOW; i++) {
      pinMode(SCL, OUTPUT);
      digitalWrite(SCL, LOW);
      delayMicroseconds(5);
      pinMode(SCL, INPUT_PULLUP);
      delayMicroseconds(5);
    }
    if (digitalRead(SDA) == LOW) {
      Serial.println("I2C: recovery failed (SDA still low)");
    } else {
      Serial.println("I2C: bus recovered");
    }
  }
#endif
}
#endif

static Adafruit_BME280 g_bme280;
static bool g_bme280_initialized = false;
inline void sensors_begin() {
  if (g_bme280_initialized)
    return;
// Explicitly initialize I2C on known pins when available
#if defined(SDA) && defined(SCL)
  Serial.printf("I2C: using pins SDA=%d SCL=%d\n", SDA, SCL);
#if I2C_DEBUG_SCAN
  i2c_bus_recover_if_stuck();
#endif
  Wire.begin(SDA, SCL);
#else
  Wire.begin();
#endif
#ifdef I2C_TIMEOUT_MS
  Wire.setTimeOut(I2C_TIMEOUT_MS > 0 ? I2C_TIMEOUT_MS : 50);
#endif
  Wire.setClock(I2C_CLOCK_HZ);
#if I2C_DEBUG_SCAN
  Serial.println("I2C: scanning...");
  const uint8_t candidates[] = {0x76, 0x77};
  for (uint8_t i = 0; i < sizeof(candidates); i++) {
    uint8_t addr = candidates[i];
    Wire.beginTransmission(addr);
    uint8_t err = Wire.endTransmission();
    if (err == 0) {
      Serial.printf("I2C: found 0x%02X\n", addr);
    } else {
      Serial.printf("I2C: no device at 0x%02X (err=%u)\n", addr, err);
    }
  }
#endif
  // Try default I2C address 0x77 then 0x76
  if (!g_bme280.begin(0x77) && !g_bme280.begin(0x76)) {
    Serial.println("BME280 not found");
    g_bme280_initialized = false;
    return;
  }
  g_bme280.setSampling(Adafruit_BME280::MODE_FORCED,
                       Adafruit_BME280::SAMPLING_X1, // temp
                       Adafruit_BME280::SAMPLING_X1, // pressure
                       Adafruit_BME280::SAMPLING_X1, // humidity
                       Adafruit_BME280::FILTER_OFF);
  g_bme280_initialized = true;
}
#else
inline void sensors_begin() { /* noop until SHT4x added */ }
#endif

struct InsideReadings {
  float temperatureC = NAN;
  float humidityPct = NAN;
  float pressureHPa = NAN;
};

inline InsideReadings read_inside_sensors() {
  InsideReadings r;
#if USE_BME280
  sensors_begin();
  if (!g_bme280_initialized)
    return r;
  // Forced mode: trigger one measurement for low power
  g_bme280.takeForcedMeasurement();
  r.temperatureC = g_bme280.readTemperature();
  r.humidityPct = g_bme280.readHumidity();
  // Adafruit_BME280::readPressure returns Pascals; convert to hPa for MQTT/HA
  r.pressureHPa = g_bme280.readPressure() / 100.0f;
#endif
  return r;
}
