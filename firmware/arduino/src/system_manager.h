#pragma once

// System management module - extracted from main.cpp
// Handles deep sleep, diagnostics, NVS cache, and system utilities

#include <Arduino.h>
#include <esp_system.h>
#include <Preferences.h>
#include "common_types.h"

// Memory diagnostics structure
struct MemoryDiagnostics {
    uint32_t free_heap;
    uint32_t min_free_heap;
    uint32_t largest_free_block;
    float fragmentation_pct;
    uint32_t psram_free;
    uint32_t psram_size;
};

// Deep sleep and wake management
void go_deep_sleep_with_tracking(uint32_t seconds);
uint32_t get_wake_count();
void increment_wake_count();
void reset_wake_count();

// System diagnostics
void print_boot_diagnostics();
MemoryDiagnostics get_memory_diagnostics();
const char* get_reset_reason_string(esp_reset_reason_t reason);
bool reset_reason_is_crash(esp_reset_reason_t reason);

// NVS cache operations
void nvs_begin_cache();
void nvs_end_cache();
void nvs_store_float(const char* key, float value);
void nvs_store_uint(const char* key, uint32_t value);
void nvs_store_ushort(const char* key, uint16_t value);
void nvs_store_uchar(const char* key, uint8_t value);
float nvs_load_float(const char* key, float defaultValue);
uint32_t nvs_load_uint(const char* key, uint32_t defaultValue);
uint16_t nvs_load_ushort(const char* key, uint16_t defaultValue);
uint8_t nvs_load_uchar(const char* key, uint8_t defaultValue);

// Serial command handling
void handle_serial_command_line(const String& line);

// System utilities
void print_memory_stats();
uint32_t get_display_deadline_ms();
void set_display_deadline_ms(uint32_t deadline);

// CRC and validation utilities
uint32_t fast_crc32(const uint8_t* data, size_t len);

// Helper templates for conditional redraws
template <typename DrawFn>
bool maybe_redraw_numeric(const int rect[4], float currentValue, float& lastValue,
                         float threshold, DrawFn drawFn);

template <typename T, typename DrawFn>
bool maybe_redraw_value(const int rect[4], const T& currentValue, T& lastValue,
                       DrawFn drawFn);