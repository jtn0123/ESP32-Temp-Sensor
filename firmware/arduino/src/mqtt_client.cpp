// MQTT client implementation - extracted from net.h
#include "mqtt_client.h"
#include "generated_config.h"
#include "config.h"
#include <Preferences.h>
#if LOG_MQTT_ENABLED
#include "logging/log_mqtt.h"
#endif

// Static storage
static WiFiClient g_wifi_client;
static PubSubClient g_mqtt(g_wifi_client);
static OutsideReadings g_outside;
static char g_mqtt_client_id[40];  // Renamed to avoid conflict with net.h
static Preferences g_mqtt_prefs;

// Diagnostic mode flags
static bool g_diagnostic_mode_requested = false;
static bool g_diagnostic_mode_request_value = false;

// Helper to build MQTT topic
static String build_topic(const char* suffix) {
  return String("espsensor/") + g_mqtt_client_id + "/" + suffix;
}

void mqtt_begin() {
  // Client ID will be set externally via mqtt_set_client_id
  // to avoid WiFi dependency in this module
  
  // Configure MQTT client
  g_mqtt.setBufferSize(MQTT_MAX_PACKET_SIZE);
  
  // Set MQTT server
  #ifdef MQTT_HOST
  g_mqtt.setServer(MQTT_HOST, MQTT_PORT);
  #endif
  
  // Set up MQTT callback for commands and outdoor data
  g_mqtt.setCallback([](char* topic, byte* payload, unsigned int length) {
    String topicStr(topic);
    
    // Handle diagnostic mode commands
    if (topicStr.endsWith("/cmd/diagnostic_mode")) {
      if (length > 0) {
        char value = (char)payload[0];
        g_diagnostic_mode_requested = true;
        g_diagnostic_mode_request_value = (value == '1' || value == 't' || value == 'T');
      }
      return;
    }
    
    // Forward log commands to LogMQTT
    #if LOG_MQTT_ENABLED
    if (topicStr.indexOf("/cmd/clear_logs") >= 0 || topicStr.indexOf("/cmd/log_level") >= 0) {
      log_mqtt_handle_command(topic, (const uint8_t*)payload, length);
      return;
    }
    #endif
    
    // Handle outdoor weather data (alias topics)
    #ifdef MQTT_SUB_BASE
    // Helper function to check if topic ends with a string
    auto ends_with = [](const String& str, const char* suffix) {
      int suffixLen = strlen(suffix);
      int strLen = str.length();
      if (strLen < suffixLen) return false;
      return str.substring(strLen - suffixLen) == suffix;
    };
    
    // Convert payload to string
    char value_str[64];
    if (length < sizeof(value_str)) {
      memcpy(value_str, payload, length);
      value_str[length] = '\0';
    } else {
      value_str[0] = '\0';
    }
    
    // Handle temperature in Fahrenheit
    if (ends_with(topicStr, "/temp_f")) {
      float temp_f = atof(value_str);
      if (isfinite(temp_f)) {
        // Convert to Celsius and update outside readings
        float temp_c = (temp_f - 32.0f) * 5.0f / 9.0f;
        g_outside.temperatureC = temp_c;
        g_outside.validTemp = true;
      }
    }
    // Handle temperature in Celsius (legacy)
    else if (ends_with(topicStr, "/temp")) {
      float temp_c = atof(value_str);
      if (isfinite(temp_c)) {
        g_outside.temperatureC = temp_c;
        g_outside.validTemp = true;
      }
    }
    // Handle weather condition text
    else if (ends_with(topicStr, "/condition")) {
      snprintf(g_outside.weather, sizeof(g_outside.weather), "%s", value_str);
      g_outside.validWeather = true;
    }
    // Handle weather description (legacy)
    else if (ends_with(topicStr, "/weather")) {
      snprintf(g_outside.weather, sizeof(g_outside.weather), "%s", value_str);
      g_outside.validWeather = true;
    }
    // Handle weather condition code (currently not stored separately)
    else if (ends_with(topicStr, "/condition_code")) {
      // Weather code could be used to map to weather text if needed
      // For now, we rely on the condition text itself
    }
    // Handle weather ID (legacy - currently not stored separately)
    else if (ends_with(topicStr, "/weather_id")) {
      // Weather ID could be used to map to weather text if needed  
      // For now, we rely on the weather text itself
    }
    #endif
  });
}

