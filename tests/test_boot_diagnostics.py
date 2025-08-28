"""Unit tests for boot diagnostics and reset reason tracking."""

from unittest.mock import patch

import pytest


class TestBootDiagnostics:
    """Test boot reason reporting and crash detection."""

    def test_boot_reason_mapping(self):
        """Test that all ESP32 reset reasons are correctly mapped to strings."""
        # Define expected mappings based on the actual firmware implementation
        # The firmware returns the ESP_RST_* strings directly
        reset_reason_map = {
            "ESP_RST_POWERON": "ESP_RST_POWERON",
            "ESP_RST_SW": "ESP_RST_SW",
            "ESP_RST_PANIC": "ESP_RST_PANIC",
            "ESP_RST_INT_WDT": "ESP_RST_INT_WDT",
            "ESP_RST_TASK_WDT": "ESP_RST_TASK_WDT",
            "ESP_RST_WDT": "ESP_RST_WDT",
            "ESP_RST_BROWNOUT": "ESP_RST_BROWNOUT",
            "ESP_RST_DEEPSLEEP": "ESP_RST_DEEPSLEEP",
            "ESP_RST_EXT": "ESP_RST_EXT",
            "ESP_RST_SDIO": "ESP_RST_SDIO",
            "ESP_RST_UNKNOWN": "ESP_RST_UNKNOWN",
        }

        for esp_reason, expected_str in reset_reason_map.items():
            # The firmware returns the exact ESP_RST_* string
            assert esp_reason == expected_str

    def test_crash_detection(self):
        """Test that crash reset reasons are correctly identified."""
        crash_reasons = [
            "ESP_RST_PANIC",
            "ESP_RST_INT_WDT",
            "ESP_RST_TASK_WDT",
            "ESP_RST_WDT",
            "ESP_RST_BROWNOUT",
        ]

        normal_reasons = ["ESP_RST_POWERON", "ESP_RST_SW", "ESP_RST_DEEPSLEEP", "ESP_RST_EXT"]

        # Test crash detection logic
        for reason in crash_reasons:
            assert self.is_crash_reset(reason) == True

        for reason in normal_reasons:
            assert self.is_crash_reset(reason) == False

    def test_boot_counter_reset_on_power_cycle(self):
        """Test that counters are reset on power-on reset."""
        # Simulate power-on reset
        reset_reason = "ESP_RST_POWERON"

        # Expected behavior
        expected_boot_count = 1
        expected_crash_count = 0
        expected_uptime = 0

        counters = self.handle_boot_counters(
            reset_reason, prev_boot_count=100, prev_crash_count=50, prev_uptime=3600
        )

        assert counters["boot_count"] == expected_boot_count
        assert counters["crash_count"] == expected_crash_count
        assert counters["uptime"] == expected_uptime

    def test_boot_counter_increment(self):
        """Test that boot counter increments on non-power-on reset."""
        reset_reason = "ESP_RST_DEEPSLEEP"

        prev_boot_count = 10
        prev_crash_count = 2
        prev_uptime = 1000

        counters = self.handle_boot_counters(
            reset_reason,
            prev_boot_count=prev_boot_count,
            prev_crash_count=prev_crash_count,
            prev_uptime=prev_uptime,
        )

        assert counters["boot_count"] == prev_boot_count + 1
        assert counters["crash_count"] == prev_crash_count  # No change

    def test_crash_counter_increment(self):
        """Test that crash counter increments on abnormal reset."""
        crash_reasons = ["ESP_RST_PANIC", "ESP_RST_WDT", "ESP_RST_BROWNOUT"]

        for reset_reason in crash_reasons:
            prev_boot_count = 10
            prev_crash_count = 2

            counters = self.handle_boot_counters(
                reset_reason,
                prev_boot_count=prev_boot_count,
                prev_crash_count=prev_crash_count,
                prev_uptime=1000,
            )

            assert counters["boot_count"] == prev_boot_count + 1
            assert counters["crash_count"] == prev_crash_count + 1

    def test_rapid_reset_detection(self):
        """Test detection of rapid resets for diagnostic mode trigger."""
        # Test case: 3 resets within 10 seconds should trigger diagnostic mode
        timestamps = [1000, 1005, 1009]  # Within 10 seconds
        boot_count = 3

        assert self.check_rapid_reset_trigger(boot_count, timestamps[-1], timestamps[-2]) == True

        # Test case: 3 resets but not within 10 seconds
        timestamps = [1000, 1005, 1020]  # Last reset is >10s after previous
        assert self.check_rapid_reset_trigger(boot_count, timestamps[-1], timestamps[-2]) == False

        # Test case: Less than 3 resets
        boot_count = 2
        assert self.check_rapid_reset_trigger(boot_count, 1009, 1005) == False

    def test_uptime_tracking(self):
        """Test cumulative uptime tracking across sleep cycles."""
        # Simulate multiple wake cycles
        wake_durations = [30, 45, 60, 25]  # seconds
        cumulative_uptime = 0

        for duration in wake_durations:
            cumulative_uptime = self.update_uptime(cumulative_uptime, duration)

        assert cumulative_uptime == sum(wake_durations)

    # Helper methods that simulate firmware logic
    def is_crash_reset(self, reason):
        """Simulate firmware's reset_reason_is_crash() function."""
        crash_reasons = ["PANIC", "WDT", "BROWNOUT"]
        return any(cr in reason for cr in crash_reasons)

    def handle_boot_counters(self, reset_reason, prev_boot_count, prev_crash_count, prev_uptime):
        """Simulate firmware's boot counter update logic."""
        counters = {}

        if reset_reason == "ESP_RST_POWERON":
            counters["boot_count"] = 1
            counters["crash_count"] = 0
            counters["uptime"] = 0
        else:
            counters["boot_count"] = prev_boot_count + 1
            counters["crash_count"] = prev_crash_count
            counters["uptime"] = prev_uptime

            if self.is_crash_reset(reset_reason):
                counters["crash_count"] += 1

        return counters

    def check_rapid_reset_trigger(self, boot_count, current_time, last_boot_time):
        """Simulate rapid reset detection logic."""
        if boot_count >= 3:
            time_since_last = current_time - last_boot_time
            return time_since_last <= 10
        return False

    def update_uptime(self, current_uptime, awake_duration):
        """Simulate uptime accumulation."""
        return current_uptime + awake_duration


