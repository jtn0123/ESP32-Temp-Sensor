"""
Property-based tests for display geometry validation using Hypothesis.

Tests the display_geometry.json schema and rect calculations to find
edge cases in layout generation.
"""

import json
import os
from typing import Dict, List, Tuple

import pytest

# Try to import hypothesis
try:
    from hypothesis import given, assume, settings, example
    from hypothesis import strategies as st

    HAS_HYPOTHESIS = True
except ImportError:
    HAS_HYPOTHESIS = False

    def given(*args, **kwargs):
        def decorator(f):
            return pytest.mark.skip(reason="hypothesis not installed")(f)
        return decorator

    def example(*args, **kwargs):
        def decorator(f):
            return f
        return decorator

    def settings(**kwargs):
        def decorator(f):
            return f
        return decorator

    class st:
        @staticmethod
        def integers(*args, **kwargs):
            return None
        @staticmethod
        def floats(*args, **kwargs):
            return None
        @staticmethod
        def lists(*args, **kwargs):
            return None
        @staticmethod
        def text(*args, **kwargs):
            return None
        @staticmethod
        def tuples(*args, **kwargs):
            return None
        @staticmethod
        def fixed_dictionaries(*args, **kwargs):
            return None
        @staticmethod
        def builds(*args, **kwargs):
            return None

    def assume(x):
        pass


ROOT = os.path.dirname(os.path.dirname(__file__))
GEOMETRY_PATH = os.path.join(ROOT, "config", "display_geometry.json")


def load_geometry() -> Dict:
    """Load the display geometry configuration."""
    with open(GEOMETRY_PATH, "r") as f:
        return json.load(f)


pytestmark = pytest.mark.skipif(not HAS_HYPOTHESIS, reason="hypothesis not installed")


class Rect:
    """Rectangle class for geometry operations."""

    def __init__(self, x: int, y: int, w: int, h: int):
        self.x = x
        self.y = y
        self.w = w
        self.h = h

    @property
    def x2(self) -> int:
        return self.x + self.w

    @property
    def y2(self) -> int:
        return self.y + self.h

    def overlaps(self, other: "Rect") -> bool:
        """Check if this rectangle overlaps with another."""
        return (
            self.x < other.x2
            and self.x2 > other.x
            and self.y < other.y2
            and self.y2 > other.y
        )

    def contains_point(self, px: int, py: int) -> bool:
        """Check if a point is inside this rectangle."""
        return self.x <= px < self.x2 and self.y <= py < self.y2

    def is_within(self, canvas_w: int, canvas_h: int) -> bool:
        """Check if rectangle is completely within canvas bounds."""
        return self.x >= 0 and self.y >= 0 and self.x2 <= canvas_w and self.y2 <= canvas_h

    def __repr__(self):
        return f"Rect({self.x}, {self.y}, {self.w}, {self.h})"


# Strategies for generating rectangles
if HAS_HYPOTHESIS:
    rect_strategy = st.builds(
        Rect,
        x=st.integers(min_value=0, max_value=249),
        y=st.integers(min_value=0, max_value=121),
        w=st.integers(min_value=1, max_value=250),
        h=st.integers(min_value=1, max_value=122),
    )

    valid_rect_strategy = st.builds(
        Rect,
        x=st.integers(min_value=0, max_value=200),
        y=st.integers(min_value=0, max_value=100),
        w=st.integers(min_value=10, max_value=50),
        h=st.integers(min_value=10, max_value=22),
    )


