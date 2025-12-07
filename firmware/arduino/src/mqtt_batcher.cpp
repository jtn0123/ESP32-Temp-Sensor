#include "mqtt_batcher.h"
#include "safe_strings.h"

MQTTBatcher& MQTTBatcher::getInstance() {
    static MQTTBatcher instance;
    return instance;
}

bool MQTTBatcher::queue(const char* topic, const char* payload, bool retain) {
    stats_.total_queued++;

    if (queue_count_ >= MAX_BATCH) {
        stats_.queue_full_drops++;
        Serial.printf("[MQTTBatch] Queue full, dropping: %s\n", topic);
        return false;
    }

    QueuedPublish& entry = queue_[queue_count_];
    safe_strcpy(entry.topic, topic);
    safe_strcpy(entry.payload, payload);
    entry.retain = retain;
    entry.valid = true;

    queue_count_++;
    return true;
}

size_t MQTTBatcher::flush(PubSubClient* client) {
    if (!client || !client->connected() || queue_count_ == 0) {
        return 0;
    }

    stats_.flush_count++;
    size_t success_count = 0;

    for (size_t i = 0; i < queue_count_; i++) {
        QueuedPublish& entry = queue_[i];
        if (entry.valid) {
            if (client->publish(entry.topic, entry.payload, entry.retain)) {
                success_count++;
            } else {
                Serial.printf("[MQTTBatch] Failed to publish: %s\n", entry.topic);
            }
            entry.valid = false;
        }
    }

    stats_.total_flushed += success_count;
    queue_count_ = 0;

    return success_count;
}

void MQTTBatcher::clear() {
    for (size_t i = 0; i < queue_count_; i++) {
        queue_[i].valid = false;
    }
    queue_count_ = 0;
}

void MQTTBatcher::resetStats() {
    stats_ = {};
}

void MQTTBatcher::formatStatsJson(char* out, size_t out_size) const {
    float avg_batch = stats_.flush_count > 0
        ? (float)stats_.total_flushed / stats_.flush_count
        : 0.0f;

    safe_snprintf_rt(out, out_size,
            "{\"queued\":%u,\"flushed\":%u,\"flushes\":%u,\"drops\":%u,\"avg_batch\":%.1f,\"current_queue\":%zu}",
            stats_.total_queued, stats_.total_flushed, stats_.flush_count,
            stats_.queue_full_drops, avg_batch, queue_count_);
}
