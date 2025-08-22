#pragma once

// Copyright 2024 Justin
// C system / ESP-IDF C headers
#include <esp_wifi.h>
#include <time.h>

// C++ system headers
#include <cstdio>

// C++/Arduino and third-party headers
#include <Arduino.h>
#include <Preferences.h>
#include <PubSubClient.h>
#include <WiFi.h>

// Project headers
#include "config.h"
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
#include "power.h"
#include "sensors.h"
// Layout identity (version, CRC, md5)
#include "display_layout.h"

// All configuration should come from generated_config.h

// Forward declarations for functions referenced before their definitions
inline void net_publish_ha_discovery();
inline void net_publish_inside(float tempC, float rhPct);
inline void net_publish_pressure(float pressureHPa);
inline void net_publish_battery(float voltage, int percent);
inline void net_publish_wifi_rssi(int rssiDbm);
inline void net_publish_publish_latency_ms(uint32_t publishLatencyMs);

struct OutsideReadings {
  float temperatureC = NAN;
  float humidityPct = NAN;
  char weather[64];
  // OpenWeatherMap single primary item support
  int weatherId = 0;              // OWM weather[0].id
  char weatherDesc[64];           // OWM weather[0].description
  char weatherIcon[8];            // OWM weather[0].icon (e.g., "10n")
  float windMps = NAN;
  float highTempC = NAN;
  float lowTempC = NAN;
  bool validTemp = false;
  bool validHum = false;
  bool validWeather = false;
  bool validWeatherId = false;
  bool validWeatherDesc = false;
  bool validWeatherIcon = false;
  bool validWind = false;
  bool validHigh = false;
  bool validLow = false;
};

static WiFiClient g_wifi_client;
static PubSubClient g_mqtt(g_wifi_client);
static OutsideReadings g_outside;
// Flag set when any outside MQTT field changes; consumed by UI to trigger full refresh
static volatile bool g_outside_dirty = false;
inline bool net_consume_outside_dirty() {
  bool was = g_outside_dirty;
  g_outside_dirty = false;
  return was;
}
// Optional time (HH:MM) from MQTT; fallback to SNTP/RTC
static char g_time_hhmm[8] = {0};
static bool g_have_time_from_mqtt = false;
static char g_client_id[40];
static Preferences g_net_prefs;
static Preferences g_offline_prefs;

#ifndef WIFI_CONNECT_TIMEOUT_MS
#define WIFI_CONNECT_TIMEOUT_MS 6000
#endif
#ifndef MQTT_CONNECT_TIMEOUT_MS
#define MQTT_CONNECT_TIMEOUT_MS 4000
#endif

inline bool parse_bssid(const char* str, uint8_t out[6]) {
  if (!str)
    return false;
  int vals[6];
  int n =
      sscanf(str, "%x:%x:%x:%x:%x:%x", &vals[0], &vals[1], &vals[2], &vals[3], &vals[4], &vals[5]);
  if (n != 6)
    return false;
  for (int i = 0; i < 6; ++i)
    out[i] = static_cast<uint8_t>(vals[i]);
  return true;
}

inline bool is_all_zero_bssid(const uint8_t b[6]) {
  for (int i = 0; i < 6; ++i)
    if (b[i] != 0)
      return false;
  return true;
}

// Optional tuning knobs (can be overridden via build_flags)
#ifndef WIFI_RSSI_THRESHOLD
#define WIFI_RSSI_THRESHOLD -75
#endif
#ifndef WIFI_AUTHMODE_THRESHOLD
#define WIFI_AUTHMODE_THRESHOLD WIFI_AUTH_WPA2_PSK
#endif

// Number of consecutive failed connects with a pinned BSSID before clearing
//     it
#ifndef WIFI_BSSID_FAIL_CLEAR_N
#define WIFI_BSSID_FAIL_CLEAR_N 3
#endif

// NVS helpers: remember last successful AP (SSID + BSSID)
inline bool nvs_load_last_ap(String& ssid, uint8_t bssid[6]) {
  bool ok = false;
  if (g_net_prefs.begin("net", true)) {
    ssid = g_net_prefs.getString("last_ssid", "");
    size_t n = g_net_prefs.getBytes("last_bssid", bssid, 6);
    g_net_prefs.end();
    if (ssid.length() > 0 && n == 6 && !is_all_zero_bssid(bssid))
      ok = true;
  } else {
    ssid = String();
    memset(bssid, 0, 6);
  }
  return ok;
}

inline void nvs_store_last_ap(const char* ssid, const uint8_t bssid[6]) {
  if (!ssid || !bssid)
    return;
  if (g_net_prefs.begin("net", false)) {
    g_net_prefs.putString("last_ssid", ssid);
    g_net_prefs.putBytes("last_bssid", bssid, 6);
    g_net_prefs.end();
  }
}

// Track consecutive failures when attempting BSSID-pinned joins so we can
// clear the saved BSSID after repeated misses (AP moved/changed).
inline uint32_t nvs_get_bssid_fail_count() {
  uint32_t c = 0;
  if (g_net_prefs.begin("net", true)) {
    c = g_net_prefs.getUInt("bssid_fail", 0);
    g_net_prefs.end();
  }
  return c;
}

inline void nvs_set_bssid_fail_count(uint32_t v) {
  if (g_net_prefs.begin("net", false)) {
    g_net_prefs.putUInt("bssid_fail", v);
    g_net_prefs.end();
  }
}

inline void nvs_clear_last_ap() {
  if (g_net_prefs.begin("net", false)) {
    g_net_prefs.remove("last_bssid");
    g_net_prefs.remove("last_ssid");
    g_net_prefs.end();
  }
}

inline bool ends_with(const char* s, const char* suffix) {
  size_t ls = strlen(s);
  size_t lf = strlen(suffix);
  if (lf > ls)
    return false;
  return strcmp(s + (ls - lf), suffix) == 0;
}

// -------------------- Time sync (SNTP) --------------------
#ifndef TIME_FRESH_EPOCH_MIN
#define TIME_FRESH_EPOCH_MIN 1609459200UL // 2021-01-01,
//     anything earlier considered stale
#endif
#ifndef TIME_RESYNC_INTERVAL_SEC
#define TIME_RESYNC_INTERVAL_SEC (24UL * 60UL * 60UL) // once per day
#endif

