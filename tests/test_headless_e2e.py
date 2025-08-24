"""
End-to-end validation against a real/device broker.

This test seeds outdoor MQTT topics (including aliases) on the broker the device
is connected to, then waits for the device to publish a retained debug_ui
snapshot at sensors/<room>/debug_ui and asserts the values the UI would consume.

Default: skipped. Enable by setting E2E_DEVICE=1 and point to the broker or
ensure config/device.yaml points to a reachable broker from this host.
Optional env overrides:
  - E2E_MQTT_HOST / E2E_MQTT_PORT
  - E2E_PUB_BASE (if you want to override sensors/<room> derived from device.yaml)
  - E2E_SUB_BASE (override outdoor base if not using device.yaml)
"""

from __future__ import annotations

import json
import os
from typing import Tuple

import pytest
import yaml  # type: ignore

from scripts.test_mqtt_integration import MqttTestClient, _now_ms

ROOT = os.path.dirname(os.path.dirname(__file__))


def _load_device_yaml() -> dict:
    path = os.path.join(ROOT, "config", "device.yaml")
    if not os.path.exists(path):
        # Fallback to sample to avoid errors; users can override via env
        path = os.path.join(ROOT, "config", "device.sample.yaml")
    with open(path, "r") as f:
        return yaml.safe_load(f) or {}


def _resolve_bases_from_yaml() -> Tuple[str, str]:
    d = _load_device_yaml()
    m = d.get("mqtt") or {}
    bt = m.get("base_topics") or {}
    pub = str(bt.get("publish", "")).strip()
    sub = str(bt.get("subscribe", "")).strip()
    assert pub and sub
    return pub, sub


def _resolve_broker() -> Tuple[str, int]:
    host = os.environ.get("E2E_MQTT_HOST")
    port_s = os.environ.get("E2E_MQTT_PORT")
    if host and port_s:
        return host, int(port_s)
    d = _load_device_yaml()
    m = d.get("mqtt") or {}
    return str(m.get("host", "127.0.0.1")), int(m.get("port", 1883))


@pytest.mark.skipif(os.environ.get("E2E_DEVICE", "0") != "1", \
                     reason="Set E2E_DEVICE=1 to enable E2E device test")
def test_device_publishes_ui_debug_from_outdoor_aliases():
    mqtt_host, mqtt_port = _resolve_broker()
    pub_base_yaml, sub_base_yaml = _resolve_bases_from_yaml()
    pub_base = os.environ.get("E2E_PUB_BASE", pub_base_yaml)
    sub_base = os.environ.get("E2E_SUB_BASE", sub_base_yaml)

    # Clear any previous retained debug_ui from the device to avoid stale reads
    ctl = MqttTestClient(mqtt_host, mqtt_port, client_id=f"e2e-ctl-{_now_ms()}")
    ctl.connect()
    ctl.publish(f"{pub_base}/debug_ui", "", retain=True, qos=1)

    # Seed outdoor alias topics retained
    # Choose distinct values so mapping/formatting is obvious
    expected = {
        "tempF": 71.2,
        "rhPct": 49.0,
        "windMps": 3.4,
        "weather": "partly-cloudy",
        "weatherId": 802,
    }
    seeds = {
        f"{sub_base}/temp_f": f"{expected['tempF']}",
        f"{sub_base}/rh": f"{int(expected['rhPct'])}",
        f"{sub_base}/wind_mps": f"{expected['windMps']}",
        f"{sub_base}/condition": expected["weather"],
        f"{sub_base}/condition_code": f"{expected['weatherId']}",
    }
    for t, v in seeds.items():
        ctl.publish(t, v, retain=True, qos=1)

    # Ask device to emit a ui_debug snapshot now (in case it's already awake)
    ctl.publish(f"{pub_base}/cmd", "ui_debug", retain=False, qos=0)

    # Subscribe for the device's retained debug_ui snapshot. Allow a short window
    # for the device to reconnect, fetch retained, and publish the snapshot.
    sub = MqttTestClient(mqtt_host, mqtt_port, client_id=f"e2e-sub-{_now_ms()}")
    sub.connect()
    msgs = sub.subscribe_and_wait(f"{pub_base}/debug_ui", expected_count=1, timeout_s=10.0)
    assert msgs, f"No debug_ui message received from {pub_base}/debug_ui"
    payload, retained = msgs[0]
    # Live publish may arrive as non-retained; verify retained on a fresh subscriber next
    data = json.loads(payload)
    assert data.get("event") == "ui_debug"
    outside = data.get("outside") or {}

    # Validate mapping used by UI
    if outside.get("tempF") is not None:
        assert abs(float(outside["tempF"]) - expected["tempF"]) < 0.2
    if outside.get("rhPct") is not None:
        assert int(float(outside["rhPct"])) == int(expected["rhPct"])
    if outside.get("windMps") is not None:
        assert abs(float(outside["windMps"]) - expected["windMps"]) < 0.2
    if outside.get("weather") is not None:
        assert str(outside["weather"]).lower().startswith("partly")
    if outside.get("weatherId") is not None:
        assert int(outside["weatherId"]) == expected["weatherId"]

    # Verify a fresh subscriber receives retained debug_ui (command or boot snapshot)
    val = MqttTestClient(mqtt_host, mqtt_port, client_id=f"e2e-val-{_now_ms()}")
    val.connect()
    msgs_val = val.subscribe_and_wait(f"{pub_base}/debug_ui", expected_count=1, timeout_s=5.0)
    assert msgs_val and msgs_val[0][1] is True, "debug_ui should be retained for new subscribers"
    val.disconnect()

    # Also verify the device publishes a layout identity retained
    msgs_layout = sub.subscribe_and_wait(f"{pub_base}/layout", expected_count=1, timeout_s=5.0)
    assert msgs_layout and msgs_layout[0][1] is True
    layout_payload = msgs_layout[0][0]
    assert "layout_version" in layout_payload
    assert "layout_crc" in layout_payload

    # And verify inside readings are being published (retained) in the same wake
    msgs_temp = sub.subscribe_and_wait(f"{pub_base}/inside/temp", expected_count=1, timeout_s=5.0)
    msgs_hum = sub.subscribe_and_wait(f"{pub_base}/inside/hum", expected_count=1, timeout_s=5.0)
    assert msgs_temp and msgs_temp[0][1] is True
    assert msgs_hum and msgs_hum[0][1] is True
    # Sanity: temp payload parses as float; humidity as int
    try:
        float(msgs_temp[0][0])
    except Exception as e:
        raise AssertionError(f"inside/temp not a float: {msgs_temp[0][0]}") from e
    try:
        int(float(msgs_hum[0][0]))
    except Exception as e:
        raise AssertionError(f"inside/hum not an int: {msgs_hum[0][0]}") from e

    sub.disconnect()
    ctl.disconnect()


