#pragma once

// Home Assistant MQTT discovery module - extracted from net.h
// Handles automatic discovery of sensors in Home Assistant

#include <Arduino.h>

// Home Assistant discovery functions
void ha_discovery_begin(const char* client_id);
void ha_discovery_publish_all();
void ha_discovery_publish_temperature_sensor();
void ha_discovery_publish_humidity_sensor();
void ha_discovery_publish_pressure_sensor();
void ha_discovery_publish_battery_sensor();
void ha_discovery_publish_rssi_sensor();
void ha_discovery_publish_diagnostic_sensors();

// Set whether to include diagnostic entities
void ha_discovery_set_diagnostic_mode(bool enable);