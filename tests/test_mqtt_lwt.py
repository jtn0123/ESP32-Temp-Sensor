import json
import os
import sys
import threading
import time

import pytest

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from scripts.test_mqtt_integration import MqttTestClient, _now_ms  # noqa: E402


def test_last_will_offline_on_abrupt_disconnect(mosquitto_broker):
    host, port = mosquitto_broker

    device_id = f"room_node_{_now_ms()}"
    pub_base = f"sensors/{device_id}"
    availability_topic = f"{pub_base}/availability"

    # Subscriber to observe availability
    sub = MqttTestClient(host, port, client_id=f"sub-{_now_ms()}")
    sub.connect()
    events = []
    got_offline = threading.Event()

    def on_msg(client, userdata, msg):
        events.append((msg.payload.decode("utf-8", "ignore"), bool(msg.retain)))
        if msg.payload.decode("utf-8", "ignore") == "offline":
            got_offline.set()

    sub.client.on_message = on_msg
    sub.subscribe_and_confirm(availability_topic)

    # Spawn a helper script process that sets LWT=offline and then we kill it.
    # Reuse paho client to set will and publish online once, then sleep.
    helper = os.path.join(ROOT, "tests", "_mqtt_lwt_helper.py")
    with open(helper, "w", encoding="utf-8") as f:
        f.write(
            """
import os, sys, time
import paho.mqtt.client as mqtt
host, port = sys.argv[1], int(sys.argv[2])
avail = sys.argv[3]
client = mqtt.Client(protocol=mqtt.MQTTv311)
client.will_set(avail, payload="offline", retain=False, qos=0)
client.connect(host, port, keepalive=30)
client.loop_start()
client.publish(avail, "online", retain=False, qos=0)
time.sleep(10)
"""
        )

    proc = None
    try:
        proc = __import__("subprocess").Popen(
            [sys.executable, helper, host, str(port), availability_topic],
            stdout=__import__("subprocess").PIPE,
            stderr=__import__("subprocess").STDOUT,
            text=True,
        )
        # Give it a moment to connect and publish online
        time.sleep(0.5)
        # Abruptly kill to trigger broker sending LWT
        proc.kill()
        # Wait a short time for offline to be observed
        end_at = time.time() + 3.0
        while time.time() < end_at and not got_offline.is_set():
            time.sleep(0.05)
        assert (
            got_offline.is_set()
        ), f"Did not see LWT offline on {availability_topic}; events={events}"
    finally:
        try:
            if proc and proc.poll() is None:
                proc.kill()
        except Exception:
            pass
        try:
            os.remove(helper)
        except Exception:
            pass
        sub.disconnect()
