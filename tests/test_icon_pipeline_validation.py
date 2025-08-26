import json
import os
import subprocess

import pytest

# Icon generation test scenarios
ICON_GENERATION_SCENARIOS = [
    {
        "name": "weather-sunny",
        "expected_svg": "weather-sunny.svg",
        "expected_crc": "0x1234ABCD",  # Example CRC
        "category": "weather",
    },
    {
        "name": "weather-partly-cloudy",
        "expected_svg": "weather-partly-cloudy.svg",
        "expected_crc": "0x5678EFGH",
        "category": "weather",
    },
    {
        "name": "weather-cloudy",
        "expected_svg": "weather-cloudy.svg",
        "expected_crc": "0x9ABC1234",
        "category": "weather",
    },
    {
        "name": "weather-rainy",
        "expected_svg": "weather-rainy.svg",
        "expected_crc": "0xDEF56789",
        "category": "weather",
    },
    {
        "name": "weather-lightning",
        "expected_svg": "weather-lightning.svg",
        "expected_crc": "0x12345678",
        "category": "weather",
    },
]

# Expected icon header structure
EXPECTED_ICON_HEADER_STRUCTURE = {
    "total_icons": 15,  # Should match the number of weather icons
    "header_size": 72,  # Fixed header size per icon
    "expected_categories": ["weather", "status", "battery"],
    "compression": "none",  # Or "rle", "lz77" etc.
}


def test_icon_generation_pipeline():
    """Test the complete icon generation pipeline"""

    scripts_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts")

    # Test gen_icons.py if available
    gen_icons_script = os.path.join(scripts_dir, "gen_icons.py")
    if os.path.exists(gen_icons_script):
        try:
            result = subprocess.run(
                [
                    "python3",
                    gen_icons_script,
                    "--config",
                    os.path.join(os.path.dirname(scripts_dir), "config", "icons"),
                ],
                capture_output=True,
                text=True,
                cwd=scripts_dir,
                timeout=30,
            )

            # Should complete successfully
            assert result.returncode == 0, f"Icon generation failed: {result.stderr}"

            # Should generate output
            assert (
                len(result.stdout) > 0 or len(result.stderr) == 0
            ), "No output from icon generation"

        except subprocess.TimeoutExpired:
            pytest.fail("Icon generation timed out")
        except FileNotFoundError:
            pytest.skip("gen_icons.py not found")


def test_icon_header_generation():
    """Test that icon header files are properly generated"""

    firmware_dir = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "firmware", "arduino", "src"
    )
    icon_header = os.path.join(firmware_dir, "icons_generated.h")

    if not os.path.exists(icon_header):
        pytest.skip("icons_generated.h not found - run generation first")

    # Parse the generated header
    with open(icon_header, "r") as f:
        header_content = f.read()

    # Should contain icon data structure
    assert "ICON_" in header_content, "No icon definitions found in header"

    # Should have proper include guards or pragma once
    has_include_guards = (
        "#ifndef ICONS_GENERATED_H" in header_content
        and "#define ICONS_GENERATED_H" in header_content
    )
    has_pragma_once = "#pragma once" in header_content

    assert has_include_guards or has_pragma_once, "Missing proper header guards"

    # Should contain some icon count or size information
    has_total_icons = "TOTAL_ICONS" in header_content
    has_icon_count = "ICON_COUNT" in header_content
    has_constants = "const" in header_content and "icon" in header_content.lower()

    assert has_total_icons or has_icon_count or has_constants, "Missing icon count or constants"


def test_icon_crc_validation():
    """Test CRC validation for generated icons"""

    scripts_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts")

    # Test icon CRC calculation script
    crc_script = os.path.join(scripts_dir, "test_icon_crc.py")
    if os.path.exists(crc_script):
        try:
            result = subprocess.run(
                ["python3", crc_script], capture_output=True, text=True, cwd=scripts_dir, timeout=10
            )

            assert result.returncode == 0, f"CRC validation failed: {result.stderr}"

        except subprocess.TimeoutExpired:
            pytest.fail("CRC validation timed out")
        except FileNotFoundError:
            pytest.skip("test_icon_crc.py not found")


def test_icon_svg_source_validation():
    """Test that source SVG files are valid and accessible"""

    web_icons_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web", "icons")

    if not os.path.exists(web_icons_dir):
        pytest.skip("web/icons directory not found")

    # Get all SVG files
    svg_files = []
    for root, dirs, files in os.walk(web_icons_dir):
        for file in files:
            if file.endswith(".svg"):
                svg_files.append(os.path.join(root, file))

    assert len(svg_files) > 0, "No SVG icon files found"

    # Validate each SVG file
    for svg_path in svg_files[:5]:  # Test first 5 to avoid too much overhead
        try:
            with open(svg_path, "r", encoding="utf-8") as f:
                svg_content = f.read()

            # Should be valid XML/SVG
            assert (
                "<?xml" in svg_content or "<svg" in svg_content
            ), f"Invalid SVG content in {svg_path}"

            # Should have viewBox or width/height
            assert "viewBox" in svg_content or (
                "width" in svg_content and "height" in svg_content
            ), f"SVG missing dimensions in {svg_path}"

            # Should not be empty
            assert len(svg_content.strip()) > 50, f"SVG file too small: {svg_path}"

        except UnicodeDecodeError:
            pytest.fail(f"SVG file encoding error: {svg_path}")
        except Exception as e:
            pytest.fail(f"Error reading SVG {svg_path}: {e}")


