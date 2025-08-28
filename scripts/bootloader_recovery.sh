#!/bin/bash

# ESP32-S2 Bootloader Recovery Script
# This script helps recover an ESP32-S2 that won't boot or flash normally

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
FIRMWARE_DIR="$PROJECT_ROOT/firmware/arduino"

echo "==================================="
echo "ESP32-S2 BOOTLOADER RECOVERY TOOL"
echo "==================================="
echo ""

# Function to find USB port
find_port() {
    # Look for USB modem or serial ports
    for port in /dev/cu.usbmodem* /dev/tty.usbmodem* /dev/cu.usbserial* /dev/tty.usbserial* /dev/cu.SLAB* /dev/tty.SLAB*; do
        if [ -e "$port" ]; then
            echo "$port"
            return 0
        fi
    done
    return 1
}

# Step 1: Instructions
echo "MANUAL BOOTLOADER MODE INSTRUCTIONS:"
echo "====================================="
echo "1. DISCONNECT the USB cable from your ESP32-S2"
echo "2. Locate the BOOT button (might be labeled BOOT, B0, or GPIO0)"
echo "3. HOLD DOWN the BOOT button"
echo "4. While holding BOOT, CONNECT the USB cable"
echo "5. Keep holding BOOT for 3-4 seconds"
echo "6. Release the BOOT button"
echo ""
echo "Press Enter when ready to continue..."
read -r

# Step 2: Wait for device
echo ""
echo "Waiting for device to appear..."
echo "(If nothing happens after 10 seconds, try the manual steps again)"
echo ""

ATTEMPTS=0
MAX_ATTEMPTS=20
PORT=""

while [ $ATTEMPTS -lt $MAX_ATTEMPTS ]; do
    if PORT=$(find_port); then
        echo "✓ Found device on port: $PORT"
        break
    fi
    echo -n "."
    sleep 0.5
    ATTEMPTS=$((ATTEMPTS + 1))
done

if [ -z "$PORT" ]; then
    echo ""
    echo "❌ No device found after 10 seconds"
    echo ""
    echo "TROUBLESHOOTING:"
    echo "1. Try a different USB cable"
    echo "2. Try a different USB port"
    echo "3. Make sure you're holding BOOT while connecting"
    echo "4. On some boards, you may need to press RESET while holding BOOT"
    exit 1
fi

# Step 3: Flash bootloader and firmware
echo ""
echo "Device found! Starting recovery flash..."
echo "========================================"

# First, try to flash just the bootloader
echo ""
echo "Step 1: Flashing bootloader..."
if [ -f "$FIRMWARE_DIR/.pio/build/feather_esp32s2_display_only/bootloader.bin" ]; then
    python3 -m esptool \
        --chip esp32s2 \
        --port "$PORT" \
        --baud 460800 \
        --before default_reset \
        --after no_reset \
        write_flash \
        -z \
        --flash_mode dio \
        --flash_freq 40m \
        --flash_size 4MB \
        0x1000 "$FIRMWARE_DIR/.pio/build/feather_esp32s2_display_only/bootloader.bin" || {
            echo "⚠️  Bootloader flash failed, trying alternate method..."
        }
else
    echo "⚠️  Bootloader not found, skipping..."
fi

# Flash partition table
echo ""
echo "Step 2: Flashing partition table..."
if [ -f "$FIRMWARE_DIR/.pio/build/feather_esp32s2_display_only/partitions.bin" ]; then
    python3 -m esptool \
        --chip esp32s2 \
        --port "$PORT" \
        --baud 460800 \
        --before no_reset \
        --after no_reset \
        write_flash \
        -z \
        --flash_mode dio \
        --flash_freq 40m \
        --flash_size 4MB \
        0x8000 "$FIRMWARE_DIR/.pio/build/feather_esp32s2_display_only/partitions.bin" || {
            echo "⚠️  Partition table flash failed"
        }
else
    echo "⚠️  Partition table not found, skipping..."
fi

# Flash main firmware
echo ""
echo "Step 3: Flashing main firmware..."
if [ -f "$FIRMWARE_DIR/.pio/build/feather_esp32s2_display_only/firmware.bin" ]; then
    python3 -m esptool \
        --chip esp32s2 \
        --port "$PORT" \
        --baud 460800 \
        --before no_reset \
        --after hard_reset \
        write_flash \
        -z \
        --flash_mode dio \
        --flash_freq 40m \
        --flash_size 4MB \
        0x10000 "$FIRMWARE_DIR/.pio/build/feather_esp32s2_display_only/firmware.bin" && {
            echo ""
            echo "✅ FIRMWARE FLASH SUCCESSFUL!"
            echo ""
            echo "The device should now reset and boot normally."
            echo "You can monitor it with:"
            echo "  pio device monitor -p $PORT"
            echo ""
            
            # Offer to monitor
            echo "Would you like to monitor the device now? (y/n)"
            read -r MONITOR
            if [[ "$MONITOR" =~ ^[Yy]$ ]]; then
                cd "$FIRMWARE_DIR"
                pio device monitor -p "$PORT"
            fi
        } || {
            echo ""
            echo "❌ Firmware flash failed"
            echo ""
            echo "Try running this script again, or use the manual command:"
            echo "  python3 -m esptool --chip esp32s2 --port $PORT erase_flash"
            echo "  Then run this script again"
            exit 1
        }
else
    echo "❌ Firmware file not found!"
    echo "Please build the firmware first with:"
    echo "  cd $FIRMWARE_DIR && pio run -e feather_esp32s2_display_only"
    exit 1
fi