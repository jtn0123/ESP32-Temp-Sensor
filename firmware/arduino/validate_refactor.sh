#!/bin/bash

echo "=== ESP32 Firmware Refactoring Validation ==="
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

echo "1. Checking compilation..."
check "Display build compiles" "pio run -e feather_esp32s2_display_only"
check "Headless build compiles" "pio run -e feather_esp32s2_headless"

echo ""
echo "2. Checking for common issues..."

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
echo "3. Checking MQTT consistency..."

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
echo "4. Checking module separation..."

# Check that system functions are not in display files
check "System functions not in display module" "! grep -E 'deep_sleep|nvs_|wake_count' src/display_manager.cpp"

# Check that display functions are not in system files  
check "Display functions not in system module" "! grep -E 'display\\.|draw_|partial_update' src/system_manager.cpp"

# Check that network functions are properly separated
check "WiFi functions isolated to wifi_manager" "! grep -E 'WiFi\\.' src/mqtt_client.cpp src/ha_discovery.cpp"

echo ""
echo "5. Checking memory usage..."

# Get memory usage from build output
DISPLAY_RAM=$(pio run -e feather_esp32s2_display_only 2>&1 | grep "RAM:" | grep -oE '[0-9]+ bytes' | head -1 | cut -d' ' -f1)
HEADLESS_RAM=$(pio run -e feather_esp32s2_headless 2>&1 | grep "RAM:" | grep -oE '[0-9]+ bytes' | head -1 | cut -d' ' -f1)

if [ -n "$DISPLAY_RAM" ] && [ -n "$HEADLESS_RAM" ]; then
    echo -e "${GREEN}✓${NC} Display build RAM: $DISPLAY_RAM bytes"
    echo -e "${GREEN}✓${NC} Headless build RAM: $HEADLESS_RAM bytes"
    ((PASS+=2))
fi

echo ""
echo "6. File size analysis..."

# Check if any file is too large
for file in src/*.cpp src/*.h; do
    lines=$(wc -l < "$file")
    name=$(basename "$file")
    if [ $lines -gt 500 ]; then
        if [ $lines -gt 1000 ]; then
            echo -e "${RED}✗${NC} $name has $lines lines (>1000)"
            ((FAIL++))
        else
            echo -e "${YELLOW}⚠${NC} $name has $lines lines (>500)"
            ((WARN++))
        fi
    fi
done

echo ""
echo "=== Validation Summary ==="
echo -e "Passed: ${GREEN}$PASS${NC}"
echo -e "Warnings: ${YELLOW}$WARN${NC}"
echo -e "Failed: ${RED}$FAIL${NC}"

if [ $FAIL -eq 0 ]; then
    echo -e "\n${GREEN}Refactoring validation PASSED!${NC}"
    exit 0
else
    echo -e "\n${RED}Refactoring validation FAILED!${NC}"
    exit 1
fi