"""
Property-based tests for MQTT topic generation using Hypothesis.

Tests the mqtt_topics.py module with automatically generated test cases
to ensure topic structure consistency and firmware parity.
"""

import os
import re
import sys

import pytest

# Try to import hypothesis
try:
    from hypothesis import given, assume, settings, example
    from hypothesis import strategies as st

    HAS_HYPOTHESIS = True
except ImportError:
    HAS_HYPOTHESIS = False

    def given(*args, **kwargs):
        def decorator(f):
            return pytest.mark.skip(reason="hypothesis not installed")(f)
        return decorator

    def example(*args, **kwargs):
        def decorator(f):
            return f
        return decorator

    def settings(**kwargs):
        def decorator(f):
            return f
        return decorator

    class st:
        @staticmethod
        def text(*args, **kwargs):
            return None
        @staticmethod
        def sampled_from(*args, **kwargs):
            return None
        @staticmethod
        def floats(*args, **kwargs):
            return None
        @staticmethod
        def integers(*args, **kwargs):
            return None
        @staticmethod
        def from_regex(*args, **kwargs):
            return None

    def assume(x):
        pass


# Import mqtt_topics module
ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from mqtt_topics import (
    build_topic,
    build_discovery_topic,
    build_discovery_config,
    get_standard_sensors,
    format_sensor_value,
)


pytestmark = pytest.mark.skipif(not HAS_HYPOTHESIS, reason="hypothesis not installed")


# Strategies for valid identifiers
if HAS_HYPOTHESIS:
    # Valid device IDs: alphanumeric with underscores and hyphens
    device_id_strategy = st.from_regex(r"[a-z][a-z0-9_-]{2,30}", fullmatch=True)

    # Valid room names
    room_name_strategy = st.from_regex(r"[A-Za-z][A-Za-z0-9 ]{0,20}", fullmatch=True)

    # Valid topic suffixes
    suffix_strategy = st.sampled_from([
        "inside/temperature",
        "inside/humidity",
        "inside/pressure",
        "battery/voltage",
        "battery/percent",
        "wifi/rssi",
        "availability",
        "status",
        "debug/json",
        "debug/memory",
        "cmd/+",
    ])


class TestBuildTopicProperties:
    """Property-based tests for build_topic function."""

    @given(
        device_id=st.from_regex(r"[a-z][a-z0-9_-]{2,20}", fullmatch=True),
        suffix=st.from_regex(r"[a-z][a-z0-9/_]{0,30}", fullmatch=True),
    )
    @settings(max_examples=200)
    def test_topic_structure(self, device_id, suffix):
        """Topic should have structure: espsensor/{device_id}/{suffix}"""
        topic = build_topic(device_id, suffix)

        assert topic.startswith("espsensor/")
        assert device_id in topic
        assert topic.endswith(suffix)

    @given(device_id=st.from_regex(r"[a-z][a-z0-9_-]{2,20}", fullmatch=True))
    @settings(max_examples=100)
    def test_topic_no_leading_slash(self, device_id):
        """Topics should never start with a slash."""
        topic = build_topic(device_id, "status")
        assert not topic.startswith("/")

    @given(device_id=st.from_regex(r"[a-z][a-z0-9_-]{2,20}", fullmatch=True))
    @settings(max_examples=100)
    def test_topic_no_trailing_slash(self, device_id):
        """Topics should never end with a slash (unless suffix ends with slash)."""
        topic = build_topic(device_id, "status")
        assert not topic.endswith("/")

    @given(device_id=st.from_regex(r"[a-z][a-z0-9_-]{2,20}", fullmatch=True))
    @settings(max_examples=100)
    def test_topic_no_double_slashes(self, device_id):
        """Topics should never contain double slashes."""
        topic = build_topic(device_id, "inside/temperature")
        assert "//" not in topic

    @given(device_id=st.from_regex(r"[a-z][a-z0-9_-]{2,20}", fullmatch=True))
    @settings(max_examples=100)
    def test_topic_no_spaces(self, device_id):
        """Topics should never contain spaces."""
        topic = build_topic(device_id, "inside/temperature")
        assert " " not in topic

    @given(
        device_id=st.from_regex(r"[a-z][a-z0-9_-]{2,20}", fullmatch=True),
        suffix=st.sampled_from([
            "inside/temperature",
            "inside/humidity",
            "battery/voltage",
            "status",
            "availability",
        ]),
    )
    @settings(max_examples=100)
    def test_topic_idempotent(self, device_id, suffix):
        """Building same topic twice should give identical results."""
        topic1 = build_topic(device_id, suffix)
        topic2 = build_topic(device_id, suffix)
        assert topic1 == topic2


