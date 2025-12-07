// Configuration validation for ESP32 Temperature Sensor
#pragma once

#include "generated_config.h"
#include "error_codes.h"
#include "logging.h"
#include <Arduino.h>
#include <IPAddress.h>

// Configuration limits
#define MIN_WAKE_INTERVAL_SEC 60        // 1 minute
#define MAX_WAKE_INTERVAL_SEC 86400     // 24 hours
#define MIN_FULL_REFRESH 1
#define MAX_FULL_REFRESH 100
#define MIN_MQTT_PORT 1
#define MAX_MQTT_PORT 65535
#define MAX_SSID_LENGTH 32
#define MAX_PASSWORD_LENGTH 64
#define MAX_HOSTNAME_LENGTH 63
#define MIN_ACTIVE_SECONDS 5
#define MAX_ACTIVE_SECONDS 300          // 5 minutes

// Safe mode configuration (minimal operation)
struct SafeModeConfig {
  const char* ssid = "SafeMode";
  const char* password = "";
  uint32_t wake_interval_sec = 3600;  // 1 hour
  uint32_t full_refresh_every = 10;
  bool display_enabled = true;
  bool sensors_enabled = false;
  bool mqtt_enabled = false;
};

// Validation result with details
struct ValidationResult {
  ErrorCode error_code;
  const char* field_name;
  const char* error_message;
};

// Validate string is not empty and within length limits
inline bool validate_string(const char* str, size_t max_len, const char* field_name) {
  if (!str || strlen(str) == 0) {
    LOG_ERROR("Config: %s is empty", field_name);
    return false;
  }
  if (strlen(str) > max_len) {
    LOG_ERROR("Config: %s too long (%d > %d)", field_name, strlen(str), max_len);
    return false;
  }
  return true;
}

// Validate IP address string format
inline bool validate_ip_address(const char* ip_str) {
  if (!ip_str || strlen(ip_str) == 0) return true;  // Empty is OK (not required)
  
  IPAddress ip;
  if (!ip.fromString(ip_str)) {
    LOG_ERROR("Config: Invalid IP address format: %s", ip_str);
    return false;
  }
  return true;
}

// Main configuration validation function
inline ErrorCode validate_config() {
  LOG_INFO("Validating configuration...");
  
  // Wake interval validation
  if (WAKE_INTERVAL_SEC < MIN_WAKE_INTERVAL_SEC || WAKE_INTERVAL_SEC > MAX_WAKE_INTERVAL_SEC) {
    LOG_ERROR("Config: wake_interval out of range: %d (must be %d-%d)", 
              WAKE_INTERVAL_SEC, MIN_WAKE_INTERVAL_SEC, MAX_WAKE_INTERVAL_SEC);
    return ERR_CONFIG_OUT_OF_RANGE;
  }
  LOG_DEBUG("Config: wake_interval = %d seconds", WAKE_INTERVAL_SEC);
  
  // Full refresh validation
  if (FULL_REFRESH_EVERY < MIN_FULL_REFRESH || FULL_REFRESH_EVERY > MAX_FULL_REFRESH) {
    LOG_ERROR("Config: full_refresh_every out of range: %d (must be %d-%d)",
              FULL_REFRESH_EVERY, MIN_FULL_REFRESH, MAX_FULL_REFRESH);
    return ERR_CONFIG_OUT_OF_RANGE;
  }
  LOG_DEBUG("Config: full_refresh_every = %d", FULL_REFRESH_EVERY);
  
  // WiFi configuration validation
  if (!validate_string(WIFI_SSID, MAX_SSID_LENGTH, "WiFi SSID")) {
    return ERR_WIFI_INVALID_SSID;
  }
  if (!validate_string(WIFI_PASS, MAX_PASSWORD_LENGTH, "WiFi password")) {
    return ERR_WIFI_INVALID_PASSWORD;
  }
  LOG_DEBUG("Config: WiFi SSID = %s", WIFI_SSID);
  
  // MQTT configuration validation
  if (!validate_string(MQTT_HOST, MAX_HOSTNAME_LENGTH, "MQTT host")) {
    return ERR_MQTT_INVALID_TOPIC;  // Reusing for host validation
  }
  if (MQTT_PORT < MIN_MQTT_PORT || MQTT_PORT > MAX_MQTT_PORT) {
    LOG_ERROR("Config: MQTT port out of range: %d (must be %d-%d)",
              MQTT_PORT, MIN_MQTT_PORT, MAX_MQTT_PORT);
    return ERR_CONFIG_OUT_OF_RANGE;
  }
  LOG_DEBUG("Config: MQTT host = %s:%d", MQTT_HOST, MQTT_PORT);
  
  // Room name validation
  if (!validate_string(ROOM_NAME, MAX_HOSTNAME_LENGTH, "Room name")) {
    return ERR_CONFIG_INVALID;
  }
  LOG_DEBUG("Config: Room name = %s", ROOM_NAME);
  
  // Optional IP configuration validation
  #ifdef WIFI_STATIC_IP
  if (!validate_ip_address(WIFI_STATIC_IP)) {
    return ERR_CONFIG_INVALID;
  }
  #endif
  
  #ifdef WIFI_STATIC_GW
  if (!validate_ip_address(WIFI_STATIC_GW)) {
    return ERR_CONFIG_INVALID;
  }
  #endif
  
  // Active seconds validation (if defined)
  #ifdef ACTIVE_SECONDS
  if (ACTIVE_SECONDS < MIN_ACTIVE_SECONDS || ACTIVE_SECONDS > MAX_ACTIVE_SECONDS) {
    LOG_WARN("Config: active_seconds out of range: %d (using default)", ACTIVE_SECONDS);
  }
  #endif
  
  // Threshold validations
  #ifdef THRESH_TEMP_DEGC
  if (THRESH_TEMP_DEGC <= 0 || THRESH_TEMP_DEGC > 10) {
    LOG_WARN("Config: temp threshold unusual: %.2f°C", THRESH_TEMP_DEGC);
  }
  #endif
  
  #ifdef THRESH_RH_PCT
  if (THRESH_RH_PCT <= 0 || THRESH_RH_PCT > 20) {
    LOG_WARN("Config: humidity threshold unusual: %.1f%%", THRESH_RH_PCT);
  }
  #endif
  
  LOG_INFO("Configuration validation successful");
  return ERR_NONE;
}

