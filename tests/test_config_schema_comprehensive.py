import json
import os
from typing import Any, Dict

import pytest
import yaml

# Configuration files to validate
CONFIG_FILES = [
    {
        "path": "config/device.yaml",
        "schema": "device_config",
        "required": True
    },
    {
        "path": "config/device.sample.yaml",
        "schema": "device_config",
        "required": True
    },
    {
        "path": "config/ui_spec.json",
        "schema": "ui_spec",
        "required": True
    },
    {
        "path": "config/display_geometry.json",
        "schema": "display_geometry",
        "required": False  # May not exist if using UI spec
    },
    {
        "path": "config/icons",
        "schema": "icons_directory",
        "required": False
    }
]

# Device configuration schema validation
DEVICE_CONFIG_SCHEMA = {
    "required_fields": [
        "room_name",
        "wake_interval",
        "full_refresh_every",
        "outside_source",
        "wifi",
        "mqtt"
    ],
    "optional_fields": [
        "fw_version",
        "ha_entities",
        "thresholds",
        "battery",
        "active_seconds"
    ],
    "wake_interval_values": ["1h", "2h", "4h"],
    "outside_source_values": ["mqtt", "ha"],
    "full_refresh_every_range": (1, 100),
    "room_name_constraints": {
        "max_length": 32,
        "disallowed_chars": set("<>:/\\|?*#")
    }
}

# UI spec schema validation
UI_SPEC_SCHEMA = {
    "required_fields": [
        "schema",
        "canvas",
        "fonts",
        "rects",
        "iconMap",
        "components",
        "variants",
        "defaultVariant"
    ],
    "canvas_required": ["w", "h"],
    "canvas_constraints": {
        "w": {"min": 100, "max": 500},
        "h": {"min": 50, "max": 300}
    }
}

def test_device_config_files_exist():
    """Test that all required device configuration files exist"""

    root_dir = os.path.dirname(os.path.dirname(__file__))

    for config_file in CONFIG_FILES:
        if config_file["required"]:
            full_path = os.path.join(root_dir, config_file["path"])
            assert os.path.exists(full_path), f"Required config file missing: {config_file['path']}"

def test_device_config_yaml_parsing():
    """Test that device YAML files parse correctly"""

    root_dir = os.path.dirname(os.path.dirname(__file__))

    yaml_files = [f for f in CONFIG_FILES if f["path"].endswith(".yaml")]

    for config_file in yaml_files:
        full_path = os.path.join(root_dir, config_file["path"])

        if os.path.exists(full_path):
            try:
                with open(full_path, 'r') as f:
                    config = yaml.safe_load(f)

                assert isinstance(config, dict), f"Config should be dict: {config_file['path']}"
                assert config is not None, f"Config should not be None: {config_file['path']}"

            except yaml.YAMLError as e:
                pytest.fail(f"YAML parsing error in {config_file['path']}: {e}")
            except Exception as e:
                pytest.fail(f"Error reading {config_file['path']}: {e}")

def test_device_config_schema_compliance():
    """Test device configuration against schema requirements"""

    root_dir = os.path.dirname(os.path.dirname(__file__))

    for config_file in CONFIG_FILES:
        if config_file["schema"] == "device_config":
            full_path = os.path.join(root_dir, config_file["path"])

            if os.path.exists(full_path):
                with open(full_path, 'r') as f:
                    config = yaml.safe_load(f)

                _validate_device_config_schema(config, config_file["path"])

