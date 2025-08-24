import importlib.util
import os

# Load power estimator module
ROOT = os.path.dirname(os.path.dirname(__file__))
_scripts = os.path.join(ROOT, "scripts")
_module_path = os.path.join(_scripts, "power_estimator.py")
_spec = importlib.util.spec_from_file_location("power_estimator", _module_path)
pe = importlib.util.module_from_spec(_spec)  # type: ignore
_spec.loader.exec_module(pe)  # type: ignore

# Edge case test scenarios
POWER_EDGE_CASES = [
    # Zero/invalid inputs
    {
        "capacity_mAh": 0, "sleep_current_mA": 0.09, "active_current_mA": 80,
        "active_seconds": 45, "wake_interval_sec": 3600, "should_error": True
    },
    {
        "capacity_mAh": 3500, "sleep_current_mA": 0, "active_current_mA": 80,
        "active_seconds": 45, "wake_interval_sec": 3600, "should_error": False
    },
    {
        "capacity_mAh": 3500, "sleep_current_mA": 0.09, "active_current_mA": 0,
        "active_seconds": 45, "wake_interval_sec": 3600, "should_error": False
    },
    {
        "capacity_mAh": 3500, "sleep_current_mA": 0.09, "active_current_mA": 80,
        "active_seconds": 0, "wake_interval_sec": 3600, "should_error": False
    },

    # Extremely high values (unrealistic but should handle gracefully)
    {
        "capacity_mAh": 999999, "sleep_current_mA": 0.09, "active_current_mA": 80,
        "active_seconds": 45, "wake_interval_sec": 3600, "should_error": False
    },
    {
        "capacity_mAh": 3500, "sleep_current_mA": 999, "active_current_mA": 80,
        "active_seconds": 45, "wake_interval_sec": 3600, "should_error": False
    },
    {
        "capacity_mAh": 3500, "sleep_current_mA": 0.09, "active_current_mA": 9999,
        "active_seconds": 45, "wake_interval_sec": 3600, "should_error": False
    },
    {
        "capacity_mAh": 3500, "sleep_current_mA": 0.09, "active_current_mA": 80,
        "active_seconds": 99999, "wake_interval_sec": 3600, "should_error": False
    },

    # Very short wake intervals (stress test)
    {
        "capacity_mAh": 3500, "sleep_current_mA": 0.09, "active_current_mA": 80,
        "active_seconds": 45, "wake_interval_sec": 60, "should_error": False
    },
    {
        "capacity_mAh": 3500, "sleep_current_mA": 0.09, "active_current_mA": 80,
        "active_seconds": 45, "wake_interval_sec": 1, "should_error": False
    },

    # Negative values (should handle gracefully)
    {
        "capacity_mAh": -1000, "sleep_current_mA": 0.09, "active_current_mA": 80,
        "active_seconds": 45, "wake_interval_sec": 3600, "should_error": True
    },
    {
        "capacity_mAh": 3500, "sleep_current_mA": -0.1, "active_current_mA": 80,
        "active_seconds": 45, "wake_interval_sec": 3600, "should_error": True
    },
    {
        "capacity_mAh": 3500, "sleep_current_mA": 0.09, "active_current_mA": -10,
        "active_seconds": 45, "wake_interval_sec": 3600, "should_error": True
    },
    {
        "capacity_mAh": 3500, "sleep_current_mA": 0.09, "active_current_mA": 80,
        "active_seconds": -5, "wake_interval_sec": 3600, "should_error": True
    },

    # Very small values
    {
        "capacity_mAh": 1, "sleep_current_mA": 0.001, "active_current_mA": 1,
        "active_seconds": 1, "wake_interval_sec": 3600, "should_error": False
    },
    {
        "capacity_mAh": 3500, "sleep_current_mA": 0.0001, "active_current_mA": 80,
        "active_seconds": 45, "wake_interval_sec": 3600, "should_error": False
    },
]

# Battery chemistry scenarios
BATTERY_CHEMISTRY_SCENARIOS = [
    {
        "name": "LiPo 3.7V", "capacity_mAh": 3500, "nominal_voltage": 3.7,
        "sleep_current_mA": 0.09, "active_current_mA": 80
    },
    {
        "name": "Li-ion 18650", "capacity_mAh": 2500, "nominal_voltage": 3.6,
        "sleep_current_mA": 0.05, "active_current_mA": 120
    },
    {
        "name": "Alkaline AA (2x)", "capacity_mAh": 2400, "nominal_voltage": 3.0,
        "sleep_current_mA": 0.15, "active_current_mA": 60
    },
    {
        "name": "NiMH AA (4x)", "capacity_mAh": 2000, "nominal_voltage": 4.8,
        "sleep_current_mA": 0.8, "active_current_mA": 100
    },
]

