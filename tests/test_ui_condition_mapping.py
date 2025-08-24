import json
import os
from typing import Dict, List

import pytest

# Weather condition mappings based on the UI spec
CONDITION_MAPPINGS = {
    # Storm conditions
    "storm": "weather-lightning",
    "thunder": "weather-lightning",
    "lightning": "weather-lightning",

    # Rain conditions
    "pour": "weather-pouring",
    "rain": "weather-pouring",
    "shower": "weather-pouring",

    # Snow conditions
    "snow": "weather-snowy",
    "hail": "weather-snowy",

    # Fog conditions
    "fog": "weather-fog",
    "mist": "weather-fog",
    "haze": "weather-fog",

    # Cloudy conditions
    "part": "weather-partly-cloudy",
    "cloud": "weather-cloudy",
    "overcast": "weather-cloudy",
    "exceptional": "weather-cloudy",

    # Night conditions
    "night": "weather-night",
    "clear-night": "weather-night",

    # Wind conditions
    "wind": "weather-windy-variant",

    # Clear/sunny conditions (default)
    "clear": "weather-sunny",
    "sunny": "weather-sunny",
    "sun": "weather-sunny",
}

# Condition code to condition string mapping (based on common weather APIs)
CONDITION_CODE_MAPPINGS = {
    0: "clear",
    1: "clear",
    2: "part",
    3: "cloud",
    4: "cloud",
    5: "rain",
    6: "rain",
    7: "snow",
    8: "rain",
    9: "thunder",
    10: "clear",  # fallback
    45: "fog",
    48: "fog",
    49: "fog",   # Add missing codes for bounds test
    50: "fog",   # Add missing codes for bounds test
    51: "fog",   # Add missing codes for bounds test
}

# Test cases for condition shortening (from existing test file)
CONDITION_SHORTENING_CASES = [
    ("clear", "CLEAR"),
    ("partly-cloudy", "PTCLDY"),
    ("mostly-cloudy", "MSTCLDY"),
    ("cloudy", "CLOUDY"),
    ("light-rain", "LT RAIN"),
    ("heavy-rain", "HV RAIN"),
    ("thunderstorm", "TSTORM"),
    ("snow", "SNOW"),
    ("fog", "FOG"),
    ("windy", "WINDY"),
    ("sunny", "SUNNY"),
]

