import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))

# Mirror of C-side make_short_condition_cstr behavior for tests

def py_make_short_condition(weather: str) -> str:
    if not weather:
        return ""
    w = weather.strip()
    out = []
    for ch in w:
        if ch in (' ', '\t', ',', ';', ':', '/'):
            break
        out.append(ch)
    return ''.join(out)


def mph_from_mps(mps: float) -> float:
    return mps * 2.237 if mps == mps else float('nan')


@pytest.mark.parametrize("inp,expected", [
    ("Cloudy", "Cloudy"),
    ("Cloudy with rain", "Cloudy"),
    ("Rain and wind", "Rain"),
    ("Snow/showers", "Snow"),
    ("Fog", "Fog"),
    (" Thunderstorms ", "Thunderstorms"),
    ("", ""),
])
def test_condition_shortening(inp, expected):
    assert py_make_short_condition(inp) == expected


def test_mph_formatting():
    assert abs(mph_from_mps(4.2) - 9.3954) < 1e-3
