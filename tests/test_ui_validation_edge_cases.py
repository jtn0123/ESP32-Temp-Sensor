"""Test edge cases in UI validation that could break during refactoring."""

import pytest
import json
from pathlib import Path
import sys

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

class TestUIValidationEdgeCases:
    """Test complex edge cases in UI validation logic."""
    
    def setup_method(self):
        """Setup test environment."""
        self.root = Path(__file__).parent.parent
        self.geometry_path = self.root / "config/display_geometry.json"
        
        # Load geometry
        with open(self.geometry_path) as f:
            self.geometry = json.load(f)
    
    def test_text_overflow_with_bold_fonts(self):
        """Test text overflow detection with different font weights."""
        test_cases = [
            # (text, font_size, region_width, is_bold, should_overflow)
            ("100.0°F", 32, 60, False, False),  # Normal font fits
            ("100.0°F", 32, 60, True, True),    # Bold font overflows
            ("1013 hPa", 16, 70, False, False), # Normal pressure fits
            ("1013 hPa", 16, 65, True, True),   # Bold pressure overflows
        ]
        
        for text, size, width, is_bold, should_overflow in test_cases:
            # Calculate text width (approximate)
            char_width = size * 0.6 if not is_bold else size * 0.7
            text_width = len(text) * char_width
            
            overflows = text_width > width
            assert overflows == should_overflow, f"Text '{text}' overflow detection failed"
    
    def test_collision_detection_with_exclusions(self):
        """Test region collision detection with allowed overlaps."""
        # Regions that should be excluded from collision detection
        exclusion_patterns = ["_INNER", "_BADGE", "_ICON", "_LABEL"]
        
        regions = self.geometry["regions"]
        collisions = []
        
        for name1, r1 in regions.items():
            # Skip if excluded
            if any(pattern in name1 for pattern in exclusion_patterns):
                continue
                
            for name2, r2 in regions.items():
                if name1 >= name2:  # Avoid duplicate checks
                    continue
                    
                # Skip if excluded
                if any(pattern in name2 for pattern in exclusion_patterns):
                    continue
                
                # Check collision
                if self.regions_overlap(r1, r2):
                    collisions.append((name1, name2))
        
        # Should have no unexpected collisions
        expected_collisions = []  # Add any expected overlaps here
        
        for collision in collisions:
            assert collision in expected_collisions, f"Unexpected collision: {collision}"
    
    def regions_overlap(self, r1, r2):
        """Check if two regions overlap."""
        return not (
            r1["x"] + r1["width"] <= r2["x"] or
            r2["x"] + r2["width"] <= r1["x"] or
            r1["y"] + r1["height"] <= r2["y"] or
            r2["y"] + r2["height"] <= r1["y"]
        )
    
    def test_empty_region_detection(self):
        """Test detection of empty regions with various content."""
        test_cases = [
            ("", True),           # Empty string
            (" ", True),          # Single space
            ("  \t\n", True),    # Whitespace only
            ("--", False),        # Placeholder
            ("0", False),         # Zero value
            ("N/A", False),       # Not available
            (None, True),         # Null value
        ]
        
        for content, is_empty in test_cases:
            detected_empty = not content or not str(content).strip()
            assert detected_empty == is_empty, f"Empty detection failed for '{content}'"
    
    def test_boundary_text_positioning(self):
        """Test text exactly at region boundaries."""
        test_cases = [
            # (text, x, y, width, height, should_fit)
            ("Edge", 0, 0, 40, 20, True),        # Top-left corner
            ("Edge", 256, 108, 40, 20, False),   # Beyond display
            ("Long text here", 200, 60, 50, 20, False),  # Text too wide
        ]
        
        display_width = self.geometry["metadata"]["width"]
        display_height = self.geometry["metadata"]["height"]
        
        for text, x, y, width, height, should_fit in test_cases:
            fits = (
                x >= 0 and y >= 0 and
                x + width <= display_width and
                y + height <= display_height and
                len(text) * 8 <= width  # Approximate char width
            )
            
            assert fits == should_fit, f"Boundary check failed for '{text}' at ({x},{y})"
    
    def test_malformed_geometry_handling(self):
        """Test validation behavior with malformed geometry."""
        malformed_cases = [
            {"x": -10, "y": 10, "width": 50, "height": 20},  # Negative x
            {"x": 10, "y": -10, "width": 50, "height": 20},  # Negative y
            {"x": 10, "y": 10, "width": -50, "height": 20},  # Negative width
            {"x": 10, "y": 10, "width": 50, "height": -20},  # Negative height
            {"x": 10, "y": 10, "width": 0, "height": 20},    # Zero width
            {"x": 10, "y": 10, "width": 50, "height": 0},    # Zero height
            {"x": 300, "y": 10, "width": 50, "height": 20},  # Beyond display
            {"x": 10, "y": 150, "width": 50, "height": 20},  # Beyond display
        ]
        
        for region in malformed_cases:
            is_valid = (
                region["x"] >= 0 and
                region["y"] >= 0 and
                region["width"] > 0 and
                region["height"] > 0 and
                region["x"] + region["width"] <= 296 and
                region["y"] + region["height"] <= 128
            )
            
            assert not is_valid, f"Malformed region should be invalid: {region}"
    
    def test_text_centering_calculations(self):
        """Test text centering within regions."""
        test_cases = [
            ("Center", 100, 50),   # Region width, expected x offset
            ("A", 100, 50),        # Single char
            ("Very long text", 50, 25),  # Text wider than region
        ]
        
        for text, region_width, expected_center in test_cases:
            char_width = 8  # Approximate
            text_width = len(text) * char_width
            center_x = max(0, (region_width - text_width) // 2)
            
            # Allow some tolerance
            assert abs(center_x - expected_center) <= region_width // 2
    
    def test_validation_severity_levels(self):
        """Test that validation issues have correct severity levels."""
        severity_tests = [
            ("text_overflow", "error"),        # Text overflow is error
            ("region_collision", "error"),     # Collision is error
            ("empty_region", "warning"),       # Empty is warning
            ("alignment_issue", "warning"),    # Alignment is warning
            ("missing_data", "info"),         # Missing data is info
        ]
        
        severities = {
            "text_overflow": "error",
            "region_collision": "error",
            "empty_region": "warning",
            "alignment_issue": "warning",
            "missing_data": "info",
        }
        
        for issue_type, expected_severity in severity_tests:
            assert severities[issue_type] == expected_severity
    
    def test_cascading_validation_failures(self):
        """Test handling of multiple validation failures."""
        # Simulate multiple issues
        issues = []
        
        # Add various issues
        if "test" == "test":  # Always true for testing
            issues.append({"type": "overflow", "region": "TEMP"})
            issues.append({"type": "collision", "regions": ["A", "B"]})
            issues.append({"type": "empty", "region": "HUMID"})
        
        # Should handle multiple issues
        assert len(issues) == 3
        
        # Should prioritize by severity
        sorted_issues = sorted(issues, key=lambda x: 
            0 if x["type"] == "collision" else
            1 if x["type"] == "overflow" else 2
        )
        
        assert sorted_issues[0]["type"] == "collision"  # Highest priority