inline bool time_is_stale() {
  time_t now = time(nullptr);
  uint32_t last_sync = 0;
  if (g_net_prefs.begin("net", true)) {
    last_sync = g_net_prefs.getUInt("last_ntp", 0);
    g_net_prefs.end();
  }
  if (static_cast<uint32_t>(now) < TIME_FRESH_EPOCH_MIN)
    return true;
  if (last_sync == 0)
    return true;
  return (static_cast<uint32_t>(now) - last_sync) > TIME_RESYNC_INTERVAL_SEC;
}

inline void ensure_time_synced_if_stale() {
  if (!WiFi.isConnected())
    return;
  if (!time_is_stale())
    return;
  // Use IDF/Arduino SNTP helper via configTime; keep timeout short
  configTime(0, 0, "pool.ntp.org", "time.nist.gov", "time.google.com");
  // Poll briefly until time looks sane
  uint32_t start = millis();
  while (static_cast<uint32_t>(time(nullptr)) < TIME_FRESH_EPOCH_MIN && millis() - start < 2000UL) {
    delay(50);
  }
  uint32_t now_epoch = static_cast<uint32_t>(time(nullptr));
  if (now_epoch >= TIME_FRESH_EPOCH_MIN) {
    if (g_net_prefs.begin("net", false)) {
      g_net_prefs.putUInt("last_ntp", now_epoch);
      g_net_prefs.end();
    }
    Serial.println("Time: SNTP sync ok");
  } else {
    Serial.println("Time: SNTP sync timeout (continuing)");
  }
}

// -------------------- Offline buffer (NVS ring) --------------------
#ifndef OFFLINE_CAPACITY
#define OFFLINE_CAPACITY 96U // number of samples to retain when offline
#endif
#ifndef OFFLINE_DRAIN_MAX_PER_WAKE
#define OFFLINE_DRAIN_MAX_PER_WAKE 64U
#endif
// Additional budgets to prevent long awake time on large backlogs
#ifndef OFFLINE_DRAIN_MAX_MS
#define OFFLINE_DRAIN_MAX_MS 2500UL
#endif
#ifndef OFFLINE_DRAIN_MAX_BYTES
#define OFFLINE_DRAIN_MAX_BYTES 8192UL
#endif

struct OfflineSample {
  uint32_t epoch;
  float tempC;
  float rhPct;
};

inline void offline_get_bounds(uint32_t& head, uint32_t& tail) {
  head = g_offline_prefs.getUInt("head", 0);
  tail = g_offline_prefs.getUInt("tail", 0);
}

inline void offline_set_bounds(uint32_t head, uint32_t tail) {
  g_offline_prefs.putUInt("head", head);
  g_offline_prefs.putUInt("tail", tail);
}

inline void offline_key_for(uint32_t seq, char out[], size_t out_size) {
  snprintf(out, out_size, "s%u", seq);
}

inline void offline_enqueue_sample(float tempC, float rhPct) {
  uint32_t ts = static_cast<uint32_t>(time(nullptr));
  OfflineSample s{ts, tempC, rhPct};
  if (!g_offline_prefs.begin("obuf", false))
    return;
  uint32_t head = 0, tail = 0;
  offline_get_bounds(head, tail);
  // Drop oldest if at capacity
  if (head - tail >= OFFLINE_CAPACITY) {
    char delk[16];
    offline_key_for(tail, delk, sizeof(delk));
    g_offline_prefs.remove(delk);
    tail++;
  }
  char key[16];
  offline_key_for(head, key, sizeof(key));
  g_offline_prefs.putBytes(key, &s, sizeof(s));
  offline_set_bounds(head + 1, tail);
  g_offline_prefs.end();
  Serial.printf("Offline: queued seq=%u ts=%u (C=%.2f RH=%.0f)\n", static_cast<unsigned>(head),
                static_cast<unsigned>(ts),
                //     s.tempC,
                s.rhPct);
}

inline uint32_t net_publish_inside_history(uint32_t epoch, float tempC, float rhPct) {
  if (!g_mqtt.connected())
    return 0;
  char topic[128];
  snprintf(topic, sizeof(topic), "%s/inside/history", MQTT_PUB_BASE);
  // Build compact JSON with F and RH integer; keep payload small
  char tbuf[16];
  char rhbuf[8];
  dtostrf(tempC * 9.0f / 5.0f + 32.0f, 0, 1, tbuf);
  dtostrf(rhPct, 0, 0, rhbuf);
  char payload[96];
  int plen = snprintf(payload, sizeof(payload), "{\"ts\":%u,\"tempF\":%s,\"rh\":%s}",
                      static_cast<unsigned>(epoch), tbuf, rhbuf);
  g_mqtt.publish(topic, payload, false);
  // Approximate bytes published as topic + payload length
  uint32_t tlen = static_cast<uint32_t>(strlen(topic));
  uint32_t blen = static_cast<uint32_t>(plen > 0 ? plen : static_cast<int>(strlen(payload)));
  return tlen + blen;
}