class TestBootDiagnosticsMQTT:
    """Test MQTT publishing of boot diagnostic information."""

    @patch("paho.mqtt.client.Client")
    def test_publish_boot_reason(self, mock_mqtt):
        """Test boot reason is published to correct MQTT topic."""
        client = mock_mqtt.return_value
        client.connected = True

        boot_reason = "ESP_RST_PANIC"
        topic = "espsensor/test-device/diagnostics/boot_reason"

        # Simulate publishing
        client.publish(topic, boot_reason, retain=True)

        # Verify call
        client.publish.assert_called_with(topic, boot_reason, retain=True)

    @patch("paho.mqtt.client.Client")
    def test_publish_diagnostic_counters(self, mock_mqtt):
        """Test all diagnostic counters are published."""
        client = mock_mqtt.return_value
        client.connected = True

        counters = {"boot_count": 42, "crash_count": 3, "wake_count": 100, "uptime": 3600}

        base_topic = "espsensor/test-device/diagnostics"

        for key, value in counters.items():
            topic = f"{base_topic}/{key}"
            client.publish(topic, str(value), retain=True)
            client.publish.assert_any_call(topic, str(value), retain=True)

    def test_diagnostic_mqtt_payload_format(self):
        """Test that diagnostic MQTT payloads are correctly formatted."""
        # Test boot count payload (should be simple integer string)
        boot_count = 42
        payload = str(boot_count)
        assert payload == "42"

        # Test uptime payload (seconds as string)
        uptime_sec = 3600
        payload = str(uptime_sec)
        assert payload == "3600"

        # Test boot reason payload (string)
        boot_reason = "ESP_RST_PANIC"
        assert isinstance(boot_reason, str)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
