#!/usr/bin/env python3
"""
Force flash script - aggressively tries to flash ESP32
Continuously monitors for device and flashes as soon as it appears
"""

import time
import subprocess
import sys
import os
import glob

def find_esp32_port():
    """Find ESP32 USB port"""
    patterns = [
        "/dev/tty.usbmodem*",
        "/dev/cu.usbmodem*", 
        "/dev/ttyUSB*",
        "/dev/ttyACM*",
    ]
    
    for pattern in patterns:
        ports = glob.glob(pattern)
        if ports:
            return ports[0]
    return None

def try_read_device(port):
    """Try to read from device to see if it's responding"""
    print(f"Trying to read from {port}...")
    try:
        # Try using esptool to read chip info
        result = subprocess.run(
            ["python3", "-m", "esptool", "--chip", "esp32s2", "--port", port, "chip_id"],
            capture_output=True,
            text=True,
            timeout=2
        )
        if result.returncode == 0:
            print("✅ Device responding to esptool!")
            print(result.stdout)
            return True
        else:
            print(f"❌ Device not responding: {result.stderr[:200]}")
            return False
    except subprocess.TimeoutExpired:
        print("⏱️ Timeout reading device")
        return False
    except Exception as e:
        print(f"Error: {e}")
        return False

def erase_flash(port):
    """Erase flash completely"""
    print(f"\n🗑️ ERASING FLASH on {port}...")
    try:
        result = subprocess.run(
            ["python3", "-m", "esptool", "--chip", "esp32s2", "--port", port, 
             "--before", "default_reset", "--after", "hard_reset", "erase_flash"],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            print("✅ Flash erased successfully!")
            return True
        else:
            print(f"❌ Erase failed: {result.stderr[:200]}")
            return False
    except Exception as e:
        print(f"Error erasing: {e}")
        return False

def flash_firmware(port, firmware_path):
    """Flash firmware to device"""
    print(f"\n📦 FLASHING FIRMWARE to {port}...")
    try:
        # Build the firmware first
        print("Building firmware...")
        build_result = subprocess.run(
            ["pio", "run", "-e", "feather_esp32s2_display_only"],
            cwd=os.path.dirname(firmware_path),
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if build_result.returncode != 0:
            print(f"❌ Build failed: {build_result.stderr[:500]}")
            return False
            
        print("✅ Build successful")
        
        # Now flash it
        result = subprocess.run(
            ["pio", "run", "-e", "feather_esp32s2_display_only", "-t", "upload", 
             "--upload-port", port],
            cwd=os.path.dirname(firmware_path),
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode == 0:
            print("✅ Firmware flashed successfully!")
            return True
        else:
            print(f"❌ Flash failed: {result.stderr[:500]}")
            return False
    except Exception as e:
        print(f"Error flashing: {e}")
        return False

def monitor_device(port):
    """Quick monitor to see if device boots"""
    print(f"\n👀 Monitoring {port} for 3 seconds...")
    try:
        import serial
        ser = serial.Serial(port, 115200, timeout=1)
        start = time.time()
        while time.time() - start < 3:
            if ser.in_waiting:
                data = ser.readline()
                print(f"  > {data.decode('utf-8', errors='ignore').strip()}")
        ser.close()
    except Exception as e:
        print(f"Monitor error: {e}")

def main():
    print("=" * 60)
    print("ESP32 FORCE FLASH RECOVERY TOOL")
    print("=" * 60)
    print("\nThis tool will:")
    print("1. Continuously scan for ESP32")
    print("2. Try to read device info")
    print("3. Erase flash if possible")
    print("4. Flash new firmware")
    print("\n⚠️  IMPORTANT: Try these while running this script:")
    print("  - Hold BOOT button and press RESET")
    print("  - Hold BOOT while plugging in USB")
    print("  - Press RESET multiple times")
    print("\nPress Ctrl+C to stop\n")
    
    firmware_path = os.path.join(
        os.path.dirname(__file__),
        "..", "firmware", "arduino"
    )
    
    last_port = None
    attempts = 0
    
    while True:
        attempts += 1
        print(f"\n🔄 Attempt #{attempts}")
        
        # Find device
        port = find_esp32_port()
        
        if not port:
            print("⏳ No device found. Waiting...")
            print("   Try: Hold BOOT + press RESET")
            time.sleep(2)
            continue
            
        if port != last_port:
            print(f"🔌 Found device at: {port}")
            last_port = port
        
        # Try to read device
        if try_read_device(port):
            # Device is responding, try to erase
            if erase_flash(port):
                # Flash erased, now flash firmware
                if flash_firmware(port, firmware_path):
                    print("\n🎉 SUCCESS! Device recovered!")
                    monitor_device(port)
                    break
                else:
                    print("Retrying in 5 seconds...")
                    time.sleep(5)
            else:
                print("Could not erase. Trying different approach...")
                # Try direct flash without erase
                if flash_firmware(port, firmware_path):
                    print("\n🎉 SUCCESS! Device flashed without erase!")
                    monitor_device(port)
                    break
        else:
            print("Device not responding. Please:")
            print("  1. Hold BOOT button")
            print("  2. Press RESET while holding BOOT")
            print("  3. Keep holding BOOT for 2-3 seconds")
            print("  4. Release BOOT")
            time.sleep(3)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nStopped by user")
        sys.exit(0)