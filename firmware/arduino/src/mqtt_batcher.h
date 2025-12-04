#pragma once

#include <Arduino.h>
#include <PubSubClient.h>

// MQTT publish batcher - queues messages and sends in batch
// Reduces WiFi active time by minimizing publish round-trips
//
// Usage:
//   MQTTBatcher& batcher = MQTTBatcher::getInstance();
//   batcher.queue("topic1", "payload1", true);
//   batcher.queue("topic2", "payload2", true);
//   batcher.flush(mqtt_client);

class MQTTBatcher {
public:
    static constexpr size_t MAX_BATCH = 12;
    static constexpr size_t MAX_TOPIC_LEN = 64;
    static constexpr size_t MAX_PAYLOAD_LEN = 48;

    struct QueuedPublish {
        char topic[MAX_TOPIC_LEN];
        char payload[MAX_PAYLOAD_LEN];
        bool retain;
        bool valid;
    };

    static MQTTBatcher& getInstance();

    // Queue a message for batched publish
    // Returns false if queue is full
    bool queue(const char* topic, const char* payload, bool retain = false);

    // Flush all queued messages
    // Returns number of messages successfully published
    size_t flush(PubSubClient* client);

    // Get queue status
    size_t getQueuedCount() const { return queue_count_; }
    bool isFull() const { return queue_count_ >= MAX_BATCH; }
    bool isEmpty() const { return queue_count_ == 0; }

    // Clear queue without publishing
    void clear();

    // Stats
    struct Stats {
        uint32_t total_queued;
        uint32_t total_flushed;
        uint32_t flush_count;        // Number of flush operations
        uint32_t queue_full_drops;   // Messages dropped due to full queue
    };

    const Stats& getStats() const { return stats_; }
    void resetStats();

    void formatStatsJson(char* out, size_t out_size) const;

private:
    MQTTBatcher() = default;
    ~MQTTBatcher() = default;
    MQTTBatcher(const MQTTBatcher&) = delete;
    MQTTBatcher& operator=(const MQTTBatcher&) = delete;

    QueuedPublish queue_[MAX_BATCH];
    size_t queue_count_ = 0;
    Stats stats_ = {};
};
