#!/usr/bin/env python3
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional


@dataclass
class HistoryRecord:
    ts: int
    tempF: float
    rh: float


def parse_history_payload(s: str) -> Optional[HistoryRecord]:
    try:
        obj = json.loads(s)
        ts = int(obj["ts"])  # raises if missing or not int-ish
        tempF = float(obj["tempF"])  # numeric in firmware JSON
        rh = float(obj["rh"])  # integer printed, still parse as float
        return HistoryRecord(ts=ts, tempF=tempF, rh=rh)
    except Exception:
        return None


if __name__ == "__main__":
    sample = '{"ts":1710000000,"tempF":72.5,"rh":47}'
    print(parse_history_payload(sample))


