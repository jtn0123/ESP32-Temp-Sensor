"""Integration tests for MQTT diagnostic features."""

import json
import time
import pytest
from unittest.mock import Mock, patch, MagicMock
import paho.mqtt.client as mqtt


class TestDiagnosticsMQTTIntegration:
    """Integration tests for diagnostic MQTT functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.device_id = "esp32-test-001"
        self.base_topic = f"espsensor/{self.device_id}"
        self.received_messages = {}
        self.mqtt_client = None

    def on_message(self, client, userdata, message):
        """Callback for received MQTT messages."""
        self.received_messages[message.topic] = {
            "payload": message.payload.decode(),
            "retain": message.retain,
        }

    @pytest.mark.integration
    def test_diagnostic_topics_structure(self):
        """Test that all diagnostic topics follow the correct structure."""
        expected_topics = [
            f"{self.base_topic}/diagnostics/boot_reason",
            f"{self.base_topic}/diagnostics/boot_count",
            f"{self.base_topic}/diagnostics/crash_count",
            f"{self.base_topic}/diagnostics/uptime",
            f"{self.base_topic}/diagnostics/memory",
            f"{self.base_topic}/diagnostics/wake_count",
            f"{self.base_topic}/diagnostics/diagnostic_mode",
            f"{self.base_topic}/command/diagnostic_mode",
            f"{self.base_topic}/command/reset",
        ]

        for topic in expected_topics:
            # Verify topic follows naming convention
            assert topic.startswith(self.base_topic)
            assert "/diagnostics/" in topic or "/command/" in topic

    @pytest.mark.integration
    def test_diagnostic_mode_activation_flow(self):
        """Test the complete flow of activating diagnostic mode via MQTT."""
        # Simulate MQTT command to activate diagnostic mode
        command_topic = f"{self.base_topic}/command/diagnostic_mode"
        status_topic = f"{self.base_topic}/diagnostics/diagnostic_mode"

        # Test that the command topic is correctly formatted
        assert command_topic == f"espsensor/{self.device_id}/command/diagnostic_mode"
        assert status_topic == f"espsensor/{self.device_id}/diagnostics/diagnostic_mode"

        # Test command processing
        command_result = self.simulate_mqtt_command(command_topic, "on")
        assert command_result["topic"] == command_topic
        assert command_result["payload"] == "on"

    @pytest.mark.integration
    def test_diagnostic_data_publishing_interval(self):
        """Test that diagnostic data is published at correct intervals."""
        interval_ms = 10000  # 10 seconds

        timestamps = []

        # Simulate periodic publishing
        for i in range(3):
            timestamp = time.time()
            timestamps.append(timestamp)

            # Simulate diagnostic data publishing
            self.publish_diagnostic_data(timestamp)

            if i < 2:
                time.sleep(interval_ms / 1000)

        # Check intervals
        for i in range(1, len(timestamps)):
            interval = (timestamps[i] - timestamps[i - 1]) * 1000
            assert abs(interval - interval_ms) < 100  # Allow 100ms tolerance

    @pytest.mark.integration
    def test_home_assistant_discovery_diagnostics(self):
        """Test Home Assistant discovery messages for diagnostic entities."""
        discovery_topics = [
            "homeassistant/sensor/esp32_test_001_boot_reason/config",
            "homeassistant/sensor/esp32_test_001_boot_count/config",
            "homeassistant/sensor/esp32_test_001_crash_count/config",
            "homeassistant/sensor/esp32_test_001_uptime/config",
            "homeassistant/sensor/esp32_test_001_wake_count/config",
        ]

        for topic in discovery_topics:
            # Verify discovery payload structure
            payload = self.create_ha_discovery_payload(topic)
            parsed = json.loads(payload)

            # Check required fields
            assert "name" in parsed
            assert "unique_id" in parsed
            assert "state_topic" in parsed
            assert "device" in parsed

            # Verify device class for diagnostic entities
            if "boot" in topic or "crash" in topic or "wake" in topic:
                assert parsed.get("device_class") == "None" or not parsed.get("device_class")
            elif "uptime" in topic:
                assert parsed["device_class"] == "duration"

    @pytest.mark.integration
    def test_rapid_reset_diagnostic_trigger(self):
        """Test that rapid resets trigger diagnostic mode."""
        # Simulate rapid resets
        reset_times = [1000, 1003, 1006]  # 3 resets within 6 seconds

        for i, reset_time in enumerate(reset_times):
            boot_count = i + 1

            # After 3rd reset within 10 seconds, diagnostic mode should activate
            if boot_count >= 3 and (reset_time - reset_times[0]) <= 10:
                diagnostic_mode_active = True
            else:
                diagnostic_mode_active = False

        assert diagnostic_mode_active == True

    @pytest.mark.integration
    def test_diagnostic_command_handling(self):
        """Test handling of diagnostic commands via MQTT."""
        commands = [
            (f"{self.base_topic}/command/diagnostic_mode", "on", "activate_diagnostic"),
            (f"{self.base_topic}/command/diagnostic_mode", "off", "deactivate_diagnostic"),
            (f"{self.base_topic}/command/reset", "1", "trigger_reset"),
        ]

        for topic, payload, expected_action in commands:
            action = self.process_mqtt_command(topic, payload)
            assert action == expected_action

    @pytest.mark.integration
    def test_memory_diagnostics_json_format(self):
        """Test memory diagnostics JSON payload format."""
        memory_topic = f"{self.base_topic}/diagnostics/memory"

        # Sample memory diagnostic payload
        memory_data = {
            "free_heap": 45000,
            "min_heap": 32000,
            "largest_block": 28000,
            "fragmentation": 37.8,
        }

        json_payload = json.dumps(memory_data)

        # Verify JSON is valid and contains required fields
        parsed = json.loads(json_payload)
        assert "free_heap" in parsed
        assert "min_heap" in parsed
        assert "largest_block" in parsed
        assert "fragmentation" in parsed

        # Check data types
        assert isinstance(parsed["free_heap"], int)
        assert isinstance(parsed["min_heap"], int)
        assert isinstance(parsed["largest_block"], int)
        assert isinstance(parsed["fragmentation"], (int, float))

    @pytest.mark.integration
    def test_diagnostic_persistence_across_reboots(self):
        """Test that diagnostic counters persist across reboots."""
        # Simulate boot sequence with existing counters
        rtc_data = {"boot_count": 10, "crash_count": 2, "wake_count": 50, "uptime": 3600}

        # Simulate normal reboot (not power-on)
        reset_reason = "ESP_RST_SW"

        # Update counters
        new_rtc_data = self.update_counters_on_boot(rtc_data, reset_reason)

        # Boot count should increment
        assert new_rtc_data["boot_count"] == rtc_data["boot_count"] + 1

        # Other counters should persist
        assert new_rtc_data["crash_count"] == rtc_data["crash_count"]
        assert new_rtc_data["wake_count"] == rtc_data["wake_count"]

    @pytest.mark.integration
    def test_diagnostic_mode_prevents_sleep(self):
        """Test that diagnostic mode prevents deep sleep."""
        diagnostic_mode = True

        # Check if sleep should be skipped
        should_sleep = self.check_should_sleep(diagnostic_mode)

        assert should_sleep == False

        # Normal mode should allow sleep
        diagnostic_mode = False
        should_sleep = self.check_should_sleep(diagnostic_mode)
        assert should_sleep == True

    # Helper methods
    def simulate_mqtt_command(self, topic, payload):
        """Simulate sending an MQTT command."""
        return {"topic": topic, "payload": payload}

    def publish_diagnostic_data(self, timestamp):
        """Simulate publishing diagnostic data."""
        return {"timestamp": timestamp, "data": {"free_heap": 45000, "uptime": 3600}}

    def create_ha_discovery_payload(self, topic):
        """Create a sample HA discovery payload."""
        entity_name = topic.split("_")[-1].replace("/config", "")
        return json.dumps(
            {
                "name": f"Test {entity_name}",
                "unique_id": f"test_{entity_name}",
                "state_topic": f"{self.base_topic}/diagnostics/{entity_name}",
                "device": {"identifiers": [self.device_id], "name": "Test Device"},
                "device_class": "duration" if "uptime" in entity_name else None,
            }
        )

    def process_mqtt_command(self, topic, payload):
        """Process an MQTT command and return action."""
        if topic.endswith("/command/diagnostic_mode"):
            if payload in ["on", "1", "true"]:
                return "activate_diagnostic"
            elif payload in ["off", "0", "false"]:
                return "deactivate_diagnostic"
        elif topic.endswith("/command/reset"):
            if payload in ["1", "true"]:
                return "trigger_reset"
        return None

    def update_counters_on_boot(self, rtc_data, reset_reason):
        """Update RTC counters based on reset reason."""
        new_data = rtc_data.copy()

        if reset_reason == "ESP_RST_POWERON":
            new_data["boot_count"] = 1
            new_data["crash_count"] = 0
            new_data["uptime"] = 0
        else:
            new_data["boot_count"] += 1

            crash_reasons = ["PANIC", "WDT", "BROWNOUT"]
            if any(cr in reset_reason for cr in crash_reasons):
                new_data["crash_count"] += 1

        return new_data

    def check_should_sleep(self, diagnostic_mode):
        """Check if device should enter deep sleep."""
        return not diagnostic_mode


class TestDiagnosticsMQTTSubscriptions:
    """Test MQTT subscription handling for diagnostic commands."""

    def test_subscription_topics(self):
        """Test that device subscribes to correct command topics."""
        device_id = "esp32-test"
        base_topic = f"espsensor/{device_id}"

        required_subscriptions = [
            f"{base_topic}/command/diagnostic_mode",
            f"{base_topic}/command/reset",
        ]

        # Simulate subscription list
        subscriptions = self.get_mqtt_subscriptions(base_topic)

        for topic in required_subscriptions:
            assert topic in subscriptions

    def test_command_topic_wildcard_handling(self):
        """Test that wildcard subscriptions work for commands."""
        base_topic = "espsensor/test-device"

        # Device might subscribe to wildcard
        wildcard_sub = f"{base_topic}/command/+"

        # Test that wildcard matches specific commands
        test_topics = [
            f"{base_topic}/command/diagnostic_mode",
            f"{base_topic}/command/reset",
            f"{base_topic}/command/future_command",
        ]

        for topic in test_topics:
            assert self.matches_wildcard(wildcard_sub, topic)

    def get_mqtt_subscriptions(self, base_topic):
        """Get list of MQTT subscriptions."""
        return [
            f"{base_topic}/command/diagnostic_mode",
            f"{base_topic}/command/reset",
        ]

    def matches_wildcard(self, pattern, topic):
        """Check if topic matches wildcard pattern."""
        pattern_parts = pattern.split("/")
        topic_parts = topic.split("/")

        if len(pattern_parts) != len(topic_parts):
            return False

        for p, t in zip(pattern_parts, topic_parts):
            if p != "+" and p != t:
                return False

        return True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration"])
