#pragma once

#include <Arduino.h>
#include <cstdint>

// Static buffer pool for reducing heap fragmentation
// Provides pre-allocated buffers for temporary string operations
//
// Usage:
//   char* buf = BufferPool::getInstance().acquireSmall();
//   snprintf(buf, BufferPool::SMALL_BUF, "format %d", value);
//   // ... use buffer
//   BufferPool::getInstance().release(buf);
//
// Or use RAII helper:
//   {
//       ScopedBuffer buf(BufferPool::SMALL_BUF);
//       snprintf(buf.get(), buf.size(), "format %d", value);
//       // ... automatic release on scope exit
//   }

class BufferPool {
public:
    static constexpr size_t SMALL_BUF = 64;    // For small strings (topics, short messages)
    static constexpr size_t MEDIUM_BUF = 128;  // For medium strings (JSON snippets)
    static constexpr size_t LARGE_BUF = 256;   // For large strings (full JSON messages)

    static constexpr size_t SMALL_POOL_SIZE = 4;   // 4 x 64 = 256 bytes
    static constexpr size_t MEDIUM_POOL_SIZE = 2;  // 2 x 128 = 256 bytes
    static constexpr size_t LARGE_POOL_SIZE = 1;   // 1 x 256 = 256 bytes
    // Total static allocation: 768 bytes

    static BufferPool& getInstance() {
        static BufferPool instance;
        return instance;
    }

    // Acquire buffers (returns nullptr if pool exhausted)
    char* acquireSmall();
    char* acquireMedium();
    char* acquireLarge();

    // Generic acquire by size
    char* acquire(size_t size);

    // Release buffer back to pool
    void release(char* buf);

    // Check if buffer belongs to pool
    bool isPoolBuffer(const char* buf) const;

    // Statistics
    struct Stats {
        uint32_t small_acquired;
        uint32_t medium_acquired;
        uint32_t large_acquired;
        uint32_t small_released;
        uint32_t medium_released;
        uint32_t large_released;
        uint32_t acquire_failures;  // Pool exhausted
        uint32_t invalid_releases;  // Tried to release non-pool buffer
        uint8_t small_in_use;
        uint8_t medium_in_use;
        uint8_t large_in_use;
    };

    const Stats& getStats() const { return stats_; }
    void resetStats();

    // Format stats to JSON
    void formatStatsJson(char* out, size_t out_size) const;

private:
    BufferPool();
    ~BufferPool() = default;
    BufferPool(const BufferPool&) = delete;
    BufferPool& operator=(const BufferPool&) = delete;

    // Buffer pools
    char small_pool_[SMALL_POOL_SIZE][SMALL_BUF];
    char medium_pool_[MEDIUM_POOL_SIZE][MEDIUM_BUF];
    char large_pool_[LARGE_POOL_SIZE][LARGE_BUF];

    // In-use bitmasks (1 bit per buffer)
    uint8_t small_in_use_;   // 4 bits used
    uint8_t medium_in_use_;  // 2 bits used
    uint8_t large_in_use_;   // 1 bit used

    Stats stats_;

    // Helper to find free slot
    int8_t findFreeSlot(uint8_t mask, uint8_t max_count) const;
};

// RAII wrapper for automatic buffer release
class ScopedBuffer {
public:
    explicit ScopedBuffer(size_t size) : buf_(nullptr), size_(0) {
        buf_ = BufferPool::getInstance().acquire(size);
        if (buf_) {
            size_ = (size <= BufferPool::SMALL_BUF) ? BufferPool::SMALL_BUF :
                    (size <= BufferPool::MEDIUM_BUF) ? BufferPool::MEDIUM_BUF :
                    BufferPool::LARGE_BUF;
        }
    }

    ~ScopedBuffer() {
        if (buf_) {
            BufferPool::getInstance().release(buf_);
        }
    }

    // No copy
    ScopedBuffer(const ScopedBuffer&) = delete;
    ScopedBuffer& operator=(const ScopedBuffer&) = delete;

    // Move support
    ScopedBuffer(ScopedBuffer&& other) noexcept : buf_(other.buf_), size_(other.size_) {
        other.buf_ = nullptr;
        other.size_ = 0;
    }

    char* get() { return buf_; }
    const char* get() const { return buf_; }
    size_t size() const { return size_; }
    bool valid() const { return buf_ != nullptr; }
    operator bool() const { return valid(); }

private:
    char* buf_;
    size_t size_;
};
