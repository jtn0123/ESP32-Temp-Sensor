import importlib.util
import os

ROOT = os.path.dirname(os.path.dirname(__file__))
_scripts = os.path.join(ROOT, "scripts")
_module_path = os.path.join(_scripts, "power_estimator.py")
_spec = importlib.util.spec_from_file_location("power_estimator", _module_path)
pe = importlib.util.module_from_spec(_spec)  # type: ignore
_spec.loader.exec_module(pe)  # type: ignore


def test_estimate_days_zero_current():
    assert pe.estimate_days(3500, 0, 0, 0, 7200) == 0


def test_estimate_days_reasonable_values():
    days = pe.estimate_days(3500, 0.09, 80, 45, 7200)
    assert 200 < days < 300
