// Test harness for the comprehensive logging system
#include <Arduino.h>
#include "config.h"

#ifdef LOG_ENABLED
#include "logging/logger.h"
#include "logging/log_buffer.h"
#include "logging/log_storage.h"
#include "logging/log_mqtt.h"

LOG_MODULE("TEST");

void test_logging_system() {
    Serial.println("\n=== LOGGING SYSTEM TEST ===\n");
    
    // Initialize logger with test configuration
    Logger::Config config;
    config.min_level = LogLevel::TRACE;
    config.serial_enabled = true;
    config.buffer_enabled = true;
    config.nvs_enabled = true;
    config.mqtt_enabled = false;  // Start with MQTT disabled
    
    Logger& logger = Logger::getInstance();
    logger.begin(config);
    
    // Test 1: Basic logging at different levels
    Serial.println("TEST 1: Log levels");
    LOG_TRACE("This is a trace message: %d", 123);
    LOG_DEBUG("This is a debug message: %s", "test");
    LOG_INFO("This is an info message: %.2f", 3.14);
    LOG_WARN("This is a warning message");
    LOG_ERROR("This is an error message: code=%d", 404);
    
    // Test 2: Module registration
    Serial.println("\nTEST 2: Module registration");
    uint8_t net_module = logger.registerModule("NETWORK");
    uint8_t sensor_module = logger.registerModule("SENSOR");
    logger.info(net_module, "Network module initialized");
    logger.info(sensor_module, "Sensor module initialized");
    
    // Test 3: Circular buffer
    Serial.println("\nTEST 3: Circular buffer");
    LogBuffer* buffer = LogBuffer::getInstance();
    Serial.printf("Buffer capacity: %zu\n", buffer->getCapacity());
    Serial.printf("Buffer count: %zu\n", buffer->getCount());
    
    // Fill buffer with test entries
    for (int i = 0; i < 10; i++) {
        LOG_INFO("Test buffer entry %d", i);
    }
    
    Serial.printf("Buffer count after fills: %zu\n", buffer->getCount());
    
    // Test 4: NVS storage
    Serial.println("\nTEST 4: NVS storage");
    LogStorage* storage = LogStorage::getInstance();
    
    // Store some error entries
    LOG_ERROR("Test error 1 for NVS");
    LOG_ERROR("Test error 2 for NVS");
    LOG_FATAL("Test fatal error for NVS");
    
    delay(100);  // Allow storage to process
    
    Serial.printf("Stored entries: %zu\n", storage->getStoredCount());
    
    // Test 5: Dump crash log
    Serial.println("\nTEST 5: Crash log dump");
    logger.dumpCrashLog();
    
    // Test 6: Memory diagnostics with logging
    Serial.println("\nTEST 6: Memory diagnostics");
    uint32_t free_heap = esp_get_free_heap_size();
    uint32_t min_heap = esp_get_minimum_free_heap_size();
    LOG_INFO("Memory stats - free: %u, min: %u", free_heap, min_heap);
    
    // Test 7: Level filtering
    Serial.println("\nTEST 7: Level filtering");
    logger.setLevel(LogLevel::WARN);
    LOG_DEBUG("This debug should NOT appear");
    LOG_INFO("This info should NOT appear");
    LOG_WARN("This warning SHOULD appear");
    LOG_ERROR("This error SHOULD appear");
    
    // Reset to INFO level
    logger.setLevel(LogLevel::INFO);
    
    // Test 8: Buffer overflow handling
    Serial.println("\nTEST 8: Buffer overflow");
    for (int i = 0; i < 300; i++) {  // Exceeds buffer size of 256
        LOG_INFO("Overflow test %d", i);
    }
    
    Serial.printf("Buffer overflow count: %u\n", buffer->getOverflowCount());
    
    // Test 9: Clear functions
    Serial.println("\nTEST 9: Clear functions");
    logger.clearCrashLog();
    buffer->clear();
    storage->clearLogs();
    
    Serial.printf("Buffer count after clear: %zu\n", buffer->getCount());
    Serial.printf("Storage count after clear: %zu\n", storage->getStoredCount());
    
    // Test 10: MQTT log forwarding (if connected)
    #ifdef LOG_MQTT_ENABLED
    Serial.println("\nTEST 10: MQTT logging (enable when connected)");
    logger.enableMQTT(true);
    LogMQTT* mqtt_logger = LogMQTT::getInstance();
    mqtt_logger->setClientId("test_device");
    LOG_INFO("Test MQTT log message");
    LOG_ERROR("Test MQTT error message");
    Serial.printf("MQTT queued: %zu\n", mqtt_logger->getQueuedCount());
    #endif
    
    // Final summary
    Serial.println("\n=== TEST COMPLETE ===");
    Serial.printf("Total logs dropped: %u\n", logger.getDroppedCount());
    Serial.printf("Final buffer count: %zu\n", buffer->getCount());
    Serial.printf("Final storage count: %zu\n", storage->getStoredCount());
    
    logger.flush();
}

#else
void test_logging_system() {
    Serial.println("Logging system disabled in config.h");
}
#endif