inline void offline_drain_if_any() {
  if (!g_mqtt.connected())
    return;
  if (!g_offline_prefs.begin("obuf", false))
    return;
  uint32_t head = 0, tail = 0;
  offline_get_bounds(head, tail);
  uint32_t to_send = head - tail;
  if (to_send == 0) {
    g_offline_prefs.end();
    return;
  }
  if (to_send > OFFLINE_DRAIN_MAX_PER_WAKE)
    to_send = OFFLINE_DRAIN_MAX_PER_WAKE;
  Serial.printf("Offline: draining %u samples (tail=%u head=%u)\n", static_cast<unsigned>(to_send),
                static_cast<unsigned>(tail), static_cast<unsigned>(head));
  uint32_t drain_start_ms = millis();
  uint32_t bytes_sent = 0;
  uint32_t orig_tail = tail;
  uint32_t processed = 0;
  while (processed < to_send && g_mqtt.connected()) {
    // Time budget check before reading/publishing next sample
    if (OFFLINE_DRAIN_MAX_MS > 0 && (millis() - drain_start_ms) >= OFFLINE_DRAIN_MAX_MS) {

      Serial.printf("Offline: drain stop (time budget) elapsed_ms=%u sent=%u bytes=%u\n",
                    static_cast<unsigned>(millis() - drain_start_ms),
                    static_cast<unsigned>(tail - orig_tail), static_cast<unsigned>(bytes_sent));
      break;
    }
    uint32_t seq = tail;
    char key[16];
    offline_key_for(seq, key, sizeof(key));
    OfflineSample s{};
    size_t n = g_offline_prefs.getBytes(key, &s, sizeof(s));
    if (n == sizeof(s)) {
      bytes_sent += net_publish_inside_history(s.epoch, s.tempC, s.rhPct);
      // Immediately delete upon publish; advance tail
      g_offline_prefs.remove(key);
      tail = seq + 1;
      processed++;
      // Give MQTT time to pump
      for (int k = 0; k < 3; ++k) {
        if (g_mqtt.connected())
          g_mqtt.loop();
        delay(5);
      }
      // Post-publish budget checks
      if ((OFFLINE_DRAIN_MAX_BYTES > 0 && bytes_sent >= OFFLINE_DRAIN_MAX_BYTES) ||
          (OFFLINE_DRAIN_MAX_MS > 0 && (millis() - drain_start_ms) >= OFFLINE_DRAIN_MAX_MS)) {

        Serial.printf("Offline: drain stop (%s budget) elapsed_ms=%u sent=%u bytes=%u\n",
                      (bytes_sent >= OFFLINE_DRAIN_MAX_BYTES ? "byte" : "time"),
                      static_cast<unsigned>(millis() - drain_start_ms),
                      static_cast<unsigned>(tail - orig_tail), static_cast<unsigned>(bytes_sent));
        break;
      }
    } else {
      // Missing or corrupt entry; skip it
      tail = seq + 1;
      processed++;
    }
  }
  offline_set_bounds(head, tail);
  g_offline_prefs.end();
}

inline void mqtt_callback(char* topic, uint8_t* payload, unsigned int length) {
  char val[128];
  unsigned int n = length < (sizeof(val) - 1) ? length : (unsigned int)(sizeof(val) - 1);
  for (unsigned int i = 0; i < n; ++i)
    val[i] = static_cast<char>(payload[i]);
  val[n] = '\0';
  // Home Assistant birth: when HA announces online, republish discovery and
  // current states
  if (strcmp(topic, "homeassistant/status") == 0) {
    if (n == 6 && memcmp(payload, "online", 6) == 0) {
      net_publish_ha_discovery();
      // Publish current states (inside temp/RH and battery)
      InsideReadings ir = read_inside_sensors();
      if (isfinite(ir.temperatureC) && isfinite(ir.humidityPct)) {
        net_publish_inside(ir.temperatureC, ir.humidityPct);
      }
      if (isfinite(ir.pressureHPa)) {
        net_publish_pressure(ir.pressureHPa);
      }
      BatteryStatus bs = read_battery_status();
      if (isfinite(bs.voltage) && bs.percent >= 0) {
        net_publish_battery(bs.voltage, bs.percent);
      }
    }
    return;
  }
  if (ends_with(topic, "/temp")) {
    g_outside.temperatureC = atof(val);
    g_outside.validTemp = true;
    g_outside_dirty = true;
  } else if (ends_with(topic, "/hum") || ends_with(topic, "/rh")) {
    g_outside.humidityPct = atof(val);
    g_outside.validHum = true;
    g_outside_dirty = true;
  } else if (ends_with(topic, "/temp_f")) {
    // Fahrenheit alias: convert to Celsius for internal representation
    float f = atof(val);
    float c = (f - 32.0f) * (5.0f / 9.0f);
    g_outside.temperatureC = c;
    g_outside.validTemp = isfinite(c);
    g_outside_dirty = true;
  } else if (ends_with(topic, "/weather")) {
    strncpy(g_outside.weather, val, sizeof(g_outside.weather) - 1);
    g_outside.weather[sizeof(g_outside.weather) - 1] = '\0';
    g_outside.validWeather = g_outside.weather[0] != '\0';
    g_outside_dirty = true;
  } else if (ends_with(topic, "/condition")) {
    // Alias for textual condition
    strncpy(g_outside.weather, val, sizeof(g_outside.weather) - 1);
    g_outside.weather[sizeof(g_outside.weather) - 1] = '\0';
    g_outside.validWeather = g_outside.weather[0] != '\0';
    g_outside_dirty = true;
  } else if (ends_with(topic, "/weather_id")) {
    g_outside.weatherId = atoi(val);
    g_outside.validWeatherId = (g_outside.weatherId != 0) || (strcmp(val, "0") == 0);
    g_outside_dirty = true;
  } else if (ends_with(topic, "/condition_code")) {
    // Alias for numeric condition code
    g_outside.weatherId = atoi(val);
    g_outside.validWeatherId = (g_outside.weatherId != 0) || (strcmp(val, "0") == 0);
    g_outside_dirty = true;
  } else if (ends_with(topic, "/weather_desc")) {
    strncpy(g_outside.weatherDesc, val, sizeof(g_outside.weatherDesc) - 1);
    g_outside.weatherDesc[sizeof(g_outside.weatherDesc) - 1] = '\0';
    g_outside.validWeatherDesc = g_outside.weatherDesc[0] != '\0';
    g_outside_dirty = true;
  } else if (ends_with(topic, "/weather_icon")) {
    strncpy(g_outside.weatherIcon, val, sizeof(g_outside.weatherIcon) - 1);
    g_outside.weatherIcon[sizeof(g_outside.weatherIcon) - 1] = '\0';
    g_outside.validWeatherIcon = g_outside.weatherIcon[0] != '\0';
    g_outside_dirty = true;
  } else if (ends_with(topic, "/wind") || ends_with(topic, "/wind_mps") ||
             ends_with(topic, "/wind_mph")) {
    float w = atof(val);
    if (ends_with(topic, "/wind_mph"))
      w = w / 2.237f;
    g_outside.windMps = w;
    g_outside.validWind = isfinite(w);
    g_outside_dirty = true;
  } else if (ends_with(topic, "/hi") || ends_with(topic, "/high")) {
    g_outside.highTempC = atof(val);
    g_outside.validHigh = isfinite(g_outside.highTempC);
    g_outside_dirty = true;
  } else if (ends_with(topic, "/lo") || ends_with(topic, "/low")) {
    g_outside.lowTempC = atof(val);
    g_outside.validLow = isfinite(g_outside.lowTempC);
    g_outside_dirty = true;
  } else if (ends_with(topic, "/time") || ends_with(topic, "/clock")) {
    // Accept sanitized HH:MM text for header time
    char buf[8] = {0};
    size_t j = 0;
    for (unsigned int i = 0; i < n && j < sizeof(buf) - 1; ++i) {
      char c = val[i];
      if ((c >= '0' && c <= '9') || c == ':') buf[j++] = c;
    }
    buf[j] = '\0';
    if (strlen(buf) == 5 && buf[2] == ':' && isdigit(buf[0]) && isdigit(buf[1]) && isdigit(buf[3]) && isdigit(buf[4])) {
      strncpy(g_time_hhmm, buf, sizeof(g_time_hhmm));
      g_time_hhmm[sizeof(g_time_hhmm) - 1] = '\0';
      g_have_time_from_mqtt = true;
    }
  }
}

