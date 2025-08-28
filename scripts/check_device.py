#!/usr/bin/env python3
"""
Check ESP32 device state and try various recovery methods
"""

import subprocess
import time
import sys
import glob
import os

def run_cmd(cmd, timeout=5):
    """Run command and return output"""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=isinstance(cmd, str)
        )
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", "Timeout"
    except Exception as e:
        return False, "", str(e)

def find_ports():
    """Find all possible ESP32 ports"""
    ports = []
    patterns = [
        "/dev/tty.usbmodem*",
        "/dev/cu.usbmodem*",
        "/dev/ttyUSB*",
        "/dev/ttyACM*",
    ]
    
    for pattern in patterns:
        ports.extend(glob.glob(pattern))
    
    return sorted(set(ports))

def check_port_with_screen(port):
    """Try to read using screen command"""
    print(f"\n📺 Trying screen on {port}...")
    print("  (Press Ctrl+A then K to kill screen)")
    subprocess.call(["screen", port, "115200"])

def check_port_with_cat(port):
    """Try to read using cat"""
    print(f"\n📖 Reading raw data from {port}...")
    try:
        proc = subprocess.Popen(
            ["cat", port],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        time.sleep(2)
        proc.terminate()
        output, error = proc.communicate(timeout=1)
        if output:
            print(f"  Got data: {output[:200]}")
        else:
            print("  No data received")
    except Exception as e:
        print(f"  Error: {e}")

def check_with_esptool(port):
    """Check device with esptool"""
    print(f"\n🔧 Checking {port} with esptool...")
    
    # Try to read chip ID
    success, stdout, stderr = run_cmd(
        ["python3", "-m", "esptool", "--chip", "esp32s2", "--port", port, "chip_id"],
        timeout=5
    )
    
    if success:
        print("✅ Device responding!")
        print(stdout)
    else:
        print(f"❌ Not responding: {stderr[:200]}")
    
    # Try to read flash ID
    print("\n🔍 Trying to read flash ID...")
    success, stdout, stderr = run_cmd(
        ["python3", "-m", "esptool", "--chip", "esp32s2", "--port", port, "flash_id"],
        timeout=5
    )
    
    if success:
        print("✅ Flash ID read!")
        print(stdout)
    else:
        print(f"❌ Could not read flash: {stderr[:200]}")

def check_with_stty(port):
    """Check port settings with stty"""
    print(f"\n⚙️ Checking port settings for {port}...")
    success, stdout, stderr = run_cmd(f"stty -f {port}")
    if success:
        print(stdout)
    else:
        print(f"Error: {stderr}")

def try_reset_port(port):
    """Try to reset the port"""
    print(f"\n🔄 Trying to reset {port}...")
    
    # Set DTR and RTS to reset ESP32
    try:
        import serial
        ser = serial.Serial(port, 115200, timeout=1)
        ser.dtr = False
        ser.rts = True
        time.sleep(0.1)
        ser.rts = False
        time.sleep(0.5)
        
        # Try to read
        ser.timeout = 2
        data = ser.read(1000)
        if data:
            print(f"✅ Got data after reset: {data[:100]}")
        else:
            print("❌ No data after reset")
        
        ser.close()
    except Exception as e:
        print(f"Error: {e}")

def main():
    print("=" * 60)
    print("ESP32 DEVICE CHECKER")
    print("=" * 60)
    
    # Find ports
    ports = find_ports()
    
    if not ports:
        print("\n❌ No USB serial ports found!")
        print("\nTry:")
        print("1. Check USB cable")
        print("2. Hold BOOT and press RESET")
        print("3. Try different USB port")
        sys.exit(1)
    
    print(f"\n✅ Found {len(ports)} port(s): {', '.join(ports)}")
    
    for port in ports:
        print("\n" + "=" * 60)
        print(f"CHECKING: {port}")
        print("=" * 60)
        
        # Check with various methods
        check_with_esptool(port)
        try_reset_port(port)
        check_with_stty(port)
        
        print(f"\n💡 Manual test options for {port}:")
        print(f"1. Simple cat:    cat {port}")
        print(f"2. With stty:     stty -f {port} 115200 && cat {port}")
        print(f"3. With screen:   screen {port} 115200")
        print(f"4. With minicom:  minicom -D {port} -b 115200")
        print(f"5. Force boot:    Hold BOOT, press RESET, then:")
        print(f"                  python3 -m esptool --port {port} chip_id")
    
    print("\n" + "=" * 60)
    print("RECOVERY OPTIONS")
    print("=" * 60)
    print("\n1. Run force flash script:")
    print("   python3 scripts/force_flash.py")
    print("\n2. Manual erase + flash:")
    print(f"   python3 -m esptool --chip esp32s2 --port {ports[0]} erase_flash")
    print(f"   pio run -e feather_esp32s2_display_only -t upload --upload-port {ports[0]}")
    print("\n3. Low-level flash:")
    print(f"   esptool.py --chip esp32s2 --port {ports[0]} --baud 115200 \\")
    print("     write_flash 0x10000 .pio/build/feather_esp32s2_display_only/firmware.bin")

if __name__ == "__main__":
    main()