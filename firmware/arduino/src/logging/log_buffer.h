#pragma once

#include "logger.h"
#include <freertos/FreeRTOS.h>
#include <freertos/semphr.h>

class LogBuffer {
public:
    static constexpr size_t BUFFER_SIZE = 64;  // Reduced from 256 to fit in RTC memory
    
    static LogBuffer* getInstance();
    
    void begin();
    void end();
    
    bool push(const LogEntry& entry);
    
    bool pop(LogEntry& entry);
    
    bool getEntry(size_t index, LogEntry& entry) const;
    
    size_t getCount() const;
    
    bool isFull() const;
    bool isEmpty() const;
    
    void clear();
    
    size_t getCapacity() const { return BUFFER_SIZE; }
    
    uint32_t getOverflowCount() const { return overflow_count_; }
    void resetOverflowCount() { overflow_count_ = 0; }
    
    void dump(void (*output_fn)(const LogEntry&));
    
private:
    LogBuffer() = default;
    ~LogBuffer() = default;
    LogBuffer(const LogBuffer&) = delete;
    LogBuffer& operator=(const LogBuffer&) = delete;
    
    RTC_DATA_ATTR static LogEntry buffer_[BUFFER_SIZE];
    RTC_DATA_ATTR static size_t head_;
    RTC_DATA_ATTR static size_t tail_;
    RTC_DATA_ATTR static size_t count_;
    RTC_DATA_ATTR static uint32_t overflow_count_;
    RTC_DATA_ATTR static bool wrapped_;
    
    mutable SemaphoreHandle_t mutex_ = nullptr;
    bool initialized_ = false;
    
    bool pushUnsafe(const LogEntry& entry);
    bool popUnsafe(LogEntry& entry);
};