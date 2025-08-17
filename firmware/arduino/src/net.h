#pragma once

#include <Arduino.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <Preferences.h>
#include <esp_wifi.h>

// All configuration should come from generated_config.h

struct OutsideReadings {
    float temperatureC = NAN;
    float humidityPct = NAN;
    char weather[64];
    float windMps = NAN;
    float highTempC = NAN;
    float lowTempC = NAN;
    bool validTemp = false;
    bool validHum = false;
    bool validWeather = false;
    bool validWind = false;
    bool validHigh = false;
    bool validLow = false;
};

static WiFiClient g_wifi_client;
static PubSubClient g_mqtt(g_wifi_client);
static OutsideReadings g_outside;
static char g_client_id[40];
static Preferences g_net_prefs;

#ifndef WIFI_CONNECT_TIMEOUT_MS
#define WIFI_CONNECT_TIMEOUT_MS 6000
#endif
#ifndef MQTT_CONNECT_TIMEOUT_MS
#define MQTT_CONNECT_TIMEOUT_MS 4000
#endif

inline bool parse_bssid(const char* str, uint8_t out[6]) {
    if (!str) return false;
    int vals[6];
    int n = sscanf(str, "%x:%x:%x:%x:%x:%x", &vals[0], &vals[1], &vals[2], &vals[3], &vals[4], &vals[5]);
    if (n != 6) return false;
    for (int i = 0; i < 6; ++i) out[i] = (uint8_t)vals[i];
    return true;
}

inline bool is_all_zero_bssid(const uint8_t b[6]) {
    for (int i = 0; i < 6; ++i) if (b[i] != 0) return false;
    return true;
}

// Optional tuning knobs (can be overridden via build_flags)
#ifndef WIFI_RSSI_THRESHOLD
#define WIFI_RSSI_THRESHOLD -75
#endif
#ifndef WIFI_AUTHMODE_THRESHOLD
#define WIFI_AUTHMODE_THRESHOLD WIFI_AUTH_WPA2_PSK
#endif

// NVS helpers: remember last successful AP (SSID + BSSID)
inline bool nvs_load_last_ap(String& ssid, uint8_t bssid[6]) {
    bool ok = false;
    if (g_net_prefs.begin("net", true)) {
        ssid = g_net_prefs.getString("last_ssid", "");
        size_t n = g_net_prefs.getBytes("last_bssid", bssid, 6);
        g_net_prefs.end();
        if (ssid.length() > 0 && n == 6 && !is_all_zero_bssid(bssid)) ok = true;
    } else {
        ssid = String();
        memset(bssid, 0, 6);
    }
    return ok;
}

inline void nvs_store_last_ap(const char* ssid, const uint8_t bssid[6]) {
    if (!ssid || !bssid) return;
    if (g_net_prefs.begin("net", false)) {
        g_net_prefs.putString("last_ssid", ssid);
        g_net_prefs.putBytes("last_bssid", bssid, 6);
        g_net_prefs.end();
    }
}

inline bool ends_with(const char* s, const char* suffix) {
    size_t ls = strlen(s);
    size_t lf = strlen(suffix);
    if (lf > ls) return false;
    return strcmp(s + (ls - lf), suffix) == 0;
}

inline void mqtt_callback(char* topic, uint8_t* payload, unsigned int length) {
    char val[128];
    unsigned int n = length < (sizeof(val) - 1) ? length : (unsigned int)(sizeof(val) - 1);
    for (unsigned int i = 0; i < n; ++i) val[i] = (char)payload[i];
    val[n] = '\0';
    if (ends_with(topic, "/temp")) {
        g_outside.temperatureC = atof(val);
        g_outside.validTemp = true;
    } else if (ends_with(topic, "/hum") || ends_with(topic, "/rh")) {
        g_outside.humidityPct = atof(val);
        g_outside.validHum = true;
    } else if (ends_with(topic, "/weather")) {
        strncpy(g_outside.weather, val, sizeof(g_outside.weather) - 1);
        g_outside.weather[sizeof(g_outside.weather) - 1] = '\0';
        g_outside.validWeather = g_outside.weather[0] != '\0';
    } else if (ends_with(topic, "/wind") || ends_with(topic, "/wind_mps") || ends_with(topic, "/wind_mph")) {
        float w = atof(val);
        if (ends_with(topic, "/wind_mph")) w = w / 2.237f;
        g_outside.windMps = w;
        g_outside.validWind = isfinite(w);
    } else if (ends_with(topic, "/hi") || ends_with(topic, "/high")) {
        g_outside.highTempC = atof(val);
        g_outside.validHigh = isfinite(g_outside.highTempC);
    } else if (ends_with(topic, "/lo") || ends_with(topic, "/low")) {
        g_outside.lowTempC = atof(val);
        g_outside.validLow = isfinite(g_outside.lowTempC);
    }
}

