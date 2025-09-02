// Structured error handling for ESP32 Temperature Sensor
#pragma once

#include "logging.h"
#include <Arduino.h>

// Error code definitions
enum ErrorCode {
  // Success
  ERR_NONE = 0,
  
  // WiFi errors (100-199)
  ERR_WIFI_CONNECT_FAILED = 100,
  ERR_WIFI_TIMEOUT = 101,
  ERR_WIFI_INVALID_SSID = 102,
  ERR_WIFI_INVALID_PASSWORD = 103,
  ERR_WIFI_NO_AP_FOUND = 104,
  ERR_WIFI_DISCONNECTED = 105,
  
  // MQTT errors (200-299)
  ERR_MQTT_CONNECT_FAILED = 200,
  ERR_MQTT_PUBLISH_FAILED = 201,
  ERR_MQTT_SUBSCRIBE_FAILED = 202,
  ERR_MQTT_BUFFER_OVERFLOW = 203,
  ERR_MQTT_INVALID_TOPIC = 204,
  ERR_MQTT_TIMEOUT = 205,
  
  // Sensor errors (300-399)
  ERR_SENSOR_INIT_FAILED = 300,
  ERR_SENSOR_READ_FAILED = 301,
  ERR_SENSOR_NOT_FOUND = 302,
  ERR_SENSOR_INVALID_DATA = 303,
  ERR_SENSOR_TIMEOUT = 304,
  
  // Battery/Power errors (400-499)
  ERR_BATTERY_GAUGE_FAILED = 400,
  ERR_BATTERY_LOW = 401,
  ERR_POWER_RAIL_FAILED = 402,
  ERR_BATTERY_CRITICAL = 403,
  
  // Configuration errors (500-599)
  ERR_CONFIG_INVALID = 500,
  ERR_CONFIG_MISSING = 501,
  ERR_CONFIG_PARSE_FAILED = 502,
  ERR_CONFIG_OUT_OF_RANGE = 503,
  
  // Memory errors (600-699)
  ERR_MEMORY_LOW = 600,
  ERR_MEMORY_ALLOCATION_FAILED = 601,
  ERR_HEAP_FRAGMENTED = 602,
  ERR_STACK_OVERFLOW = 603,
  
  // Display errors (700-799)
  ERR_DISPLAY_INIT_FAILED = 700,
  ERR_DISPLAY_UPDATE_FAILED = 701,
  ERR_DISPLAY_BUSY_TIMEOUT = 702,
  
  // System errors (800-899)
  ERR_NVS_INIT_FAILED = 800,
  ERR_NVS_READ_FAILED = 801,
  ERR_NVS_WRITE_FAILED = 802,
  ERR_RTC_INIT_FAILED = 803,
  ERR_WATCHDOG_TIMEOUT = 804,
  
  // Generic errors (900-999)
  ERR_UNKNOWN = 900,
  ERR_NOT_IMPLEMENTED = 901,
  ERR_INVALID_PARAMETER = 902,
  ERR_OPERATION_FAILED = 903
};

// Error context for tracking where errors occurred
struct ErrorContext {
  ErrorCode code;
  const char* function;
  const char* file;
  int line;
  uint32_t timestamp;
  uint32_t free_heap;
};

// Global error tracking
extern ErrorContext g_last_error;
extern uint32_t g_error_count;

// Error handling macros
#define SET_ERROR(code) do { \
  g_last_error.code = (code); \
  g_last_error.function = __FUNCTION__; \
  g_last_error.file = __FILE__; \
  g_last_error.line = __LINE__; \
  g_last_error.timestamp = millis(); \
  g_last_error.free_heap = ESP.getFreeHeap(); \
  g_error_count++; \
  LOG_ERROR("Error %d: %s at %s:%d (heap=%d)", \
            (code), error_to_string(code), __FUNCTION__, __LINE__, \
            g_last_error.free_heap); \
} while(0)

#define RETURN_ERROR(code) do { \
  SET_ERROR(code); \
  return (code); \
} while(0)

#define CHECK_ERROR(expr) do { \
  ErrorCode _err = (expr); \
  if (_err != ERR_NONE) { \
    SET_ERROR(_err); \
    return _err; \
  } \
} while(0)

#define LOG_AND_RETURN_ERROR(code, fmt, ...) do { \
  LOG_ERROR(fmt, ##__VA_ARGS__); \
  RETURN_ERROR(code); \
} while(0)