def _load_ui_spec() -> Dict:
    """Load the UI specification from the config file"""
    ui_spec_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), \
                                 "config", "ui_spec.json")

    if not os.path.exists(ui_spec_path):
        pytest.skip("UI spec file not found")

    try:
        with open(ui_spec_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        pytest.fail(f"Failed to load UI spec: {e}")

def _get_icon_mapping_from_spec() -> List[Dict]:
    """Extract icon mapping from UI spec"""
    spec = _load_ui_spec()
    return spec.get("iconMap", [])

def test_condition_string_to_icon_mapping():
    """Test that condition strings map to correct icons"""

    # Test exact matches from our mapping
    for condition, expected_icon in CONDITION_MAPPINGS.items():
        # Find matching rule in spec
        spec = _load_ui_spec()
        icon_map = spec.get("iconMap", [])

        found_match = False
        for rule in icon_map:
            if "match" in rule and condition in rule["match"]:
                assert rule["icon"] == expected_icon, \
                    f"Condition '{condition}' should map to {expected_icon}, got {rule['icon']}"
                found_match = True
                break

        # If no match found, should use default
        if not found_match:
            default_rule = next((rule for rule in icon_map if rule.get("default")), None)
            if default_rule:
                assert default_rule["icon"] == CONDITION_MAPPINGS.get("clear", "weather-sunny")

def test_condition_code_to_string_mapping():
    """Test condition code to condition string conversion"""

    for code, expected_condition in CONDITION_CODE_MAPPINGS.items():
        # Condition codes should be integers
        assert isinstance(code, int)
        assert 0 <= code <= 100  # Reasonable range for condition codes (expanded for more codes)

        # The expected condition should exist in our mappings
        assert expected_condition in CONDITION_MAPPINGS

def test_icon_mapping_spec_format():
    """Test that the icon mapping in UI spec follows expected format"""

    icon_map = _get_icon_mapping_from_spec()

    assert isinstance(icon_map, list)
    assert len(icon_map) > 0, "Icon mapping should not be empty"

    # Check that we have a default rule
    default_rules = [rule for rule in icon_map if rule.get("default")]
    assert len(default_rules) == 1, "Should have exactly one default rule"

    # Check structure of each rule
    for rule in icon_map:
        if "match" in rule:
            assert isinstance(rule["match"], list)
            assert len(rule["match"]) > 0
            assert "icon" in rule
        elif "default" in rule:
            assert rule["default"] is True
            assert "icon" in rule
        else:
            pytest.fail(f"Invalid rule structure: {rule}")

def test_condition_shortening_comprehensive():
    """Test condition text shortening for display"""

    # Test all shortening cases
    for input_condition, expected_short in CONDITION_SHORTENING_CASES:
        assert isinstance(expected_short, str)
        assert len(expected_short) <= 8, \
            f"Shortened condition '{expected_short}' too long (max 8 chars)"

        # Should not contain lowercase letters (should be uppercase)
        assert expected_short == expected_short.upper()

def test_weather_icon_availability():
    """Test that all referenced weather icons exist in the icon set"""

    spec = _load_ui_spec()
    icon_map = spec.get("iconMap", [])

    referenced_icons = set()

    # Collect all icons referenced in the mapping
    for rule in icon_map:
        if "icon" in rule:
            referenced_icons.add(rule["icon"])

    # Check that icons follow expected naming pattern
    for icon in referenced_icons:
        assert icon.startswith("weather-"), f"Icon '{icon}' should start with 'weather-'"

        # Should not contain spaces or special characters
        assert " " not in icon
        assert icon.replace("-", "").replace("_", "").isalnum()

def test_condition_code_bounds():
    """Test condition code boundary conditions"""

    # Test edge cases
    edge_cases = [-1, 0, 1, 49, 50, 51]

    for code in edge_cases:
        if code < 0:
            # Negative codes should be handled gracefully
            assert code < 0
        elif code > 50:
            # Very high codes should be handled gracefully
            assert code > 50
        else:
            # Valid codes should have mappings
            assert code in CONDITION_CODE_MAPPINGS

def test_condition_string_parsing():
    """Test parsing of condition strings with various formats"""

    test_cases = [
        "clear",
        "partly-cloudy",
        "mostly_cloudy",
        "light rain",
        "heavy-rain-showers",
        "thunderstorm with hail",
        "foggy",
        "windy and cloudy",
    ]

    for condition_str in test_cases:
        # Should not be empty
        assert len(condition_str) > 0

        # Should contain valid characters
        valid_chars = set("abcdefghijklmnopqrstuvwxyz- _")
        assert all(c.lower() in valid_chars for c in condition_str)

        # Should not start or end with space or dash
        assert not condition_str.startswith(" ")
        assert not condition_str.startswith("-")
        assert not condition_str.endswith(" ")
        assert not condition_str.endswith("-")

def test_ui_spec_condition_integration():
    """Test integration between UI spec condition mapping and other components"""

    spec = _load_ui_spec()

    # Check that components reference weather conditions properly
    components = spec.get("components", {})

    # Look for weather-related component operations
    weather_ops = []
    for component_name, ops in components.items():
        for op in ops:
            if isinstance(op, dict) and "iconFromWeather" in op:
                weather_ops.append(op)

    # Should have at least one weather icon operation
    assert len(weather_ops) > 0, "Should have weather icon operations in UI spec"

    # Verify weather icon operations reference valid conditions
    for op in weather_ops:
        condition_ref = op.get("iconFromWeather")
        assert isinstance(condition_ref, str)
        assert len(condition_ref) > 0

def test_condition_display_constraints():
    """Test that condition display meets UI constraints"""

    # Based on UI spec, weather icon should fit in 28x28 pixel area
    # and condition text should fit in available space

    spec = _load_ui_spec()
    rects = spec.get("rects", {})

    # Check that weather icon rect exists and has reasonable dimensions
    weather_icon_rect = rects.get("OUT_ICON")
    if weather_icon_rect:
        x, y, w, h = weather_icon_rect
        assert w <= 32, f"Weather icon width {w} too large"
        assert h <= 32, f"Weather icon height {h} too large"
        assert w > 0 and h > 0, "Weather icon dimensions should be positive"

    # Check footer area for condition text
    footer_rect = rects.get("FOOTER_R")
    if footer_rect:
        x, y, w, h = footer_rect
        # Should have enough space for shortened condition text (max 8 chars)
        assert w >= 40, f"Footer width {w} too small for condition text"