void mqtt_loop() {
  if (g_mqtt.connected()) {
    g_mqtt.loop();
  }
}

bool mqtt_connect() {
  // Assume caller has already checked WiFi connectivity
  // This removes WiFi dependency from mqtt module
  
  if (g_mqtt.connected()) {
    return true;
  }
  
  // Build LWT topic and message
  String lwt_topic = build_topic("availability");
  
  // Connect with authentication if configured
  bool connected = false;
  #if defined(MQTT_USER) && defined(MQTT_PASS)
  connected = g_mqtt.connect(g_mqtt_client_id, MQTT_USER, MQTT_PASS,
                            lwt_topic.c_str(), 0, true, "offline");
  #else
  connected = g_mqtt.connect(g_mqtt_client_id, lwt_topic.c_str(), 0, true, "offline");
  #endif
  
  if (connected) {
    // Publish online status
    g_mqtt.publish(lwt_topic.c_str(), "online", true);
    
    // Subscribe to command topics
    String cmd_topic = build_topic("cmd/+");
    g_mqtt.subscribe(cmd_topic.c_str());
    
    // Subscribe to outdoor weather data (alias topics)
    #ifdef MQTT_SUB_BASE
    String outdoor_base = String(MQTT_SUB_BASE);
    // Subscribe to alias topics for outdoor data
    String sub_topics[] = {
      outdoor_base + "/temp_f",      // Temperature in Fahrenheit
      outdoor_base + "/condition",   // Weather condition text
      outdoor_base + "/condition_code", // Weather condition code
      // Legacy topics for backward compatibility
      outdoor_base + "/temp",        // Temperature in Celsius
      outdoor_base + "/weather",     // Weather description
      outdoor_base + "/weather_id"   // Weather ID
    };
    
    for (const String& topic : sub_topics) {
      g_mqtt.subscribe(topic.c_str());
    }
    #endif
  }
  
  return connected;
}

bool mqtt_is_connected() {
  return g_mqtt.connected();
}

void mqtt_disconnect() {
  if (g_mqtt.connected()) {
    // Publish offline status before disconnecting
    String lwt_topic = build_topic("availability");
    g_mqtt.publish(lwt_topic.c_str(), "offline", true);
    g_mqtt.disconnect();
  }
}

void mqtt_set_client_id(const char* client_id) {
  if (client_id) {
    snprintf(g_mqtt_client_id, sizeof(g_mqtt_client_id), "%s", client_id);
  }
}

void mqtt_set_server(const char* server, uint16_t port) {
  g_mqtt.setServer(server, port);
}

bool mqtt_publish_raw(const char* topic, const char* payload, bool retain) {
  if (!g_mqtt.connected()) return false;
  return g_mqtt.publish(topic, payload, retain);
}

// Publishing implementations
void mqtt_publish_inside(float tempC, float rhPct) {
  if (!g_mqtt.connected()) return;
  
  char payload[64];
  
  // Publish temperature
  if (isfinite(tempC)) {
    snprintf(payload, sizeof(payload), "%.1f", tempC);
    g_mqtt.publish(build_topic("inside/temperature").c_str(), payload, true);
  }
  
  // Publish humidity
  if (isfinite(rhPct)) {
    snprintf(payload, sizeof(payload), "%.1f", rhPct);
    g_mqtt.publish(build_topic("inside/humidity").c_str(), payload, true);
  }
}

void mqtt_publish_pressure(float pressureHPa) {
  if (!g_mqtt.connected() || !isfinite(pressureHPa)) return;
  
  char payload[32];
  snprintf(payload, sizeof(payload), "%.1f", pressureHPa);
  g_mqtt.publish(build_topic("inside/pressure").c_str(), payload, true);
}

void mqtt_publish_battery(float voltage, int percent) {
  if (!g_mqtt.connected()) return;
  
  char payload[32];
  
  // Publish voltage
  if (isfinite(voltage)) {
    snprintf(payload, sizeof(payload), "%.2f", voltage);
    g_mqtt.publish(build_topic("battery/voltage").c_str(), payload, true);
  }
  
  // Publish percentage
  if (percent >= 0) {
    snprintf(payload, sizeof(payload), "%d", percent);
    g_mqtt.publish(build_topic("battery/percent").c_str(), payload, true);
  }
}

