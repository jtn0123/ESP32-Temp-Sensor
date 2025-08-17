#!/usr/bin/env python3
import argparse
import os
import subprocess
import sys


def run(cmd: list[str]) -> int:
    print("$", " ".join(cmd))
    return subprocess.call(cmd)


def main() -> int:
    parser = argparse.ArgumentParser(description="Flash ESP32 firmware with common modes")
    parser.add_argument(
        "--port",
        help=(
            "Serial port (e.g. /dev/cu.usbmodem101). "
            "If omitted, auto-detect is used by PlatformIO."
        ),
    )
    parser.add_argument(
        "--mode",
        choices=["1h", "3m", "always"],
        default="1h",
        help="Sleep behavior: 1h (default), 3m cycle, or always (no sleep)",
    )
    parser.add_argument(
        "--build-only",
        action="store_true",
        help="Only build; do not upload",
    )
    args = parser.parse_args()

    proj = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    arduino_dir = os.path.join(proj, "firmware", "arduino")

    if args.mode == "1h":
        env = "feather_esp32s2_headless_1h"
    elif args.mode == "3m":
        env = "feather_esp32s2_dev2"
    else:
        env = "feather_esp32s2_headless_always"

    base = ["pio", "run", "-d", arduino_dir, "-e", env]
    if args.build_only:
        return run(base)

    upload = base + ["-t", "upload"]
    if args.port:
        upload += ["--upload-port", args.port]
    return run(upload)


if __name__ == "__main__":
    sys.exit(main())


