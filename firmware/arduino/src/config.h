#pragma once

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
// Select provisioning transport. BLE by default for field units; SoftAP optional.
#ifndef WIFI_PROV_USE_BLE
#define WIFI_PROV_USE_BLE 1
#endif
#ifndef WIFI_PROV_USE_SOFTAP
#define WIFI_PROV_USE_SOFTAP 0
#endif
// Security level: 1 enables proof-of-possession (recommended). 0 disables POP.
#ifndef WIFI_PROV_SECURITY
#define WIFI_PROV_SECURITY 1
#endif
// Timeout for provisioning session before giving up (seconds)
#ifndef WIFI_PROV_TIMEOUT_SEC
#define WIFI_PROV_TIMEOUT_SEC 180
#endif


