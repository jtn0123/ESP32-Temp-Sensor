// Metrics and diagnostics implementation
#include "metrics_diagnostics.h"
#include "generated_config.h"
#include "display_layout.h"
#include "net.h"
#include "mqtt_client.h"
#include <time.h>

#if USE_STATUS_PIXEL
#include <Adafruit_NeoPixel.h>
#endif

// Global diagnostic mode flag
static bool g_diagnostic_mode = false;

// RTC variables for boot tracking (persist across deep sleep)
RTC_DATA_ATTR static uint32_t rtc_boot_count = 0;           // Total boots since power-on
RTC_DATA_ATTR static uint32_t rtc_crash_count = 0;          // Count of abnormal resets
RTC_DATA_ATTR static uint32_t rtc_cumulative_uptime_sec = 0; // Total awake time in seconds
RTC_DATA_ATTR static uint32_t rtc_last_boot_timestamp = 0;   // Timestamp of last boot
RTC_DATA_ATTR static esp_reset_reason_t rtc_last_reset_reason = ESP_RST_UNKNOWN;

// Status pixel object if enabled
#if USE_STATUS_PIXEL
static Adafruit_NeoPixel* g_status_pixel = nullptr;
static uint8_t g_pixel_phase = 0;
#endif

// Check if diagnostic mode is active
bool is_diagnostic_mode_active() {
  return g_diagnostic_mode;
}

// Set diagnostic mode
void set_diagnostic_mode(bool active) {
  g_diagnostic_mode = active;
  mqtt_publish_diagnostic_mode(active);
}

// Check for rapid reset diagnostic trigger
bool check_rapid_reset_diagnostic_trigger() {
  // Check if we've had 3+ resets within a short time window
  // This would require tracking reset times in RTC memory
  // For now, simplified implementation
  
  static uint32_t last_reset_time = 0;
  uint32_t now = millis();
  
  // If reset within 10 seconds of boot, consider it rapid
  if (now < 10000) {
    // Would need to check RTC memory for previous reset times
    // Simplified: always return false for now
    return false;
  }
  
  return false;
}

// Emit metrics as JSON for debugging
void emit_metrics_json(float tempC, float rhPct, float pressHPa) {
  if (!mqtt_is_connected()) {
    return;
  }
  
  char json[256];
  snprintf(json, sizeof(json),
           "{\"temp_c\":%.2f,\"rh_pct\":%.1f,\"press_hpa\":%.1f,\"ts\":%lu}",
           isfinite(tempC) ? tempC : 0.0f,
           isfinite(rhPct) ? rhPct : 0.0f,
           isfinite(pressHPa) ? pressHPa : 0.0f,
           (unsigned long)time(nullptr));
  
  mqtt_publish_debug_json(json, false);
}

// Publish layout identity for UI parity checking
void publish_layout_identity() {
  if (!mqtt_is_connected()) {
    return;
  }
  
  char topic[128];
  snprintf(topic, sizeof(topic), "%s/layout", MQTT_PUB_BASE);
  
  char payload[96];
  snprintf(payload, sizeof(payload), 
           "{\"layout_version\":%u,\"layout_crc\":\"0x%08X\"}",
           static_cast<unsigned>(LAYOUT_VERSION), 
           static_cast<unsigned>(LAYOUT_CRC));
  
  mqtt_publish_raw(topic, payload, true);
}

// Pump network for a duration to receive MQTT messages
void pump_network_ms(uint32_t duration_ms) {
  uint32_t start = millis();
  
  while (millis() - start < duration_ms) {
    net_loop();
    delay(10);
    
    #if USE_STATUS_PIXEL
    status_pixel_tick();
    #endif
  }
}

// Get current time as HH:MM string
void net_time_hhmm(char* out, size_t out_size) {
  if (!out || out_size < 6) {
    return;
  }
  
  time_t now = time(nullptr);
  struct tm tm_now;
  localtime_r(&now, &tm_now);
  
  snprintf(out, out_size, "%02d:%02d", tm_now.tm_hour, tm_now.tm_min);
}

// Status pixel operations
#if USE_STATUS_PIXEL