void mqtt_publish_wifi_rssi(int rssiDbm) {
  if (!g_mqtt.connected()) return;
  
  char payload[16];
  snprintf(payload, sizeof(payload), "%d", rssiDbm);
  g_mqtt.publish(build_topic("wifi/rssi").c_str(), payload, true);
}

void mqtt_publish_status(const char* payload, bool retain) {
  if (!g_mqtt.connected() || !payload) return;
  g_mqtt.publish(build_topic("status").c_str(), payload, retain);
}

void mqtt_publish_debug_json(const char* payload, bool retain) {
  if (!g_mqtt.connected() || !payload) return;
  g_mqtt.publish(build_topic("debug/json").c_str(), payload, retain);
}

void mqtt_publish_last_crash(const char* reason_or_null) {
  if (!g_mqtt.connected()) return;
  
  if (reason_or_null) {
    g_mqtt.publish(build_topic("debug/last_crash").c_str(), reason_or_null, true);
  } else {
    g_mqtt.publish(build_topic("debug/last_crash").c_str(), "none", true);
  }
}

void mqtt_publish_debug_probe(const char* payload, bool retain) {
  if (!g_mqtt.connected() || !payload) return;
  g_mqtt.publish(build_topic("debug/probe").c_str(), payload, retain);
}

void mqtt_publish_boot_reason(const char* reason) {
  if (!g_mqtt.connected() || !reason) return;
  g_mqtt.publish(build_topic("debug/boot_reason").c_str(), reason, true);
}

void mqtt_publish_boot_count(uint32_t count) {
  if (!g_mqtt.connected()) return;
  
  char payload[16];
  snprintf(payload, sizeof(payload), "%u", count);
  g_mqtt.publish(build_topic("debug/boot_count").c_str(), payload, true);
}

void mqtt_publish_crash_count(uint32_t count) {
  if (!g_mqtt.connected()) return;
  
  char payload[16];
  snprintf(payload, sizeof(payload), "%u", count);
  g_mqtt.publish(build_topic("debug/crash_count").c_str(), payload, true);
}

void mqtt_publish_uptime(uint32_t uptime_sec) {
  if (!g_mqtt.connected()) return;
  
  char payload[16];
  snprintf(payload, sizeof(payload), "%u", uptime_sec);
  g_mqtt.publish(build_topic("debug/uptime").c_str(), payload, true);
}

void mqtt_publish_wake_count(uint32_t count) {
  if (!g_mqtt.connected()) return;
  
  char payload[16];
  snprintf(payload, sizeof(payload), "%u", count);
  g_mqtt.publish(build_topic("debug/wake_count").c_str(), payload, true);
}

void mqtt_publish_memory_diagnostics(uint32_t free_heap, uint32_t min_heap, 
                                    uint32_t largest_block, float fragmentation_pct) {
  if (!g_mqtt.connected()) return;
  
  char payload[128];
  snprintf(payload, sizeof(payload), 
          "{\"free\":%u,\"min\":%u,\"largest\":%u,\"frag\":%.1f}",
          free_heap, min_heap, largest_block, fragmentation_pct);
  g_mqtt.publish(build_topic("debug/memory").c_str(), payload, true);
}

void mqtt_publish_diagnostic_mode(bool active) {
  if (!g_mqtt.connected()) return;
  g_mqtt.publish(build_topic("diagnostic_mode").c_str(), active ? "true" : "false", true);
}

void mqtt_publish_publish_latency_ms(uint32_t publishLatencyMs) {
  if (!g_mqtt.connected()) return;
  
  char payload[16];
  snprintf(payload, sizeof(payload), "%u", publishLatencyMs);
  g_mqtt.publish(build_topic("debug/publish_latency_ms").c_str(), payload, true);
}

// Outside readings management
void mqtt_update_outside_readings(const OutsideReadings& readings) {
  g_outside = readings;
}

OutsideReadings mqtt_get_outside_readings() {
  return g_outside;
}

// Diagnostic mode
bool mqtt_is_diagnostic_mode_requested() {
  return g_diagnostic_mode_requested;
}

bool mqtt_get_diagnostic_mode_value() {
  return g_diagnostic_mode_request_value;
}

void mqtt_clear_diagnostic_mode_request() {
  g_diagnostic_mode_requested = false;
}

PubSubClient* mqtt_get_client() {
  return &g_mqtt;
}