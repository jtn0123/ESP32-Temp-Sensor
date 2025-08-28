#pragma once
// Sensor management module
// Copyright 2024 Justin

#include "config.h"
#include <Arduino.h>

// Sensor reading structure
struct InsideReadings {
  float temperatureC = NAN;
  float humidityPct = NAN;
  float pressureHPa = NAN;
};

// Core sensor functions
void sensors_begin();
InsideReadings read_inside_sensors();

// Extended sensor management
void sensors_init_all();
InsideReadings read_sensors_with_timeout(uint32_t timeout_ms = SENSOR_PHASE_TIMEOUT_MS);