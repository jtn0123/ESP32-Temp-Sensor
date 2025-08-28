#pragma once
// Copyright 2024 Justin

// Compile-time toggles (filled in later as features land)
#ifndef USE_DISPLAY
#define USE_DISPLAY 1
#endif
#ifndef DEV_NO_SLEEP
#define DEV_NO_SLEEP 0
#endif
#ifndef DEV_CYCLE_MODE
#define DEV_CYCLE_MODE 0
#endif
#ifndef DEV_ACTIVE_SEC
#define DEV_ACTIVE_SEC 180
#endif
#ifndef DEV_SLEEP_SEC
#define DEV_SLEEP_SEC 180
#endif
#ifndef USE_SHT40
#define USE_SHT40 0
#endif
#ifndef USE_BME280
#define USE_BME280 1
#endif
#define USE_MQTT 1
#define USE_ESPHOME_API 0
// Support either fuel gauge; runtime probe decides which one is present
#ifndef USE_MAX17048
#define USE_MAX17048 1
#endif
#ifndef USE_LC709203F
#define USE_LC709203F 1
#endif

// Wi-Fi provisioning (ESP-IDF wifi_prov_mgr) compile-time switch
#ifndef USE_WIFI_PROVISIONING
#define USE_WIFI_PROVISIONING 0
#endif
// Select provisioning transport. ESP32-S2 has no BLE, so SoftAP by default.
#ifndef WIFI_PROV_USE_BLE
#define WIFI_PROV_USE_BLE 0
#endif
#ifndef WIFI_PROV_USE_SOFTAP
#define WIFI_PROV_USE_SOFTAP 1
#endif
// Security level: 1 enables proof-of-possession. 0 disables POP (simpler).
#ifndef WIFI_PROV_SECURITY
#define WIFI_PROV_SECURITY 0
#endif
// Timeout for provisioning session before giving up (seconds)
#ifndef WIFI_PROV_TIMEOUT_SEC
#define WIFI_PROV_TIMEOUT_SEC 180
#endif

#ifndef I2C_TIMEOUT_MS
#define I2C_TIMEOUT_MS 150
#endif
// Default I2C bus speed
#ifndef I2C_CLOCK_HZ
#define I2C_CLOCK_HZ 100000
#endif
// Optional: scan I2C bus and print detected addresses at startup
#ifndef I2C_DEBUG_SCAN
#define I2C_DEBUG_SCAN 0
#endif

// Phase budgets (ms). Keep each phase bounded so a stall can't eat the whole
// wake.
#ifndef SENSOR_PHASE_TIMEOUT_MS
#define SENSOR_PHASE_TIMEOUT_MS 300
#endif
#ifndef FETCH_RETAINED_TIMEOUT_MS
#define FETCH_RETAINED_TIMEOUT_MS 2000
#endif
#ifndef DISPLAY_PHASE_TIMEOUT_MS
#define DISPLAY_PHASE_TIMEOUT_MS 8000
#endif
#ifndef PUBLISH_PHASE_TIMEOUT_MS
#define PUBLISH_PHASE_TIMEOUT_MS 800
#endif
// Debounce window to coalesce multiple MQTT outside updates before a draw
#ifndef MQTT_OUTSIDE_DEBOUNCE_MS
#define MQTT_OUTSIDE_DEBOUNCE_MS 1200
#endif

// Logging system configuration
#ifndef LOG_ENABLED
#define LOG_ENABLED 1
#endif

#ifndef LOG_LEVEL_DEFAULT
#define LOG_LEVEL_DEFAULT 2  // 0=TRACE, 1=DEBUG, 2=INFO, 3=WARN, 4=ERROR, 5=FATAL
#endif

#ifndef LOG_SERIAL_ENABLED
#define LOG_SERIAL_ENABLED 1
#endif

#ifndef LOG_BUFFER_ENABLED
#define LOG_BUFFER_ENABLED 1
#endif

#ifndef LOG_NVS_ENABLED
#define LOG_NVS_ENABLED 1
#endif

#ifndef LOG_MQTT_ENABLED
#define LOG_MQTT_ENABLED 1
#endif

#ifndef LOG_MQTT_RATE_LIMIT_MS
#define LOG_MQTT_RATE_LIMIT_MS 1000
#endif

// Status pixel configuration 
#ifndef USE_STATUS_PIXEL
#define USE_STATUS_PIXEL 0
#endif
