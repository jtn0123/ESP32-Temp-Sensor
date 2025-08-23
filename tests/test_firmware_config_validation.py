import json
import os
import re
from typing import Dict, Any

import pytest

# Wake interval configurations and their expected behavior
WAKE_INTERVAL_CONFIGS = {
    "1h": {"seconds": 3600, "valid": True},
    "2h": {"seconds": 7200, "valid": True},
    "4h": {"seconds": 14400, "valid": True},
    "3600": {"seconds": 3600, "valid": True},
    "7200": {"seconds": 7200, "valid": True},
    "14400": {"seconds": 14400, "valid": True},
    "30m": {"seconds": 1800, "valid": False},  # Not supported
    "0": {"seconds": 0, "valid": False},       # Invalid
    "-1": {"seconds": -1, "valid": False},     # Invalid
}

# Threshold configurations for validation
THRESHOLD_RANGES = {
    "temp_degC": {"min": 0.0, "max": 5.0, "default": 0.1},
    "rh_pct": {"min": 0.0, "max": 10.0, "default": 1.0},
}

def _load_device_config() -> Dict[str, Any]:
    """Load device configuration from YAML files"""
    config_paths = [
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "device.yaml"),
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "device.sample.yaml")
    ]

    for path in config_paths:
        if os.path.exists(path):
            try:
                import yaml
                with open(path, 'r') as f:
                    return yaml.safe_load(f) or {}
            except Exception:
                continue

    return {}

