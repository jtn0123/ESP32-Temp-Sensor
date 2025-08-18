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
#define USE_SHT40 0
#define USE_BME280 1
#define USE_MQTT 1
#define USE_ESPHOME_API 0
#ifndef USE_MAX17048
#define USE_MAX17048 0
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

// Phase budgets (ms). Keep each phase bounded so a stall can't eat the whole
// wake.
#ifndef SENSOR_PHASE_TIMEOUT_MS
#define SENSOR_PHASE_TIMEOUT_MS 300
#endif
#ifndef FETCH_RETAINED_TIMEOUT_MS
#define FETCH_RETAINED_TIMEOUT_MS 800
#endif
#ifndef DISPLAY_PHASE_TIMEOUT_MS
#define DISPLAY_PHASE_TIMEOUT_MS 2000
#endif
#ifndef PUBLISH_PHASE_TIMEOUT_MS
#define PUBLISH_PHASE_TIMEOUT_MS 800
#endif
