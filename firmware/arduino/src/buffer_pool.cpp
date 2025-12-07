#include "buffer_pool.h"
#include <cstring>

BufferPool::BufferPool()
    : small_in_use_(0)
    , medium_in_use_(0)
    , large_in_use_(0)
    , stats_{}
{
    // Zero all buffers
    memset(small_pool_, 0, sizeof(small_pool_));
    memset(medium_pool_, 0, sizeof(medium_pool_));
    memset(large_pool_, 0, sizeof(large_pool_));
}

char* BufferPool::acquireSmall() {
    int8_t slot = findFreeSlot(small_in_use_, SMALL_POOL_SIZE);
    if (slot < 0) {
        stats_.acquire_failures++;
        return nullptr;
    }

    small_in_use_ |= (1 << slot);
    stats_.small_acquired++;
    stats_.small_in_use++;

    return small_pool_[slot];
}

char* BufferPool::acquireMedium() {
    int8_t slot = findFreeSlot(medium_in_use_, MEDIUM_POOL_SIZE);
    if (slot < 0) {
        stats_.acquire_failures++;
        return nullptr;
    }

    medium_in_use_ |= (1 << slot);
    stats_.medium_acquired++;
    stats_.medium_in_use++;

    return medium_pool_[slot];
}

char* BufferPool::acquireLarge() {
    int8_t slot = findFreeSlot(large_in_use_, LARGE_POOL_SIZE);
    if (slot < 0) {
        stats_.acquire_failures++;
        return nullptr;
    }

    large_in_use_ |= (1 << slot);
    stats_.large_acquired++;
    stats_.large_in_use++;

    return large_pool_[slot];
}

char* BufferPool::acquire(size_t size) {
    // Note: size == 0 returns smallest buffer (valid use case for empty strings)
    // Caller is responsible for reserving space for null terminator if needed
    if (size <= SMALL_BUF) {
        return acquireSmall();
    } else if (size <= MEDIUM_BUF) {
        return acquireMedium();
    } else if (size <= LARGE_BUF) {
        return acquireLarge();
    }

    // Size too large for pool
    stats_.acquire_failures++;
    return nullptr;
}

void BufferPool::release(char* buf) {
    if (!buf) return;

    // Check small pool
    for (size_t i = 0; i < SMALL_POOL_SIZE; i++) {
        if (buf == small_pool_[i]) {
            uint8_t mask = (1 << i);
            if (small_in_use_ & mask) {
                small_in_use_ &= ~mask;
                stats_.small_released++;
                if (stats_.small_in_use > 0) stats_.small_in_use--;
                return;
            } else {
                // Double release detected
                stats_.invalid_releases++;
                Serial.println("[BufferPool] WARN: Double release of small buffer");
                return;
            }
        }
    }

    // Check medium pool
    for (size_t i = 0; i < MEDIUM_POOL_SIZE; i++) {
        if (buf == medium_pool_[i]) {
            uint8_t mask = (1 << i);
            if (medium_in_use_ & mask) {
                medium_in_use_ &= ~mask;
                stats_.medium_released++;
                if (stats_.medium_in_use > 0) stats_.medium_in_use--;
                return;
            } else {
                // Double release detected
                stats_.invalid_releases++;
                Serial.println("[BufferPool] WARN: Double release of medium buffer");
                return;
            }
        }
    }

    // Check large pool
    for (size_t i = 0; i < LARGE_POOL_SIZE; i++) {
        if (buf == large_pool_[i]) {
            uint8_t mask = (1 << i);
            if (large_in_use_ & mask) {
                large_in_use_ &= ~mask;
                stats_.large_released++;
                if (stats_.large_in_use > 0) stats_.large_in_use--;
                return;
            } else {
                // Double release detected
                stats_.invalid_releases++;
                Serial.println("[BufferPool] WARN: Double release of large buffer");
                return;
            }
        }
    }

    // Not a pool buffer
    stats_.invalid_releases++;
    Serial.println("[BufferPool] WARN: Release of non-pool buffer");
}

bool BufferPool::isPoolBuffer(const char* buf) const {
    if (!buf) return false;

    // Check if pointer is within any pool
    for (size_t i = 0; i < SMALL_POOL_SIZE; i++) {
        if (buf == small_pool_[i]) return true;
    }

    for (size_t i = 0; i < MEDIUM_POOL_SIZE; i++) {
        if (buf == medium_pool_[i]) return true;
    }

    for (size_t i = 0; i < LARGE_POOL_SIZE; i++) {
        if (buf == large_pool_[i]) return true;
    }

    return false;
}

void BufferPool::resetStats() {
    stats_.small_acquired = 0;
    stats_.medium_acquired = 0;
    stats_.large_acquired = 0;
    stats_.small_released = 0;
    stats_.medium_released = 0;
    stats_.large_released = 0;
    stats_.acquire_failures = 0;
    stats_.invalid_releases = 0;
    // Don't reset in_use counters - those are actual state
}

void BufferPool::formatStatsJson(char* out, size_t out_size) const {
    snprintf(out, out_size,
            "{\"small\":{\"acquired\":%u,\"released\":%u,\"in_use\":%u},"
            "\"medium\":{\"acquired\":%u,\"released\":%u,\"in_use\":%u},"
            "\"large\":{\"acquired\":%u,\"released\":%u,\"in_use\":%u},"
            "\"failures\":%u,\"invalid_releases\":%u}",
            stats_.small_acquired, stats_.small_released, stats_.small_in_use,
            stats_.medium_acquired, stats_.medium_released, stats_.medium_in_use,
            stats_.large_acquired, stats_.large_released, stats_.large_in_use,
            stats_.acquire_failures, stats_.invalid_releases);
}

int8_t BufferPool::findFreeSlot(uint8_t mask, uint8_t max_count) const {
    for (uint8_t i = 0; i < max_count; i++) {
        if ((mask & (1 << i)) == 0) {
            return i;
        }
    }
    return -1;  // No free slot
}
