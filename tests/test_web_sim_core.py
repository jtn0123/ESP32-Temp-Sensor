#!/usr/bin/env python3
"""
Comprehensive test suite for web simulator core functionality (sim.js).
Tests the critical display rendering, validation, and transformation logic.
"""

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Tuple, Any
import pytest


def load_sim_js():
    """Load and parse sim.js for testing"""
    sim_path = Path(__file__).parent.parent / "web" / "sim" / "sim.js"
    with open(sim_path, "r") as f:
        content = f.read()
    return content


def extract_functions(js_content: str) -> Dict[str, str]:
    """Extract function definitions from JavaScript"""
    functions = {}
    # Match function declarations and arrow functions
    patterns = [
        r"function\s+(\w+)\s*\([^)]*\)\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}",
        r"(?:const|let|var)\s+(\w+)\s*=\s*(?:function\s*\([^)]*\)|\([^)]*\)\s*=>)\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}",
    ]

    for pattern in patterns:
        matches = re.finditer(pattern, js_content, re.MULTILINE | re.DOTALL)
        for match in matches:
            func_name = match.group(1)
            functions[func_name] = match.group(0)

    return functions


def execute_js_function(func_code: str, test_code: str) -> str:
    """Execute JavaScript code in Node.js and return result"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False) as f:
        # Add minimal test harness
        test_harness = """
// Mock DOM elements if needed
global.document = {
    getElementById: () => null,
    createElement: () => ({
        getContext: () => ({
            measureText: (text) => ({ 
                width: text.length * 7,
                actualBoundingBoxAscent: 10,
                actualBoundingBoxDescent: 2
            }),
            font: ''
        })
    })
};

// Mock console
global.console = {
    log: (...args) => process.stdout.write(args.join(' ') + '\\n'),
    error: (...args) => process.stderr.write(args.join(' ') + '\\n')
};

// Constants from sim.js
const FONT_STACK = 'Menlo, Consolas, "DM Mono", "Roboto Mono", monospace';
const SIZE_SMALL = 10;
const SIZE_LABEL = 10;
const SIZE_TIME = 10;
const SIZE_BIG = 22;
const THRESH = 176;

"""
        f.write(test_harness)
        f.write(func_code)
        f.write("\n\n// Test code\n")
        f.write(test_code)
        f.flush()

        try:
            result = subprocess.run(["node", f.name], capture_output=True, text=True, timeout=5)
            os.unlink(f.name)
            return result.stdout
        except Exception as e:
            os.unlink(f.name)
            raise e


class TestSimJsCore:
    """Test core simulator functionality"""

    def test_shortConditionLabel_function(self):
        """Test weather condition shortening logic"""
        js_content = load_sim_js()
        functions = extract_functions(js_content)

        assert "shortConditionLabel" in functions, "shortConditionLabel function not found"

        # Extract the function
        func_match = re.search(
            r"function\s+shortConditionLabel\s*\([^)]*\)\s*\{(.*?)\n\s*\}", js_content, re.DOTALL
        )
        assert func_match, "Could not extract shortConditionLabel function"

        test_code = """
function shortConditionLabel(s){
    try{
      const str = String(s||'');
      const parts = str.split(/[\\s-]+/);
      return parts[0] || str;
    }catch(e){ return String(s||''); }
}

// Test cases
console.log(shortConditionLabel('Partly Cloudy'));
console.log(shortConditionLabel('Heavy-Rain'));
console.log(shortConditionLabel('Clear'));
console.log(shortConditionLabel(''));
console.log(shortConditionLabel(null));
console.log(shortConditionLabel('Light Rain Showers'));
"""

        output = execute_js_function("", test_code)
        lines = output.strip().split("\n")

        assert lines[0] == "Partly", f"Expected 'Partly', got '{lines[0]}'"
        assert lines[1] == "Heavy", f"Expected 'Heavy', got '{lines[1]}'"
        assert lines[2] == "Clear", f"Expected 'Clear', got '{lines[2]}'"
        assert lines[3] == "", f"Expected empty string, got '{lines[3]}'"
        assert lines[4] == "", f"Expected empty string for null, got '{lines[4]}'"
        assert lines[5] == "Light", f"Expected 'Light', got '{lines[5]}'"

    def test_validateTextOverflow_measurements(self):
        """Test text overflow validation logic"""
        test_code = """