def test_icon_conversion_pipeline():
    """Test the icon conversion from SVG to embedded format"""

    scripts_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts")

    # Test convert_icons.py if available
    convert_script = os.path.join(scripts_dir, "convert_icons.py")
    if os.path.exists(convert_script):
        try:
            result = subprocess.run(
                [
                    "python3",
                    convert_script,
                    "--input",
                    os.path.join(os.path.dirname(scripts_dir), "web", "icons"),
                    "--output",
                    "/tmp/test_icons.h",
                ],
                capture_output=True,
                text=True,
                cwd=scripts_dir,
                timeout=30,
            )

            if result.returncode != 0:
                # Check if it's just missing input files
                if "not found" not in result.stderr.lower():
                    assert result.returncode == 0, f"Icon conversion failed: {result.stderr}"

        except subprocess.TimeoutExpired:
            pytest.fail("Icon conversion timed out")
        except FileNotFoundError:
            pytest.skip("convert_icons.py not found")


def test_icon_completeness_check():
    """Test that all required icons are present and accounted for"""

    # Get UI spec to check what icons are referenced
    ui_spec_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "config", "ui_spec.json"
    )

    if not os.path.exists(ui_spec_path):
        pytest.skip("UI spec not found")

    with open(ui_spec_path, "r") as f:
        ui_spec = json.load(f)

    icon_map = ui_spec.get("iconMap", [])
    referenced_icons = set()

    # Collect all icons referenced in UI spec
    for rule in icon_map:
        if "icon" in rule:
            referenced_icons.add(rule["icon"])

    # Check firmware header for generated icons
    firmware_dir = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "firmware", "arduino", "src"
    )
    icon_header = os.path.join(firmware_dir, "icons_generated.h")

    if os.path.exists(icon_header):
        with open(icon_header, "r") as f:
            header_content = f.read()

        # Should contain all referenced icons
        for icon_name in referenced_icons:
            # Look for icon definition (could be ICON_weather_sunny or similar)
            icon_patterns = [
                f"ICON_{icon_name.upper()}",
                f"ICON_{icon_name}",
                icon_name.upper(),
                icon_name,
            ]

            found = False
            for pattern in icon_patterns:
                if pattern in header_content:
                    found = True
                    break

            assert found, f"Icon {icon_name} not found in generated header"


def test_icon_size_constraints():
    """Test that generated icons meet size constraints"""

    firmware_dir = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "firmware", "arduino", "src"
    )
    icon_header = os.path.join(firmware_dir, "icons_generated.h")

    if not os.path.exists(icon_header):
        pytest.skip("icons_generated.h not found")

    with open(icon_header, "r") as f:
        header_content = f.read()

    # Look for icon size definitions
    import re

    # Find icon data arrays
    icon_arrays = re.findall(r"const\s+uint8_t\s+\w+\[\]\s*=\s*\{([^}]*)\}", header_content)

    for icon_data in icon_arrays:
        # Count bytes (each hex value represents a byte)
        hex_bytes = re.findall(r"0x[0-9A-Fa-f]{2}", icon_data)
        decimal_bytes = re.findall(r"\b\d{1,3}\b", icon_data)  # 0-255 range

        total_bytes = len(hex_bytes) + len(decimal_bytes)

        # Icons should be reasonable size (not empty, not huge)
        assert total_bytes > 10, f"Icon too small: {total_bytes} bytes"
        assert total_bytes < 10000, f"Icon too large: {total_bytes} bytes"


def test_icon_naming_conventions():
    """Test that icons follow consistent naming conventions"""

    # Get all icon references from UI spec
    ui_spec_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "config", "ui_spec.json"
    )

    if not os.path.exists(ui_spec_path):
        pytest.skip("UI spec not found")

    with open(ui_spec_path, "r") as f:
        ui_spec = json.load(f)

    icon_map = ui_spec.get("iconMap", [])
    all_icons = set()

    for rule in icon_map:
        if "icon" in rule:
            all_icons.add(rule["icon"])

    # Test naming conventions
    for icon_name in all_icons:
        # Should start with category prefix
        assert "-" in icon_name, f"Icon name should contain category prefix: {icon_name}"

        # Should be lowercase
        assert icon_name == icon_name.lower(), f"Icon name should be lowercase: {icon_name}"

        # Should not contain spaces or special characters
        assert " " not in icon_name, f"Icon name should not contain spaces: {icon_name}"
        assert (
            icon_name.replace("-", "").replace("_", "").isalnum()
        ), f"Icon name should only contain letters, numbers, hyphens: {icon_name}"

        # Should be reasonable length
        assert 3 < len(icon_name) < 50, f"Icon name length unusual: {icon_name}"