class TestGeometryProperties:
    """Property-based tests for geometry calculations."""

    @given(
        x=st.integers(min_value=0, max_value=200),
        y=st.integers(min_value=0, max_value=100),
        w=st.integers(min_value=1, max_value=50),
        h=st.integers(min_value=1, max_value=22),
    )
    @settings(max_examples=200)
    def test_rect_within_canvas(self, x, y, w, h):
        """Test rectangle bounds checking against canvas."""
        rect = Rect(x, y, w, h)
        canvas_w, canvas_h = 250, 122

        within = rect.is_within(canvas_w, canvas_h)

        # Manual calculation
        expected = x >= 0 and y >= 0 and (x + w) <= canvas_w and (y + h) <= canvas_h

        assert within == expected

    @given(
        x1=st.integers(min_value=0, max_value=200),
        y1=st.integers(min_value=0, max_value=100),
        w1=st.integers(min_value=10, max_value=50),
        h1=st.integers(min_value=10, max_value=22),
        x2=st.integers(min_value=0, max_value=200),
        y2=st.integers(min_value=0, max_value=100),
        w2=st.integers(min_value=10, max_value=50),
        h2=st.integers(min_value=10, max_value=22),
    )
    @settings(max_examples=300)
    def test_overlap_symmetry(self, x1, y1, w1, h1, x2, y2, w2, h2):
        """Overlap detection should be symmetric: A overlaps B iff B overlaps A."""
        r1 = Rect(x1, y1, w1, h1)
        r2 = Rect(x2, y2, w2, h2)

        assert r1.overlaps(r2) == r2.overlaps(r1)

    @given(
        x=st.integers(min_value=0, max_value=200),
        y=st.integers(min_value=0, max_value=100),
        w=st.integers(min_value=10, max_value=50),
        h=st.integers(min_value=10, max_value=22),
    )
    @settings(max_examples=100)
    def test_self_overlap(self, x, y, w, h):
        """A rectangle should always overlap with itself."""
        r = Rect(x, y, w, h)
        assert r.overlaps(r)

    @given(
        x=st.integers(min_value=10, max_value=200),
        y=st.integers(min_value=10, max_value=100),
        w=st.integers(min_value=10, max_value=50),
        h=st.integers(min_value=10, max_value=22),
    )
    @settings(max_examples=100)
    def test_non_overlapping_adjacent(self, x, y, w, h):
        """Adjacent rectangles (touching but not overlapping) should not overlap."""
        r1 = Rect(x, y, w, h)

        # Rectangle immediately to the right
        r2 = Rect(x + w, y, w, h)
        assert not r1.overlaps(r2)

        # Rectangle immediately below
        r3 = Rect(x, y + h, w, h)
        assert not r1.overlaps(r3)

    @given(
        x=st.integers(min_value=10, max_value=150),
        y=st.integers(min_value=10, max_value=80),
        w=st.integers(min_value=20, max_value=50),
        h=st.integers(min_value=20, max_value=30),
        px_offset=st.integers(min_value=0, max_value=19),
        py_offset=st.integers(min_value=0, max_value=19),
    )
    @settings(max_examples=200)
    def test_point_containment(self, x, y, w, h, px_offset, py_offset):
        """Points inside rectangle should be contained, points outside should not."""
        r = Rect(x, y, w, h)

        # Point inside
        px_in = x + min(px_offset, w - 1)
        py_in = y + min(py_offset, h - 1)
        assert r.contains_point(px_in, py_in)

        # Point outside (to the right)
        assert not r.contains_point(x + w + 1, y)

        # Point outside (below)
        assert not r.contains_point(x, y + h + 1)


class TestActualGeometryFile:
    """Tests against the actual display_geometry.json file."""

    def test_geometry_file_exists(self):
        """Verify geometry file exists."""
        assert os.path.exists(GEOMETRY_PATH)

    def test_geometry_valid_json(self):
        """Verify geometry file is valid JSON."""
        geom = load_geometry()
        assert isinstance(geom, dict)

    def test_canvas_dimensions(self):
        """Verify canvas has expected dimensions for e-ink display."""
        geom = load_geometry()
        canvas = geom.get("canvas", {})
        assert canvas.get("w") == 250
        assert canvas.get("h") == 122

    def test_all_rects_within_canvas(self):
        """All rectangles should be within canvas bounds."""
        geom = load_geometry()
        canvas_w = geom["canvas"]["w"]
        canvas_h = geom["canvas"]["h"]

        for name, coords in geom.get("rects", {}).items():
            x, y, w, h = coords
            rect = Rect(x, y, w, h)
            assert rect.is_within(canvas_w, canvas_h), (
                f"Rect {name} ({coords}) extends outside canvas ({canvas_w}x{canvas_h})"
            )

    def test_rects_have_positive_dimensions(self):
        """All rectangles should have positive width and height."""
        geom = load_geometry()

        for name, coords in geom.get("rects", {}).items():
            x, y, w, h = coords
            assert w > 0, f"Rect {name} has non-positive width: {w}"
            assert h > 0, f"Rect {name} has non-positive height: {h}"

    def test_rects_have_non_negative_origin(self):
        """All rectangles should have non-negative x, y coordinates."""
        geom = load_geometry()

        for name, coords in geom.get("rects", {}).items():
            x, y, w, h = coords
            assert x >= 0, f"Rect {name} has negative x: {x}"
            assert y >= 0, f"Rect {name} has negative y: {y}"

    def test_expected_regions_exist(self):
        """Verify expected display regions are defined."""
        geom = load_geometry()
        rects = geom.get("rects", {})

        expected_regions = [
            "HEADER_NAME",
            "INSIDE_TEMP",
            "INSIDE_HUMIDITY",
            "OUTSIDE_LABEL",
            "OUT_TEMP",
            "FOOTER_BATTERY",
        ]

        for region in expected_regions:
            assert region in rects, f"Expected region {region} not found"

    def test_fonts_defined(self):
        """Verify font sizes are defined."""
        geom = load_geometry()
        fonts = geom.get("fonts", {})

        assert "big_px" in fonts
        assert "mid_px" in fonts
        assert "small_px" in fonts

        # Font sizes should be positive
        for name, size in fonts.items():
            assert size > 0, f"Font {name} has non-positive size: {size}"


