"""Unit tests for memory diagnostics and heap monitoring."""

import json
import pytest
from unittest.mock import Mock, patch


class TestMemoryDiagnostics:
    """Test memory diagnostic calculations and monitoring."""

    def test_fragmentation_calculation(self):
        """Test heap fragmentation percentage calculation."""
        # Test case: 50% fragmentation
        free_heap = 50000
        largest_block = 25000
        expected_fragmentation = ((free_heap - largest_block) / free_heap) * 100

        fragmentation = self.calculate_fragmentation(free_heap, largest_block)
        assert abs(fragmentation - expected_fragmentation) < 0.01
        assert fragmentation == 50.0

        # Test case: No fragmentation (largest block equals free heap)
        free_heap = 50000
        largest_block = 50000
        fragmentation = self.calculate_fragmentation(free_heap, largest_block)
        assert fragmentation == 0.0

        # Test case: High fragmentation
        free_heap = 100000
        largest_block = 10000
        expected_fragmentation = 90.0
        fragmentation = self.calculate_fragmentation(free_heap, largest_block)
        assert abs(fragmentation - expected_fragmentation) < 0.01

    def test_fragmentation_edge_cases(self):
        """Test fragmentation calculation with edge cases."""
        # Test case: Zero free heap (should return 0 to avoid division by zero)
        fragmentation = self.calculate_fragmentation(0, 0)
        assert fragmentation == 0.0

        # Test case: Largest block > free heap (invalid, should handle gracefully)
        fragmentation = self.calculate_fragmentation(1000, 2000)
        assert fragmentation == 0.0  # Should clamp or return 0

    def test_memory_diagnostics_structure(self):
        """Test the memory diagnostics data structure."""
        diag = self.create_memory_diagnostics(free_heap=45000, min_heap=32000, largest_block=28000)

        assert diag["free_heap"] == 45000
        assert diag["min_heap"] == 32000
        assert diag["largest_block"] == 28000
        assert "fragmentation_pct" in diag

        # Calculate expected fragmentation
        expected_frag = ((45000 - 28000) / 45000) * 100
        assert abs(diag["fragmentation_pct"] - expected_frag) < 0.01

    def test_memory_leak_detection(self):
        """Test detection of potential memory leaks."""
        # Simulate memory readings over time
        memory_samples = [
            {"free_heap": 50000, "min_heap": 45000},
            {"free_heap": 48000, "min_heap": 43000},
            {"free_heap": 46000, "min_heap": 41000},
            {"free_heap": 44000, "min_heap": 39000},
            {"free_heap": 42000, "min_heap": 37000},
        ]

        # Check for declining trend (potential leak)
        assert self.detect_memory_leak(memory_samples) == True

        # Stable memory (no leak)
        stable_samples = [
            {"free_heap": 50000, "min_heap": 45000},
            {"free_heap": 49500, "min_heap": 45000},
            {"free_heap": 50200, "min_heap": 45000},
            {"free_heap": 49800, "min_heap": 45000},
        ]

        assert self.detect_memory_leak(stable_samples) == False

    def test_memory_threshold_alerts(self):
        """Test memory threshold alerting."""
        # Define thresholds
        critical_threshold = 10000  # bytes
        warning_threshold = 20000  # bytes

        # Test critical level
        assert (
            self.check_memory_threshold(8000, critical_threshold, warning_threshold) == "critical"
        )

        # Test warning level
        assert (
            self.check_memory_threshold(15000, critical_threshold, warning_threshold) == "warning"
        )

        # Test normal level
        assert self.check_memory_threshold(30000, critical_threshold, warning_threshold) == "normal"

    def test_memory_json_payload(self):
        """Test JSON payload formatting for MQTT publishing."""
        mem_data = {
            "free_heap": 45000,
            "min_heap": 32000,
            "largest_block": 28000,
            "fragmentation": 37.8,
        }

        json_payload = json.dumps(
            {
                "free_heap": mem_data["free_heap"],
                "min_heap": mem_data["min_heap"],
                "largest_block": mem_data["largest_block"],
                "fragmentation": round(mem_data["fragmentation"], 1),
            }
        )

        parsed = json.loads(json_payload)
        assert parsed["free_heap"] == 45000
        assert parsed["min_heap"] == 32000
        assert parsed["largest_block"] == 28000
        assert parsed["fragmentation"] == 37.8

    # Helper methods
    def calculate_fragmentation(self, free_heap, largest_block):
        """Calculate fragmentation percentage."""
        if free_heap > 0 and largest_block > 0 and largest_block <= free_heap:
            return ((free_heap - largest_block) / free_heap) * 100.0
        return 0.0

    def create_memory_diagnostics(self, free_heap, min_heap, largest_block):
        """Create memory diagnostics structure."""
        return {
            "free_heap": free_heap,
            "min_heap": min_heap,
            "largest_block": largest_block,
            "fragmentation_pct": self.calculate_fragmentation(free_heap, largest_block),
        }

    def detect_memory_leak(self, samples):
        """Simple leak detection based on declining free heap trend."""
        if len(samples) < 3:
            return False

        # Check if free heap is consistently declining
        declining_count = 0
        for i in range(1, len(samples)):
            if samples[i]["free_heap"] < samples[i - 1]["free_heap"]:
                declining_count += 1

        # If more than 75% of samples show decline, potential leak
        return declining_count > len(samples) * 0.75

    def check_memory_threshold(self, free_heap, critical, warning):
        """Check memory against thresholds."""
        if free_heap < critical:
            return "critical"
        elif free_heap < warning:
            return "warning"
        return "normal"


