#pragma once
// Copyright 2024 Justin

#include "config.h"

#include <Arduino.h>
#include <Wire.h>

#if USE_BME280
#include <Adafruit_BME280.h>
static Adafruit_BME280 g_bme280;
static bool g_bme280_initialized = false;
inline void sensors_begin() {
  if (g_bme280_initialized)
    return;
  Wire.begin();
#ifdef I2C_TIMEOUT_MS
  Wire.setTimeOut(I2C_TIMEOUT_MS);
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
