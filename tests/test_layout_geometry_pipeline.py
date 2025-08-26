"""Test the layout geometry transformation pipeline from JSON to display."""

import pytest
import json
import subprocess
import tempfile
from pathlib import Path
import zlib

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
            "OUT_TEMP", "OUT_HUMIDITY", "OUT_CONDITION",
            "BATTERY", "BATTERY_PERCENT"
        ]
        
        rects = self.geometry["rects"]
        for region in critical_regions:
            assert region in rects, f"Missing critical region: {region}"
            assert isinstance(rects[region], list), f"Region {region} should be a list"
            assert len(rects[region]) == 4, f"Region {region} should have 4 values [x, y, w, h]"
    
    def test_geometry_bounds_validation(self):
        """Test that all regions fit within display bounds."""
        width = self.geometry["metadata"]["width"]
        height = self.geometry["metadata"]["height"]
        
        for name, region in self.geometry["regions"].items():
            x, y = region["x"], region["y"]
            w, h = region["width"], region["height"]
            
            assert x >= 0, f"Region {name} has negative x: {x}"
            assert y >= 0, f"Region {name} has negative y: {y}"
            assert x + w <= width, f"Region {name} exceeds width: {x}+{w} > {width}"
            assert y + h <= height, f"Region {name} exceeds height: {y}+{h} > {height}"
    
    def test_region_overlap_detection(self):
        """Test for unintended region overlaps."""
        regions = self.geometry["regions"]
        
        # Regions that are allowed to overlap
        allowed_overlaps = [
            ("BATTERY", "BATTERY_ICON"),  # Icon inside battery region
            ("INSIDE_TEMP", "INSIDE_TEMP_INNER"),
            ("OUT_TEMP", "OUT_TEMP_INNER"),
        ]
        
        # Check for overlaps
        region_names = list(regions.keys())
        for i, name1 in enumerate(region_names):
            for name2 in region_names[i+1:]:
                if (name1, name2) in allowed_overlaps or (name2, name1) in allowed_overlaps:
                    continue
                
                if "_INNER" in name1 or "_INNER" in name2:
                    continue  # Inner regions are allowed to overlap
                
                r1 = regions[name1]
                r2 = regions[name2]
                
                # Check for overlap
                overlap = not (
                    r1["x"] + r1["width"] <= r2["x"] or
                    r2["x"] + r2["width"] <= r1["x"] or
                    r1["y"] + r1["height"] <= r2["y"] or
                    r2["y"] + r2["height"] <= r1["y"]
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
        
        # Run generator in test mode
        with tempfile.NamedTemporaryFile(suffix=".h", mode='w', delete=False) as f:
            temp_header = Path(f.name)
        
        try:
            # Generate header
            result = subprocess.run(
                ["python3", str(self.gen_layout_script), "--output", str(temp_header)],
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                # Try without --output flag
                result = subprocess.run(
                    ["python3", str(self.gen_layout_script)],
                    capture_output=True,
                    text=True
                )
            
            # Check header was created
            assert temp_header.exists() or self.display_layout_h.exists()
            
            # Validate C++ syntax
            header_content = temp_header.read_text() if temp_header.exists() else self.display_layout_h.read_text()
            
            assert "#ifndef" in header_content
            assert "#define" in header_content
            assert "#endif" in header_content
            
            # Check for key defines
            for region_name in self.geometry["regions"]:
                assert f"#define {region_name}_X" in header_content
                assert f"#define {region_name}_Y" in header_content
                assert f"#define {region_name}_WIDTH" in header_content
                assert f"#define {region_name}_HEIGHT" in header_content
        
        finally:
            if temp_header.exists():
                temp_header.unlink()
    
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
        metadata = self.geometry.get("metadata", {})
        
        # Should have version field
        assert "version" in metadata or "crc" in metadata, "Geometry should have version or CRC tracking"
        
        # If CRC exists, should be valid hex
        if "crc" in metadata:
            crc_str = metadata["crc"]
            try:
                int(crc_str, 16)
            except ValueError:
                pytest.fail(f"Invalid CRC format: {crc_str}")
    
    def test_coordinate_system_consistency(self):
        """Test that coordinate system is consistent (top-left origin)."""
        regions = self.geometry["regions"]
        
        # Header should be at top
        if "HEADER_NAME" in regions:
            assert regions["HEADER_NAME"]["y"] < 30, "Header should be near top"
        
        # Battery should be at bottom
        if "BATTERY" in regions:
            assert regions["BATTERY"]["y"] > 90, "Battery should be near bottom"
        
        # Inside temp should be on left
        if "INSIDE_TEMP" in regions:
            assert regions["INSIDE_TEMP"]["x"] < 150, "Inside temp should be on left"
        
        # Outside temp should be on right  
        if "OUT_TEMP" in regions:
            assert regions["OUT_TEMP"]["x"] > 150, "Outside temp should be on right"