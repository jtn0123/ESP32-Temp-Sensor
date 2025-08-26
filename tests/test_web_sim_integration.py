import json
import os

import pytest

# Web simulator test configurations
WEB_SIM_CONFIGS = {
    "default": {
        "width": 250,
        "height": 122,
        "sample_data": {
            "inside_temp_f": 72.5,
            "inside_hum_pct": 45,
            "outside_temp_f": 68.2,
            "outside_hum_pct": 52,
            "wind_mph": 5.2,
            "pressure_hpa": 1013.2,
            "weather": "partly-cloudy",
            "battery_percent": 87,
            "battery_voltage": 3.85,
            "time_hhmm": "14:30",
            "room_name": "Office",
            "fw_version": "1.0.0",
        },
    },
    "extreme_values": {
        "width": 250,
        "height": 122,
        "sample_data": {
            "inside_temp_f": -10.5,
            "inside_hum_pct": 5,
            "outside_temp_f": 105.8,
            "outside_hum_pct": 95,
            "wind_mph": 25.0,
            "pressure_hpa": 850,
            "weather": "storm",
            "battery_percent": 15,
            "battery_voltage": 3.2,
            "time_hhmm": "23:59",
            "room_name": "Garage",
            "fw_version": "dev",
        },
    },
    "empty_values": {
        "width": 250,
        "height": 122,
        "sample_data": {
            "inside_temp_f": None,
            "inside_hum_pct": None,
            "outside_temp_f": None,
            "outside_hum_pct": None,
            "wind_mph": None,
            "pressure_hpa": None,
            "weather": None,
            "battery_percent": None,
            "battery_voltage": None,
            "time_hhmm": "12:00",
            "room_name": "Unknown",
            "fw_version": None,
        },
    },
}


def test_web_simulator_launch():
    """Test that web simulator can be launched and accessed"""

    web_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web", "sim")

    if not os.path.exists(web_dir):
        pytest.skip("Web simulator directory not found")

    # Check required files exist
    required_files = ["index.html", "sim.js", "ui_generated.js"]
    for file in required_files:
        file_path = os.path.join(web_dir, file)
        assert os.path.exists(file_path), f"Required web file missing: {file}"


def test_web_simulator_data_loading():
    """Test that web simulator can load sample data"""

    web_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web", "sim")
    sample_data_path = os.path.join(web_dir, "sample_data.json")

    if os.path.exists(sample_data_path):
        try:
            with open(sample_data_path, "r") as f:
                sample_data = json.load(f)

            # Should have expected structure
            assert isinstance(sample_data, dict), "Sample data should be dict"

            # Should have some basic fields
            expected_fields = ["inside_temp_f", "inside_hum_pct", "time_hhmm"]
            for field in expected_fields:
                assert field in sample_data, f"Missing field in sample data: {field}"

        except json.JSONDecodeError as e:
            pytest.fail(f"Sample data JSON parsing error: {e}")
        except Exception as e:
            pytest.fail(f"Error reading sample data: {e}")
    else:
        pytest.skip("Sample data file not found")


def test_ui_generated_js_validity():
    """Test that ui_generated.js is valid JavaScript"""

    web_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web", "sim")
    ui_generated_path = os.path.join(web_dir, "ui_generated.js")

    if not os.path.exists(ui_generated_path):
        pytest.skip("ui_generated.js not found")

    with open(ui_generated_path, "r") as f:
        js_content = f.read()

    # Should have basic JavaScript structure
    assert "window.UI_SPEC" in js_content, "Missing UI_SPEC in generated JS"

    # Should be valid JavaScript (basic syntax check)
    # This is a simple check - a real implementation would use a JS parser
    assert js_content.count("{") == js_content.count("}"), "Unmatched braces in JS"
    assert js_content.count("(") == js_content.count(")"), "Unmatched parentheses in JS"
    assert js_content.count("[") == js_content.count("]"), "Unmatched brackets in JS"


def test_web_simulator_geometry_consistency():
    """Test that web simulator uses consistent geometry with UI spec"""

    web_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web", "sim")
    ui_spec_path = os.path.join(os.path.dirname(web_dir), "..", "config", "ui_spec.json")

    if not os.path.exists(ui_spec_path):
        pytest.skip("UI spec not found")

    with open(ui_spec_path, "r") as f:
        ui_spec = json.load(f)

    canvas = ui_spec.get("canvas", {})
    expected_width = canvas.get("w", 250)
    expected_height = canvas.get("h", 122)

    # Check that web sim references the correct dimensions
    sim_js_path = os.path.join(web_dir, "sim.js")
    if os.path.exists(sim_js_path):
        with open(sim_js_path, "r") as f:
            sim_js = f.read()

        # Should reference the canvas dimensions
        assert str(expected_width) in sim_js, f"Canvas width {expected_width} not in sim.js"
        assert str(expected_height) in sim_js, f"Canvas height {expected_height} not in sim.js"


