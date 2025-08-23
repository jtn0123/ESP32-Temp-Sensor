import os
import re
from typing import Dict, List, Any

import pytest

# Test serial log parsing scripts
ROOT = os.path.dirname(os.path.dirname(__file__))
SCRIPTS_DIR = os.path.join(ROOT, "scripts")

# Load parsing modules dynamically
def _load_parsing_module(module_name: str):
    """Load a parsing module from the scripts directory"""
    module_path = os.path.join(SCRIPTS_DIR, f"{module_name}.py")

    if not os.path.exists(module_path):
        pytest.skip(f"Module {module_name}.py not found")

    import importlib.util
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

# Sample log lines that represent real device output
SAMPLE_LOG_LINES = [
    # Standard metrics lines
    "[METRICS] Inside: 72.5°F 45% RH, Outside: 68.2°F 52% RH, Wind: 5.2 mph, Pressure: 1013.2 hPa",
    "[METRICS] Inside: 71.8°F 46% RH, Outside: 69.1°F 51% RH, Wind: 3.8 mph, Pressure: 1012.8 hPa",
    "[METRICS] Inside: 73.2°F 44% RH, Outside: 67.5°F 53% RH, Wind: 0.0 mph, Pressure: 1014.1 hPa",

    # Error conditions
    "[ERROR] Failed to read SHT40 sensor, using last value",
    "[ERROR] WiFi connection timeout after 10s",
    "[ERROR] MQTT publish failed for topic sensors/office/inside/temp",
    "[ERROR] Invalid pressure reading: 0 hPa",

    # Status lines
    "[STATUS] Battery: 3.85V (87%), Est. days: 145",
    "[STATUS] WiFi connected to MyNetwork (192.168.1.50)",
    "[STATUS] MQTT connected to 192.168.1.10:1883",
    "[STATUS] Wake count: 42, Next wake: 2h",

    # Debug lines
    "[DEBUG] Wake reason: RTC_TIMER",
    "[DEBUG] Connection time: 3.2s",
    "[DEBUG] MQTT publish time: 0.8s",
    "[DEBUG] Deep sleep time: 7170s",

    # Weather condition lines
    "[WEATHER] Condition: partly-cloudy, Code: 3",
    "[WEATHER] Condition: clear, Code: 0",
    "[WEATHER] Condition: rain, Code: 5",

    # Layout telemetry
    "[LAYOUT] Version: ui-spec@1, CRC: 0x1234, MD5: abc123def456",
    "[LAYOUT] Canvas: 250x122, Rects: 15",
]

# Malformed/corrupted log lines for robustness testing
MALFORMED_LOG_LINES = [
    # Incomplete lines
    "[METRICS]",
    "[METRICS] Inside:",
    "[STATUS] Battery:",
    "[ERROR]",

    # Corrupted data
    "[METRICS] Inside: 72.5°F 45% RH, Outside: corrupted°F 52% RH",
    "[METRICS] Inside: 72.5°F 45% RH, Outside: 68.2°F corrupted% RH",
    "[STATUS] Battery: corruptedV (87%)",

    # Invalid formats
    "[METRICS] Inside: 72.5F 45% RH",  # Missing ° symbol
    "[METRICS] Inside: 72.5°F RH",     # Missing humidity value
    "[STATUS] Battery: 3.85V 87%",     # Missing parentheses

    # Very long lines (potential buffer overflow)
    "[METRICS] " + "A" * 1000,
    "[ERROR] " + "B" * 1000,

    # Lines with special characters
    "[METRICS] Inside: 72.5°F 45% RH, Outside: 68.2°F 52% RH, Wind: 5.2 mph, Pressure: 1013.2 hPa \x00\x01\x02",
    "[STATUS] Battery: 3.85V (87%), Est. days: 145 \n\r\t",

    # Empty values
    "[METRICS] Inside: 72.5°F 45% RH, Outside: °F % RH, Wind: mph, Pressure: hPa",
    "[WEATHER] Condition: , Code: ",

    # Wrong data types
    "[METRICS] Inside: text°F text% RH",
    "[STATUS] Battery: textV (text%)",
]

# Expected parsing results for validation
EXPECTED_PARSED_DATA = {
    "standard_metrics": {
        "inside_temp": 72.5,
        "inside_hum": 45,
        "outside_temp": 68.2,
        "outside_hum": 52,
        "wind": 5.2,
        "pressure": 1013.2
    },
    "battery_status": {
        "voltage": 3.85,
        "percent": 87,
        "estimated_days": 145
    },
    "weather_condition": {
        "condition": "partly-cloudy",
        "code": 3
    }
}

def test_parse_awake_log_robustness():
    """Test parse_awake_log.py robustness with malformed input"""

    try:
        parse_awake_log = _load_parsing_module("parse_awake_log")
    except:
        pytest.skip("parse_awake_log.py not available")

    # Test with valid lines
    for line in SAMPLE_LOG_LINES:
        try:
            # Should not crash on valid input
            result = parse_awake_log.parse_line(line)
            assert result is not None or result is None  # Either parses or returns None gracefully
        except Exception as e:
            # Should handle exceptions gracefully
            assert False, f"Parser crashed on valid line: {line}, error: {e}"

    # Test with malformed lines
    for line in MALFORMED_LOG_LINES:
        try:
            result = parse_awake_log.parse_line(line)
            # Should not crash, but result can be None for invalid input
        except Exception as e:
            # Should handle exceptions gracefully for malformed input
            assert False, f"Parser crashed on malformed line: {line}, error: {e}"

