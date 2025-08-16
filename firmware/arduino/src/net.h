#pragma once

#include <Arduino.h>
#include <WiFi.h>
#include <PubSubClient.h>

// All configuration should come from generated_config.h

struct OutsideReadings {
    float temperatureC = NAN;
    float humidityPct = NAN;
    String weather;
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

inline void mqtt_callback(char* topic, uint8_t* payload, unsigned int length) {
    String t(topic);
    String v;
    v.reserve(length + 1);
    for (unsigned int i = 0; i < length; i++) v += (char)payload[i];
    if (t.endsWith("/temp")) {
        g_outside.temperatureC = v.toFloat();
        g_outside.validTemp = true;
    } else if (t.endsWith("/hum") || t.endsWith("/rh")) {
        g_outside.humidityPct = v.toFloat();
        g_outside.validHum = true;
    } else if (t.endsWith("/weather")) {
        g_outside.weather = v;
        g_outside.validWeather = v.length() > 0;
    } else if (t.endsWith("/wind") || t.endsWith("/wind_mps") || t.endsWith("/wind_mph")) {
        // Accept m/s by default; if mph, convert to m/s by dividing by 2.237 when topic endswith wind_mph
        float w = v.toFloat();
        if (t.endsWith("/wind_mph")) w = w / 2.237f;
        g_outside.windMps = w;
        g_outside.validWind = isfinite(w);
    } else if (t.endsWith("/hi") || t.endsWith("/high")) {
        g_outside.highTempC = v.toFloat();
        g_outside.validHigh = isfinite(g_outside.highTempC);
    } else if (t.endsWith("/lo") || t.endsWith("/low")) {
        g_outside.lowTempC = v.toFloat();
        g_outside.validLow = isfinite(g_outside.lowTempC);
    }
}

inline void ensure_wifi_connected() {
    if (WiFi.isConnected()) return;
    if (strlen(WIFI_SSID) == 0) return;
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
}

inline void ensure_mqtt_connected() {
    if (g_mqtt.connected()) return;
    if (strlen(MQTT_HOST) == 0) return;
    g_mqtt.setServer(MQTT_HOST, MQTT_PORT);
    g_mqtt.setCallback(mqtt_callback);
    String clientId = String("esp32-room-") + String((uint32_t)ESP.getEfuseMac(), HEX);
    unsigned long start = millis();
    const char* user = nullptr;
    const char* pass = nullptr;
    #ifdef MQTT_USER
    if (strlen(MQTT_USER) > 0) user = MQTT_USER;
    #endif
    #ifdef MQTT_PASS
    if (strlen(MQTT_PASS) > 0) pass = MQTT_PASS;
    #endif
    while (!g_mqtt.connect(clientId.c_str(), user, pass) && millis() - start < MQTT_CONNECT_TIMEOUT_MS) {
        delay(200);
    }
    if (g_mqtt.connected()) {
        String base = MQTT_SUB_BASE;
        g_mqtt.subscribe((base + "/temp").c_str());
        g_mqtt.subscribe((base + "/hum").c_str());
        g_mqtt.subscribe((base + "/rh").c_str());
        g_mqtt.subscribe((base + "/weather").c_str());
        g_mqtt.subscribe((base + "/wind").c_str());
        g_mqtt.subscribe((base + "/wind_mps").c_str());
        g_mqtt.subscribe((base + "/wind_mph").c_str());
        g_mqtt.subscribe((base + "/high").c_str());
        g_mqtt.subscribe((base + "/hi").c_str());
        g_mqtt.subscribe((base + "/low").c_str());
        g_mqtt.subscribe((base + "/lo").c_str());
    }
}

inline void net_begin() {
    ensure_wifi_connected();
    ensure_mqtt_connected();
}

inline void net_loop() {
    if (!WiFi.isConnected()) ensure_wifi_connected();
    if (WiFi.isConnected() && !g_mqtt.connected()) ensure_mqtt_connected();
    if (g_mqtt.connected()) g_mqtt.loop();
}

inline String net_ip() {
    if (!WiFi.isConnected()) return String("0.0.0.0");
    return WiFi.localIP().toString();
}

inline OutsideReadings net_get_outside() { return g_outside; }

inline void net_publish_inside(float tempC, float rhPct) {
    if (!g_mqtt.connected()) return;
    String base = MQTT_PUB_BASE;
    char buf[32];
    dtostrf(tempC, 0, 2, buf);
    g_mqtt.publish((base + "/inside/temp").c_str(), buf, true);
    dtostrf(rhPct, 0, 0, buf);
    g_mqtt.publish((base + "/inside/hum").c_str(), buf, true);
}


