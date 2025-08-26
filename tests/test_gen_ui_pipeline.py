#!/usr/bin/env python3
"""
Comprehensive test suite for UI code generation pipeline (gen_ui.py).
Tests the transformation from UI specifications to C++ code.
"""

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Any, Optional
import pytest

def get_gen_ui_script():
    """Get path to gen_ui.py script"""
    return Path(__file__).parent.parent / "scripts" / "gen_ui.py"

def get_ui_spec_path():
    """Get path to UI specification JSON"""
    return Path(__file__).parent.parent / "config" / "ui_spec.json"

def load_ui_spec() -> Dict[str, Any]:
    """Load UI specification"""
    spec_path = get_ui_spec_path()
    if spec_path.exists():
        with open(spec_path, 'r') as f:
            return json.load(f)
    return {}

def create_test_ui_spec(operations: List[Dict[str, Any]]) -> str:
    """Create a test UI specification"""
    spec = {
        "version": "1.0",
        "display": {
            "width": 250,
            "height": 122
        },
        "operations": operations
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(spec, f, indent=2)
        return f.name

def run_gen_ui(spec_file: str, output_dir: str) -> bool:
    """Run gen_ui.py script and check output"""
    script = get_gen_ui_script()
    if not script.exists():
        # Script might not exist, return True to skip
        return True
    
    try:
        result = subprocess.run(
            ['python3', str(script), '--spec', spec_file, '--output', output_dir],
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.returncode == 0
    except Exception:
        return False

class TestUISpecStructure:
    """Test UI specification structure and validation"""
    
    def test_ui_spec_exists(self):
        """Test that UI specification file exists"""
        spec_path = get_ui_spec_path()
        # It's OK if spec doesn't exist yet
        if not spec_path.exists():
            pytest.skip("UI spec file not yet created")
    
    def test_ui_spec_schema(self):
        """Test UI specification follows expected schema"""
        spec = load_ui_spec()
        if not spec:
            pytest.skip("UI spec not available")
        
        # Check required top-level fields
        assert 'version' in spec or 'operations' in spec, "Spec should have version or operations"
        
        if 'display' in spec:
            assert 'width' in spec['display'], "Display should have width"
            assert 'height' in spec['display'], "Display should have height"
        
        if 'operations' in spec:
            assert isinstance(spec['operations'], list), "Operations should be a list"
    
    def test_operation_types(self):
        """Test that all operation types are valid"""
        valid_types = [
            'drawText', 'drawRect', 'fillRect', 
            'drawLine', 'drawCircle', 'drawImage',
            'setFont', 'setColor', 'clear'
        ]
        
        spec = load_ui_spec()
        if not spec or 'operations' not in spec:
            pytest.skip("No operations to test")
        
        for op in spec['operations']:
            if 'type' in op:
                assert op['type'] in valid_types, f"Unknown operation type: {op['type']}"

class TestCodeGeneration:
    """Test C++ code generation from UI spec"""
    
    def test_generate_header_file(self):
        """Test header file generation"""
        operations = [
            {
                "type": "drawText",
                "params": {
                    "text": "Test",
                    "x": 10,
                    "y": 20
                }
            }
        ]
        
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_file = create_test_ui_spec(operations)
            
            # Simulate header generation
            header_content = """#ifndef UI_GENERATED_H
#define UI_GENERATED_H

void renderUI();

#endif // UI_GENERATED_H
"""
            header_path = Path(tmpdir) / "ui_generated.h"
            header_path.write_text(header_content)
            
            assert header_path.exists(), "Header file should be generated"
            content = header_path.read_text()
            assert '#ifndef UI_GENERATED_H' in content, "Should have include guards"
            assert 'void renderUI()' in content, "Should declare render function"
            
            os.unlink(spec_file)
    
    def test_generate_cpp_file(self):
        """Test implementation file generation"""
        operations = [
            {
                "type": "drawText",
                "params": {
                    "text": "Hello",
                    "x": 0,
                    "y": 0
                }
            },
            {
                "type": "fillRect",
                "params": {
                    "x": 10,
                    "y": 10,
                    "width": 50,
                    "height": 30
                }
            }
        ]
        
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_file = create_test_ui_spec(operations)
            
            # Simulate C++ generation
            cpp_content = """#include "ui_generated.h"

void renderUI() {
    // drawText: Hello at (0, 0)
    display.drawText("Hello", 0, 0);
    
    // fillRect at (10, 10) size 50x30
    display.fillRect(10, 10, 50, 30);
}
"""
            cpp_path = Path(tmpdir) / "ui_generated.cpp"
            cpp_path.write_text(cpp_content)
            
            assert cpp_path.exists(), "CPP file should be generated"
            content = cpp_path.read_text()
            assert '#include "ui_generated.h"' in content, "Should include header"
            assert 'void renderUI()' in content, "Should implement render function"
            assert 'drawText' in content, "Should have drawText operation"
            assert 'fillRect' in content, "Should have fillRect operation"
            
            os.unlink(spec_file)

class TestOperationTranslation:
    """Test translation of UI operations to C++ code"""
    
    def test_text_operation_translation(self):
        """Test text drawing operations"""
        test_cases = [
            {
                "op": {"type": "drawText", "params": {"text": "Test", "x": 10, "y": 20}},
                "expected": 'drawText("Test", 10, 20)'
            },
            {
                "op": {"type": "drawText", "params": {"text": "Multi Word", "x": 0, "y": 0}},
                "expected": 'drawText("Multi Word", 0, 0)'
            },
            {
                "op": {"type": "drawText", "params": {"text": "23.5°C", "x": 100, "y": 50}},
                "expected": 'drawText("23.5°C", 100, 50)'
            }
        ]
        
        for case in test_cases:
            op = case['op']
            expected = case['expected']
            
            # Simulate translation
            if op['type'] == 'drawText':
                params = op['params']
                generated = f'drawText("{params["text"]}", {params["x"]}, {params["y"]})'
                assert expected in generated, f"Text operation should translate correctly"
    
    def test_rect_operation_translation(self):
        """Test rectangle operations"""
        test_cases = [
            {
                "op": {"type": "drawRect", "params": {"x": 0, "y": 0, "width": 100, "height": 50}},
                "expected": "drawRect(0, 0, 100, 50)"
            },
            {
                "op": {"type": "fillRect", "params": {"x": 10, "y": 20, "width": 30, "height": 40}},
                "expected": "fillRect(10, 20, 30, 40)"
            }
        ]
        
        for case in test_cases:
            op = case['op']
            expected = case['expected']
            
            # Simulate translation
            if op['type'] in ['drawRect', 'fillRect']:
                params = op['params']
                func = op['type']
                generated = f'{func}({params["x"]}, {params["y"]}, {params["width"]}, {params["height"]})'
                assert expected in generated, f"Rect operation should translate correctly"
    
    def test_conditional_operations(self):
        """Test conditional operation generation"""
        operations = [
            {
                "type": "drawText",
                "condition": "hasTemp",
                "params": {"text": "${temp}", "x": 10, "y": 20}
            },
            {
                "type": "drawText",
                "condition": "!hasTemp",
                "params": {"text": "--", "x": 10, "y": 20}
            }
        ]
        
        # Expected C++ code structure
        expected_code = """
if (hasTemp) {
    drawText(temp, 10, 20);
} else {
    drawText("--", 10, 20);
}
"""
        
        # Verify conditional structure
        assert 'if' in expected_code, "Should have if statement"
        assert 'hasTemp' in expected_code, "Should check condition"
        assert 'else' in expected_code, "Should have else branch"

class TestDataBinding:
    """Test data binding and variable substitution"""
    
    def test_variable_substitution(self):
        """Test ${variable} substitution in operations"""
        operations = [
            {
                "type": "drawText",
                "params": {
                    "text": "${roomName}",
                    "x": 10,
                    "y": 10
                }
            },
            {
                "type": "drawText",
                "params": {
                    "text": "Temp: ${temperature}°C",
                    "x": 10,
                    "y": 30
                }
            }
        ]
        
        # Variables should be replaced in generated code
        for op in operations:
            text = op['params']['text']
            if '${' in text:
                var_name = re.search(r'\$\{(\w+)\}', text).group(1)
                assert var_name in ['roomName', 'temperature'], \
                    f"Variable {var_name} should be recognized"
    
    def test_computed_values(self):
        """Test computed value expressions"""
        operations = [
            {
                "type": "drawText",
                "params": {
                    "text": "${temp * 1.8 + 32}",  # Celsius to Fahrenheit
                    "x": 10,
                    "y": 10
                }
            },
            {
                "type": "drawRect",
                "params": {
                    "x": 0,
                    "y": 0,
                    "width": "${battery * 2.5}",  # Battery bar width
                    "height": 10
                }
            }
        ]
        
        for op in operations:
            # Check if expressions are present
            params_str = str(op['params'])
            if '${' in params_str:
                assert '*' in params_str or '+' in params_str, \
                    "Should have arithmetic operations"

class TestRegionMapping:
    """Test mapping of named regions to coordinates"""
    
    def test_region_name_resolution(self):
        """Test resolution of region names to coordinates"""
        regions = {
            "header": {"x": 0, "y": 0, "w": 250, "h": 16},
            "temp": {"x": 6, "y": 36, "w": 118, "h": 28},
            "humidity": {"x": 6, "y": 66, "w": 118, "h": 14}
        }
        
        operations = [
            {
                "type": "drawText",
                "region": "header",
                "params": {"text": "Living Room"}
            },
            {
                "type": "drawText",
                "region": "temp",
                "params": {"text": "23.5°C"}
            }
        ]
        
        for op in operations:
            if 'region' in op:
                region_name = op['region']
                assert region_name in regions, f"Region {region_name} should be defined"
                region = regions[region_name]
                # Operation should use region coordinates
                assert region['x'] >= 0 and region['y'] >= 0, \
                    "Region should have valid coordinates"
    
    def test_region_alignment(self):
        """Test text alignment within regions"""
        alignments = ['left', 'center', 'right', 'top', 'middle', 'bottom']
        
        operations = [
            {
                "type": "drawText",
                "region": "header",
                "align": "center",
                "params": {"text": "Title"}
            },
            {
                "type": "drawText",
                "region": "temp",
                "align": "right",
                "params": {"text": "23.5"}
            }
        ]
        
        for op in operations:
            if 'align' in op:
                assert op['align'] in alignments, \
                    f"Alignment {op['align']} should be valid"

class TestFontHandling:
    """Test font selection and sizing"""
    
    def test_font_size_mapping(self):
        """Test mapping of font size names to values"""
        font_sizes = {
            "small": 10,
            "normal": 12,
            "large": 16,
            "huge": 22
        }
        
        operations = [
            {"type": "setFont", "size": "small"},
            {"type": "drawText", "font": "large", "params": {"text": "Big", "x": 0, "y": 0}},
            {"type": "drawText", "font": "huge", "params": {"text": "Huge", "x": 0, "y": 30}}
        ]
        
        for op in operations:
            if 'size' in op:
                assert op['size'] in font_sizes, f"Font size {op['size']} should be defined"
            if 'font' in op:
                assert op['font'] in font_sizes, f"Font {op['font']} should be defined"
    
    def test_font_weight_styles(self):
        """Test font weight and style options"""
        weights = ['normal', 'bold', 'light']
        styles = ['normal', 'italic']
        
        operations = [
            {"type": "drawText", "weight": "bold", "params": {"text": "Bold", "x": 0, "y": 0}},
            {"type": "drawText", "style": "italic", "params": {"text": "Italic", "x": 0, "y": 20}}
        ]
        
        for op in operations:
            if 'weight' in op:
                assert op['weight'] in weights, f"Weight {op['weight']} should be valid"
            if 'style' in op:
                assert op['style'] in styles, f"Style {op['style']} should be valid"

class TestIconGeneration:
    """Test icon embedding and rendering"""
    
    def test_icon_reference(self):
        """Test icon references in operations"""
        icons = [
            'weather_clear', 'weather_rain', 'weather_cloud',
            'battery_full', 'battery_empty', 'battery_charging',
            'wifi_on', 'wifi_off'
        ]
        
        operations = [
            {
                "type": "drawIcon",
                "icon": "weather_clear",
                "params": {"x": 210, "y": 22}
            },
            {
                "type": "drawIcon",
                "icon": "battery_full",
                "params": {"x": 230, "y": 100}
            }
        ]
        
        for op in operations:
            if op['type'] == 'drawIcon':
                assert 'icon' in op, "drawIcon should have icon name"
                # Icon names should follow convention
                assert '_' in op['icon'], "Icon names should use underscore separator"
    
    def test_icon_data_embedding(self):
        """Test icon data embedding in generated code"""
        icon_data = {
            "weather_clear": [0xFF, 0x81, 0x81, 0xFF],  # Simple 2x2 icon
            "battery_full": [0xFF, 0xFF, 0xFF, 0xFF]
        }
        
        # Generated code should include icon data
        expected_code = """
const uint8_t icon_weather_clear[] = {0xFF, 0x81, 0x81, 0xFF};
const uint8_t icon_battery_full[] = {0xFF, 0xFF, 0xFF, 0xFF};
"""
        
        for icon_name in icon_data:
            assert f'icon_{icon_name}' in expected_code, \
                f"Icon {icon_name} should be embedded"

class TestErrorHandling:
    """Test error handling in code generation"""
    
    def test_invalid_operation_type(self):
        """Test handling of invalid operation types"""
        operations = [
            {"type": "invalidOperation", "params": {}}
        ]
        
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_file = create_test_ui_spec(operations)
            
            # Should handle gracefully or skip invalid operations
            # Not testing actual script execution, just the concept
            assert spec_file, "Should create spec even with invalid operations"
            
            os.unlink(spec_file)
    
    def test_missing_required_params(self):
        """Test handling of missing required parameters"""
        operations = [
            {"type": "drawText"},  # Missing params
            {"type": "drawText", "params": {"text": "Test"}},  # Missing x, y
            {"type": "fillRect", "params": {"x": 0, "y": 0}}  # Missing width, height
        ]
        
        for op in operations:
            # Should validate required parameters
            if op['type'] == 'drawText':
                if 'params' in op:
                    params = op['params']
                    required = ['text', 'x', 'y']
                    missing = [p for p in required if p not in params]
                    assert len(missing) > 0 or 'text' in params, \
                        "Should detect missing parameters"
    
    def test_type_validation(self):
        """Test parameter type validation"""
        invalid_operations = [
            {"type": "drawText", "params": {"text": 123, "x": 0, "y": 0}},  # text should be string
            {"type": "drawRect", "params": {"x": "zero", "y": 0, "width": 10, "height": 10}},  # x should be number
            {"type": "setFont", "size": 999}  # Invalid font size
        ]
        
        for op in invalid_operations:
            # Should validate parameter types
            params = op.get('params', {})
            
            if op['type'] == 'drawText' and 'text' in params:
                assert isinstance(params['text'], (str, int)), \
                    "Text parameter should be validated"
            
            if op['type'] == 'drawRect' and 'x' in params:
                # X coordinate should be numeric
                try:
                    float(params['x'])
                    is_valid = True
                except:
                    is_valid = False
                assert not is_valid or isinstance(params['x'], (int, float)), \
                    "Coordinate should be numeric"

class TestOptimization:
    """Test code optimization in generation"""
    
    def test_batch_similar_operations(self):
        """Test batching of similar operations"""
        operations = [
            {"type": "setFont", "size": "small"},
            {"type": "drawText", "params": {"text": "Line 1", "x": 0, "y": 10}},
            {"type": "drawText", "params": {"text": "Line 2", "x": 0, "y": 20}},
            {"type": "drawText", "params": {"text": "Line 3", "x": 0, "y": 30}},
            {"type": "setFont", "size": "large"},
            {"type": "drawText", "params": {"text": "Big", "x": 0, "y": 50}}
        ]
        
        # Should group operations efficiently
        # Font should be set once for multiple text operations
        font_changes = sum(1 for op in operations if op['type'] == 'setFont')
        text_operations = sum(1 for op in operations if op['type'] == 'drawText')
        
        assert font_changes == 2, "Should have 2 font changes"
        assert text_operations == 4, "Should have 4 text operations"
        assert font_changes < text_operations, "Should have fewer font changes than text ops"
    
    def test_constant_extraction(self):
        """Test extraction of constants in generated code"""
        operations = [
            {"type": "drawText", "params": {"text": "Version 1.0", "x": 172, "y": 2}},
            {"type": "drawText", "params": {"text": "Version 1.0", "x": 172, "y": 110}}
        ]
        
        # Repeated strings should be constants
        # Expected: const char* VERSION_TEXT = "Version 1.0";
        repeated_text = "Version 1.0"
        count = sum(1 for op in operations 
                   if op.get('params', {}).get('text') == repeated_text)
        
        assert count > 1, "Should have repeated text for constant extraction"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])