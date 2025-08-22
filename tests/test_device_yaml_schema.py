import os

import yaml  # type: ignore


def _load_yaml(path: str):
    with open(path, "r") as f:
        return yaml.safe_load(f) or {}


def _validate_yaml(data: dict):
    # Top-level required
    assert isinstance(data.get("room_name"), str) and data["room_name"].strip()

    # Wake interval: allow "1h"/"2h"/"4h" or seconds (int or digit string)
    wake = data.get("wake_interval")
    assert wake is not None
    allowed = {"1h", "2h", "4h"}
    if isinstance(wake, int):
        assert wake > 0
    elif isinstance(wake, str):
        w = wake.strip().lower()
        assert (w in allowed) or w.isdigit(), "wake_interval must be 1h/2h/4h or seconds"
        if w.isdigit():
            assert int(w) > 0
    else:
        raise AssertionError("wake_interval must be string or int")

    # Full refresh bound (positive int)
    fre = data.get("full_refresh_every", 12)
    assert int(fre) >= 1

    # outside_source
    outside = str(data.get("outside_source", "mqtt")).strip().lower()
    assert outside in ("ha", "mqtt")

    # Wi-Fi creds present
    wifi = data.get("wifi", {}) or {}
    ssid = wifi.get("ssid")
    pw = wifi.get("password")
    assert isinstance(ssid, str) and ssid.strip()
    assert isinstance(pw, str) and pw.strip()

    # MQTT host required if outside_source=mqtt
    mqtt = data.get("mqtt", {}) or {}
    if outside == "mqtt":
        host = mqtt.get("host")
        assert isinstance(host, str) and host.strip()

    # Thresholds non-negative
    th = data.get("thresholds", {}) or {}
    if "temp_degC" in th:
        assert float(th["temp_degC"]) >= 0
    if "rh_pct" in th:
        assert float(th["rh_pct"]) >= 0

    # Battery currents non-negative; capacity positive
    batt = data.get("battery", {}) or {}
    if "capacity_mAh" in batt:
        assert float(batt["capacity_mAh"]) > 0
    if "sleep_current_mA" in batt:
        assert float(batt["sleep_current_mA"]) >= 0
    if "active_current_mA" in batt:
        assert float(batt["active_current_mA"]) >= 0

    # Optional active_seconds if present should be non-negative
    if "active_seconds" in data:
        assert int(data["active_seconds"]) >= 0


def test_device_sample_yaml_schema_and_ranges():
    root = os.path.dirname(os.path.dirname(__file__))
    path = os.path.join(root, "config", "device.sample.yaml")
    data = _load_yaml(path)
    _validate_yaml(data)


def test_device_yaml_schema_and_ranges():
    root = os.path.dirname(os.path.dirname(__file__))
    path = os.path.join(root, "config", "device.yaml")
    # Device yaml may be missing in clean clones; skip if not present
    if not os.path.exists(path):
        return
    data = _load_yaml(path)
    _validate_yaml(data)
