#pragma once

#include <Arduino.h>
#include <WiFi.h>
#include <PubSubClient.h>

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
    // Optional fast connect via channel/BSSID
    #ifdef WIFI_BSSID
    {
        uint8_t bssid[6];
        int channel = 0;
        #ifdef WIFI_CHANNEL
        channel = WIFI_CHANNEL;
        #endif
        if (parse_bssid(WIFI_BSSID, bssid)) {
            WiFi.begin(WIFI_SSID, WIFI_PASS, channel, bssid, true);
        } else {
            WiFi.begin(WIFI_SSID, WIFI_PASS);
        }
    }
    #else
    #ifdef WIFI_CHANNEL
    WiFi.begin(WIFI_SSID, WIFI_PASS, WIFI_CHANNEL);
    #else
    WiFi.begin(WIFI_SSID, WIFI_PASS);
    #endif
    #endif
    unsigned long start = millis();
    while (!WiFi.isConnected() && millis() - start < WIFI_CONNECT_TIMEOUT_MS) {
        delay(100);
    }
    if (WiFi.isConnected()) {
        Serial.printf("WiFi: connected, IP %s RSSI %d dBm\n", WiFi.localIP().toString().c_str(), WiFi.RSSI());
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

inline void net_publish_status(const char* payload, bool retain = true) {
    if (!g_mqtt.connected() || !payload) return;
    char topic[128];
    snprintf(topic, sizeof(topic), "%s/status", MQTT_PUB_BASE);
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

    pub_disc("inside_temp", "Inside Temperature", "°F", "temperature", "inside/temp");
    pub_disc("inside_hum",  "Inside Humidity",    "%",  "humidity",   "inside/hum");
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