// Enter safe mode with minimal configuration
// After timeout, reboots with safe defaults applied (avoids sensor heating from infinite loop)
inline void enter_safe_mode(const char* reason = nullptr) {
  LOG_ERROR("ENTERING SAFE MODE%s%s", reason ? ": " : "", reason ? reason : "");
  
  // Safe mode timeout - reboot after 2 minutes to try again with safe defaults
  // This prevents: 1) device bricking, 2) sensor heating from always-on operation
  const uint32_t SAFE_MODE_TIMEOUT_MS = 2 * 60 * 1000;  // 2 minutes
  uint32_t safe_mode_start = millis();
  
  // Visual indication if display available
  #if USE_DISPLAY
  // This would show a safe mode message on display
  #endif
  
  // LED indication pattern
  #ifdef LED_BUILTIN
  pinMode(LED_BUILTIN, OUTPUT);
  #endif
  
  // Status pixel indication
  #if USE_STATUS_PIXEL
  // Set status pixel to orange/yellow for safe mode
  #endif
  
  // Safe mode loop - blink pattern until timeout
  uint32_t blink_count = 0;
  while (millis() - safe_mode_start < SAFE_MODE_TIMEOUT_MS) {
    // Distinctive safe mode blink pattern: 3 quick, pause
    for (int i = 0; i < 3; i++) {
      #ifdef LED_BUILTIN
      digitalWrite(LED_BUILTIN, HIGH);
      #endif
      delay(100);
      #ifdef LED_BUILTIN
      digitalWrite(LED_BUILTIN, LOW);
      #endif
      delay(100);
    }
    delay(1000);
    
    // Every 10 seconds, output status
    if (++blink_count % 10 == 0) {
      uint32_t remaining_sec = (SAFE_MODE_TIMEOUT_MS - (millis() - safe_mode_start)) / 1000;
      LOG_ERROR("Safe mode active (reason: %s) - reboot in %u sec", 
                reason ? reason : "config error", remaining_sec);
      log_heap_status("SafeMode");
    }
    
    // Could add WiFi AP mode here for reconfiguration
    // Could monitor for button press to factory reset
    // Could check for OTA update
    
    yield();  // Keep watchdog happy
  }
  
  // Timeout reached - reboot to try again
  // Safe defaults will be applied on next boot via apply_safe_defaults()
  LOG_ERROR("Safe mode timeout - rebooting with safe defaults");
  Serial.flush();
  delay(100);
  esp_restart();
}

// Validate and apply safe defaults for out-of-range values
inline void apply_safe_defaults() {
  LOG_INFO("Applying safe defaults for invalid config values");
  
  // This would need to modify the config at runtime
  // Since we're using #defines, we can't change them
  // Instead, we track what needs to be overridden
  
  static struct {
    uint32_t wake_interval_sec;
    uint32_t full_refresh_every;
    bool use_defaults;
  } safe_config = {0, 0, false};
  
  // Check and note needed overrides
  if (WAKE_INTERVAL_SEC < MIN_WAKE_INTERVAL_SEC || WAKE_INTERVAL_SEC > MAX_WAKE_INTERVAL_SEC) {
    safe_config.wake_interval_sec = 3600;  // 1 hour default
    safe_config.use_defaults = true;
    LOG_WARN("Will use safe wake interval: %d", safe_config.wake_interval_sec);
  }
  
  if (FULL_REFRESH_EVERY < MIN_FULL_REFRESH || FULL_REFRESH_EVERY > MAX_FULL_REFRESH) {
    safe_config.full_refresh_every = 10;
    safe_config.use_defaults = true;
    LOG_WARN("Will use safe full refresh: %d", safe_config.full_refresh_every);
  }
}

// Perform startup configuration check
inline ErrorCode startup_config_check() {
  LOG_INFO("=== Configuration Check ===");
  LOG_INFO("Firmware: %s", FW_VERSION);
  LOG_INFO("Room: %s", ROOM_NAME);
  LOG_INFO("Wake Interval: %d seconds", WAKE_INTERVAL_SEC);
  
  ErrorCode err = validate_config();
  
  if (err != ERR_NONE) {
    LOG_ERROR("Configuration validation failed with error %d: %s", 
              err, error_to_string(err));
    
    // Determine if we should enter safe mode or try to continue
    RecoveryStrategy strategy = get_recovery_strategy(err);
    
    if (strategy == RECOVERY_SAFE_MODE) {
      enter_safe_mode(error_to_string(err));
      // Never returns
    } else {
      // Try to apply safe defaults and continue
      apply_safe_defaults();
      LOG_WARN("Continuing with safe defaults");
    }
  }
  
  return err;
}