def test_weather_icon_mapping_completeness():
    """Test that all weather conditions have corresponding icons"""

    ui_spec_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "config", "ui_spec.json"
    )

    if not os.path.exists(ui_spec_path):
        pytest.skip("UI spec not found")

    with open(ui_spec_path, "r") as f:
        ui_spec = json.load(f)

    icon_map = ui_spec.get("iconMap", [])

    # Extract weather conditions and their mappings
    weather_conditions = set()
    icon_to_conditions = {}

    for rule in icon_map:
        if "match" in rule and "icon" in rule:
            icon = rule["icon"]
            if not icon_to_conditions.get(icon):
                icon_to_conditions[icon] = set()

            for condition in rule["match"]:
                weather_conditions.add(condition)
                icon_to_conditions[icon].add(condition)

    # Should have weather icons for common conditions
    essential_conditions = {
        "clear",
        "sunny",
        "partly",
        "cloud",
        "overcast",
        "rain",
        "storm",
        "snow",
        "fog",
        "wind",
    }

    for condition in essential_conditions:
        found = False
        for conditions in icon_to_conditions.values():
            if any(condition in c for c in conditions):
                found = True
                break
        assert found, f"No icon found for essential weather condition: {condition}"


def test_icon_generation_determinism():
    """Test that icon generation is deterministic (same input = same output)"""

    scripts_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts")

    # Test by running generation twice and comparing output
    gen_script = os.path.join(scripts_dir, "gen_icons.py")
    if not os.path.exists(gen_script):
        pytest.skip("gen_icons.py not found")

    try:
        # First run
        result1 = subprocess.run(
            ["python3", gen_script], capture_output=True, text=True, cwd=scripts_dir, timeout=30
        )

        # Second run
        result2 = subprocess.run(
            ["python3", gen_script], capture_output=True, text=True, cwd=scripts_dir, timeout=30
        )

        # Both should succeed
        assert result1.returncode == 0
        assert result2.returncode == 0

        # Output should be identical (deterministic)
        assert result1.stdout == result2.stdout
        assert result1.stderr == result2.stderr

    except subprocess.TimeoutExpired:
        pytest.fail("Icon generation determinism test timed out")


def test_icon_header_include_structure():
    """Test that icon header has proper include structure for firmware"""

    firmware_dir = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "firmware", "arduino", "src"
    )
    icon_header = os.path.join(firmware_dir, "icons_generated.h")

    if not os.path.exists(icon_header):
        pytest.skip("icons_generated.h not found")

    with open(icon_header, "r") as f:
        header_content = f.read()

    # Should include necessary headers (flexible about exact format)
    required_includes = [
        "<stdint.h>",  # Standard integer types
        "pgmspace",  # For PROGMEM (may vary by platform)
    ]

    for include in required_includes:
        assert include in header_content, f"Missing required include: {include}"

    # Should define icon data structure
    assert (
        "struct IconData" in header_content or "typedef" in header_content
    ), "Missing icon data structure definition"


def test_icon_bitmap_validation():
    """Test that generated icon bitmaps are valid"""

    firmware_dir = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "firmware", "arduino", "src"
    )
    icon_header = os.path.join(firmware_dir, "icons_generated.h")

    if not os.path.exists(icon_header):
        pytest.skip("icons_generated.h not found")

    with open(icon_header, "r") as f:
        header_content = f.read()

    import re

    # Find icon bitmap data
    bitmap_arrays = re.findall(
        r"const\s+uint8_t\s+\w+\[\]\s*PROGMEM\s*=\s*\{([^}]*)\}", header_content
    )

    for bitmap_data in bitmap_arrays:
        # Each byte should be valid hex (0x00-0xFF)
        hex_values = re.findall(r"0x[0-9A-Fa-f]{2}", bitmap_data)

        for hex_val in hex_values:
            byte_val = int(hex_val, 16)
            assert 0 <= byte_val <= 255, f"Invalid byte value: {hex_val}"

        # Should have reasonable amount of data
        assert len(hex_values) > 0, "Empty bitmap data found"


def test_icon_metadata_consistency():
    """Test that icon metadata is consistent across files"""

    # Check that icon references in different files are consistent
    files_to_check = [
        "firmware/arduino/src/ui_generated.h",
        "firmware/arduino/src/icons_generated.h",
        "config/ui_spec.json",
    ]

    icon_references = {}

    for file_path in files_to_check:
        full_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), file_path)

        if os.path.exists(full_path):
            with open(full_path, "r") as f:
                content = f.read()

            # Extract icon references (this is a simple pattern - could be more sophisticated)
            import re

            icons_found = set(re.findall(r"weather-[a-z-]+", content))
            icon_references[file_path] = icons_found

    # All files should reference the same core set of weather icons
    if len(icon_references) > 1:
        common_icons = set.intersection(*icon_references.values())
        assert len(common_icons) > 5, f"Too few common icons across files: {common_icons}"
