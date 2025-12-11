"""
Property-based tests for power estimation using Hypothesis.

Tests the power_estimator.py module with automatically generated test cases
to find edge cases and ensure mathematical properties hold.
"""

import importlib.util
import os
import sys

import pytest

# Try to import hypothesis, skip tests if not available
try:
    from hypothesis import given, assume, settings, example
    from hypothesis import strategies as st

    HAS_HYPOTHESIS = True
except ImportError:
    HAS_HYPOTHESIS = False
    # Create dummy decorators for when hypothesis isn't available
    def given(*args, **kwargs):
        def decorator(f):
            return pytest.mark.skip(reason="hypothesis not installed")(f)
        return decorator

    def example(*args, **kwargs):
        def decorator(f):
            return f
        return decorator

    def settings(**kwargs):
        def decorator(f):
            return f
        return decorator

    class st:
        @staticmethod
        def floats(*args, **kwargs):
            return None
        @staticmethod
        def integers(*args, **kwargs):
            return None

    def assume(x):
        pass

# Load power_estimator module
ROOT = os.path.dirname(os.path.dirname(__file__))
_scripts = os.path.join(ROOT, "scripts")
_module_path = os.path.join(_scripts, "power_estimator.py")
_spec = importlib.util.spec_from_file_location("power_estimator", _module_path)
pe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pe)


pytestmark = pytest.mark.skipif(not HAS_HYPOTHESIS, reason="hypothesis not installed")


