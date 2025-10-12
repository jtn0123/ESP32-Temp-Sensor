#!/usr/bin/env python3
"""
Test to ensure display_geometry.json stays in sync between config/ and web/sim/

This prevents the common issue where the simulator and firmware use different layouts.
"""

import json
from pathlib import Path

import pytest

# Path setup
ROOT = Path(__file__).resolve().parents[1]
CONFIG_GEOMETRY = ROOT / "config" / "display_geometry.json"
WEB_SIM_GEOMETRY = ROOT / "web" / "sim" / "geometry.json"


def load_geometry(path: Path) -> dict:
    """Load and parse geometry JSON file"""
    assert path.exists(), f"Geometry file not found: {path}"
    with open(path) as f:
        return json.load(f)


def normalize_geometry(data: dict) -> dict:
    """
    Normalize geometry data for comparison.

    Removes fields that may differ but don't affect functional equivalence.
    """
    normalized = {
        "canvas": data.get("canvas", {}),
        "fonts": data.get("fonts", {}),
        "rects": data.get("rects", {}),
    }

    # Also include layout_version and layout_crc if present (they should match)
    if "layout_version" in data:
        normalized["layout_version"] = data["layout_version"]
    if "layout_crc" in data:
        normalized["layout_crc"] = data["layout_crc"]

    return normalized


def test_geometry_files_exist():
    """Verify both geometry files exist"""
    assert CONFIG_GEOMETRY.exists(), f"Missing config geometry: {CONFIG_GEOMETRY}"
    assert WEB_SIM_GEOMETRY.exists(), f"Missing web sim geometry: {WEB_SIM_GEOMETRY}"


def test_geometry_files_in_sync():
    """
    Verify that config/display_geometry.json and web/sim/geometry.json are in sync.

    These files must be identical (or at least functionally equivalent) to ensure
    the web simulator matches the firmware behavior.
    """
    config_data = load_geometry(CONFIG_GEOMETRY)
    web_sim_data = load_geometry(WEB_SIM_GEOMETRY)

    # Normalize for comparison
    config_norm = normalize_geometry(config_data)
    web_sim_norm = normalize_geometry(web_sim_data)

    # Check canvas dimensions
    assert config_norm["canvas"] == web_sim_norm["canvas"], (
        f"Canvas dimensions differ:\n"
        f"  Config: {config_norm['canvas']}\n"
        f"  Web Sim: {web_sim_norm['canvas']}"
    )

    # Check fonts
    assert config_norm["fonts"] == web_sim_norm["fonts"], (
        f"Font definitions differ:\n"
        f"  Config: {config_norm['fonts']}\n"
        f"  Web Sim: {web_sim_norm['fonts']}"
    )

    # Check rectangles (the most critical part)
    assert config_norm["rects"] == web_sim_norm["rects"], (
        f"Rectangle definitions differ:\n"
        f"  Config has {len(config_norm['rects'])} regions\n"
        f"  Web Sim has {len(web_sim_norm['rects'])} regions\n"
        f"  Differences: {set(config_norm['rects'].keys()) ^ set(web_sim_norm['rects'].keys())}"
    )

    # Check layout version/CRC if present
    if "layout_version" in config_norm and "layout_version" in web_sim_norm:
        assert config_norm["layout_version"] == web_sim_norm["layout_version"], (
            f"Layout versions differ: config={config_norm['layout_version']}, "
            f"web_sim={web_sim_norm['layout_version']}"
        )

    if "layout_crc" in config_norm and "layout_crc" in web_sim_norm:
        assert config_norm["layout_crc"] == web_sim_norm["layout_crc"], (
            f"Layout CRCs differ: config={config_norm['layout_crc']}, "
            f"web_sim={web_sim_norm['layout_crc']}"
        )


def test_all_regions_within_canvas():
    """Verify all regions fit within the canvas bounds"""
    config_data = load_geometry(CONFIG_GEOMETRY)

    canvas_w = config_data["canvas"]["w"]
    canvas_h = config_data["canvas"]["h"]

    for name, rect in config_data["rects"].items():
        x, y, w, h = rect

        # Check bounds
        assert x >= 0, f"{name}: x={x} is negative"
        assert y >= 0, f"{name}: y={y} is negative"
        assert x + w <= canvas_w, (
            f"{name}: right edge ({x}+{w}={x+w}) exceeds canvas width ({canvas_w})"
        )
        assert y + h <= canvas_h, (
            f"{name}: bottom edge ({y}+{h}={y+h}) exceeds canvas height ({canvas_h})"
        )


def test_regions_aligned_to_4px_grid():
    """
    Verify regions are aligned to 4px grid (design guideline).

    This is a soft requirement - warn if violated but don't fail.
    """
    config_data = load_geometry(CONFIG_GEOMETRY)

    misaligned = []
    for name, rect in config_data["rects"].items():
        x, y, w, h = rect

        if x % 4 != 0 or y % 4 != 0:
            misaligned.append(f"{name}: position ({x}, {y}) not aligned to 4px grid")

    if misaligned:
        # Use pytest.warn or just print (don't fail the test)
        print(f"\nWarning: {len(misaligned)} regions not aligned to 4px grid:")
        for msg in misaligned:
            print(f"  - {msg}")


def test_layout_crc_consistency():
    """Verify layout_crc matches the computed CRC"""
    import zlib

    config_data = load_geometry(CONFIG_GEOMETRY)

    # Compute CRC the same way gen_layout_header.py does
    crc_obj = json.dumps(
        {"canvas": config_data["canvas"], "rects": config_data["rects"]},
        sort_keys=True
    ).encode("utf-8")
    computed_crc = zlib.crc32(crc_obj) & 0xFFFFFFFF

    if "layout_crc" in config_data:
        # Remove '0x' prefix if present and convert to int
        stored_crc_str = config_data["layout_crc"]
        if isinstance(stored_crc_str, str):
            stored_crc = int(stored_crc_str, 16) if stored_crc_str.startswith("0x") else int(stored_crc_str)
        else:
            stored_crc = stored_crc_str

        assert computed_crc == stored_crc, (
            f"Layout CRC mismatch:\n"
            f"  Stored:   0x{stored_crc:08X}\n"
            f"  Computed: 0x{computed_crc:08X}\n"
            f"Run scripts/gen_layout_header.py to update"
        )


if __name__ == "__main__":
    # Run tests when executed directly
    pytest.main([__file__, "-v"])
