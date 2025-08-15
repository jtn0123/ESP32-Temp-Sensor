#pragma once

struct BatteryStatus {
    float voltage = NAN;
    int percent = -1;
    int estimatedDays = -1;
};

inline BatteryStatus read_battery_status() {
    BatteryStatus b;
    return b;
}

inline void go_deep_sleep_seconds(uint32_t seconds) {
    // TODO: implement deep sleep setup (timer wake)
}


