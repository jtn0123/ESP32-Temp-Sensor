#include "display_smart_refresh.h"
#include <cstring>

SmartRefresh& SmartRefresh::getInstance() {
    static SmartRefresh instance;
    return instance;
}

void SmartRefresh::registerRegion(uint8_t region_id) {
    if (findRegion(region_id)) return;  // Already registered
    if (region_count_ >= MAX_REGIONS) return;

    regions_[region_count_].region_id = region_id;
    regions_[region_count_].content_hash = 0;
    regions_[region_count_].last_update_ms = 0;
    regions_[region_count_].dirty = true;  // Initial state is dirty
    region_count_++;
}

SmartRefresh::RegionState* SmartRefresh::findRegion(uint8_t region_id) {
    for (size_t i = 0; i < region_count_; i++) {
        if (regions_[i].region_id == region_id) {
            return &regions_[i];
        }
    }
    return nullptr;
}

uint32_t SmartRefresh::computeHash(const char* data, size_t len) {
    // FNV-1a hash
    uint32_t hash = 2166136261u;
    for (size_t i = 0; i < len; i++) {
        hash ^= (uint8_t)data[i];
        hash *= 16777619u;
    }
    return hash;
}

bool SmartRefresh::hasContentChanged(uint8_t region_id, const char* content) {
    stats_.total_checks++;

    RegionState* region = findRegion(region_id);
    if (!region) {
        // Unknown region, assume changed
        stats_.actual_updates++;
        return true;
    }

    size_t len = content ? strlen(content) : 0;
    uint32_t new_hash = computeHash(content, len);

    if (new_hash != region->content_hash || region->dirty) {
        region->content_hash = new_hash;
        region->last_update_ms = millis();
        region->dirty = true;
        stats_.actual_updates++;
        return true;
    }

    stats_.skipped_updates++;
    return false;
}

bool SmartRefresh::hasContentChanged(uint8_t region_id, int32_t value) {
    char buf[16];
    snprintf(buf, sizeof(buf), "%ld", (long)value);
    return hasContentChanged(region_id, buf);
}

bool SmartRefresh::hasContentChanged(uint8_t region_id, float value, int decimals) {
    char buf[16];
    snprintf(buf, sizeof(buf), "%.*f", decimals, value);
    return hasContentChanged(region_id, buf);
}

void SmartRefresh::markDirty(uint8_t region_id) {
    RegionState* region = findRegion(region_id);
    if (region) {
        region->dirty = true;
    }
}

void SmartRefresh::markAllDirty() {
    for (size_t i = 0; i < region_count_; i++) {
        regions_[i].dirty = true;
    }
}

void SmartRefresh::markClean(uint8_t region_id) {
    RegionState* region = findRegion(region_id);
    if (region) {
        region->dirty = false;
    }
}

bool SmartRefresh::hasAnyDirty() const {
    for (size_t i = 0; i < region_count_; i++) {
        if (regions_[i].dirty) return true;
    }
    return false;
}

uint16_t SmartRefresh::getDirtyMask() const {
    uint16_t mask = 0;
    for (size_t i = 0; i < region_count_; i++) {
        if (regions_[i].dirty) {
            mask |= (1 << regions_[i].region_id);
        }
    }
    return mask;
}

void SmartRefresh::resetStats() {
    stats_ = {};
}

void SmartRefresh::formatStatsJson(char* out, size_t out_size) const {
    float skip_rate = stats_.total_checks > 0
        ? (100.0f * stats_.skipped_updates / stats_.total_checks)
        : 0.0f;

    snprintf(out, out_size,
            "{\"total_checks\":%u,\"actual_updates\":%u,\"skipped\":%u,\"skip_rate\":%.1f}",
            stats_.total_checks, stats_.actual_updates, stats_.skipped_updates, skip_rate);
}
