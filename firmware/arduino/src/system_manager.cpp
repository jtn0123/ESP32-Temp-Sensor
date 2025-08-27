// System management implementation - extracted from main.cpp
#include "system_manager.h"
#include <esp_heap_caps.h>
#include <esp_sleep.h>
#include "config.h"
#include "generated_config.h"

// RTC memory for persisting data across deep sleep
RTC_DATA_ATTR static uint32_t rtc_wake_count = 0;

// Global preferences object for NVS cache
static Preferences g_prefs;

// Display deadline for timing
static uint32_t g_display_deadline_ms = 0;

// Get current wake count
uint32_t get_wake_count() {
    return rtc_wake_count;
}

// Increment wake count
void increment_wake_count() {
    rtc_wake_count++;
}

void reset_wake_count() {
    rtc_wake_count = 0;
}

// Get memory diagnostics
MemoryDiagnostics get_memory_diagnostics() {
    MemoryDiagnostics diag;
    diag.free_heap = esp_get_free_heap_size();
    diag.min_free_heap = esp_get_minimum_free_heap_size();
    diag.largest_free_block = heap_caps_get_largest_free_block(MALLOC_CAP_DEFAULT);
    
    // Calculate fragmentation percentage
    if (diag.free_heap > 0 && diag.largest_free_block > 0) {
        diag.fragmentation_pct = ((float)(diag.free_heap - diag.largest_free_block) / 
                                  (float)diag.free_heap) * 100.0f;
    } else {
        diag.fragmentation_pct = 0.0f;
    }
    
    #ifdef CONFIG_SPIRAM
    diag.psram_free = heap_caps_get_free_size(MALLOC_CAP_SPIRAM);
    diag.psram_size = heap_caps_get_total_size(MALLOC_CAP_SPIRAM);
    #else
    diag.psram_free = 0;
    diag.psram_size = 0;
    #endif
    return diag;
}

// Print boot diagnostics
void print_boot_diagnostics() {
    Serial.println(F("\n=== Boot Diagnostics ==="));
    
    // Reset reason
    esp_reset_reason_t reset_reason = esp_reset_reason();
    Serial.print(F("Reset reason: "));
    Serial.println(get_reset_reason_string(reset_reason));
    
    // Memory stats
    MemoryDiagnostics mem = get_memory_diagnostics();
    Serial.printf("Heap: free=%u min=%u\n", mem.free_heap, mem.min_free_heap);
    
    // Wake count
    Serial.printf("Wake count: %u\n", rtc_wake_count);
    
    Serial.println(F("========================"));
}

// Get reset reason as string
const char* get_reset_reason_string(esp_reset_reason_t reason) {
    switch (reason) {
        case ESP_RST_UNKNOWN: return "UNKNOWN";
        case ESP_RST_POWERON: return "POWERON";
        case ESP_RST_EXT: return "EXTERNAL";
        case ESP_RST_SW: return "SOFTWARE";
        case ESP_RST_PANIC: return "PANIC";
        case ESP_RST_INT_WDT: return "INT_WATCHDOG";
        case ESP_RST_TASK_WDT: return "TASK_WATCHDOG";
        case ESP_RST_WDT: return "WATCHDOG";
        case ESP_RST_DEEPSLEEP: return "DEEPSLEEP";
        case ESP_RST_BROWNOUT: return "BROWNOUT";
        case ESP_RST_SDIO: return "SDIO";
        default: return "UNKNOWN";
    }
}

// Check if reset reason indicates a crash
bool reset_reason_is_crash(esp_reset_reason_t reason) {
    return (reason == ESP_RST_PANIC || 
            reason == ESP_RST_INT_WDT || 
            reason == ESP_RST_TASK_WDT || 
            reason == ESP_RST_WDT || 
            reason == ESP_RST_BROWNOUT);
}

// Go to deep sleep with wake tracking
void go_deep_sleep_with_tracking(uint32_t seconds) {
    Serial.printf("Entering deep sleep for %u seconds\n", seconds);
    Serial.flush();
    
    // Configure wake timer
    esp_sleep_enable_timer_wakeup(seconds * 1000000ULL);
    
    // Increment wake count for next boot
    rtc_wake_count++;
    
    // Enter deep sleep
    esp_deep_sleep_start();
}

// NVS cache operations
void nvs_begin_cache() {
    g_prefs.begin("cache", false);
}

void nvs_end_cache() {
    g_prefs.end();
}

void nvs_store_float(const char* key, float value) {
    g_prefs.putFloat(key, value);
}

void nvs_store_uint(const char* key, uint32_t value) {
    g_prefs.putUInt(key, value);
}

void nvs_store_ushort(const char* key, uint16_t value) {
    g_prefs.putUShort(key, value);
}

void nvs_store_uchar(const char* key, uint8_t value) {
    g_prefs.putUChar(key, value);
}

float nvs_load_float(const char* key, float defaultValue) {
    return g_prefs.getFloat(key, defaultValue);
}

uint32_t nvs_load_uint(const char* key, uint32_t defaultValue) {
    return g_prefs.getUInt(key, defaultValue);
}

uint16_t nvs_load_ushort(const char* key, uint16_t defaultValue) {
    return g_prefs.getUShort(key, defaultValue);
}

uint8_t nvs_load_uchar(const char* key, uint8_t defaultValue) {
    return g_prefs.getUChar(key, defaultValue);
}

// Get/set display deadline
uint32_t get_display_deadline_ms() {
    return g_display_deadline_ms;
}

void set_display_deadline_ms(uint32_t deadline) {
    g_display_deadline_ms = deadline;
}

// Print memory statistics
void print_memory_stats() {
    MemoryDiagnostics mem = get_memory_diagnostics();
    Serial.printf("Free heap: %u bytes\n", mem.free_heap);
    Serial.printf("Min free heap: %u bytes\n", mem.min_free_heap);
    Serial.printf("Largest free block: %u bytes\n", mem.largest_free_block);
    Serial.printf("Fragmentation: %.1f%%\n", mem.fragmentation_pct);
    if (mem.psram_size > 0) {
        Serial.printf("PSRAM free: %u/%u bytes\n", mem.psram_free, mem.psram_size);
    }
}

// Load cache values if unset (moved from main.cpp)

// Handle serial command line (will be moved from main.cpp)
void handle_serial_command_line(const String& line) {
    // This will be filled in when we move the actual implementation
    // For now, just a placeholder
    Serial.println(F("Command handling not yet implemented in system_manager"));
}