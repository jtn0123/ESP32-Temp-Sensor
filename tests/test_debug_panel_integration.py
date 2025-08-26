#!/usr/bin/env python3
"""
Test debug panel integration with simulator
Verifies that all debug controls properly update the display
"""

import json
from pathlib import Path
import subprocess
import time

import pytest

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    pytest.skip("Playwright not installed", allow_module_level=True)


ROOT = Path(__file__).resolve().parents[1]


class TestDebugPanelIntegration:
    """Test debug panel functionality"""

    @classmethod
    def setup_class(cls):
        """Start web server"""
        cls.port = 8234
        cls.server = subprocess.Popen(
            ["python3", "-m", "http.server", str(cls.port), "--bind", "127.0.0.1"],
            cwd=str(ROOT / "web" / "sim"),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        time.sleep(1)

    @classmethod
    def teardown_class(cls):
        """Stop web server"""
        cls.server.terminate()
        cls.server.wait(timeout=2)

    def test_draw_function_exposed(self):
        """Test that draw function is properly exposed"""
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(f"http://127.0.0.1:{self.port}/index.html")
            page.wait_for_timeout(1000)

            # Check if draw function exists
            has_draw = page.evaluate("() => typeof window.draw === 'function'")
            assert has_draw, "window.draw function not exposed"

            # Check if DEFAULTS exists
            has_defaults = page.evaluate("() => typeof window.DEFAULTS === 'object'")
            assert has_defaults, "window.DEFAULTS not exposed"

            browser.close()

    def test_data_editor_updates_display(self):
        """Test that data editor fields update the display"""
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(f"http://127.0.0.1:{self.port}/index.html")
            page.wait_for_timeout(1000)

            # Expand debug panel
            page.click("summary:has-text('Advanced Debug Tools')")
            page.wait_for_timeout(200)

            # Test room name update
            page.fill("#field_room_name", "Test Room 123")
            page.click("#applyData")
            page.wait_for_timeout(200)

            # Verify the data was applied
            last_data = page.evaluate("() => window.lastData")
            assert last_data.get("room_name") == "Test Room 123"

            # Test temperature update
            page.fill("#field_inside_temp_f", "88.8")
            page.click("#applyData")
            page.wait_for_timeout(200)

            last_data = page.evaluate("() => window.lastData")
            assert last_data.get("inside_temp_f") == 88.8

            browser.close()

    def test_scenario_selector(self):
        """Test that scenario selector applies test data"""
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(f"http://127.0.0.1:{self.port}/index.html")
            page.wait_for_timeout(1000)

            # Expand debug panel
            page.click("summary:has-text('Advanced Debug Tools')")
            page.wait_for_timeout(200)

            # Select a test scenario category
            page.select_option("#scenarioCategory", "battery_states")
            page.wait_for_timeout(100)

            # Select a specific scenario
            page.select_option("#scenarioList", "0")  # Critical battery
            page.click("#applyScenario")
            page.wait_for_timeout(200)

            # Verify the scenario was applied
            last_data = page.evaluate("() => window.lastData")
            assert last_data.get("battery_percent") == 5

            browser.close()

    def test_weather_icon_buttons(self):
        """Test weather icon quick buttons"""
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(f"http://127.0.0.1:{self.port}/index.html")
            page.wait_for_timeout(1000)

            # Expand debug panel
            page.click("summary:has-text('Advanced Debug Tools')")
            page.wait_for_timeout(200)

            # Click weather icon buttons
            weather_types = ["sunny", "rain", "snow", "fog"]

            for weather in weather_types:
                page.click(f"button.icon-test[data-weather='{weather}']")
                page.wait_for_timeout(200)

                last_data = page.evaluate("() => window.lastData")
                assert last_data.get("weather") == weather

            browser.close()

    def test_reset_data(self):
        """Test reset button clears custom data"""
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(f"http://127.0.0.1:{self.port}/index.html")
            page.wait_for_timeout(1000)

            # Expand debug panel
            page.click("summary:has-text('Advanced Debug Tools')")
            page.wait_for_timeout(200)

            # Set some custom data
            page.fill("#field_room_name", "Custom Room")
            page.fill("#field_inside_temp_f", "99")
            page.click("#applyData")
            page.wait_for_timeout(200)

            # Verify data was applied
            last_data = page.evaluate("() => window.lastData")
            assert last_data.get("room_name") == "Custom Room"

            # Reset data
            page.click("#resetData")
            page.wait_for_timeout(200)

            # Verify fields are cleared
            room_value = page.input_value("#field_room_name")
            assert room_value == ""

            browser.close()

    def test_performance_monitoring(self):
        """Test that performance metrics are updated"""
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(f"http://127.0.0.1:{self.port}/index.html")
            page.wait_for_timeout(1000)

            # Expand debug panel
            page.click("summary:has-text('Advanced Debug Tools')")
            page.wait_for_timeout(200)

            # Trigger some draws
            for i in range(3):
                page.evaluate(f"() => window.draw({{ inside_temp_f: {70 + i} }})")
                page.wait_for_timeout(100)

            # Check that frame count increased
            frame_count = page.text_content("#debugFrameCount")
            assert int(frame_count) > 0

            # Reset performance metrics
            page.click("#perfReset")
            page.wait_for_timeout(100)

            frame_count_after = page.text_content("#debugFrameCount")
            assert int(frame_count_after) == 0 or int(frame_count_after) < int(frame_count)

            browser.close()

    def test_state_inspector(self):
        """Test state inspector shows current data"""
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(f"http://127.0.0.1:{self.port}/index.html")
            page.wait_for_timeout(1000)

            # Expand debug panel
            page.click("summary:has-text('Advanced Debug Tools')")
            page.wait_for_timeout(200)

            # Apply some test data
            test_data = {"room_name": "State Test", "inside_temp_f": 77.7}
            page.evaluate(f"() => window.draw({json.dumps(test_data)})")
            page.wait_for_timeout(200)

            # Refresh state inspector
            page.click("#refreshState")
            page.wait_for_timeout(100)

            # Check state contains our data
            state_text = page.text_content("#stateInspector")
            assert "State Test" in state_text
            assert "77.7" in state_text

            browser.close()

    def test_custom_weather_input(self):
        """Test custom weather text input"""
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(f"http://127.0.0.1:{self.port}/index.html")
            page.wait_for_timeout(1000)

            # Expand debug panel
            page.click("summary:has-text('Advanced Debug Tools')")
            page.wait_for_timeout(200)

            # Enter custom weather
            page.fill("#customWeather", "heavy thunderstorms")
            page.click("#testCustomWeather")
            page.wait_for_timeout(200)

            # Verify it was applied
            last_data = page.evaluate("() => window.lastData")
            assert last_data.get("weather") == "heavy thunderstorms"

            browser.close()

    def test_preset_selector_integration(self):
        """Test that built-in preset selector still works"""
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(f"http://127.0.0.1:{self.port}/index.html")
            page.wait_for_timeout(1000)

            # Use the original preset selector
            page.select_option("#presetMode", "low_batt")
            page.wait_for_timeout(200)

            # Verify low battery was applied
            last_data = page.evaluate("() => window.lastData")
            assert last_data.get("battery_percent") == 12

            # Try extreme preset
            page.select_option("#presetMode", "extreme")
            page.wait_for_timeout(200)

            last_data = page.evaluate("() => window.lastData")
            assert last_data.get("inside_temp_f") == -10.2
            assert last_data.get("outside_temp_f") == 109.9

            browser.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
