#!/usr/bin/env python3
"""Test V2.1 layout compliance and visual analyzer integration"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def test_v2_1_layout_compliance():
    """Test that V2.1 layout meets all compliance requirements"""
    from visual_layout_analyzer import VisualLayoutAnalyzer
    
    analyzer = VisualLayoutAnalyzer()
    results = analyzer.run(['v2_1_grid'])
    
    data = results.get('v2_1_grid') or {}
    summary = data.get('summary') or {}
    issues = data.get('issues') or []
    
    # Check for critical overflow issues
    crit_bounds = [i for i in issues if getattr(i, 'severity', '') == 'critical' and getattr(i, 'issue_type', '') == 'overflow']
    assert len(crit_bounds) == 0, f"Critical overflow present in v2.1: {[i.description for i in crit_bounds]}"
    
    # All regions must fit within canvas
    assert summary.get('bounds_compliant', 0) == summary.get('total_regions', 0), \
        f"Not all regions fit canvas: {summary.get('bounds_compliant')}/{summary.get('total_regions')}"
    
    # Check for critical empty content (excluding HEADER_NAME which may appear empty in binary thresholding)
    crit_empty = [i for i in issues if getattr(i, 'severity', '') == 'critical' 
                  and getattr(i, 'issue_type', '') == 'empty_content' 
                  and 'HEADER_NAME' not in (getattr(i, 'regions', []) or [])]
    assert len(crit_empty) == 0, f"Critical empty content in v2.1: {[i.description for i in crit_empty]}"
    
    # Reasonable number of empty regions
    assert summary.get('empty_regions', 0) <= 5, \
        f"Too many empty regions: {summary.get('empty_regions')}"
    
    # Minimum average coverage
    assert summary.get('avg_coverage', 0.0) >= 3.0, \
        f"Average coverage too low: {summary.get('avg_coverage', 0.0):.1f}%"


def test_v2_1_grid_alignment():
    """Test that V2.1 layout follows 4px grid alignment"""
    import json
    
    spec_path = ROOT / "config" / "ui_spec.json"
    with open(spec_path) as f:
        spec = json.load(f)
    
    rects = spec.get('rects_v2_1', {})
    
    misaligned = []
    for name, rect in rects.items():
        x, y, w, h = rect
        issues = []
        if x % 4 != 0:
            issues.append(f"x={x}")
        if y % 4 != 0:
            issues.append(f"y={y}")
        if w % 4 != 0:
            issues.append(f"w={w}")
        if h % 4 != 0:
            issues.append(f"h={h}")
        
        if issues:
            misaligned.append(f"{name}: {', '.join(issues)}")
    
    assert len(misaligned) == 0, f"Regions not aligned to 4px grid:\n" + "\n".join(misaligned)


def test_v2_1_hierarchy_structure():
    """Test that V2.1 maintains proper hierarchical structure"""
    import json
    
    spec_path = ROOT / "config" / "ui_spec.json"
    with open(spec_path) as f:
        spec = json.load(f)
    
    rects = spec.get('rects_v2_1', {})
    
    # Check temperature display hierarchy
    for side in ['INSIDE', 'OUT']:
        parent = f"{side}_TEMP"
        label_box = f"{side}_LABEL_BOX"
        inner = f"{side}_TEMP_INNER"
        badge = f"{side}_TEMP_BADGE"
        
        assert parent in rects, f"Missing parent region {parent}"
        assert label_box in rects, f"Missing label box {label_box}"
        assert inner in rects, f"Missing inner region {inner}"
        assert badge in rects, f"Missing badge region {badge}"
        
        # Label should be within parent
        p_rect = rects[parent]
        l_rect = rects[label_box]
        assert l_rect[0] >= p_rect[0], f"{label_box} extends left of {parent}"
        assert l_rect[1] >= p_rect[1], f"{label_box} extends above {parent}"
        assert l_rect[0] + l_rect[2] <= p_rect[0] + p_rect[2], f"{label_box} extends right of {parent}"
        assert l_rect[1] + l_rect[3] <= p_rect[1] + p_rect[3], f"{label_box} extends below {parent}"
        
        # Inner and badge should be horizontally aligned
        i_rect = rects[inner]
        b_rect = rects[badge]
        assert i_rect[1] == b_rect[1], f"{inner} and {badge} not horizontally aligned: {i_rect[1]} vs {b_rect[1]}"


def test_v2_1_footer_boundaries():
    """Test that V2.1 footer elements stay within boundaries"""
    import json
    
    spec_path = ROOT / "config" / "ui_spec.json"
    with open(spec_path) as f:
        spec = json.load(f)
    
    rects = spec.get('rects_v2_1', {})
    components = spec.get('components', {})
    footer_ops = components.get('footer_v2_1', [])
    
    CANVAS_WIDTH = 250
    CANVAS_HEIGHT = 122
    
    # Check STATUS bar
    status = rects.get('STATUS', [0, 0, 0, 0])
    assert status[1] + status[3] <= CANVAS_HEIGHT, \
        f"STATUS bar extends below canvas: {status[1]} + {status[3]} = {status[1] + status[3]} > {CANVAS_HEIGHT}"
    
    # Check footer text positions
    for op in footer_ops:
        if op.get('op') == 'text' and 'x' in op and 'y' in op:
            x = op['x']
            y = op['y']
            text = op.get('text', '')
            
            # Basic boundary check
            assert x >= 0, f"Text '{text}' has negative x: {x}"
            assert y >= 0, f"Text '{text}' has negative y: {y}"
            assert x < CANVAS_WIDTH, f"Text '{text}' starts beyond canvas: {x}"
            assert y < CANVAS_HEIGHT - 10, f"Text '{text}' too close to bottom: {y}"
            
            # Check if text with maxWidth stays within bounds
            if 'maxWidth' in op:
                assert x + op['maxWidth'] <= CANVAS_WIDTH, \
                    f"Text '{text}' with maxWidth extends beyond canvas: {x} + {op['maxWidth']} > {CANVAS_WIDTH}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])