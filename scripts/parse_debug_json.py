#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from typing import Optional


@dataclass
class DebugRecord:
    ms_boot_to_wifi: Optional[int] = None
    ms_wifi_to_mqtt: Optional[int] = None
    ms_sensor_read: Optional[int] = None
    ms_publish: Optional[int] = None
    sleep_scheduled_ms: Optional[int] = None
    deep_sleep_us: Optional[int] = None
    timeouts: Optional[int] = None
    reset_reason: Optional[str] = None
    wakeup_cause: Optional[str] = None


def parse_debug_payload(payload: str) -> Optional[DebugRecord]:
    try:
        data = json.loads(payload)
    except Exception:
        return None
    rec = DebugRecord()
    # Safe extraction of known fields; tolerate partial payloads
    for k in (
        "ms_boot_to_wifi",
        "ms_wifi_to_mqtt",
        "ms_sensor_read",
        "ms_publish",
        "sleep_scheduled_ms",
        "deep_sleep_us",
        "timeouts",
    ):
        if k in data and isinstance(data[k], (int, float)):
            setattr(rec, k, int(data[k]))
    for k in ("reset_reason", "wakeup_cause"):
        if k in data and isinstance(data[k], str):
            setattr(rec, k, data[k])
    return rec


def main() -> None:
    ap = argparse.ArgumentParser(
        description=(
            "Parse a single debug JSON payload and render a summary"
        )
    )
    ap.add_argument("payload", help="JSON string")
    args = ap.parse_args()
    rec = parse_debug_payload(args.payload)
    if not rec:
        print("ERR: invalid JSON")
        raise SystemExit(1)
    print(rec)


if __name__ == "__main__":
    main()