class TestDiscoveryTopicProperties:
    """Property-based tests for discovery topic generation."""

    @given(
        device_id=st.from_regex(r"[a-z][a-z0-9_-]{2,20}", fullmatch=True),
        sensor_key=st.sampled_from([
            "temperature", "humidity", "pressure",
            "battery_voltage", "battery", "rssi"
        ]),
    )
    @settings(max_examples=100)
    def test_discovery_topic_structure(self, device_id, sensor_key):
        """Discovery topic should follow HA convention."""
        topic = build_discovery_topic(device_id, sensor_key)

        assert topic.startswith("homeassistant/sensor/")
        assert topic.endswith("/config")
        assert device_id in topic
        assert sensor_key in topic

    @given(device_id=st.from_regex(r"[a-z][a-z0-9_-]{2,20}", fullmatch=True))
    @settings(max_examples=50)
    def test_discovery_topic_unique_per_sensor(self, device_id):
        """Each sensor should have a unique discovery topic."""
        sensors = ["temperature", "humidity", "pressure", "battery"]
        topics = [build_discovery_topic(device_id, s) for s in sensors]

        # All topics should be unique
        assert len(topics) == len(set(topics))


class TestDiscoveryConfigProperties:
    """Property-based tests for discovery config generation."""

    @given(
        device_id=st.from_regex(r"[a-z][a-z0-9_-]{2,20}", fullmatch=True),
        room_name=st.from_regex(r"[A-Za-z][A-Za-z0-9 ]{0,15}", fullmatch=True),
    )
    @settings(max_examples=100)
    def test_discovery_config_required_fields(self, device_id, room_name):
        """Discovery config should have all required HA fields."""
        config = build_discovery_config(
            device_id=device_id,
            sensor_key="temperature",
            sensor_name=f"{room_name} Temperature",
            room_name=room_name,
            unit="°C",
            device_class="temperature",
            state_topic_suffix="inside/temperature",
        )

        required_fields = [
            "name",
            "unique_id",
            "state_topic",
            "availability_topic",
            "device_class",
            "device",
        ]

        for field in required_fields:
            assert field in config, f"Missing required field: {field}"

    @given(
        device_id=st.from_regex(r"[a-z][a-z0-9_-]{2,20}", fullmatch=True),
        room_name=st.from_regex(r"[A-Za-z][A-Za-z0-9 ]{0,15}", fullmatch=True),
    )
    @settings(max_examples=100)
    def test_unique_id_format(self, device_id, room_name):
        """Unique ID should combine device_id and sensor_key."""
        config = build_discovery_config(
            device_id=device_id,
            sensor_key="temperature",
            sensor_name=f"{room_name} Temperature",
            room_name=room_name,
            unit="°C",
            device_class="temperature",
            state_topic_suffix="inside/temperature",
        )

        unique_id = config["unique_id"]
        assert device_id in unique_id
        assert "temperature" in unique_id

    @given(device_id=st.from_regex(r"[a-z][a-z0-9_-]{2,20}", fullmatch=True))
    @settings(max_examples=50)
    def test_state_topic_matches_build_topic(self, device_id):
        """State topic in config should match build_topic output."""
        suffix = "inside/temperature"
        config = build_discovery_config(
            device_id=device_id,
            sensor_key="temperature",
            sensor_name="Test Temperature",
            room_name="Test",
            unit="°C",
            device_class="temperature",
            state_topic_suffix=suffix,
        )

        expected_topic = build_topic(device_id, suffix)
        assert config["state_topic"] == expected_topic

    @given(device_id=st.from_regex(r"[a-z][a-z0-9_-]{2,20}", fullmatch=True))
    @settings(max_examples=50)
    def test_availability_topic_format(self, device_id):
        """Availability topic should use 'availability' suffix."""
        config = build_discovery_config(
            device_id=device_id,
            sensor_key="temperature",
            sensor_name="Test Temperature",
            room_name="Test",
            unit="°C",
            device_class="temperature",
            state_topic_suffix="inside/temperature",
        )

        expected = build_topic(device_id, "availability")
        assert config["availability_topic"] == expected


class TestSensorValueFormatting:
    """Property-based tests for sensor value formatting."""

    @given(value=st.floats(min_value=-50, max_value=150, allow_nan=False, allow_infinity=False))
    @settings(max_examples=200)
    def test_temperature_formatting_precision(self, value):
        """Temperature should be formatted with 1 decimal place."""
        formatted = format_sensor_value(value, "temperature")
        if formatted:  # Not empty
            # Should have exactly 1 decimal place
            parts = formatted.split(".")
            assert len(parts) == 2
            assert len(parts[1]) == 1

    @given(value=st.floats(min_value=0, max_value=100, allow_nan=False, allow_infinity=False))
    @settings(max_examples=200)
    def test_humidity_formatting_precision(self, value):
        """Humidity should be formatted with 1 decimal place."""
        formatted = format_sensor_value(value, "humidity")
        if formatted:
            parts = formatted.split(".")
            assert len(parts) == 2
            assert len(parts[1]) == 1

    @given(value=st.floats(min_value=2.5, max_value=4.5, allow_nan=False, allow_infinity=False))
    @settings(max_examples=200)
    def test_battery_voltage_formatting_precision(self, value):
        """Battery voltage should be formatted with 2 decimal places."""
        formatted = format_sensor_value(value, "battery_voltage")
        if formatted:
            parts = formatted.split(".")
            assert len(parts) == 2
            assert len(parts[1]) == 2

    @given(value=st.integers(min_value=0, max_value=100))
    @settings(max_examples=100)
    def test_battery_percent_formatting_integer(self, value):
        """Battery percent should be formatted as integer."""
        formatted = format_sensor_value(float(value), "battery_percent")
        if formatted:
            assert "." not in formatted
            assert formatted == str(value)

    @given(value=st.integers(min_value=-100, max_value=0))
    @settings(max_examples=100)
    def test_rssi_formatting_integer(self, value):
        """RSSI should be formatted as integer (typically negative)."""
        formatted = format_sensor_value(float(value), "rssi")
        if formatted:
            assert "." not in formatted

    def test_nan_returns_empty(self):
        """NaN values should return empty string."""
        import math
        formatted = format_sensor_value(math.nan, "temperature")
        assert formatted == ""

    def test_inf_returns_empty(self):
        """Infinity values should return empty string."""
        import math
        formatted = format_sensor_value(math.inf, "temperature")
        assert formatted == ""


