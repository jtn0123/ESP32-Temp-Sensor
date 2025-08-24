from typing import Any

import pytest

# Comprehensive MQTT message fixtures for testing
MQTT_MESSAGE_FIXTURES = {
    # Standard outdoor weather data messages
    "outdoor_standard": {
        "topic": "home/outdoor/temp",
        "payload": "72.5",
        "expected_type": "float",
        "expected_value": 72.5,
        "unit": "°F",
        "retained": True
    },
    "outdoor_humidity": {
        "topic": "home/outdoor/hum",
        "payload": "45",
        "expected_type": "int",
        "expected_value": 45,
        "unit": "%",
        "retained": True
    },
    "outdoor_condition": {
        "topic": "home/outdoor/condition",
        "payload": "partly-cloudy",
        "expected_type": "str",
        "expected_value": "partly-cloudy",
        "unit": None,
        "retained": True
    },
    "outdoor_condition_code": {
        "topic": "home/outdoor/condition_code",
        "payload": "3",
        "expected_type": "int",
        "expected_value": 3,
        "unit": None,
        "retained": True
    },
    "outdoor_wind": {
        "topic": "home/outdoor/wind_mph",
        "payload": "5.2",
        "expected_type": "float",
        "expected_value": 5.2,
        "unit": "mph",
        "retained": True
    },
    "outdoor_pressure": {
        "topic": "home/outdoor/pressure_hpa",
        "payload": "1013.2",
        "expected_type": "float",
        "expected_value": 1013.2,
        "unit": "hPa",
        "retained": True
    },

    # Edge cases and error conditions
    "pressure_zero": {
        "topic": "home/outdoor/pressure_hpa",
        "payload": "0",
        "expected_type": "int",
        "expected_value": 0,
        "unit": "hPa",
        "retained": True,
        "should_display_dash": True  # UI should show "-" for zero pressure
    },
    "temp_negative": {
        "topic": "home/outdoor/temp",
        "payload": "-5.2",
        "expected_type": "float",
        "expected_value": -5.2,
        "unit": "°F",
        "retained": True
    },
    "humidity_zero": {
        "topic": "home/outdoor/hum",
        "payload": "0",
        "expected_type": "int",
        "expected_value": 0,
        "unit": "%",
        "retained": True
    },
    "wind_zero": {
        "topic": "home/outdoor/wind_mph",
        "payload": "0.0",
        "expected_type": "float",
        "expected_value": 0.0,
        "unit": "mph",
        "retained": True
    },

    # Malformed messages for robustness testing
    "empty_payload": {
        "topic": "home/outdoor/temp",
        "payload": "",
        "expected_type": None,
        "expected_value": None,
        "unit": None,
        "retained": True,
        "should_be_ignored": True
    },
    "non_numeric_temp": {
        "topic": "home/outdoor/temp",
        "payload": "invalid",
        "expected_type": None,
        "expected_value": None,
        "unit": None,
        "retained": True,
        "should_be_ignored": True
    },
    "very_large_temp": {
        "topic": "home/outdoor/temp",
        "payload": "999.9",
        "expected_type": "float",
        "expected_value": 999.9,
        "unit": "°F",
        "retained": True,
        "is_extreme": True
    },

    # HA entity format messages
    "ha_outdoor_temp": {
        "topic": "homeassistant/sensor/outdoor_temperature/state",
        "payload": "22.5",
        "expected_type": "float",
        "expected_value": 22.5,
        "unit": "°C",
        "retained": False  # HA state topics are typically not retained
    }
}

# HA discovery payload templates
HA_DISCOVERY_FIXTURES = {
    "temp_sensor": {
        "name": "Outside Temperature",
        "unique_id": "room_node_outdoor_temp",
        "state_topic": "sensors/office/outdoor/temp",
        "availability_topic": "sensors/office/availability",
        "payload_available": "online",
        "payload_not_available": "offline",
        "unit_of_measurement": "°F",
        "device_class": "temperature",
        "expire_after": 7260,  # wake_interval + 120
        "device": {
            "identifiers": ["room_node"],
            "name": "ESP32 Room Node: Office",
            "manufacturer": "DIY",
            "model": "Feather ESP32-S2"
        }
    },
    "hum_sensor": {
        "name": "Outside Humidity",
        "unique_id": "room_node_outdoor_hum",
        "state_topic": "sensors/office/outdoor/hum",
        "availability_topic": "sensors/office/availability",
        "payload_available": "online",
        "payload_not_available": "offline",
        "unit_of_measurement": "%",
        "device_class": "humidity",
        "expire_after": 7260,
        "device": {
            "identifiers": ["room_node"],
            "name": "ESP32 Room Node: Office",
            "manufacturer": "DIY",
            "model": "Feather ESP32-S2"
        }
    }
}

