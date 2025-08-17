import os
import time
import pytest
import paho.mqtt.client as mqtt  # type: ignore

from scripts.parse_history_payload import parse_history_payload


pytestmark = pytest.mark.slow


@pytest.mark.skipif(not os.environ.get("MQTT_HOST"), reason="requires MQTT broker env (MQTT_HOST)")
def test_inside_history_payload_shape(tmp_path):
    host = os.environ.get("MQTT_HOST", "localhost")
    port = int(os.environ.get("MQTT_PORT", "1883"))
    pub_base = os.environ.get("MQTT_PUB_BASE", "sensors/room")
    topic = f"{pub_base}/inside/history"

    msgs: list[str] = []

    def on_connect(client, userdata, flags, rc):
        client.subscribe([(topic, 0)])

    def on_message(client, userdata, msg):
        if msg.topic == topic:
            try:
                msgs.append(msg.payload.decode("utf-8", "ignore"))
            except Exception:
                pass

    c = mqtt.Client()
    c.on_connect = on_connect
    c.on_message = on_message
    c.connect(host, port, 30)

    # Allow some time for messages to arrive; in CI we only validate parsing/shape
    deadline = time.time() + 2.0
    while time.time() < deadline:
        c.loop(timeout=0.2)
        time.sleep(0.05)

    # If nothing arrived during window, skip rather than fail (device may be offline)
    if not msgs:
        pytest.skip("no history message during window")

    ok = False
    for payload in msgs:
        rec = parse_history_payload(payload)
        if rec is None:
            continue
        # Minimal sanity checks
        assert rec.ts > 1_600_000_000  # within plausible epoch range
        assert  -100.0 < rec.tempF < 200.0
        assert   0.0 <= rec.rh    <= 100.0
        ok = True
        break

    assert ok, "no valid history payload parsed"