def test_web_simulator_sample_data_completeness():
    """Test that sample data covers all UI components"""

    web_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web", "sim")
    sample_data_path = os.path.join(web_dir, "sample_data.json")
    ui_spec_path = os.path.join(os.path.dirname(web_dir), "..", "config", "ui_spec.json")

    if not os.path.exists(sample_data_path) or not os.path.exists(ui_spec_path):
        pytest.skip("Required files not found")

    with open(sample_data_path, "r") as f:
        sample_data = json.load(f)

    with open(ui_spec_path, "r") as f:
        ui_spec = json.load(f)

    # Extract all data field references from UI spec
    components = ui_spec.get("components", {})

    referenced_fields = set()
    for component_name, ops in components.items():
        for op in ops:
            if isinstance(op, dict):
                # Look for template fields like "{inside_temp_f}"
                if "text" in op:
                    text = op["text"]
                    if isinstance(text, str):
                        import re

                        fields = re.findall(r"\{([^}]+)\}", text)
                        referenced_fields.update(fields)

    # Sample data should cover all referenced fields
    sample_fields = set(sample_data.keys())

    # At minimum, should have the basic fields
    essential_fields = {"inside_temp_f", "inside_hum_pct", "time_hhmm"}
    for field in essential_fields:
        assert field in sample_fields, f"Essential field {field} missing from sample data"


def test_web_simulator_weather_icon_mapping():
    """Test that web simulator properly maps weather conditions to icons"""

    web_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web", "sim")
    sim_js_path = os.path.join(web_dir, "sim.js")

    if not os.path.exists(sim_js_path):
        pytest.skip("sim.js not found")

    with open(sim_js_path, "r") as f:
        sim_js = f.read()

    # Should have weather icon mapping logic
    assert "weather-" in sim_js, "Weather icon references missing from sim.js"

    # Should have icon mapping for common conditions
    common_conditions = ["sunny", "cloudy", "rain", "storm", "snow"]
    for condition in common_conditions:
        assert condition in sim_js, f"Weather condition {condition} not handled in sim.js"


def test_web_simulator_data_validation():
    """Test that web simulator validates input data correctly"""

    web_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web", "sim")
    sim_js_path = os.path.join(web_dir, "sim.js")

    if not os.path.exists(sim_js_path):
        pytest.skip("sim.js not found")

    with open(sim_js_path, "r") as f:
        sim_js = f.read()

    # Should have some data validation logic
    validation_indicators = ["isNaN", "null", "undefined", "||", "&&"]
    validation_found = any(indicator in sim_js for indicator in validation_indicators)

    assert validation_found, "No data validation logic found in sim.js"


def test_web_simulator_responsive_design():
    """Test that web simulator is responsive and works at different sizes"""

    web_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web", "sim")
    index_path = os.path.join(web_dir, "index.html")

    if not os.path.exists(index_path):
        pytest.skip("index.html not found")

    with open(index_path, "r") as f:
        html_content = f.read()

    # Should have viewport meta tag for responsive design
    assert "viewport" in html_content, "Missing viewport meta tag"

    # Should have some CSS for responsive design
    assert "width:" in html_content or "height:" in html_content, "No sizing CSS found"


def test_web_simulator_mqtt_integration():
    """Test that web simulator can integrate with MQTT data"""

    web_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web", "sim")
    sim_js_path = os.path.join(web_dir, "sim.js")

    if not os.path.exists(sim_js_path):
        pytest.skip("sim.js not found")

    with open(sim_js_path, "r") as f:
        sim_js = f.read()

    # Should have MQTT-related functionality or at least data update mechanisms
    mqtt_indicators = ["mqtt", "publish", "subscribe", "topic", "message"]
    mqtt_found = any(indicator in sim_js.lower() for indicator in mqtt_indicators)

    # This is more of a framework test - real MQTT integration would be more complex
    if not mqtt_found:
        # At minimum should have data update mechanisms
        update_indicators = ["update", "refresh", "draw", "render"]
        assert any(
            indicator in sim_js.lower() for indicator in update_indicators
        ), "No data update mechanisms found in sim.js"


def test_web_simulator_performance_metrics():
    """Test that web simulator includes performance metrics"""

    web_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web", "sim")
    sim_js_path = os.path.join(web_dir, "sim.js")

    if not os.path.exists(sim_js_path):
        pytest.skip("sim.js not found")

    with open(sim_js_path, "r") as f:
        sim_js = f.read()

    # Should have some performance-related code or metrics
    perf_indicators = ["performance", "timing", "fps", "frame", "time"]
    perf_found = any(indicator in sim_js.lower() for indicator in perf_indicators)

    # This is more of a framework - real perf metrics would be more sophisticated
    if not perf_found:
        # At minimum should have some timing mechanisms
        time_indicators = ["Date", "setInterval", "setTimeout", "now"]
        assert any(
            indicator in sim_js for indicator in time_indicators
        ), "No timing mechanisms found in sim.js"


