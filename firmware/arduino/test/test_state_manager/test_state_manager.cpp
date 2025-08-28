// Unit tests for state_manager module
#include <unity.h>
#include <Arduino.h>

// Mock the display and other dependencies
#define USE_DISPLAY 0

// Include the module under test
#include "../../src/state_manager.h"

// Test wake count operations
void test_wake_count_increment() {
    // Reset wake count
    reset_wake_count();
    TEST_ASSERT_EQUAL_UINT32(0, get_wake_count());
    
    // Increment and verify
    increment_wake_count();
    TEST_ASSERT_EQUAL_UINT32(1, get_wake_count());
    
    // Multiple increments
    increment_wake_count();
    increment_wake_count();
    TEST_ASSERT_EQUAL_UINT32(3, get_wake_count());
}

void test_wake_count_reset() {
    // Set to non-zero
    increment_wake_count();
    increment_wake_count();
    TEST_ASSERT_GREATER_THAN(0, get_wake_count());
    
    // Reset and verify
    reset_wake_count();
    TEST_ASSERT_EQUAL_UINT32(0, get_wake_count());
}

// Test partial counter operations
void test_partial_counter_operations() {
    // Reset counter
    reset_partial_counter();
    TEST_ASSERT_EQUAL_UINT16(0, get_partial_counter());
    
    // Increment
    increment_partial_counter();
    TEST_ASSERT_EQUAL_UINT16(1, get_partial_counter());
    
    // Set specific value
    set_partial_counter(10);
    TEST_ASSERT_EQUAL_UINT16(10, get_partial_counter());
}

// Test temperature state
void test_temperature_state() {
    // Initial state should be NAN
    TEST_ASSERT_TRUE(isnan(get_last_inside_temp_f()));
    TEST_ASSERT_TRUE(isnan(get_last_outside_temp_f()));
    
    // Set values
    set_last_inside_temp_f(72.5f);
    set_last_outside_temp_f(65.3f);
    
    // Verify
    TEST_ASSERT_FLOAT_WITHIN(0.01f, 72.5f, get_last_inside_temp_f());
    TEST_ASSERT_FLOAT_WITHIN(0.01f, 65.3f, get_last_outside_temp_f());
}

// Test humidity state
void test_humidity_state() {
    // Initial state
    TEST_ASSERT_TRUE(isnan(get_last_inside_rh()));
    TEST_ASSERT_TRUE(isnan(get_last_outside_rh()));
    
    // Set values
    set_last_inside_rh(45);
    set_last_outside_rh(80);
    
    // Verify
    TEST_ASSERT_EQUAL_INT16(45, get_last_inside_rh());
    TEST_ASSERT_EQUAL_INT16(80, get_last_outside_rh());
}

// Test pressure state
void test_pressure_state() {
    // Initial state
    TEST_ASSERT_TRUE(isnan(get_last_pressure()));
    
    // Set value
    set_last_pressure(1013.25f);
    
    // Verify
    TEST_ASSERT_FLOAT_WITHIN(0.01f, 1013.25f, get_last_pressure());
}

// Test battery state
void test_battery_state() {
    // Initial state
    TEST_ASSERT_EQUAL_INT8(-1, get_last_battery_pct());
    
    // Set value
    set_last_battery_pct(75);
    
    // Verify
    TEST_ASSERT_EQUAL_INT8(75, get_last_battery_pct());
    
    // Test boundary values
    set_last_battery_pct(0);
    TEST_ASSERT_EQUAL_INT8(0, get_last_battery_pct());
    
    set_last_battery_pct(100);
    TEST_ASSERT_EQUAL_INT8(100, get_last_battery_pct());
}

// Test weather state
void test_weather_state() {
    // Get initial CRC (should be 0 or consistent)
    uint32_t initial_crc = get_last_weather_crc();
    
    // Set a new CRC
    set_last_weather_crc(0x12345678);
    TEST_ASSERT_EQUAL_UINT32(0x12345678, get_last_weather_crc());
    
    // Test status CRC
    set_last_status_crc(0xABCDEF01);
    TEST_ASSERT_EQUAL_UINT32(0xABCDEF01, get_last_status_crc());
}

// Test display mode flags
void test_display_mode_flags() {
    // Test full-only mode
    set_full_only_mode(true);
    TEST_ASSERT_TRUE(get_full_only_mode());
    
    set_full_only_mode(false);
    TEST_ASSERT_FALSE(get_full_only_mode());
    
    // Test has changed flag
    set_has_changed(true);
    TEST_ASSERT_TRUE(get_has_changed());
    
    set_has_changed(false);
    TEST_ASSERT_FALSE(get_has_changed());
}

// Test wake timing
void test_wake_timing() {
    // Set wake time
    set_wake_time_ms(1000);
    TEST_ASSERT_EQUAL_UINT32(1000, get_wake_time_ms());
    
    set_wake_time_ms(5000);
    TEST_ASSERT_EQUAL_UINT32(5000, get_wake_time_ms());
}

// Main test runner
void setup() {
    UNITY_BEGIN();
    
    // Run all tests
    RUN_TEST(test_wake_count_increment);
    RUN_TEST(test_wake_count_reset);
    RUN_TEST(test_partial_counter_operations);
    RUN_TEST(test_temperature_state);
    RUN_TEST(test_humidity_state);
    RUN_TEST(test_pressure_state);
    RUN_TEST(test_battery_state);
    RUN_TEST(test_weather_state);
    RUN_TEST(test_display_mode_flags);
    RUN_TEST(test_wake_timing);
    
    UNITY_END();
}

void loop() {
    // Empty loop
}