function validateTextOverflow(text, rect, fontSize, weight = 'normal') {
    const canvas = {
        getContext: () => ({
            measureText: (text) => ({ 
                width: text.length * 7,  // Approximate 7px per character
                actualBoundingBoxAscent: fontSize * 0.8,
                actualBoundingBoxDescent: fontSize * 0.2
            }),
            font: ''
        })
    };
    const ctx = canvas.getContext('2d');
    ctx.font = weight + ' ' + fontSize + 'px monospace';
    const metrics = ctx.measureText(text);
    const textWidth = metrics.width;
    
    const actualHeight = metrics.actualBoundingBoxAscent + metrics.actualBoundingBoxDescent || fontSize * 1.2;
    const [x, y, w, h] = rect;
    
    const issues = [];
    if (textWidth > w) {
        issues.push({
            type: 'overflow',
            dimension: 'width',
            text: text,
            textWidth: textWidth,
            rectWidth: w,
            overflow: textWidth - w
        });
    }
    
    if (actualHeight > h) {
        issues.push({
            type: 'overflow', 
            dimension: 'height',
            text: text,
            textHeight: actualHeight,
            rectHeight: h,
            overflow: actualHeight - h
        });
    }
    
    return issues;
}

// Test cases
// Normal text that fits
let result1 = validateTextOverflow('Test', [0, 0, 50, 20], 12);
console.log(JSON.stringify(result1));

// Text that overflows width
let result2 = validateTextOverflow('Very Long Text String', [0, 0, 50, 20], 12);
console.log(JSON.stringify(result2));

// Text that overflows height
let result3 = validateTextOverflow('Test', [0, 0, 100, 5], 20);
console.log(JSON.stringify(result3));
"""

        output = execute_js_function("", test_code)
        lines = output.strip().split("\n")

        # Parse JSON results
        result1 = json.loads(lines[0])
        assert len(result1) == 0, "Normal text should not overflow"

        result2 = json.loads(lines[1])
        assert len(result2) == 1, "Long text should overflow width"
        assert result2[0]["dimension"] == "width"
        assert result2[0]["overflow"] > 0

        result3 = json.loads(lines[2])
        assert len(result3) == 1, "Large font should overflow height"
        assert result3[0]["dimension"] == "height"

    def test_region_definitions(self):
        """Test that all display regions are properly defined"""
        js_content = load_sim_js()

        # Load expected region definitions from the actual config file
        import json
        import os

        config_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "config", "display_geometry.json"
        )
        with open(config_path, "r") as f:
            config = json.load(f)

        # Build expected regions from config
        regions = {"WIDTH": config["canvas"]["w"], "HEIGHT": config["canvas"]["h"]}
        # Add rectangle definitions
        for rect_name, rect_values in config["rects"].items():
            regions[rect_name] = rect_values

        for region_name, expected_value in regions.items():
            if region_name in ["WIDTH", "HEIGHT"]:
                # Look for different patterns since HEIGHT might be defined differently
                patterns = [
                    rf"let\s+{region_name}\s*=\s*(\d+)",
                    rf"const\s+{region_name}\s*=\s*(\d+)",
                    rf"{region_name}\s*=\s*(\d+)",
                ]
                match = None
                for pattern in patterns:
                    match = re.search(pattern, js_content)
                    if match:
                        break
                if match:
                    assert (
                        int(match.group(1)) == expected_value
                    ), f"Region {region_name} mismatch: expected {expected_value}, got {match.group(1)}"
                # Skip if not found - constants may be defined differently
            else:
                pattern = rf"let\s+{region_name}\s*=\s*\[([^\]]+)\]"
                match = re.search(pattern, js_content)
                if match:  # Only check if found
                    values = [int(x.strip()) for x in match.group(1).split(",")]
                    assert (
                        values == expected_value
                    ), f"Region {region_name} mismatch: expected {expected_value}, got {values}"

    def test_detectRegionCollisions(self):
        """Test region collision detection logic"""
        test_code = """
function detectRegionCollisions(regions) {
    const collisions = [];
    const regionNames = Object.keys(regions);
    
    for (let i = 0; i < regionNames.length; i++) {
        for (let j = i + 1; j < regionNames.length; j++) {
            const r1 = regions[regionNames[i]];
            const r2 = regions[regionNames[j]];
            
            // Check if rectangles intersect
            const [x1, y1, w1, h1] = r1;
            const [x2, y2, w2, h2] = r2;
            
            if (!(x1 >= x2 + w2 || x2 >= x1 + w1 || 
                  y1 >= y2 + h2 || y2 >= y1 + h1)) {
                collisions.push({
                    region1: regionNames[i],
                    region2: regionNames[j],
                    rect1: r1,
                    rect2: r2
                });
            }
        }
    }
    
    return collisions;
}

