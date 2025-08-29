#!/bin/bash

# Integration test suite for ESP32 Temperature Sensor
# Runs comprehensive tests to catch issues before hardware testing

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
FIRMWARE_DIR="$PROJECT_ROOT/firmware/arduino"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "========================================="
echo "ESP32 Temperature Sensor Integration Test"
echo "========================================="
echo ""

# Track test results
TESTS_PASSED=0
TESTS_FAILED=0
WARNINGS=0

# Function to print test results
print_result() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✓${NC} $2"
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        echo -e "${RED}✗${NC} $2"
        TESTS_FAILED=$((TESTS_FAILED + 1))
    fi
}

# Function to print warnings
print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
    WARNINGS=$((WARNINGS + 1))
}

echo "1. Checking project structure..."
echo "--------------------------------"

# Check required directories exist
if [ -d "$FIRMWARE_DIR" ]; then
    print_result 0 "Firmware directory exists"
else
    print_result 1 "Firmware directory missing"
fi

if [ -d "$PROJECT_ROOT/config" ]; then
    print_result 0 "Config directory exists"
else
    print_result 1 "Config directory missing"
fi

if [ -d "$PROJECT_ROOT/scripts" ]; then
    print_result 0 "Scripts directory exists"
else
    print_result 1 "Scripts directory missing"
fi

# Check required config files
if [ -f "$PROJECT_ROOT/config/device.yaml" ]; then
    print_result 0 "device.yaml exists"
else
    print_result 1 "device.yaml missing"
fi

if [ -f "$PROJECT_ROOT/config/display_geometry.json" ]; then
    print_result 0 "display_geometry.json exists"
else
    print_result 1 "display_geometry.json missing"
fi

echo ""
echo "2. Validating Python scripts..."
echo "-------------------------------"

