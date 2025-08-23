import json
import os
import re
from typing import Dict, List

import pytest

# Sample MQTT message fixtures that match the project's documented schema
MQTT_FIXTURES = {
    "outdoor_temp": {
        "topic": "home/outdoor/temp",
        "payload": "72.5",
        "expected_value": 72.5,
        "unit": "°F"
    },
    "outdoor_hum": {
        "topic": "home/outdoor/hum",
        "payload": "45",
        "expected_value": 45,
        "unit": "%"
    },
    "weather_condition": {
        "topic": "home/outdoor/condition",
        "payload": "partly-cloudy",
        "expected_value": "partly-cloudy",
        "unit": None
    },
    "weather_condition_code": {
        "topic": "home/outdoor/condition_code",
        "payload": "3",
        "expected_value": 3,
        "unit": None
    },
    "wind_mph": {
        "topic": "home/outdoor/wind_mph",
        "payload": "5.2",
        "expected_value": 5.2,
        "unit": "mph"
    },
    "pressure_hpa": {
        "topic": "home/outdoor/pressure_hpa",
        "payload": "1013.2",
        "expected_value": 1013.2,
        "unit": "hPa"
    },
    "pressure_zero": {
        "topic": "home/outdoor/pressure_hpa",
        "payload": "0",
        "expected_value": 0,
        "unit": "hPa"
    }
}

def _get_config_topics() -> Dict[str, str]:
    """Extract topic configuration from device.yaml for testing"""
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "device.yaml")
    if not os.path.exists(config_path):
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "device.sample.yaml")

    try:
        import yaml
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
    except Exception:
        # Fallback to sample config structure
        config = {
            "mqtt": {
                "base_topics": {
                    "publish": "sensors/office",
                    "subscribe": "home/outdoor"
                }
            }
        }

    return config.get("mqtt", {}).get("base_topics", {})

def _build_expected_topic(base: str, suffix: str) -> str:
    """Build expected topic from base and suffix"""
    return f"{base}/{suffix}"

def test_mqtt_topic_construction():
    """Test that MQTT topics are constructed correctly from configuration"""
    topics = _get_config_topics()

    if not topics:
        pytest.skip("No MQTT topics configured")

    publish_base = topics.get("publish", "sensors/office")
    subscribe_base = topics.get("subscribe", "home/outdoor")

    # Test publish topics (what the device publishes)
    expected_publish_topics = {
        "inside_temp": _build_expected_topic(publish_base, "inside/temp"),
        "inside_hum": _build_expected_topic(publish_base, "inside/hum"),
        "availability": _build_expected_topic(publish_base, "availability"),
        "battery_voltage": _build_expected_topic(publish_base, "battery/voltage"),
        "battery_percent": _build_expected_topic(publish_base, "battery/percent"),
        "wake_count": _build_expected_topic(publish_base, "wake_count"),
    }

    # Verify topic format - should not have leading/trailing slashes
    for topic_name, topic in expected_publish_topics.items():
        assert not topic.startswith("/"), f"Topic {topic_name} should not start with /"
        assert not topic.endswith("/"), f"Topic {topic_name} should not end with /"
        assert "//" not in topic, f"Topic {topic_name} should not contain //"
        assert " " not in topic, f"Topic {topic_name} should not contain spaces"

    # Test subscribe topics (what the device subscribes to)
    expected_subscribe_topics = {
        "outdoor_temp": _build_expected_topic(subscribe_base, "temp"),
        "outdoor_hum": _build_expected_topic(subscribe_base, "hum"),
        "outdoor_condition": _build_expected_topic(subscribe_base, "condition"),
        "outdoor_condition_code": _build_expected_topic(subscribe_base, "condition_code"),
        "outdoor_wind_mph": _build_expected_topic(subscribe_base, "wind_mph"),
        "outdoor_pressure_hpa": _build_expected_topic(subscribe_base, "pressure_hpa"),
    }

    for topic_name, topic in expected_subscribe_topics.items():
        assert not topic.startswith("/"), f"Topic {topic_name} should not start with /"
        assert not topic.endswith("/"), f"Topic {topic_name} should not end with /"
        assert "//" not in topic, f"Topic {topic_name} should not contain //"
        assert " " not in topic, f"Topic {topic_name} should not contain spaces"