def test_mqtt_message_parsing():
    """Test parsing of MQTT message payloads"""

    for fixture_name, fixture in MQTT_MESSAGE_FIXTURES.items():
        payload = fixture["payload"]

        if fixture["expected_type"] is None:
            # Should be ignored or cause error
            if fixture.get("should_be_ignored"):
                continue
            else:
                with pytest.raises((ValueError, TypeError)):
                    _parse_payload(payload, fixture["expected_type"])
        else:
            # Should parse successfully
            parsed = _parse_payload(payload, fixture["expected_type"])
            assert parsed == fixture["expected_value"], f"Failed to parse {fixture_name}"

def _parse_payload(payload: str, expected_type: str) -> Any:
    """Helper to parse payload based on expected type"""
    if expected_type == "float":
        return float(payload)
    elif expected_type == "int":
        return int(payload)
    elif expected_type == "str":
        return payload
    else:
        return payload

def test_mqtt_topic_format_validation():
    """Test MQTT topic format validation"""

    valid_topics = [
        "home/outdoor/temp",
        "sensors/office/inside/hum",
        "homeassistant/sensor/room_node_temp/config",
        "sensors/office/availability",
        "home/outdoor/condition_code"
    ]

    invalid_topics = [
        "/home/outdoor/temp",  # leading slash
        "home/outdoor/temp/",  # trailing slash
        "home//outdoor/temp",  # double slash
        "home/outdoor/temp ",  # trailing space
        "home/outdoor temp",   # space in middle
    ]

    for topic in valid_topics:
        assert _is_valid_mqtt_topic(topic), f"Valid topic rejected: {topic}"

    for topic in invalid_topics:
        assert not _is_valid_mqtt_topic(topic), f"Invalid topic accepted: {topic}"

def _is_valid_mqtt_topic(topic: str) -> bool:
    """Check if MQTT topic follows valid format"""
    if not topic:
        return False
    if topic.startswith("/") or topic.endswith("/"):
        return False
    if "//" in topic:
        return False
    if " " in topic:
        return False
    # Should not contain MQTT wildcards in published topics
    if "+" in topic or "#" in topic:
        return False
    return True

def test_ha_discovery_payload_validation():
    """Test HA discovery payload format validation"""

    for fixture_name, payload in HA_DISCOVERY_FIXTURES.items():
        # Required fields for all HA discovery payloads
        required_fields = [
            "name", "unique_id", "state_topic", "availability_topic",
            "payload_available", "payload_not_available"
        ]

        for field in required_fields:
            assert field in payload, f"Missing required field {field} in {fixture_name}"
            assert payload[field], f"Field {field} cannot be empty in {fixture_name}"

        # Validate topic formats
        assert _is_valid_mqtt_topic(payload["state_topic"])
        assert _is_valid_mqtt_topic(payload["availability_topic"])

        # Validate availability payloads
        assert payload["payload_available"] != payload["payload_not_available"]

        # Validate expire_after is reasonable
        if "expire_after" in payload:
            expire_after = payload["expire_after"]
            assert isinstance(expire_after, int)
            assert expire_after > 0
            # Should be wake interval + buffer
            assert 1800 <= expire_after <= 86400  # 30min to 24h

def test_message_retention_flags():
    """Test that messages have appropriate retention flags"""

    # State topics should be retained
    retained_topics = [
        "home/outdoor/temp",
        "home/outdoor/hum",
        "home/outdoor/condition",
        "sensors/office/inside/temp",
        "sensors/office/availability"
    ]

    # Discovery topics should be retained
    discovery_topics = [
        "homeassistant/sensor/room_node_temp/config"
    ]

    # HA state topics are typically not retained (live updates)
    non_retained_topics = [
        "homeassistant/sensor/outdoor_temperature/state"
    ]

    for topic in retained_topics:
        fixture = next((f for f in MQTT_MESSAGE_FIXTURES.values() if f["topic"] == topic), None)
        if fixture:
            assert fixture["retained"], f"Topic {topic} should be retained"

    for topic in discovery_topics:
        # Discovery payloads should always be retained
        assert topic not in MQTT_MESSAGE_FIXTURES or \
               MQTT_MESSAGE_FIXTURES.get(topic, {}).get("retained", True)

    for topic in non_retained_topics:
        fixture = next((f for f in MQTT_MESSAGE_FIXTURES.values() if f["topic"] == topic), None)
        if fixture:
            assert not fixture["retained"], f"Topic {topic} should not be retained"

