#pragma once

// WiFi management module - extracted from net.h
// Handles WiFi connection, provisioning, and status

#include <Arduino.h>
#include <WiFi.h>
#include <esp_wifi.h>
#include <Preferences.h>

#if USE_WIFI_PROVISIONING
#include <esp_err.h>
#include <esp_event.h>
#include <esp_netif.h>
#include <wifi_provisioning/manager.h>
#if WIFI_PROV_USE_SOFTAP
#include <wifi_provisioning/scheme_softap.h>
#endif
#if WIFI_PROV_USE_BLE
#include <wifi_provisioning/scheme_ble.h>
#endif
#endif

// WiFi connection parameters
#ifndef WIFI_CONNECT_TIMEOUT_MS
#define WIFI_CONNECT_TIMEOUT_MS 6000
#endif

#ifndef WIFI_RSSI_THRESHOLD
#define WIFI_RSSI_THRESHOLD -75
#endif

#ifndef WIFI_AUTHMODE_THRESHOLD
#define WIFI_AUTHMODE_THRESHOLD WIFI_AUTH_WPA_PSK
#endif

// WiFi connection state management
enum WiFiConnectionState {
  WIFI_STATE_IDLE,
  WIFI_STATE_CONNECTING,
  WIFI_STATE_CONNECTED,
  WIFI_STATE_FAILED,
  WIFI_STATE_DISCONNECTED
};

// WiFi management functions
bool wifi_connect_with_timeout(uint32_t timeout_ms);
bool wifi_connect_with_exponential_backoff(uint32_t max_attempts = 5, uint32_t initial_delay_ms = 1000);
bool wifi_is_connected();
String wifi_get_ip();
void wifi_get_ip_cstr(char* out, size_t out_size);
int wifi_get_rssi();
bool wifi_clear_provisioning();
void wifi_begin_provisioning();
bool wifi_is_provisioning_active();
WiFiConnectionState wifi_get_state();
const char* wifi_state_to_string(WiFiConnectionState state);

// BSSID utilities
bool parse_bssid(const char* str, uint8_t out[6]);
bool is_all_zero_bssid(const uint8_t b[6]);

// WiFi configuration
void wifi_set_hostname(const char* hostname);
void wifi_configure_power_save(bool enable);