// Provisioning helper implementations (enabled via USE_WIFI_PROVISIONING)
#if USE_WIFI_PROVISIONING
static void ensure_system_netif_and_loop_inited() {
  static bool done = false;
  if (done)
    return;
  esp_err_t e;
  e = esp_netif_init();
  if (e != ESP_OK && e != ESP_ERR_INVALID_STATE) {
    Serial.printf("esp_netif_init err=%d\n", static_cast<int>(e));
  }
  e = esp_event_loop_create_default();
  if (e != ESP_OK && e != ESP_ERR_INVALID_STATE) {
    Serial.printf("esp_event_loop_create_default err=%d\n", static_cast<int>(e));
  }
  done = true;
}

static bool start_wifi_station_connect_from_nvs(uint32_t timeout_ms) {
  WiFi.mode(WIFI_STA);
  WiFi.persistent(false);
  WiFi.setAutoReconnect(true);
// Constrain scan channels by country when provided (faster, legal)
#ifdef WIFI_COUNTRY
  // Use IDF API directly for broad core compatibility across ESP32 variants
  esp_wifi_set_country_code(WIFI_COUNTRY, true);
#endif
  // Unlock channel and apply thresholds and optional preferred BSSID
  //     remembered
  // in our own NVS
  wifi_config_t cfg;
  memset(&cfg, 0, sizeof(cfg));
  esp_wifi_get_config(WIFI_IF_STA, &cfg);
  cfg.sta.scan_method = WIFI_FAST_SCAN;
  cfg.sta.threshold.rssi = WIFI_RSSI_THRESHOLD;
  cfg.sta.threshold.authmode = WIFI_AUTHMODE_THRESHOLD;
  cfg.sta.channel = 0;
  // Prefer last successful BSSID if it matches the provisioned SSID
  String last_ssid;
  uint8_t prefer_bssid[6] = {0};
  bool have_bssid = false;
  if (nvs_load_last_ap(last_ssid, prefer_bssid)) {
    if (last_ssid.length() > 0 &&
        strncmp((const char*)cfg.sta.ssid, last_ssid.c_str(), sizeof(cfg.sta.ssid)) == 0) {
      memcpy(cfg.sta.bssid, prefer_bssid, 6);
      cfg.sta.bssid_set = 1;
      have_bssid = true;

      Serial.printf("WiFi: preferring BSSID %02x:%02x:%02x:%02x:%02x:%02x (prov)\n",
                    prefer_bssid[0], prefer_bssid[1], prefer_bssid[2], prefer_bssid[3],
                    prefer_bssid[4], prefer_bssid[5]);
    } else {
      memset(cfg.sta.bssid, 0, 6);
      cfg.sta.bssid_set = 0;
    }
  }
  esp_wifi_set_config(WIFI_IF_STA, &cfg);
  esp_wifi_start();
  esp_wifi_connect();
  uint32_t start = millis();
  while (!WiFi.isConnected() && (millis() - start) < timeout_ms) {
    delay(100);
  }
  if (WiFi.isConnected()) {
    Serial.printf("WiFi: connected, IP %s RSSI %d dBm\n", WiFi.localIP().toString().c_str(),
                  WiFi.RSSI());
    // Reset failure counter on success
    nvs_set_bssid_fail_count(0);
    // Cache last SSID + BSSID for next wake if available
    uint8_t now_bssid[6] = {0};
    const uint8_t* bp = WiFi.BSSID();
    if (bp)
      memcpy(now_bssid, bp, 6);
    if (!is_all_zero_bssid(now_bssid)) {
      String ssid = WiFi.SSID();
      nvs_store_last_ap(ssid.c_str(), now_bssid);
    }
    return true;
  }
  Serial.printf("WiFi: connect timeout (status=%d)\n", static_cast<int>(WiFi.status()));
  // Increment consecutive failure count and clear saved BSSID after N misses
  if (have_bssid) {
    uint32_t c = nvs_get_bssid_fail_count();
    c++;
    nvs_set_bssid_fail_count(c);
    if (c >= WIFI_BSSID_FAIL_CLEAR_N) {
      Serial.println("WiFi: clearing saved BSSID after repeated failures (prov)");
      nvs_clear_last_ap();
      nvs_set_bssid_fail_count(0);
    }
  }
  return false;
}