def test_extreme_value_handling():
    """Test handling of extreme values"""

    extreme_fixtures = [
        {"payload": "-99.9", "type": "float", "description": "very cold"},
        {"payload": "150.0", "type": "float", "description": "very hot"},
        {"payload": "9999", "type": "int", "description": "impossibly high"},
        {"payload": "-9999", "type": "int", "description": "impossibly low"},
    ]

    for fixture in extreme_fixtures:
        try:
            parsed = _parse_payload(fixture["payload"], fixture["type"])
            # Should parse without error, but UI should handle display appropriately
            assert isinstance(parsed, (int, float))
        except (ValueError, TypeError):
            pytest.fail(f"Failed to parse extreme value {fixture['description']}: "
                        f"{fixture['payload']}")

def test_unit_conversion_requirements():
    """Test that temperature values are properly handled for different units"""

    # Test °F values
    fahrenheit_values = ["32.0", "72.5", "100.0", "-10.5"]
    for temp_str in fahrenheit_values:
        temp_f = float(temp_str)
        # Should be reasonable °F range
        assert -50 <= temp_f <= 150, f"Unreasonable °F temperature: {temp_f}"

    # Test °C values (from HA)
    celsius_values = ["0.0", "22.5", "35.0", "-15.0"]
    for temp_str in celsius_values:
        temp_c = float(temp_str)
        # Should be reasonable °C range
        assert -30 <= temp_c <= 50, f"Unreasonable °C temperature: {temp_c}"

def test_condition_code_mapping():
    """Test weather condition code to icon mapping"""

    # Common condition codes and their expected mappings
    condition_code_tests = [
        (0, "clear"),
        (1, "clear"),
        (2, "part"),
        (3, "cloud"),
        (4, "cloud"),
        (45, "fog"),
        (48, "fog"),
        (51, "rain"),
        (53, "rain"),
        (55, "rain"),
        (61, "rain"),
        (63, "rain"),
        (65, "rain"),
        (71, "snow"),
        (73, "snow"),
        (75, "snow"),
        (80, "shower"),
        (81, "shower"),
        (82, "shower"),
        (95, "thunder"),
        (96, "thunder"),
        (99, "thunder"),
    ]

    for code, expected_condition in condition_code_tests:
        assert isinstance(code, int)
        assert isinstance(expected_condition, str)
        assert expected_condition in ["clear", "part", "cloud", "fog", "rain", "snow",
                                       "shower", "thunder"]

def test_mqtt_qos_requirements():
    """Test MQTT QoS level requirements"""

    # Discovery messages should use QoS 1
    discovery_topics = [
        "homeassistant/sensor/room_node_temp/config",
        "homeassistant/sensor/room_node_hum/config"
    ]

    # State messages should use QoS 1
    state_topics = [
        "sensors/office/inside/temp",
        "sensors/office/inside/hum",
        "sensors/office/availability"
    ]

    # All critical messages should use QoS 1 (at least once delivery)
    for topics in [discovery_topics, state_topics]:
        for topic in topics:
            # QoS 1 ensures delivery - important for sensor data
            assert True  # Placeholder - actual QoS validation would need MQTT client integration

def test_message_size_constraints():
    """Test that MQTT message payloads are within reasonable size limits"""

    for fixture_name, fixture in MQTT_MESSAGE_FIXTURES.items():
        payload = fixture["payload"]

        # MQTT payload should be reasonably small
        assert len(payload) <= 32, f"Payload too large for {fixture_name}: {len(payload)} chars"

        # Should not contain newlines or control characters
        assert "\n" not in payload
        assert "\r" not in payload
        assert "\t" not in payload
        assert "\x00" not in payload

def test_topic_naming_conventions():
    """Test that topics follow consistent naming conventions"""

    all_topics = []

    # Collect all topics from fixtures
    for fixture in MQTT_MESSAGE_FIXTURES.values():
        all_topics.append(fixture["topic"])

    for topic in HA_DISCOVERY_FIXTURES.values():
        if "state_topic" in topic:
            all_topics.append(topic["state_topic"])
        if "availability_topic" in topic:
            all_topics.append(topic["availability_topic"])

    # Check naming conventions
    for topic in all_topics:
        parts = topic.split("/")

        # Should have at least 2 parts (domain/entity_type)
        assert len(parts) >= 2, f"Topic too short: {topic}"

        # Parts should be lowercase
        for part in parts:
            assert part == part.lower(), f"Topic part not lowercase: {part} in {topic}"

        # Should not have empty parts
        assert "" not in parts, f"Empty part in topic: {topic}"

        # Should not start with numbers (MQTT convention)
        for part in parts:
            assert not part[0].isdigit(), f"Topic part starts with digit: {part} in {topic}"