class TestStandardSensors:
    """Property-based tests for standard sensor configurations."""

    @given(
        device_id=st.from_regex(r"[a-z][a-z0-9_-]{2,20}", fullmatch=True),
        room_name=st.from_regex(r"[A-Za-z][A-Za-z0-9 ]{0,15}", fullmatch=True),
    )
    @settings(max_examples=50)
    def test_standard_sensors_complete(self, device_id, room_name):
        """Standard sensors should include all expected types."""
        sensors = get_standard_sensors(device_id, room_name)

        expected_sensors = [
            "temperature",
            "humidity",
            "pressure",
            "battery_voltage",
            "battery_percent",
            "rssi",
        ]

        for sensor in expected_sensors:
            assert sensor in sensors, f"Missing sensor: {sensor}"

    @given(
        device_id=st.from_regex(r"[a-z][a-z0-9_-]{2,20}", fullmatch=True),
        room_name=st.from_regex(r"[A-Za-z][A-Za-z0-9 ]{0,15}", fullmatch=True),
    )
    @settings(max_examples=50)
    def test_all_sensors_have_valid_configs(self, device_id, room_name):
        """All standard sensors should have valid discovery configs."""
        sensors = get_standard_sensors(device_id, room_name)

        for sensor_key, (config, suffix) in sensors.items():
            # Config should be a dict with required fields
            assert isinstance(config, dict)
            assert "name" in config
            assert "unique_id" in config
            assert "state_topic" in config
            assert "device_class" in config

            # Suffix should be a non-empty string
            assert isinstance(suffix, str)
            assert len(suffix) > 0


class TestFirmwareParity:
    """Tests to ensure Python implementation matches firmware."""

    def test_topic_prefix(self):
        """Topic prefix should match firmware's 'espsensor/' prefix."""
        topic = build_topic("test_device", "status")
        assert topic.startswith("espsensor/")

    def test_availability_payloads(self):
        """Availability payloads should match firmware."""
        config = build_discovery_config(
            device_id="test",
            sensor_key="temperature",
            sensor_name="Test",
            room_name="Test",
            unit="°C",
            device_class="temperature",
            state_topic_suffix="inside/temperature",
        )

        # Firmware uses "online" and "offline"
        assert config["payload_available"] == "online"
        assert config["payload_not_available"] == "offline"

    @given(device_id=st.from_regex(r"[a-z][a-z0-9_-]{2,20}", fullmatch=True))
    @settings(max_examples=30)
    def test_discovery_topic_matches_firmware_pattern(self, device_id):
        """Discovery topic should match firmware ha_discovery.cpp pattern."""
        # Firmware pattern: homeassistant/sensor/{device_id}_{sensor_key}/config
        topic = build_discovery_topic(device_id, "temperature")

        # Parse the topic
        parts = topic.split("/")
        assert parts[0] == "homeassistant"
        assert parts[1] == "sensor"
        assert parts[3] == "config"

        # The entity ID should contain device_id and sensor_key
        entity_id = parts[2]
        assert device_id in entity_id
        assert "temperature" in entity_id


class TestEdgeCases:
    """Edge case tests for MQTT topic generation."""

    def test_device_id_with_underscores(self):
        """Device IDs with underscores should work correctly."""
        topic = build_topic("office_sensor_1", "status")
        assert "office_sensor_1" in topic
        assert "//" not in topic

    def test_device_id_with_hyphens(self):
        """Device IDs with hyphens should work correctly."""
        topic = build_topic("office-sensor-1", "status")
        assert "office-sensor-1" in topic
        assert "//" not in topic

    def test_nested_suffix(self):
        """Suffixes with multiple levels should work correctly."""
        topic = build_topic("device", "debug/memory/heap")
        assert topic == "espsensor/device/debug/memory/heap"

    def test_empty_suffix(self):
        """Empty suffix should produce valid topic."""
        topic = build_topic("device", "")
        assert topic == "espsensor/device/"

    def test_special_characters_in_room_name(self):
        """Room names with special characters should be handled."""
        # Room name is used in sensor names, not topics
        sensors = get_standard_sensors("device", "Living Room 1")
        config, _ = sensors["temperature"]
        assert "Living Room 1" in config["name"]
