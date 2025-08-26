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
            stderr=subprocess.DEVNULL
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
        self.load_simulator({
            "room": "A Very Long Room Name That Will Definitely Overflow",
            "temp": "999.9",
            "temp_out": "888.8",
            "rh": "100",
            "rh_out": "100",
            "pressure": "1013.25 hPa",  # Long pressure value
            "wind": "99.9 mph"
        })

        issues = self.get_validation_issues()
        overflow_issues = [i for i in issues if i['type'] == 'text_overflow']

        assert len(overflow_issues) > 0, "Should detect text overflow issues"

        # Check specific regions that should overflow
        overflow_regions = {i['region'] for i in overflow_issues}
        assert 'HEADER_NAME' in overflow_regions, "Should detect header name overflow"

    def test_empty_region_detection(self):
        """Test that empty regions are properly detected."""
        self.load_simulator({
            # Minimal data - many regions will be empty
            "room": "Test",
            "temp": "72"
        })

        issues = self.get_validation_issues()
        empty_issues = [i for i in issues if i['type'] == 'empty_region']

        assert len(empty_issues) > 0, "Should detect empty regions"

        # Check that expected empty regions are detected
        empty_regions = {i['region'] for i in empty_issues}
        assert 'OUT_TEMP' in empty_regions, "Should detect empty outside temp"
        assert 'STATUS' in empty_regions, "Should detect empty status"

    def test_bounds_exceeded_detection(self):
        """Test that content exceeding region bounds is detected."""
        self.load_simulator({
            "room": "Test Room",
            "temp": "72.5",
            "temp_out": "68.4",
            "rh": "47",
            "rh_out": "53"
        })

        # Force validation
        self.driver.execute_script("runValidation();")

        issues = self.get_validation_issues()
        bounds_issues = [i for i in issues if i['type'] == 'bounds_exceeded']

        # Check if any temperature values exceed their bounds
        if bounds_issues:
            bounds_regions = {i['region'] for i in bounds_issues}
            print(f"Detected bounds exceeded in: {bounds_regions}")

    def test_collision_detection(self):
        """Test that region collisions are properly detected."""
        # Temporarily modify allowed collisions to test detection
        script = """
        const oldAllowed = window.allowedCollisions;
        window.allowedCollisions = new Set();  // Clear allowed list
        runValidation();
        const issues = window.validationIssues || [];
        window.allowedCollisions = oldAllowed;  // Restore
        return issues;
        """

        self.load_simulator()
        issues = self.driver.execute_script(script)

        collision_issues = [i for i in issues if i['type'] == 'collision']
        assert len(collision_issues) > 0, "Should detect collisions when allowed list is empty"

    def test_validation_ui_updates(self):
        """Test that validation UI properly updates."""
        self.load_simulator()

        # Check badge exists and shows status
        badge = self.driver.find_element(By.ID, "validationBadge")
        assert badge is not None, "Validation badge should exist"

        badge_text = badge.text
        assert badge_text in ['OK', 'warnings', 'errors', 'critical'], \
            f"Badge should show valid status, got: {badge_text}"

        # Check results panel exists
        results = self.driver.find_element(By.ID, "validationResults")
        assert results is not None, "Validation results panel should exist"

    def test_visual_overlay_rendering(self):
        """Test that validation overlay renders correctly."""
        self.load_simulator({
            "room": "Very Long Room Name That Overflows",
            "temp": "999.9",
            "temp_out": "888.8"
        })

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