# Environmental temperature scenarios
TEMPERATURE_SCENARIOS = [
    {"temp_c": -20, "capacity_multiplier": 0.6, "description": "Cold weather"},
    {"temp_c": 0, "capacity_multiplier": 0.8, "description": "Freezing"},
    {"temp_c": 20, "capacity_multiplier": 1.0, "description": "Room temperature"},
    {"temp_c": 40, "capacity_multiplier": 0.9, "description": "Hot weather"},
    {"temp_c": 60, "capacity_multiplier": 0.7, "description": "Very hot"},
]

def test_power_estimation_edge_cases():
    """Test power estimation with edge case inputs"""

    for i, case in enumerate(POWER_EDGE_CASES):
        capacity = case["capacity_mAh"]
        sleep_current = case["sleep_current_mA"]
        active_current = case["active_current_mA"]
        active_seconds = case["active_seconds"]
        wake_interval = case["wake_interval_sec"]

        if case["should_error"]:
            # Should either raise an exception or return a sensible error value
            try:
                days = pe.estimate_days(capacity, sleep_current, active_current, active_seconds, wake_interval)
                # If no exception, should return a reasonable value or 0 for invalid inputs
                assert days >= 0, f"Case {i}: Negative days for invalid input"
            except (ValueError, ZeroDivisionError):
                # Expected for invalid inputs
                pass
        else:
            # Should complete without error
            days = pe.estimate_days(capacity, sleep_current, active_current, active_seconds, wake_interval)
            assert days >= 0, f"Case {i}: Negative days for valid input"
            assert not (days == float('inf')), f"Case {i}: Infinite days"

def test_power_estimation_mathematical_correctness():
    """Test mathematical correctness of power estimation"""

    # Test with known values
    capacity = 3500  # mAh
    sleep_current = 0.09  # mA
    active_current = 80  # mA
    active_seconds = 45  # seconds
    wake_interval = 3600  # seconds (1 hour)

    days = pe.estimate_days(capacity, sleep_current, active_current, active_seconds, wake_interval)

    # Manual calculation for verification
    # Total capacity in mAh = 3500
    # Sleep time per hour = 3600 - 45 = 3555 seconds
    # Active energy per hour = 80mA * 45s = 3600 mAs = 1 mAh
    # Sleep energy per hour = 0.09mA * 3555s ≈ 0.31995 mAs ≈ 0.00032 mAh
    # Total energy per hour ≈ 1.00032 mAh
    # Days = 3500 / (24 * 1.00032) ≈ 3500 / 24.00768 ≈ 145.8

    assert 130 < days < 160, f"Expected ~145 days, got {days}"

def test_power_estimation_scaling():
    """Test that power estimates scale correctly with input changes"""

    base_capacity = 3500
    base_sleep = 0.09
    base_active = 80
    base_active_time = 45
    base_interval = 3600

    base_days = pe.estimate_days(base_capacity, base_sleep, base_active, base_active_time, base_interval)

    # Double capacity should roughly double days
    double_capacity_days = pe.estimate_days(base_capacity * 2, base_sleep, base_active, base_active_time, base_interval)
    assert 1.9 * base_days < double_capacity_days < 2.1 * base_days

    # Half capacity should roughly halve days
    half_capacity_days = pe.estimate_days(base_capacity / 2, base_sleep, base_active, base_active_time, base_interval)
    assert 0.45 * base_days < half_capacity_days < 0.55 * base_days

    # Double wake interval should significantly increase days according to the model
    double_interval_days = pe.estimate_days(base_capacity, base_sleep, base_active, base_active_time, base_interval * 2)
    # Expected ratio based on average current formula:
    # avg = sleep + (active - sleep) * (awake / interval)
    avg1 = base_sleep + (base_active - base_sleep) * (base_active_time / base_interval)
    avg2 = base_sleep + (base_active - base_sleep) * (base_active_time / (base_interval * 2))
    expected_ratio = avg1 / avg2
    ratio = double_interval_days / base_days
    # Allow a small tolerance
    assert 0.95 * expected_ratio < ratio < 1.05 * expected_ratio

def test_power_estimation_current_relationships():
    """Test that higher currents result in shorter battery life"""

    capacity = 3500
    sleep_current = 0.09
    active_seconds = 45
    wake_interval = 3600

    # Test active current variations
    low_active = pe.estimate_days(capacity, sleep_current, 50, active_seconds, wake_interval)
    medium_active = pe.estimate_days(capacity, sleep_current, 100, active_seconds, wake_interval)
    high_active = pe.estimate_days(capacity, sleep_current, 200, active_seconds, wake_interval)

    # Higher active current should result in shorter battery life
    assert low_active > medium_active > high_active

    # Test sleep current variations
    low_sleep = pe.estimate_days(capacity, 0.05, 80, active_seconds, wake_interval)
    medium_sleep = pe.estimate_days(capacity, 0.10, 80, active_seconds, wake_interval)
    high_sleep = pe.estimate_days(capacity, 0.20, 80, active_seconds, wake_interval)

    # Higher sleep current should result in shorter battery life
    assert low_sleep > medium_sleep > high_sleep

