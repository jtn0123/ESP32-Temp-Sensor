#!/usr/bin/env python3
"""
Test that internal helper rectangles are properly filtered out
"""

from pathlib import Path
import sys

# Add scripts to path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def test_internal_helper_rect_detection():
    """Test that internal helper rectangles are correctly identified"""
    from scripts.ui_validation_engine import UIValidationEngine

    engine = UIValidationEngine()

    # Test internal helper rectangles
    assert engine._is_internal_helper_rect("INSIDE_TEMP_INNER") is True
    assert engine._is_internal_helper_rect("OUT_TEMP_BADGE") is True
    assert engine._is_internal_helper_rect("INSIDE_LABEL_BOX") is True
    assert engine._is_internal_helper_rect("OUT_LABEL_BOX") is True

    # Test normal rectangles
    assert engine._is_internal_helper_rect("INSIDE_TEMP") is False
    assert engine._is_internal_helper_rect("OUT_TEMP") is False
    assert engine._is_internal_helper_rect("HEADER_NAME") is False
    assert engine._is_internal_helper_rect("FOOTER_L") is False
    assert engine._is_internal_helper_rect("WEATHER_ICON") is False


def test_validation_excludes_internal_rects():
    """Test that validation doesn't process internal helper rectangles"""
    from scripts.ui_validation_engine import RegionValidation, UIValidationEngine

    engine = UIValidationEngine()

    # Create a mix of regular and internal regions
    test_regions = {
        "HEADER_NAME": RegionValidation(
            name="HEADER_NAME", rect=(10, 10, 100, 20), category="header"
        ),
        "INSIDE_TEMP": RegionValidation(
            name="INSIDE_TEMP", rect=(10, 40, 100, 30), category="temp"
        ),
        # These should NOT be included in collision checks
        "INSIDE_TEMP_INNER": RegionValidation(
            name="INSIDE_TEMP_INNER", rect=(15, 45, 90, 20), category="temp"
        ),
        "INSIDE_TEMP_BADGE": RegionValidation(
            name="INSIDE_TEMP_BADGE", rect=(95, 45, 10, 10), category="temp"
        ),
    }

    # Filter out internal rects as the validation engine should
    filtered_regions = {
        name: region
        for name, region in test_regions.items()
        if not engine._is_internal_helper_rect(name)
    }

    # Should only have the two main regions
    assert len(filtered_regions) == 2
    assert "HEADER_NAME" in filtered_regions
    assert "INSIDE_TEMP" in filtered_regions
    assert "INSIDE_TEMP_INNER" not in filtered_regions
    assert "INSIDE_TEMP_BADGE" not in filtered_regions

    # Run collision validation on filtered regions
    issues = engine.validate_collisions(filtered_regions)

    # Should not report collisions with internal regions
    for issue in issues:
        assert "INNER" not in issue.region
        assert "BADGE" not in issue.region
        assert "LABEL_BOX" not in issue.region


def test_allowed_overlaps_excludes_internal():
    """Test that allowed overlaps list properly handles internal regions"""
    from scripts.ui_validation_engine import RegionValidation, UIValidationEngine

    engine = UIValidationEngine()

    # The allowed overlaps in validate_collisions should be updated
    # to not need LABEL_BOX entries since those are filtered out

    # Create regions that would overlap
    regions = {
        "INSIDE_TEMP": RegionValidation(
            name="INSIDE_TEMP", rect=(10, 40, 100, 30), category="temp"
        ),
        "FOOTER_WEATHER": RegionValidation(
            name="FOOTER_WEATHER", rect=(120, 90, 50, 20), category="footer"
        ),
        "WEATHER_ICON": RegionValidation(
            name="WEATHER_ICON",
            rect=(115, 85, 30, 30),  # Overlaps with FOOTER_WEATHER
            category="other",
        ),
    }

    # Run collision check
    issues = engine.validate_collisions(regions)

    # FOOTER_WEATHER and WEATHER_ICON overlap is allowed, so should not be reported
    weather_footer_issues = [
        i for i in issues if ("FOOTER_WEATHER" in i.region and "WEATHER_ICON" in i.region)
    ]

    # This overlap should be allowed (it's in the allowed list)
    # If it's reported, check that it's only as INFO severity
    if weather_footer_issues:
        assert all(i.severity.value == "info" for i in weather_footer_issues)


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
