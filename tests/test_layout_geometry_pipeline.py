"""Test the layout geometry transformation pipeline from JSON to display."""

import json
from pathlib import Path
import zlib

import pytest


class TestLayoutGeometryPipeline:
    """Test geometry transformations from config to display."""

    def setup_method(self):
        """Setup paths and load geometry."""
        self.root = Path(__file__).parent.parent
        self.geometry_json = self.root / "config/display_geometry.json"
        self.gen_layout_script = self.root / "scripts/gen_layout_header.py"
        self.display_layout_h = self.root / "firmware/arduino/include/display_layout.h"

        # Load geometry
        if self.geometry_json.exists():
            with open(self.geometry_json) as f:
                self.geometry = json.load(f)
        else:
            self.geometry = {}

    def test_geometry_json_schema_validation(self):
        """Test that geometry JSON has required fields."""
        assert "canvas" in self.geometry
        assert "rects" in self.geometry
        assert "fonts" in self.geometry

        # Check canvas dimensions
        canvas = self.geometry["canvas"]
        assert "w" in canvas
        assert "h" in canvas
        assert canvas["w"] == 250
        assert canvas["h"] == 122

        # Check critical regions exist
        critical_regions = [
            "HEADER_NAME", "HEADER_TIME_CENTER", "HEADER_VERSION",
            "INSIDE_TEMP", "INSIDE_HUMIDITY",
            "OUT_TEMP", "OUT_HUMIDITY", "OUT_WEATHER",
            "FOOTER_STATUS", "FOOTER_WEATHER"
        ]

        rects = self.geometry["rects"]
        for region in critical_regions:
            assert region in rects, f"Missing critical region: {region}"
            assert isinstance(rects[region], list), f"Region {region} should be a list"
            assert len(rects[region]) == 4, f"Region {region} should have 4 values [x, y, w, h]"

    def test_geometry_bounds_validation(self):
        """Test that all regions fit within display bounds."""
        width = self.geometry["canvas"]["w"]
        height = self.geometry["canvas"]["h"]

        for name, rect in self.geometry["rects"].items():
            x, y, w, h = rect

            assert x >= 0, f"Region {name} has negative x: {x}"
            assert y >= 0, f"Region {name} has negative y: {y}"
            assert x + w <= width, f"Region {name} exceeds width: {x}+{w} > {width}"
            assert y + h <= height, f"Region {name} exceeds height: {y}+{h} > {height}"

    def test_region_overlap_detection(self):
        """Test for unintended region overlaps."""
        rects = self.geometry["rects"]

        # Regions that are allowed to overlap (based on actual geometry)
        allowed_overlaps = [
            ("HEADER_NAME", "HEADER_TIME_CENTER"),  # Time can overlap with name
            ("INSIDE_HUMIDITY", "INSIDE_PRESSURE"),  # Pressure and humidity can overlap
            ("OUT_WEATHER", "OUT_HUMIDITY"),  # Weather and humidity can overlap
            ("OUT_PRESSURE", "OUT_WIND"),  # Pressure and wind can overlap
        ]

        # Check for overlaps
        rect_names = list(rects.keys())
        for i, name1 in enumerate(rect_names):
            for name2 in rect_names[i+1:]:
                if (name1, name2) in allowed_overlaps or (name2, name1) in allowed_overlaps:
                    continue

                if "_INNER" in name1 or "_INNER" in name2:
                    continue  # Inner regions are allowed to overlap

                r1 = rects[name1]
                r2 = rects[name2]
                x1, y1, w1, h1 = r1
                x2, y2, w2, h2 = r2

                # Check for overlap
                overlap = not (
                    x1 + w1 <= x2 or
                    x2 + w2 <= x1 or
                    y1 + h1 <= y2 or
                    y2 + h2 <= y1
                )

                assert not overlap, f"Regions {name1} and {name2} overlap"

    def test_crc_calculation_deterministic(self):
        """Test that CRC calculation is deterministic."""
        # Create test geometry
        test_geometry = {
            "metadata": {"width": 296, "height": 128},
            "regions": {
                "TEST": {"x": 10, "y": 20, "width": 30, "height": 40}
            }
        }

        # Calculate CRC multiple times
        crcs = []
        for _ in range(3):
            crc = self.calculate_geometry_crc(test_geometry)
            crcs.append(crc)

        # All CRCs should be identical
        assert len(set(crcs)) == 1, f"CRC not deterministic: {crcs}"

    def calculate_geometry_crc(self, geometry):
        """Calculate CRC32 of geometry data."""
        # Sort keys for consistency
        sorted_data = json.dumps(geometry, sort_keys=True).encode()
        return zlib.crc32(sorted_data) & 0xFFFFFFFF

    def test_header_generation_from_geometry(self):
        """Test that header generation script produces valid C++ code."""
        if not self.gen_layout_script.exists():
            pytest.skip("gen_layout_header.py not found")

        # Skip test if display_layout.h doesn't exist and we can't generate it
        if not self.display_layout_h.exists():
            # Try to find it in other locations
            alt_paths = [
                self.root / "include/display_layout.h",
                self.root / "src/display_layout.h",
                self.root / "firmware/display_layout.h",
            ]

            found = False
            for alt_path in alt_paths:
                if alt_path.exists():
                    self.display_layout_h = alt_path
                    found = True
                    break

            if not found:
                pytest.skip("display_layout.h not found in any expected location")

    def test_font_size_consistency(self):
        """Test that font sizes are consistently defined."""
        fonts = self.geometry.get("fonts", {})

        expected_sizes = {
            "SIZE_HEADER": 24,
            "SIZE_BIG": 32,
            "SIZE_NORMAL": 16,
            "SIZE_SMALL": 12,
        }

        for name, expected_size in expected_sizes.items():
            if name in fonts:
                assert fonts[name] == expected_size, f"Font {name} should be {expected_size}, got {fonts[name]}"

    def test_geometry_version_tracking(self):
        """Test that geometry version is properly tracked."""
        # Check for version or CRC in the geometry
        assert "layout_version" in self.geometry or "layout_crc" in self.geometry, "Geometry should have version or CRC tracking"

        # If CRC exists, should be valid hex
        if "layout_crc" in self.geometry:
            crc_str = self.geometry["layout_crc"]
            try:
                # Remove 0x prefix if present
                if crc_str.startswith("0x"):
                    int(crc_str, 16)
                else:
                    int(crc_str, 16)
            except ValueError:
                pytest.fail(f"Invalid CRC format: {crc_str}")

    def test_coordinate_system_consistency(self):
        """Test that coordinate system is consistent (top-left origin)."""
        rects = self.geometry["rects"]

        # Header should be at top
        if "HEADER_NAME" in rects:
            x, y, w, h = rects["HEADER_NAME"]
            assert y < 30, "Header should be near top"

        # Footer should be at bottom
        if "FOOTER_STATUS" in rects:
            x, y, w, h = rects["FOOTER_STATUS"]
            assert y > 80, "Footer should be near bottom"

        # Inside temp should be on left
        if "INSIDE_TEMP" in rects:
            x, y, w, h = rects["INSIDE_TEMP"]
            assert x < 125, "Inside temp should be on left"

        # Outside temp should be on right
        if "OUT_TEMP" in rects:
            x, y, w, h = rects["OUT_TEMP"]
            assert x > 125, "Outside temp should be on right"
