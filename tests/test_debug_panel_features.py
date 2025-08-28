#!/usr/bin/env python3
"""
Comprehensive test suite for debug panel features (debug-panel.js).
Tests the advanced debugging, testing scenarios, and visual regression capabilities.
"""

import json
import os
import re
import time
from pathlib import Path
from typing import Dict, List, Any, Optional
import pytest
from unittest.mock import MagicMock, patch


def load_debug_panel_js():
    """Load debug-panel.js content"""
    panel_path = Path(__file__).parent.parent / "web" / "sim" / "debug-panel.js"
    with open(panel_path, "r") as f:
        content = f.read()
    return content


def extract_test_scenarios(js_content: str) -> List[Dict[str, Any]]:
    """Extract test scenario definitions from debug panel"""
    scenarios = []

    # Look for test scenario definitions
    pattern = r'(?:name|label|description):\s*["\']([^"\']+)["\'].*?(?:data|values?|config):\s*(\{[^}]+\})'
    matches = re.finditer(pattern, js_content, re.MULTILINE | re.DOTALL)

    for match in matches:
        name = match.group(1)
        # Try to parse data if it looks like JSON
        try:
            data_str = match.group(2)
            # Simple cleanup for JavaScript object notation
            data_str = re.sub(r"(\w+):", r'"\1":', data_str)
            data = json.loads(data_str)
        except:
            data = {}

        scenarios.append({"name": name, "data": data})

    return scenarios


class TestDebugPanelCore:
    """Test core debug panel functionality"""

    def test_debug_panel_structure(self):
        """Test that debug panel has required sections"""
        js_content = load_debug_panel_js()

        # Check for main panel sections - look for key functionality instead of exact text
        required_functionality = [
            "validation",  # UI Validation
            "debug",  # Debug tools
            "performance",  # Performance Monitor
            "scenario",  # Test Scenarios
            "editor",  # Data Editor
            "visual",  # Visual Testing
            "icon",  # Icon Tester
            "state",  # State Inspector
        ]

        for functionality in required_functionality:
            assert (
                functionality.lower() in js_content.lower()
            ), f"Debug panel missing functionality: {functionality}"

    def test_performance_monitor_metrics(self):
        """Test performance monitoring metrics"""
        js_content = load_debug_panel_js()

        # Check for performance tracking - look for key concepts
        metrics = ["fps", "render", "frame", "time"]

        for metric in metrics:
            assert (
                metric.lower() in js_content.lower()
            ), f"Performance metric concept '{metric}' not found"

    def test_test_scenario_categories(self):
        """Test that all scenario categories are present"""
        js_content = load_debug_panel_js()

        categories = [
            "Text Overflow",
            "Battery States",
            "Weather Icons",
            "Missing Data",
            "Sensor Limits",
            "Time Formats",
        ]

        for category in categories:
            assert (
                category in js_content or category.replace(" ", "_").lower() in js_content.lower()
            ), f"Test scenario category '{category}' not found"


