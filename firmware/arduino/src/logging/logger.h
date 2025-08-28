#pragma once

#include <Arduino.h>
#include <esp_timer.h>
#include <cstdarg>

enum class LogLevel : uint8_t {
    TRACE = 0,
    DEBUG = 1,
    INFO = 2,
    WARN = 3,
    ERROR = 4,
    FATAL = 5,
    NONE = 6
};

struct LogEntry {
    uint32_t timestamp;     
    LogLevel level;         
    uint8_t module_id;      
    uint16_t sequence;      
    char message[48];       
} __attribute__((packed));

class Logger {
public:
    static constexpr size_t MAX_MESSAGE_LENGTH = 128;
    static constexpr size_t MAX_MODULE_NAME_LENGTH = 16;
    
    struct Config {
        LogLevel min_level;
        bool serial_enabled;
        bool buffer_enabled;
        bool nvs_enabled;
        bool mqtt_enabled;
        uint16_t mqtt_rate_limit_ms;
        
        Config() : 
            min_level(LogLevel::INFO),
            serial_enabled(true),
            buffer_enabled(true),
            nvs_enabled(false),
            mqtt_enabled(false),
            mqtt_rate_limit_ms(1000) {}
    };
    
    static Logger& getInstance();
    
    void begin(const Config& config = Config());
    void end();
    
    uint8_t registerModule(const char* name);
    
    void log(LogLevel level, uint8_t module, const char* format, ...);
    void logv(LogLevel level, uint8_t module, const char* format, va_list args);
    
    void trace(uint8_t module, const char* format, ...);
    void debug(uint8_t module, const char* format, ...);
    void info(uint8_t module, const char* format, ...);
    void warn(uint8_t module, const char* format, ...);
    void error(uint8_t module, const char* format, ...);
    void fatal(uint8_t module, const char* format, ...);
    
    void setLevel(LogLevel level);
    LogLevel getLevel() const { return config_.min_level; }
    
    void enableSerial(bool enable) { config_.serial_enabled = enable; }
    void enableBuffer(bool enable) { config_.buffer_enabled = enable; }
    void enableNVS(bool enable) { config_.nvs_enabled = enable; }
    void enableMQTT(bool enable) { config_.mqtt_enabled = enable; }
    
    const char* levelToString(LogLevel level) const;
    LogLevel stringToLevel(const char* str) const;
    
    void flush();
    
    void dumpCrashLog();
    void clearCrashLog();
    
    size_t getBufferedCount() const;
    bool getBufferedEntry(size_t index, LogEntry& entry) const;
    
    uint32_t getDroppedCount() const { return dropped_count_; }
    void resetDroppedCount() { dropped_count_ = 0; }
    
private:
    Logger() = default;
    ~Logger() = default;
    Logger(const Logger&) = delete;
    Logger& operator=(const Logger&) = delete;
    
    void outputSerial(const LogEntry& entry);
    void outputBuffer(const LogEntry& entry);
    void outputNVS(const LogEntry& entry);
    void outputMQTT(const LogEntry& entry);
    
    Config config_;
    char module_names_[16][MAX_MODULE_NAME_LENGTH];
    uint8_t module_count_ = 0;
    uint16_t sequence_ = 0;
    uint32_t dropped_count_ = 0;
    uint32_t last_mqtt_time_ = 0;
    bool initialized_ = false;
};

#define LOG_MODULE(name) static uint8_t log_module_id = Logger::getInstance().registerModule(name)

#define LOG_TRACE(fmt, ...) Logger::getInstance().trace(log_module_id, fmt, ##__VA_ARGS__)
#define LOG_DEBUG(fmt, ...) Logger::getInstance().debug(log_module_id, fmt, ##__VA_ARGS__)
#define LOG_INFO(fmt, ...) Logger::getInstance().info(log_module_id, fmt, ##__VA_ARGS__)
#define LOG_WARN(fmt, ...) Logger::getInstance().warn(log_module_id, fmt, ##__VA_ARGS__)
#define LOG_ERROR(fmt, ...) Logger::getInstance().error(log_module_id, fmt, ##__VA_ARGS__)
#define LOG_FATAL(fmt, ...) Logger::getInstance().fatal(log_module_id, fmt, ##__VA_ARGS__)

#define LOG_LEVEL_SET(level) Logger::getInstance().setLevel(level)
#define LOG_FLUSH() Logger::getInstance().flush()
#define LOG_DUMP_CRASH() Logger::getInstance().dumpCrashLog()
#define LOG_CLEAR_CRASH() Logger::getInstance().clearCrashLog()