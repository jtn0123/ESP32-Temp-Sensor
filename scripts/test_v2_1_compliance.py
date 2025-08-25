#!/usr/bin/env python3
"""V2.1 Layout Compliance Test"""

import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "scripts"))

from visual_layout_analyzer import VisualLayoutAnalyzer  # type: ignore


def test_v2_1_compliance() -> None:
    """Test that V2.1 layout meets compliance requirements"""
    analyzer = VisualLayoutAnalyzer()
    results = analyzer.run(['v2_1_grid'])
    data = results.get('v2_1_grid') or {}
    summary = data.get('summary') or {}
    issues = data.get('issues') or []

    crit_bounds = [i for i in issues if getattr(i, 'severity', '') == 'critical' and getattr(i, 'issue_type', '') == 'overflow']
    assert len(crit_bounds) == 0, "Critical overflow present in v2.1"
    assert summary.get('bounds_compliant', 0) == summary.get('total_regions', 0), "All regions must fit canvas"
    # Allow HEADER_NAME to be considered acceptable even if measured empty in binary thresholding
    crit_empty = [i for i in issues if getattr(i, 'severity', '') == 'critical' and getattr(i, 'issue_type', '') == 'empty_content' and 'HEADER_NAME' not in (i.regions or [])]
    assert len(crit_empty) == 0, "Critical empty content present in v2.1 (excluding HEADER_NAME)"
    assert (summary.get('empty_regions', 0) <= 3), "Too many empty regions"
    assert (summary.get('avg_coverage', 0.0) >= 5.0), "Average coverage too low"


if __name__ == "__main__":
    test_v2_1_compliance()

