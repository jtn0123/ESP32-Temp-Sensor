#!/usr/bin/env python3
"""Test V2.1 text layout to ensure no stacking"""

import json
from pathlib import Path

def test_text_layout():
    """Check that text elements don't overlap in v2.1 layout"""
    spec_path = Path(__file__).parent.parent / "config" / "ui_spec.json"
    with open(spec_path) as f:
        spec = json.load(f)
    
    footer_ops = spec['components']['footer_v2_1']
    
    # Track text positions
    text_positions = []
    
    for op in footer_ops:
        if op['op'] == 'text' and 'x' in op and 'y' in op:
            x = op['x']
            y = op['y']
            text = op.get('text', '')
            
            # Estimate text width (rough approximation)
            if '%' in text and 'V' in text:  # Battery percent + voltage
                width = 60
            elif 'IP:' in text:
                width = 50
            elif '~' in text and 'd' in text:  # Days
                width = 30
            elif 'hhmm' in text:  # Time
                width = 35
            elif 'weather' in text.lower():
                width = op.get('maxWidth', 80)
            else:
                width = len(text) * 6  # Rough estimate
            
            text_positions.append({
                'x': x,
                'y': y,
                'width': width,
                'text': text,
                'x_end': x + width
            })
    
    # Check for horizontal overlaps on same line
    print("V2.1 Text Layout Analysis")
    print("=" * 60)
    print("\nText elements in footer:")
    
    for pos in sorted(text_positions, key=lambda p: (p['y'], p['x'])):
        print(f"  y={pos['y']:3}, x={pos['x']:3} to {pos['x_end']:3} : {pos['text']}")
    
    print("\nChecking for overlaps...")
    overlaps = []
    
    for i, pos1 in enumerate(text_positions):
        for pos2 in text_positions[i+1:]:
            # Check if on same line
            if abs(pos1['y'] - pos2['y']) < 2:  # Same line
                # Check for horizontal overlap
                if (pos1['x'] < pos2['x_end'] and pos2['x'] < pos1['x_end']):
                    overlaps.append(f"  '{pos1['text']}' overlaps with '{pos2['text']}'")
    
    if overlaps:
        print("❌ Found text overlaps:")
        for overlap in overlaps:
            print(overlap)
        return False
    else:
        print("✅ No text overlaps detected")
        
    # Check boundaries
    print("\nBoundary checks:")
    FOOTER_L_END = 124  # FOOTER_L ends at x=4+120=124
    FOOTER_R_START = 128  # FOOTER_R starts at x=128
    FOOTER_R_END = 244  # FOOTER_R ends at x=128+116=244
    
    violations = []
    for pos in text_positions:
        if pos['x'] < 128:  # Left footer
            if pos['x_end'] > FOOTER_L_END:
                violations.append(f"  '{pos['text']}' extends beyond FOOTER_L (ends at {pos['x_end']}, max is {FOOTER_L_END})")
        else:  # Right footer
            if pos['x_end'] > FOOTER_R_END:
                violations.append(f"  '{pos['text']}' extends beyond FOOTER_R (ends at {pos['x_end']}, max is {FOOTER_R_END})")
    
    if violations:
        print("⚠️  Boundary violations:")
        for v in violations:
            print(v)
    else:
        print("✅ All text stays within boundaries")
    
    return len(overlaps) == 0 and len(violations) == 0

if __name__ == "__main__":
    success = test_text_layout()
    exit(0 if success else 1)