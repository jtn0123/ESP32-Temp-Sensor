#!/usr/bin/env python3
import argparse
import os
import subprocess
import sys


def run(cmd: list[str]) -> int:
    print("$", " ".join(cmd))
    return subprocess.call(cmd)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Flash ESP32 firmware with common modes"
    )
    parser.add_argument(
        "--port",
        help=(
            "Serial port (e.g. /dev/cu.usbmodem101). "
            "If omitted, auto-detect is used by PlatformIO."
        ),
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
    if args.port:
        upload += ["--upload-port", args.port]
    return run(upload)


if __name__ == "__main__":
    sys.exit(main())
