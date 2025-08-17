#!/usr/bin/env python3
import re
import sys

AWAKE_RE = re.compile(r"Awake ms:\s*(\d+)")
SLEEP_RE = re.compile(r"Sleeping for (\d+)s")


def parse(lines):

    awake_ms = None
    sleep_s = None
    for line in lines:
        m = AWAKE_RE.search(line)
        if m:
            awake_ms = int(m.group(1))
        m = SLEEP_RE.search(line)
        if m:
            sleep_s = int(m.group(1))
    return awake_ms, sleep_s


def main():

    if len(sys.argv) < 2:
        print("Usage: parse_awake_log.py <serial_log.txt> [--max-awake-ms 45000] [--sleep-s 7200]")
        return 2
    path = sys.argv[1]
    max_awake_ms = 45000
    expected_sleep_s = None
    for i, arg in enumerate(sys.argv[2:], start=2):
        if arg == "--max-awake-ms" and i + 1 < len(sys.argv):
            max_awake_ms = int(sys.argv[i + 1])
        elif arg == "--sleep-s" and i + 1 < len(sys.argv):
            expected_sleep_s = int(sys.argv[i + 1])
    with open(path, "r") as f:
        awake_ms, sleep_s = parse(f)
    if awake_ms is None:
        print("ERROR: No 'Awake ms:' line found")
        return 1
    if awake_ms > max_awake_ms:
        print(f"ERROR: Awake duration {awake_ms} ms exceeds limit {max_awake_ms} ms")
        return 1
    if expected_sleep_s is not None and sleep_s != expected_sleep_s:
        print(f"ERROR: Sleep seconds {sleep_s} != expected {expected_sleep_s}")
        return 1
    print(f"OK: Awake {awake_ms} ms; Sleep {sleep_s if sleep_s is not None else 'n/a'} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
