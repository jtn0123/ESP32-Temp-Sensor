#!/usr/bin/env python3
import argparse


def estimate_days(
    capacity_mAh: float,
    sleep_current_mA: float,
    active_current_mA: float,
    awake_seconds: float,
    interval_seconds: float,
) -> float:
    avg_mA = (
        active_current_mA * awake_seconds
        + sleep_current_mA * max(0.0, interval_seconds - awake_seconds)
    ) / interval_seconds
    if avg_mA <= 0:
        return 0.0
    hours = capacity_mAh / avg_mA
    return hours / 24.0

def main():
    p = argparse.ArgumentParser(description="Estimate runtime days for ESP32 eInk Room Node")
    p.add_argument("--capacity", type=float, default=3500, help="Battery capacity mAh (default 3500)")
    p.add_argument("--sleep_mA", type=float, default=0.09, help="Sleep current mA (default 0.09)")
    p.add_argument("--active_mA", type=float, default=80, help="Active current mA (default 80)")
    p.add_argument("--awake_s", type=float, default=45, help="Awake seconds per cycle (default 45)")
    p.add_argument("--interval_s", type=float, default=7200, help="Interval seconds (default 7200 = 2h)")
    args = p.parse_args()

    days = estimate_days(args.capacity, args.sleep_mA, args.active_mA, args.awake_s, args.interval_s)
    print(f"Estimated runtime: {days:.1f} days")

if __name__ == "__main__":
    main()