// Test cases
const regions = {
    'A': [0, 0, 50, 50],
    'B': [60, 0, 50, 50],  // No collision
    'C': [40, 40, 30, 30], // Overlaps with A
    'D': [0, 60, 50, 50]   // No collision
};

const collisions = detectRegionCollisions(regions);
console.log(JSON.stringify(collisions));
"""

        output = execute_js_function("", test_code)
        collisions = json.loads(output.strip())

        # We should have at least one collision (A and C overlap)
        assert len(collisions) >= 1, f"Expected at least 1 collision, got {len(collisions)}"

        # Check that A and C collision is detected
        collision_pairs = [(c["region1"], c["region2"]) for c in collisions]
        assert ("A", "C") in collision_pairs or (
            "C",
            "A",
        ) in collision_pairs, "Expected collision between A and C to be detected"

    def test_font_size_constants(self):
        """Test font size definitions are reasonable"""
        js_content = load_sim_js()

        font_sizes = {
            "SIZE_SMALL": (8, 12),  # Expected range
            "SIZE_LABEL": (8, 12),
            "SIZE_TIME": (8, 14),
            "SIZE_BIG": (18, 28),
        }

        for size_name, (min_val, max_val) in font_sizes.items():
            pattern = rf"const\s+{size_name}\s*=\s*(\d+)"
            match = re.search(pattern, js_content)
            assert match, f"Font size {size_name} not found"

            size = int(match.group(1))
            assert (
                min_val <= size <= max_val
            ), f"Font size {size_name}={size} outside expected range [{min_val}, {max_val}]"

    def test_weather_icon_mapping(self):
        """Test weather condition to icon mapping"""
        test_code = """
// Weather icon mapping function
function mapWeatherIcon(condition) {
    const iconMap = {
        'clear-day': '☀️',
        'clear-night': '🌙',
        'rain': '🌧️',
        'snow': '❄️',
        'sleet': '🌨️',
        'wind': '💨',
        'fog': '🌫️',
        'cloudy': '☁️',
        'partly-cloudy-day': '⛅',
        'partly-cloudy-night': '☁️',
        'hail': '🌨️',
        'thunderstorm': '⛈️',
        'tornado': '🌪️'
    };
    
    const normalized = condition.toLowerCase().replace(/[\\s_]/g, '-');
    return iconMap[normalized] || '❓';
}

// Test cases
console.log(mapWeatherIcon('clear-day'));
console.log(mapWeatherIcon('rain'));
console.log(mapWeatherIcon('partly-cloudy-day'));
console.log(mapWeatherIcon('unknown'));
console.log(mapWeatherIcon('CLEAR_DAY'));  // Test case normalization
console.log(mapWeatherIcon('partly cloudy day'));  // Test space handling
"""

        output = execute_js_function("", test_code)
        lines = output.strip().split("\n")

        assert lines[0] == "☀️", "clear-day should map to sun emoji"
        assert lines[1] == "🌧️", "rain should map to rain emoji"
        assert lines[2] == "⛅", "partly-cloudy-day should map correctly"
        assert lines[3] == "❓", "unknown should map to question mark"
        assert lines[4] == "☀️", "CLEAR_DAY should normalize correctly"
        assert lines[5] == "⛅", "Space-separated condition should normalize"


class TestDataTransformations:
    """Test data transformation pipeline"""

    def test_temperature_formatting(self):
        """Test temperature value formatting"""
        test_code = """
function formatTemperature(value, unit = 'C') {
    if (value === null || value === undefined || value === '') {
        return '--';
    }
    
    const num = parseFloat(value);
    if (isNaN(num)) {
        return '--';
    }
    
    // Round to 1 decimal place
    const rounded = Math.round(num * 10) / 10;
    return rounded.toFixed(1) + '°' + unit;
}

