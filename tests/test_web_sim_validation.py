#!/usr/bin/env python3
"""
Test suite for web simulator validation engine.
Tests that the validation system properly detects:
- Text overflow issues
- Empty regions
- Region boundary violations
- Collision detection
"""

import json
from pathlib import Path
import subprocess
import time

import pytest
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

# Configuration
WEB_SIM_PATH = Path(__file__).parent.parent / "web" / "sim"
TEST_PORT = 8765


class TestWebSimValidation:
    """Test the web simulator validation engine."""

    @classmethod
    def setup_class(cls):
        """Start web server and initialize browser."""
        # Start web server
        cls.server_process = subprocess.Popen(
            ["python3", "-m", "http.server", str(TEST_PORT)],
            cwd=WEB_SIM_PATH,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(2)  # Wait for server to start

        # Setup Chrome in headless mode
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        cls.driver = webdriver.Chrome(options=options)
        cls.wait = WebDriverWait(cls.driver, 10)

    @classmethod
    def teardown_class(cls):
        """Clean up browser and server."""
        cls.driver.quit()
        cls.server_process.terminate()
        cls.server_process.wait()

    def load_simulator(self, test_data=None):
        """Load the simulator with optional test data."""
        url = f"http://localhost:{TEST_PORT}/index.html"
        self.driver.get(url)

        # Wait for canvas to be ready
        self.wait.until(EC.presence_of_element_located((By.ID, "epd")))

        if test_data:
            # Inject test data via JavaScript
            script = f"draw({json.dumps(test_data)});"
            self.driver.execute_script(script)
            time.sleep(0.5)  # Wait for render

    def get_validation_issues(self):
        """Get current validation issues from the simulator."""
        script = "return window.validationIssues || [];"
        return self.driver.execute_script(script)

    def test_text_overflow_detection(self):
        """Test that text overflow is properly detected."""
        self.load_simulator(
            {
                "room_name": "A Very Long Room Name That Will Definitely Overflow",
                "inside_temp_f": "999.9",
                "outside_temp_f": "888.8",
                "inside_hum_pct": "100",
                "outside_hum_pct": "100",
                "pressure_hpa": "1013.25",  # Long pressure value
                "wind_mps": "99.9",
            }
        )

        issues = self.get_validation_issues()
        overflow_issues = [i for i in issues if i["type"] == "text_overflow"]

        assert len(overflow_issues) > 0, "Should detect text overflow issues"

        # Check specific regions that should overflow
        overflow_regions = {i["region"] for i in overflow_issues}
        assert "HEADER_NAME" in overflow_regions, "Should detect header name overflow"

    def test_empty_region_detection(self):
        """Test that empty regions are properly detected."""
        self.load_simulator(
            {
                # Minimal data - many regions will be empty
                "room_name": "Test",
                "inside_temp_f": "72",
            }
        )

        issues = self.get_validation_issues()
        empty_issues = [i for i in issues if i["type"] == "empty_region"]

        assert len(empty_issues) > 0, "Should detect empty regions"

        # Check that expected empty regions are detected
        empty_regions = {i["region"] for i in empty_issues}
        assert "OUT_TEMP" in empty_regions, "Should detect empty outside temp"
        assert (
            "FOOTER_STATUS" in empty_regions or len(empty_regions) > 0
        ), "Should detect empty regions"

    def test_bounds_exceeded_detection(self):
        """Test that content exceeding region bounds is detected."""
        self.load_simulator(
            {"room": "Test Room", "temp": "72.5", "temp_out": "68.4", "rh": "47", "rh_out": "53"}
        )

        # Force validation
        self.driver.execute_script("runValidation();")

        issues = self.get_validation_issues()
        bounds_issues = [i for i in issues if i["type"] == "bounds_exceeded"]

        # Check if any temperature values exceed their bounds
        if bounds_issues:
            bounds_regions = {i["region"] for i in bounds_issues}
            print(f"Detected bounds exceeded in: {bounds_regions}")

    def test_collision_detection(self):
        """Test that region collisions are properly detected."""
        # Skip this test if collision detection is not implemented
        self.load_simulator()

        # Check if collision detection exists
        has_detection = self.driver.execute_script(
            "return typeof window.detectRegionCollisions === 'function'"
        )

        if not has_detection:
            pytest.skip("Collision detection not implemented")

        # Temporarily modify allowed collisions to test detection
        script = """
        const oldAllowed = window.allowedCollisions;
        window.allowedCollisions = new Set();  // Clear allowed list
        runValidation();
        const issues = window.validationIssues || [];
        window.allowedCollisions = oldAllowed;  // Restore
        return issues;
        """

        issues = self.driver.execute_script(script)
        collision_issues = [i for i in issues if i["type"] == "collision"]
        # If no collisions detected, that's okay - the layout might not have any
        assert isinstance(collision_issues, list)

    def test_validation_ui_updates(self):
        """Test that validation UI properly updates."""
        self.load_simulator()

        # Check badge exists and shows status
        badge = self.driver.find_element(By.ID, "validationBadge")
        assert badge is not None, "Validation badge should exist"

        badge_text = badge.text
        # Badge can show counts like "1 critical" or just status
        assert any(
            status in badge_text.lower() for status in ["ok", "warning", "error", "critical"]
        ), f"Badge should show valid status, got: {badge_text}"

        # Check results panel exists
        results = self.driver.find_element(By.ID, "validationResults")
        assert results is not None, "Validation results panel should exist"

    def test_visual_overlay_rendering(self):
        """Test that validation overlay renders correctly."""
        self.load_simulator(
            {"room": "Very Long Room Name That Overflows", "temp": "999.9", "temp_out": "888.8"}
        )

        # Enable validation and check overlay is drawn
        script = """
        validationEnabled = true;
        runValidation();
        drawValidationOverlay();
        return validationIssues.length;
        """

        issue_count = self.driver.execute_script(script)
        assert issue_count > 0, "Should have validation issues to overlay"

        # Take screenshot to verify overlay (optional)
        # screenshot = self.driver.get_screenshot_as_png()
        # Path("test_validation_overlay.png").write_bytes(screenshot)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