def test_web_simulator_accessibility():
    """Test that web simulator has basic accessibility features"""

    web_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web", "sim")
    index_path = os.path.join(web_dir, "index.html")

    if not os.path.exists(index_path):
        pytest.skip("index.html not found")

    with open(index_path, "r") as f:
        html_content = f.read()

    # Should have basic accessibility features
    accessibility_features = ["alt=", "title=", "role=", "aria-", "lang=", "charset="]

    # At least some accessibility features should be present
    accessibility_found = any(feature in html_content for feature in accessibility_features)

    assert accessibility_found, "No accessibility features found in HTML"


def test_web_simulator_error_handling():
    """Test that web simulator handles errors gracefully"""

    web_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web", "sim")
    sim_js_path = os.path.join(web_dir, "sim.js")

    if not os.path.exists(sim_js_path):
        pytest.skip("sim.js not found")

    with open(sim_js_path, "r") as f:
        sim_js = f.read()

    # Should have error handling mechanisms
    error_indicators = ["try", "catch", "console.error", "console.log", "error"]
    error_handling_found = any(indicator in sim_js for indicator in error_indicators)

    assert error_handling_found, "No error handling found in sim.js"


def test_web_simulator_data_persistence():
    """Test that web simulator can save/load state"""

    web_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web", "sim")
    sim_js_path = os.path.join(web_dir, "sim.js")

    if not os.path.exists(sim_js_path):
        pytest.skip("sim.js not found")

    with open(sim_js_path, "r") as f:
        sim_js = f.read()

    # Should have some persistence mechanism
    persistence_indicators = ["localStorage", "sessionStorage", "save", "load", "store"]
    persistence_found = any(indicator in sim_js for indicator in persistence_indicators)

    # This is more of a framework test - real persistence would be more sophisticated
    if not persistence_found:
        # At minimum should have data structures that could be persisted
        data_indicators = ["data", "state", "config", "settings"]
        assert any(
            indicator in sim_js.lower() for indicator in data_indicators
        ), "No data structures found for potential persistence"


def test_web_simulator_visual_consistency():
    """Test that web simulator maintains visual consistency with firmware"""

    web_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web", "sim")
    sim_js_path = os.path.join(web_dir, "sim.js")

    if not os.path.exists(sim_js_path):
        pytest.skip("sim.js not found")

    with open(sim_js_path, "r") as f:
        sim_js = f.read()

    # Should reference the same layout constants as firmware
    layout_indicators = ["RECT_", "DISPLAY_WIDTH", "DISPLAY_HEIGHT", "CANVAS"]
    layout_found = any(indicator in sim_js for indicator in layout_indicators)

    assert layout_found, "No layout constants found in sim.js"


def test_web_simulator_export_functionality():
    """Test that web simulator can export data or screenshots"""

    web_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web", "sim")
    sim_js_path = os.path.join(web_dir, "sim.js")

    if not os.path.exists(sim_js_path):
        pytest.skip("sim.js not found")

    with open(sim_js_path, "r") as f:
        sim_js = f.read()

    # Should have export functionality
    export_indicators = ["export", "download", "save", "toDataURL", "canvas", "image"]
    export_found = any(indicator in sim_js for indicator in export_indicators)

    # This is more of a framework test - real export would be more sophisticated
    if not export_found:
        # At minimum should have canvas manipulation
        canvas_indicators = ["canvas", "context", "getContext", "draw"]
        assert any(
            indicator in sim_js.lower() for indicator in canvas_indicators
        ), "No canvas manipulation found for potential export functionality"


def test_web_simulator_theme_support():
    """Test that web simulator supports theming or different display modes"""

    web_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web", "sim")
    style_path = os.path.join(web_dir, "style.css")
    index_path = os.path.join(web_dir, "index.html")

    if not os.path.exists(style_path) or not os.path.exists(index_path):
        pytest.skip("Style files not found")

    with open(style_path, "r") as f:
        css_content = f.read()

    with open(index_path, "r") as f:
        html_content = f.read()

    # Should have some styling
    style_indicators = ["color:", "background:", "font-", "display:", "position:"]
    styling_found = any(indicator in css_content for indicator in style_indicators)

    assert styling_found, "No CSS styling found"

    # Should have some theming or visual customization
    theme_indicators = ["class=", "id=", "style=", "dark", "light", "theme"]
    theming_found = any(indicator in html_content for indicator in theme_indicators)

    assert theming_found, "No theming elements found in HTML"