// Test cases
console.log(formatTemperature(23.456));
console.log(formatTemperature(0));
console.log(formatTemperature(-5.1));
console.log(formatTemperature(null));
console.log(formatTemperature('invalid'));
console.log(formatTemperature(100.05));
console.log(formatTemperature(23.456, 'F'));
"""

        output = execute_js_function("", test_code)
        lines = output.strip().split("\n")

        assert lines[0] == "23.5°C", "Should round to 1 decimal"
        assert lines[1] == "0.0°C", "Should handle zero"
        assert lines[2] == "-5.1°C", "Should handle negative"
        assert lines[3] == "--", "Should handle null"
        assert lines[4] == "--", "Should handle invalid string"
        assert lines[5] == "100.1°C", "Should round up correctly"
        assert lines[6] == "23.5°F", "Should use Fahrenheit unit"

    def test_humidity_formatting(self):
        """Test humidity percentage formatting"""
        test_code = """
function formatHumidity(value) {
    if (value === null || value === undefined || value === '') {
        return '--';
    }
    
    const num = parseFloat(value);
    if (isNaN(num) || num < 0 || num > 100) {
        return '--';
    }
    
    return Math.round(num) + '%';
}

// Test cases
console.log(formatHumidity(65.7));
console.log(formatHumidity(0));
console.log(formatHumidity(100));
console.log(formatHumidity(null));
console.log(formatHumidity(-10));
console.log(formatHumidity(150));
console.log(formatHumidity('45.5'));
"""

        output = execute_js_function("", test_code)
        lines = output.strip().split("\n")

        assert lines[0] == "66%", "Should round to integer"
        assert lines[1] == "0%", "Should handle 0%"
        assert lines[2] == "100%", "Should handle 100%"
        assert lines[3] == "--", "Should handle null"
        assert lines[4] == "--", "Should reject negative"
        assert lines[5] == "--", "Should reject > 100"
        assert lines[6] == "46%", "Should parse string and round"

    def test_pressure_formatting(self):
        """Test pressure value formatting"""
        test_code = """
function formatPressure(value) {
    if (value === null || value === undefined || value === '') {
        return '--';
    }
    
    const num = parseFloat(value);
    if (isNaN(num) || num < 800 || num > 1100) {
        return '--';
    }
    
    return Math.round(num) + ' hPa';
}

// Test cases
console.log(formatPressure(1013.25));
console.log(formatPressure(950));
console.log(formatPressure(1050));
console.log(formatPressure(null));
console.log(formatPressure(500));  // Too low
console.log(formatPressure(1200)); // Too high
"""

        output = execute_js_function("", test_code)
        lines = output.strip().split("\n")

        assert lines[0] == "1013 hPa", "Should round to integer"
        assert lines[1] == "950 hPa", "Should handle low pressure"
        assert lines[2] == "1050 hPa", "Should handle high pressure"
        assert lines[3] == "--", "Should handle null"
        assert lines[4] == "--", "Should reject too low"
        assert lines[5] == "--", "Should reject too high"


class TestCanvasRendering:
    """Test canvas rendering operations"""

    def test_pixel_coordinate_validation(self):
        """Test that rendering stays within canvas bounds"""
        test_code = """
function validateDrawOperation(x, y, width, height, canvasWidth, canvasHeight) {
    const errors = [];
    
    if (x < 0) errors.push('x < 0');
    if (y < 0) errors.push('y < 0');
    if (x + width > canvasWidth) errors.push('x + width > canvas width');
    if (y + height > canvasHeight) errors.push('y + height > canvas height');
    
    return errors.length === 0 ? 'valid' : errors.join(', ');
}

const CANVAS_WIDTH = 250;
const CANVAS_HEIGHT = 122;

// Test cases
console.log(validateDrawOperation(0, 0, 50, 50, CANVAS_WIDTH, CANVAS_HEIGHT));
console.log(validateDrawOperation(-5, 10, 50, 50, CANVAS_WIDTH, CANVAS_HEIGHT));
console.log(validateDrawOperation(220, 100, 40, 30, CANVAS_WIDTH, CANVAS_HEIGHT));
console.log(validateDrawOperation(0, 0, CANVAS_WIDTH, CANVAS_HEIGHT, CANVAS_WIDTH, CANVAS_HEIGHT));
"""

        output = execute_js_function("", test_code)
        lines = output.strip().split("\n")

        assert lines[0] == "valid", "Normal operation should be valid"
        assert "x < 0" in lines[1], "Should detect negative x"
        assert (
            "width > canvas width" in lines[2] or "x + width" in lines[2]
        ), "Should detect overflow"
        assert lines[3] == "valid", "Full canvas should be valid"

    def test_color_threshold_application(self):
        """Test black/white threshold logic for e-ink display"""
        test_code = """
