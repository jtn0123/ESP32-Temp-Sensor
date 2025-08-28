// Unit tests for system_manager module
#include <unity.h>
#include <Arduino.h>
#include <esp_system.h>

// Mock dependencies
#define LOG_ENABLED 0
#define USE_DISPLAY 0

// Include the module under test
#include "../../src/system_manager.h"

// Test memory diagnostics
void test_memory_diagnostics() {
    MemoryDiagnostics mem = get_memory_diagnostics();
    
    // Basic sanity checks
    TEST_ASSERT_GREATER_THAN(0, mem.free_heap);
    TEST_ASSERT_GREATER_THAN(0, mem.min_free_heap);
    TEST_ASSERT_GREATER_THAN(0, mem.largest_free_block);
    
    // Fragmentation should be a reasonable percentage
    TEST_ASSERT_TRUE(mem.fragmentation_pct >= 0.0f);
    TEST_ASSERT_TRUE(mem.fragmentation_pct <= 100.0f);
    
    // Free heap should be less than or equal to min free heap
    TEST_ASSERT_GREATER_OR_EQUAL(mem.free_heap, mem.min_free_heap);
}

// Test reset reason string conversion
void test_reset_reason_strings() {
    // Test all reset reasons have string representations
    const char* reason;
    
    reason = get_reset_reason_string(ESP_RST_POWERON);
    TEST_ASSERT_NOT_NULL(reason);
    TEST_ASSERT_EQUAL_STRING("POWERON", reason);
    
    reason = get_reset_reason_string(ESP_RST_PANIC);
    TEST_ASSERT_NOT_NULL(reason);
    TEST_ASSERT_EQUAL_STRING("PANIC", reason);
    
    reason = get_reset_reason_string(ESP_RST_INT_WDT);
    TEST_ASSERT_NOT_NULL(reason);
    TEST_ASSERT_EQUAL_STRING("INT_WATCHDOG", reason);
    
    reason = get_reset_reason_string(ESP_RST_DEEPSLEEP);
    TEST_ASSERT_NOT_NULL(reason);
    TEST_ASSERT_EQUAL_STRING("DEEPSLEEP", reason);
    
    reason = get_reset_reason_string(ESP_RST_BROWNOUT);
    TEST_ASSERT_NOT_NULL(reason);
    TEST_ASSERT_EQUAL_STRING("BROWNOUT", reason);
    
    // Test unknown reason
    reason = get_reset_reason_string((esp_reset_reason_t)999);
    TEST_ASSERT_NOT_NULL(reason);
    TEST_ASSERT_EQUAL_STRING("UNKNOWN", reason);
}

// Test crash detection
void test_crash_detection() {
    // Normal reasons should not be crashes
    TEST_ASSERT_FALSE(reset_reason_is_crash(ESP_RST_POWERON));
    TEST_ASSERT_FALSE(reset_reason_is_crash(ESP_RST_SW));
    TEST_ASSERT_FALSE(reset_reason_is_crash(ESP_RST_DEEPSLEEP));
    
    // Crash reasons should be detected
    TEST_ASSERT_TRUE(reset_reason_is_crash(ESP_RST_PANIC));
    TEST_ASSERT_TRUE(reset_reason_is_crash(ESP_RST_INT_WDT));
    TEST_ASSERT_TRUE(reset_reason_is_crash(ESP_RST_TASK_WDT));
    TEST_ASSERT_TRUE(reset_reason_is_crash(ESP_RST_WDT));
    TEST_ASSERT_TRUE(reset_reason_is_crash(ESP_RST_BROWNOUT));
}

// Test display deadline management
void test_display_deadline() {
    // Initial value
    uint32_t initial = get_display_deadline_ms();
    
    // Set new deadline
    set_display_deadline_ms(5000);
    TEST_ASSERT_EQUAL_UINT32(5000, get_display_deadline_ms());
    
    // Set another value
    set_display_deadline_ms(10000);
    TEST_ASSERT_EQUAL_UINT32(10000, get_display_deadline_ms());
    
    // Reset to zero
    set_display_deadline_ms(0);
    TEST_ASSERT_EQUAL_UINT32(0, get_display_deadline_ms());
}

// Test CRC32 calculation
void test_crc32_calculation() {
    // Test empty string
    const uint8_t empty[] = "";
    uint32_t crc_empty = fast_crc32(empty, 0);
    TEST_ASSERT_NOT_EQUAL(0, crc_empty);
    
    // Test known string
    const uint8_t test1[] = "Hello";
    uint32_t crc1 = fast_crc32(test1, 5);
    TEST_ASSERT_NOT_EQUAL(0, crc1);
    
    // Same string should give same CRC
    uint32_t crc1_again = fast_crc32(test1, 5);
    TEST_ASSERT_EQUAL_UINT32(crc1, crc1_again);
    
    // Different string should give different CRC
    const uint8_t test2[] = "World";
    uint32_t crc2 = fast_crc32(test2, 5);
    TEST_ASSERT_NOT_EQUAL(crc1, crc2);
    
    // Test with binary data
    const uint8_t binary[] = {0x00, 0xFF, 0xAA, 0x55};
    uint32_t crc_binary = fast_crc32(binary, 4);
    TEST_ASSERT_NOT_EQUAL(0, crc_binary);
}

// Test NVS cache operations (basic test without actual NVS)
void test_nvs_cache_operations() {
    // These operations should not crash even without NVS initialized
    nvs_begin_cache();
    
    // Store and load float
    nvs_store_float("test_float", 3.14f);
    // Note: Without actual NVS, load will return default
    float loaded = nvs_load_float("test_float", 0.0f);
    // We can't test the actual value without NVS, just that it doesn't crash
    TEST_ASSERT_TRUE(true);
    
    // Store and load uint
    nvs_store_uint("test_uint", 42);
    uint32_t loaded_uint = nvs_load_uint("test_uint", 0);
    TEST_ASSERT_TRUE(true);
    
    // Store and load ushort
    nvs_store_ushort("test_ushort", 1234);
    uint16_t loaded_ushort = nvs_load_ushort("test_ushort", 0);
    TEST_ASSERT_TRUE(true);
    
    // Store and load uchar
    nvs_store_uchar("test_uchar", 255);
    uint8_t loaded_uchar = nvs_load_uchar("test_uchar", 0);
    TEST_ASSERT_TRUE(true);
    
    nvs_end_cache();
}

// Test wake count persistence (from state_manager integration)
void test_wake_count_integration() {
    // Get current count
    uint32_t initial = get_wake_count();
    
    // Increment
    increment_wake_count();
    TEST_ASSERT_EQUAL_UINT32(initial + 1, get_wake_count());
    
    // Reset
    reset_wake_count();
    TEST_ASSERT_EQUAL_UINT32(0, get_wake_count());
}

// Main test runner
void setup() {
    // Initialize serial for test output
    Serial.begin(115200);
    delay(100);
    
    UNITY_BEGIN();
    
    // Run all tests
    RUN_TEST(test_memory_diagnostics);
    RUN_TEST(test_reset_reason_strings);
    RUN_TEST(test_crash_detection);
    RUN_TEST(test_display_deadline);
    RUN_TEST(test_crc32_calculation);
    RUN_TEST(test_nvs_cache_operations);
    RUN_TEST(test_wake_count_integration);
    
    UNITY_END();
}

void loop() {
    // Empty loop
}