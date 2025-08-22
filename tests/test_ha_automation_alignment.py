import os
import subprocess
import time

import pytest

from scripts.test_mqtt_integration import MqttTestClient, _now_ms


ROOT = os.path.dirname(os.path.dirname(__file__))


def _try_yaml_lint() -> None:
    # Basic syntax check using python -c to load YAML; avoids adding extra deps
    p = subprocess.run(
        [
            "python3",
            "-c",
            ("import sys,yaml;" "yaml.safe_load(open(sys.argv[1],'r').read());" "print('OK')"),
            os.path.join(ROOT, "homeassistant", "mqtt_outdoor_publish.yaml"),
        ],
        capture_output=True,
        text=True,
    )
    assert p.returncode == 0, p.stdout + p.stderr


def _mqtt_host_port():
    host = os.environ.get("MQTT_HOST", "127.0.0.1")
    port = int(os.environ.get("MQTT_PORT", "1883"))
    return host, port


def _broker_required():
    host, port = _mqtt_host_port()
    c = MqttTestClient(host, port, client_id=f"probe-{_now_ms()}")
    try:
        c.connect()
    except Exception as e:  # pragma: no cover - conditional skip
        pytest.skip(f"MQTT broker not available at {host}:{port}: {e}")
    finally:
        try:
            c.disconnect()
        except Exception:
            pass


def test_homeassistant_yaml_loads_and_retained_topics_present():
    _try_yaml_lint()
    _broker_required()
    host, port = _mqtt_host_port()

    # Simulate HA/automation by publishing retained outdoor topics the device expects
    pub = MqttTestClient(host, port, client_id=f"ha-pub-{_now_ms()}")
    pub.connect()
    base = "home/outdoor"
    messages = {
        f"{base}/temp": "21.5",
        f"{base}/hum": "48",
        f"{base}/weather": "Cloudy",
        f"{base}/wind": "3.2",
        f"{base}/high": "26.0",
        f"{base}/low": "12.1",
    }
    for t, v in messages.items():
        pub.publish(t, v, retain=True, qos=1)

    # A fresh subscriber (device) should receive all retained messages
    sub = MqttTestClient(host, port, client_id=f"dev-sub-{_now_ms()}")
    sub.connect()
    received = {}
    import threading

    got_all = threading.Event()

    def on_msg(_c, _u, msg):  # pragma: no cover - I/O dependent
        received[msg.topic] = (msg.payload.decode("utf-8", "ignore"), bool(msg.retain))
        if len(received) >= len(messages):
            got_all.set()

    sub.client.on_message = on_msg
    for t in messages.keys():
        sub.subscribe_and_confirm(t)

    end_at = time.time() + 3.0
    while time.time() < end_at and not got_all.is_set():
        time.sleep(0.05)

    for t, v in messages.items():
        assert t in received, f"Missing retained message for {t}"
        payload, retained = received[t]
        assert retained, f"{t} should be retained"
        assert payload == v

    sub.disconnect()
    pub.disconnect()
