import os
import sys

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))

import power_estimator as pe  # type: ignore


def test_estimate_days_zero_current():
    assert pe.estimate_days(3500, 0, 0, 0, 7200) == 0


def test_estimate_days_reasonable_values():
    days = pe.estimate_days(3500, 0.09, 80, 45, 7200)
    assert 200 < days < 300