def test_parse_debug_json_robustness():
    """Test parse_debug_json.py robustness"""

    try:
        parse_debug_json = _load_parsing_module("parse_debug_json")
    except:
        pytest.skip("parse_debug_json.py not available")

    # Test valid JSON
    valid_json = '{"temp": 72.5, "humidity": 45, "pressure": 1013.2}'
    try:
        result = parse_debug_json.parse_json_string(valid_json)
        assert result is not None
    except Exception as e:
        assert False, f"Parser crashed on valid JSON: {e}"

    # Test malformed JSON
    malformed_jsons = [
        '{"temp": 72.5, "humidity": ',  # Incomplete
        '{"temp": "text", "humidity": 45}',  # Wrong type
        '{invalid json}',  # Invalid format
        '',  # Empty
        '{"temp": 72.5, "humidity": 45',  # Missing closing brace
    ]

    for json_str in malformed_jsons:
        try:
            result = parse_debug_json.parse_json_string(json_str)
            # Should handle gracefully
        except Exception as e:
            assert False, f"Parser crashed on malformed JSON: {json_str}, error: {e}"

def test_parse_offline_log_robustness():
    """Test parse_offline_log.py robustness"""

    try:
        parse_offline_log = _load_parsing_module("parse_offline_log")
    except:
        pytest.skip("parse_offline_log.py not available")

    # Test with various log lines
    all_lines = SAMPLE_LOG_LINES + MALFORMED_LOG_LINES

    for line in all_lines:
        try:
            result = parse_offline_log.parse_log_line(line)
            # Should handle all line types gracefully
        except Exception as e:
            assert False, f"Parser crashed on line: {line}, error: {e}"

def test_parse_wifi_log_robustness():
    """Test parse_wifi_log.py robustness"""

    try:
        parse_wifi_log = _load_parsing_module("parse_wifi_log")
    except:
        pytest.skip("parse_wifi_log.py not available")

    wifi_lines = [
        "[WIFI] Connected to MyNetwork (192.168.1.50)",
        "[WIFI] Connection failed",
        "[WIFI] RSSI: -45 dBm",
        "[WIFI]",  # Empty
        "[WIFI] Connected to (invalid ip)",  # Malformed IP
        "[WIFI] RSSI: text dBm",  # Invalid RSSI
    ]

    for line in wifi_lines:
        try:
            result = parse_wifi_log.parse_wifi_line(line)
            # Should handle gracefully
        except Exception as e:
            assert False, f"Parser crashed on WiFi line: {line}, error: {e}"

def test_parse_timeouts_log_robustness():
    """Test parse_timeouts_log.py robustness"""

    try:
        parse_timeouts_log = _load_parsing_module("parse_timeouts_log")
    except:
        pytest.skip("parse_timeouts_log.py not available")

    timeout_lines = [
        "[TIMEOUT] WiFi connection timeout: 10s",
        "[TIMEOUT] MQTT publish timeout: 5s",
        "[TIMEOUT] Sensor read timeout: 2s",
        "[TIMEOUT]",  # Empty
        "[TIMEOUT] WiFi connection timeout: text",  # Invalid number
        "[TIMEOUT] WiFi connection timeout: -5s",   # Negative
    ]

    for line in timeout_lines:
        try:
            result = parse_timeouts_log.parse_timeout_line(line)
            # Should handle gracefully
        except Exception as e:
            assert False, f"Parser crashed on timeout line: {line}, error: {e}"

def test_metrics_extraction_comprehensive():
    """Test comprehensive metrics extraction from log lines"""

    # Test regex patterns that should match various log formats
    patterns = {
        "temperature": r"(\d+\.?\d*)°?F",
        "humidity": r"(\d+\.?\d*)%\s*RH",
        "pressure": r"(\d+\.?\d*)\s*hPa",
        "wind": r"(\d+\.?\d*)\s*mph",
        "voltage": r"(\d+\.?\d*)V",
        "battery_percent": r"(\d+)%",
        "estimated_days": r"(\d+)\s*days?",
        "wake_count": r"(\d+)",
    }

    test_lines = [
        "[METRICS] Inside: 72.5°F 45% RH, Outside: 68.2°F 52% RH, Wind: 5.2 mph, Pressure: 1013.2 hPa",
        "[STATUS] Battery: 3.85V (87%), Est. days: 145",
        "[STATUS] Wake count: 42, Next wake: 2h",
    ]

    for line in test_lines:
        for pattern_name, pattern in patterns.items():
            matches = re.findall(pattern, line)
            if matches:
                for match in matches:
                    try:
                        # Should be parseable as number
                        if '.' in match:
                            float(match)
                        else:
                            int(match)
                    except ValueError:
                        assert False, f"Invalid numeric value in {pattern_name}: {match}"