# Check Python script syntax
for script in "$SCRIPT_DIR"/*.py; do
    if [ -f "$script" ]; then
        python3 -m py_compile "$script" 2>/dev/null
        if [ $? -eq 0 ]; then
            print_result 0 "$(basename $script) syntax OK"
        else
            print_result 1 "$(basename $script) has syntax errors"
        fi
    fi
done

echo ""
echo "3. Running code generation..."
echo "-----------------------------"

# Run code generators
cd "$FIRMWARE_DIR"
python3 "$SCRIPT_DIR/gen_device_header.py" 2>/dev/null
print_result $? "Generated device header"

python3 "$SCRIPT_DIR/gen_layout_header.py" 2>/dev/null
print_result $? "Generated layout header"

echo ""
echo "4. Building all environments..."
echo "-------------------------------"

# Build each environment and check for errors
ENVIRONMENTS=("dev_display" "feather_esp32s2_display_only" "feather_esp32s2_headless")

for env in "${ENVIRONMENTS[@]}"; do
    echo -n "Building $env... "
    
    # Capture build output
    BUILD_OUTPUT=$(pio run -e $env 2>&1)
    BUILD_RESULT=$?
    
    if [ $BUILD_RESULT -eq 0 ]; then
        # Check binary size
        SIZE_LINE=$(echo "$BUILD_OUTPUT" | grep "Flash:" | tail -1)
        if [[ $SIZE_LINE =~ ([0-9]+)% ]]; then
            FLASH_PERCENT=${BASH_REMATCH[1]}
            if [ $FLASH_PERCENT -gt 90 ]; then
                print_warning "$env uses $FLASH_PERCENT% of flash (>90%)"
            else
                print_result 0 "$env built successfully (Flash: $FLASH_PERCENT%)"
            fi
        else
            print_result 0 "$env built successfully"
        fi
    else
        print_result 1 "$env build failed"
        # Show last few lines of error
        echo "$BUILD_OUTPUT" | tail -5
    fi
    
    # Check for warnings
    WARNING_COUNT=$(echo "$BUILD_OUTPUT" | grep -c "warning:" || true)
    if [ $WARNING_COUNT -gt 0 ]; then
        print_warning "$env has $WARNING_COUNT compiler warnings"
    fi
done

echo ""
echo "5. Checking for common issues..."
echo "--------------------------------"

# Check for missing namespace declarations
NAMESPACE_ISSUES=$(grep -r "OP_\|RECT_" "$FIRMWARE_DIR/src" 2>/dev/null | grep -v "ui::" | grep -v "using namespace ui" | wc -l || echo "0")
if [ "$NAMESPACE_ISSUES" -gt 0 ]; then
    print_warning "Found $NAMESPACE_ISSUES potential namespace issues"
else
    print_result 0 "No namespace issues detected"
fi

# Check for potential null pointer dereferences
NULL_CHECK=$(grep -r "\->" "$FIRMWARE_DIR/src" 2>/dev/null | grep -v "if.*!" | grep -v "if.*==" | grep -v "//" | wc -l || echo "0")
if [ "$NULL_CHECK" -gt 50 ]; then
    print_warning "Many pointer dereferences without null checks ($NULL_CHECK)"
else
    print_result 0 "Pointer usage appears safe"
fi

# Check for memory leaks (new without delete)
NEW_COUNT=$(grep -r "new " "$FIRMWARE_DIR/src" --include="*.cpp" 2>/dev/null | wc -l || echo "0")
DELETE_COUNT=$(grep -r "delete " "$FIRMWARE_DIR/src" --include="*.cpp" 2>/dev/null | wc -l || echo "0")
if [ "$NEW_COUNT" -gt "$DELETE_COUNT" ]; then
    print_warning "Potential memory leaks: $NEW_COUNT 'new' vs $DELETE_COUNT 'delete'"
else
    print_result 0 "Memory allocation balanced"
fi

echo ""
echo "6. Running unit tests..."
echo "-----------------------"

# Run PlatformIO tests if they exist
if [ -d "$FIRMWARE_DIR/test" ]; then
    # Count available tests
    TEST_COUNT=$(find "$FIRMWARE_DIR/test" -name "test_*.cpp" 2>/dev/null | wc -l || echo "0")
    if [ "$TEST_COUNT" -gt 0 ]; then
        echo "Found $TEST_COUNT unit test files"
        # Note: pio test would run on actual hardware, so we skip for now
        print_warning "Unit tests require hardware to run"
    else
        print_warning "No unit tests found"
    fi
else
    print_warning "Test directory not found"
fi

echo ""
echo "7. Validating configuration..."
echo "-----------------------------"

# Check if WiFi credentials are set
if grep -q 'WIFI_SSID ""' "$FIRMWARE_DIR/src/generated_config.h" 2>/dev/null; then
    print_warning "WiFi credentials not configured"
else
    print_result 0 "WiFi credentials configured"
fi

# Check if MQTT is configured
if grep -q 'MQTT_HOST ""' "$FIRMWARE_DIR/src/generated_config.h" 2>/dev/null; then
    print_warning "MQTT broker not configured"
else
    print_result 0 "MQTT broker configured"
fi

echo ""
echo "8. Display diagnostics..."
echo "------------------------"

# Check display configuration consistency
if [ -f "$PROJECT_ROOT/config/display_geometry.json" ]; then
    # Check if display dimensions match
    WIDTH=$(grep "DISPLAY_WIDTH\|EINK_WIDTH" "$FIRMWARE_DIR/src/config.h" | head -1 | grep -o "[0-9]*" || echo "0")
    HEIGHT=$(grep "DISPLAY_HEIGHT\|EINK_HEIGHT" "$FIRMWARE_DIR/src/config.h" | head -1 | grep -o "[0-9]*" || echo "0")
    
    if [ "$WIDTH" = "250" ] && [ "$HEIGHT" = "122" ]; then
        print_result 0 "Display dimensions correct (250x122)"
    else
        print_warning "Display dimensions: ${WIDTH}x${HEIGHT} (expected 250x122)"
    fi
fi

echo ""
echo "========================================="
echo "              TEST SUMMARY               "
echo "========================================="
echo -e "Tests Passed: ${GREEN}$TESTS_PASSED${NC}"
echo -e "Tests Failed: ${RED}$TESTS_FAILED${NC}"
echo -e "Warnings:     ${YELLOW}$WARNINGS${NC}"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All critical tests passed!${NC}"
    echo ""
    echo "Ready for hardware testing. Use:"
    echo "  python3 scripts/flash.py --env dev --mode always --monitor"
    exit 0
else
    echo -e "${RED}✗ Some tests failed. Please fix issues before hardware testing.${NC}"
    exit 1
fi