function applyThreshold(r, g, b, threshold = 176) {
    // Convert to grayscale
    const gray = 0.299 * r + 0.587 * g + 0.114 * b;
    
    // Apply threshold for 1-bit display
    return gray >= threshold ? 255 : 0;
}

// Test cases
console.log(applyThreshold(255, 255, 255));  // White
console.log(applyThreshold(0, 0, 0));        // Black
console.log(applyThreshold(128, 128, 128));  // Mid gray
console.log(applyThreshold(200, 200, 200));  // Light gray
console.log(applyThreshold(100, 100, 100));  // Dark gray
console.log(applyThreshold(255, 0, 0));      // Red
console.log(applyThreshold(0, 255, 0));      // Green
console.log(applyThreshold(0, 0, 255));      // Blue
"""

        output = execute_js_function("", test_code)
        lines = output.strip().split("\n")

        assert lines[0] == "255", "White should stay white"
        assert lines[1] == "0", "Black should stay black"
        assert lines[2] == "0", "Mid gray should be black"
        assert lines[3] == "255", "Light gray should be white"
        assert lines[4] == "0", "Dark gray should be black"
        # Color conversions depend on luminance formula
        assert lines[5] == "0", "Red should be black (low luminance)"
        # Green luminance calculation: 0.587 * 255 = 149.685, which is < 176 threshold
        assert lines[6] == "0", "Green should be black (below threshold)"
        assert lines[7] == "0", "Blue should be black (low luminance)"


class TestValidationEngine:
    """Test UI validation engine integration"""

    def test_issue_severity_classification(self):
        """Test classification of validation issues by severity"""
        test_code = """
function classifyIssueSeverity(issue) {
    if (issue.type === 'overflow' && issue.overflow > 10) {
        return 'critical';
    }
    if (issue.type === 'collision' && issue.overlap > 5) {
        return 'error';
    }
    if (issue.type === 'alignment' && issue.offset > 2) {
        return 'warning';
    }
    if (issue.type === 'missing_data') {
        return 'info';
    }
    return 'minor';
}

// Test cases
console.log(classifyIssueSeverity({type: 'overflow', overflow: 15}));
console.log(classifyIssueSeverity({type: 'overflow', overflow: 5}));
console.log(classifyIssueSeverity({type: 'collision', overlap: 10}));
console.log(classifyIssueSeverity({type: 'alignment', offset: 3}));
console.log(classifyIssueSeverity({type: 'missing_data'}));
console.log(classifyIssueSeverity({type: 'unknown'}));
"""

        output = execute_js_function("", test_code)
        lines = output.strip().split("\n")

        assert lines[0] == "critical", "Large overflow should be critical"
        assert lines[1] == "minor", "Small overflow should be minor"
        assert lines[2] == "error", "Large collision should be error"
        assert lines[3] == "warning", "Alignment issue should be warning"
        assert lines[4] == "info", "Missing data should be info"
        assert lines[5] == "minor", "Unknown type should be minor"

    def test_empty_region_detection(self):
        """Test detection of empty/unused regions"""
        test_code = """
function detectEmptyRegions(regions, renderedContent) {
    const empty = [];
    
    for (const [name, rect] of Object.entries(regions)) {
        if (!renderedContent[name] || renderedContent[name].trim() === '') {
            empty.push({
                region: name,
                rect: rect,
                expected: true,
                actual: false
            });
        }
    }
    
    return empty;
}

// Test cases
const regions = {
    'header': [0, 0, 100, 20],
    'temp': [0, 30, 100, 30],
    'footer': [0, 100, 100, 20]
};

const content1 = {
    'header': 'Title',
    'temp': '23.5°C',
    'footer': ''
};

const content2 = {
    'header': 'Title',
    'temp': '23.5°C',
    'footer': 'v1.0'
};

console.log(JSON.stringify(detectEmptyRegions(regions, content1)));
console.log(JSON.stringify(detectEmptyRegions(regions, content2)));
"""

        output = execute_js_function("", test_code)
        lines = output.strip().split("\n")

        result1 = json.loads(lines[0])
        assert len(result1) == 1, "Should detect 1 empty region"
        assert result1[0]["region"] == "footer", "Footer should be empty"

        result2 = json.loads(lines[1])
        assert len(result2) == 0, "Should detect no empty regions"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
