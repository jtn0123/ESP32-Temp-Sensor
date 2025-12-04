#include "log_buffer.h"
#include "metrics_diagnostics.h"

RTC_DATA_ATTR LogEntry LogBuffer::buffer_[LogBuffer::BUFFER_SIZE];
RTC_DATA_ATTR size_t LogBuffer::head_ = 0;
RTC_DATA_ATTR size_t LogBuffer::tail_ = 0;
RTC_DATA_ATTR size_t LogBuffer::count_ = 0;
RTC_DATA_ATTR uint32_t LogBuffer::overflow_count_ = 0;
RTC_DATA_ATTR bool LogBuffer::wrapped_ = false;

// Guard against race condition in begin() - static ensures single initialization
static volatile bool s_begin_in_progress = false;

LogBuffer* LogBuffer::getInstance() {
    static LogBuffer instance;
    return &instance;
}

void LogBuffer::begin() {
    if (initialized_) return;
    
    // Simple race condition guard - not fully atomic but prevents most issues
    // In practice, begin() is only called from setup() which is single-threaded
    if (s_begin_in_progress) return;
    s_begin_in_progress = true;
    
    // Double-check after acquiring guard
    if (initialized_) {
        s_begin_in_progress = false;
        return;
    }
    
    mutex_ = xSemaphoreCreateMutex();
    if (mutex_ == nullptr) {
        // Mutex creation failed - cannot proceed safely
        Serial.println("[LogBuffer] FATAL: Failed to create mutex");
        s_begin_in_progress = false;
        return;
    }
    
    if (!wrapped_) {
        // First boot - initialize to clean state
        head_ = 0;
        tail_ = 0;
        count_ = 0;
        overflow_count_ = 0;
    } else {
        // Waking from deep sleep - validate RTC memory integrity
        // Check that indices are within bounds (could be corrupted)
        if (head_ >= BUFFER_SIZE || tail_ >= BUFFER_SIZE || count_ > BUFFER_SIZE) {
            Serial.println("[LogBuffer] WARN: RTC memory corruption detected, resetting");
            increment_error_stat("rtc_corruption");
            head_ = 0;
            tail_ = 0;
            count_ = 0;
            overflow_count_ = 0;
            wrapped_ = false;
        }
    }
    
    initialized_ = true;
    s_begin_in_progress = false;
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

    MutexGuard guard(mutex_);
    if (!guard.acquired()) return false;

    return pushUnsafe(entry);
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

    MutexGuard guard(mutex_);
    if (!guard.acquired()) return false;

    // Check isEmpty inside mutex to avoid race condition
    if (count_ == 0) {
        return false;
    }

    return popUnsafe(entry);
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

    MutexGuard guard(mutex_);
    if (!guard.acquired()) return false;

    // Check index inside mutex to avoid race condition
    if (index >= count_) {
        return false;
    }

    size_t actual_index = (tail_ + index) % BUFFER_SIZE;
    entry = buffer_[actual_index];

    return true;
}

size_t LogBuffer::getCount() const {
    if (!initialized_ || mutex_ == nullptr) return 0;

    MutexGuard guard(mutex_);
    if (!guard.acquired()) return 0;

    return count_;
}

bool LogBuffer::isFull() const {
    if (!initialized_ || mutex_ == nullptr) return false;

    MutexGuard guard(mutex_);
    if (!guard.acquired()) return false;

    return count_ >= BUFFER_SIZE;
}

bool LogBuffer::isEmpty() const {
    if (!initialized_ || mutex_ == nullptr) return true;

    MutexGuard guard(mutex_);
    if (!guard.acquired()) return true;  // Fail-safe: assume empty if we can't get mutex

    return count_ == 0;
}

void LogBuffer::clear() {
    if (!initialized_ || mutex_ == nullptr) return;

    MutexGuard guard(mutex_);
    if (!guard.acquired()) return;

    head_ = 0;
    tail_ = 0;
    count_ = 0;
    overflow_count_ = 0;
    wrapped_ = false;
    memset(buffer_, 0, sizeof(buffer_));
}

void LogBuffer::dump(void (*output_fn)(const LogEntry&)) {
    if (!initialized_ || mutex_ == nullptr || !output_fn) return;

    MutexGuard guard(mutex_);
    if (!guard.acquired()) return;

    for (size_t i = 0; i < count_; i++) {
        size_t index = (tail_ + i) % BUFFER_SIZE;
        output_fn(buffer_[index]);
    }
}