static void ensure_wifi_connected_provisioned_impl() {
  if (WiFi.isConnected())
    return;
  ensure_system_netif_and_loop_inited();

  wifi_prov_mgr_config_t prov_cfg = {};
#if WIFI_PROV_USE_SOFTAP
  prov_cfg.scheme = wifi_prov_scheme_softap;
  prov_cfg.scheme_event_handler = WIFI_PROV_EVENT_HANDLER_NONE;
#elif WIFI_PROV_USE_BLE
  prov_cfg.scheme = wifi_prov_scheme_ble;
  prov_cfg.scheme_event_handler = WIFI_PROV_EVENT_HANDLER_NONE;
#else
#error "Enable at least one provisioning scheme"
#endif
  if (wifi_prov_mgr_init(prov_cfg) != ESP_OK) {
    Serial.println("WiFiProv: mgr init failed");
    return;
  }

  bool is_prov = false;
  if (wifi_prov_mgr_is_provisioned(&is_prov) != ESP_OK) {
    Serial.println("WiFiProv: query failed");
    wifi_prov_mgr_deinit();
    return;
  }

  if (!is_prov) {
    // Generate friendly service name: PROV_XXXXXX (lower 24 bits of MAC)
    char service_name[16];
    uint64_t mac = ESP.getEfuseMac();
    snprintf(service_name, sizeof(service_name), "PROV_%06X", (unsigned int)(mac & 0xFFFFFF));
    const char* service_key = NULL; // open softAP by default
#if WIFI_PROV_SECURITY == 1
    wifi_prov_security_t sec = WIFI_PROV_SECURITY_1;
    const char* pop = "esp32-pop"; // customize via build flag if desired
#else
    wifi_prov_security_t sec = WIFI_PROV_SECURITY_0;
    const char* pop = NULL;
#endif
    Serial.printf("WiFiProv: starting provisioning (%s), service '%s'\n",
#if WIFI_PROV_USE_SOFTAP
//                   "softAP",
#else
//                   "BLE",
#endif
                  service_name);
    if (wifi_prov_mgr_start_provisioning(sec, pop, service_name, service_key) != ESP_OK) {
      Serial.println("WiFiProv: start failed");
    } else {
      // Wait until provisioned or timeout
      uint32_t t0 = millis();
      while (millis() - t0 < static_cast<uint32_t>(WIFI_PROV_TIMEOUT_SEC) * 1000U) {
        bool prov = false;
        if (wifi_prov_mgr_is_provisioned(&prov) == ESP_OK && prov)
          break;
        delay(200);
      }
      // Stop provisioning service
      wifi_prov_mgr_stop_provisioning();
    }
  }

  // Deinit manager to free resources
  wifi_prov_mgr_deinit();
  // Attempt connection using creds in NVS
  start_wifi_station_connect_from_nvs(WIFI_CONNECT_TIMEOUT_MS);
}
#endif // USE_WIFI_PROVISIONING

inline bool net_wifi_clear_provisioning() {
#if USE_WIFI_PROVISIONING
  ensure_system_netif_and_loop_inited();
  wifi_prov_mgr_config_t prov_cfg = {};
#if WIFI_PROV_USE_SOFTAP
  prov_cfg.scheme = wifi_prov_scheme_softap;
  prov_cfg.scheme_event_handler = WIFI_PROV_EVENT_HANDLER_NONE;
#elif WIFI_PROV_USE_BLE
  prov_cfg.scheme = wifi_prov_scheme_ble;
  prov_cfg.scheme_event_handler = WIFI_PROV_EVENT_HANDLER_NONE;
#endif
  if (wifi_prov_mgr_init(prov_cfg) != ESP_OK)
    return false;
  esp_err_t err = wifi_prov_mgr_reset_provisioning();
  wifi_prov_mgr_deinit();
  return err == ESP_OK;
#else
  return false;
#endif
}