def _validate_device_config_schema(config: Dict[str, Any], file_path: str):
    """Validate device configuration against schema"""

    # Check required fields
    for field in DEVICE_CONFIG_SCHEMA["required_fields"]:
        assert field in config, f"Missing required field '{field}' in {file_path}"

    # Validate room_name
    room_name = config.get("room_name")
    assert room_name and isinstance(room_name, str), f"Invalid room_name in {file_path}"
    assert len(room_name.strip()) > 0, f"Empty room_name in {file_path}"
    assert len(room_name) <= DEVICE_CONFIG_SCHEMA["room_name_constraints"]["max_length"], \
        f"room_name too long in {file_path}"

    # Check for disallowed characters in room_name
    for char in DEVICE_CONFIG_SCHEMA["room_name_constraints"]["disallowed_chars"]:
        assert char not in room_name, f"Disallowed character '{char}' in room_name: {file_path}"

    # Validate wake_interval
    wake_interval = config.get("wake_interval")
    if isinstance(wake_interval, str):
        assert wake_interval in DEVICE_CONFIG_SCHEMA["wake_interval_values"], \
            f"Invalid wake_interval '{wake_interval}' in {file_path}"
    elif isinstance(wake_interval, int):
        assert wake_interval > 0, f"Wake interval must be positive in {file_path}"

    # Validate full_refresh_every
    full_refresh = config.get("full_refresh_every", 12)
    min_val, max_val = DEVICE_CONFIG_SCHEMA["full_refresh_every_range"]
    assert min_val <= full_refresh <= max_val, \
        f"full_refresh_every {full_refresh} out of range [{min_val}, {max_val}] in {file_path}"

    # Validate outside_source
    outside_source = config.get("outside_source")
    assert outside_source in DEVICE_CONFIG_SCHEMA["outside_source_values"], \
        f"Invalid outside_source '{outside_source}' in {file_path}"

def test_ui_spec_json_parsing():
    """Test that UI spec JSON file parses correctly"""

    root_dir = os.path.dirname(os.path.dirname(__file__))
    ui_spec_path = os.path.join(root_dir, "config", "ui_spec.json")

    if os.path.exists(ui_spec_path):
        try:
            with open(ui_spec_path, 'r') as f:
                ui_spec = json.load(f)

            assert isinstance(ui_spec, dict), "UI spec should be dict"
            assert ui_spec is not None, "UI spec should not be None"

        except json.JSONDecodeError as e:
            pytest.fail(f"JSON parsing error in UI spec: {e}")
        except Exception as e:
            pytest.fail(f"Error reading UI spec: {e}")

def test_ui_spec_schema_compliance():
    """Test UI spec against schema requirements"""

    root_dir = os.path.dirname(os.path.dirname(__file__))
    ui_spec_path = os.path.join(root_dir, "config", "ui_spec.json")

    if os.path.exists(ui_spec_path):
        with open(ui_spec_path, 'r') as f:
            ui_spec = json.load(f)

        _validate_ui_spec_schema(ui_spec)

def _validate_ui_spec_schema(ui_spec: Dict[str, Any]):
    """Validate UI spec against schema"""

    # Check required fields
    for field in UI_SPEC_SCHEMA["required_fields"]:
        assert field in ui_spec, f"Missing required field '{field}' in UI spec"

    # Validate schema version
    schema_version = ui_spec.get("schema")
    assert schema_version == "ui-spec@1", f"Unsupported schema version: {schema_version}"

    # Validate canvas
    canvas = ui_spec.get("canvas", {})
    for required in UI_SPEC_SCHEMA["canvas_required"]:
        assert required in canvas, f"Missing canvas field '{required}'"

    # Validate canvas dimensions
    canvas_w = canvas.get("w")
    canvas_h = canvas.get("h")

    w_constraints = UI_SPEC_SCHEMA["canvas_constraints"]["w"]
    h_constraints = UI_SPEC_SCHEMA["canvas_constraints"]["h"]

    assert w_constraints["min"] <= canvas_w <= w_constraints["max"], \
        f"Canvas width {canvas_w} out of range"
    assert h_constraints["min"] <= canvas_h <= h_constraints["max"], \
        f"Canvas height {canvas_h} out of range"

    # Validate rects
    rects = ui_spec.get("rects", {})
    assert isinstance(rects, dict), "rects should be dict"
    assert len(rects) > 0, "Should have at least one rect"

    for rect_name, rect_coords in rects.items():
        assert isinstance(rect_coords, list), f"Rect {rect_name} should be list"
        assert len(rect_coords) == 4, f"Rect {rect_name} should have 4 coordinates"

        x, y, w, h = rect_coords
        assert all(isinstance(coord, int) for coord in rect_coords), \
            f"Rect {rect_name} coordinates should be integers"
        assert w > 0 and h > 0, f"Rect {rect_name} dimensions should be positive"

