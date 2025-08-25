#!/usr/bin/env python3
"""
Automated Visual Layout Analyzer for ESP32 eInk Display

Captures screenshots of the web simulator for v2 layout, analyzes overlaps,
gaps, and alignment issues, and generates annotated reports.
"""

from __future__ import annotations

import json
import os
import sys
import time
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple, Optional

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
    issue_type: str  # 'overlap', 'gap', 'misalignment', 'overflow'
    severity: str    # 'critical', 'warning', 'info'
    regions: List[str]
    description: str
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
        if n.startswith("header_"): return "header"
        if n.startswith("footer_") or name == "STATUS": return "footer"
        if "label" in n: return "label"
        if n.startswith("out_row"): return "footer"
        if n.startswith("inside_") or n.startswith("out_") or "temp" in n: return "temp"
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
        except Exception:
            pass
        page.wait_for_timeout(100)
        return page.screenshot(clip={"x":0, "y":0, "width":250, "height":122})

    def _get_rects_from_page(self, page) -> Dict[str, List[int]]:
        try:
            rects = page.evaluate("() => (window.UI_SPEC && window.UI_SPEC.rects) || {}")
            if rects and isinstance(rects, dict):
                return {str(k): [int(v[0]), int(v[1]), int(v[2]), int(v[3])] for k,v in rects.items() if isinstance(v, list) and len(v)==4}
        except Exception:
            pass
        # fallback to ui_spec.json
        spec = json.loads((ROOT / "config" / "ui_spec.json").read_text())
        return spec.get("rects", {})

    def capture_variant(self, page, variant: str) -> Tuple[np.ndarray, np.ndarray, Dict[str, List[int]]]:
        page.wait_for_timeout(100)
        rects = self._get_rects_from_page(page)
        # A: base capture without overlays (for coverage)
        base_png = self._capture(page, overlays=False)
        # B: overlay capture for annotation
        over_png = self._capture(page, overlays=True)
        base = Image.open(io.BytesIO(base_png)).convert("RGB")
        over = Image.open(io.BytesIO(over_png)).convert("RGB")
        return np.array(base), np.array(over), rects

    def analyze_coverage(self, img: np.ndarray, rects: Dict[str, List[int]]) -> Dict[str, RegionAnalysis]:
        H, W = img.shape[0], img.shape[1]
        # Convert to grayscale and threshold
        gray = 0.2126 * img[:, :, 0] + 0.7152 * img[:, :, 1] + 0.0722 * img[:, :, 2]
        binary = (gray < 176).astype(np.uint8)
        out: Dict[str, RegionAnalysis] = {}
        for name, (x,y,w,h) in rects.items():
            x2, y2 = max(0,x), max(0,y)
            w2, h2 = max(0,min(w, W-x2)), max(0,min(h, H-y2))
            region = binary[y2:y2+h2, x2:x2+w2]
            total = max(1, w2*h2)
            content = int(region.sum())
            cov = (content/total)*100.0
            bounds: Optional[Tuple[int,int,int,int]] = None
            ys, xs = np.where(region>0)
            if ys.size:
                miny, maxy = int(ys.min()), int(ys.max())
                minx, maxx = int(xs.min()), int(xs.max())
                bounds = (x2+minx, y2+miny, maxx-minx+1, maxy-miny+1)
            out[name] = RegionAnalysis(name, (x,y,w,h), self._categorize(name), cov, bounds, [])
        return out

    def detect_empty_blocks(self, analyses: Dict[str, RegionAnalysis], variant: str) -> List[LayoutIssue]:
        issues: List[LayoutIssue] = []
        expected_content_regions: Dict[str, Dict[str, str]] = {
            'v2_grid': {
                'HEADER_NAME': 'Room name text',
                'HEADER_TIME': 'Current time',
                'INSIDE_TEMP': 'Inside temperature display',
                'OUT_TEMP': 'Outside temperature display',
                'INSIDE_RH': 'Inside humidity percentage',
                'OUT_ROW1_L': 'Outside humidity',
                'OUT_ROW1_R': 'Wind speed',
                'WEATHER_BAR': 'Weather icon and condition',
                'STATUS': 'Battery and system status',
            },
        }
        expected = expected_content_regions.get(variant, {})
        min_cov = {'header': 1.0, 'temp': 15.0, 'label': 8.0, 'footer': 3.0, 'other': 2.0}
        for name, hint in expected.items():
            if name not in analyses:
                issues.append(LayoutIssue('missing_region', 'critical', [name], f"Expected region {name} ({hint}) not found in {variant}"))
                continue
            a = analyses[name]
            thr = min_cov.get(a.category, 2.0)
            if a.pixel_coverage < thr:
                if ('TEMP' in name) or (name in ('HEADER_NAME', 'STATUS')):
                    sev = 'critical'
                elif ('LABEL' in name) or (name in ('HEADER_TIME', 'INSIDE_RH')):
                    sev = 'warning'
                else:
                    sev = 'info'
                issues.append(LayoutIssue('empty_content', sev, [name], f"{name} appears empty: {a.pixel_coverage:.1f}% (< {thr}%) for {hint}", a.rect))
        return issues

    def generate_enhanced_text_report(self, variant: str, analyses: Dict[str, RegionAnalysis], issues: List[LayoutIssue]) -> str:
        lines: List[str] = [
            f"Enhanced Visual Layout Analysis - {variant.upper()}",
            "=" * 60,
            f"Analyzed {len(analyses)} regions",
            f"Found {len(issues)} total issues",
            "",
        ]
        for sev in ('critical','warning','info'):
            items = [i for i in issues if i.severity == sev]
            if items:
                icon = {'critical':'🔴','warning':'🟡','info':'ℹ️'}[sev]
                lines.append(f"{icon} {sev.upper()} ISSUES ({len(items)}):")
                for it in items:
                    lines.append(f"  • {it.description}")
                lines.append("")
        lines.extend(["Region Coverage Analysis:", "-"*30])
        cats: Dict[str, List[RegionAnalysis]] = {}
        for a in analyses.values():
            cats.setdefault(a.category, []).append(a)
        for cat, arr in cats.items():
            avg_cov = sum(x.pixel_coverage for x in arr)/len(arr)
            empty = len([x for x in arr if x.pixel_coverage < 2.0])
            lines.append(f"• {cat.title()}: {len(arr)} regions, avg {avg_cov:.1f}% coverage, {empty} empty")
        return "\n".join(lines)

    def _generate_variant_summary(self, analyses: Dict[str, RegionAnalysis], issues: List[LayoutIssue]) -> Dict[str, object]:
        crit = [i for i in issues if i.severity == 'critical']
        warn = [i for i in issues if i.severity == 'warning']
        # Count empty regions via reported issues (critical/warning), rather than raw pixel threshold
        empty_issue_count = len([i for i in issues if i.issue_type == 'empty_content' and i.severity in ('critical','warning')])
        bounds_ok = len([a for a in analyses.values() if (a.rect[0]+a.rect[2] <= 250 and a.rect[1]+a.rect[3] <= 122)])
        avg_cov = (sum(a.pixel_coverage for a in analyses.values())/len(analyses)) if analyses else 0.0
        return {
            'total_regions': len(analyses),
            'total_issues': len(issues),
            'critical_issues': len(crit),
            'warning_issues': len(warn),
            'empty_regions': empty_issue_count,
            'avg_coverage': avg_cov,
            'bounds_compliant': bounds_ok,
        }

    def detect_overlaps(self, analyses: Dict[str, RegionAnalysis]) -> List[LayoutIssue]:
        issues: List[LayoutIssue] = []
        names = list(analyses.keys())
        def contains(r1: Tuple[int,int,int,int], r2: Tuple[int,int,int,int]) -> bool:
            x1,y1,w1,h1 = r1; x2,y2,w2,h2 = r2
            return x1 <= x2 and y1 <= y2 and (x1+w1) >= (x2+w2) and (y1+h1) >= (y2+h2)
        def group(name: str) -> Optional[str]:
            n = name.upper()
            if n.startswith('INSIDE_TEMP') or n == 'INSIDE_LABEL_BOX': return 'INSIDE_TEMP'
            if n.startswith('OUT_TEMP') or n == 'OUT_LABEL_BOX': return 'OUT_TEMP'
            if n in ('FOOTER_L','FOOTER_R','STATUS','WEATHER_BAR'): return 'FOOTER'
            if n in ('OUT_ICON',): return 'WEATHER'
            return None
        def expected_overlap(a: str, ra: Tuple[int,int,int,int], b: str, rb: Tuple[int,int,int,int]) -> bool:
            ga, gb = group(a), group(b)
            if ga and ga == gb and (contains(ra, rb) or contains(rb, ra)):
                return True
            if (a.upper() == 'WEATHER_BAR' and b.upper() == 'OUT_ICON' and contains(ra, rb)) or \
               (b.upper() == 'WEATHER_BAR' and a.upper() == 'OUT_ICON' and contains(rb, ra)):
                return True
            # OUT_ICON lives inside the right footer region
            if (a.upper() == 'FOOTER_R' and b.upper() == 'OUT_ICON' and contains(ra, rb)) or \
               (b.upper() == 'FOOTER_R' and a.upper() == 'OUT_ICON' and contains(rb, ra)):
                return True
            return False
        for i, a in enumerate(names):
            x1,y1,w1,h1 = analyses[a].rect
            for b in names[i+1:]:
                x2,y2,w2,h2 = analyses[b].rect
                L,R = max(x1,x2), min(x1+w1, x2+w2)
                T,B = max(y1,y2), min(y1+h1, y2+h2)
                if L<R and T<B:
                    if expected_overlap(a, (x1,y1,w1,h1), b, (x2,y2,w2,h2)):
                        continue
                    area = (R-L)*(B-T)
                    base = min(w1*h1, w2*h2)
                    pct = (area/base)*100.0 if base>0 else 0.0
                    sev = 'critical' if pct>50 else ('warning' if pct>10 else 'info')
                    issues.append(LayoutIssue('overlap', sev, [a,b], f"{a}∩{b} ≈ {pct:.1f}%", (L,T,R-L,B-T)))
        return issues

    def detect_alignment(self, analyses: Dict[str, RegionAnalysis], grid4: bool) -> List[LayoutIssue]:
        issues: List[LayoutIssue] = []
        # Inside left alignment
        inside = [a for a in analyses.values() if a.name.startswith('INSIDE_')]
        if len(inside)>=2:
            xs = {a.rect[0] for a in inside}
            if len(xs)>1:
                issues.append(LayoutIssue('misalignment','warning',[a.name for a in inside], f"INSIDE_* x not equal: {sorted(xs)}"))
        # OUT_ROW*_L vs OUT_ROW*_R y alignment
        rows = sorted([a for a in analyses.values() if a.name.startswith('OUT_ROW')], key=lambda r:(r.rect[1], r.name))
        for i in range(0,len(rows),2):
            if i+1<len(rows):
                a,b = rows[i], rows[i+1]
                if abs(a.rect[1]-b.rect[1])>1:
                    issues.append(LayoutIssue('misalignment','warning',[a.name,b.name], f"Row y mismatch: {a.name}@{a.rect[1]} vs {b.name}@{b.rect[1]}"))
        # v2 grid alignment (x,y multiples of 4)
        if grid4:
            bad_pos = [a.name for a in analyses.values() if (a.rect[0]%4!=0 or a.rect[1]%4!=0)]
            if bad_pos:
                issues.append(LayoutIssue('misalignment','info', bad_pos, 'Position not aligned to 4px grid'))
            bad_size = [a.name for a in analyses.values() if (a.rect[2]%4!=0 or a.rect[3]%4!=0)]
            if bad_size:
                issues.append(LayoutIssue('misalignment','info', bad_size, 'Size not aligned to 4px grid'))
        return issues

    def detect_canvas_overflow(self, analyses: Dict[str, RegionAnalysis]) -> List[LayoutIssue]:
        issues: List[LayoutIssue] = []
        CANVAS_W, CANVAS_H = 250, 122
        for name, a in analyses.items():
            x,y,w,h = a.rect
            if x < 0 or y < 0 or (x+w) > CANVAS_W or (y+h) > CANVAS_H:
                issues.append(LayoutIssue('overflow','critical',[name], f"{name} exceeds canvas: ({x},{y},{w},{h})"))
        return issues

    def detect_gaps(self, analyses: Dict[str, RegionAnalysis]) -> List[LayoutIssue]:
        issues: List[LayoutIssue] = []
        def bottom(a: RegionAnalysis) -> int: return a.rect[1]+a.rect[3]
        # Example expectations derived from rects rather than hardcoding
        pairs = [('INSIDE_TEMP','INSIDE_RH'), ('OUT_TEMP','OUT_ROW1_L')]
        for a,b in pairs:
            if a in analyses and b in analyses:
                exp = analyses[b].rect[1]-bottom(analyses[a])
                actual = exp  # computed from current rects; placeholder for future golden
                # no-op unless we establish goldens; keep structure
        return issues

    def annotate(self, base_img: np.ndarray, analyses: Dict[str, RegionAnalysis], issues: List[LayoutIssue]) -> Image.Image:
        img = Image.fromarray(base_img).convert('RGBA')
        ov = Image.new('RGBA', img.size, (0,0,0,0))
        draw = ImageDraw.Draw(ov)
        for a in analyses.values():
            x,y,w,h = a.rect
            draw.rectangle([x,y,x+w-1,y+h-1], outline=(128,128,128,255), fill=(128,128,128,64), width=1)
            try:
                font = ImageFont.load_default()
                draw.text((x+2,y+2), a.name, fill=(0,0,0,255), font=font)
            except Exception:
                draw.text((x+2,y+2), a.name, fill=(0,0,0,255))
        for issue in issues:
            color = (255,0,0,128) if issue.severity=='critical' else ((255,165,0,128) if issue.severity=='warning' else (255,255,0,128))
            if issue.coordinates:
                x,y,w,h = issue.coordinates
                draw.rectangle([x,y,x+w-1,y+h-1], outline=color[:3]+(255,), fill=color, width=2)
            else:
                for r in issue.regions:
                    if r in analyses:
                        x,y,w,h = analyses[r].rect
                        draw.rectangle([x,y,x+w-1,y+h-1], outline=color[:3]+(255,), fill=color, width=2)
        return Image.alpha_composite(img, ov).convert('RGB')

    def run(self, variants: Optional[List[str]] = None) -> Dict[str, Dict[str, object]]:
        variants = variants or ['v2_grid']
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
                    issues += self.detect_alignment(analyses, grid4=(variant.startswith('v2')))
                    issues += self.detect_canvas_overflow(analyses)
                    issues += self.detect_empty_blocks(analyses, variant)
                    issues += self.detect_gaps(analyses)
                    annotated = self.annotate(over_img, analyses, issues)
                    # Save artifacts
                    Image.fromarray(base_img).save(self.out_dir / f"layout_analysis_{variant}.png")
                    annotated.save(self.out_dir / f"layout_analysis_{variant}_annotated.png")
                    # Enhanced text report
                    report_txt = self.generate_enhanced_text_report(variant, analyses, issues)
                    (self.out_dir / f"layout_analysis_{variant}_report.txt").write_text(report_txt)
                    results[variant] = {"analyses": analyses, "issues": issues, "text_report": report_txt, "summary": self._generate_variant_summary(analyses, issues)}
                browser.close()
        finally:
            server.terminate(); server.wait(timeout=2)
        return results


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description="Analyze ESP32 eInk display layout")
    ap.add_argument("--variants", nargs="*", default=['v2_grid'])
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
            if isinstance(i, LayoutIssue) and i.severity == 'critical':
                critical += 1
    if critical:
        print(f"Found {critical} critical issues.")
        sys.exit(1)
    print("No critical layout issues detected.")


if __name__ == "__main__":
    main()