void status_pixel_begin() {
  if (!g_status_pixel) {
    #ifdef STATUS_PIXEL_PIN
    g_status_pixel = new Adafruit_NeoPixel(1, STATUS_PIXEL_PIN, NEO_GRB + NEO_KHZ800);
    #else
    // If no pin defined, use a default or skip
    return;
    #endif
    g_status_pixel->begin();
    g_status_pixel->setBrightness(20);
    g_status_pixel->show();
  }
}

void status_pixel_off() {
  if (g_status_pixel) {
    g_status_pixel->clear();
    g_status_pixel->show();
  }
}

void status_pixel_tick() {
  if (!g_status_pixel) {
    return;
  }
  
  // Simple color cycling for status indication
  static uint32_t last_change = 0;
  uint32_t now = millis();
  
  if (now - last_change >= 250) {
    g_pixel_phase = (g_pixel_phase + 1) % 4;
    
    switch (g_pixel_phase) {
      case 0:
        g_status_pixel->setPixelColor(0, 0, 0, 255);  // Blue
        break;
      case 1:
        g_status_pixel->setPixelColor(0, 0, 255, 0);  // Green
        break;
      case 2:
        g_status_pixel->setPixelColor(0, 255, 0, 0);  // Red
        break;
      case 3:
        g_status_pixel->setPixelColor(0, 255, 255, 0);  // Yellow
        break;
    }
    
    g_status_pixel->show();
    last_change = now;
  }
}

#endif // USE_STATUS_PIXEL

// Boot and crash tracking functions
void update_boot_counters() {
  esp_reset_reason_t current_reset_reason = esp_reset_reason();
  rtc_last_reset_reason = current_reset_reason;
  
  // Update boot and crash counters
  if (current_reset_reason == ESP_RST_POWERON) {
    // Power-on reset: clear all counters
    rtc_boot_count = 1;
    rtc_crash_count = 0;
    rtc_cumulative_uptime_sec = 0;
  } else {
    // Any other reset: increment boot count
    rtc_boot_count++;
    
    // Increment crash count for abnormal resets
    // Need to check if it's a crash (would need system_manager function)
    if (current_reset_reason == ESP_RST_PANIC || 
        current_reset_reason == ESP_RST_INT_WDT ||
        current_reset_reason == ESP_RST_TASK_WDT ||
        current_reset_reason == ESP_RST_WDT ||
        current_reset_reason == ESP_RST_BROWNOUT) {
      rtc_crash_count++;
    }
  }
  
  // Update boot timestamp for rapid reset detection
  rtc_last_boot_timestamp = static_cast<uint32_t>(time(nullptr));
}

uint32_t get_boot_count() {
  return rtc_boot_count;
}

uint32_t get_crash_count() {
  return rtc_crash_count;
}

uint32_t get_cumulative_uptime_sec() {
  return rtc_cumulative_uptime_sec;
}

void add_to_cumulative_uptime(uint32_t seconds) {
  rtc_cumulative_uptime_sec += seconds;
}

uint32_t get_last_boot_timestamp() {
  return rtc_last_boot_timestamp;
}

void set_last_boot_timestamp(uint32_t timestamp) {
  rtc_last_boot_timestamp = timestamp;
}

esp_reset_reason_t get_last_reset_reason() {
  return rtc_last_reset_reason;
}

void publish_boot_diagnostics() {
  if (!mqtt_is_connected()) {
    return;
  }
  
  // Publish boot diagnostics via MQTT
  char topic[128];
  char payload[64];
  
  snprintf(topic, sizeof(topic), "%s/debug/boot_count", MQTT_PUB_BASE);
  snprintf(payload, sizeof(payload), "%lu", (unsigned long)rtc_boot_count);
  mqtt_publish_raw(topic, payload, false);
  
  snprintf(topic, sizeof(topic), "%s/debug/crash_count", MQTT_PUB_BASE);
  snprintf(payload, sizeof(payload), "%lu", (unsigned long)rtc_crash_count);
  mqtt_publish_raw(topic, payload, false);
  
  snprintf(topic, sizeof(topic), "%s/debug/uptime", MQTT_PUB_BASE);
  snprintf(payload, sizeof(payload), "%lu", (unsigned long)rtc_cumulative_uptime_sec);
  mqtt_publish_raw(topic, payload, false);
}