import json
import os
import sys
import time

import pytest

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from scripts.test_mqtt_integration import MqttTestClient, _now_ms  # noqa: E402


from typing import Tuple


def _build_discovery_payload(*, device_id: str, room_name: str, pub_base: str, key: str,
                             name: str, unit: str, dev_class: str, state_suffix: str) -> str:
    availability_topic = f"{pub_base}/availability"
    state_topic = f"{pub_base}/{state_suffix}"
    # Match README contract
    payload = {
        "name": name,
        "unique_id": f"{device_id}_{key}",
        "state_topic": state_topic,
        "availability_topic": availability_topic,
        "payload_available": "online",
        "payload_not_available": "offline",
        "unit_of_measurement": unit,
        "device_class": dev_class,
        "state_class": "measurement",
        # Example precision/expiry matching README guidance
        "suggested_display_precision": 1 if unit == "°F" else (2 if unit == "V" else 0),
        "expire_after": 3600 + 120,
        "device": {
            "identifiers": [device_id],
            "name": f"ESP32 Room Node: {room_name}",
            "manufacturer": "DIY",
            "model": "Feather ESP32-S2",
        },
    }
    return json.dumps(payload)


def test_mqtt_discovery_contract(mosquitto_broker):
    host, port = mosquitto_broker

    device_id = f"room_node_{_now_ms()}"
    room_name = "Office"
    pub_base = f"sensors/{room_name.lower()}"
    ha_prefix = "homeassistant"

    publisher = MqttTestClient(host, port, client_id=f"pub-{_now_ms()}")
    publisher.connect()

    # Build discovery payloads per README
    d_temp = _build_discovery_payload(
        device_id=device_id,
        room_name=room_name,
        pub_base=pub_base,
        key="inside_temp",
        name="Inside Temperature",
        unit="°F",
        dev_class="temperature",
        state_suffix="inside/temp",
    )
    d_hum = _build_discovery_payload(
        device_id=device_id,
        room_name=room_name,
        pub_base=pub_base,
        key="inside_hum",
        name="Inside Humidity",
        unit="%",
        dev_class="humidity",
        state_suffix="inside/hum",
    )

    # Publish retained discovery
    publisher.publish(f"{ha_prefix}/sensor/{device_id}_inside_temp/config", d_temp, retain=True, qos=1)
    publisher.publish(f"{ha_prefix}/sensor/{device_id}_inside_hum/config", d_hum, retain=True, qos=1)

    # Publish retained states and availability
    publisher.publish(f"{pub_base}/inside/temp", "72.5", retain=True, qos=1)
    publisher.publish(f"{pub_base}/inside/hum", "42", retain=True, qos=1)
    publisher.publish(f"{pub_base}/availability", "online", retain=True, qos=1)

    # Subscribe and verify retained deliveries
    ha = MqttTestClient(host, port, client_id=f"ha-{_now_ms()}")
    ha.connect()

    cfg_t, cfg_h = (
        f"{ha_prefix}/sensor/{device_id}_inside_temp/config",
        f"{ha_prefix}/sensor/{device_id}_inside_hum/config",
    )
    msgs_cfg_t = ha.subscribe_and_wait(cfg_t, expected_count=1, timeout_s=3.0)
    msgs_cfg_h = ha.subscribe_and_wait(cfg_h, expected_count=1, timeout_s=3.0)
    assert msgs_cfg_t and msgs_cfg_t[0][1] is True
    assert msgs_cfg_h and msgs_cfg_h[0][1] is True

    # Validate JSON keys
    data_t = json.loads(msgs_cfg_t[0][0])
    data_h = json.loads(msgs_cfg_h[0][0])
    for data in (data_t, data_h):
        assert "state_topic" in data
        assert "availability_topic" in data
        assert data.get("payload_available") == "online"
        assert data.get("payload_not_available") == "offline"
        assert data.get("unit_of_measurement") in ("°F", "%")
        assert data.get("state_class") == "measurement"
        assert isinstance(data.get("expire_after"), int)
        assert isinstance(data.get("device"), dict)
        assert isinstance(data["device"].get("identifiers"), list)

    # Verify retained state topics and availability
    msgs_temp = ha.subscribe_and_wait(f"{pub_base}/inside/temp", expected_count=1, timeout_s=3.0)
    msgs_hum = ha.subscribe_and_wait(f"{pub_base}/inside/hum", expected_count=1, timeout_s=3.0)
    msgs_avail = ha.subscribe_and_wait(f"{pub_base}/availability", expected_count=1, timeout_s=3.0)
    assert msgs_temp and msgs_temp[0][1] is True
    assert msgs_hum and msgs_hum[0][1] is True
    assert msgs_avail and msgs_avail[0][1] is True

    # A fresh subscriber should receive retained discovery and states
    val = MqttTestClient(host, port, client_id=f"val-{_now_ms()}")
    val.connect()
    for t in (cfg_t, cfg_h, f"{pub_base}/inside/temp", f"{pub_base}/inside/hum", f"{pub_base}/availability"):
        got = val.subscribe_and_wait(t, expected_count=1, timeout_s=3.0)
        assert got and got[0][1] is True, f"Expected retained on {t}"
    val.disconnect()

    ha.disconnect()
    publisher.disconnect()


