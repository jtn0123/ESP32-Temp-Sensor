#!/bin/bash

# Wait for ESP32 device to appear and alert user

echo "Waiting for ESP32 device to appear..."
echo "Try the manual bootloader steps:"
echo "1. Hold BOOT button"
echo "2. Connect USB while holding BOOT"
echo "3. Keep holding for 3-4 seconds"
echo "4. Release BOOT"
echo ""

while true; do
    for port in /dev/cu.usbmodem* /dev/tty.usbmodem* /dev/cu.usbserial* /dev/tty.usbserial*; do
        if [ -e "$port" ]; then
            echo ""
            echo "🎉 DEVICE DETECTED on $port!"
            echo ""
            echo "Quick flash command:"
            echo "cd firmware/arduino && python3 -m esptool --chip esp32s2 --port $port --baud 460800 write_flash -z --flash_mode dio --flash_freq 40m --flash_size 4MB 0x10000 .pio/build/feather_esp32s2_display_only/firmware.bin"
            echo ""
            echo "Or run: ./scripts/bootloader_recovery.sh"
            exit 0
        fi
    done
    echo -n "."
    sleep 0.5
done