def test_power_estimation_time_relationships():
    """Test that time parameters affect battery life correctly"""

    capacity = 3500
    sleep_current = 0.09
    active_current = 80

    # Longer wake intervals should increase battery life
    short_interval = pe.estimate_days(capacity, sleep_current, active_current, 45, 1800)  # 30 min
    medium_interval = pe.estimate_days(capacity, sleep_current, active_current, 45, 3600)  # 1 hour
    long_interval = pe.estimate_days(capacity, sleep_current, active_current, 45, 7200)   # 2 hours

    assert short_interval < medium_interval < long_interval

    # Longer active time should decrease battery life
    short_active = pe.estimate_days(capacity, sleep_current, active_current, 30, 3600)
    medium_active = pe.estimate_days(capacity, sleep_current, active_current, 60, 3600)
    long_active = pe.estimate_days(capacity, sleep_current, active_current, 120, 3600)

    assert short_active > medium_active > long_active

def test_battery_chemistry_scenarios():
    """Test power estimation with different battery chemistries"""

    active_seconds = 45
    wake_interval = 3600

    for battery in BATTERY_CHEMISTRY_SCENARIOS:
        days = pe.estimate_days(
            battery["capacity_mAh"],
            battery["sleep_current_mA"],
            battery["active_current_mA"],
            active_seconds,
            wake_interval
        )

        # Should produce reasonable battery life estimates
        assert days > 0, f"{battery['name']}: Invalid days estimate"
        assert not (days == float('inf')), f"{battery['name']}: Infinite days"

        # LiPo should generally have better performance than alkaline
        # (This is a rough sanity check)
        if "LiPo" in battery["name"]:
            assert days > 50, f"{battery['name']}: LiPo should last >50 days"
        elif "Alkaline" in battery["name"]:
            assert days > 20, f"{battery['name']}: Alkaline should last >20 days"

def test_temperature_impact_estimation():
    """Test power estimation with temperature considerations"""

    # This is more of a framework for temperature-aware estimation
    # In a real implementation, you'd adjust capacity based on temperature

    base_capacity = 3500
    sleep_current = 0.09
    active_current = 80
    active_seconds = 45
    wake_interval = 3600

    for temp_scenario in TEMPERATURE_SCENARIOS:
        # Simulate temperature impact by adjusting capacity
        adjusted_capacity = base_capacity * temp_scenario["capacity_multiplier"]

        days = pe.estimate_days(adjusted_capacity, sleep_current, active_current, active_seconds, wake_interval)

        # Colder temperatures should reduce battery life
        assert days > 0, f"{temp_scenario['description']}: Invalid days estimate"

        # Very cold should have significantly reduced life
        if temp_scenario["temp_c"] == -20:
            assert days < 100, f"{temp_scenario['description']}: Should be <100 days in cold"

def test_power_estimation_precision():
    """Test precision and rounding behavior of power estimates"""

    # Test that small input changes don't cause huge output swings
    base_days = pe.estimate_days(3500, 0.09, 80, 45, 3600)

    # Small changes in current should produce proportional changes
    small_change = pe.estimate_days(3500, 0.0901, 80, 45, 3600)  # 0.11% increase
    large_change = pe.estimate_days(3500, 0.1, 80, 45, 3600)     # 11% increase

    # Small changes should have small effects
    ratio_small = small_change / base_days
    ratio_large = large_change / base_days

    assert 0.99 < ratio_small < 1.01, f"Small current change caused large effect: {ratio_small}"
    assert 0.8 < ratio_large < 1.0, f"Large current change effect: {ratio_large}"

def test_power_estimation_consistency():
    """Test that repeated calculations give consistent results"""

    # Same inputs should always give same outputs
    inputs = (3500, 0.09, 80, 45, 3600)

    results = []
    for _ in range(10):
        days = pe.estimate_days(*inputs)
        results.append(days)

    # All results should be identical
    assert len(set(results)) == 1, f"Inconsistent results: {results}"

def test_power_estimation_bounds():
    """Test that power estimates stay within reasonable bounds"""

    test_cases = [
        (100, 0.01, 10, 10, 3600),     # Small battery, low currents
        (10000, 0.5, 500, 300, 3600),  # Large battery, high currents
        (2000, 0.05, 50, 30, 1800),    # Medium, short intervals
        (5000, 0.2, 150, 60, 7200),    # Large, long intervals
    ]

    for capacity, sleep_current, active_current, active_seconds, wake_interval in test_cases:
        days = pe.estimate_days(capacity, sleep_current, active_current, active_seconds, wake_interval)

        # Should be positive finite number
        assert days > 0, f"Negative days for inputs: {locals()}"
        assert days < float('inf'), f"Infinite days for inputs: {locals()}"

        # Should be reasonable range for battery life (1 day to 1000 years)
        assert 1 <= days <= 365000, f"Unreasonable days estimate: {days}"
