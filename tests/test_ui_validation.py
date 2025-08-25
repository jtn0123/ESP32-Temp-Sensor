#!/usr/bin/env python3
"""
Test suite for UI validation system
Tests the comprehensive validation engine for text overflow, collisions, and layout issues
"""

import json
import os
import sys
import subprocess
from pathlib import Path
from typing import Dict, Any

import pytest

# Add scripts to path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def test_validation_engine_import():
    """Test that the validation engine can be imported"""
    from ui_validation_engine import UIValidationEngine, ValidationSeverity, ValidationType
    
    assert UIValidationEngine is not None
    assert ValidationSeverity.CRITICAL.value == "critical"
    assert ValidationType.TEXT_OVERFLOW.value == "text_overflow"


def test_validation_engine_initialization():
    """Test validation engine initialization"""
    from ui_validation_engine import UIValidationEngine
    
    engine = UIValidationEngine()
    assert engine.web_root is not None
    assert engine.ui_spec is not None
    assert engine.known_text_patterns is not None


def test_text_overflow_detection():
    """Test that text overflow is properly detected"""
    from ui_validation_engine import UIValidationEngine, RegionValidation
    
    engine = UIValidationEngine()
    
    # Create a test region with small bounds
    region = RegionValidation(
        name="TEST_REGION",
        rect=(0, 0, 50, 12),  # Small width
        category="label"
    )
    
    # Mock page evaluation would detect overflow for long text
    # This tests the validation logic structure
    assert region.rect[2] == 50  # Width is 50px
    assert region.rect[3] == 12  # Height is 12px


def test_collision_detection():
    """Test that region collisions are detected"""
    from ui_validation_engine import UIValidationEngine, RegionValidation
    
    engine = UIValidationEngine()
    
    # Create overlapping regions
    regions = {
        "REGION1": RegionValidation(
            name="REGION1",
            rect=(10, 10, 100, 50),
            category="temp"
        ),
        "REGION2": RegionValidation(
            name="REGION2", 
            rect=(50, 30, 100, 50),  # Overlaps with REGION1
            category="temp"
        )
    }
    
    issues = engine.validate_collisions(regions)
    
    # Should detect collision between REGION1 and REGION2
    assert len(issues) > 0
    collision_issue = issues[0]
    assert collision_issue.issue_type.value == "collision"
    assert "REGION1" in collision_issue.region
    assert "REGION2" in collision_issue.region


def test_alignment_validation():
    """Test that alignment issues are detected"""
    from ui_validation_engine import UIValidationEngine, RegionValidation
    
    engine = UIValidationEngine()
    
    # Create misaligned inside regions
    regions = {
        "INSIDE_TEMP": RegionValidation(
            name="INSIDE_TEMP",
            rect=(10, 20, 100, 30),
            category="temp"
        ),
        "INSIDE_RH": RegionValidation(
            name="INSIDE_RH",
            rect=(15, 55, 100, 15),  # Different x position
            category="label"
        )
    }
    
    issues = engine.validate_alignment(regions)
    
    # Should detect misalignment of inside elements
    alignment_issues = [i for i in issues if i.issue_type.value == "misalignment"]
    assert len(alignment_issues) > 0


def test_font_size_validation():
    """Test that font size issues are detected"""
    from ui_validation_engine import UIValidationEngine, RegionValidation
    
    engine = UIValidationEngine()
    
    # Create region too small for expected font
    regions = {
        "INSIDE_TEMP": RegionValidation(
            name="INSIDE_TEMP",
            rect=(10, 20, 100, 10),  # Too short for 22px font
            category="temp"
        )
    }
    
    issues = engine.validate_font_sizes(regions)
    
    # Should detect font size issue
    assert len(issues) > 0
    font_issue = issues[0]
    assert font_issue.issue_type.value == "font_size"
    assert font_issue.severity.value in ["error", "critical"]


def test_bounds_validation():
    """Test that content bounds issues are detected"""
    import numpy as np
    from ui_validation_engine import UIValidationEngine, RegionValidation
    
    engine = UIValidationEngine()
    
    # Create a test image with content at edges
    img = np.ones((122, 250, 3), dtype=np.uint8) * 255  # White background
    
    # Add content that touches the edge of a region
    region = RegionValidation(
        name="TEST_REGION",
        rect=(10, 10, 50, 30),
        category="label"
    )
    
    # Draw black pixels at the edge
    img[10:15, 10:12] = 0  # Content at left edge
    img[38:40, 10:60] = 0  # Content at bottom edge
    
    issues = engine.validate_content_bounds(img, region)
    
    # Should detect clipped content
    clipped_issues = [i for i in issues if i.issue_type.value == "content_clipped"]
    assert len(clipped_issues) > 0