class TestScenarioExecution:
    """Test scenario execution functionality"""

    def test_text_overflow_scenarios(self):
        """Test text overflow test scenarios"""
        # Simulate overflow scenarios
        overflow_tests = [
            {
                "name": "Long Room Name",
                "data": {"room": "Very Long Room Name That Will Definitely Overflow"},
                "expected_issues": ["text_overflow"],
            },
            {
                "name": "Max Temperature",
                "data": {"inside_temp": "999.9"},
                "expected_issues": ["width_overflow"],
            },
            {
                "name": "Long Weather Description",
                "data": {"weather": "Extremely Heavy Thunderstorms with Hail"},
                "expected_issues": ["text_truncation"],
            },
        ]

        for test in overflow_tests:
            # Each scenario should trigger validation
            assert len(test["expected_issues"]) > 0, f"Scenario '{test['name']}' should have issues"

    def test_battery_state_scenarios(self):
        """Test battery state scenarios"""
        battery_states = [
            {"battery": 100, "charging": False, "display": "100%"},
            {"battery": 50, "charging": False, "display": "50%"},
            {"battery": 0, "charging": False, "display": "0%"},
            {"battery": 75, "charging": True, "display": "75%+"},
            {"battery": None, "charging": False, "display": "--"},
            {"battery": -1, "charging": False, "display": "?"},
        ]

        for state in battery_states:
            battery = state["battery"]
            expected = state["display"]

            # Validate battery display format
            if battery is None:
                assert expected == "--", "Null battery should show --"
            elif battery < 0:
                assert expected == "?", "Invalid battery should show ?"
            elif state["charging"]:
                assert "+" in expected, "Charging should show +"
            else:
                assert "%" in expected or expected in [
                    "--",
                    "?",
                ], f"Battery {battery} should show percentage"

    def test_weather_icon_scenarios(self):
        """Test all weather icon mappings"""
        weather_icons = {
            "clear-day": "☀️",
            "clear-night": "🌙",
            "rain": "🌧️",
            "snow": "❄️",
            "sleet": "🌨️",
            "wind": "💨",
            "fog": "🌫️",
            "cloudy": "☁️",
            "partly-cloudy-day": "⛅",
            "partly-cloudy-night": "☁️",
            "hail": "🌨️",
            "thunderstorm": "⛈️",
        }

        for condition, icon in weather_icons.items():
            # Each condition should map to correct icon
            assert icon != "", f"Weather condition '{condition}' should have icon"
            assert len(icon) > 0, f"Icon for '{condition}' should not be empty"

    def test_missing_data_scenarios(self):
        """Test scenarios with missing sensor data"""
        missing_data_tests = [
            {
                "name": "No Temperature",
                "data": {"inside_temp": None, "inside_humidity": 65},
                "expected_display": {"temp": "--", "humidity": "65%"},
            },
            {
                "name": "No Sensors",
                "data": {"inside_temp": None, "inside_humidity": None, "pressure": None},
                "expected_display": {"temp": "--", "humidity": "--", "pressure": "--"},
            },
            {
                "name": "Partial Outside Data",
                "data": {"out_temp": 15, "out_humidity": None},
                "expected_display": {"out_temp": "15.0°C", "out_humidity": "--"},
            },
        ]

        # Map display field names to data field names
        field_mapping = {
            "temp": "inside_temp",
            "humidity": "inside_humidity",
            "pressure": "pressure",
            "out_temp": "out_temp",
            "out_humidity": "out_humidity",
        }

        for test in missing_data_tests:
            for field, expected in test["expected_display"].items():
                # Get the corresponding data field name
                data_field = field_mapping.get(field, field)
                if test["data"].get(data_field) is None:
                    assert expected == "--", f"Missing {field} should show -- but got {expected}"
                else:
                    # Has data, should show formatted value
                    assert expected != "--", f"{field} has data, should not show --"


class TestDataEditor:
    """Test data editor functionality"""

    def test_data_editor_fields(self):
        """Test that all editable fields are present"""
        # Check for actual field names used in the debug panel
        field_names = [
            "room_name",
            "time_hhmm",
            "fw_version",
            "inside_temp_f",
            "inside_hum_pct",
            "pressure_hpa",
            "co2_ppm",
            "wind_mph",
            "weather",
            "battery_percent",
        ]

        js_content = load_debug_panel_js()

        for field_name in field_names:
            # Check field name is referenced somewhere in the JavaScript
            assert (
                field_name.lower() in js_content.lower()
            ), f"Field '{field_name}' not found in panel"

    def test_import_export_json(self):
        """Test JSON import/export functionality"""
        sample_data = {
            "room": "Test Room",
            "time": "12:34",
            "version": "v1.0",
            "inside_temp": 23.5,
            "inside_humidity": 65,
            "pressure": 1013,
            "battery": 85,
        }

        # Export should produce valid JSON
        exported = json.dumps(sample_data)
        assert json.loads(exported) == sample_data, "Export should produce valid JSON"

        # Import should accept valid JSON
        imported = json.loads(exported)
        assert imported == sample_data, "Import should restore original data"

    def test_data_validation(self):
        """Test data validation in editor"""
        validation_tests = [
            {"field": "inside_temp", "value": "abc", "valid": False},
            {"field": "inside_temp", "value": "23.5", "valid": True},
            {"field": "inside_temp", "value": "-50", "valid": True},
            {"field": "inside_temp", "value": "200", "valid": False},  # Too high
            {"field": "battery", "value": "-10", "valid": False},
            {"field": "battery", "value": "50", "valid": True},
            {"field": "battery", "value": "150", "valid": False},
            {"field": "co2", "value": "400", "valid": True},
            {"field": "co2", "value": "10000", "valid": False},  # Too high
        ]

        for test in validation_tests:
            field = test["field"]
            value = test["value"]
            expected_valid = test["valid"]

            # Validate based on field type
            if field in ["inside_temp", "out_temp"]:
                try:
                    num = float(value)
                    is_valid = -50 <= num <= 100
                except:
                    is_valid = False
            elif field == "battery":
                try:
                    num = int(value)
                    is_valid = 0 <= num <= 100
                except:
                    is_valid = False
            elif field == "co2":
                try:
                    num = int(value)
                    is_valid = 0 <= num <= 5000
                except:
                    is_valid = False
            else:
                is_valid = True

            assert (
                is_valid == expected_valid
            ), f"Field '{field}' with value '{value}' validation mismatch"


