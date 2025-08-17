import importlib.util
import os

ROOT = os.path.dirname(os.path.dirname(__file__))
_scripts = os.path.join(ROOT, "scripts")
_module_path = os.path.join(_scripts, "power_estimator.py")
_spec = importlib.util.spec_from_file_location("power_estimator", _module_path)
pe = importlib.util.module_from_spec(_spec)  # type: ignore
_spec.loader.exec_module(pe)  # type: ignore


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
