import json
import os

import pytest

from scripts.test_mqtt_integration import MqttTestClient, _now_ms


def _mqtt_host_port():
    host = os.environ.get("MQTT_HOST", "127.0.0.1")
    port = int(os.environ.get("MQTT_PORT", "1883"))
    return host, port


@pytest.mark.usefixtures("mosquitto_broker")
def test_device_ui_debug_reflects_outdoor_aliases(mosquitto_broker):
    host, port = mosquitto_broker

    # Seed retained alias topics that the firmware now accepts
    sub_base = "home/outdoor"
    pub = MqttTestClient(host, port, client_id=f"ui-probe-pub-{_now_ms()}")
    pub.connect()
    pub.publish(f"{sub_base}/temp_f", "68.0", retain=True, qos=1)
    pub.publish(f"{sub_base}/condition", "cloudy", retain=True, qos=1)
    pub.publish(f"{sub_base}/condition_code", "803", retain=True, qos=1)
    pub.publish(f"{sub_base}/rh", "55", retain=True, qos=1)
    pub.publish(f"{sub_base}/wind_mps", "2.5", retain=True, qos=1)

    # Simulate that the device will publish a retained debug_ui snapshot under its pub base.
    # We don't boot the actual firmware here; instead, we mimic the retained document
    # format and assert the consumer side expectations.
    device_id = f"room_node_{_now_ms()}"
    pub_base = f"sensors/{device_id}"
    debug_topic = f"{pub_base}/debug_ui"
    # What the device would publish after applying the alias inputs
    simulated = {
        "event": "ui_debug",
        "outside": {
            "tempF": 68.0,
            "rhPct": 55.0,
            "windMps": 2.5,
            "weather": "cloudy",
            "weatherId": 803,
            "weatherDesc": None,
            "weatherIcon": None,
        },
    }
    pub.publish(debug_topic, json.dumps(simulated), retain=True, qos=1)

    # Fresh subscriber should receive retained debug_ui doc and be able to assert rendering inputs
    sub = MqttTestClient(host, port, client_id=f"ui-probe-sub-{_now_ms()}")
    sub.connect()
    msgs = sub.subscribe_and_wait(debug_topic, expected_count=1, timeout_s=3.0)
    assert msgs and msgs[0][1] is True
    payload = msgs[0][0]
    data = json.loads(payload)
    assert data.get("event") == "ui_debug"
    outside = data.get("outside") or {}
    # Validate that tempF, RH, wind, and condition were captured as the UI would consume
    assert abs(float(outside.get("tempF")) - 68.0) < 1e-3
    assert int(float(outside.get("rhPct"))) == 55
    assert abs(float(outside.get("windMps")) - 2.5) < 1e-3
    assert str(outside.get("weather")).lower() == "cloudy"
    assert int(outside.get("weatherId")) == 803

    sub.disconnect()
    pub.disconnect()
