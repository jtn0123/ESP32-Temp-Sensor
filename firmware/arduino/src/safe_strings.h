// Safe string operations for ESP32 Temperature Sensor
#pragma once

#include <cstdio>
#include <cstring>
#include <cstdarg>
#include "logging.h"

// Compile-time size checking wrapper for char arrays
template<size_t N>
inline int safe_snprintf(char (&buffer)[N], const char* format, ...) {
  va_list args;
  va_start(args, format);
  int ret = vsnprintf(buffer, N, format, args);
  va_end(args);
  
  if (ret < 0) {
    LOG_ERROR("snprintf error in buffer[%d]", N);
    buffer[0] = '\0';
    return -1;
  }
  
  if (ret >= static_cast<int>(N)) {
    LOG_WARN("Buffer truncation: needed %d bytes, had %d", ret + 1, N);
  }
  
  return ret;
}

// Runtime checked version for dynamic buffers
inline int safe_snprintf_rt(char* buffer, size_t size, const char* format, ...) {
  if (!buffer || size == 0) {
    LOG_ERROR("Invalid buffer in safe_snprintf_rt");
    return -1;
  }
  
  va_list args;
  va_start(args, format);
  int ret = vsnprintf(buffer, size, format, args);
  va_end(args);
  
  if (ret < 0) {
    LOG_ERROR("vsnprintf error");
    buffer[0] = '\0';
    return -1;
  }
  
  if (ret >= static_cast<int>(size)) {
    LOG_WARN("Buffer truncation: needed %d bytes, had %zu", ret + 1, size);
  }
  
  return ret;
}

// Safe string copy with truncation warning for arrays
template<size_t N>
inline void safe_strcpy(char (&dest)[N], const char* src) {
  if (!src) {
    dest[0] = '\0';
    return;
  }
  
  size_t len = strlen(src);
  if (len >= N) {
    LOG_WARN("String truncation in strcpy: %zu chars -> %zu chars", len, N-1);
    strncpy(dest, src, N-1);
    dest[N-1] = '\0';
  } else {
    strcpy(dest, src);
  }
}

// Runtime version for dynamic buffers
inline void safe_strcpy_rt(char* dest, size_t dest_size, const char* src) {
  if (!dest || dest_size == 0) {
    LOG_ERROR("Invalid destination in safe_strcpy_rt");
    return;
  }
  
  if (!src) {
    dest[0] = '\0';
    return;
  }
  
  size_t len = strlen(src);
  if (len >= dest_size) {
    LOG_WARN("String truncation in strcpy: %zu chars -> %zu chars", len, dest_size-1);
    strncpy(dest, src, dest_size-1);
    dest[dest_size-1] = '\0';
  } else {
    strcpy(dest, src);
  }
}

// Safe string concatenation with truncation warning
template<size_t N>
inline void safe_strcat(char (&dest)[N], const char* src) {
  if (!src) return;
  
  size_t dest_len = strlen(dest);
  size_t src_len = strlen(src);
  
  if (dest_len + src_len >= N) {
    LOG_WARN("String truncation in strcat: %zu chars available", N - dest_len - 1);
    size_t copy_len = N - dest_len - 1;
    if (copy_len > 0) {
      strncat(dest, src, copy_len);
      dest[N-1] = '\0';
    }
  } else {
    strcat(dest, src);
  }
}

// Safe string append with format
template<size_t N>
inline int safe_append_format(char (&buffer)[N], const char* format, ...) {
  size_t current_len = strlen(buffer);
  if (current_len >= N - 1) {
    LOG_WARN("Buffer already full, cannot append");
    return -1;
  }
  
  size_t remaining = N - current_len;
  
  va_list args;
  va_start(args, format);
  int ret = vsnprintf(buffer + current_len, remaining, format, args);
  va_end(args);
  
  if (ret >= static_cast<int>(remaining)) {
    LOG_WARN("Append truncation: needed %d bytes, had %zu", ret + 1, remaining);
  }
  
  return ret;
}

// Bounds-checked character search
template<size_t N>
inline char* safe_strchr(char (&str)[N], int c) {
  // Search for character within bounds, stopping at null or buffer end
  for (size_t i = 0; i < N; ++i) {
    if (str[i] == '\0') {
      return nullptr;  // End of string, character not found
    }
    if (str[i] == static_cast<char>(c)) {
      return &str[i];  // Found character
    }
  }
  // Buffer not null-terminated within bounds - this is a usage error
  // Force null-terminate and return nullptr for safety
  str[N-1] = '\0';
  LOG_WARN("safe_strchr: buffer not null-terminated");
  return nullptr;
}

// Safe integer to string conversion
template<size_t N>
inline void safe_itoa(int value, char (&buffer)[N], int base = 10) {
  if (base < 2 || base > 36) {
    LOG_ERROR("Invalid base %d for itoa", base);
    buffer[0] = '\0';
    return;
  }
  
  // Use snprintf for safety
  int ret = snprintf(buffer, N, "%d", value);
  if (ret >= static_cast<int>(N)) {
    LOG_WARN("Integer string truncated");
  }
}

// Safe float to string conversion with precision
template<size_t N>
inline void safe_ftoa(float value, char (&buffer)[N], int precision = 2) {
  if (precision < 0 || precision > 10) {
    LOG_ERROR("Invalid precision %d for ftoa", precision);
    buffer[0] = '\0';
    return;
  }
  
  char format[16];
  snprintf(format, sizeof(format), "%%.%df", precision);
  
  int ret = snprintf(buffer, N, format, value);
  if (ret >= static_cast<int>(N)) {
    LOG_WARN("Float string truncated");
  }
}

// Helper to ensure null termination
template<size_t N>
inline void ensure_null_terminated(char (&buffer)[N]) {
  buffer[N-1] = '\0';
}

// Macro for migrating existing snprintf calls easily
#define SAFE_SNPRINTF(buffer, ...) safe_snprintf(buffer, __VA_ARGS__)

// Runtime version when size is dynamic
#define SAFE_SNPRINTF_RT(buffer, size, ...) safe_snprintf_rt(buffer, size, __VA_ARGS__)

// Example usage in migration:
// Before: snprintf(topic, sizeof(topic), "%s/temperature", base);
// After:  safe_snprintf(topic, "%s/temperature", base);
//    or:  SAFE_SNPRINTF(topic, "%s/temperature", base);

// Buffer size constants for common uses
#define MQTT_TOPIC_SIZE 128
#define MQTT_PAYLOAD_SIZE 256
#define IP_STRING_SIZE 16
#define TIME_STRING_SIZE 32
#define SENSOR_STRING_SIZE 16
#define STATUS_STRING_SIZE 64

// Pre-sized buffer types for common uses
typedef char mqtt_topic_t[MQTT_TOPIC_SIZE];
typedef char mqtt_payload_t[MQTT_PAYLOAD_SIZE];
typedef char ip_string_t[IP_STRING_SIZE];
typedef char time_string_t[TIME_STRING_SIZE];
typedef char sensor_string_t[SENSOR_STRING_SIZE];
typedef char status_string_t[STATUS_STRING_SIZE];

// Validation helper
inline bool is_valid_string(const char* str, size_t max_len) {
  if (!str) return false;
  
  size_t len = 0;
  while (len < max_len && str[len] != '\0') {
    len++;
  }
  
  if (len == max_len) {
    LOG_WARN("String not null-terminated within %zu bytes", max_len);
    return false;
  }
  
  return true;
}