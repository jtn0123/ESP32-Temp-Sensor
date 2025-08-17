#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable, Optional

QUEUED_RE = re.compile(r"^Offline: queued seq=(\d+) ts=(\d+) \(C=([0-9\.-]+) RH=([0-9\.-]+)\)")
DRAIN_RE = re.compile(r"^Offline: draining (\d+) samples \(tail=(\d+) head=(\d+)\)")
SNTP_OK_RE = re.compile(r"^Time: SNTP sync ok")
SNTP_TO_RE = re.compile(r"^Time: SNTP sync timeout")


@dataclass
class OfflineEvent:
    queued: int = 0
    drained: int = 0
    last_tail: Optional[int] = None
    last_head: Optional[int] = None
    saw_sntp_ok: bool = False
    saw_sntp_timeout: bool = False


def parse(lines: Iterable[str]) -> OfflineEvent:
    evt = OfflineEvent()
    for raw in lines:
        line = raw.strip()
        m = QUEUED_RE.search(line)
        if m:
            evt.queued += 1
            continue
        m = DRAIN_RE.search(line)
        if m:
            try:
                evt.drained += int(m.group(1))
                evt.last_tail = int(m.group(2))
                evt.last_head = int(m.group(3))
            except Exception:
                pass
            continue
        if SNTP_OK_RE.search(line):
            evt.saw_sntp_ok = True
            continue
        if SNTP_TO_RE.search(line):
            evt.saw_sntp_timeout = True
            continue
    return evt


if __name__ == "__main__":
    sample = [
        "Offline: queued seq=0 ts=1710000000 (C=21.4 RH=43)",
        "Offline: draining 10 samples (tail=0 head=10)",
        "Time: SNTP sync ok",
    ]
    print(parse(sample))
