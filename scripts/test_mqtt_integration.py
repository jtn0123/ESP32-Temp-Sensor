#!/usr/bin/env python3
"""
MQTT integration check for CI

This script:
- Publishes Home Assistant MQTT Discovery configs for temperature, humidity, and battery
- Publishes retained state messages for each entity
- Flips availability (online/offline/online) and asserts messages are observed
- Re-subscribes with a new client to assert discovery and states are retained

Broker and topics are intentionally simple and unauthenticated for CI usage.
"""

from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import paho.mqtt.client as mqtt  # type: ignore


def _now_ms() -> int:
    return int(time.time() * 1000)


@dataclass
class SensorSpec:
    key: str
    name: str
    state_topic: str
    unit_of_measurement: str
    device_class: str
    sample_value: str


class MqttTestClient:
    def __init__(self, host: str, port: int, client_id: Optional[str] = None) -> None:
        # Use default callback API; keep code compatible across paho versions
        self.client = mqtt.Client(client_id=client_id)
        self._host = host
        self._port = port
        self._connected_event = threading.Event()
        self._disconnected_event = threading.Event()

        # Support both v1 and v2 callback signatures
        def on_connect(client, userdata, flags, rc=None, properties=None):  # type: ignore[no-redef]
            self._connected_event.set()

        def on_disconnect(client, userdata, rc=None, properties=None):  # type: ignore[no-redef]
            self._disconnected_event.set()

        self.client.on_connect = on_connect
        self.client.on_disconnect = on_disconnect

    def connect(self, timeout_s: float = 10.0) -> None:
        self.client.connect(self._host, self._port, keepalive=30)
        self.client.loop_start()
        if not self._connected_event.wait(timeout_s):
            raise RuntimeError("MQTT client failed to connect within timeout")

    def disconnect(self, timeout_s: float = 5.0) -> None:
        self.client.disconnect()
        if not self._disconnected_event.wait(timeout_s):
            # Ensure loop stops even if disconnect event didn't arrive
            pass
        self.client.loop_stop()

    def publish(self, topic: str, payload: str, retain: bool = False, qos: int = 0) -> None:
        result = self.client.publish(topic, payload=payload, retain=retain, qos=qos)
        # Compatible with paho-mqtt 1.x and 2.x (no timeout argument)
        result.wait_for_publish()
        if result.rc is not mqtt.MQTT_ERR_SUCCESS:
            raise RuntimeError(f"Publish failed rc={result.rc} topic={topic}")

    def subscribe_and_wait(
        self,
        topic: str,
        expected_count: int = 1,
        timeout_s: float = 5.0,
    ) -> List[Tuple[str, bool]]:
        """
        Subscribe to a topic and wait for messages.
        Returns a list of (payload, retained_flag) tuples in arrival order.
        """
        messages: List[Tuple[str, bool]] = []
        got_all = threading.Event()

        def on_message(client, userdata, msg):  # type: ignore[no-redef]
            messages.append((msg.payload.decode("utf-8", "ignore"), bool(msg.retain)))
            if len(messages) >= expected_count:
                got_all.set()

        self.client.subscribe(topic, qos=0)
        self.client.on_message = on_message
        # Give broker a moment to process SUB and send retained
        end_at = time.time() + timeout_s
        while time.time() < end_at:
            if got_all.is_set():
                break
            time.sleep(0.05)
        return messages


def build_discovery_config(
    device_id: str,
    availability_topic: str,
    sensor: SensorSpec,
) -> Dict[str, object]:
    return {
        "name": f"Room Node CI {sensor.name}",
        "unique_id": f"{device_id}_{sensor.key}",
        "state_topic": sensor.state_topic,
        "availability_topic": availability_topic,
        "payload_available": "online",
        "payload_not_available": "offline",
        "device_class": sensor.device_class,
        "unit_of_measurement": sensor.unit_of_measurement,
        "state_class": "measurement",
        "device": {
            "identifiers": [device_id],
            "name": "Room Node CI",
            "manufacturer": "ESP32-Temp-Sensor",
            "model": "CI",
        },
    }


