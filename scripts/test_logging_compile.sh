#!/bin/bash
# Simple compile test for logging system
# Run this to validate the logging integration compiles correctly

set -e  # Exit on error

echo "=== Testing Logging System Compilation ==="
echo

cd "$(dirname "$0")/../firmware/arduino"

# Test with logging enabled (default)
echo "1. Testing with logging ENABLED..."
pio run -e feather_esp32s2_display_only --target clean >/dev/null 2>&1 || true
if pio run -e feather_esp32s2_display_only 2>&1 | tee /tmp/build_log.txt | grep -E "SUCCESS|Error"; then
    if grep -q "Error" /tmp/build_log.txt; then
        echo "❌ Build failed with logging enabled"
        exit 1
    else
        echo "✅ Build successful with logging enabled"
    fi
else
    echo "❌ Build command failed"
    exit 1
fi

echo
echo "2. Testing with logging DISABLED..."
# Create temporary build flags to disable logging
export PLATFORMIO_BUILD_FLAGS="-DLOG_ENABLED=0"
pio run -e feather_esp32s2_display_only --target clean >/dev/null 2>&1 || true
if pio run -e feather_esp32s2_display_only 2>&1 | tee /tmp/build_log.txt | grep -E "SUCCESS|Error"; then
    if grep -q "Error" /tmp/build_log.txt; then
        echo "❌ Build failed with logging disabled"
        exit 1
    else
        echo "✅ Build successful with logging disabled"
    fi
else
    echo "❌ Build command failed"
    exit 1
fi
unset PLATFORMIO_BUILD_FLAGS

echo
echo "=== Logging System Compile Test PASSED ==="
echo
echo "Quick validation checklist:"
echo "✅ Logging headers compile without errors"
echo "✅ System builds with LOG_ENABLED=1"
echo "✅ System builds with LOG_ENABLED=0"
echo
echo "To test logging at runtime:"
echo "1. Flash the device: pio run -e feather_esp32s2_display_only -t upload"
echo "2. Monitor serial: pio device monitor"
echo "3. Type these commands in serial monitor:"
echo "   log test   - Run a quick logging test"
echo "   log stats  - Show buffer and storage statistics"
echo "   log dump   - Dump the crash log buffer"
echo "   log level DEBUG  - Change log level"
echo
echo "MQTT testing (when connected):"
echo "- Logs publish to: espsensor/<device_id>/logs/<level>"
echo "- Clear logs: mosquitto_pub -t espsensor/<id>/cmd/clear_logs -m '1'"
echo "- Set level: mosquitto_pub -t espsensor/<id>/cmd/log_level -m 'DEBUG'"