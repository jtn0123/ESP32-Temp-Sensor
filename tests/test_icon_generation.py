import os
import re
import subprocess
import zlib
from typing import Dict, List, Tuple


ROOT = os.path.dirname(os.path.dirname(__file__))
HEADER = os.path.join(ROOT, "firmware", "arduino", "src", "icons_generated.h")
SRC_DIR = os.path.join(ROOT, "web", "icons", "mdi")
GOLDEN = os.path.join(ROOT, "tests", "icon_crc_golden.txt")


def _extract_icons_and_arrays(text: str) -> Tuple[List[str], Dict[str, bytes]]:
    # Parse enum names to ensure presence
    enum_names: List[str] = []
    arrays: Dict[str, bytes] = {}
    enum_section = False
    for ln in text.splitlines():
        if ln.strip().startswith("enum IconId"):
            enum_section = True
            continue
        if enum_section:
            if ln.strip().startswith("};"):
                enum_section = False
            else:
                m = re.search(r"ICON_([A-Z0-9_]+)", ln)
                if m:
                    enum_names.append(m.group(1))
    # Parse PROGMEM arrays
    pat = re.compile(r"static const uint8_t\s+(\w+)\[\]\s+PROGMEM\s*=\s*\{(.*?)\};", re.S)
    for m in pat.finditer(text):
        name = m.group(1)
        body = m.group(2)
        # Collect hex bytes
        hex_bytes = re.findall(r"0x([0-9A-Fa-f]{2})", body)
        arrays[name] = bytes(int(h, 16) for h in hex_bytes)
    return enum_names, arrays


def test_icon_header_contains_required_icons_and_lengths():
    # Ensure header is up to date with the current SVGs
    r = subprocess.run(
        ["python3", os.path.join(ROOT, "scripts", "convert_icons.py")],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    with open(HEADER, "r") as f:
        content = f.read()
    enum_names, arrays = _extract_icons_and_arrays(content)
    # Basic presence checks for weather and moon icon enums
    required = [
        "WEATHER_SUNNY",
        "WEATHER_PARTLY_CLOUDY",
        "WEATHER_CLOUDY",
        "WEATHER_FOG",
        "WEATHER_SNOWY",
        "WEATHER_POURING",
        "WEATHER_LIGHTNING",
        "WEATHER_NIGHT",
        "MOON_NEW",
        "MOON_WAXING_CRESCENT",
        "MOON_FIRST_QUARTER",
        "MOON_WAXING_GIBBOUS",
        "MOON_FULL",
        "MOON_WANING_GIBBOUS",
        "MOON_LAST_QUARTER",
        "MOON_WANING_CRESCENT",
    ]
    for r in required:
        assert r in enum_names, f"Missing enum {r} in icons_generated.h"

    # Each 24x24 1-bit icon should be 24 * ceil(24/8) = 24 * 3 = 72 bytes
    EXPECT_BYTES = 72
    bad: List[str] = []
    for arr_name, data in arrays.items():
        if len(data) != EXPECT_BYTES:
            bad.append(f"{arr_name}:{len(data)}")
    assert not bad, f"Unexpected byte lengths for arrays: {', '.join(bad)}"


def test_icon_svgs_exist_for_declared_names():
    # If a declared icon is missing from the src directory, fail fast
    with open(HEADER, "r") as f:
        content = f.read()
    # From enum names, derive expected SVG filenames
    enum_names, _ = _extract_icons_and_arrays(content)
    # Map back to typical filenames (lowercase, hyphenated; skip MOON_ prefix translation)
    expect_files: List[str] = []
    for e in enum_names:
        n = e.lower()
        if n.startswith("moon_"):
            n = n.replace("_", "-")
        elif n.startswith("weather_"):
            n = n.replace("_", "-")
        else:
            n = n.replace("_", "-")
        expect_files.append(f"{n}.svg")
    missing = [
        fn for fn in expect_files if not os.path.exists(os.path.join(SRC_DIR, fn))
    ]
    # Only warn on extras that are not strictly required; but do fail if core
    # weather icons are missing
    core = {
        "weather-sunny.svg",
        "weather-partly-cloudy.svg",
        "weather-cloudy.svg",
        "weather-fog.svg",
        "weather-pouring.svg",
        "weather-snowy.svg",
        "weather-lightning.svg",
    }
    missing_core = [m for m in missing if m in core]
    assert not missing_core, f"Missing core icon SVGs: {missing_core}"


def test_icon_crc_matches_golden():
    # Compute CRC32 for each icon byte array and compare to a committed golden list
    with open(HEADER, "r") as f:
        content = f.read()
    _names, arrays = _extract_icons_and_arrays(content)
    crc_map = {k: zlib.crc32(v) & 0xFFFFFFFF for k, v in arrays.items()}
    lines = [f"{k} {crc_map[k]:08X} {len(arrays[k])}\n" for k in sorted(arrays.keys())]
    if not os.path.exists(GOLDEN):
        if os.environ.get("CI"):
            raise AssertionError("Missing icon CRC golden; commit tests/icon_crc_golden.txt")
        with open(GOLDEN, "w") as f:
            f.writelines(lines)
        assert True
        return
    with open(GOLDEN, "r") as f:
        golden_lines = [ln.strip() for ln in f if ln.strip()]
    actual_lines = [ln.strip() for ln in lines]
    assert (
        actual_lines == golden_lines
    ), "Icon CRC/lengths differ from golden; re-generate if intentional"
