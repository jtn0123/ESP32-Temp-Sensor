#!/bin/bash
# Validation Script for ESP32 Temperature Sensor Refactoring
# This script validates that the refactoring has not broken functionality

set -e  # Exit on first error

echo "======================================"
echo "ESP32 Temp Sensor Refactoring Validation"
echo "======================================"
echo ""

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

PASS=0
FAIL=0
WARN=0

# Function to check a condition
check() {
    local description=$1
    local command=$2
    
    if eval "$command" > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} $description"
        ((PASS++))
    else
        echo -e "${RED}✗${NC} $description"
        ((FAIL++))
    fi
}

# Function to warn about potential issues
warn_check() {
    local description=$1
    local command=$2
    
    if eval "$command" > /dev/null 2>&1; then
        echo -e "${YELLOW}⚠${NC} $description"
        ((WARN++))
    fi
}

echo "Phase 1: Code Generation"
echo "------------------------"
cd ../..
check "Generate device header" "python3 scripts/gen_device_header.py"
check "Generate layout header" "python3 scripts/gen_layout_header.py"
cd firmware/arduino

echo ""
echo "Phase 2: C++ Compilation"
echo "------------------------"
check "Display build compiles" "pio run -e feather_esp32s2_display_only"
check "Headless build compiles" "pio run -e feather_esp32s2_headless"

# Run native tests
echo ""
echo "Phase 3: Native Tests"
echo "---------------------"
check "PlatformIO native tests" "pio test -e native"

echo ""
echo "Phase 4: Code Quality Checks"
echo "-----------------------------"

# Check for duplicate symbols
warn_check "Duplicate g_client_id found" "grep -r 'static.*g_client_id' src/*.cpp src/*.h | grep -v '//' | wc -l | grep -v '^1$'"

# Check for undefined references to removed functions
check "No undefined g_mqtt references" "! grep -r 'g_mqtt\\.' src/*.cpp src/*.h | grep -v mqtt_client.cpp | grep -v '//' | grep ."

# Check for orphaned includes
check "No references to non-existent headers" "! grep -r '#include.*\\.h' src/*.cpp | xargs -I {} basename {} | while read f; do [ ! -f src/\$f ]; done"

# Check header guards
check "All headers have guards" "! ls src/*.h | xargs grep -L '#pragma once'"

# Check for circular dependencies
warn_check "Potential circular dependency detected" "grep -l wifi_manager.h src/*.cpp src/*.h | xargs grep -l mqtt_client.h | grep -v net.h | grep ."

echo ""
echo "Phase 5: Module Consistency"
echo "----------------------------"

# Check MQTT topic patterns
ESPSENSOR_COUNT=$(grep -r 'espsensor/' src/*.cpp src/*.h | wc -l)
SENSORS_COUNT=$(grep -r 'sensors/' src/*.cpp src/*.h | grep -v espsensor | wc -l)

if [ $ESPSENSOR_COUNT -gt 0 ] && [ $SENSORS_COUNT -gt 0 ]; then
    echo -e "${YELLOW}⚠${NC} Mixed MQTT topic patterns found (espsensor: $ESPSENSOR_COUNT, sensors: $SENSORS_COUNT)"
    ((WARN++))
else
    echo -e "${GREEN}✓${NC} MQTT topic patterns consistent"
    ((PASS++))
fi

echo ""
echo "Phase 6: Module Separation"
echo "---------------------------"

# Check that system functions are not in display files
check "System functions not in display module" "! grep -E 'deep_sleep|nvs_|wake_count' src/display_manager.cpp"

# Check that display functions are not in system files  
check "Display functions not in system module" "! grep -E 'display\\.|draw_|partial_update' src/system_manager.cpp"

# Check that network functions are properly separated
check "WiFi functions isolated to wifi_manager" "! grep -E 'WiFi\\.' src/mqtt_client.cpp src/ha_discovery.cpp"

echo ""
echo "Phase 7: Memory Usage Analysis"
echo "-------------------------------"

# Get memory usage from build output
DISPLAY_RAM=$(pio run -e feather_esp32s2_display_only 2>&1 | grep "RAM:" | grep -oE '[0-9]+ bytes' | head -1 | cut -d' ' -f1)
HEADLESS_RAM=$(pio run -e feather_esp32s2_headless 2>&1 | grep "RAM:" | grep -oE '[0-9]+ bytes' | head -1 | cut -d' ' -f1)

if [ -n "$DISPLAY_RAM" ] && [ -n "$HEADLESS_RAM" ]; then
    echo -e "${GREEN}✓${NC} Display build RAM: $DISPLAY_RAM bytes"
    echo -e "${GREEN}✓${NC} Headless build RAM: $HEADLESS_RAM bytes"
    ((PASS+=2))
fi

echo ""
echo "Phase 8: File Size Analysis"
echo "----------------------------"

# Check main.cpp is under 1000 lines
MAIN_LINES=$(wc -l < src/main.cpp)
echo "main.cpp: $MAIN_LINES lines"
if [ $MAIN_LINES -lt 1000 ]; then
    echo -e "${GREEN}✓${NC} main.cpp successfully reduced (target: <1000)"
    ((PASS++))
else
    echo -e "${RED}✗${NC} main.cpp still too large"
    ((FAIL++))
fi

# Check other files
echo ""
echo "Module sizes:"
for file in src/state_manager.cpp src/system_manager.cpp src/app_controller.cpp src/sensors.cpp src/power.cpp src/mqtt_client.cpp src/wifi_manager.cpp; do
    if [ -f "$file" ]; then
        lines=$(wc -l < "$file")
        name=$(basename "$file")
        if [ $lines -gt 1000 ]; then
            echo -e "${RED}✗${NC} $name: $lines lines (>1000)"
            ((FAIL++))
        elif [ $lines -gt 500 ]; then
            echo -e "${YELLOW}⚠${NC} $name: $lines lines (>500)"
            ((WARN++))
        else
            echo -e "${GREEN}✓${NC} $name: $lines lines"
            ((PASS++))
        fi
    fi
done

echo ""
echo "======================================"
echo "VALIDATION SUMMARY"
echo "======================================"
echo -e "Tests Passed: ${GREEN}$PASS${NC}"
echo -e "Warnings: ${YELLOW}$WARN${NC}"
echo -e "Tests Failed: ${RED}$FAIL${NC}"
echo ""

if [ $FAIL -eq 0 ]; then
    echo -e "${GREEN}✓ VALIDATION PASSED${NC}"
    echo "The refactoring has been validated successfully."
    echo "All modules compile correctly and tests pass."
    exit 0
else
    echo -e "${RED}✗ VALIDATION FAILED${NC}"
    echo "Please review the failures above."
    exit 1
fi