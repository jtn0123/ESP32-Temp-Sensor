#include "logger.h"
#include "log_buffer.h"
#include "log_storage.h"
#include "log_mqtt.h"
#include "../config.h"
#include <esp_system.h>

static LogBuffer* g_log_buffer = nullptr;
static LogStorage* g_log_storage = nullptr;
static LogMQTT* g_log_mqtt = nullptr;

Logger& Logger::getInstance() {
    static Logger instance;
    return instance;
}

void Logger::begin(const Config& config) {
    if (initialized_) return;
    
    config_ = config;
    module_count_ = 0;
    sequence_ = 0;
    dropped_count_ = 0;
    
    memset(module_names_, 0, sizeof(module_names_));
    
    registerModule("SYSTEM");
    
    if (config_.buffer_enabled) {
        g_log_buffer = LogBuffer::getInstance();
        g_log_buffer->begin();
    }
    
    if (config_.nvs_enabled) {
        g_log_storage = LogStorage::getInstance();
        g_log_storage->begin();
    }
    
    if (config_.mqtt_enabled) {
        g_log_mqtt = LogMQTT::getInstance();
        g_log_mqtt->begin();
    }
    
    initialized_ = true;
    
    // Don't use LOG_INFO here since we haven't set up the module yet
    if (config_.serial_enabled) {
        Serial.printf("Logger initialized (level=%s, serial=%d, buffer=%d, nvs=%d, mqtt=%d)\n",
                     levelToString(config_.min_level),
                     config_.serial_enabled,
                     config_.buffer_enabled,
                     config_.nvs_enabled,
                     config_.mqtt_enabled);
    }
}

void Logger::end() {
    if (!initialized_) return;
    
    flush();
    
    if (g_log_mqtt) {
        g_log_mqtt->end();
        g_log_mqtt = nullptr;
    }
    
    if (g_log_storage) {
        g_log_storage->end();
        g_log_storage = nullptr;
    }
    
    if (g_log_buffer) {
        g_log_buffer->end();
        g_log_buffer = nullptr;
    }
    
    initialized_ = false;
}

uint8_t Logger::registerModule(const char* name) {
    if (module_count_ >= 16) {
        return 0;
    }
    
    strncpy(module_names_[module_count_], name, MAX_MODULE_NAME_LENGTH - 1);
    module_names_[module_count_][MAX_MODULE_NAME_LENGTH - 1] = '\0';
    
    return module_count_++;
}

void Logger::log(LogLevel level, uint8_t module, const char* format, ...) {
    va_list args;
    va_start(args, format);
    logv(level, module, format, args);
    va_end(args);
}

void Logger::logv(LogLevel level, uint8_t module, const char* format, va_list args) {
    if (level < config_.min_level) return;
    
    LogEntry entry;
    entry.timestamp = esp_timer_get_time() / 1000;
    entry.level = level;
    entry.module_id = module;
    entry.sequence = sequence_++;
    
    vsnprintf(entry.message, sizeof(entry.message), format, args);
    
    if (config_.serial_enabled) {
        outputSerial(entry);
    }
    
    if (config_.buffer_enabled && g_log_buffer) {
        outputBuffer(entry);
    }
    
    if (config_.nvs_enabled && g_log_storage && level >= LogLevel::ERROR) {
        outputNVS(entry);
    }
    
    if (config_.mqtt_enabled && g_log_mqtt) {
        uint32_t now = millis();
        if (now - last_mqtt_time_ >= config_.mqtt_rate_limit_ms) {
            outputMQTT(entry);
            last_mqtt_time_ = now;
        } else if (level >= LogLevel::ERROR) {
            outputMQTT(entry);
        }
    }
}

void Logger::trace(uint8_t module, const char* format, ...) {
    va_list args;
    va_start(args, format);
    logv(LogLevel::TRACE, module, format, args);
    va_end(args);
}

void Logger::debug(uint8_t module, const char* format, ...) {
    va_list args;
    va_start(args, format);
    logv(LogLevel::DEBUG, module, format, args);
    va_end(args);
}

