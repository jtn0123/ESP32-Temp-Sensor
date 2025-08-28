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