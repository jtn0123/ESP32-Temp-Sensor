#include "log_buffer.h"

RTC_DATA_ATTR LogEntry LogBuffer::buffer_[LogBuffer::BUFFER_SIZE];
RTC_DATA_ATTR size_t LogBuffer::head_ = 0;
RTC_DATA_ATTR size_t LogBuffer::tail_ = 0;
RTC_DATA_ATTR size_t LogBuffer::count_ = 0;
RTC_DATA_ATTR uint32_t LogBuffer::overflow_count_ = 0;
RTC_DATA_ATTR bool LogBuffer::wrapped_ = false;

LogBuffer* LogBuffer::getInstance() {
    static LogBuffer instance;
    return &instance;
}

void LogBuffer::begin() {
    if (initialized_) return;
    
    mutex_ = xSemaphoreCreateMutex();
    if (mutex_ == nullptr) {
        // Mutex creation failed - cannot proceed safely
        Serial.println("[LogBuffer] FATAL: Failed to create mutex");
        return;
    }
    
    if (!wrapped_) {
        head_ = 0;
        tail_ = 0;
        count_ = 0;
        overflow_count_ = 0;
    }
    
    initialized_ = true;
}

void LogBuffer::end() {
    if (!initialized_) return;
    
    if (mutex_) {
        vSemaphoreDelete(mutex_);
        mutex_ = nullptr;
    }
    
    initialized_ = false;
}

bool LogBuffer::push(const LogEntry& entry) {
    if (!initialized_ || mutex_ == nullptr) return false;
    
    if (xSemaphoreTake(mutex_, portMAX_DELAY) != pdTRUE) {
        return false;
    }
    
    bool result = pushUnsafe(entry);
    
    xSemaphoreGive(mutex_);
    
    return result;
}

bool LogBuffer::pushUnsafe(const LogEntry& entry) {
    buffer_[head_] = entry;
    
    head_ = (head_ + 1) % BUFFER_SIZE;
    
    if (count_ < BUFFER_SIZE) {
        count_++;
    } else {
        tail_ = (tail_ + 1) % BUFFER_SIZE;
        overflow_count_++;
        wrapped_ = true;
    }
    
    return true;
}

bool LogBuffer::pop(LogEntry& entry) {
    if (!initialized_ || mutex_ == nullptr) return false;
    
    if (xSemaphoreTake(mutex_, portMAX_DELAY) != pdTRUE) {
        return false;
    }
    
    // Check isEmpty inside mutex to avoid race condition
    if (count_ == 0) {
        xSemaphoreGive(mutex_);
        return false;
    }
    
    bool result = popUnsafe(entry);
    
    xSemaphoreGive(mutex_);
    
    return result;
}

bool LogBuffer::popUnsafe(LogEntry& entry) {
    if (count_ == 0) return false;
    
    entry = buffer_[tail_];
    tail_ = (tail_ + 1) % BUFFER_SIZE;
    count_--;
    
    return true;
}

bool LogBuffer::getEntry(size_t index, LogEntry& entry) const {
    if (!initialized_ || mutex_ == nullptr) return false;
    
    if (xSemaphoreTake(mutex_, portMAX_DELAY) != pdTRUE) {
        return false;
    }
    
    // Check index inside mutex to avoid race condition
    if (index >= count_) {
        xSemaphoreGive(mutex_);
        return false;
    }
    
    size_t actual_index = (tail_ + index) % BUFFER_SIZE;
    entry = buffer_[actual_index];
    
    xSemaphoreGive(mutex_);
    
    return true;
}

size_t LogBuffer::getCount() const {
    if (!initialized_ || mutex_ == nullptr) return 0;
    
    if (xSemaphoreTake(mutex_, portMAX_DELAY) != pdTRUE) {
        return 0;
    }
    size_t result = count_;
    xSemaphoreGive(mutex_);
    return result;
}

bool LogBuffer::isFull() const {
    if (!initialized_ || mutex_ == nullptr) return false;
    
    if (xSemaphoreTake(mutex_, portMAX_DELAY) != pdTRUE) {
        return false;
    }
    bool result = count_ >= BUFFER_SIZE;
    xSemaphoreGive(mutex_);
    return result;
}

bool LogBuffer::isEmpty() const {
    if (!initialized_ || mutex_ == nullptr) return true;
    
    if (xSemaphoreTake(mutex_, portMAX_DELAY) != pdTRUE) {
        return true;  // Fail-safe: assume empty if we can't get mutex
    }
    bool result = count_ == 0;
    xSemaphoreGive(mutex_);
    return result;
}

void LogBuffer::clear() {
    if (!initialized_ || mutex_ == nullptr) return;
    
    if (xSemaphoreTake(mutex_, portMAX_DELAY) != pdTRUE) {
        return;
    }
    
    head_ = 0;
    tail_ = 0;
    count_ = 0;
    overflow_count_ = 0;
    wrapped_ = false;
    memset(buffer_, 0, sizeof(buffer_));
    
    xSemaphoreGive(mutex_);
}

void LogBuffer::dump(void (*output_fn)(const LogEntry&)) {
    if (!initialized_ || mutex_ == nullptr || !output_fn) return;
    
    if (xSemaphoreTake(mutex_, portMAX_DELAY) != pdTRUE) {
        return;
    }
    
    for (size_t i = 0; i < count_; i++) {
        size_t index = (tail_ + i) % BUFFER_SIZE;
        output_fn(buffer_[index]);
    }
    
    xSemaphoreGive(mutex_);
}