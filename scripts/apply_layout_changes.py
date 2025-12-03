#!/usr/bin/env python3
"""
Apply Layout Changes - Workflow tool for updating display geometry

This script takes a modified geometry JSON file (exported from the web simulator),
validates it, and applies the changes to both the canonical config and web simulator.

Workflow:
1. Edit layout visually in web simulator (http://localhost:8000)
2. Export modified JSON from Layout Editor panel
3. Run this script: python3 scripts/apply_layout_changes.py path/to/modified.json
4. Script validates, updates config files, regenerates headers
5. Reload simulator or rebuild firmware

Usage:
    python3 scripts/apply_layout_changes.py display_geometry_modified.json
    python3 scripts/apply_layout_changes.py --dry-run modified.json
    python3 scripts/apply_layout_changes.py --validate-only modified.json
"""

import argparse
import json
import shutil
import subprocess
import sys
import zlib
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Path setup
ROOT = Path(__file__).resolve().parents[1]
CONFIG_GEOMETRY = ROOT / "config" / "display_geometry.json"
WEB_SIM_GEOMETRY = ROOT / "web" / "sim" / "geometry.json"
GEN_LAYOUT_SCRIPT = ROOT / "scripts" / "gen_layout_header.py"


class ValidationError(Exception):
    """Raised when layout validation fails"""
    pass


def load_json(path: Path) -> Dict[str, Any]:
    """Load JSON file"""
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    with open(path) as f:
        return json.load(f)


def save_json(path: Path, data: Dict[str, Any]) -> None:
    """Save JSON file with formatting"""
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)
        f.write('\n')  # Trailing newline


def compute_layout_crc(data: Dict[str, Any]) -> str:
    """Compute layout CRC the same way gen_layout_header.py does"""
    crc_obj = json.dumps(
        {"canvas": data["canvas"], "rects": data["rects"]},
        sort_keys=True
    ).encode("utf-8")
    crc = zlib.crc32(crc_obj) & 0xFFFFFFFF
    return f"0x{crc:08X}"


def validate_layout(data: Dict[str, Any]) -> List[str]:
    """
    Validate layout data for correctness.

    Returns list of validation errors (empty if valid).
    """
    errors = []

    # Check required fields
    if "canvas" not in data:
        errors.append("Missing 'canvas' field")
        return errors

    if "rects" not in data:
        errors.append("Missing 'rects' field")
        return errors

    canvas = data["canvas"]
    rects = data["rects"]

    # Validate canvas
    if "w" not in canvas or "h" not in canvas:
        errors.append("Canvas missing 'w' or 'h'")
        return errors

    canvas_w = canvas["w"]
    canvas_h = canvas["h"]

    if not isinstance(canvas_w, int) or not isinstance(canvas_h, int):
        errors.append(f"Canvas dimensions must be integers: w={canvas_w}, h={canvas_h}")

    if canvas_w <= 0 or canvas_h <= 0:
        errors.append(f"Canvas dimensions must be positive: {canvas_w}x{canvas_h}")

    # Validate regions
    for name, rect in rects.items():
        if not isinstance(rect, list) or len(rect) != 4:
            errors.append(f"{name}: Region must be [x, y, w, h], got {rect}")
            continue

        x, y, w, h = rect

        # Check types
        if not all(isinstance(v, int) for v in [x, y, w, h]):
            errors.append(f"{name}: Coordinates must be integers: {rect}")
            continue

        # Check bounds
        if x < 0 or y < 0:
            errors.append(f"{name}: Negative position ({x}, {y})")

        if w <= 0 or h <= 0:
            errors.append(f"{name}: Non-positive dimensions ({w}x{h})")

        if x + w > canvas_w:
            errors.append(
                f"{name}: Right edge ({x}+{w}={x+w}) exceeds canvas width ({canvas_w})"
            )

        if y + h > canvas_h:
            errors.append(
                f"{name}: Bottom edge ({y}+{h}={y+h}) exceeds canvas height ({canvas_h})"
            )

    # Check for collisions (warnings, not errors)
    collisions = []
    region_list = list(rects.items())
    for i in range(len(region_list)):
        for j in range(i + 1, len(region_list)):
            name1, rect1 = region_list[i]
            name2, rect2 = region_list[j]

            if rects_overlap(rect1, rect2):
                collisions.append(f"Collision: {name1} ↔ {name2}")

    if collisions:
        print("\n⚠️  Warning: Region collisions detected:")
        for collision in collisions:
            print(f"  - {collision}")
        print()

    return errors


def rects_overlap(rect1: List[int], rect2: List[int]) -> bool:
    """Check if two rectangles overlap"""
    x1, y1, w1, h1 = rect1
    x2, y2, w2, h2 = rect2

    return not (x1 + w1 <= x2 or x2 + w2 <= x1 or y1 + h1 <= y2 or y2 + h2 <= y1)


def check_grid_alignment(data: Dict[str, Any], grid_size: int = 4) -> List[str]:
    """Check if regions are aligned to grid (advisory, not blocking)"""
    misaligned = []

    for name, rect in data["rects"].items():
        x, y, w, h = rect

        if x % grid_size != 0 or y % grid_size != 0:
            misaligned.append(f"{name}: position ({x}, {y}) not aligned to {grid_size}px grid")

    return misaligned