def test_display_geometry_consistency():
    """Test consistency between display geometry and UI spec"""

    root_dir = os.path.dirname(os.path.dirname(__file__))

    ui_spec_path = os.path.join(root_dir, "config", "ui_spec.json")
    geom_path = os.path.join(root_dir, "config", "display_geometry.json")

    if os.path.exists(ui_spec_path) and os.path.exists(geom_path):
        with open(ui_spec_path, 'r') as f:
            ui_spec = json.load(f)

        with open(geom_path, 'r') as f:
            geom = json.load(f)

        # Canvas dimensions should match
        ui_canvas = ui_spec.get("canvas", {})
        geom_canvas = geom.get("canvas", {})

        if ui_canvas and geom_canvas:
            assert ui_canvas.get("w") == geom_canvas.get("w"), \
                "Canvas width mismatch between UI spec and display geometry"
            assert ui_canvas.get("h") == geom_canvas.get("h"), \
                "Canvas height mismatch between UI spec and display geometry"

def test_config_file_references():
    """Test that configuration files properly reference each other"""

    root_dir = os.path.dirname(os.path.dirname(__file__))

    # Load all config files
    configs = {}

    for config_file in CONFIG_FILES:
        if config_file["path"].endswith((".yaml", ".json")):
            full_path = os.path.join(root_dir, config_file["path"])
            if os.path.exists(full_path):
                if config_file["path"].endswith(".yaml"):
                    with open(full_path, 'r') as f:
                        configs[config_file["path"]] = yaml.safe_load(f)
                else:
                    with open(full_path, 'r') as f:
                        configs[config_file["path"]] = json.load(f)

    # Check that UI spec is referenced in device config if using ha_entities
    device_config = configs.get("config/device.yaml") or configs.get("config/device.sample.yaml")
    ui_spec = configs.get("config/ui_spec.json")

    if device_config and ui_spec:
        ha_entities = device_config.get("ha_entities", {})

        if ha_entities:
            # If using HA entities, there should be corresponding weather/icon references in UI spec
            assert "iconMap" in ui_spec, "UI spec should have iconMap when using HA entities"

            icon_map = ui_spec.get("iconMap", [])
            assert len(icon_map) > 0, "Should have weather icons when using HA entities"

def test_wifi_config_validation():
    """Test Wi-Fi configuration validation"""

    root_dir = os.path.dirname(os.path.dirname(__file__))

    device_configs = ["config/device.yaml", "config/device.sample.yaml"]

    for config_path in device_configs:
        full_path = os.path.join(root_dir, config_path)

        if os.path.exists(full_path):
            with open(full_path, 'r') as f:
                config = yaml.safe_load(f)

            wifi = config.get("wifi", {})

            if wifi:
                # Required Wi-Fi fields
                assert "ssid" in wifi, f"Missing Wi-Fi SSID in {config_path}"
                assert "password" in wifi, f"Missing Wi-Fi password in {config_path}"

                ssid = wifi.get("ssid", "")
                password = wifi.get("password", "")

                assert len(ssid.strip()) > 0, f"Empty Wi-Fi SSID in {config_path}"
                assert len(password.strip()) > 0, f"Empty Wi-Fi password in {config_path}"

                # Optional static IP validation
                if "static" in wifi:
                    static = wifi["static"]
                    required_static = ["ip", "gateway", "subnet"]

                    for field in required_static:
                        assert field in static, \
                            f"Missing static IP field '{field}' in {config_path}"
                        assert static[field].strip(), \
                            f"Empty static IP field '{field}' in {config_path}"

