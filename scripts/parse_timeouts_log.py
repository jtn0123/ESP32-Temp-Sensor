#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from typing import Iterable


SENSOR_RE = re.compile(r"^Timeout: sensor read(?: \(secondary\))? exceeded budget ms=(\d+) budget=(\d+)")
FETCH_RE = re.compile(r"^Timeout: retained fetch budget reached ms=(\d+) budget=(\d+)")
DISPLAY_RE = re.compile(r"^Timeout: display phase exceeded budget ms=(\d+) budget=(\d+)")
PUBLISH_RE = re.compile(r"^Timeout: publish exceeded budget ms=(\d+) budget=(\d+)")


@dataclass
class TimeoutSummary:
    sensor_count: int = 0
    fetch_count: int = 0
    display_count: int = 0
    publish_count: int = 0


def parse(lines: Iterable[str]) -> TimeoutSummary:
    s = TimeoutSummary()
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        if SENSOR_RE.search(line):
            s.sensor_count += 1
            continue
        if FETCH_RE.search(line):
            s.fetch_count += 1
            continue
        if DISPLAY_RE.search(line):
            s.display_count += 1
            continue
        if PUBLISH_RE.search(line):
            s.publish_count += 1
            continue
    return s


def main() -> None:
    ap = argparse.ArgumentParser(description="Parse ESP32 timeout logs and summarize counts")
    ap.add_argument("logfile", help="Path to serial log file to parse (or - for stdin)")
    args = ap.parse_args()

    if args.logfile == "-":
        import sys
        lines = sys.stdin
    else:
        lines = open(args.logfile, "r", encoding="utf-8", errors="ignore")
    try:
        s = parse(lines)
        print(f"sensor={s.sensor_count} fetch={s.fetch_count} display={s.display_count} publish={s.publish_count}")
    finally:
        try:
            lines.close()  # type: ignore[attr-defined]
        except Exception:
            pass


if __name__ == "__main__":
    main()