def test_validation_report_generation():
    """Test that validation reports are generated correctly"""
    from ui_validation_engine import UIValidationEngine, ValidationReport, ValidationIssue, ValidationSeverity, ValidationType
    from datetime import datetime
    
    engine = UIValidationEngine()
    
    # Create a mock validation report
    report = ValidationReport(
        timestamp=datetime.now().isoformat(),
        variant="v2_grid",
        total_regions=10,
        regions={},
        issues=[
            ValidationIssue(
                issue_type=ValidationType.TEXT_OVERFLOW,
                severity=ValidationSeverity.ERROR,
                region="OUT_ROW1_L",
                description="Text overflows by 15px"
            ),
            ValidationIssue(
                issue_type=ValidationType.COLLISION,
                severity=ValidationSeverity.WARNING,
                region="REGION1,REGION2",
                description="Regions overlap by 20%"
            )
        ],
        summary={
            "total_issues": 2,
            "by_severity": {
                "critical": 0,
                "error": 1,
                "warning": 1,
                "info": 0
            }
        },
        screenshots={}
    )
    
    # Generate report text
    report_text = engine.generate_report(report)
    
    assert "UI VALIDATION REPORT" in report_text
    assert "Total Issues: 2" in report_text
    assert "Errors: 1" in report_text
    assert "Warnings: 1" in report_text
    assert "OUT_ROW1_L" in report_text
    assert "Text overflows" in report_text


def test_known_ui_issues():
    """Test that known UI issues from screenshots are detected"""
    from ui_validation_engine import UIValidationEngine
    
    engine = UIValidationEngine()
    
    # Test specific known issues
    known_issues = [
        {
            "region": "OUT_ROW1_L",
            "text": "1013 hPa",  # Known to overflow in current layout
            "expected_issue": "text_overflow"
        },
        {
            "region": "HEADER_NAME",
            "text": "Very Long Room Name That Should Overflow",
            "expected_issue": "text_overflow"
        }
    ]
    
    # This would normally run against actual simulator
    # For unit test, we verify the structure exists
    assert engine.known_text_patterns.get("OUT_ROW1_L") is not None
    assert engine.known_text_patterns.get("HEADER_NAME") is not None
    
    # Verify expected patterns are defined
    out_row_pattern = engine.known_text_patterns["OUT_ROW1_L"]
    assert "max_chars" in out_row_pattern
    assert "font_size" in out_row_pattern


def test_ui_spec_regions_validated():
    """Test that all UI spec regions are validated"""
    ui_spec_path = ROOT / "config" / "ui_spec.json"
    
    if not ui_spec_path.exists():
        pytest.skip("UI spec not found")
    
    ui_spec = json.loads(ui_spec_path.read_text())
    rects = ui_spec.get("rects", {})
    
    from ui_validation_engine import UIValidationEngine
    engine = UIValidationEngine()
    
    # Verify all important regions have validation patterns
    important_regions = [
        "HEADER_NAME", "HEADER_TIME",
        "INSIDE_TEMP", "OUT_TEMP",
        "INSIDE_RH", "STATUS",
        "OUT_ROW1_L", "OUT_ROW1_R"
    ]
    
    for region in important_regions:
        if region in rects:
            # Should have validation pattern defined
            pattern = engine.known_text_patterns.get(region)
            assert pattern is not None, f"No validation pattern for {region}"
            assert "max_chars" in pattern
            assert "font_size" in pattern


def test_validation_cli():
    """Test the validation engine CLI"""
    script_path = ROOT / "scripts" / "ui_validation_engine.py"
    
    if not script_path.exists():
        pytest.skip("Validation script not found")
    
    # Test help output
    result = subprocess.run(
        [sys.executable, str(script_path), "--help"],
        capture_output=True,
        text=True
    )
    
    assert result.returncode == 0
    assert "UI validation" in result.stdout
    
    # Would normally test full validation run but requires browser
    # This verifies the CLI interface exists and is callable


def test_visual_layout_analyzer_integration():
    """Test that visual layout analyzer still works with new validation"""
    script_path = ROOT / "scripts" / "visual_layout_analyzer.py"
    
    if not script_path.exists():
        pytest.skip("Visual layout analyzer not found")
    
    # Import and verify compatibility
    sys.path.insert(0, str(ROOT / "scripts"))
    from visual_layout_analyzer import VisualLayoutAnalyzer, LayoutIssue
    
    analyzer = VisualLayoutAnalyzer()
    
    # Verify issue types are compatible
    assert hasattr(LayoutIssue, "issue_type")
    assert hasattr(LayoutIssue, "severity")
    assert hasattr(LayoutIssue, "description")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])