#include "crash_handler.h"
#include "safe_strings.h"
#include <esp_heap_caps.h>

// RTC memory - persists across resets
RTC_DATA_ATTR CrashHandler::CrashInfo CrashHandler::crash_info_ = {};

CrashHandler& CrashHandler::getInstance() {
    static CrashHandler instance;
    return instance;
}

void CrashHandler::begin() {
    if (initialized_) return;

    // Increment boot count
    if (crash_info_.magic == CRASH_MAGIC) {
        crash_info_.boot_count++;
    } else {
        // First boot or invalid data - initialize
        memset(&crash_info_, 0, sizeof(crash_info_));
        crash_info_.magic = CRASH_MAGIC;
        crash_info_.boot_count = 1;
    }

    // Get reset reason
    esp_reset_reason_t reason = esp_reset_reason();
    crash_info_.reset_reason = reason;
    crash_info_.rtc_reset_reason = rtc_get_reset_reason(0);

    // If abnormal reset, increment crash count
    if (reason == ESP_RST_PANIC ||
        reason == ESP_RST_INT_WDT ||
        reason == ESP_RST_TASK_WDT ||
        reason == ESP_RST_WDT ||
        reason == ESP_RST_BROWNOUT) {

        crash_info_.crash_count++;
        crash_info_.last_crash_timestamp = millis();
        crash_info_.free_heap_at_crash = esp_get_free_heap_size();
        crash_info_.min_free_heap = esp_get_minimum_free_heap_size();
    }

    // Update checksum
    crash_info_.checksum = calculateChecksum(crash_info_);

    initialized_ = true;
}

bool CrashHandler::hasCrashInfo() const {
    if (crash_info_.magic != CRASH_MAGIC) return false;
    if (!validateChecksum(crash_info_)) return false;

    // Check if last reset was a crash
    return (crash_info_.reset_reason == ESP_RST_PANIC ||
            crash_info_.reset_reason == ESP_RST_INT_WDT ||
            crash_info_.reset_reason == ESP_RST_TASK_WDT ||
            crash_info_.reset_reason == ESP_RST_WDT ||
            crash_info_.reset_reason == ESP_RST_BROWNOUT);
}

void CrashHandler::clearCrashInfo() {
    // Keep boot/crash counts and magic, but clear crash-specific data
    crash_info_.last_crash_timestamp = 0;
    crash_info_.last_crash_pc = 0;
    crash_info_.last_crash_sp = 0;
    crash_info_.last_function[0] = '\0';
    crash_info_.free_heap_at_crash = 0;

    // Update checksum
    crash_info_.checksum = calculateChecksum(crash_info_);
}

void CrashHandler::recordFunction(const char* function_name) {
    if (function_name) {
        safe_strcpy(crash_info_.last_function, function_name);
        crash_info_.checksum = calculateChecksum(crash_info_);
    }
}

void CrashHandler::updateHeapStats() {
    uint32_t min_heap = esp_get_minimum_free_heap_size();
    if (min_heap < crash_info_.min_free_heap || crash_info_.min_free_heap == 0) {
        crash_info_.min_free_heap = min_heap;
        crash_info_.checksum = calculateChecksum(crash_info_);
    }
}

void CrashHandler::formatCrashReport(char* out, size_t out_size) const {
    snprintf(out, out_size,
            "{\"crash_count\":%u,"
            "\"boot_count\":%u,"
            "\"last_crash_ms\":%u,"
            "\"reset_reason\":\"%s\","
            "\"rtc_reason\":\"%s\","
            "\"last_function\":\"%s\","
            "\"heap_at_crash\":%u,"
            "\"min_heap\":%u}",
            crash_info_.crash_count,
            crash_info_.boot_count,
            crash_info_.last_crash_timestamp,
            getResetReasonString(crash_info_.reset_reason),
            getRtcResetReasonString(crash_info_.rtc_reset_reason),
            crash_info_.last_function,
            crash_info_.free_heap_at_crash,
            crash_info_.min_free_heap);
}

const char* CrashHandler::getResetReasonString(esp_reset_reason_t reason) const {
    switch (reason) {
        case ESP_RST_UNKNOWN:   return "UNKNOWN";
        case ESP_RST_POWERON:   return "POWERON";
        case ESP_RST_EXT:       return "EXTERNAL";
        case ESP_RST_SW:        return "SOFTWARE";
        case ESP_RST_PANIC:     return "PANIC";
        case ESP_RST_INT_WDT:   return "INT_WDT";
        case ESP_RST_TASK_WDT:  return "TASK_WDT";
        case ESP_RST_WDT:       return "WDT";
        case ESP_RST_DEEPSLEEP: return "DEEPSLEEP";
        case ESP_RST_BROWNOUT:  return "BROWNOUT";
        case ESP_RST_SDIO:      return "SDIO";
        default:                return "UNKNOWN";
    }
}

const char* CrashHandler::getRtcResetReasonString(RESET_REASON reason) const {
    switch (reason) {
        case POWERON_RESET:          return "POWERON";
        case RTC_SW_SYS_RESET:       return "SW_RESET";
        case DEEPSLEEP_RESET:        return "DEEPSLEEP";
        case TG0WDT_SYS_RESET:       return "TG0WDT";
        case TG1WDT_SYS_RESET:       return "TG1WDT";
        case RTCWDT_SYS_RESET:       return "RTCWDT";
        case INTRUSION_RESET:        return "INTRUSION";
        case TG0WDT_CPU_RESET:       return "TG0WDT_CPU";
        case RTC_SW_CPU_RESET:       return "SW_CPU";
        case RTCWDT_CPU_RESET:       return "RTCWDT_CPU";
        case RTCWDT_BROWN_OUT_RESET: return "BROWNOUT";
        case RTCWDT_RTC_RESET:       return "RTCWDT_RTC";
        case TG1WDT_CPU_RESET:       return "TG1WDT_CPU";
        case SUPER_WDT_RESET:        return "SUPER_WDT";
        case GLITCH_RTC_RESET:       return "GLITCH_RTC";
        default:                     return "UNKNOWN";
    }
}

uint16_t CrashHandler::calculateChecksum(const CrashInfo& info) const {
    // Simple XOR checksum of all fields except checksum itself
    const uint8_t* data = reinterpret_cast<const uint8_t*>(&info);
    size_t len = offsetof(CrashInfo, checksum);  // Everything before checksum field

    uint16_t sum = 0;
    for (size_t i = 0; i < len; i++) {
        sum ^= data[i];
        sum = (sum << 1) | (sum >> 15);  // Rotate left
    }

    return sum;
}

bool CrashHandler::validateChecksum(const CrashInfo& info) const {
    return calculateChecksum(info) == info.checksum;
}
