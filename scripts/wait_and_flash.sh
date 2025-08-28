#!/bin/bash
# Aggressive wait-and-flash script
# Watches for device to appear and immediately tries to flash it

echo "=========================================="
echo "ESP32 WAIT AND FLASH SCRIPT"
echo "=========================================="
echo ""
echo "Instructions:"
echo "1. Hold the BOOT button on your ESP32"
echo "2. Connect USB cable (or press RESET if already connected)"
echo "3. Keep holding BOOT for 3 seconds"
echo "4. Release BOOT"
echo ""
echo "Waiting for device to appear..."

# Function to find ESP32 port
find_port() {
    ls /dev/tty.usbmodem* /dev/cu.usbmodem* 2>/dev/null | head -1
}

# Function to try flashing
try_flash() {
    local port=$1
    echo ""
    echo "🔥 ATTEMPTING FLASH on $port"
    
    # First try to erase
    echo "Step 1: Erasing flash..."
    python3 -m esptool --chip esp32s2 --port "$port" --before default_reset --after hard_reset erase_flash
    
    if [ $? -eq 0 ]; then
        echo "✅ Erase successful!"
        
        # Now try to flash
        echo "Step 2: Flashing firmware..."
        cd "$(dirname "$0")/../firmware/arduino"
        pio run -e feather_esp32s2_display_only -t upload --upload-port "$port"
        
        if [ $? -eq 0 ]; then
            echo "✅ FLASH SUCCESSFUL!"
            echo "Monitoring output..."
            python3 ../../scripts/monitor_usb.py "$port" --raw
            return 0
        else
            echo "❌ Flash failed"
        fi
    else
        echo "❌ Erase failed - trying direct flash..."
        cd "$(dirname "$0")/../firmware/arduino"
        pio run -e feather_esp32s2_display_only -t upload --upload-port "$port"
        if [ $? -eq 0 ]; then
            echo "✅ Direct flash successful!"
            return 0
        fi
    fi
    
    return 1
}

# Main loop
attempt=0
while true; do
    ((attempt++))
    
    # Look for device
    port=$(find_port)
    
    if [ -n "$port" ]; then
        echo ""
        echo "🎯 DEVICE FOUND at $port (attempt #$attempt)"
        
        # Try to flash immediately
        try_flash "$port"
        
        if [ $? -eq 0 ]; then
            echo "🎉 SUCCESS!"
            break
        else
            echo "Retrying in 2 seconds..."
            echo "Try: Hold BOOT + press RESET"
            sleep 2
        fi
    else
        # No device found
        echo -ne "\r⏳ Waiting for device... (attempt #$attempt) "
        echo -ne "Hold BOOT + connect USB or press RESET"
        sleep 1
    fi
done