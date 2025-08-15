#!/usr/bin/env python3
import os
import sys

try:
    import yaml  # type: ignore
except Exception:
    yaml = None

def parse_duration(s: str) -> int:
    if not s:
        return 3600
    s = str(s).strip().lower()
    try:
        # allow plain seconds
        return int(s)
    except Exception:
        pass
    num = ""
    unit = ""
    for ch in s:
        if ch.isdigit():
            num += ch
        else:
            unit += ch
    try:
        n = int(num)
    except Exception:
        return 3600
    if unit in ("s", "sec", "secs", "second", "seconds"):
        return n
    if unit in ("m", "min", "mins", "minute", "minutes"):
        return n * 60
    if unit in ("h", "hr", "hrs", "hour", "hours"):
        return n * 3600
    if unit in ("d", "day", "days"):
        return n * 86400
    return 3600

def c_string(s: str) -> str:
    return '"' + str(s).replace('\\', r'\\').replace('"', r'\"') + '"'

def main():
    prj = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    cfg_dir = os.path.join(prj, 'config')
    y_path = os.path.join(cfg_dir, 'device.yaml')
    if not os.path.exists(y_path):
        y_path = os.path.join(cfg_dir, 'device.sample.yaml')
    data = {}
    if yaml is not None and os.path.exists(y_path):
        with open(y_path, 'r') as f:
            data = yaml.safe_load(f) or {}
    # defaults
    room_name = data.get('room_name', 'Room')
    wake_interval = parse_duration(data.get('wake_interval', '2h'))
    full_refresh_every = int(data.get('full_refresh_every', 12) or 12)
    outside_source = str(data.get('outside_source', 'mqtt'))
    wifi = data.get('wifi', {})
    ha = data.get('ha_entities', {})
    mqtt = data.get('mqtt', {})
    base_topics = mqtt.get('base_topics', {})
    wifi_ssid = wifi.get('ssid', '')
    wifi_pass = wifi.get('password', '')
    mqtt_host = mqtt.get('host', '')
    mqtt_port = int(mqtt.get('port', 1883) or 1883)
    mqtt_pub = base_topics.get('publish', 'sensors/' + room_name.lower())
    mqtt_sub = base_topics.get('subscribe', 'home/outdoor')

    out_dir = os.path.join(prj, 'firmware', 'arduino', 'src')
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, 'generated_config.h')
    with open(out_path, 'w') as f:
        f.write('// Auto-generated from config/device.yaml by scripts/gen_device_header.py\n')
        f.write('#pragma once\n\n')
        f.write(f'#define ROOM_NAME {c_string(room_name)}\n')
        f.write(f'#define WAKE_INTERVAL_SEC {wake_interval}\n')
        f.write(f'#define FULL_REFRESH_EVERY {full_refresh_every}\n')
        f.write(f'#define OUTSIDE_SOURCE {c_string(outside_source)}\n')
        f.write(f'#define WIFI_SSID {c_string(wifi_ssid)}\n')
        f.write(f'#define WIFI_PASS {c_string(wifi_pass)}\n')
        f.write(f'#define MQTT_HOST {c_string(mqtt_host)}\n')
        f.write(f'#define MQTT_PORT {mqtt_port}\n')
        f.write(f'#define MQTT_PUB_BASE {c_string(mqtt_pub)}\n')
        f.write(f'#define MQTT_SUB_BASE {c_string(mqtt_sub)}\n')
    print(f"Wrote {out_path}")

if __name__ == '__main__':
    main()