def test_mqtt_config_validation():
    """Test MQTT configuration validation"""

    root_dir = os.path.dirname(os.path.dirname(__file__))

    device_configs = ["config/device.yaml", "config/device.sample.yaml"]

    for config_path in device_configs:
        full_path = os.path.join(root_dir, config_path)

        if os.path.exists(full_path):
            with open(full_path, 'r') as f:
                config = yaml.safe_load(f)

            mqtt = config.get("mqtt", {})

            if mqtt:
                # If outside_source is mqtt, host is required
                outside_source = config.get("outside_source", "mqtt")

                if outside_source == "mqtt":
                    assert "host" in mqtt, \
                        f"Missing MQTT host when outside_source=mqtt in {config_path}"
                    assert mqtt["host"].strip(), f"Empty MQTT host in {config_path}"

                # Validate MQTT port if present
                if "port" in mqtt:
                    port = mqtt["port"]
                    assert isinstance(port, int), f"MQTT port should be integer in {config_path}"
                    assert 1 <= port <= 65535, f"Invalid MQTT port {port} in {config_path}"

                # Validate MQTT topic base formats
                if "base_topics" in mqtt:
                    base_topics = mqtt["base_topics"]
                    assert isinstance(base_topics, dict), \
                        f"base_topics should be dict in {config_path}"

                    if "publish" in base_topics:
                        pub_topic = base_topics["publish"]
                        assert pub_topic.strip(), f"Empty publish base topic in {config_path}"
                        assert not pub_topic.startswith("/"), \
                            f"Publish base topic should not start with / in {config_path}"
                        assert not pub_topic.endswith("/"), \
                            f"Publish base topic should not end with / in {config_path}"

                    if "subscribe" in base_topics:
                        sub_topic = base_topics["subscribe"]
                        assert sub_topic.strip(), f"Empty subscribe base topic in {config_path}"
                        assert not sub_topic.startswith("/"), \
                            f"Subscribe base topic should not start with / in {config_path}"
                        assert not sub_topic.endswith("/"), \
                            f"Subscribe base topic should not end with / in {config_path}"

def test_battery_config_validation():
    """Test battery configuration validation"""

    root_dir = os.path.dirname(os.path.dirname(__file__))

    device_configs = ["config/device.yaml", "config/device.sample.yaml"]

    for config_path in device_configs:
        full_path = os.path.join(root_dir, config_path)

        if os.path.exists(full_path):
            with open(full_path, 'r') as f:
                config = yaml.safe_load(f)

            battery = config.get("battery", {})

            if battery:
                # Required battery fields
                required_battery = ["capacity_mAh", "sleep_current_mA", "active_current_mA"]

                for field in required_battery:
                    assert field in battery, f"Missing battery field '{field}' in {config_path}"

                    value = battery[field]
                    assert isinstance(value, (int, float)), \
                        f"Battery {field} should be number in {config_path}"
                    assert value > 0, f"Battery {field} should be positive in {config_path}"

                # Validate realistic ranges
                capacity = battery.get("capacity_mAh", 0)
                sleep_current = battery.get("sleep_current_mA", 0)

                assert capacity >= 100, f"Battery capacity {capacity} too small in {config_path}"
                assert capacity <= 20000, f"Battery capacity {capacity} too large in {config_path}"
                assert sleep_current <= 1.0, \
                    f"Sleep current {sleep_current} too high in {config_path}"

                # Optional battery fields
                if "low_pct" in battery:
                    low_pct = battery["low_pct"]
                    assert 0 < low_pct <= 100, f"Invalid battery low_pct {low_pct} in {config_path}"