class TestPowerEstimatorProperties:
    """Property-based tests for power estimation."""

    @given(
        capacity=st.floats(min_value=100, max_value=20000, allow_nan=False, allow_infinity=False),
        sleep_mA=st.floats(min_value=0.01, max_value=10, allow_nan=False, allow_infinity=False),
        active_mA=st.floats(min_value=10, max_value=500, allow_nan=False, allow_infinity=False),
        awake_s=st.floats(min_value=1, max_value=300, allow_nan=False, allow_infinity=False),
        interval_s=st.floats(min_value=60, max_value=86400, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=200)
    def test_estimate_days_always_non_negative(
        self, capacity, sleep_mA, active_mA, awake_s, interval_s
    ):
        """Estimated days should always be >= 0 for valid inputs."""
        result = pe.estimate_days(capacity, sleep_mA, active_mA, awake_s, interval_s)
        assert result >= 0, f"Got negative days: {result}"

    @given(
        capacity=st.floats(min_value=1000, max_value=10000, allow_nan=False, allow_infinity=False),
        sleep_mA=st.floats(min_value=0.01, max_value=1, allow_nan=False, allow_infinity=False),
        active_mA=st.floats(min_value=50, max_value=200, allow_nan=False, allow_infinity=False),
        awake_s=st.floats(min_value=10, max_value=120, allow_nan=False, allow_infinity=False),
        interval_s=st.floats(min_value=300, max_value=14400, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=200)
    def test_double_capacity_doubles_days(
        self, capacity, sleep_mA, active_mA, awake_s, interval_s
    ):
        """Doubling battery capacity should approximately double estimated days."""
        days_normal = pe.estimate_days(capacity, sleep_mA, active_mA, awake_s, interval_s)
        days_double = pe.estimate_days(capacity * 2, sleep_mA, active_mA, awake_s, interval_s)

        # Allow 1% tolerance for floating-point precision
        assert abs(days_double - days_normal * 2) < days_normal * 0.01 + 0.001

    @given(
        capacity=st.floats(min_value=1000, max_value=10000, allow_nan=False, allow_infinity=False),
        sleep_mA=st.floats(min_value=0.01, max_value=1, allow_nan=False, allow_infinity=False),
        active_mA=st.floats(min_value=50, max_value=200, allow_nan=False, allow_infinity=False),
        awake_s=st.floats(min_value=10, max_value=120, allow_nan=False, allow_infinity=False),
        interval_s1=st.floats(min_value=300, max_value=7200, allow_nan=False, allow_infinity=False),
        interval_s2=st.floats(min_value=300, max_value=7200, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=200)
    def test_longer_interval_more_days(
        self, capacity, sleep_mA, active_mA, awake_s, interval_s1, interval_s2
    ):
        """Longer sleep intervals should result in more estimated days (lower average current)."""
        assume(interval_s1 != interval_s2)
        assume(awake_s < min(interval_s1, interval_s2))  # Awake time must fit in interval

        days1 = pe.estimate_days(capacity, sleep_mA, active_mA, awake_s, interval_s1)
        days2 = pe.estimate_days(capacity, sleep_mA, active_mA, awake_s, interval_s2)

        if interval_s1 > interval_s2:
            assert days1 >= days2 - 0.001  # Allow tiny tolerance
        else:
            assert days2 >= days1 - 0.001

    @given(
        capacity=st.floats(min_value=1000, max_value=10000, allow_nan=False, allow_infinity=False),
        sleep_mA=st.floats(min_value=0.01, max_value=1, allow_nan=False, allow_infinity=False),
        active_mA1=st.floats(min_value=50, max_value=200, allow_nan=False, allow_infinity=False),
        active_mA2=st.floats(min_value=50, max_value=200, allow_nan=False, allow_infinity=False),
        awake_s=st.floats(min_value=10, max_value=120, allow_nan=False, allow_infinity=False),
        interval_s=st.floats(min_value=300, max_value=14400, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=200)
    def test_higher_active_current_fewer_days(
        self, capacity, sleep_mA, active_mA1, active_mA2, awake_s, interval_s
    ):
        """Higher active current should result in fewer estimated days."""
        assume(active_mA1 != active_mA2)
        assume(awake_s < interval_s)

        days1 = pe.estimate_days(capacity, sleep_mA, active_mA1, awake_s, interval_s)
        days2 = pe.estimate_days(capacity, sleep_mA, active_mA2, awake_s, interval_s)

        if active_mA1 > active_mA2:
            assert days1 <= days2 + 0.001
        else:
            assert days2 <= days1 + 0.001

    @given(
        capacity=st.floats(min_value=1000, max_value=10000, allow_nan=False, allow_infinity=False),
        active_mA=st.floats(min_value=50, max_value=200, allow_nan=False, allow_infinity=False),
        awake_s=st.floats(min_value=10, max_value=120, allow_nan=False, allow_infinity=False),
        interval_s=st.floats(min_value=300, max_value=14400, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=100)
    def test_zero_sleep_current_still_works(
        self, capacity, active_mA, awake_s, interval_s
    ):
        """Zero sleep current should still produce valid results."""
        assume(awake_s < interval_s)
        result = pe.estimate_days(capacity, 0.0, active_mA, awake_s, interval_s)
        assert result >= 0

    @example(capacity=0, sleep_mA=0.1, active_mA=80, awake_s=45, interval_s=7200)
    @example(capacity=3500, sleep_mA=0.1, active_mA=80, awake_s=45, interval_s=0)
    @example(capacity=-100, sleep_mA=0.1, active_mA=80, awake_s=45, interval_s=7200)
    @given(
        capacity=st.floats(allow_nan=True, allow_infinity=True),
        sleep_mA=st.floats(allow_nan=True, allow_infinity=True),
        active_mA=st.floats(allow_nan=True, allow_infinity=True),
        awake_s=st.floats(allow_nan=True, allow_infinity=True),
        interval_s=st.floats(allow_nan=True, allow_infinity=True),
    )
    @settings(max_examples=100)
    def test_invalid_inputs_return_zero_or_nan(
        self, capacity, sleep_mA, active_mA, awake_s, interval_s
    ):
        """Invalid inputs (negative, zero, NaN, Inf) should return 0 or NaN (not a normal positive number)."""
        import math

        # Check if any input is invalid
        invalid = (
            capacity <= 0
            or interval_s <= 0
            or active_mA < 0
            or sleep_mA < 0
            or awake_s < 0
            or not math.isfinite(capacity)
            or not math.isfinite(sleep_mA)
            or not math.isfinite(active_mA)
            or not math.isfinite(awake_s)
            or not math.isfinite(interval_s)
        )

        result = pe.estimate_days(capacity, sleep_mA, active_mA, awake_s, interval_s)

        if invalid:
            # Function should return 0 for clearly invalid inputs (negative, zero)
            # NaN inputs may propagate as NaN (which is also not a valid positive result)
            assert result == 0 or math.isnan(result), f"Expected 0 or NaN for invalid input, got {result}"


class TestPowerEstimatorRealisticScenarios:
    """Property tests with realistic ESP32 device parameters."""

    @given(
        capacity=st.sampled_from([1000, 2000, 3000, 3500, 5000, 10000]),  # Common battery sizes mAh
        sleep_mA=st.floats(min_value=0.05, max_value=0.5, allow_nan=False),  # ESP32 deep sleep
        active_mA=st.sampled_from([40, 60, 80, 100, 120, 150]),  # WiFi + sensor active
        awake_s=st.sampled_from([15, 30, 45, 60, 90, 120]),  # Wake durations
        interval_s=st.sampled_from([300, 600, 1800, 3600, 7200, 14400]),  # 5min to 4hr
    )
    @settings(max_examples=100)
    def test_realistic_esp32_scenarios(
        self, capacity, sleep_mA, active_mA, awake_s, interval_s
    ):
        """Test with realistic ESP32 eInk room node parameters."""
        result = pe.estimate_days(capacity, sleep_mA, active_mA, awake_s, interval_s)

        # Should always be positive
        assert result > 0

        # Sanity bounds: ESP32 devices typically last 30-600 days
        # With very conservative params could go higher
        assert result < 5000, f"Unrealistic high estimate: {result} days"

    @given(
        interval_s=st.sampled_from([300, 600, 1800, 3600, 7200, 14400]),
    )
    @settings(max_examples=20)
    def test_project_default_parameters(self, interval_s):
        """Test with project's documented default parameters."""
        # From CLAUDE.md: 3500mAh battery, 0.09mA sleep, 80mA active, 45s awake
        capacity = 3500
        sleep_mA = 0.09
        active_mA = 80
        awake_s = 45

        result = pe.estimate_days(capacity, sleep_mA, active_mA, awake_s, interval_s)

        # Should be in reasonable range
        # Shorter intervals (300s) result in ~12 days due to more frequent active periods
        # Longer intervals (14400s) result in ~400+ days
        assert result > 0, f"Should be positive, got {result}"
        assert result < 1000, f"Should be less than 1000 days, got {result}"


class TestPowerEstimatorMathematicalProperties:
    """Tests for mathematical properties of the estimation formula."""

    @given(
        capacity=st.floats(min_value=1000, max_value=10000, allow_nan=False, allow_infinity=False),
        current_mA=st.floats(min_value=0.1, max_value=100, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=100)
    def test_continuous_operation_baseline(self, capacity, current_mA):
        """When awake_s equals interval_s, should be simple capacity/current calculation."""
        interval_s = 3600  # 1 hour
        awake_s = interval_s  # Continuously awake

        result = pe.estimate_days(capacity, 0, current_mA, awake_s, interval_s)

        # Expected: (capacity_mAh / current_mA) / 24 hours
        expected = (capacity / current_mA) / 24
        assert abs(result - expected) < 0.01

    @given(
        capacity=st.floats(min_value=1000, max_value=10000, allow_nan=False, allow_infinity=False),
        sleep_mA=st.floats(min_value=0.01, max_value=1, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=100)
    def test_sleep_only_baseline(self, capacity, sleep_mA):
        """When awake_s is 0, should be pure sleep current calculation."""
        interval_s = 3600
        awake_s = 0

        result = pe.estimate_days(capacity, sleep_mA, 100, awake_s, interval_s)

        # Expected: (capacity_mAh / sleep_mA) / 24 hours
        expected = (capacity / sleep_mA) / 24
        assert abs(result - expected) < 0.01

    @given(
        capacity=st.floats(min_value=1000, max_value=10000, allow_nan=False, allow_infinity=False),
        sleep_mA=st.floats(min_value=0.01, max_value=1, allow_nan=False, allow_infinity=False),
        active_mA=st.floats(min_value=50, max_value=200, allow_nan=False, allow_infinity=False),
        awake_s=st.floats(min_value=10, max_value=120, allow_nan=False, allow_infinity=False),
        interval_s=st.floats(min_value=300, max_value=14400, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=100)
    def test_average_current_formula(
        self, capacity, sleep_mA, active_mA, awake_s, interval_s
    ):
        """Verify the weighted average current calculation."""
        assume(awake_s <= interval_s)

        result = pe.estimate_days(capacity, sleep_mA, active_mA, awake_s, interval_s)

        # Calculate expected average current
        sleep_time = interval_s - awake_s
        avg_mA = (active_mA * awake_s + sleep_mA * sleep_time) / interval_s

        if avg_mA > 0:
            expected = (capacity / avg_mA) / 24
            assert abs(result - expected) < 0.01


class TestPowerEstimatorEdgeCases:
    """Edge case tests discovered through property testing."""

    def test_very_small_sleep_current(self):
        """Test with extremely small sleep current (realistic for ESP32-S3)."""
        result = pe.estimate_days(3500, 0.007, 80, 45, 7200)  # 7µA sleep
        assert result > 0
        assert result < 10000  # Sanity check

    def test_very_long_interval(self):
        """Test with very long sleep interval (24 hours)."""
        result = pe.estimate_days(3500, 0.09, 80, 45, 86400)
        assert result > 0
        assert result > 300  # Should be quite long with 24hr interval

    def test_awake_time_equals_interval(self):
        """Test when device is always awake."""
        result = pe.estimate_days(3500, 0.09, 80, 3600, 3600)
        # Should be capacity / active_current / 24
        expected = 3500 / 80 / 24
        assert abs(result - expected) < 0.1

    def test_awake_time_exceeds_interval(self):
        """Test when awake time exceeds interval (should clamp)."""
        # The function should clamp awake_s to interval_s
        result = pe.estimate_days(3500, 0.09, 80, 7200, 3600)
        # With clamping, awake_s becomes 3600 (same as interval)
        expected = 3500 / 80 / 24
        assert abs(result - expected) < 0.1

    def test_fractional_values(self):
        """Test with fractional mAh and current values."""
        result = pe.estimate_days(3456.789, 0.0876, 79.5, 44.5, 7199.9)
        assert result > 0
        assert isinstance(result, float)
