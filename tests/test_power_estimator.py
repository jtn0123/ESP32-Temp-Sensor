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


def test_estimate_days_schedules_and_currents():
    capacity = 3500
    awake_seconds = 45
    # Currents from README ranges
    sleep_current = 0.09
    active_currents = [60, 80, 100]
    intervals = {
        "1h": 3600,
        "2h": 7200,
        "4h": 14400,
    }
    # Expect longer intervals and lower active current => longer days
    results = {}
    for label, interval in intervals.items():
        for active in active_currents:
            days = pe.estimate_days(capacity, sleep_current, active, awake_seconds, interval)
            # Sanity bounds: within plausible device ranges
            assert days > 0
            results[(label, active)] = days
    # Monotonic checks across active current for fixed interval
    for label in intervals.keys():
        assert results[(label, 60)] > results[(label, 80)] > results[(label, 100)]
    # Monotonic checks across intervals for fixed active current
    for active in active_currents:
        assert results[("4h", active)] > results[("2h", active)] > results[("1h", active)]


def test_estimate_days_scaled_with_capacity():
    base = pe.estimate_days(3500, 0.09, 80, 45, 7200)
    doubled = pe.estimate_days(7000, 0.09, 80, 45, 7200)
    assert 1.9 * base < doubled < 2.1 * base
