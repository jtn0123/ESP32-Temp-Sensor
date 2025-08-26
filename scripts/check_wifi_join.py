#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
import time
from typing import List

from scripts.parse_wifi_log import parse

try:
    import serial
except Exception:  # pragma: no cover - optional
    serial = None


def read_until_connected_from_serial(port: str, baud: int, timeout_s: float) -> List[str]:
    if serial is None:
        raise RuntimeError("pyserial not installed. pip install pyserial")
    end_at = time.time() + timeout_s
    lines: List[str] = []
    with serial.Serial(port, baud, timeout=1) as ser:
        time.sleep(0.1)
        while time.time() < end_at:
            raw = ser.readline().decode(errors="ignore")
            if not raw:
                continue
            line = raw.strip()
            lines.append(line)
            if line.startswith("WiFi: connected, IP "):
                break
    return lines


def main() -> int:
    ap = argparse.ArgumentParser(description="Check Wi-Fi join time from serial or log file")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--port", help="Serial port (e.g. /dev/cu.usbmodem*, /dev/tty.usbserial*)")
    g.add_argument("--from-file", dest="from_file", help="Path to a text log file to parse")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--timeout", type=float, default=20.0, help="Serial wait timeout seconds")
    ap.add_argument("--max-ms", type=int, default=6000, help="Maximum acceptable join time in ms")
    args = ap.parse_args()

    lines: List[str]
    if args.from_file:
        with open(args.from_file, "r", encoding="utf-8", errors="ignore") as f:
            lines = [ln.rstrip("\n") for ln in f]
    else:
        lines = read_until_connected_from_serial(args.port, args.baud, args.timeout)

    evt = parse(lines)
    print(f"ssid={evt.ssid} ip={evt.ip} rssi={evt.rssi_dbm} join_ms={evt.join_ms}")
    if evt.ip is None:
        print("ERROR: did not observe WiFi connected in logs", file=sys.stderr)
        return 2
    if evt.join_ms is not None and evt.join_ms > args.max_ms:
        print(f"ERROR: join_ms {evt.join_ms} exceeds max {args.max_ms}", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
