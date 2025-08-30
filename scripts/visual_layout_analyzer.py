#!/usr/bin/env python3
"""
Automated Visual Layout Analyzer for ESP32 eInk Display

Captures screenshots of the web simulator for v2 layout, analyzes overlaps,
gaps, and alignment issues, and generates annotated reports.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Dict, List, Optional, Tuple
import base64

# Add project root to path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    import io

    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    from playwright.sync_api import sync_playwright
except Exception as e:  # pragma: no cover
    print(f"Missing dependency: {e}")
    print("Install with: pip install numpy pillow playwright")
    sys.exit(1)


@dataclass
class LayoutIssue:
    # Defaults provided so tests can introspect class attributes directly
    issue_type: str = ""  # 'overlap', 'gap', 'misalignment', 'overflow'
    severity: str = ""  # 'critical', 'warning', 'info'
    regions: List[str] = None  # type: ignore[assignment]
    description: str = ""
    coordinates: Optional[Tuple[int, int, int, int]] = None  # x,y,w,h


@dataclass
class RegionAnalysis:
    name: str
    rect: Tuple[int, int, int, int]
    category: str
    pixel_coverage: float
    content_bounds: Optional[Tuple[int, int, int, int]]
    issues: List[LayoutIssue]


class VisualLayoutAnalyzer:
    def __init__(self, web_root: Optional[str] = None):
        self.web_root = web_root or str(ROOT / "web" / "sim")
        self.out_dir = ROOT / "out"
        self.out_dir.mkdir(exist_ok=True)

    def _find_free_port(self) -> int:
        import socket

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            return s.getsockname()[1]

    def _start_http_server(self, root: str, port: int) -> subprocess.Popen:
        return subprocess.Popen(
            [sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1", "-d", root],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def _categorize(self, name: str) -> str:
        n = name.lower()
        if n.startswith("header_"):
            return "header"
        if n.startswith("footer_") or name == "STATUS":
            return "footer"
        if "label" in n:
            return "label"
        if n.startswith("out_row"):
            return "footer"
        if n.startswith("inside_") or n.startswith("out_") or "temp" in n:
            return "temp"
        return "other"

    def _capture(self, page, overlays: bool) -> bytes:
        # Toggle overlays via checkboxes if present
        try:
            if overlays:
                page.check("#showRects")
                page.uncheck("#showLabels")
            else:
                # ensure both off
                page.uncheck("#showRects")
                page.uncheck("#showLabels")
                # Also disable validation to prevent overlay artifacts
                page.uncheck("#enableValidation")
        except Exception:
            pass
        page.wait_for_timeout(100)

        # Prefer exact canvas pixels via toDataURL to avoid CSS scaling and mis-centering
        try:
            data_url = page.evaluate(
                "() => { const c = document.getElementById('epd'); return c ? c.toDataURL('image/png') : null; }"
            )
            if data_url and isinstance(data_url, str) and data_url.startswith("data:image/png"):
                b64 = data_url.split(",", 1)[1]
                return base64.b64decode(b64)
        except Exception:
            pass

        # Fallback: screenshot the canvas element if present
        try:
            el = page.query_selector("#epd")
            if el:
                return el.screenshot()
        except Exception:
            pass

        # Last resort: static clip (may be mis-centered depending on layout)
        return page.screenshot(clip={"x": 0, "y": 0, "width": 250, "height": 122})

    def _get_rects_from_page(self, page) -> Dict[str, List[int]]:
        try:
            rects = page.evaluate("() => (window.UI_SPEC && window.UI_SPEC.rects) || {}")
            if rects and isinstance(rects, dict):
                return {
                    str(k): [int(v[0]), int(v[1]), int(v[2]), int(v[3])]
                    for k, v in rects.items()
                    if isinstance(v, list) and len(v) == 4
                }
        except Exception:
            pass
        # fallback to ui_spec.json
        spec = json.loads((ROOT / "config" / "ui_spec.json").read_text())
        return spec.get("rects", {})

    def capture_variant(
        self, page, variant: str
    ) -> Tuple[np.ndarray, np.ndarray, Dict[str, List[int]]]:
        page.wait_for_timeout(100)
        rects = self._get_rects_from_page(page)
        # Capture base canvas pixels only and annotate ourselves for stability
        base_png = self._capture(page, overlays=False)
        base = Image.open(io.BytesIO(base_png)).convert("RGB")
        # Use base image as the background for annotated output
        return np.array(base), np.array(base.copy()), rects

    def analyze_coverage(
        self, img: np.ndarray, rects: Dict[str, List[int]]
    ) -> Dict[str, RegionAnalysis]:
        H, W = img.shape[0], img.shape[1]
        # Convert to grayscale and threshold
        gray = 0.2126 * img[:, :, 0] + 0.7152 * img[:, :, 1] + 0.0722 * img[:, :, 2]
        binary = (gray < 176).astype(np.uint8)
        out: Dict[str, RegionAnalysis] = {}
        for name, (x, y, w, h) in rects.items():
            x2, y2 = max(0, x), max(0, y)
            w2, h2 = max(0, min(w, W - x2)), max(0, min(h, H - y2))
            region = binary[y2 : y2 + h2, x2 : x2 + w2]
            total = max(1, w2 * h2)
            content = int(region.sum())
            cov = (content / total) * 100.0
            bounds: Optional[Tuple[int, int, int, int]] = None
            ys, xs = np.where(region > 0)
            if ys.size:
                miny, maxy = int(ys.min()), int(ys.max())
                minx, maxx = int(xs.min()), int(xs.max())
                bounds = (x2 + minx, y2 + miny, maxx - minx + 1, maxy - miny + 1)
            out[name] = RegionAnalysis(name, (x, y, w, h), self._categorize(name), cov, bounds, [])
        return out

    def detect_empty_blocks(
        self, analyses: Dict[str, RegionAnalysis], variant: str
    ) -> List[LayoutIssue]:
        issues: List[LayoutIssue] = []
        expected_content_regions: Dict[str, Dict[str, str]] = {
            "v2_grid": {
                "HEADER_NAME": "Room name text",
                "HEADER_TIME_CENTER": "Current time",
                "INSIDE_TEMP": "Inside temperature display",
                "OUT_TEMP": "Outside temperature display",
                "INSIDE_HUMIDITY": "Inside humidity percentage",
                "OUT_HUMIDITY": "Outside humidity",
                "OUT_WIND": "Wind speed",
                "FOOTER_STATUS": "Battery and system status",
            },
        }
        expected = expected_content_regions.get(variant, {})
        min_cov = {"header": 1.0, "temp": 15.0, "label": 8.0, "footer": 3.0, "other": 2.0}
        for name, hint in expected.items():
            if name not in analyses:
                issues.append(
                    LayoutIssue(
                        "missing_region",
                        "critical",
                        [name],
                        f"Expected region {name} ({hint}) not found in {variant}",
                    )
                )
                continue
            a = analyses[name]
            thr = min_cov.get(a.category, 2.0)
            if a.pixel_coverage < thr:
                if ("TEMP" in name) or (name in ("HEADER_NAME", "FOOTER_STATUS")):
                    sev = "critical"
                elif ("LABEL" in name) or (name in ("HEADER_TIME_CENTER", "INSIDE_HUMIDITY")):
                    sev = "warning"
                else:
                    sev = "info"
                issues.append(
                    LayoutIssue(
                        "empty_content",
                        sev,
                        [name],
                        f"{name} appears empty: {a.pixel_coverage:.1f}% " f"(< {thr}%) for {hint}",
                        a.rect,
                    )
                )
        return issues

    def generate_enhanced_text_report(
        self, variant: str, analyses: Dict[str, RegionAnalysis], issues: List[LayoutIssue]
    ) -> str:
        lines: List[str] = [
            f"Enhanced Visual Layout Analysis - {variant.upper()}",
            "=" * 60,
            f"Analyzed {len(analyses)} regions",
            f"Found {len(issues)} total issues",
            "",
        ]
        for sev in ("critical", "warning", "info"):
            items = [i for i in issues if i.severity == sev]
            if items:
                icon = {"critical": "🔴", "warning": "🟡", "info": "ℹ️"}[sev]
                lines.append(f"{icon} {sev.upper()} ISSUES ({len(items)}):")
                for it in items:
                    lines.append(f"  • {it.description}")
                lines.append("")
        lines.extend(["Region Coverage Analysis:", "-" * 30])
        cats: Dict[str, List[RegionAnalysis]] = {}
        for a in analyses.values():
            cats.setdefault(a.category, []).append(a)
        for cat, arr in cats.items():
            avg_cov = sum(x.pixel_coverage for x in arr) / len(arr)
            empty = len([x for x in arr if x.pixel_coverage < 2.0])
            lines.append(
                f"• {cat.title()}: {len(arr)} regions, "
                f"avg {avg_cov:.1f}% coverage, {empty} empty"
            )
        return "\n".join(lines)

    def _generate_variant_summary(
        self, analyses: Dict[str, RegionAnalysis], issues: List[LayoutIssue]
    ) -> Dict[str, object]:
        crit = [i for i in issues if i.severity == "critical"]
        warn = [i for i in issues if i.severity == "warning"]
        # Count empty regions via reported issues (critical/warning),
        # rather than raw pixel threshold
        empty_issue_count = len(
            [
                i
                for i in issues
                if i.issue_type == "empty_content" and i.severity in ("critical", "warning")
            ]
        )
        bounds_ok = len(
            [
                a
                for a in analyses.values()
                if (a.rect[0] + a.rect[2] <= 250 and a.rect[1] + a.rect[3] <= 122)
            ]
        )
        avg_cov = (
            (sum(a.pixel_coverage for a in analyses.values()) / len(analyses)) if analyses else 0.0
        )
        return {
            "total_regions": len(analyses),
            "total_issues": len(issues),
            "critical_issues": len(crit),
            "warning_issues": len(warn),
            "empty_regions": empty_issue_count,
            "avg_coverage": avg_cov,
            "bounds_compliant": bounds_ok,
        }

    def detect_overlaps(self, analyses: Dict[str, RegionAnalysis]) -> List[LayoutIssue]:
        issues: List[LayoutIssue] = []
        names = list(analyses.keys())

        def contains(r1: Tuple[int, int, int, int], r2: Tuple[int, int, int, int]) -> bool:
            x1, y1, w1, h1 = r1
            x2, y2, w2, h2 = r2
            return x1 <= x2 and y1 <= y2 and (x1 + w1) >= (x2 + w2) and (y1 + h1) >= (y2 + h2)

        def group(name: str) -> Optional[str]:
            n = name.upper()
            if n.startswith("INSIDE_TEMP") or n == "INSIDE_LABEL_BOX":
                return "INSIDE_TEMP"
            if n.startswith("OUT_TEMP") or n == "OUT_LABEL_BOX":
                return "OUT_TEMP"
            if n in ("FOOTER_L", "FOOTER_WEATHER", "STATUS"):
                return "FOOTER"
            if n in ("WEATHER_ICON",):
                return "WEATHER"
            return None

        def expected_overlap(
            a: str, ra: Tuple[int, int, int, int], b: str, rb: Tuple[int, int, int, int]
        ) -> bool:
            ga, gb = group(a), group(b)
            if ga and ga == gb and (contains(ra, rb) or contains(rb, ra)):
                return True
            # WEATHER_ICON lives inside the right footer region
            if (
                a.upper() == "FOOTER_WEATHER" and b.upper() == "WEATHER_ICON" and contains(ra, rb)
            ) or (
                b.upper() == "FOOTER_WEATHER" and a.upper() == "WEATHER_ICON" and contains(rb, ra)
            ):
                return True
            return False

        for i, a in enumerate(names):
            x1, y1, w1, h1 = analyses[a].rect
            for b in names[i + 1 :]:
                x2, y2, w2, h2 = analyses[b].rect
                L, R = max(x1, x2), min(x1 + w1, x2 + w2)
                T, B = max(y1, y2), min(y1 + h1, y2 + h2)
                if L < R and T < B:
                    if expected_overlap(a, (x1, y1, w1, h1), b, (x2, y2, w2, h2)):
                        continue
                    area = (R - L) * (B - T)
                    base = min(w1 * h1, w2 * h2)
                    pct = (area / base) * 100.0 if base > 0 else 0.0
                    sev = "critical" if pct > 50 else ("warning" if pct > 10 else "info")
                    issues.append(
                        LayoutIssue(
                            "overlap", sev, [a, b], f"{a}∩{b} ≈ {pct:.1f}%", (L, T, R - L, B - T)
                        )
                    )
        return issues

    def detect_alignment(
        self, analyses: Dict[str, RegionAnalysis], grid4: bool
    ) -> List[LayoutIssue]:
        issues: List[LayoutIssue] = []
        # Inside left alignment
        inside = [a for a in analyses.values() if a.name.startswith("INSIDE_")]
        if len(inside) >= 2:
            xs = {a.rect[0] for a in inside}
            if len(xs) > 1:
                issues.append(
                    LayoutIssue(
                        "misalignment",
                        "warning",
                        [a.name for a in inside],
                        f"INSIDE_* x not equal: {sorted(xs)}",
                    )
                )
        # OUT_ROW*_L vs OUT_ROW*_R y alignment
        rows = sorted(
            [a for a in analyses.values() if a.name.startswith("OUT_ROW")],
            key=lambda r: (r.rect[1], r.name),
        )
        for i in range(0, len(rows), 2):
            if i + 1 < len(rows):
                a, b = rows[i], rows[i + 1]
                if abs(a.rect[1] - b.rect[1]) > 1:
                    issues.append(
                        LayoutIssue(
                            "misalignment",
                            "warning",
                            [a.name, b.name],
                            f"Row y mismatch: {a.name}@{a.rect[1]} vs {b.name}@{b.rect[1]}",
                        )
                    )
        # v2 grid alignment (x,y multiples of 4)
        if grid4:
            bad_pos = [
                a.name for a in analyses.values() if (a.rect[0] % 4 != 0 or a.rect[1] % 4 != 0)
            ]
            if bad_pos:
                issues.append(
                    LayoutIssue("misalignment", "info", bad_pos, "Position not aligned to 4px grid")
                )
            bad_size = [
                a.name for a in analyses.values() if (a.rect[2] % 4 != 0 or a.rect[3] % 4 != 0)
            ]
            if bad_size:
                issues.append(
                    LayoutIssue("misalignment", "info", bad_size, "Size not aligned to 4px grid")
                )
        return issues

    def detect_canvas_overflow(self, analyses: Dict[str, RegionAnalysis]) -> List[LayoutIssue]:
        issues: List[LayoutIssue] = []
        CANVAS_W, CANVAS_H = 250, 122
        for name, a in analyses.items():
            x, y, w, h = a.rect
            if x < 0 or y < 0 or (x + w) > CANVAS_W or (y + h) > CANVAS_H:
                issues.append(
                    LayoutIssue(
                        "overflow", "critical", [name], f"{name} exceeds canvas: ({x},{y},{w},{h})"
                    )
                )
        return issues

    def detect_gaps(self, analyses: Dict[str, RegionAnalysis]) -> List[LayoutIssue]:
        issues: List[LayoutIssue] = []

        def bottom(a: RegionAnalysis) -> int:
            return a.rect[1] + a.rect[3]

        # Example expectations derived from rects rather than hardcoding
        pairs = [("INSIDE_TEMP", "INSIDE_RH"), ("OUT_TEMP", "OUT_ROW1_L")]
        for a, b in pairs:
            if a in analyses and b in analyses:
                analyses[b].rect[1] - bottom(analyses[a])
                # no-op unless we establish goldens; keep structure
        return issues

    def detect_temp_cropping(self, analyses: Dict[str, RegionAnalysis]) -> List[LayoutIssue]:
        issues: List[LayoutIssue] = []
        for name in ("INSIDE_TEMP", "OUT_TEMP"):
            a = analyses.get(name)
            if not a or not a.content_bounds:
                continue
            x, y, w, h = a.rect
            bx, by, bw, bh = a.content_bounds
            top_touch = (by - y) <= 1
            bottom_touch = (y + h) - (by + bh) <= 1
            if top_touch or bottom_touch:
                issues.append(
                    LayoutIssue(
                        "temp_cropping",
                        "error",
                        name,
                        "Temperature content touches region {} edge".format(
                            "top" if top_touch else "bottom"
                        ),
                        a.rect,
                    )
                )
        return issues

    def detect_weather_layout(self, analyses: Dict[str, RegionAnalysis]) -> List[LayoutIssue]:
        issues: List[LayoutIssue] = []
        icon = analyses.get("WEATHER_ICON")
        bar = analyses.get("FOOTER_WEATHER")
        # Check icon left-justified inside its rect
        if icon and icon.content_bounds:
            rx, ry, rw, rh = icon.rect
            bx, by, bw, bh = icon.content_bounds
            if (bx - rx) > 3:
                issues.append(
                    LayoutIssue(
                        "weather_icon_alignment",
                        "warning",
                        "WEATHER_ICON",
                        "Weather icon not left-justified in its box",
                        icon.rect,
                    )
                )
        # Check that FOOTER_WEATHER has text starting right of the icon box
        if icon and bar and bar.content_bounds:
            ix, iy, iw, ih = icon.rect
            bx, by, bw, bh = bar.content_bounds
            if bx < (ix + iw + 4):
                issues.append(
                    LayoutIssue(
                        "weather_text_alignment",
                        "warning",
                        "FOOTER_WEATHER",
                        "Weather text starts too far left; should follow icon",
                        bar.rect,
                    )
                )
        return issues

    def detect_label_clear_line(self, base_img: np.ndarray, analyses: Dict[str, RegionAnalysis]) -> List[LayoutIssue]:
        """Detect horizontal lines cutting through text labels using dynamic spec-driven detection"""
        issues: List[LayoutIssue] = []
        import numpy as _np
        H, W = base_img.shape[0], base_img.shape[1]
        gray = 0.2126 * base_img[:, :, 0] + 0.7152 * base_img[:, :, 1] + 0.0722 * base_img[:, :, 2]
        binary = (gray < 176).astype(_np.uint8)
        
        # Load spec-driven parameters
        try:
            spec = json.loads((ROOT / "config" / "ui_spec.json").read_text())
            tokens = spec.get("fonts", {}).get("tokens", {})
            label_px = int(tokens.get("label", {}).get("px", 11))
        except Exception:
            spec = {}
            label_px = 11
        
        # Find center divider x from chrome
        center_x = 125
        try:
            for ln in spec.get("components", {}).get("chrome", []):
                if ln.get("op") != "line":
                    continue
                x1, y1 = ln.get("from", [0, 0])
                x2, y2 = ln.get("to", [0, 0])
                if x1 == x2 and y1 != y2:  # Vertical line
                    center_x = int(x1)
                    break
        except Exception:
            pass
        
        # Find label positions from spec components
        def find_label_xy(section: str):
            ops = spec.get("components", {}).get(section, [])
            for op in ops:
                if op.get("op") == "text" and op.get("font") == "label":
                    return int(op.get("x", 0)), int(op.get("y", 20))
            return None, None
        
        inside_x, inside_y = find_label_xy("inside")
        outside_x, outside_y = find_label_xy("outside")
        
        # Use temp rects to bound scan width
        left_rect = analyses.get("INSIDE_TEMP")
        right_rect = analyses.get("OUT_TEMP")
        
        label_regions = []
        if inside_y is not None and left_rect:
            left_x1 = left_rect.rect[0]
            left_x2 = min(left_rect.rect[0] + left_rect.rect[2] - 1, center_x - 3)
            label_regions.append(("INSIDE", left_x1, left_x2, inside_y, min(H, inside_y + label_px)))
        
        if outside_y is not None and right_rect:
            right_x1 = max(right_rect.rect[0], center_x + 3)
            right_x2 = min(right_rect.rect[0] + right_rect.rect[2] - 1, W - 2)
            label_regions.append(("OUTSIDE", right_x1, right_x2, outside_y, min(H, outside_y + label_px)))
        
        # Build chrome mask to exclude chrome pixels from content
        chrome_mask = _np.zeros_like(binary)
        try:
            for ln in spec.get("components", {}).get("chrome", []):
                if ln.get("op") != "line":
                    continue
                x1, y1 = ln.get("from", [0, 0])
                x2, y2 = ln.get("to", [0, 0])
                if y1 == y2:  # Horizontal line
                    y = int(y1)
                    if 0 <= y < H:
                        chrome_mask[y, max(0, min(x1, x2)):min(W, max(x1, x2) + 1)] = 1
                elif x1 == x2:  # Vertical line
                    x = int(x1)
                    if 0 <= x < W:
                        chrome_mask[max(0, min(y1, y2)):min(H, max(y1, y2) + 1), x] = 1
        except Exception:
            pass
        
        # Remove chrome pixels from binary to get content only
        content = binary.copy()
        content[chrome_mask == 1] = 0
        
        for label_name, x_start, x_end, y_start, y_end in label_regions:
            if x_end <= x_start or y_end <= y_start:
                continue
            
            # Check for lines NEAR the label region, not within the text itself
            # Check 2 pixels above and below the label region
            check_ys = []
            if y_start - 2 >= 0:
                check_ys.append(y_start - 2)
            if y_start - 1 >= 0:
                check_ys.append(y_start - 1)
            if y_end < H:
                check_ys.append(y_end)
            if y_end + 1 < H:
                check_ys.append(y_end + 1)
            
            for y in check_ys:
                if x_end <= W:
                    line_pixels = content[y, x_start:x_end+1]
                    
                    # Detect segments (lines broken by text)
                    segments = []
                    in_segment = False
                    segment_start = 0
                    
                    for x_idx, pixel in enumerate(line_pixels):
                        if pixel > 0:
                            if not in_segment:
                                segment_start = x_idx
                                in_segment = True
                        else:
                            if in_segment:
                                segment_len = x_idx - segment_start
                                if segment_len >= 2:
                                    segments.append((segment_start, x_idx))
                                in_segment = False
                    
                    # Handle segment at end
                    if in_segment:
                        segment_len = len(line_pixels) - segment_start
                        if segment_len >= 2:
                            segments.append((segment_start, len(line_pixels)))
                    
                    # Check for line-through-text pattern
                    if len(segments) >= 2:
                        total_pixels = sum(end - start for start, end in segments)
                        coverage = total_pixels / len(line_pixels) if len(line_pixels) > 0 else 0
                        
                        gaps = []
                        for i in range(1, len(segments)):
                            gap = segments[i][0] - segments[i-1][1]
                            gaps.append(gap)
                        
                        avg_gap = sum(gaps) / len(gaps) if gaps else 0
                        
                        # Heuristics: coverage > 0.20 and gaps 2-15px indicates line through text
                        if coverage > 0.20 and 2 <= avg_gap <= 15:
                            issues.append(
                                LayoutIssue(
                                    "line_through_text",
                                    "critical",
                                    [label_name + "_LABEL"],
                                    f"Horizontal line intersects {label_name} label at y={y}",
                                    (x_start, y, x_end - x_start + 1, 1)
                                )
                            )
                            break  # Only report once per label
        
        return issues
    
    def detect_label_temp_collision(self, analyses: Dict[str, RegionAnalysis]) -> List[LayoutIssue]:
        """Detect collision between INSIDE/OUTSIDE labels and temperature values using geometry"""
        issues: List[LayoutIssue] = []
        
        # Get label positions from spec
        try:
            spec = json.loads((ROOT / "config" / "ui_spec.json").read_text())
            label_px = int(spec.get("fonts", {}).get("tokens", {}).get("label", {}).get("px", 11))
            
            def get_label_y(section: str) -> Optional[int]:
                for op in spec.get("components", {}).get(section, []):
                    if op.get("op") == "text" and op.get("font") == "label":
                        return int(op.get("y", 20))
                return None
            
            inside_label_y = get_label_y("inside")
            outside_label_y = get_label_y("outside")
        except Exception:
            label_px = 11
            inside_label_y = None
            outside_label_y = None
        
        # Check collisions using actual geometry
        pairs = [
            ("INSIDE_TEMP", inside_label_y, "INSIDE"),
            ("OUT_TEMP", outside_label_y, "OUTSIDE")
        ]
        
        for temp_name, label_y, label_name in pairs:
            if label_y is None:
                continue
                
            temp_region = analyses.get(temp_name)
            if temp_region is None:
                continue
            
            # Calculate overlap
            label_bottom = label_y + label_px
            temp_top = temp_region.rect[1]
            overlap = label_bottom - temp_top
            
            # Report based on thresholds
            if overlap >= 4:
                issues.append(
                    LayoutIssue(
                        "label_temp_overlap",
                        "critical",
                        [temp_name],
                        f"{label_name} label overlaps temperature by {overlap}px",
                        temp_region.rect
                    )
                )
            elif overlap >= 1:
                issues.append(
                    LayoutIssue(
                        "label_temp_proximity",
                        "warning",
                        [temp_name],
                        f"{label_name} label too close to temperature (overlap: {overlap}px)",
                        temp_region.rect
                    )
                )
        
        return issues
    
    def detect_fahrenheit_centerline_collision(self, analyses: Dict[str, RegionAnalysis]) -> List[LayoutIssue]:
        """[DEPRECATED] Fahrenheit collision detection is now handled by detect_centerline_content_collision.
        
        This method is kept for backward compatibility but returns no issues.
        The geometry-based detection in detect_centerline_content_collision now handles
        all content-divider collisions including temperature badges.
        """
        return []  # Functionality moved to detect_centerline_content_collision
    
    def detect_centerline_content_collision(self, base_img: np.ndarray, analyses: Dict[str, RegionAnalysis]) -> List[LayoutIssue]:
        """Detect content collision with center divider using pure geometry"""
        issues: List[LayoutIssue] = []
        
        # Get center divider position from chrome
        center_x = 125
        try:
            spec = json.loads((ROOT / "config" / "ui_spec.json").read_text())
            for ln in spec.get("components", {}).get("chrome", []):
                if ln.get("op") != "line":
                    continue
                x1, y1 = ln.get("from", [0, 0])
                x2, y2 = ln.get("to", [0, 0])
                if x1 == x2 and y1 != y2:  # Vertical line
                    center_x = int(x1)
                    break
        except Exception:
            pass
        
        # Check gaps using geometry only
        left = analyses.get("INSIDE_TEMP")
        right = analyses.get("OUT_TEMP")
        min_gap = 4  # Threshold for warnings
        
        if left:
            # Calculate gap from left region to center
            left_edge = left.rect[0] + left.rect[2]
            left_gap = center_x - left_edge
            
            # Debug output
            if self.debug:
                print(f"DEBUG: INSIDE_TEMP rect={left.rect}, left_edge={left_edge}, center_x={center_x}, gap={left_gap}")
            
            if left_gap < 0:
                issues.append(
                    LayoutIssue(
                        "inside_temp_centerline_collision",
                        "critical",
                        ["INSIDE_TEMP"],
                        f"INSIDE temperature crosses center divider (gap: {left_gap}px)",
                        (center_x - 5, left.rect[1], 10, left.rect[3])
                    )
                )
            elif left_gap < min_gap:
                issues.append(
                    LayoutIssue(
                        "inside_temp_centerline_proximity",
                        "warning",
                        ["INSIDE_TEMP"],
                        f"INSIDE temperature too close to center divider (gap: {left_gap}px)",
                        (center_x - 5, left.rect[1], 10, left.rect[3])
                    )
                )
        
        if right:
            # Calculate gap from center to right region
            right_edge = right.rect[0]
            right_gap = right_edge - center_x
            
            if right_gap < 0:
                issues.append(
                    LayoutIssue(
                        "outside_temp_centerline_collision",
                        "critical",
                        ["OUT_TEMP"],
                        f"OUTSIDE temperature crosses center divider (gap: {right_gap}px)",
                        (center_x - 5, right.rect[1], 10, right.rect[3])
                    )
                )
            elif right_gap < min_gap:
                issues.append(
                    LayoutIssue(
                        "outside_temp_centerline_proximity",
                        "warning",
                        ["OUT_TEMP"],
                        f"OUTSIDE temperature too close to center divider (gap: {right_gap}px)",
                        (center_x - 5, right.rect[1], 10, right.rect[3])
                    )
                )
        
        return issues

    def check_chrome_continuity(self, img: np.ndarray) -> List[LayoutIssue]:
        """Check for gaps in chrome lines defined in ui_spec.json"""
        issues: List[LayoutIssue] = []
        
        # Load chrome definitions from ui_spec
        try:
            spec = json.loads((ROOT / "config" / "ui_spec.json").read_text())
            chrome_lines = spec.get("components", {}).get("chrome", [])
        except Exception:
            return issues
        
        # Convert to grayscale and threshold
        gray = 0.2126 * img[:, :, 0] + 0.7152 * img[:, :, 1] + 0.0722 * img[:, :, 2]
        binary = (gray < 176).astype(np.uint8)
        
        for line_def in chrome_lines:
            if line_def.get("op") != "line":
                continue
            
            from_pt = line_def.get("from", [0, 0])
            to_pt = line_def.get("to", [0, 0])
            x1, y1 = from_pt[0], from_pt[1]
            x2, y2 = to_pt[0], to_pt[1]
            
            # Check horizontal lines
            if y1 == y2:
                y = y1
                if y < 0 or y >= img.shape[0]:
                    continue
                x_start = min(x1, x2)
                x_end = max(x1, x2)
                # Sample along the line
                gaps = []
                for x in range(x_start, min(x_end + 1, img.shape[1])):
                    if binary[y, x] == 0:  # No pixel at this position
                        gaps.append(x)
                
                # Report significant gaps (more than 2 pixels)
                if len(gaps) > 2:
                    gap_ranges = []
                    start = gaps[0]
                    for i in range(1, len(gaps)):
                        if gaps[i] != gaps[i-1] + 1:
                            gap_ranges.append((start, gaps[i-1]))
                            start = gaps[i]
                    gap_ranges.append((start, gaps[-1]))
                    
                    for gap_start, gap_end in gap_ranges:
                        gap_width = gap_end - gap_start + 1
                        if gap_width > 5:  # Only report gaps wider than 5 pixels (allow for text overlap)
                            issues.append(
                                LayoutIssue(
                                    "chrome_gap",
                                    "info" if gap_width < 10 else "warning" if gap_width < 30 else "critical",
                                    [],
                                    f"Gap in horizontal chrome line at y={y}, x={gap_start}-{gap_end} ({gap_width}px)",
                                    (gap_start, y, gap_width, 1)
                                )
                            )
            
            # Check vertical lines
            elif x1 == x2:
                x = x1
                if x < 0 or x >= img.shape[1]:
                    continue
                y_start = min(y1, y2)
                y_end = max(y1, y2)
                # Sample along the line
                gaps = []
                for y in range(y_start, min(y_end + 1, img.shape[0])):
                    if binary[y, x] == 0:  # No pixel at this position
                        gaps.append(y)
                
                # Report significant gaps
                if len(gaps) > 2:
                    gap_ranges = []
                    start = gaps[0]
                    for i in range(1, len(gaps)):
                        if gaps[i] != gaps[i-1] + 1:
                            gap_ranges.append((start, gaps[i-1]))
                            start = gaps[i]
                    gap_ranges.append((start, gaps[-1]))
                    
                    for gap_start, gap_end in gap_ranges:
                        gap_width = gap_end - gap_start + 1
                        if gap_width > 5:  # Only report gaps wider than 5 pixels (allow for text overlap)
                            issues.append(
                                LayoutIssue(
                                    "chrome_gap",
                                    "info" if gap_width < 10 else "warning" if gap_width < 30 else "critical",
                                    [],
                                    f"Gap in vertical chrome line at x={x}, y={gap_start}-{gap_end} ({gap_width}px)",
                                    (x, gap_start, 1, gap_width)
                                )
                            )
        
        return issues

    def annotate(
        self, base_img: np.ndarray, analyses: Dict[str, RegionAnalysis], issues: List[LayoutIssue]
    ) -> Image.Image:
        img = Image.fromarray(base_img).convert("RGBA")
        ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(ov)
        for a in analyses.values():
            x, y, w, h = a.rect
            # Skip invalid/non-positive rectangles
            if w <= 0 or h <= 0:
                continue
            draw.rectangle(
                (x, y, x + w - 1, y + h - 1),
                outline=(128, 128, 128, 255),
                fill=(128, 128, 128, 64),
                width=1,
            )
            try:
                font = ImageFont.load_default()
                draw.text((x + 2, y + 2), a.name, fill=(0, 0, 0, 255), font=font)
            except Exception:
                draw.text((x + 2, y + 2), a.name, fill=(0, 0, 0, 255))
        for issue in issues:
            color = (
                (255, 0, 0, 128)
                if issue.severity == "critical"
                else (255, 165, 0, 128) if issue.severity == "warning" else (255, 255, 0, 128)
            )
            if issue.coordinates:
                x, y, w, h = issue.coordinates
                if w > 0 and h > 0:
                    draw.rectangle(
                        (x, y, x + w - 1, y + h - 1), outline=color[:3] + (255,), fill=color, width=2
                    )
            else:
                for r in issue.regions:
                    if r in analyses:
                        x, y, w, h = analyses[r].rect
                        if w <= 0 or h <= 0:
                            continue
                        draw.rectangle(
                            (x, y, x + w - 1, y + h - 1),
                            outline=color[:3] + (255,),
                            fill=color,
                            width=2,
                        )
        return Image.alpha_composite(img, ov).convert("RGB")

    def run(self, variants: Optional[List[str]] = None) -> Dict[str, Dict[str, object]]:
        variants = variants or ["v2_grid"]
        port = self._find_free_port()
        server = self._start_http_server(self.web_root, port)
        results: Dict[str, Dict[str, object]] = {}
        try:
            time.sleep(0.4)
            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page(viewport={"width": 700, "height": 400})
                page.goto(f"http://127.0.0.1:{port}/index.html", wait_until="load")
                page.wait_for_timeout(300)
                for variant in variants:
                    base_img, over_img, rects = self.capture_variant(page, variant)
                    analyses = self.analyze_coverage(base_img, rects)
                    issues: List[LayoutIssue] = []
                    issues += self.detect_overlaps(analyses)
                    issues += self.detect_alignment(analyses, grid4=(variant.startswith("v2")))
                    issues += self.detect_canvas_overflow(analyses)
                    issues += self.detect_empty_blocks(analyses, variant)
                    issues += self.detect_gaps(analyses)
                    issues += self.detect_temp_cropping(analyses)
                    issues += self.detect_weather_layout(analyses)
                    # Detect all label and layout issues
                    issues += self.detect_label_clear_line(base_img, analyses)
                    issues += self.detect_label_temp_collision(analyses)
                    issues += self.detect_fahrenheit_centerline_collision(analyses)
                    issues += self.detect_centerline_content_collision(base_img, analyses)
                    annotated = self.annotate(base_img, analyses, issues)
                    # Save artifacts
                    Image.fromarray(base_img).save(self.out_dir / f"layout_analysis_{variant}.png")
                    annotated.save(self.out_dir / f"layout_analysis_{variant}_annotated.png")
                    # Enhanced text report
                    report_txt = self.generate_enhanced_text_report(variant, analyses, issues)
                    (self.out_dir / f"layout_analysis_{variant}_report.txt").write_text(report_txt)
                    results[variant] = {
                        "analyses": analyses,
                        "issues": issues,
                        "text_report": report_txt,
                        "summary": self._generate_variant_summary(analyses, issues),
                    }
                browser.close()
        finally:
            server.terminate()
            server.wait(timeout=2)
        return results


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(description="Analyze ESP32 eInk display layout")
    ap.add_argument("--variants", nargs="*", default=["v2_grid"])
    ap.add_argument("--web-root", default=str(ROOT / "web" / "sim"))
    args = ap.parse_args()
    analyzer = VisualLayoutAnalyzer(args.web_root)
    results = analyzer.run(args.variants)
    # Count critical issues explicitly to satisfy type checkers
    critical = 0
    for v in results.values():
        issues_list_obj = v.get("issues")
        if not isinstance(issues_list_obj, list):
            continue
        for i in issues_list_obj:
            if isinstance(i, LayoutIssue) and i.severity == "critical":
                critical += 1
    if critical:
        print(f"Found {critical} critical issues.")
        sys.exit(1)
    print("No critical layout issues detected.")


if __name__ == "__main__":
    main()
