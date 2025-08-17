import os
import sys

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))

import power_estimator as pe  # type: ignore


def test_monotonic_capacity():
    base = pe.estimate_days(3000, 0.1, 80, 45, 7200)
    higher = pe.estimate_days(6000, 0.1, 80, 45, 7200)
    assert higher > base


def test_monotonic_sleep_current():
    low = pe.estimate_days(3500, 0.05, 80, 45, 7200)
    high = pe.estimate_days(3500, 0.2, 80, 45, 7200)
    assert low > high


def test_monotonic_awake_time():
    short = pe.estimate_days(3500, 0.09, 80, 30, 7200)
    long = pe.estimate_days(3500, 0.09, 80, 90, 7200)
    assert short > long


def test_invalid_inputs_return_zero():
    assert pe.estimate_days(0, 0.0, 0.0, 0.0, 7200) == 0
    assert pe.estimate_days(3500, -1.0, -2.0, -3.0, 7200) >= 0


