#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
import time

try:
    import serial  # type: ignore
except Exception:  # pragma: no cover - optional
    serial = None  # type: ignore


def wait_for_lines(port: str, baud: int, timeout_s: float) -> tuple[
    bool, bool, list[str]
]:
    if serial is None:
        raise RuntimeError("pyserial not installed. pip install pyserial")
    end_at = time.time() + timeout_s
    saw_prov = False
    saw_connected = False
    lines: list[str] = []
    with serial.Serial(port, baud, timeout=1) as ser:  # type: ignore[
        attr-defined
    ]
        time.sleep(0.1)
        # send wificlear to force provisioning mode
        ser.write(b"wificlear\n")
        time.sleep(0.1)
        while time.time() < end_at:
            raw = ser.readline().decode(errors="ignore")
            if not raw:
                continue
            line = raw.strip()
            lines.append(line)
            if line.startswith("WiFiProv: starting provisioning"):
                saw_prov = True
            if line.startswith("WiFi: connected, IP "):
                saw_connected = True
                break
    return saw_prov, saw_connected, lines


def main() -> int:
    ap = argparse.ArgumentParser(
        description=("Check provisioning start and Wi-Fi connect via serial")
    )
    ap.add_argument("port")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--timeout", type=float, default=60.0)
    args = ap.parse_args()

    saw_prov, saw_connected, lines = wait_for_lines(
        args.port, args.baud, args.timeout
    )
    print("Observed provisioning:", saw_prov)
    print("Observed connect:", saw_connected)
    if not saw_prov:
        print("ERROR: did not observe provisioning start", file=sys.stderr)
        return 2
    if not saw_connected:
        print(
            "ERROR: did not observe WiFi connected after provisioning",
            file=sys.stderr
        )
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