// Convert error code to string
inline const char* error_to_string(ErrorCode code) {
  switch(code) {
    case ERR_NONE: return "Success";
    
    // WiFi errors
    case ERR_WIFI_CONNECT_FAILED: return "WiFi connection failed";
    case ERR_WIFI_TIMEOUT: return "WiFi timeout";
    case ERR_WIFI_INVALID_SSID: return "Invalid WiFi SSID";
    case ERR_WIFI_INVALID_PASSWORD: return "Invalid WiFi password";
    case ERR_WIFI_NO_AP_FOUND: return "No WiFi AP found";
    case ERR_WIFI_DISCONNECTED: return "WiFi disconnected";
    
    // MQTT errors
    case ERR_MQTT_CONNECT_FAILED: return "MQTT connection failed";
    case ERR_MQTT_PUBLISH_FAILED: return "MQTT publish failed";
    case ERR_MQTT_SUBSCRIBE_FAILED: return "MQTT subscribe failed";
    case ERR_MQTT_BUFFER_OVERFLOW: return "MQTT buffer overflow";
    case ERR_MQTT_INVALID_TOPIC: return "Invalid MQTT topic";
    case ERR_MQTT_TIMEOUT: return "MQTT timeout";
    
    // Sensor errors
    case ERR_SENSOR_INIT_FAILED: return "Sensor init failed";
    case ERR_SENSOR_READ_FAILED: return "Sensor read failed";
    case ERR_SENSOR_NOT_FOUND: return "Sensor not found";
    case ERR_SENSOR_INVALID_DATA: return "Invalid sensor data";
    case ERR_SENSOR_TIMEOUT: return "Sensor timeout";
    
    // Battery errors
    case ERR_BATTERY_GAUGE_FAILED: return "Battery gauge failed";
    case ERR_BATTERY_LOW: return "Battery low";
    case ERR_POWER_RAIL_FAILED: return "Power rail failed";
    case ERR_BATTERY_CRITICAL: return "Battery critical";
    
    // Config errors
    case ERR_CONFIG_INVALID: return "Invalid configuration";
    case ERR_CONFIG_MISSING: return "Missing configuration";
    case ERR_CONFIG_PARSE_FAILED: return "Config parse failed";
    case ERR_CONFIG_OUT_OF_RANGE: return "Config value out of range";
    
    // Memory errors
    case ERR_MEMORY_LOW: return "Memory low";
    case ERR_MEMORY_ALLOCATION_FAILED: return "Memory allocation failed";
    case ERR_HEAP_FRAGMENTED: return "Heap fragmented";
    case ERR_STACK_OVERFLOW: return "Stack overflow";
    
    // Display errors
    case ERR_DISPLAY_INIT_FAILED: return "Display init failed";
    case ERR_DISPLAY_UPDATE_FAILED: return "Display update failed";
    case ERR_DISPLAY_BUSY_TIMEOUT: return "Display busy timeout";
    
    // System errors
    case ERR_NVS_INIT_FAILED: return "NVS init failed";
    case ERR_NVS_READ_FAILED: return "NVS read failed";
    case ERR_NVS_WRITE_FAILED: return "NVS write failed";
    case ERR_RTC_INIT_FAILED: return "RTC init failed";
    case ERR_WATCHDOG_TIMEOUT: return "Watchdog timeout";
    
    // Generic errors
    case ERR_UNKNOWN: return "Unknown error";
    case ERR_NOT_IMPLEMENTED: return "Not implemented";
    case ERR_INVALID_PARAMETER: return "Invalid parameter";
    case ERR_OPERATION_FAILED: return "Operation failed";
    
    default: return "Undefined error";
  }
}

// Error recovery strategies
enum RecoveryStrategy {
  RECOVERY_NONE,        // No recovery, continue
  RECOVERY_RETRY,       // Retry the operation
  RECOVERY_RESET,       // Reset the module/subsystem
  RECOVERY_REBOOT,      // Reboot the device
  RECOVERY_SAFE_MODE    // Enter safe mode
};

// Get recommended recovery strategy for an error
inline RecoveryStrategy get_recovery_strategy(ErrorCode code) {
  switch(code) {
    // Retry for transient errors
    case ERR_WIFI_TIMEOUT:
    case ERR_MQTT_TIMEOUT:
    case ERR_SENSOR_TIMEOUT:
      return RECOVERY_RETRY;
    
    // Reset for connection failures
    case ERR_WIFI_CONNECT_FAILED:
    case ERR_MQTT_CONNECT_FAILED:
      return RECOVERY_RESET;
    
    // Reboot for critical errors
    case ERR_MEMORY_LOW:
    case ERR_HEAP_FRAGMENTED:
    case ERR_STACK_OVERFLOW:
    case ERR_WATCHDOG_TIMEOUT:
      return RECOVERY_REBOOT;
    
    // Safe mode for config errors
    case ERR_CONFIG_INVALID:
    case ERR_CONFIG_MISSING:
    case ERR_CONFIG_OUT_OF_RANGE:
      return RECOVERY_SAFE_MODE;
    
    default:
      return RECOVERY_NONE;
  }
}

// Execute recovery action
inline void execute_recovery(RecoveryStrategy strategy) {
  switch(strategy) {
    case RECOVERY_RETRY:
      LOG_INFO("Recovery: Retrying operation");
      break;
      
    case RECOVERY_RESET:
      LOG_WARN("Recovery: Resetting module");
      // Module-specific reset code would go here
      break;
      
    case RECOVERY_REBOOT:
      LOG_ERROR("Recovery: Rebooting device");
      delay(1000);
      ESP.restart();
      break;
      
    case RECOVERY_SAFE_MODE:
      LOG_ERROR("Recovery: Entering safe mode");
      // Safe mode implementation would go here
      break;
      
    case RECOVERY_NONE:
    default:
      break;
  }
}

// Helper to check and handle errors with recovery
#define CHECK_AND_RECOVER(expr) do { \
  ErrorCode _err = (expr); \
  if (_err != ERR_NONE) { \
    SET_ERROR(_err); \
    RecoveryStrategy _strategy = get_recovery_strategy(_err); \
    if (_strategy != RECOVERY_NONE) { \
      execute_recovery(_strategy); \
    } \
    return _err; \
  } \
} while(0)