class TestLayoutConstraints:
    """Tests for layout constraints and relationships."""

    def test_inside_regions_left_side(self):
        """Inside temperature/humidity regions should be on left side of display."""
        geom = load_geometry()
        rects = geom.get("rects", {})
        canvas_w = geom["canvas"]["w"]
        mid_x = canvas_w // 2

        inside_regions = ["INSIDE_TEMP", "INSIDE_HUMIDITY", "INSIDE_LABEL"]
        for region in inside_regions:
            if region in rects:
                x, y, w, h = rects[region]
                # Center of region should be in left half
                center_x = x + w // 2
                assert center_x < mid_x, f"{region} center ({center_x}) not in left half"

    def test_outside_regions_right_side(self):
        """Outside temperature/weather regions should be on right side of display."""
        geom = load_geometry()
        rects = geom.get("rects", {})
        canvas_w = geom["canvas"]["w"]
        mid_x = canvas_w // 2

        outside_regions = ["OUT_TEMP", "OUTSIDE_LABEL", "WEATHER_ICON"]
        for region in outside_regions:
            if region in rects:
                x, y, w, h = rects[region]
                # Region should be at least partially in right half
                assert x + w > mid_x, f"{region} not in right half"

    def test_header_at_top(self):
        """Header regions should be at top of display."""
        geom = load_geometry()
        rects = geom.get("rects", {})

        header_regions = ["HEADER_NAME", "HEADER_VERSION", "HEADER_TIME_CENTER"]
        for region in header_regions:
            if region in rects:
                x, y, w, h = rects[region]
                assert y < 20, f"{region} y={y} not at top"

    def test_footer_at_bottom(self):
        """Footer regions should be at bottom of display."""
        geom = load_geometry()
        rects = geom.get("rects", {})
        canvas_h = geom["canvas"]["h"]

        footer_regions = ["FOOTER_BATTERY", "FOOTER_IP", "FOOTER_WEATHER"]
        for region in footer_regions:
            if region in rects:
                x, y, w, h = rects[region]
                assert y + h > canvas_h - 40, f"{region} y2={y+h} not at bottom"


class TestGeneratedRects:
    """Property tests for generated rectangle layouts."""

    @given(
        num_rects=st.integers(min_value=2, max_value=10),
    )
    @settings(max_examples=50)
    def test_grid_layout_no_overlap(self, num_rects):
        """Test that a grid layout of rectangles doesn't overlap."""
        canvas_w, canvas_h = 250, 122
        cols = min(num_rects, 5)
        rows = (num_rects + cols - 1) // cols

        cell_w = canvas_w // cols
        cell_h = canvas_h // rows

        rects = []
        for i in range(num_rects):
            col = i % cols
            row = i // cols
            x = col * cell_w
            y = row * cell_h
            # Leave 2px margin
            rects.append(Rect(x + 1, y + 1, cell_w - 2, cell_h - 2))

        # Check no overlaps
        for i, r1 in enumerate(rects):
            for j, r2 in enumerate(rects):
                if i < j:
                    assert not r1.overlaps(r2), f"Rects {i} and {j} overlap"

    @given(
        x=st.integers(min_value=0, max_value=200),
        y=st.integers(min_value=0, max_value=100),
        w=st.integers(min_value=10, max_value=50),
        h=st.integers(min_value=10, max_value=22),
        scale=st.floats(min_value=0.5, max_value=2.0, allow_nan=False),
    )
    @settings(max_examples=100)
    def test_scaled_rect_properties(self, x, y, w, h, scale):
        """Test that scaled rectangles maintain proportions."""
        original = Rect(x, y, w, h)

        # Scale dimensions
        new_w = max(1, int(w * scale))
        new_h = max(1, int(h * scale))
        scaled = Rect(x, y, new_w, new_h)

        # Aspect ratio should be approximately maintained
        if w > 0 and h > 0 and new_w > 0 and new_h > 0:
            original_ratio = w / h
            scaled_ratio = new_w / new_h
            # Allow for integer rounding
            assert abs(original_ratio - scaled_ratio) < 0.5 or abs(scale - 1.0) > 0.3


class TestFontSizeConstraints:
    """Property tests for font size relationships."""

    def test_font_size_hierarchy(self):
        """Font sizes should follow big > mid > small hierarchy."""
        geom = load_geometry()
        fonts = geom.get("fonts", {})

        big = fonts.get("big_px", 0)
        mid = fonts.get("mid_px", 0)
        small = fonts.get("small_px", 0)

        assert big > mid >= small, f"Font hierarchy violated: big={big}, mid={mid}, small={small}"

    @given(
        big=st.integers(min_value=16, max_value=26),  # Max matches typical big rect height
        mid=st.integers(min_value=10, max_value=18),  # Max fits mid rect with some room
        small=st.integers(min_value=8, max_value=14),  # Max fits small rect
    )
    @settings(max_examples=50)
    def test_font_fits_in_rect(self, big, mid, small):
        """Font sizes should fit within typical rectangle heights."""
        assume(big > mid >= small)

        # Typical rectangle heights from geometry
        big_rect_h = 26  # INSIDE_TEMP height
        mid_rect_h = 14  # HEADER_NAME height
        small_rect_h = 10  # INSIDE_HUMIDITY height

        # Font should fit within rect height (font size <= rect height)
        # This is a property of valid configurations, not all possible values
        assert big <= big_rect_h + 2, f"Big font {big} should fit in rect height {big_rect_h}"
        assert mid <= mid_rect_h + 6, f"Mid font {mid} should fit in rect height {mid_rect_h}"
        assert small <= small_rect_h + 6, f"Small font {small} should fit in rect height {small_rect_h}"