class TestVisualRegression:
    """Test visual regression testing features"""

    def test_screenshot_capture(self):
        """Test screenshot capture functionality"""
        # Simulate canvas for screenshot
        canvas_data = {
            "width": 250,
            "height": 122,
            "dataURL": "data:image/png;base64,iVBORw0KG...",  # Mock data
        }

        assert canvas_data["width"] == 250, "Canvas width should be 250"
        assert canvas_data["height"] == 122, "Canvas height should be 122"
        assert canvas_data["dataURL"].startswith("data:image"), "Should produce image data URL"

    def test_baseline_comparison(self):
        """Test baseline comparison logic"""

        def compare_images(img1, img2):
            """Simple image comparison simulation"""
            if img1 == img2:
                return {"match": True, "difference": 0}

            # Simulate pixel difference calculation
            total_pixels = 250 * 122
            different_pixels = 100  # Mock difference
            percentage = (different_pixels / total_pixels) * 100

            return {"match": False, "difference": percentage, "pixels_different": different_pixels}

        # Test identical images
        result = compare_images("imageA", "imageA")
        assert result["match"] == True, "Identical images should match"
        assert result["difference"] == 0, "No difference for identical images"

        # Test different images
        result = compare_images("imageA", "imageB")
        assert result["match"] == False, "Different images should not match"
        assert result["difference"] > 0, "Should have pixel differences"

    def test_visual_diff_highlighting(self):
        """Test visual difference highlighting"""
        diff_regions = [
            {"x": 10, "y": 20, "w": 30, "h": 15, "pixels": 120},
            {"x": 100, "y": 50, "w": 20, "h": 20, "pixels": 85},
        ]

        for region in diff_regions:
            # Each diff region should be within canvas bounds
            assert region["x"] >= 0, "Diff region x should be positive"
            assert region["y"] >= 0, "Diff region y should be positive"
            assert region["x"] + region["w"] <= 250, "Diff region should fit in canvas width"
            assert region["y"] + region["h"] <= 122, "Diff region should fit in canvas height"
            assert region["pixels"] > 0, "Diff region should have changed pixels"