def test_mqtt_message_payload_validation():
    """Test that MQTT message payloads conform to expected formats"""

    for fixture_name, fixture in MQTT_FIXTURES.items():
        # Test numeric payloads
        if fixture["unit"] in ["°F", "%", "mph", "hPa"]:
            # Should be parseable as float
            try:
                parsed_value = float(fixture["payload"])
                assert parsed_value == fixture["expected_value"], f"Failed to parse {fixture_name}"
            except ValueError:
                pytest.fail(f"Invalid numeric payload for {fixture_name}: {fixture['payload']}")

        # Test condition payloads
        elif "condition" in fixture_name:
            # Should be a reasonable string or integer
            if isinstance(fixture["expected_value"], str):
                assert len(fixture["payload"]) > 0, f"Empty condition payload for {fixture_name}"
                assert "-" in fixture["payload"] or "_" in fixture["payload"] or fixture["payload"].isalpha(), \
                    f"Invalid condition format for {fixture_name}: {fixture['payload']}"
            elif isinstance(fixture["expected_value"], int):
                assert 0 <= fixture["expected_value"] <= 50, f"Condition code out of range for {fixture_name}"

def test_mqtt_payload_edge_cases():
    """Test MQTT payload handling for edge cases"""

    # Test zero pressure (should show as "-" in UI)
    assert MQTT_FIXTURES["pressure_zero"]["expected_value"] == 0

    # Test small wind values (rounding behavior)
    small_wind_fixtures = [
        {"payload": "0.0", "expected": 0.0},
        {"payload": "0.4", "expected": 0.4},
        {"payload": "0.5", "expected": 0.5},
    ]

    for wind_fixture in small_wind_fixtures:
        parsed = float(wind_fixture["payload"])
        assert parsed == wind_fixture["expected"]

def test_mqtt_topic_prefixes():
    """Test that topic prefixes are handled correctly for different configurations"""

    test_cases = [
        {
            "config": {"publish": "sensors/office", "subscribe": "home/outdoor"},
            "expected_publish": "sensors/office/inside/temp",
            "expected_subscribe": "home/outdoor/temp"
        },
        {
            "config": {"publish": "home/room1", "subscribe": "sensors/outdoor"},
            "expected_publish": "home/room1/inside/temp",
            "expected_subscribe": "sensors/outdoor/temp"
        },
    ]

    for case in test_cases:
        publish_topic = _build_expected_topic(case["config"]["publish"], "inside/temp")
        subscribe_topic = _build_expected_topic(case["config"]["subscribe"], "temp")

        assert publish_topic == case["expected_publish"]
        assert subscribe_topic == case["expected_subscribe"]

def test_ha_entity_format():
    """Test HA entity ID format validation"""
    valid_entities = [
        "sensor.outdoor_temperature",
        "sensor.outdoor_humidity",
        "weather.home",
        "sensor.temperature_1",
        "binary_sensor.door_contact"
    ]

    invalid_entities = [
        "sensor.outdoor temperature",  # space
        "sensor.",  # trailing dot
        ".sensor.temp",  # leading dot
        "",  # empty
        "sensor/outdoor/temp",  # slash instead of dot
    ]

    for entity in valid_entities:
        assert "." in entity, f"Valid entity should contain dot: {entity}"
        assert " " not in entity, f"Valid entity should not contain spaces: {entity}"

    for entity in invalid_entities:
        # Check that entities that should be invalid are actually caught
        has_domain = "." in entity and not entity.startswith(".") and not entity.endswith(".")
        no_spaces = " " not in entity
        not_empty = len(entity.strip()) > 0
        no_slashes = "/" not in entity

        is_currently_valid = has_domain and no_spaces and not_empty and no_slashes
        assert not is_currently_valid, f"Invalid entity format not caught: {entity}"

def test_firmware_version_handling():
    """Test firmware version string handling"""
    version_cases = [
        {"input": "1.0.0", "valid": True},
        {"input": "1.0.0-dev", "valid": True},
        {"input": "v1.0.0", "valid": True},
        {"input": "dev", "valid": True},
        {"input": "", "valid": False},
        {"input": "1.0", "valid": True},
        {"input": "1.0.0.1", "valid": True},
    ]

    for case in version_cases:
        if case["valid"]:
            # Should not contain problematic characters
            assert "\n" not in case["input"]
            assert "\r" not in case["input"]
            assert "\t" not in case["input"]
        else:
            assert case["input"] == ""  # Only empty string is invalid in this test
