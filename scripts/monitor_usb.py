#!/usr/bin/env python3
import argparse
from dataclasses import dataclass
import json
import sys
import time

try:
    import serial  # type: ignore
except Exception:  # pragma: no cover - optional at import time
    serial = None  # type: ignore


@dataclass
class Metrics:
    ip: str
    tempC: float | None = None
    tempF: float | None = None
    rhPct: float | None = None
    wifi: bool = False
    mqtt: bool = False
    v: float | None = None
    pct: int | None = None


def parse_metrics_line(line: str) -> Metrics | None:
    try:
        obj = json.loads(line)
        if obj.get("event") != "metrics":
            return None
        return Metrics(
            ip=obj.get("ip") or "0.0.0.0",
            tempC=float(obj["tempC"]) if obj.get("tempC") is not None else None,
            tempF=float(obj["tempF"]) if obj.get("tempF") is not None else None,
            rhPct=float(obj["rhPct"]) if obj.get("rhPct") is not None else None,
            wifi=bool(obj.get("wifi")),
            mqtt=bool(obj.get("mqtt")),
            v=float(obj["v"]) if obj.get("v") is not None else None,
            pct=int(obj["pct"]) if obj.get("pct") is not None else None,
        )
    except Exception:
        return None


def format_metrics(m: Metrics) -> str:
    parts: list[str] = []
    parts.append(f"ip={m.ip}")
    if m.tempC is not None:
        parts.append(f"tempC={m.tempC:.2f}")
    # Prefer provided tempF, fallback to derived from tempC
    if m.tempF is not None:
        parts.append(f"tempF={m.tempF:.2f}")
    elif m.tempC is not None:
        parts.append(f"tempF={(m.tempC * 9/5) + 32:.2f}")
    if m.rhPct is not None:
        parts.append(f"rh%={m.rhPct:.0f}")
    parts.append(f"wifi={'up' if m.wifi else 'down'}")
    parts.append(f"mqtt={'up' if m.mqtt else 'down'}")
    if m.v is not None:
        parts.append(f"battV={m.v:.2f}")
    if m.pct is not None:
        parts.append(f"batt%={m.pct}")
    return "  ".join(parts)


def main() -> int:
    ap = argparse.ArgumentParser(description="Monitor ESP32 metrics JSON over USB serial")
    ap.add_argument(
        "port",
        help=(
            "Serial port (e.g. /dev/cu.usbmodem*, /dev/tty.usbserial*)"
        ),
    )
    ap.add_argument(
        "--baud",
        type=int,
        default=115200,
        help=("Baud rate (default: 115200)"),
    )
    ap.add_argument(
        "--raw",
        action="store_true",
        help=("Print raw lines in addition to parsed summary"),
    )
    args = ap.parse_args()

    if serial is None:
        print("pyserial is not installed. Install with: pip3 install pyserial", file=sys.stderr)
        return 2
    try:
        with serial.Serial(args.port, args.baud, timeout=1) as ser:  # type: ignore[attr-defined]
            # Give the port a moment after opening
            time.sleep(0.1)
            print(f"Connected to {args.port} @ {args.baud}")
            while True:
                line = ser.readline().decode(errors="ignore").strip()
                if not line:
                    continue
                if args.raw:
                    print(line)
                m = parse_metrics_line(line)
                if m:
                    print(format_metrics(m))
    except KeyboardInterrupt:
        return 0
    except serial.SerialException as e:
        print(f"Serial error: {e}", file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())


