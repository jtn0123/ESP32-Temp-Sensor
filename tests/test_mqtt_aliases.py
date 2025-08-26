import os
import time

import pytest

from scripts.test_mqtt_integration import MqttTestClient, _now_ms


def _mqtt_host_port():
    host = os.environ.get("MQTT_HOST", "127.0.0.1")
    port = int(os.environ.get("MQTT_PORT", "1883"))
    return host, port


@pytest.mark.usefixtures("mosquitto_broker")
def test_retained_alias_topics_deliver_on_fresh_subscriber(mosquitto_broker):
    host, port = mosquitto_broker

    base = "home/outdoor"
    pub = MqttTestClient(host, port, client_id=f"alias-pub-{_now_ms()}")
    pub.connect()

    # Seed retained alias topics
    messages = {
        f"{base}/temp_f": "73.7",
        f"{base}/condition": "clear",
        f"{base}/condition_code": "800",
        # Keep legacy keys too to ensure no regressions when both exist
        f"{base}/temp": "23.4",
        f"{base}/weather": "Clear",
        f"{base}/weather_id": "800",
    }
    for t, v in messages.items():
        pub.publish(t, v, retain=True, qos=1)

    # Fresh subscriber should get retained deliveries for all seeded topics
    sub = MqttTestClient(host, port, client_id=f"alias-sub-{_now_ms()}")
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