void Logger::info(uint8_t module, const char* format, ...) {
    va_list args;
    va_start(args, format);
    logv(LogLevel::INFO, module, format, args);
    va_end(args);
}

void Logger::warn(uint8_t module, const char* format, ...) {
    va_list args;
    va_start(args, format);
    logv(LogLevel::WARN, module, format, args);
    va_end(args);
}

void Logger::error(uint8_t module, const char* format, ...) {
    va_list args;
    va_start(args, format);
    logv(LogLevel::ERROR, module, format, args);
    va_end(args);
}

void Logger::fatal(uint8_t module, const char* format, ...) {
    va_list args;
    va_start(args, format);
    logv(LogLevel::FATAL, module, format, args);
    va_end(args);
    
    flush();
    
    if (g_log_storage) {
        g_log_storage->markCrash();
    }
}

void Logger::setLevel(LogLevel level) {
    config_.min_level = level;
}

const char* Logger::levelToString(LogLevel level) const {
    switch (level) {
        case LogLevel::TRACE: return "TRACE";
        case LogLevel::DEBUG: return "DEBUG";
        case LogLevel::INFO:  return "INFO";
        case LogLevel::WARN:  return "WARN";
        case LogLevel::ERROR: return "ERROR";
        case LogLevel::FATAL: return "FATAL";
        default: return "NONE";
    }
}

LogLevel Logger::stringToLevel(const char* str) const {
    if (strcasecmp(str, "TRACE") == 0) return LogLevel::TRACE;
    if (strcasecmp(str, "DEBUG") == 0) return LogLevel::DEBUG;
    if (strcasecmp(str, "INFO") == 0) return LogLevel::INFO;
    if (strcasecmp(str, "WARN") == 0) return LogLevel::WARN;
    if (strcasecmp(str, "ERROR") == 0) return LogLevel::ERROR;
    if (strcasecmp(str, "FATAL") == 0) return LogLevel::FATAL;
    return LogLevel::NONE;
}

void Logger::flush() {
    if (g_log_storage) {
        g_log_storage->flush();
    }
    
    if (g_log_mqtt) {
        g_log_mqtt->flush();
    }
}

void Logger::dumpCrashLog() {
    if (!g_log_buffer) return;
    
    Serial.println("=== CRASH LOG DUMP ===");
    
    size_t count = g_log_buffer->getCount();
    LogEntry entry;
    
    for (size_t i = 0; i < count; i++) {
        if (g_log_buffer->getEntry(i, entry)) {
            outputSerial(entry);
        }
    }
    
    Serial.println("=== END CRASH LOG ===");
}

void Logger::clearCrashLog() {
    if (g_log_buffer) {
        g_log_buffer->clear();
    }
    
    if (g_log_storage) {
        g_log_storage->clearLogs();
    }
}

size_t Logger::getBufferedCount() const {
    return g_log_buffer ? g_log_buffer->getCount() : 0;
}

bool Logger::getBufferedEntry(size_t index, LogEntry& entry) const {
    return g_log_buffer ? g_log_buffer->getEntry(index, entry) : false;
}

void Logger::outputSerial(const LogEntry& entry) {
    char timestamp_str[16];
    snprintf(timestamp_str, sizeof(timestamp_str), "%lu", entry.timestamp);
    
    const char* module_name = (entry.module_id < module_count_) 
                              ? module_names_[entry.module_id] 
                              : "UNKNOWN";
    
    Serial.printf("[%s] %s [%s] %s\n",
                  timestamp_str,
                  levelToString(entry.level),
                  module_name,
                  entry.message);
}

void Logger::outputBuffer(const LogEntry& entry) {
    if (!g_log_buffer->push(entry)) {
        dropped_count_++;
    }
}

void Logger::outputNVS(const LogEntry& entry) {
    g_log_storage->storeEntry(entry);
}

void Logger::outputMQTT(const LogEntry& entry) {
    const char* module_name = (entry.module_id < module_count_) 
                              ? module_names_[entry.module_id] 
                              : "UNKNOWN";
    
    g_log_mqtt->publish(entry, module_name);
}