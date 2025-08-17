import os
import sys
import importlib

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))

pe = importlib.import_module('power_estimator')  # type: ignore


def test_estimate_days_zero_current():
    assert pe.estimate_days(3500, 0, 0, 0, 7200) == 0


def test_estimate_days_reasonable_values():
    days = pe.estimate_days(3500, 0.09, 80, 45, 7200)
    assert 200 < days < 300