inline void ensure_wifi_connected() {
    if (WiFi.isConnected()) return;
    if (strlen(WIFI_SSID) == 0) return;
    Serial.printf("WiFi: connecting to %s...\n", WIFI_SSID);
    WiFi.mode(WIFI_STA);
    WiFi.persistent(false);
    WiFi.setAutoReconnect(true);

    // Constrain scan channels by country when provided (faster, legal)
    #ifdef WIFI_COUNTRY
    esp_wifi_set_country_code(WIFI_COUNTRY, true);
    #endif
    // Optional static IP configuration
    #ifdef WIFI_STATIC_IP
    {
        IPAddress ip, gw, sn;
        IPAddress d1(0,0,0,0), d2(0,0,0,0);
        bool ok = ip.fromString(WIFI_STATIC_IP) && gw.fromString(WIFI_STATIC_GATEWAY) && sn.fromString(WIFI_STATIC_SUBNET);
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

    // Preconfigure station with connect=false so we can tweak IDF fields before connecting
    if (have_bssid) {
        WiFi.begin(WIFI_SSID, WIFI_PASS, 0 /*channel*/, prefer_bssid, false /*connect*/);
        Serial.printf("WiFi: preferring BSSID %02x:%02x:%02x:%02x:%02x:%02x\n",
                      prefer_bssid[0], prefer_bssid[1], prefer_bssid[2],
                      prefer_bssid[3], prefer_bssid[4], prefer_bssid[5]);
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

    unsigned long start = millis();
    // Give BSSID-pinned attempt a shorter window before falling back
    unsigned long bssid_try_ms = have_bssid ? (WIFI_CONNECT_TIMEOUT_MS > 4000 ? 3000UL : WIFI_CONNECT_TIMEOUT_MS / 2) : 0UL;
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
        Serial.printf("WiFi: connected, IP %s RSSI %d dBm\n", WiFi.localIP().toString().c_str(), WiFi.RSSI());
        // Cache last SSID + BSSID for next wake
        uint8_t now_bssid[6] = {0};
        const uint8_t* bp = WiFi.BSSID();
        if (bp) memcpy(now_bssid, bp, 6);
        if (!is_all_zero_bssid(now_bssid)) {
            nvs_store_last_ap(WIFI_SSID, now_bssid);
        }
    } else {
        Serial.printf("WiFi: connect timeout (status=%d)\n", (int)WiFi.status());
    }
}

inline void ensure_mqtt_connected() {
    if (g_mqtt.connected()) return;
    if (strlen(MQTT_HOST) == 0) return;
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
    Serial.printf("MQTT: connecting to %s:%u...\n", MQTT_HOST, (unsigned)MQTT_PORT);
    uint64_t mac = ESP.getEfuseMac();
    // Use lower 24 bits
    snprintf(g_client_id, sizeof(g_client_id), "esp32-room-%06x", (unsigned int)(mac & 0xFFFFFF));
    unsigned long start = millis();
    const char* user = nullptr;
    const char* pass = nullptr;
    #ifdef MQTT_USER
    if (strlen(MQTT_USER) > 0) user = MQTT_USER;
    #endif
    #ifdef MQTT_PASS
    if (strlen(MQTT_PASS) > 0) pass = MQTT_PASS;
    #endif
    // Set LWT to availability topic so HA can mark device offline if we drop unexpectedly
    char availTopic[128];
    snprintf(availTopic, sizeof(availTopic), "%s/availability", MQTT_PUB_BASE);
    while (!g_mqtt.connect(g_client_id, user, pass, availTopic, 0, true, "offline") && millis() - start < MQTT_CONNECT_TIMEOUT_MS) {
        delay(200);
    }
    if (g_mqtt.connected()) {
        Serial.println("MQTT: connected");
        // Publish availability online on successful connect
        g_mqtt.publish(availTopic, "online", true);
        char topic[128];
        const char* base = MQTT_SUB_BASE;
        auto sub = [&](const char* suffix){
            snprintf(topic, sizeof(topic), "%s%s", base, suffix);
            g_mqtt.subscribe(topic);
            Serial.printf("MQTT: subscribed %s\n", topic);
        };
        sub("/temp");
        sub("/hum");
        sub("/rh");
        sub("/weather");
        sub("/wind");
        sub("/wind_mps");
        sub("/wind_mph");
        sub("/high");
        sub("/hi");
        sub("/low");
        sub("/lo");
    } else {
        Serial.println("MQTT: connect timeout/fail");
    }
}

inline void net_begin() {
    ensure_wifi_connected();
    ensure_mqtt_connected();
}

inline void net_loop() {
    static bool last_wifi = false;
    static bool last_mqtt = false;
    if (!WiFi.isConnected()) ensure_wifi_connected();
    if (WiFi.isConnected() && !g_mqtt.connected()) ensure_mqtt_connected();
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
    if (now_mqtt) g_mqtt.loop();
}

inline String net_ip() {
    if (!WiFi.isConnected()) return String("0.0.0.0");
    return WiFi.localIP().toString();
}

inline void net_ip_cstr(char* out, size_t out_size) {
    if (!out || out_size == 0) return;
    if (!WiFi.isConnected()) {
        snprintf(out, out_size, "%s", "0.0.0.0");
        return;
    }
    IPAddress ip = WiFi.localIP();
    snprintf(out, out_size, "%u.%u.%u.%u", (unsigned)ip[0], (unsigned)ip[1], (unsigned)ip[2], (unsigned)ip[3]);
}

inline void mqtt_pump(uint32_t duration_ms) {
    unsigned long start = millis();
    while (millis() - start < duration_ms) {
        if (g_mqtt.connected()) g_mqtt.loop();
        delay(10);
    }
}

inline OutsideReadings net_get_outside() { return g_outside; }

inline void net_publish_inside(float tempC, float rhPct) {
    if (!g_mqtt.connected()) return;
    char topic[128];
    char payload[32];
    const char* base = MQTT_PUB_BASE;
    snprintf(topic, sizeof(topic), "%s/inside/temp", base);
    // Publish Fahrenheit for HA (discovery advertises °F)
    float tempF = tempC * 9.0f/5.0f + 32.0f;
    dtostrf(tempF, 0, 1, payload);
    g_mqtt.publish(topic, payload, true);
    snprintf(topic, sizeof(topic), "%s/inside/hum", base);
    dtostrf(rhPct, 0, 0, payload);
    g_mqtt.publish(topic, payload, true);
}

inline void net_publish_battery(float voltage, int percent) {
    if (!g_mqtt.connected()) return;
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

inline void net_publish_status(const char* payload, bool retain = true) {
    if (!g_mqtt.connected() || !payload) return;
    char topic[128];
    snprintf(topic, sizeof(topic), "%s/status", MQTT_PUB_BASE);
    g_mqtt.publish(topic, payload, retain);
}

// Publish a JSON debug payload with wake metrics to sensors/<node>/debug
inline void net_publish_debug_json(const char* payload, bool retain = false) {
    if (!g_mqtt.connected() || !payload) return;
    char topic[128];
    snprintf(topic, sizeof(topic), "%s/debug", MQTT_PUB_BASE);
    g_mqtt.publish(topic, payload, retain);
}

// Publish a small probe message to measure publish latency without affecting retained state
inline void net_publish_debug_probe(const char* payload, bool retain = false) {
    if (!g_mqtt.connected() || !payload) return;
    char topic[128];
    snprintf(topic, sizeof(topic), "%s/debug_probe", MQTT_PUB_BASE);
    g_mqtt.publish(topic, payload, retain);
}

// Publish Home Assistant MQTT Discovery configs for inside temperature and humidity
inline void net_publish_ha_discovery() {
    if (!g_mqtt.connected()) return;
    // Topics and availability
    char availTopic[128];
    snprintf(availTopic, sizeof(availTopic), "%s/availability", MQTT_PUB_BASE);

    // Helper to publish one discovery config
    auto pub_disc = [&](const char* key, const char* name, const char* unit, const char* dev_class, const char* state_suffix){
        char discTopic[192];
        snprintf(discTopic, sizeof(discTopic), "homeassistant/sensor/%s_%s/config", g_client_id, key);
        char stateTopic[192];
        snprintf(stateTopic, sizeof(stateTopic), "%s/%s", MQTT_PUB_BASE, state_suffix);
        char payload[640];
        // Full HA discovery keys for maximum compatibility; retained
        snprintf(payload, sizeof(payload),
            "{\"name\":\"%s\",\"unique_id\":\"%s_%s\",\"state_topic\":\"%s\",\"availability_topic\":\"%s\",\"unit_of_measurement\":\"%s\",\"device_class\":\"%s\",\"state_class\":\"measurement\",\"device\":{\"identifiers\":[\"%s\"],\"name\":\"ESP32 Room Node: %s\",\"manufacturer\":\"DIY\",\"model\":\"Feather ESP32-S2\"}}",
            name, g_client_id, key, stateTopic, availTopic, unit, dev_class, g_client_id, ROOM_NAME);
        g_mqtt.publish(discTopic, payload, true);
        Serial.print("HA discovery -> ");
        Serial.println(discTopic);
    };

    pub_disc("inside_temp",   "Inside Temperature", "°F", "temperature", "inside/temp");
    pub_disc("inside_hum",    "Inside Humidity",    "%",  "humidity",    "inside/hum");
    pub_disc("battery_volts", "Battery Voltage",    "V",  "voltage",     "battery/voltage");
    pub_disc("battery_pct",   "Battery",            "%",  "battery",     "battery/percent");
}

inline bool net_wifi_is_connected() {
    return WiFi.isConnected();
}

inline bool net_mqtt_is_connected() {
    return g_mqtt.connected();
}

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
}


