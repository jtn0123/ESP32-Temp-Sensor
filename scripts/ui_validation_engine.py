#!/usr/bin/env python3
"""
Comprehensive UI Validation Engine for ESP32 eInk Display

Validates:
- Text overflow (text extending beyond bounding boxes)
- Region collisions (unintended overlaps)
- Content placement (text/icons properly positioned)
- Font size appropriateness
- Visual consistency across simulators
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

# Add project root to path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    import io

    import numpy as np
    from PIL import Image, ImageDraw
    from playwright.sync_api import sync_playwright
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("Install with: pip install numpy pillow playwright")
    sys.exit(1)


class ValidationSeverity(Enum):
    """Severity levels for validation issues"""
    CRITICAL = "critical"  # Must fix - breaks display
    ERROR = "error"        # Should fix - visible issues
    WARNING = "warning"    # Consider fixing - minor issues
    INFO = "info"          # FYI - potential improvements


class ValidationType(Enum):
    """Types of validation issues"""
    TEXT_OVERFLOW = "text_overflow"
    COLLISION = "collision"
    MISALIGNMENT = "misalignment"
    EMPTY_REGION = "empty_region"
    FONT_SIZE = "font_size"
    BOUNDS_EXCEED = "bounds_exceed"
    CONTENT_CLIPPED = "content_clipped"
    CONTRAST = "contrast"


@dataclass
class ValidationIssue:
    """A single validation issue"""
    issue_type: ValidationType
    severity: ValidationSeverity
    region: str
    description: str
    coordinates: Optional[Tuple[int, int, int, int]] = None  # x, y, w, h
    actual_value: Optional[Any] = None
    expected_value: Optional[Any] = None
    screenshot_region: Optional[np.ndarray] = None


@dataclass
class RegionValidation:
    """Validation results for a single region"""
    name: str
    rect: Tuple[int, int, int, int]  # x, y, w, h
    category: str
    issues: List[ValidationIssue] = field(default_factory=list)
    pixel_coverage: float = 0.0
    content_bounds: Optional[Tuple[int, int, int, int]] = None
    text_content: Optional[str] = None
    font_metrics: Optional[Dict[str, float]] = None


@dataclass
class ValidationReport:
    """Complete validation report"""
    timestamp: str
    variant: str
    total_regions: int
    regions: Dict[str, RegionValidation]
    issues: List[ValidationIssue]
    summary: Dict[str, Any]
    screenshots: Dict[str, np.ndarray]


class UIValidationEngine:
    """Main validation engine for UI testing"""

    def __init__(self, web_root: Optional[str] = None):
        self.web_root = web_root or str(ROOT / "web" / "sim")
        self.out_dir = ROOT / "validation_reports"
        self.out_dir.mkdir(exist_ok=True)
        self.ui_spec = self._load_ui_spec()
        self.known_text_patterns = self._load_text_patterns()

    def _load_ui_spec(self) -> Dict[str, Any]:
        """Load UI specification"""
        spec_path = ROOT / "config" / "ui_spec.json"
        if spec_path.exists():
            return json.loads(spec_path.read_text())
        return {}

    def _load_text_patterns(self) -> Dict[str, Dict[str, Any]]:
        """Load expected text patterns for each region"""
        # Define expected content patterns and size constraints
        return {
            "HEADER_NAME": {
                "max_chars": 20,
                "expected_pattern": r"^[A-Za-z0-9 \-]+$",
                "font_size": 14,
                "single_line": True
            },
            "HEADER_TIME": {
                "max_chars": 8,
                "expected_pattern": r"^\d{1,2}:\d{2}(am|pm)?$",
                "font_size": 11,
                "single_line": True
            },
            "INSIDE_TEMP": {
                "max_chars": 7,
                "expected_pattern": r"^-?\d{1,3}\.?\d?°?[FC]?$",
                "font_size": 22,
                "single_line": True
            },
            "OUT_TEMP": {
                "max_chars": 7,
                "expected_pattern": r"^-?\d{1,3}\.?\d?°?[FC]?$",
                "font_size": 22,
                "single_line": True
            },
            "INSIDE_RH": {
                "max_chars": 10,
                "expected_pattern": r"^\d{1,3}%( RH)?$",
                "font_size": 11,
                "single_line": True
            },
            "STATUS": {
                "max_chars": 40,
                "expected_pattern": r".*",
                "font_size": 10,
                "single_line": True
            },
            "OUT_ROW1_L": {
                "max_chars": 10,
                "expected_pattern": r"^\d{1,4}\.?\d?\s*(hPa|mb|%)?$",
                "font_size": 11,
                "single_line": True
            },
            "OUT_ROW1_R": {
                "max_chars": 12,
                "expected_pattern": r"^\d{1,3}\.?\d?\s*mph$",
                "font_size": 11,
                "single_line": True
            }
        }

    def validate_text_overflow(self, page, region: RegionValidation) -> List[ValidationIssue]:
        """Validate that text doesn't overflow its bounding box"""
        issues = []

        # Get computed text metrics from the page
        try:
            script = f"""
            (() => {{
                const canvas = document.createElement('canvas');
                const ctx = canvas.getContext('2d');
                const rect = {json.dumps(region.rect)};
                const name = '{region.name}';

                // Try to get the actual text content
                let text = '';
                const el = document.querySelector(`[data-region="${{name}}"]`);
                if (el) text = el.textContent || '';

                // Estimate text bounds based on region's expected font
                const fontSize = {
                    self.known_text_patterns.get(region.name, {}).get('font_size', 11)
                };
                ctx.font = `${{fontSize}}px monospace`;
                const metrics = ctx.measureText(text || 'Sample Text');

                return {{
                    text: text,
                    textWidth: metrics.width,
                    textHeight: fontSize * 1.2,  // Approximate line height
                    rectWidth: rect[2],
                    rectHeight: rect[3]
                }};
            }})()
            """
            metrics = page.evaluate(script)

            if metrics and metrics.get('text'):
                text_width = metrics['textWidth']
                text_height = metrics['textHeight']
                rect_width = metrics['rectWidth']
                rect_height = metrics['rectHeight']

                # Check horizontal overflow
                if text_width > rect_width:
                    overflow_px = text_width - rect_width
                    overflow_pct = (overflow_px / rect_width) * 100

                    severity = (ValidationSeverity.CRITICAL if overflow_pct > 50 else
                               ValidationSeverity.ERROR if overflow_pct > 20 else
                               ValidationSeverity.WARNING)

                    issues.append(ValidationIssue(
                        issue_type=ValidationType.TEXT_OVERFLOW,
                        severity=severity,
                        region=region.name,
                        description=(
                            f"Text overflows horizontally by {overflow_px:.1f}px "
                            f"({overflow_pct:.1f}%)"
                        ),
                        coordinates=region.rect,
                        actual_value=f"{text_width:.1f}px",
                        expected_value=f"<={rect_width}px"
                    ))

                # Check vertical overflow
                if text_height > rect_height:
                    overflow_px = text_height - rect_height
                    overflow_pct = (overflow_px / rect_height) * 100

                    severity = (ValidationSeverity.ERROR if overflow_pct > 50 else
                               ValidationSeverity.WARNING)

                    issues.append(ValidationIssue(
                        issue_type=ValidationType.TEXT_OVERFLOW,
                        severity=severity,
                        region=region.name,
                        description=(
                            f"Text overflows vertically by {overflow_px:.1f}px "
                            f"({overflow_pct:.1f}%)"
                        ),
                        coordinates=region.rect,
                        actual_value=f"{text_height:.1f}px",
                        expected_value=f"<={rect_height}px"
                    ))

                region.text_content = metrics.get('text', '')
                region.font_metrics = metrics

        except Exception as e:
            print(f"Warning: Could not measure text for {region.name}: {e}")

        return issues

    def validate_content_bounds(
        self, img: np.ndarray, region: RegionValidation
    ) -> List[ValidationIssue]:
        """Validate that actual content stays within region bounds"""
        issues = []
        x, y, w, h = region.rect

        # Extract region from image
        region_img = img[y:y+h, x:x+w]

        # Convert to grayscale and find content pixels
        gray = np.dot(region_img[..., :3], [0.2126, 0.7152, 0.0722])
        content_mask = gray < 176  # Dark pixels are content

        if np.any(content_mask):
            # Find actual content bounds
            rows, cols = np.where(content_mask)
            min_row, max_row = rows.min(), rows.max()
            min_col, max_col = cols.min(), cols.max()

            content_width = max_col - min_col + 1
            content_height = max_row - min_row + 1

            # Check if content is clipped at edges
            edge_threshold = 2  # pixels

            if min_row < edge_threshold:
                issues.append(ValidationIssue(
                    issue_type=ValidationType.CONTENT_CLIPPED,
                    severity=ValidationSeverity.ERROR,
                    region=region.name,
                    description="Content appears clipped at top edge",
                    coordinates=(x + min_col, y + min_row, content_width, content_height)
                ))

            if max_row >= h - edge_threshold:
                issues.append(ValidationIssue(
                    issue_type=ValidationType.CONTENT_CLIPPED,
                    severity=ValidationSeverity.ERROR,
                    region=region.name,
                    description="Content appears clipped at bottom edge",
                    coordinates=(x + min_col, y + min_row, content_width, content_height)
                ))

            if min_col < edge_threshold:
                issues.append(ValidationIssue(
                    issue_type=ValidationType.CONTENT_CLIPPED,
                    severity=ValidationSeverity.ERROR,
                    region=region.name,
                    description="Content appears clipped at left edge",
                    coordinates=(x + min_col, y + min_row, content_width, content_height)
                ))

            if max_col >= w - edge_threshold:
                issues.append(ValidationIssue(
                    issue_type=ValidationType.CONTENT_CLIPPED,
                    severity=ValidationSeverity.ERROR,
                    region=region.name,
                    description="Content appears clipped at right edge",
                    coordinates=(x + min_col, y + min_row, content_width, content_height)
                ))

            # Store actual content bounds
            region.content_bounds = (x + min_col, y + min_row, content_width, content_height)
            region.pixel_coverage = (np.sum(content_mask) / (w * h)) * 100

        return issues

    def validate_collisions(self, regions: Dict[str, RegionValidation]) -> List[ValidationIssue]:
        """Validate that regions don't have unintended collisions"""
        issues = []

        # Define which overlaps are expected/allowed
        allowed_overlaps = {
            ("INSIDE_TEMP", "INSIDE_LABEL_BOX"),
            ("OUT_TEMP", "OUT_LABEL_BOX"),
            ("FOOTER_R", "WEATHER_ICON"),
        }

        # Check all pairs of regions
        region_list = list(regions.values())
        for i, region1 in enumerate(region_list):
            for region2 in region_list[i+1:]:
                x1, y1, w1, h1 = region1.rect
                x2, y2, w2, h2 = region2.rect

                # Calculate overlap
                overlap_x = max(0, min(x1 + w1, x2 + w2) - max(x1, x2))
                overlap_y = max(0, min(y1 + h1, y2 + h2) - max(y1, y2))

                if overlap_x > 0 and overlap_y > 0:
                    # Check if this overlap is allowed
                    pair = tuple(sorted([region1.name, region2.name]))
                    if pair in allowed_overlaps:
                        continue

                    overlap_area = overlap_x * overlap_y
                    smaller_area = min(w1 * h1, w2 * h2)
                    overlap_pct = (overlap_area / smaller_area) * 100 if smaller_area > 0 else 0

                    # Check if content actually collides
                    content_collision = False
                    if region1.content_bounds and region2.content_bounds:
                        c1x, c1y, c1w, c1h = region1.content_bounds
                        c2x, c2y, c2w, c2h = region2.content_bounds

                        content_overlap_x = max(0, min(c1x + c1w, c2x + c2w) - max(c1x, c2x))
                        content_overlap_y = max(0, min(c1y + c1h, c2y + c2h) - max(c1y, c2y))
                        content_collision = content_overlap_x > 0 and content_overlap_y > 0

                    if content_collision:
                        severity = ValidationSeverity.CRITICAL
                        desc = f"Content collision between {region1.name} and {region2.name}"
                    elif overlap_pct > 50:
                        severity = ValidationSeverity.ERROR
                        desc = (
                            f"Major overlap ({overlap_pct:.1f}%) between "
                            f"{region1.name} and {region2.name}"
                        )
                    elif overlap_pct > 10:
                        severity = ValidationSeverity.WARNING
                        desc = (
                            f"Overlap ({overlap_pct:.1f}%) between "
                            f"{region1.name} and {region2.name}"
                        )
                    else:
                        severity = ValidationSeverity.INFO
                        desc = (
                            f"Minor overlap ({overlap_pct:.1f}%) between "
                            f"{region1.name} and {region2.name}"
                        )

                    issues.append(ValidationIssue(
                        issue_type=ValidationType.COLLISION,
                        severity=severity,
                        region=f"{region1.name},{region2.name}",
                        description=desc,
                        coordinates=(max(x1, x2), max(y1, y2), overlap_x, overlap_y),
                        actual_value=f"{overlap_area}px²",
                        expected_value="0px²"
                    ))

        return issues

    def validate_alignment(self, regions: Dict[str, RegionValidation]) -> List[ValidationIssue]:
        """Validate alignment constraints between regions"""
        issues = []

        # Check inside elements alignment
        inside_regions = [r for r in regions.values() if r.name.startswith("INSIDE_")]
        if len(inside_regions) >= 2:
            x_positions = {r.rect[0] for r in inside_regions}
            if len(x_positions) > 1:
                issues.append(ValidationIssue(
                    issue_type=ValidationType.MISALIGNMENT,
                    severity=ValidationSeverity.WARNING,
                    region=",".join([r.name for r in inside_regions]),
                    description=(
                        f"Inside elements not left-aligned: x positions "
                        f"{sorted(x_positions)}"
                    ),
                    actual_value=str(sorted(x_positions)),
                    expected_value=str(min(x_positions))
                ))

        # Check row alignment
        for prefix in ["OUT_ROW1_", "OUT_ROW2_"]:
            row_regions = [r for r in regions.values() if r.name.startswith(prefix)]
            if len(row_regions) >= 2:
                y_positions = {r.rect[1] for r in row_regions}
                if len(y_positions) > 1 and max(y_positions) - min(y_positions) > 1:
                    issues.append(ValidationIssue(
                        issue_type=ValidationType.MISALIGNMENT,
                        severity=ValidationSeverity.WARNING,
                        region=",".join([r.name for r in row_regions]),
                        description=(
                            f"Row elements not horizontally aligned: y positions "
                            f"{sorted(y_positions)}"
                        ),
                        actual_value=str(sorted(y_positions)),
                        expected_value=str(min(y_positions))
                    ))

        # Check 4-pixel grid alignment for v2 layouts
        for region in regions.values():
            x, y, w, h = region.rect
            if x % 4 != 0 or y % 4 != 0:
                issues.append(ValidationIssue(
                    issue_type=ValidationType.MISALIGNMENT,
                    severity=ValidationSeverity.INFO,
                    region=region.name,
                    description=f"Position ({x},{y}) not aligned to 4px grid",
                    coordinates=region.rect,
                    actual_value=f"({x},{y})",
                    expected_value="4px multiples"
                ))

        return issues

    def validate_font_sizes(self, regions: Dict[str, RegionValidation]) -> List[ValidationIssue]:
        """Validate that font sizes are appropriate for their regions"""
        issues = []

        for region in regions.values():
            if region.name in self.known_text_patterns:
                pattern = self.known_text_patterns[region.name]
                expected_font = pattern.get("font_size", 11)

                # Minimum height needed for font (roughly 1.5x font size for padding)
                min_height = expected_font * 1.5
                actual_height = region.rect[3]

                if actual_height < min_height:
                    issues.append(ValidationIssue(
                        issue_type=ValidationType.FONT_SIZE,
                        severity=ValidationSeverity.ERROR,
                        region=region.name,
                        description=f"Region too small for {expected_font}px font",
                        coordinates=region.rect,
                        actual_value=f"{actual_height}px height",
                        expected_value=f">={min_height:.1f}px height"
                    ))

        return issues

    def _start_http_server(self, port: int) -> subprocess.Popen:
        """Start local HTTP server for web simulator"""
        return subprocess.Popen(
            [
                sys.executable, "-m", "http.server", str(port),
                "--bind", "127.0.0.1", "-d", self.web_root
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

    def _find_free_port(self) -> int:
        """Find an available port"""
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            return s.getsockname()[1]

    def capture_screenshot(self, page) -> np.ndarray:
        """Capture screenshot of the simulator"""
        screenshot_bytes = page.screenshot(clip={"x": 0, "y": 0, "width": 250, "height": 122})
        img = Image.open(io.BytesIO(screenshot_bytes)).convert("RGB")
        return np.array(img)

    def run_validation(self,
                      test_scenarios: Optional[List[Dict[str, Any]]] = None,
                      variant: str = "v2_grid") -> ValidationReport:
        """Run complete validation suite"""

        from datetime import datetime

        # Default test scenarios with various edge cases
        if test_scenarios is None:
            test_scenarios = [
                {
                    "name": "normal",
                    "data": {
                        "room_name": "Living Room",
                        "time": "10:15",
                        "inside_temp": "72.5",
                        "outside_temp": "68.4",
                        "inside_rh": "47%",
                        "outside_rh": "1013 hPa",  # This was causing overflow
                        "wind": "12.5 mph",
                        "condition": "cloudy"
                    }
                },
                {
                    "name": "extreme_values",
                    "data": {
                        "room_name": "Very Long Room Name That Might Overflow",
                        "time": "12:59pm",
                        "inside_temp": "-999.9",
                        "outside_temp": "999.9",
                        "inside_rh": "100%",
                        "outside_rh": "9999 hPa",
                        "wind": "999.9 mph",
                        "condition": "thunderstorm"
                    }
                }
            ]

        port = self._find_free_port()
        server = self._start_http_server(port)

        all_issues = []
        all_regions = {}
        screenshots = {}

        try:
            time.sleep(0.5)  # Let server start

            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page(viewport={"width": 700, "height": 400})

                for scenario in test_scenarios:
                    # Load simulator with test data
                    url = f"http://127.0.0.1:{port}/index.html"
                    if "data" in scenario:
                        # Pass test data via URL params or page evaluation
                        page.goto(url, wait_until="load")
                        page.wait_for_timeout(300)

                        # Inject test data
                        page.evaluate(f"""
                        window.testData = {json.dumps(scenario['data'])};
                        if (window.draw) window.draw();
                        """)
                    else:
                        page.goto(url, wait_until="load")

                    page.wait_for_timeout(200)

                    # Capture screenshot
                    screenshot = self.capture_screenshot(page)
                    screenshots[scenario['name']] = screenshot

                    # Get regions from UI spec, filtering out internal helper rectangles
                    regions = {}
                    if self.ui_spec and "rects" in self.ui_spec:
                        for name, rect in self.ui_spec["rects"].items():
                            # Skip internal helper rectangles - these are implementation details
                            if self._is_internal_helper_rect(name):
                                continue
                            regions[name] = RegionValidation(
                                name=name,
                                rect=tuple(rect),
                                category=self._categorize_region(name)
                            )

                    # Run all validations
                    for region in regions.values():
                        # Validate text overflow
                        issues = self.validate_text_overflow(page, region)
                        region.issues.extend(issues)
                        all_issues.extend(issues)

                        # Validate content bounds
                        issues = self.validate_content_bounds(screenshot, region)
                        region.issues.extend(issues)
                        all_issues.extend(issues)

                    # Validate collisions
                    collision_issues = self.validate_collisions(regions)
                    all_issues.extend(collision_issues)

                    # Validate alignment
                    alignment_issues = self.validate_alignment(regions)
                    all_issues.extend(alignment_issues)

                    # Validate font sizes
                    font_issues = self.validate_font_sizes(regions)
                    all_issues.extend(font_issues)

                    # Merge regions
                    for name, region in regions.items():
                        if (
                            name not in all_regions or
                            len(region.issues) > len(all_regions[name].issues)
                        ):
                            all_regions[name] = region

                browser.close()

        finally:
            server.terminate()
            server.wait(timeout=2)

        # Generate summary
        summary = {
            "total_issues": len(all_issues),
            "by_severity": {
                ValidationSeverity.CRITICAL.value: len([
                    i for i in all_issues if i.severity == ValidationSeverity.CRITICAL
                ]),
                ValidationSeverity.ERROR.value: len([
                    i for i in all_issues if i.severity == ValidationSeverity.ERROR
                ]),
                ValidationSeverity.WARNING.value: len([
                    i for i in all_issues if i.severity == ValidationSeverity.WARNING
                ]),
                ValidationSeverity.INFO.value: len([
                    i for i in all_issues if i.severity == ValidationSeverity.INFO
                ])
            },
            "by_type": {
                t.value: len([i for i in all_issues if i.issue_type == t])
                for t in ValidationType
            },
            "regions_with_issues": len([r for r in all_regions.values() if r.issues]),
            "clean_regions": len([r for r in all_regions.values() if not r.issues])
        }

        return ValidationReport(
            timestamp=datetime.now().isoformat(),
            variant=variant,
            total_regions=len(all_regions),
            regions=all_regions,
            issues=all_issues,
            summary=summary,
            screenshots=screenshots
        )

    def _is_internal_helper_rect(self, name: str) -> bool:
        """Check if a rectangle is an internal helper (not a real display region)"""
        return '_INNER' in name or '_BADGE' in name or 'LABEL_BOX' in name

    def _categorize_region(self, name: str) -> str:
        """Categorize a region by its name"""
        n = name.lower()
        if "header" in n:
            return "header"
        if "footer" in n or "status" in n:
            return "footer"
        if "temp" in n:
            return "temp"
        if "label" in n or "rh" in n:
            return "label"
        return "other"

    def generate_report(self, validation: ValidationReport) -> str:
        """Generate human-readable validation report"""
        lines = [
            "=" * 80,
            "UI VALIDATION REPORT",
            "=" * 80,
            f"Timestamp: {validation.timestamp}",
            f"Variant: {validation.variant}",
            f"Total Regions: {validation.total_regions}",
            "",
            "SUMMARY",
            "-" * 40,
            f"Total Issues: {validation.summary['total_issues']}",
            f"  Critical: {validation.summary['by_severity']['critical']}",
            f"  Errors: {validation.summary['by_severity']['error']}",
            f"  Warnings: {validation.summary['by_severity']['warning']}",
            f"  Info: {validation.summary['by_severity']['info']}",
            "",
            f"Regions with Issues: {validation.summary['regions_with_issues']}",
            f"Clean Regions: {validation.summary['clean_regions']}",
            ""
        ]

        if validation.issues:
            lines.extend([
                "ISSUES BY SEVERITY",
                "-" * 40,
            ])

            for severity in [ValidationSeverity.CRITICAL, ValidationSeverity.ERROR,
                           ValidationSeverity.WARNING, ValidationSeverity.INFO]:
                severity_issues = [i for i in validation.issues if i.severity == severity]
                if severity_issues:
                    icon = {
                        ValidationSeverity.CRITICAL: "🔴",
                        ValidationSeverity.ERROR: "🟠",
                        ValidationSeverity.WARNING: "🟡",
                        ValidationSeverity.INFO: "ℹ️"
                    }[severity]

                    lines.append(
                        f"\n{icon} {severity.value.upper()} "
                        f"({len(severity_issues)} issues):"
                    )
                    for issue in severity_issues[:10]:  # Limit to first 10 of each type
                        lines.append(f"  • [{issue.region}] {issue.description}")
                        if issue.actual_value and issue.expected_value:
                            lines.append(
                                f"    Actual: {issue.actual_value}, "
                                f"Expected: {issue.expected_value}"
                            )

        lines.extend([
            "",
            "REGION DETAILS",
            "-" * 40,
        ])

        for region in validation.regions.values():
            if region.issues:
                lines.append(f"\n{region.name} ({region.category}):")
                lines.append(f"  Rectangle: {region.rect}")
                lines.append(f"  Coverage: {region.pixel_coverage:.1f}%")
                lines.append(f"  Issues: {len(region.issues)}")
                for issue in region.issues[:3]:  # First 3 issues per region
                    lines.append(f"    - {issue.description}")

        return "\n".join(lines)

    def save_report(self, validation: ValidationReport):
        """Save validation report and artifacts"""
        timestamp = validation.timestamp.replace(":", "-").replace(".", "-")
        report_dir = self.out_dir / f"validation_{timestamp}"
        report_dir.mkdir(exist_ok=True)

        # Save text report
        report_text = self.generate_report(validation)
        (report_dir / "report.txt").write_text(report_text)

        # Save JSON report
        report_json = {
            "timestamp": validation.timestamp,
            "variant": validation.variant,
            "summary": validation.summary,
            "issues": [
                {
                    "type": i.issue_type.value,
                    "severity": i.severity.value,
                    "region": i.region,
                    "description": i.description,
                    "actual": i.actual_value,
                    "expected": i.expected_value
                }
                for i in validation.issues
            ]
        }
        (report_dir / "report.json").write_text(json.dumps(report_json, indent=2))

        # Save screenshots with annotations
        for name, screenshot in validation.screenshots.items():
            img = Image.fromarray(screenshot)

            # Create annotated version
            annotated = img.copy()
            ImageDraw.Draw(annotated)

            # Draw regions with issues
            for region in validation.regions.values():
                if region.issues:
                    x, y, w, h = region.rect
                    # Color based on worst severity
                    severities = [i.severity for i in region.issues]
                    if ValidationSeverity.CRITICAL in severities:
                        color = (255, 0, 0, 128)  # Red
                    elif ValidationSeverity.ERROR in severities:
                        color = (255, 128, 0, 128)  # Orange
                    elif ValidationSeverity.WARNING in severities:
                        color = (255, 255, 0, 128)  # Yellow
                    else:
                        color = (0, 128, 255, 128)  # Blue

                    # Draw semi-transparent overlay
                    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
                    overlay_draw = ImageDraw.Draw(overlay)
                    overlay_draw.rectangle(
                        [x, y, x + w - 1, y + h - 1],
                        fill=color,
                        outline=color[:3] + (255,),
                        width=2
                    )
                    annotated = Image.alpha_composite(
                        annotated.convert("RGBA"), overlay
                    ).convert("RGB")

            # Save both versions
            img.save(report_dir / f"{name}_original.png")
            annotated.save(report_dir / f"{name}_annotated.png")

        print(f"Report saved to: {report_dir}")
        return report_dir


def main():
    """CLI entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Comprehensive UI validation for ESP32 display")
    parser.add_argument("--web-root", help="Path to web simulator root")
    parser.add_argument("--variant", default="v2_grid", help="Layout variant to test")
    parser.add_argument("--scenario", help="Test scenario JSON file")
    parser.add_argument("--save", action="store_true", help="Save report to disk")
    parser.add_argument("--fail-on-critical", action="store_true",
                       help="Exit with error if critical issues found")

    args = parser.parse_args()

    # Load test scenarios if provided
    test_scenarios = None
    if args.scenario:
        with open(args.scenario) as f:
            test_scenarios = json.load(f)

    # Run validation
    engine = UIValidationEngine(web_root=args.web_root)
    report = engine.run_validation(test_scenarios=test_scenarios, variant=args.variant)

    # Print report
    print(engine.generate_report(report))

    # Save if requested
    if args.save:
        engine.save_report(report)

    # Exit with error if critical issues found
    if args.fail_on_critical and report.summary["by_severity"]["critical"] > 0:
        print(f"\n❌ Found {report.summary['by_severity']['critical']} critical issues!")
        sys.exit(1)

    print(f"\n✅ Validation complete: {report.summary['total_issues']} issues found")


if __name__ == "__main__":
    main()
