#!/usr/bin/env python3
import argparse
import sys

try:
    import paho.mqtt.client as mqtt  # type: ignore
except Exception as e:  # pragma: no cover - dependency not installed
    print(f"paho-mqtt missing: {e}")
    sys.exit(2)


def main() -> int:
    ap = argparse.ArgumentParser(description="Simple MQTT topic monitor")
    ap.add_argument("--host", required=True)
    ap.add_argument("--port", type=int, default=1883)
    ap.add_argument("--user", default="")
    ap.add_argument("--password", default="")
    ap.add_argument("--topic", required=True, help="Topic filter to subscribe to")
    args = ap.parse_args()

    # Support paho 1.x and 2.x
    if hasattr(mqtt, "CallbackAPIVersion"):
        try:
            client = mqtt.Client(
                callback_api_version=mqtt.CallbackAPIVersion.VERSION1,
                protocol=mqtt.MQTTv311,
            )
        except TypeError:
            client = mqtt.Client(protocol=mqtt.MQTTv311)
    else:
        client = mqtt.Client(protocol=mqtt.MQTTv311)

    if args.user:
        client.username_pw_set(args.user, args.password or None)

    def on_connect(_c, _u, _f, rc):
        print(f"connected rc={rc}", flush=True)
        _c.subscribe(args.topic, qos=0)

    def on_message(_c, _u, msg):
        try:
            payload = msg.payload.decode("utf-8", "ignore")
        except Exception:
            payload = str(msg.payload)
        retain = getattr(msg, "retain", False)
        print(f"{msg.topic}: {payload} retain={bool(retain)}", flush=True)

    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(args.host, args.port, keepalive=30)
    try:
        client.loop_forever()
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