inline void ensure_wifi_connected() {
#if USE_WIFI_PROVISIONING
  ensure_wifi_connected_provisioned_impl();
  return;
#endif
  if (WiFi.isConnected())
    return;
  if (strlen(WIFI_SSID) == 0)
    return;
  Serial.printf("WiFi: connecting to %s...\n", WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.persistent(false);
  WiFi.setAutoReconnect(true);

// Constrain scan channels by country when provided (faster, legal)
#ifdef WIFI_COUNTRY
  // Use IDF API directly for broad core compatibility across ESP32 variants
  esp_wifi_set_country_code(WIFI_COUNTRY, true);
#endif
// Optional static IP configuration
#ifdef WIFI_STATIC_IP
  {
    IPAddress ip, gw, sn;
    IPAddress d1(0, 0, 0, 0), d2(0, 0, 0, 0);
    bool ok = ip.fromString(WIFI_STATIC_IP) && gw.fromString(WIFI_STATIC_GATEWAY) &&
              sn.fromString(WIFI_STATIC_SUBNET);
#ifdef WIFI_STATIC_DNS1
    d1.fromString(WIFI_STATIC_DNS1);
#endif
#ifdef WIFI_STATIC_DNS2
    d2.fromString(WIFI_STATIC_DNS2);
#endif
    if (ok) {
      WiFi.config(ip, gw, sn, d1, d2);
    }
  }
#endif
  // Prefer last known BSSID for fast, reliable joins; don't lock channel
  bool have_bssid = false;
  uint8_t prefer_bssid[6] = {0};
  String last_ssid;
  if (nvs_load_last_ap(last_ssid, prefer_bssid) && last_ssid == WIFI_SSID) {
    have_bssid = true;
  } else {
// Fall back to compile-time BSSID if provided
#ifdef WIFI_BSSID
    if (parse_bssid(WIFI_BSSID, prefer_bssid)) {
      have_bssid = true;
    }
#endif
  }

  // Preconfigure station with connect=false so we can tweak IDF fields before
  // connecting
  if (have_bssid) {
    WiFi.begin(WIFI_SSID, WIFI_PASS, 0 /*channel*/, prefer_bssid, false /*connect*/);
    Serial.printf("WiFi: preferring BSSID %02x:%02x:%02x:%02x:%02x:%02x\n", prefer_bssid[0],
                  prefer_bssid[1], prefer_bssid[2], prefer_bssid[3], prefer_bssid[4],
                  prefer_bssid[5]);
  } else {
    WiFi.begin(WIFI_SSID, WIFI_PASS, 0 /*channel*/, nullptr, false /*connect*/);
  }

  // Apply FAST scan + thresholds, and ensure channel is unlocked
  wifi_config_t cfg;
  memset(&cfg, 0, sizeof(cfg));
  esp_wifi_get_config(WIFI_IF_STA, &cfg);
  cfg.sta.scan_method = WIFI_FAST_SCAN;
  cfg.sta.threshold.rssi = WIFI_RSSI_THRESHOLD;
  cfg.sta.threshold.authmode = WIFI_AUTHMODE_THRESHOLD;
  cfg.sta.channel = 0; // do not hard-lock channel
  if (have_bssid) {
    memcpy(cfg.sta.bssid, prefer_bssid, 6);
    cfg.sta.bssid_set = 1;
  } else {
    memset(cfg.sta.bssid, 0, 6);
    cfg.sta.bssid_set = 0;
  }
  esp_wifi_set_config(WIFI_IF_STA, &cfg);

  // Start Wi-Fi and attempt to connect
  esp_wifi_start();
  esp_wifi_connect();

  uint32_t start = millis();
  // Give BSSID-pinned attempt a shorter window before falling back
  uint32_t bssid_try_ms =
      have_bssid ? (WIFI_CONNECT_TIMEOUT_MS > 4000 ? 3000U : WIFI_CONNECT_TIMEOUT_MS / 2) : 0U;
  bool fallback_done = false;
  while (!WiFi.isConnected() && millis() - start < WIFI_CONNECT_TIMEOUT_MS) {
    if (have_bssid && !fallback_done && (millis() - start) >= bssid_try_ms) {
      // Fallback: clear BSSID to allow roaming / broad match
      Serial.println("WiFi: BSSID join slow; falling back to SSID-only");
      esp_wifi_disconnect();
      wifi_config_t cfg2;
      memset(&cfg2, 0, sizeof(cfg2));
      esp_wifi_get_config(WIFI_IF_STA, &cfg2);
      memset(cfg2.sta.bssid, 0, 6);
      cfg2.sta.bssid_set = 0;
      cfg2.sta.scan_method = WIFI_FAST_SCAN;
      cfg2.sta.threshold.rssi = WIFI_RSSI_THRESHOLD;
      cfg2.sta.threshold.authmode = WIFI_AUTHMODE_THRESHOLD;
      cfg2.sta.channel = 0;
      esp_wifi_set_config(WIFI_IF_STA, &cfg2);
      esp_wifi_connect();
      fallback_done = true;
    }
    delay(100);
  }
  if (WiFi.isConnected()) {
    Serial.printf("WiFi: connected, IP %s RSSI %d dBm\n", WiFi.localIP().toString().c_str(),
                  WiFi.RSSI());
    // Reset failure counter on success
    nvs_set_bssid_fail_count(0);
    // Cache last SSID + BSSID for next wake
    uint8_t now_bssid[6] = {0};
    const uint8_t* bp = WiFi.BSSID();
    if (bp)
      memcpy(now_bssid, bp, 6);
    if (!is_all_zero_bssid(now_bssid)) {
      nvs_store_last_ap(WIFI_SSID, now_bssid);
    }
  } else {
    Serial.printf("WiFi: connect timeout (status=%d)\n", static_cast<int>(WiFi.status()));
    // Increment consecutive failure count and clear saved BSSID after N
    //     misses
    if (have_bssid) {
      uint32_t c = nvs_get_bssid_fail_count();
      c++;
      nvs_set_bssid_fail_count(c);
      if (c >= WIFI_BSSID_FAIL_CLEAR_N) {
        Serial.println("WiFi: clearing saved BSSID after repeated failures");
        nvs_clear_last_ap();
        nvs_set_bssid_fail_count(0);
      }
    }
  }
}

inline void ensure_mqtt_connected() {
  if (g_mqtt.connected())
    return;
  if (strlen(MQTT_HOST) == 0)
    return;
  g_mqtt.setServer(MQTT_HOST, MQTT_PORT);
  // Broker stability: larger keepalive and buffers; shorter socket timeout
  g_mqtt.setKeepAlive(60);
  g_mqtt.setSocketTimeout(5);
#ifdef MQTT_MAX_PACKET_SIZE
  g_mqtt.setBufferSize(MQTT_MAX_PACKET_SIZE);
#else
  g_mqtt.setBufferSize(1024);
#endif
  g_mqtt.setCallback(mqtt_callback);
  Serial.printf("MQTT: connecting to %s:%u...\n", MQTT_HOST, static_cast<unsigned>(MQTT_PORT));
  uint64_t mac = ESP.getEfuseMac();
  // Use lower 24 bits
  snprintf(g_client_id, sizeof(g_client_id), "esp32-room-%06x", (unsigned int)(mac & 0xFFFFFF));
  uint32_t start = millis();
  const char* user = nullptr;
  const char* pass = nullptr;
#ifdef MQTT_USER
  if (strlen(MQTT_USER) > 0)
    user = MQTT_USER;
#endif
#ifdef MQTT_PASS
  if (strlen(MQTT_PASS) > 0)
    pass = MQTT_PASS;
#endif
  // Set LWT to availability topic so HA can mark device offline if we drop
  // unexpectedly
  char availTopic[128];
  snprintf(availTopic, sizeof(availTopic), "%s/availability", MQTT_PUB_BASE);
  while (!g_mqtt.connect(g_client_id, user, pass, availTopic, 0, true, "offline") &&
         millis() - start < MQTT_CONNECT_TIMEOUT_MS) {
    delay(200);
  }
  if (g_mqtt.connected()) {
    Serial.println("MQTT: connected");
    // Publish availability online on successful connect
    g_mqtt.publish(availTopic, "online", true);
    char topic[128];
    const char* base = MQTT_SUB_BASE;
    auto sub = [&](const char* suffix) {
      snprintf(topic, sizeof(topic), "%s%s", base, suffix);
      g_mqtt.subscribe(topic);
      Serial.printf("MQTT: subscribed %s\n", topic);
    };
    sub("/temp");
    // Accept Fahrenheit alias for temperature
    sub("/temp_f");
    sub("/hum");
    sub("/rh");
    // Textual condition (alias for weather description)
    sub("/weather");
    sub("/condition");
    sub("/weather_id");
    // Numeric condition code alias
    sub("/condition_code");
    sub("/weather_desc");
    sub("/weather_icon");
    sub("/wind");
    sub("/wind_mps");
    sub("/wind_mph");
    sub("/high");
    sub("/hi");
    sub("/low");
    sub("/lo");
    // Subscribe to Home Assistant birth topic for rediscovery on HA restarts
    g_mqtt.subscribe("homeassistant/status");
    Serial.printf("MQTT: subscribed %s\n", "homeassistant/status");
    // On successful MQTT connection, try to drain any offline backlog
    offline_drain_if_any();
  } else {
    Serial.printf("MQTT: connect timeout/fail (state=%d)\n", g_mqtt.state());
  }
}

inline void net_begin() {
  ensure_wifi_connected();
  // Refresh time occasionally; quick and only when stale
  ensure_time_synced_if_stale();
  ensure_mqtt_connected();
}

inline void net_time_hhmm(char* out, size_t out_size) {
  if (!out || out_size == 0) return;
  if (g_have_time_from_mqtt && g_time_hhmm[0] != '\0') {
    strncpy(out, g_time_hhmm, out_size);
    out[out_size - 1] = '\0';
    return;
  }
  time_t now = time(nullptr);
  struct tm tm_now;
  localtime_r(&now, &tm_now);
  snprintf(out, out_size, "%02d:%02d", tm_now.tm_hour, tm_now.tm_min);
}

inline void net_loop() {
  static bool last_wifi = false;
  static bool last_mqtt = false;
  if (!WiFi.isConnected())
    ensure_wifi_connected();
  if (WiFi.isConnected() && !g_mqtt.connected())
    ensure_mqtt_connected();
  bool now_wifi = WiFi.isConnected();
  bool now_mqtt = g_mqtt.connected();
  if (now_wifi != last_wifi) {
    Serial.printf("WiFi: %s\n", now_wifi ? "up" : "down");
    last_wifi = now_wifi;
  }
  if (now_mqtt != last_mqtt) {
    Serial.printf("MQTT: %s\n", now_mqtt ? "up" : "down");
    last_mqtt = now_mqtt;
  }
  if (now_mqtt)
    g_mqtt.loop();
}

inline String net_ip() {
  if (!WiFi.isConnected())
    return String("0.0.0.0");
  return WiFi.localIP().toString();
}

inline void net_ip_cstr(char* out, size_t out_size) {
  if (!out || out_size == 0)
    return;
  if (!WiFi.isConnected()) {
    snprintf(out, out_size, "%s", "0.0.0.0");
    return;
  }
  IPAddress ip = WiFi.localIP();
  snprintf(out, out_size, "%u.%u.%u.%u", static_cast<unsigned>(ip[0]), static_cast<unsigned>(ip[1]),
           static_cast<unsigned>(ip[2]), static_cast<unsigned>(ip[3]));
}

inline void mqtt_pump(uint32_t duration_ms) {
  uint32_t start = millis();
  while (millis() - start < duration_ms) {
    if (g_mqtt.connected())
      g_mqtt.loop();
    delay(10);
  }
}

inline OutsideReadings net_get_outside() { return g_outside; }

inline void net_publish_inside(float tempC, float rhPct) {
  if (!g_mqtt.connected()) {
    // Buffer a compact record for later publish with timestamp
    offline_enqueue_sample(tempC, rhPct);
    return;
  }
  char topic[128];
  char payload[32];
  const char* base = MQTT_PUB_BASE;
  snprintf(topic, sizeof(topic), "%s/inside/temp", base);
  // Publish Fahrenheit for HA (discovery advertises °F)
  float tempF = tempC * 9.0f / 5.0f + 32.0f;
  dtostrf(tempF, 0, 1, payload);
  g_mqtt.publish(topic, payload, true);
  snprintf(topic, sizeof(topic), "%s/inside/hum", base);
  dtostrf(rhPct, 0, 0, payload);
  g_mqtt.publish(topic, payload, true);
}

// Publish barometric pressure in hPa
inline void net_publish_pressure(float pressureHPa) {
  if (!g_mqtt.connected())
    return;
  char topic[128];
  char payload[32];
  const char* base = MQTT_PUB_BASE;
  snprintf(topic, sizeof(topic), "%s/inside/pressure", base);
  dtostrf(pressureHPa, 0, 1, payload);
  g_mqtt.publish(topic, payload, true);
}

inline void net_publish_battery(float voltage, int percent) {
  if (!g_mqtt.connected())
    return;
  char topic[128];
  char payload[32];
  const char* base = MQTT_PUB_BASE;
  // voltage
  snprintf(topic, sizeof(topic), "%s/battery/voltage", base);
  dtostrf(voltage, 0, 2, payload);
  g_mqtt.publish(topic, payload, true);
  // percent
  snprintf(topic, sizeof(topic), "%s/battery/percent", base);
  snprintf(payload, sizeof(payload), "%d", percent);
  g_mqtt.publish(topic, payload, true);
}

// Publish WiFi RSSI in dBm (diagnostic)
inline void net_publish_wifi_rssi(int rssiDbm) {
  if (!g_mqtt.connected())
    return;
  char topic[128];
  char payload[16];
  const char* base = MQTT_PUB_BASE;
  snprintf(topic, sizeof(topic), "%s/wifi/rssi", base);
  snprintf(payload, sizeof(payload), "%d", rssiDbm);
  g_mqtt.publish(topic, payload, true);
}

// Publish publish-latency metric in milliseconds (diagnostic)
inline void net_publish_publish_latency_ms(uint32_t publishLatencyMs) {
  if (!g_mqtt.connected())
    return;
  char topic[128];
  char payload[16];
  const char* base = MQTT_PUB_BASE;
  snprintf(topic, sizeof(topic), "%s/debug/publish_ms", base);
  snprintf(payload, sizeof(payload), "%u", static_cast<unsigned>(publishLatencyMs));
  g_mqtt.publish(topic, payload, true);
}

inline void net_publish_status(const char* payload, bool retain = true) {
  if (!g_mqtt.connected() || !payload)
    return;
  char topic[128];
  snprintf(topic, sizeof(topic), "%s/status", MQTT_PUB_BASE);
  g_mqtt.publish(topic, payload, retain);
}

// Publish a JSON debug payload with wake metrics to sensors/<node>/debug
inline void net_publish_debug_json(const char* payload, bool retain = false) {
  if (!g_mqtt.connected() || !payload)
    return;
  char topic[128];
  snprintf(topic, sizeof(topic), "%s/debug", MQTT_PUB_BASE);
  g_mqtt.publish(topic, payload, retain);
}

// Publish a UI debug snapshot (outside readings + values used in UI), retained
inline void net_publish_debug_ui(const char* payload, bool retain = true) {
  if (!g_mqtt.connected() || !payload)
    return;
  char topic[128];
  snprintf(topic, sizeof(topic), "%s/debug_ui", MQTT_PUB_BASE);
  g_mqtt.publish(topic, payload, retain);
}

// Publish layout identity for sim↔device parity checks
inline void net_publish_layout_identity() {
  if (!g_mqtt.connected())
    return;
  char topic[128];
  snprintf(topic, sizeof(topic), "%s/layout", MQTT_PUB_BASE);
  char payload[96];
  snprintf(payload, sizeof(payload), "{\"layout_version\":%u,\"layout_crc\":\"0x%08X\"}",
           static_cast<unsigned>(LAYOUT_VERSION), static_cast<unsigned>(LAYOUT_CRC));
  g_mqtt.publish(topic, payload, true);
}

inline void net_publish_last_crash(const char* reason_or_null) {
  if (!g_mqtt.connected())
    return;
  char topic[128];
  snprintf(topic, sizeof(topic), "%s/last_crash", MQTT_PUB_BASE);
  if (reason_or_null && reason_or_null[0]) {
    g_mqtt.publish(topic, reason_or_null, true);
  } else {
    // Clear retained key by publishing empty payload per MQTT convention
    g_mqtt.publish(topic, "", true);
  }
}

// Publish a small probe message to measure publish latency without affecting
// retained state
inline void net_publish_debug_probe(const char* payload, bool retain = false) {
  if (!g_mqtt.connected() || !payload)
    return;
  char topic[128];
  snprintf(topic, sizeof(topic), "%s/debug_probe", MQTT_PUB_BASE);
  g_mqtt.publish(topic, payload, retain);
}

// Publish Home Assistant MQTT Discovery configs for inside temperature and
// humidity
inline void net_publish_ha_discovery() {
  if (!g_mqtt.connected())
    return;
  // Topics and availability
  char availTopic[128];
  snprintf(availTopic, sizeof(availTopic), "%s/availability", MQTT_PUB_BASE);
  // Expire entities slightly after our scheduled wake so HA greys stale
  //     values
  // if we miss a cycle
  uint32_t expireAfterSec = static_cast<uint32_t>(WAKE_INTERVAL_SEC) + 120U;

  // Helper to publish one discovery config
  auto pub_disc = [&](const char* key, const char* name, const char* unit, const char* dev_class,
                      const char* state_suffix) {
    char discTopic[192];
    snprintf(discTopic, sizeof(discTopic), "homeassistant/sensor/%s_%s/config",

             g_client_id, key);
    char stateTopic[192];
    snprintf(stateTopic, sizeof(stateTopic), "%s/%s", MQTT_PUB_BASE, state_suffix);
    char payload[640];
    // Choose a suggested display precision based on unit to stabilize graphs
    //     in
    // HA
    int suggestedPrecision = 0;
    if (strcmp(unit, "°F") == 0)
      suggestedPrecision = 1; // Fahrenheit: one decimal
    else if (strcmp(unit, "V") == 0)
      suggestedPrecision = 2; // Volts: two decimals
    else if (strcmp(unit, "hPa") == 0)
      suggestedPrecision = 1; // Pressure: one decimal
                              //     else
    suggestedPrecision = 0;   // Percent and others: integer
    // Full HA discovery keys for maximum compatibility; retained
    snprintf(payload, sizeof(payload),

             "{\"name\":\"%s\",\"unique_id\":\"%s_%s\",\"state_topic\":\"%s\","
             //              "\"availability_topic\":\"%s\",\"unit_of_measurement\":\"%s\","
             "\"device_class\":\"%s\",\"state_class\":\"measurement\","
             //              "\"suggested_display_precision\":%d,\"expire_after\":%u,"
             "\"device\":{\"identifiers\":[\"%s\"],\"name\":\"ESP32 Room Node: "
             //              "%s\",\"manufacturer\":\"DIY\",\"model\":\"Feather "
             "ESP32-S2\",\"sw_version\":\"%s\"}}",
             name, g_client_id, key, stateTopic, availTopic, unit, dev_class,
             //     suggestedPrecision,
             static_cast<unsigned>(expireAfterSec), g_client_id, ROOM_NAME, FW_VERSION);
    g_mqtt.publish(discTopic, payload, true);
    Serial.print("HA discovery -> ");
    Serial.println(discTopic);
  };

  pub_disc("inside_temp", "Inside Temperature", "°F", "temperature", "inside/temp");
  pub_disc("inside_hum", "Inside Humidity", "%", "humidity", "inside/hum");
  pub_disc("inside_pressure", "Barometric Pressure", "hPa", "pressure", "inside/pressure");
  pub_disc("battery_volts", "Battery Voltage", "V", "voltage", "battery/voltage");
  pub_disc("battery_pct", "Battery", "%", "battery", "battery/percent");
  // Additional diagnostics published each wake
  pub_disc("wifi_rssi", "WiFi RSSI", "dBm", "signal_strength", "wifi/rssi");
  pub_disc("publish_ms", "Publish Latency", "ms", "duration", "debug/publish_ms");
}

inline bool net_wifi_is_connected() { return WiFi.isConnected(); }

inline bool net_mqtt_is_connected() { return g_mqtt.connected(); }

inline void net_prepare_for_sleep() {
  // Publish availability offline and disconnect cleanly before deep sleep
  if (g_mqtt.connected()) {
    char availTopic[128];
    snprintf(availTopic, sizeof(availTopic), "%s/availability", MQTT_PUB_BASE);
    g_mqtt.publish(availTopic, "offline", true);
    mqtt_pump(100);
    g_mqtt.disconnect();
  }
  if (WiFi.isConnected()) {
    WiFi.disconnect(true);
  }
  // Ensure the Wi-Fi radio is fully powered down between wakes
  WiFi.mode(WIFI_OFF);
}