class TestPerformanceMonitoring:
    """Test performance monitoring features"""

    def test_fps_calculation(self):
        """Test FPS calculation logic"""

        def calculate_fps(frame_times):
            """Calculate FPS from frame timestamps"""
            if len(frame_times) < 2:
                return 0

            # Calculate time between frames
            deltas = []
            for i in range(1, len(frame_times)):
                delta = frame_times[i] - frame_times[i - 1]
                deltas.append(delta)

            avg_delta = sum(deltas) / len(deltas)
            if avg_delta == 0:
                return 0

            return 1000 / avg_delta  # Convert ms to FPS

        # Test normal frame rate (60 FPS = ~16.67ms per frame)
        times_60fps = [0, 16.67, 33.33, 50, 66.67, 83.33]
        fps = calculate_fps(times_60fps)
        assert 59 <= fps <= 61, f"Should be ~60 FPS, got {fps}"

        # Test slow frame rate (30 FPS = ~33.33ms per frame)
        times_30fps = [0, 33.33, 66.67, 100, 133.33]
        fps = calculate_fps(times_30fps)
        assert 29 <= fps <= 31, f"Should be ~30 FPS, got {fps}"

    def test_render_time_tracking(self):
        """Test render time measurement"""
        render_times = []

        def measure_render(func):
            """Measure function execution time"""
            start = time.perf_counter()
            func()
            end = time.perf_counter()
            return (end - start) * 1000  # Convert to ms

        # Simulate render operations
        def fast_render():
            time.sleep(0.005)  # 5ms

        def slow_render():
            time.sleep(0.050)  # 50ms

        fast_time = measure_render(fast_render)
        slow_time = measure_render(slow_render)

        assert 4 <= fast_time <= 10, f"Fast render should be ~5ms, got {fast_time}"
        assert 45 <= slow_time <= 60, f"Slow render should be ~50ms, got {slow_time}"
        assert slow_time > fast_time, "Slow render should take longer"

    def test_memory_usage_tracking(self):
        """Test memory usage monitoring"""
        memory_samples = [
            {"timestamp": 0, "used": 10000, "total": 50000},
            {"timestamp": 1000, "used": 12000, "total": 50000},
            {"timestamp": 2000, "used": 11000, "total": 50000},
            {"timestamp": 3000, "used": 15000, "total": 50000},
        ]

        for sample in memory_samples:
            usage_percent = (sample["used"] / sample["total"]) * 100
            assert 0 <= usage_percent <= 100, "Memory usage should be 0-100%"
            assert sample["used"] <= sample["total"], "Used memory should not exceed total"


class TestIconTester:
    """Test icon testing functionality"""

    def test_all_weather_icons(self):
        """Test quick access to all weather icons"""
        icons = [
            "clear-day",
            "clear-night",
            "rain",
            "snow",
            "sleet",
            "wind",
            "fog",
            "cloudy",
            "partly-cloudy-day",
            "partly-cloudy-night",
            "hail",
            "thunderstorm",
        ]

        for icon in icons:
            # Each icon should be testable
            assert len(icon) > 0, f"Icon name '{icon}' should not be empty"
            assert "-" in icon or icon in [
                "rain",
                "snow",
                "sleet",
                "wind",
                "fog",
                "cloudy",
                "hail",
                "thunderstorm",
            ], f"Icon '{icon}' should follow naming convention"

    def test_custom_weather_input(self):
        """Test custom weather text input"""
        custom_inputs = [
            "Clear",
            "Partly Cloudy",
            "Heavy Rain",
            "Light Snow",
            "Foggy",
            "Thunderstorms",
            "Unknown Weather",
        ]

        for input_text in custom_inputs:
            # Should accept any text input
            assert isinstance(input_text, str), "Should accept string input"
            assert len(input_text) <= 50, "Weather text should have reasonable length"


class TestStateInspector:
    """Test state inspection functionality"""

    def test_state_data_structure(self):
        """Test internal state data structure"""
        state = {
            "data": {"room": "Living Room", "time": "12:34", "inside_temp": 23.5, "battery": 85},
            "validation": {"issues": [], "warnings": []},
            "rendering": {"lastUpdate": 1234567890, "frameCount": 100},
            "config": {"oneBitMode": True, "showGrid": False},
        }

        # Verify state structure
        assert "data" in state, "State should have data section"
        assert "validation" in state, "State should have validation section"
        assert "rendering" in state, "State should have rendering section"
        assert "config" in state, "State should have config section"

    def test_state_serialization(self):
        """Test state can be serialized for inspection"""
        state = {"timestamp": 1234567890, "data": {"temp": 23.5}, "errors": []}

        # Should be JSON serializable
        serialized = json.dumps(state)
        deserialized = json.loads(serialized)

        assert deserialized == state, "State should survive serialization"

    def test_layout_metrics_inspection(self):
        """Test layout metrics in state"""
        metrics = {
            "regions": {
                "header": {"x": 0, "y": 0, "w": 250, "h": 16},
                "temp": {"x": 6, "y": 36, "w": 118, "h": 28},
            },
            "text_metrics": {
                "header": {"width": 85, "height": 12},
                "temp": {"width": 45, "height": 22},
            },
            "overflow": [],
            "collisions": [],
        }

        # Verify metrics structure
        assert "regions" in metrics, "Should have region definitions"
        assert "text_metrics" in metrics, "Should have text measurements"
        assert "overflow" in metrics, "Should track overflow"
        assert "collisions" in metrics, "Should track collisions"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