def show_diff(original: Dict[str, Any], modified: Dict[str, Any]) -> None:
    """Show differences between original and modified layouts"""
    print("\n📊 Layout Changes:\n")

    orig_rects = original.get("rects", {})
    mod_rects = modified.get("rects", {})

    changes = []

    for name in sorted(set(orig_rects.keys()) | set(mod_rects.keys())):
        if name not in orig_rects:
            changes.append(f"  + {name}: NEW region {mod_rects[name]}")
        elif name not in mod_rects:
            changes.append(f"  - {name}: REMOVED")
        else:
            orig = orig_rects[name]
            mod = mod_rects[name]

            if orig != mod:
                dx = mod[0] - orig[0]
                dy = mod[1] - orig[1]
                dw = mod[2] - orig[2]
                dh = mod[3] - orig[3]

                parts = []
                if dx != 0 or dy != 0:
                    parts.append(f"moved ({dx:+d}, {dy:+d})")
                if dw != 0 or dh != 0:
                    parts.append(f"resized ({dw:+d}, {dh:+d})")

                changes.append(f"  • {name}: {orig} → {mod}")
                changes.append(f"    {', '.join(parts)}")

    if changes:
        print("\n".join(changes))
    else:
        print("  (No changes detected)")

    print()


def apply_changes(
    modified_path: Path,
    dry_run: bool = False,
    validate_only: bool = False
) -> None:
    """
    Apply layout changes from modified JSON file.

    Args:
        modified_path: Path to modified geometry JSON
        dry_run: If True, show what would be done but don't modify files
        validate_only: If True, only validate without showing diff or applying
    """
    print(f"📐 Layout Change Applier\n")
    print(f"Reading modified layout from: {modified_path}")

    # Load files
    try:
        modified_data = load_json(modified_path)
        original_data = load_json(CONFIG_GEOMETRY)
    except Exception as e:
        print(f"❌ Error loading files: {e}")
        sys.exit(1)

    # Validate modified layout
    print("\n✓ Validating modified layout...")
    errors = validate_layout(modified_data)

    if errors:
        print("\n❌ Validation failed:")
        for error in errors:
            print(f"  - {error}")
        sys.exit(1)

    print("✓ Layout is valid")

    # Check grid alignment (advisory)
    misaligned = check_grid_alignment(modified_data)
    if misaligned:
        print("\nℹ️  Grid alignment advisory (not blocking):")
        for msg in misaligned:
            print(f"  - {msg}")

    if validate_only:
        print("\n✅ Validation passed!")
        return

    # Show diff
    show_diff(original_data, modified_data)

    # Update layout_crc
    new_crc = compute_layout_crc(modified_data)
    modified_data["layout_crc"] = new_crc
    print(f"Updated layout_crc: {new_crc}")

    # Confirm changes
    if not dry_run:
        response = input("\nApply these changes? [y/N]: ").strip().lower()
        if response not in ['y', 'yes']:
            print("❌ Aborted")
            return

    # Apply changes
    if dry_run:
        print("\n🔍 Dry run mode - would perform:")
    else:
        print("\n📝 Applying changes...")

    operations = [
        (CONFIG_GEOMETRY, "Update config/display_geometry.json"),
        (WEB_SIM_GEOMETRY, "Update web/sim/geometry.json"),
    ]

    for target_path, description in operations:
        if dry_run:
            print(f"  • {description}")
        else:
            # Backup original
            backup_path = target_path.with_suffix('.json.backup')
            shutil.copy2(target_path, backup_path)

            # Write new content
            save_json(target_path, modified_data)
            print(f"  ✓ {description}")

    # Regenerate firmware headers
    if not dry_run:
        print("\n🔧 Regenerating firmware headers...")
        try:
            subprocess.run(
                [sys.executable, str(GEN_LAYOUT_SCRIPT)],
                check=True,
                capture_output=True,
                text=True
            )
            print("  ✓ Generated display_layout.h")
        except subprocess.CalledProcessError as e:
            print(f"  ⚠️  Warning: Header generation failed: {e}")
            print(f"     You may need to run: python3 {GEN_LAYOUT_SCRIPT}")

    # Success message
    print("\n" + "="*60)
    if dry_run:
        print("✅ Dry run complete - no files were modified")
    else:
        print("✅ Layout changes applied successfully!")
        print("\nNext steps:")
        print("  1. Reload web simulator: http://localhost:8000")
        print("  2. Or rebuild firmware: cd firmware/arduino && pio run")
        print("\nBackups saved with .backup extension")
    print("="*60 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Apply layout changes from web simulator export",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 scripts/apply_layout_changes.py modified.json
  python3 scripts/apply_layout_changes.py --dry-run modified.json
  python3 scripts/apply_layout_changes.py --validate-only modified.json
        """
    )

    parser.add_argument(
        "modified_json",
        type=Path,
        help="Path to modified geometry JSON exported from web simulator"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without modifying files"
    )

    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Only validate the modified JSON without applying changes"
    )

    args = parser.parse_args()

    # Check file exists
    if not args.modified_json.exists():
        print(f"❌ Error: File not found: {args.modified_json}")
        sys.exit(1)

    try:
        apply_changes(
            args.modified_json,
            dry_run=args.dry_run,
            validate_only=args.validate_only
        )
    except KeyboardInterrupt:
        print("\n\n❌ Aborted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
