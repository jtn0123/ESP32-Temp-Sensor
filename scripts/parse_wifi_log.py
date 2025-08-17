#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable, Optional

CONNECTING_RE = re.compile(r"^WiFi: connecting to (.+)\.\.\.")
PREF_BSSID_RE = re.compile(r"^WiFi: preferring BSSID ([0-9a-fA-F:]{17})")
FALLBACK_RE = re.compile(r"^WiFi: BSSID join slow; falling back to SSID-only")
CONNECTED_RE = re.compile(r"^WiFi: connected, IP ([0-9\.]+) RSSI (-?\d+) dBm")
TIME_MS_RE = re.compile(r"^(\d+): ")  # optional external timestamp prefix like "1234: "


@dataclass
class WifiJoin:
    ssid: Optional[str] = None
    preferred_bssid: Optional[str] = None
    fell_back: bool = False
    ip: Optional[str] = None
    rssi_dbm: Optional[int] = None
    # If timestamps exist in the log prefix, this can be populated by parse()
    started_ms: Optional[int] = None
    connected_ms: Optional[int] = None

    @property
    def join_ms(self) -> Optional[int]:
        if self.started_ms is None or self.connected_ms is None:
            return None
        return max(0, self.connected_ms - self.started_ms)


def parse(lines: Iterable[str]) -> WifiJoin:
    evt = WifiJoin()
    for raw in lines:
        line = raw.strip()
        # optional numeric ms prefix
        ts: Optional[int] = None
        m_ts = TIME_MS_RE.match(line)
        if m_ts:
            try:
                ts = int(m_ts.group(1))
            except Exception:
                ts = None
            line = line[m_ts.end():]

        m = CONNECTING_RE.search(line)
        if m:
            evt.ssid = m.group(1)
            if ts is not None:
                evt.started_ms = ts
            continue
        m = PREF_BSSID_RE.search(line)
        if m:
            evt.preferred_bssid = m.group(1).lower()
            continue
        if FALLBACK_RE.search(line):
            evt.fell_back = True
            continue
        m = CONNECTED_RE.search(line)
        if m:
            evt.ip = m.group(1)
            try:
                evt.rssi_dbm = int(m.group(2))
            except Exception:
                evt.rssi_dbm = None
            if ts is not None:
                evt.connected_ms = ts
            continue
    return evt


if __name__ == "__main__":
    # Manual quick test
    sample = [
        "WiFi: connecting to MySSID...",
        "WiFi: preferring BSSID aa:bb:cc:dd:ee:ff",
        "WiFi: connected, IP 192.168.1.42 RSSI -62 dBm",
    ]
    print(parse(sample))


