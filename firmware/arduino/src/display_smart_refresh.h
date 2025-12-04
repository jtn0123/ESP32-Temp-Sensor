#pragma once

#include <Arduino.h>
#include <cstdint>

// Region content change tracking for smart partial refresh
// Only refreshes regions that have actually changed
//
// Usage:
//   SmartRefresh::getInstance().registerRegion(REGION_INSIDE_TEMP);
//
//   if (SmartRefresh::getInstance().hasContentChanged(REGION_INSIDE_TEMP, temp_str)) {
//       // Content changed, redraw region
//       drawTemperature(temp_str);
//       SmartRefresh::getInstance().markClean(REGION_INSIDE_TEMP);
//   }

class SmartRefresh {
public:
    static constexpr size_t MAX_REGIONS = 16;

    struct RegionState {
        uint8_t region_id;
        uint32_t content_hash;
        uint32_t last_update_ms;
        bool dirty;
    };

    static SmartRefresh& getInstance();

    // Initialize tracking for a region
    void registerRegion(uint8_t region_id);

    // Check if content has changed (computes hash)
    // Returns true if content changed and region should be redrawn
    bool hasContentChanged(uint8_t region_id, const char* content);
    bool hasContentChanged(uint8_t region_id, int32_t value);
    bool hasContentChanged(uint8_t region_id, float value, int decimals = 1);

    // Mark region as dirty (force redraw)
    void markDirty(uint8_t region_id);
    void markAllDirty();

    // Clear dirty flag after rendering
    void markClean(uint8_t region_id);

    // Check if any region needs update
    bool hasAnyDirty() const;

    // Get dirty regions as bitmask
    uint16_t getDirtyMask() const;

    // Stats
    struct Stats {
        uint32_t total_checks;
        uint32_t actual_updates;  // Content actually changed
        uint32_t skipped_updates; // Content unchanged, skipped
    };

    const Stats& getStats() const { return stats_; }
    void resetStats();

    // Format for debug
    void formatStatsJson(char* out, size_t out_size) const;

private:
    SmartRefresh() = default;
    ~SmartRefresh() = default;
    SmartRefresh(const SmartRefresh&) = delete;
    SmartRefresh& operator=(const SmartRefresh&) = delete;

    RegionState regions_[MAX_REGIONS];
    size_t region_count_ = 0;
    Stats stats_ = {};

    // Simple hash function
    uint32_t computeHash(const char* data, size_t len);
    RegionState* findRegion(uint8_t region_id);
};
