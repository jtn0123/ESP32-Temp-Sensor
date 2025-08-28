#!/usr/bin/env python3
import argparse
import glob
import os
import subprocess
import sys


def run(cmd: list[str]) -> int:
    print("$", " ".join(cmd))
    return subprocess.call(cmd)


def find_usb_ports():
    """Find USB serial ports, excluding Bluetooth ports."""
    # Common patterns for USB serial ports on different platforms
    patterns = [
        "/dev/tty.usbmodem*",      # macOS USB
        "/dev/ttyUSB*",            # Linux USB
        "/dev/ttyACM*",            # Linux USB ACM
        "/dev/cu.usbserial*",      # macOS USB serial
        "/dev/cu.usbmodem*",       # macOS USB modem
    ]
    
    # Patterns to exclude (Bluetooth and other non-USB)
    exclude_patterns = [
        "*Bluetooth*",
        "*bluetooth*", 
        "*BT*",
        "*Wireless*",
        "*AirPod*",
        "*debug*",
    ]
    
    ports = []
    for pattern in patterns:
        ports.extend(glob.glob(pattern))
    
    # Filter out excluded patterns
    filtered_ports = []
    for port in ports:
        skip = False
        for exclude in exclude_patterns:
            if exclude.replace('*', '') in port:
                skip = True
                break
        if not skip:
            filtered_ports.append(port)
    
    return sorted(set(filtered_ports))  # Remove duplicates and sort


def list_ports_command():
    """List available USB ports for user reference."""
    ports = find_usb_ports()
    if ports:
        print("Found USB serial ports:")
        for i, port in enumerate(ports, 1):
            print(f"  {i}. {port}")
        return ports
    else:
        print("No USB serial ports found.")
        print("\nTroubleshooting:")
        print("1. Make sure your ESP32 is connected via USB")
        print("2. Check if the device appears with: ls /dev/tty.*")
        print("3. On macOS, look for /dev/tty.usbmodem* or /dev/cu.usbmodem*")
        print("4. On Linux, look for /dev/ttyUSB* or /dev/ttyACM*")
        print("\nAll available serial ports (including non-USB):")
        all_ports = glob.glob("/dev/tty.*") + glob.glob("/dev/cu.*")
        # Filter out obviously non-serial ports
        filtered = [p for p in all_ports if not any(x in p for x in 
                   ['Bluetooth', 'debug', 'AirPod', 'Wireless', 'lpss'])]
        if filtered:
            for port in sorted(filtered)[:10]:  # Limit to first 10
                print(f"  - {port}")
        else:
            print("  (none found)")
        return []


def main() -> int:
    parser = argparse.ArgumentParser(description="Flash ESP32 firmware with common modes")
    parser.add_argument(
        "--port",
        help=(
            "Serial port (e.g. /dev/tty.usbmodem101). "
            "If omitted, will auto-detect USB ports (excluding Bluetooth)."
        ),
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available USB serial ports and exit",
    )
    parser.add_argument(
        "--mode",
        choices=["3m", "1h", "2h", "always"],
        default="1h",
        help="Sleep behavior: 3m, 1h (default), 2h, or always (no sleep)",
    )
    # Default to the stable display-only firmware. The legacy "full" env is
    # intentionally not exposed here to avoid accidentally flashing the
    # experimental spec-renderer build.
    parser.add_argument(
        "--env",
        choices=["display", "headless"],
        default="display",
        help=(
            "Select PlatformIO environment: display (display-only fast loop, "
            "default) or headless (no display)."
        ),
    )
    parser.add_argument(
        "--build-only",
        action="store_true",
        help="Only build; do not upload",
    )
    args = parser.parse_args()
    
    # Handle --list flag
    if args.list:
        list_ports_command()
        return 0

    proj = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    arduino_dir = os.path.join(proj, "firmware", "arduino")

    # Choose base env: display-only or headless (full is intentionally omitted)
    if args.env == "headless":
        env = "feather_esp32s2_headless"
    else:
        env = "feather_esp32s2_display_only"

    # Build EXTRA_FLAGS to control sleep behavior and wake interval
    extra_flags = []
    if args.mode == "always":
        extra_flags.append("-DDEV_NO_SLEEP=1")
    else:
        # Use WAKE_INTERVAL to override generated_config via environment
        if args.mode == "3m":
            os.environ["WAKE_INTERVAL"] = "3m"
        elif args.mode == "1h":
            os.environ["WAKE_INTERVAL"] = "1h"
        elif args.mode == "2h":
            os.environ["WAKE_INTERVAL"] = "2h"

    # Pass dynamic flags into PlatformIO via EXTRA_FLAGS
    if extra_flags:
        os.environ["EXTRA_FLAGS"] = " ".join(extra_flags)

    base = ["pio", "run", "-d", arduino_dir, "-e", env]
    if args.build_only:
        return run(base)

    upload = base + ["-t", "upload"]
    
    # Handle port selection
    if args.port:
        # User specified a port explicitly
        upload += ["--upload-port", args.port]
        print(f"Using specified port: {args.port}")
    else:
        # Try to auto-detect USB port
        ports = find_usb_ports()
        if not ports:
            print("\nERROR: No USB serial ports found!")
            print("Please connect your ESP32 via USB and try again.")
            print("You can also specify a port manually with --port")
            return 1
        elif len(ports) == 1:
            # Only one port found, use it
            upload += ["--upload-port", ports[0]]
            print(f"Auto-detected USB port: {ports[0]}")
        else:
            # Multiple ports found, ask user to choose
            print("\nMultiple USB ports found:")
            for i, port in enumerate(ports, 1):
                print(f"  {i}. {port}")
            print("\nPlease specify which port to use with --port")
            print(f"Example: {sys.argv[0]} --port {ports[0]}")
            return 1
    
    return run(upload)


if __name__ == "__main__":
    sys.exit(main())