def main() -> None:
    mqtt_host = os.environ.get("MQTT_HOST", "127.0.0.1")
    mqtt_port = int(os.environ.get("MQTT_PORT", "1883"))

    # Topics and specs
    device_id = "room_node_ci"
    state_base = f"sensors/{device_id}"
    availability_topic = f"{state_base}/status"
    ha_prefix = "homeassistant"

    sensors: List[SensorSpec] = [
        SensorSpec(
            key="temp",
            name="Temperature",
            state_topic=f"{state_base}/inside/temp",
            unit_of_measurement="°C",
            device_class="temperature",
            sample_value="21.7",
        ),
        SensorSpec(
            key="hum",
            name="Humidity",
            state_topic=f"{state_base}/inside/hum",
            unit_of_measurement="%",
            device_class="humidity",
            sample_value="48.2",
        ),
        SensorSpec(
            key="batt",
            name="Battery",
            state_topic=f"{state_base}/battery",
            unit_of_measurement="%",
            device_class="battery",
            sample_value="93",
        ),
    ]

    publisher = MqttTestClient(mqtt_host, mqtt_port, client_id=f"pub-{_now_ms()}")
    publisher.connect()

    # 1) Publish Home Assistant discovery configs (retained)
    for s in sensors:
        cfg_topic = f"{ha_prefix}/sensor/{device_id}_{s.key}/config"
        cfg_payload = json.dumps(build_discovery_config(device_id, availability_topic, s))
        publisher.publish(cfg_topic, cfg_payload, retain=True, qos=1)

    # 2) Publish retained states for each
    for s in sensors:
        publisher.publish(s.state_topic, s.sample_value, retain=True, qos=1)

    # 3) Flip availability online -> offline -> online; no retain for availability
    publisher.publish(availability_topic, "online", retain=False)
    time.sleep(0.2)
    publisher.publish(availability_topic, "offline", retain=False)
    time.sleep(0.2)
    publisher.publish(availability_topic, "online", retain=False)

    # 4) Validate discovery topics retained (new subscriber should receive retained messages)
    validator = MqttTestClient(mqtt_host, mqtt_port, client_id=f"sub-{_now_ms()}")
    validator.connect()

    for s in sensors:
        cfg_topic = f"{ha_prefix}/sensor/{device_id}_{s.key}/config"
        msgs = validator.subscribe_and_wait(cfg_topic, expected_count=1, timeout_s=3.0)
        assert msgs, f"No discovery message received for {s.key}"
        payload, retained = msgs[0]
        assert retained, f"Discovery message for {s.key} was not retained"
        data = json.loads(payload)
        assert data["state_topic"] == s.state_topic
        assert data["availability_topic"] == availability_topic

    # 5) Validate retained states
    for s in sensors:
        msgs = validator.subscribe_and_wait(s.state_topic, expected_count=1, timeout_s=3.0)
        assert msgs, f"No state message received for {s.key}"
        payload, retained = msgs[0]
        assert retained, f"State for {s.key} was not retained"
        assert payload == s.sample_value, f"Unexpected state for {s.key}: {payload} != {s.sample_value}"

    # 6) Validate availability toggles (non-retained real-time)
    toggles_sub = MqttTestClient(mqtt_host, mqtt_port, client_id=f"tog-{_now_ms()}")
    toggles_sub.connect()
    # Subscribe before publishing toggles to ensure we capture them
    events: List[Tuple[str, bool]] = []
    got_all = threading.Event()

    def on_msg(client, userdata, msg):  # type: ignore[no-redef]
        events.append((msg.payload.decode("utf-8", "ignore"), bool(msg.retain)))
        if len(events) >= 3:
            got_all.set()

    toggles_sub.client.subscribe(availability_topic, qos=0)
    toggles_sub.client.on_message = on_msg

    # Trigger the three messages
    publisher.publish(availability_topic, "online", retain=False)
    publisher.publish(availability_topic, "offline", retain=False)
    publisher.publish(availability_topic, "online", retain=False)

    end_at = time.time() + 5.0
    while time.time() < end_at and not got_all.is_set():
        time.sleep(0.05)

    assert len(events) >= 3, f"Expected 3 availability events, got {len(events)}: {events}"
    observed = [p for p, _r in events[:3]]
    assert observed == ["online", "offline", "online"], f"Unexpected availability sequence: {observed}"
    # None of these should be retained
    assert not any(r for _p, r in events[:3]), f"Availability events should not be retained: {events[:3]}"

    toggles_sub.disconnect()
    validator.disconnect()
    publisher.disconnect()

    print("MQTT integration test passed: discovery retained, states retained, availability toggled")


if __name__ == "__main__":
    main()