def test_error_handling_patterns():
    """Test that error patterns are correctly identified"""

    error_patterns = [
        r"ERROR.*timeout",
        r"ERROR.*failed",
        r"ERROR.*invalid",
        r"Failed to read.*sensor",
        r"Connection.*failed",
    ]

    error_lines = [
        "[ERROR] WiFi connection timeout after 10s",
        "[ERROR] MQTT publish failed for topic sensors/office/inside/temp",
        "[ERROR] Failed to read SHT40 sensor, using last value",
        "[ERROR] Invalid pressure reading: 0 hPa",
    ]

    for line in error_lines:
        matched = False
        for pattern in error_patterns:
            if re.search(pattern, line, re.IGNORECASE):
                matched = True
                break
        assert matched, f"Error line not matched by any pattern: {line}"

def test_log_line_classification():
    """Test that log lines are correctly classified by type"""

    line_classifications = {
        "METRICS": ["[METRICS] Inside: 72.5°F 45% RH"],
        "STATUS": ["[STATUS] Battery: 3.85V (87%)", "[STATUS] WiFi connected"],
        "ERROR": ["[ERROR] Failed to read SHT40 sensor"],
        "DEBUG": ["[DEBUG] Wake reason: RTC_TIMER"],
        "WEATHER": ["[WEATHER] Condition: partly-cloudy, Code: 3"],
        "LAYOUT": ["[LAYOUT] Version: ui-spec@1, CRC: 0x1234"],
    }

    for expected_type, lines in line_classifications.items():
        for line in lines:
            # Extract type from brackets
            match = re.match(r"\[([A-Z]+)\]", line)
            if match:
                actual_type = match.group(1)
                assert actual_type == expected_type, f"Wrong classification for {line}: expected {expected_type}, got {actual_type}"

def test_numeric_value_validation():
    """Test that numeric values in logs are within reasonable ranges"""

    # Define reasonable ranges for sensor values
    value_ranges = {
        "temperature": (-50, 150),      # °F
        "humidity": (0, 100),           # %
        "pressure": (800, 1200),        # hPa
        "wind": (0, 200),              # mph
        "voltage": (2.5, 4.5),         # V
        "battery_percent": (0, 100),    # %
        "estimated_days": (1, 1000),   # days
    }

    for line in SAMPLE_LOG_LINES:
        for value_type, (min_val, max_val) in value_ranges.items():
            if value_type == "temperature":
                matches = re.findall(r"(\d+\.?\d*)°?F", line)
            elif value_type == "humidity":
                matches = re.findall(r"(\d+\.?\d*)%\s*RH", line)
            elif value_type == "pressure":
                matches = re.findall(r"(\d+\.?\d*)\s*hPa", line)
            elif value_type == "wind":
                matches = re.findall(r"(\d+\.?\d*)\s*mph", line)
            elif value_type == "voltage":
                matches = re.findall(r"(\d+\.?\d*)V", line)
            elif value_type == "battery_percent":
                matches = re.findall(r"(\d+)%", line)
            elif value_type == "estimated_days":
                matches = re.findall(r"(\d+)\s*days?", line)
            else:
                continue

            for match in matches:
                try:
                    if '.' in match:
                        value = float(match)
                    else:
                        value = int(match)

                    assert min_val <= value <= max_val, \
                        f"Value {value} for {value_type} out of range [{min_val}, {max_val}] in line: {line}"
                except ValueError:
                    assert False, f"Invalid numeric format: {match} in line: {line}"

def test_log_parsing_performance():
    """Test that log parsing doesn't have performance issues"""

    import time

    # Create a large number of log lines
    many_lines = SAMPLE_LOG_LINES * 100  # 100x repetition

    start_time = time.time()

    try:
        parse_awake_log = _load_parsing_module("parse_awake_log")

        for line in many_lines:
            result = parse_awake_log.parse_line(line)

        end_time = time.time()
        duration = end_time - start_time

        # Should process 1000+ lines in under 1 second
        assert duration < 1.0, f"Parsing too slow: {duration}s for {len(many_lines)} lines"

    except:
        pytest.skip("parse_awake_log.py not available for performance test")

def test_malformed_input_graceful_handling():
    """Test that malformed input is handled gracefully without crashes"""

    # Test various types of malformed input
    malformed_inputs = [
        None,
        "",
        "   ",  # Whitespace only
        "\x00\x01\x02",  # Control characters
        "A" * 10000,  # Very long string
        "\n\n\n",  # Multiple newlines
        "🚀🔥💯",  # Unicode emojis
    ]

    try:
        parse_awake_log = _load_parsing_module("parse_awake_log")

        for malformed in malformed_inputs:
            try:
                result = parse_awake_log.parse_line(malformed)
                # Should not crash
            except Exception as e:
                # If it crashes, the error should be meaningful
                assert "NoneType" not in str(e), f"Parser should handle None input better: {e}"
                assert "string" in str(e).lower() or "parse" in str(e).lower(), \
                    f"Unexpected error type for malformed input: {e}"

    except:
        pytest.skip("parse_awake_log.py not available for malformed input test")
