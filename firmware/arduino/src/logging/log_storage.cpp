#include "log_storage.h"

LogStorage* LogStorage::getInstance() {
    static LogStorage instance;
    return &instance;
}

void LogStorage::begin() {
    if (initialized_) return;
    
    prefs_.begin(NVS_NAMESPACE, false);
    loadMetadata();
    initialized_ = true;
}

void LogStorage::end() {
    if (!initialized_) return;
    
    if (dirty_) {
        flush();
    }
    
    prefs_.end();
    initialized_ = false;
}

void LogStorage::loadMetadata() {
    head_ = prefs_.getUInt(KEY_HEAD, 0);
    count_ = prefs_.getUInt(KEY_COUNT, 0);
    
    if (count_ > MAX_STORED_ENTRIES) {
        count_ = 0;
        head_ = 0;
    }
}

void LogStorage::saveMetadata() {
    prefs_.putUInt(KEY_HEAD, head_);
    prefs_.putUInt(KEY_COUNT, count_);
    dirty_ = false;
}

bool LogStorage::storeEntry(const LogEntry& entry) {
    if (!initialized_) return false;
    
    rotateIfNeeded();
    
    size_t index = (head_ + count_) % MAX_STORED_ENTRIES;
    
    if (!storeEntryAtIndex(index, entry)) {
        return false;
    }
    
    if (count_ < MAX_STORED_ENTRIES) {
        count_++;
    } else {
        head_ = (head_ + 1) % MAX_STORED_ENTRIES;
    }
    
    dirty_ = true;
    
    if ((count_ % 5) == 0) {
        flush();
    }
    
    return true;
}

bool LogStorage::getEntry(size_t index, LogEntry& entry) {
    if (!initialized_ || index >= count_) return false;
    
    size_t actual_index = (head_ + index) % MAX_STORED_ENTRIES;
    return loadEntryAtIndex(actual_index, entry);
}

size_t LogStorage::getStoredCount() {
    return count_;
}

void LogStorage::clearLogs() {
    if (!initialized_) return;
    
    for (size_t i = 0; i < MAX_STORED_ENTRIES; i++) {
        prefs_.remove(getEntryKey(i).c_str());
    }
    
    head_ = 0;
    count_ = 0;
    saveMetadata();
}

void LogStorage::markCrash() {
    if (!initialized_) return;
    
    prefs_.putBool(KEY_CRASH, true);
}

bool LogStorage::wasCrashed() {
    if (!initialized_) return false;
    
    return prefs_.getBool(KEY_CRASH, false);
}

void LogStorage::clearCrashFlag() {
    if (!initialized_) return;
    
    prefs_.remove(KEY_CRASH);
}

void LogStorage::flush() {
    if (!initialized_ || !dirty_) return;
    
    saveMetadata();
}

void LogStorage::dumpToSerial() {
    if (!initialized_) return;
    
    Serial.printf("=== NVS LOG STORAGE (%zu entries) ===\n", count_);
    
    LogEntry entry;
    for (size_t i = 0; i < count_; i++) {
        if (getEntry(i, entry)) {
            Serial.printf("[%lu] %d: %s\n", 
                         entry.timestamp, 
                         (int)entry.level, 
                         entry.message);
        }
    }
    
    Serial.println("=== END NVS LOGS ===");
}

bool LogStorage::exportToBuffer(uint8_t* buffer, size_t& size, size_t max_size) {
    if (!initialized_ || !buffer || max_size < sizeof(LogEntry)) {
        size = 0;
        return false;
    }
    
    size_t written = 0;
    size_t entry_count = 0;
    
    LogEntry entry;
    for (size_t i = 0; i < count_ && written + sizeof(LogEntry) <= max_size; i++) {
        if (getEntry(i, entry)) {
            memcpy(buffer + written, &entry, sizeof(LogEntry));
            written += sizeof(LogEntry);
            entry_count++;
        }
    }
    
    size = written;
    return entry_count > 0;
}

size_t LogStorage::getOldestTimestamp() {
    if (!initialized_ || count_ == 0) return 0;
    
    LogEntry entry;
    if (getEntry(0, entry)) {
        return entry.timestamp;
    }
    
    return 0;
}

size_t LogStorage::getNewestTimestamp() {
    if (!initialized_ || count_ == 0) return 0;
    
    LogEntry entry;
    if (getEntry(count_ - 1, entry)) {
        return entry.timestamp;
    }
    
    return 0;
}

void LogStorage::pruneOldEntries(uint32_t max_age_ms) {
    if (!initialized_ || count_ == 0) return;
    
    uint32_t current_time = esp_timer_get_time() / 1000;
    uint32_t cutoff_time = current_time - max_age_ms;
    
    size_t removed = 0;
    LogEntry entry;
    
    while (count_ > 0 && getEntry(0, entry)) {
        if (entry.timestamp < cutoff_time) {
            head_ = (head_ + 1) % MAX_STORED_ENTRIES;
            count_--;
            removed++;
        } else {
            break;
        }
    }
    
    if (removed > 0) {
        dirty_ = true;
        flush();
    }
}

String LogStorage::getEntryKey(size_t index) {
    return String(KEY_PREFIX) + String(index);
}

bool LogStorage::storeEntryAtIndex(size_t index, const LogEntry& entry) {
    String key = getEntryKey(index);
    size_t written = prefs_.putBytes(key.c_str(), &entry, sizeof(LogEntry));
    return written == sizeof(LogEntry);
}

bool LogStorage::loadEntryAtIndex(size_t index, LogEntry& entry) {
    String key = getEntryKey(index);
    size_t read = prefs_.getBytes(key.c_str(), &entry, sizeof(LogEntry));
    return read == sizeof(LogEntry);
}

void LogStorage::rotateIfNeeded() {
    if (count_ >= MAX_STORED_ENTRIES) {
        head_ = (head_ + 1) % MAX_STORED_ENTRIES;
        count_ = MAX_STORED_ENTRIES - 1;
    }
}