class TestMemoryDiagnosticsMQTT:
    """Test MQTT publishing of memory diagnostics."""

    @patch("paho.mqtt.client.Client")
    def test_publish_memory_json(self, mock_mqtt):
        """Test memory diagnostics JSON is published correctly."""
        client = mock_mqtt.return_value
        client.connected = True

        memory_data = {
            "free_heap": 45000,
            "min_heap": 32000,
            "largest_block": 28000,
            "fragmentation": 37.8,
        }

        topic = "espsensor/test-device/diagnostics/memory"
        payload = json.dumps(memory_data)

        client.publish(topic, payload, retain=True)
        client.publish.assert_called_with(topic, payload, retain=True)

    def test_memory_payload_size(self):
        """Test that memory diagnostic payload size is reasonable."""
        memory_data = {
            "free_heap": 4294967295,  # Max uint32
            "min_heap": 4294967295,
            "largest_block": 4294967295,
            "fragmentation": 100.0,
        }

        payload = json.dumps(memory_data)
        # Payload should be compact, under 256 bytes
        assert len(payload) < 256

    def test_memory_diagnostic_interval(self):
        """Test that memory diagnostics respect publishing interval."""
        interval_ms = 10000  # 10 seconds

        # Simulate time tracking
        last_publish = 0
        current_time = 5000

        # Should not publish yet
        assert (current_time - last_publish) < interval_ms

        current_time = 10001
        # Should publish now
        assert (current_time - last_publish) >= interval_ms


class TestMemoryPerformance:
    """Test memory performance monitoring and analysis."""

    def test_heap_watermark_tracking(self):
        """Test minimum heap watermark tracking."""
        heap_samples = [50000, 45000, 40000, 42000, 38000, 41000]

        min_heap = min(heap_samples)
        assert min_heap == 38000

        # Watermark should persist even if heap recovers
        current_heap = 45000
        assert min_heap < current_heap

    def test_memory_recovery_detection(self):
        """Test detection of memory recovery after allocation."""
        samples = [
            {"timestamp": 1000, "free_heap": 50000},
            {"timestamp": 2000, "free_heap": 30000},  # Large allocation
            {"timestamp": 3000, "free_heap": 48000},  # Recovery
        ]

        # Detect recovery
        assert samples[2]["free_heap"] > samples[1]["free_heap"]
        recovery_amount = samples[2]["free_heap"] - samples[1]["free_heap"]
        assert recovery_amount == 18000

    def test_fragmentation_impact_analysis(self):
        """Test analysis of fragmentation impact on allocations."""
        # High fragmentation scenario
        free_heap = 50000
        largest_block = 5000  # Very fragmented

        # Check if can allocate specific size
        allocation_size = 10000
        can_allocate = largest_block >= allocation_size
        assert can_allocate == False  # Cannot allocate due to fragmentation

        # Low fragmentation scenario
        free_heap = 50000
        largest_block = 45000
        can_allocate = largest_block >= allocation_size
        assert can_allocate == True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