def _load_generated_config() -> Dict[str, str]:
    """Load generated configuration header to extract compile-time constants"""
    header_path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                              "firmware", "arduino", "src", "generated_config.h")

    if not os.path.exists(header_path):
        return {}

    defines = {}
    try:
        with open(header_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Extract #define statements
        define_pattern = r'#define\s+(\w+)\s+(.+)'
        for match in re.finditer(define_pattern, content):
            key, value = match.groups()
            defines[key] = value.strip()

    except Exception:
        pass

    return defines

def test_wake_interval_validation():
    """Test wake interval configuration validation"""

    config = _load_device_config()
    wake_interval = config.get("wake_interval")

    if wake_interval is None:
        pytest.skip("No wake_interval configured")

    # Test the configured wake interval
    if str(wake_interval) in WAKE_INTERVAL_CONFIGS:
        expected = WAKE_INTERVAL_CONFIGS[str(wake_interval)]
        assert expected["valid"], f"Wake interval {wake_interval} should be valid"
    else:
        # Custom numeric interval
        try:
            seconds = int(wake_interval)
            assert seconds > 0, f"Wake interval {wake_interval} must be positive"
        except (ValueError, TypeError):
            pytest.fail(f"Invalid wake interval format: {wake_interval}")

def test_wake_interval_compilation():
    """Test that wake interval is properly compiled into firmware"""

    defines = _load_generated_config()
    wake_interval_sec = defines.get("WAKE_INTERVAL_SEC")

    if wake_interval_sec is None:
        pytest.skip("WAKE_INTERVAL_SEC not found in generated config")

    # Should be a positive integer
    try:
        seconds = int(wake_interval_sec)
        assert seconds > 0, f"WAKE_INTERVAL_SEC {wake_interval_sec} must be positive"
        assert seconds >= 1800, f"WAKE_INTERVAL_SEC {wake_interval_sec} too short (min 30m)"
        assert seconds <= 86400, f"WAKE_INTERVAL_SEC {wake_interval_sec} too long (max 24h)"
    except (ValueError, TypeError):
        pytest.fail(f"Invalid WAKE_INTERVAL_SEC format: {wake_interval_sec}")

def test_threshold_validation():
    """Test threshold configuration validation"""

    config = _load_device_config()
    thresholds = config.get("thresholds", {})

    # Test each configured threshold
    for threshold_name, range_info in THRESHOLD_RANGES.items():
        if threshold_name in thresholds:
            threshold_value = thresholds[threshold_name]

            try:
                value = float(threshold_value)
                assert range_info["min"] <= value <= range_info["max"], \
                    f"Threshold {threshold_name}={value} out of range [{range_info['min']}, {range_info['max']}]"
                assert value >= 0, f"Threshold {threshold_name}={value} must be non-negative"
            except (ValueError, TypeError):
                pytest.fail(f"Invalid threshold value for {threshold_name}: {threshold_value}")
        else:
            # Should have default threshold
            assert range_info["default"] > 0, f"Default threshold for {threshold_name} should be positive"

def test_battery_config_validation():
    """Test battery configuration validation"""

    config = _load_device_config()
    battery = config.get("battery", {})

    # Required battery parameters
    required_params = ["capacity_mAh", "sleep_current_mA", "active_current_mA"]

    for param in required_params:
        if param in battery:
            try:
                value = float(battery[param])
                assert value > 0, f"Battery {param}={value} must be positive"
            except (ValueError, TypeError):
                pytest.fail(f"Invalid battery parameter {param}: {battery[param]}")
        else:
            pytest.fail(f"Missing required battery parameter: {param}")

    # Optional parameters
    if "low_pct" in battery:
        try:
            low_pct = float(battery["low_pct"])
            assert 0 < low_pct <= 100, f"Battery low_pct={low_pct} must be between 0 and 100"
        except (ValueError, TypeError):
            pytest.fail(f"Invalid battery low_pct: {battery['low_pct']}")

def test_full_refresh_every_validation():
    """Test full refresh every configuration"""

    config = _load_device_config()
    full_refresh_every = config.get("full_refresh_every", 12)

    try:
        value = int(full_refresh_every)
        assert value >= 1, f"full_refresh_every={value} must be at least 1"
        assert value <= 100, f"full_refresh_every={value} too large (max 100)"
    except (ValueError, TypeError):
        pytest.fail(f"Invalid full_refresh_every: {full_refresh_every}")

def test_outside_source_validation():
    """Test outside data source configuration"""

    config = _load_device_config()
    outside_source = str(config.get("outside_source", "mqtt")).lower()

    valid_sources = ["mqtt", "ha"]
    assert outside_source in valid_sources, f"outside_source={outside_source} must be one of {valid_sources}"

    # If outside_source is mqtt, MQTT config is required
    if outside_source == "mqtt":
        mqtt_config = config.get("mqtt", {})
        assert "host" in mqtt_config, "MQTT host required when outside_source=mqtt"
        assert mqtt_config["host"].strip(), "MQTT host cannot be empty"

def test_room_name_validation():
    """Test room name configuration"""

    config = _load_device_config()
    room_name = config.get("room_name")

    if room_name is not None:
        assert isinstance(room_name, str), f"room_name must be string, got {type(room_name)}"
        assert room_name.strip(), "room_name cannot be empty"
        assert len(room_name) <= 32, f"room_name too long: {len(room_name)} chars (max 32)"

        # Should not contain special characters that could break MQTT topics
        invalid_chars = set("<>:/\\|?*#")
        for char in room_name:
            assert char not in invalid_chars, f"room_name contains invalid character: {char}"

def test_mqtt_topic_construction_from_config():
    """Test that MQTT topics are built correctly from configuration"""

    config = _load_device_config()

    if "mqtt" not in config:
        pytest.skip("No MQTT configuration")

    mqtt_config = config["mqtt"]
    base_topics = mqtt_config.get("base_topics", {})

    publish_base = base_topics.get("publish", "sensors/office")
    subscribe_base = base_topics.get("subscribe", "home/outdoor")

    # Validate base topics don't have leading/trailing slashes
    for base_topic in [publish_base, subscribe_base]:
        assert not base_topic.startswith("/"), f"Base topic should not start with /: {base_topic}"
        assert not base_topic.endswith("/"), f"Base topic should not end with /: {base_topic}"
        assert "//" not in base_topic, f"Base topic should not contain //: {base_topic}"

    # Test constructed topics
    test_topics = {
        "inside_temp": f"{publish_base}/inside/temp",
        "availability": f"{publish_base}/availability",
        "outdoor_temp": f"{subscribe_base}/temp",
        "outdoor_hum": f"{subscribe_base}/hum"
    }

    for topic_name, topic in test_topics.items():
        assert len(topic) > 0, f"Topic {topic_name} should not be empty"
        assert not topic.startswith("/"), f"Topic {topic_name} should not start with /"
        assert not topic.endswith("/"), f"Topic {topic_name} should not end with /"

def test_firmware_version_handling():
    """Test firmware version configuration and handling"""

    config = _load_device_config()
    fw_version = config.get("fw_version")

    if fw_version is not None:
        assert isinstance(fw_version, str), f"fw_version must be string, got {type(fw_version)}"
        assert fw_version.strip(), "fw_version cannot be empty"

        # Should follow semantic versioning pattern
        version_pattern = r'^v?\d+\.\d+(\.\d+)?(-[a-zA-Z0-9.-]+)?$'
        assert re.match(version_pattern, fw_version), f"fw_version '{fw_version}' does not follow semantic versioning"

def test_wifi_config_validation():
    """Test Wi-Fi configuration validation"""

    config = _load_device_config()

    if "wifi" not in config:
        pytest.skip("No Wi-Fi configuration")

    wifi = config["wifi"]
    required_wifi = ["ssid", "password"]

    for param in required_wifi:
        assert param in wifi, f"Missing required Wi-Fi parameter: {param}"
        assert isinstance(wifi[param], str), f"Wi-Fi {param} must be string"
        assert wifi[param].strip(), f"Wi-Fi {param} cannot be empty"

    # Optional static IP configuration
    if "static" in wifi:
        static = wifi["static"]
        required_static = ["ip", "gateway", "subnet"]

        for param in required_static:
            assert param in static, f"Missing static IP parameter: {param}"
            assert static[param].strip(), f"Static IP {param} cannot be empty"

            # Basic IP address validation
            if param in ["ip", "gateway"]:
                parts = static[param].split(".")
                assert len(parts) == 4, f"Invalid IP format for {param}: {static[param]}"
                for part in parts:
                    assert 0 <= int(part) <= 255, f"Invalid IP octet in {param}: {part}"

def test_ha_entities_validation():
    """Test Home Assistant entity configuration"""

    config = _load_device_config()

    if "ha_entities" not in config:
        pytest.skip("No HA entities configuration")

    ha_entities = config["ha_entities"]

    # Validate entity format
    for entity_name, entity_id in ha_entities.items():
        assert isinstance(entity_id, str), f"HA entity {entity_name} must be string"
        assert entity_id.strip(), f"HA entity {entity_name} cannot be empty"

        # Should follow HA entity ID format
        assert "." in entity_id, f"HA entity {entity_name} should contain domain: {entity_id}"
        assert " " not in entity_id, f"HA entity {entity_name} should not contain spaces: {entity_id}"

        # Common domains for weather/temperature sensors
        domain = entity_id.split(".")[0]
        valid_domains = ["sensor", "weather", "binary_sensor"]
        assert domain in valid_domains, f"HA entity {entity_name} has invalid domain '{domain}': {entity_id}"
