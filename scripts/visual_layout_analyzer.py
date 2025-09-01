#!/usr/bin/env python3
"""
Automated Visual Layout Analyzer for ESP32 eInk Display
Uses the web simulator as the single source of truth for validation.
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
from datetime import datetime

# Add project root to path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    import io
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    from playwright.sync_api import sync_playwright
except Exception as e:
    print(f"Missing dependency: {e}")
    print("Install with: pip install numpy pillow playwright")
    sys.exit(1)


@dataclass
class LayoutIssue:
    issue_type: str = ""
    severity: str = ""  # 'critical', 'error', 'warning', 'info'
    regions: List[str] = None
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
    """
    Visual Layout Analyzer that uses the web simulator's validation API.
    The simulator is the single source of truth for all validation logic.
    """
    
    def __init__(self, web_root: Optional[str] = None):
        self.web_root = web_root or str(ROOT / "web" / "sim")
        self.out_dir = ROOT / "out"
        self.out_dir.mkdir(exist_ok=True)

    def _clean_out(self, variants: List[str]) -> None:
        """Remove prior layout_analysis artifacts for the given variants."""
        try:
            for variant in variants:
                patterns = [
                    f"layout_analysis_{variant}.png",
                    f"layout_analysis_{variant}_annotated.png",
                    f"layout_analysis_{variant}_report.txt",
                    f"layout_analysis_{variant}_*.png",
                    f"layout_analysis_{variant}_*_annotated.png",
                    f"layout_analysis_{variant}_*_report.txt",
                ]
                for pat in patterns:
                    for p in self.out_dir.glob(pat):
                        if p.is_file():
                            try:
                                p.unlink()
                            except Exception:
                                pass
        except Exception:
            pass

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

    def _capture_with_sim_validation(self, page, test_data: Dict) -> Tuple[List[LayoutIssue], Optional[Image.Image]]:
        """Capture validation results from the simulator"""
        # Wait for simulator to be ready
        page.wait_for_function("() => window.__simReady === true", timeout=5000)
        
        # Draw test data
        page.evaluate(f"window.draw && window.draw({json.dumps(test_data)})")
        
        # Wait for draw to complete
        page.wait_for_function("() => window.__lastDrawAt > 0", timeout=1000)
        page.wait_for_timeout(100)  # Extra time for rendering
        
        # Get validation results with screenshot
        result = page.evaluate("() => window.exportValidation({ includeScreenshot: true })")
        
        # Convert JS issues to Python LayoutIssue objects
        issues = []
        for js_issue in result.get("issues", []):
            # Preserve simulator-provided severity
            severity = js_issue.get("severity", "info")
            
            issue = LayoutIssue(
                issue_type=js_issue.get("type", "unknown"),
                severity=severity,
                regions=[js_issue.get("region", "unknown")] if js_issue.get("region") else [],
                description=js_issue.get("description", ""),
                coordinates=tuple(js_issue["rect"]) if js_issue.get("rect") else None
            )
            issues.append(issue)
        
        # Decode screenshot if present
        screenshot = None
        if result.get("screenshot"):
            data_url = result["screenshot"]
            if data_url.startswith("data:image/png;base64,"):
                b64_data = data_url.split(",", 1)[1]
                img_bytes = base64.b64decode(b64_data)
                screenshot = Image.open(io.BytesIO(img_bytes))
        
        return issues, screenshot

    def _get_rects_from_page(self, page) -> Dict[str, List[int]]:
        """Get rectangle definitions from the simulator"""
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
        # Fallback to ui_spec.json
        spec = json.loads((ROOT / "config" / "ui_spec.json").read_text())
        return spec.get("rects", {})

    def annotate(
        self, base_img: np.ndarray, analyses: Dict[str, RegionAnalysis], issues: List[LayoutIssue]
    ) -> Image.Image:
        """Annotate image with issue highlights"""
        img = Image.fromarray(base_img).convert("RGBA")
        ov = Image.new("RGBA", img.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(ov)
        
        # Draw region boundaries
        for a in analyses.values():
            x, y, w, h = a.rect
            if w <= 0 or h <= 0:
                continue
            draw.rectangle((x, y, x + w - 1, y + h - 1), outline=(0, 0, 0, 64), width=1)
            try:
                font = ImageFont.load_default()
                draw.text((x + 2, y + 2), a.name, fill=(0, 0, 0, 255), font=font)
            except Exception:
                draw.text((x + 2, y + 2), a.name, fill=(0, 0, 0, 255))
        
        # Draw issues with severity-based colors
        for issue in issues:
            # Colors: critical(red), error(orange), warning(yellow), info(blue)
            if issue.severity == "critical":
                color = (255, 0, 0, 128)
            elif issue.severity == "error":
                color = (255, 136, 0, 128)
            elif issue.severity == "warning":
                color = (255, 187, 0, 128)
            else:
                color = (0, 136, 255, 128)
            
            if issue.coordinates:
                x, y, w, h = issue.coordinates
                if w > 0 and h > 0:
                    draw.rectangle((x, y, x + w - 1, y + h - 1),
                                   outline=color[:3] + (255,), fill=color, width=2)
        
        return Image.alpha_composite(img, ov).convert("RGB")

    def generate_enhanced_text_report(
        self, variant: str, analyses: Dict[str, RegionAnalysis], issues: List[LayoutIssue]
    ) -> str:
        """Generate text report of validation results"""
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        lines: List[str] = [
            f"Visual Layout Analysis - {variant.upper()}",
            "=" * 60,
            f"Generated: {ts}",
            f"Analyzed {len(analyses)} regions",
            f"Found {len(issues)} total issues",
            "",
        ]
        
        # Group issues by severity
        for sev in ("critical", "error", "warning", "info"):
            items = [i for i in issues if i.severity == sev]
            if items:
                icon = {"critical": "🔴", "error": "🟠", "warning": "🟡", "info": "ℹ️"}[sev]
                lines.append(f"{icon} {sev.upper()} ISSUES ({len(items)}):")
                for it in items:
                    lines.append(f"  • {it.description}")
                lines.append("")
        
        return "\n".join(lines)

    def run(self, variants: Optional[List[str]] = None) -> Dict[str, Dict[str, object]]:
        """Run validation analysis on specified variants"""
        variants = variants or ["v2_grid"]
        port = self._find_free_port()
        server = self._start_http_server(self.web_root, port)
        results: Dict[str, Dict[str, object]] = {}
        
        try:
            # Clean previous outputs
            self._clean_out(variants)
            time.sleep(0.4)
            
            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page(viewport={"width": 700, "height": 400})
                
                for variant in variants:
                    # Navigate to simulator with variant
                    page.goto(f"http://127.0.0.1:{port}/index.html?variant={variant}", wait_until="load")
                    page.wait_for_timeout(300)
                    
                    # Prepare test data
                    test_data = {
                        "room_name": "Living Room",
                        "time": "13:45",
                        "version": "v4.2",
                        "inside_temp_f": 72.5,
                        "inside_hum_pct": 47,
                        "pressure_hpa": 1013.2,
                        "outside_temp_f": 68.4,
                        "outside_hum_pct": 53,
                        "outside_pressure_hpa": 1010,
                        "wind_mps": 4.2,
                        "weather": "cloudy",
                        "weather_short": "cloudy",
                        "battery_percent": 76,
                        "battery_voltage": 4.017,
                        "days": 192,
                        "ip": "192.168.1.42"
                    }
                    
                    # Get validation results from simulator
                    issues, screenshot = self._capture_with_sim_validation(page, test_data)
                    
                    # Convert screenshot to numpy array for consistency
                    if screenshot:
                        base_img = np.array(screenshot.convert("RGB"))
                    else:
                        # Fallback: capture canvas directly
                        data_url = page.evaluate(
                            "() => { const c = document.getElementById('epd'); return c ? c.toDataURL('image/png') : null; }"
                        )
                        if data_url and data_url.startswith("data:image/png;base64,"):
                            b64_data = data_url.split(",", 1)[1]
                            img_bytes = base64.b64decode(b64_data)
                            base_img = np.array(Image.open(io.BytesIO(img_bytes)).convert("RGB"))
                        else:
                            base_img = np.zeros((122, 250, 3), dtype=np.uint8)
                    
                    # Get rects for annotation
                    rects = self._get_rects_from_page(page)
                    analyses = {}
                    for name, rect in rects.items():
                        analyses[name] = RegionAnalysis(
                            name=name,
                            rect=(int(rect[0]), int(rect[1]), int(rect[2]), int(rect[3])),
                            category="",
                            pixel_coverage=0.0,
                            content_bounds=None,
                            issues=[]
                        )
                    
                    # Annotate the screenshot with issues
                    if issues:
                        annotated = self.annotate(base_img, analyses, issues)
                    else:
                        annotated = Image.fromarray(base_img)
                    
                    # Save artifacts
                    ts = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
                    base_name = f"layout_analysis_{variant}_{ts}"
                    Image.fromarray(base_img).save(self.out_dir / f"{base_name}.png")
                    annotated.save(self.out_dir / f"{base_name}_annotated.png")
                    
                    # Generate text report
                    report_txt = self.generate_enhanced_text_report(variant, analyses, issues)
                    (self.out_dir / f"{base_name}_report.txt").write_text(report_txt)
                    
                    results[variant] = {
                        "analyses": analyses,
                        "issues": issues,
                        "text_report": report_txt,
                    }
                
                browser.close()
        finally:
            server.terminate()
            server.wait(timeout=2)
        
        return results


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(description="Analyze ESP32 eInk display layout using simulator validation")
    ap.add_argument("--variants", nargs="*", default=["v2_grid"])
    ap.add_argument("--web-root", default=str(ROOT / "web" / "sim"))
    ap.add_argument("--fail-on-critical", action="store_true",
                    help="Exit with non-zero code if critical issues found")
    ap.add_argument("--fail-on-error", action="store_true",
                    help="Exit with non-zero code if error-level issues found")
    args = ap.parse_args()
    
    # Always use simulator validation (no legacy mode)
    analyzer = VisualLayoutAnalyzer(args.web_root)
    results = analyzer.run(args.variants)
    
    # Count issues by severity
    by_severity = {"critical": 0, "error": 0, "warning": 0, "info": 0}
    for v in results.values():
        issues_list_obj = v.get("issues")
        if not isinstance(issues_list_obj, list):
            continue
        for i in issues_list_obj:
            if isinstance(i, LayoutIssue) and i.severity in by_severity:
                by_severity[i.severity] += 1
    
    # Print summary
    print(f"\nSummary: {by_severity['critical']} critical, {by_severity['error']} errors, "
          f"{by_severity['warning']} warnings, {by_severity['info']} info")
    
    # Exit based on flags
    if args.fail_on_critical and by_severity['critical'] > 0:
        print(f"Exiting with error due to {by_severity['critical']} critical issues.")
        sys.exit(1)
    elif args.fail_on_error and by_severity['error'] > 0:
        print(f"Exiting with error due to {by_severity['error']} error-level issues.")
        sys.exit(1)
    elif by_severity['critical'] > 0:
        print(f"Found {by_severity['critical']} critical issues (not failing build).")
    else:
        print("No critical layout issues detected.")


if __name__ == "__main__":
    main()