def test_ha_entities_config_validation():
    """Test Home Assistant entities configuration validation"""

    root_dir = os.path.dirname(os.path.dirname(__file__))

    device_configs = ["config/device.yaml", "config/device.sample.yaml"]

    for config_path in device_configs:
        full_path = os.path.join(root_dir, config_path)

        if os.path.exists(full_path):
            with open(full_path, 'r') as f:
                config = yaml.safe_load(f)

            ha_entities = config.get("ha_entities", {})

            if ha_entities:
                # Should be a dict
                assert isinstance(ha_entities, dict), f"ha_entities should be dict in {config_path}"

                # Each entity should follow HA entity ID format
                for entity_name, entity_id in ha_entities.items():
                    assert isinstance(entity_id, str), \
                        f"HA entity {entity_name} should be string in {config_path}"
                    assert entity_id.strip(), \
                        f"HA entity {entity_name} should not be empty in {config_path}"

                    # Should contain domain
                    assert "." in entity_id, \
                        f"HA entity {entity_name} missing domain in {config_path}"

                    # Should not contain spaces
                    assert " " not in entity_id, \
                        f"HA entity {entity_name} should not contain spaces in {config_path}"

                    # Domain should be valid
                    domain = entity_id.split(".")[0]
                    valid_domains = ["sensor", "weather", "binary_sensor", "switch"]
                    assert domain in valid_domains, \
                        f"Invalid domain '{domain}' for HA entity {entity_name} in {config_path}"

def test_config_value_ranges():
    """Test that configuration values are within reasonable ranges"""

    root_dir = os.path.dirname(os.path.dirname(__file__))

    device_configs = ["config/device.yaml", "config/device.sample.yaml"]

    for config_path in device_configs:
        full_path = os.path.join(root_dir, config_path)

        if os.path.exists(full_path):
            with open(full_path, 'r') as f:
                config = yaml.safe_load(f)

            # Test thresholds
            thresholds = config.get("thresholds", {})
            if thresholds:
                if "temp_degC" in thresholds:
                    temp_thresh = thresholds["temp_degC"]
                    assert 0.0 <= temp_thresh <= 5.0, \
                        f"Invalid temp threshold {temp_thresh} in {config_path}"

                if "rh_pct" in thresholds:
                    rh_thresh = thresholds["rh_pct"]
                    assert 0.0 <= rh_thresh <= 10.0, \
                        f"Invalid RH threshold {rh_thresh} in {config_path}"

            # Test battery values
            battery = config.get("battery", {})
            if battery:
                if "capacity_mAh" in battery:
                    capacity = battery["capacity_mAh"]
                    assert 500 <= capacity <= 10000, \
                        f"Unreasonable battery capacity {capacity} in {config_path}"

                if "sleep_current_mA" in battery:
                    sleep_current = battery["sleep_current_mA"]
                    assert 0.01 <= sleep_current <= 2.0, \
                        f"Unreasonable sleep current {sleep_current} in {config_path}"

def test_config_file_consistency():
    """Test consistency between configuration files"""

    root_dir = os.path.dirname(os.path.dirname(__file__))

    # Load device config
    device_path = os.path.join(root_dir, "config", "device.yaml")
    sample_path = os.path.join(root_dir, "config", "device.sample.yaml")

    configs = {}

    for path, name in [(device_path, "device"), (sample_path, "sample")]:
        if os.path.exists(path):
            with open(path, 'r') as f:
                configs[name] = yaml.safe_load(f)

    if len(configs) == 2:
        device_config = configs["device"]
        sample_config = configs["sample"]

        # Sample and device configs should have the same structure
        # (though values can differ)

        device_keys = set(device_config.keys())
        sample_keys = set(sample_config.keys())

        # Sample should have at least the same keys as device
        missing_keys = device_keys - sample_keys
        assert len(missing_keys) == 0, f"Sample config missing keys: {missing_keys}"

        # Common required fields should exist in both
        for field in DEVICE_CONFIG_SCHEMA["required_fields"]:
            assert field in device_config, f"Device config missing {field}"
            assert field in sample_config, f"Sample config missing {field}"

def test_config_version_compatibility():
    """Test that configuration files are compatible with current firmware"""

    root_dir = os.path.dirname(os.path.dirname(__file__))

    # Check if there are any version compatibility markers
    ui_spec_path = os.path.join(root_dir, "config", "ui_spec.json")

    if os.path.exists(ui_spec_path):
        with open(ui_spec_path, 'r') as f:
            ui_spec = json.load(f)

        schema_version = ui_spec.get("schema", "")

        # Should be a known version
        known_versions = ["ui-spec@1"]
        assert schema_version in known_versions, f"Unknown UI spec version: {schema_version}"
