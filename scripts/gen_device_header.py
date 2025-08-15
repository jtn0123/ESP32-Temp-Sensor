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
    # battery
    battery = data.get('battery', {})
    capacity_mAh = int(battery.get('capacity_mAh', 3500) or 3500)
    sleep_current_mA = float(battery.get('sleep_current_mA', 0.09) or 0.09)
    active_current_mA = float(battery.get('active_current_mA', 80) or 80)
    active_seconds = int(data.get('active_seconds', 10) or 10)
    vbat_adc_pin = int(battery.get('adc_pin', -1) or -1)
    vbat_divider = float(battery.get('divider', 2.0) or 2.0)
    adc_max = int(battery.get('adc_max', 4095) or 4095)
    adc_ref = float(battery.get('adc_ref', 3.3) or 3.3)

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
        f.write(f'#define BATTERY_CAPACITY_MAH {capacity_mAh}\n')
        f.write(f'#define SLEEP_CURRENT_MA {sleep_current_mA}\n')
        f.write(f'#define ACTIVE_CURRENT_MA {active_current_mA}\n')
        f.write(f'#define ACTIVE_SECONDS {active_seconds}\n')
        f.write(f'#define VBAT_ADC_PIN {vbat_adc_pin}\n')
        f.write(f'#define VBAT_DIVIDER {vbat_divider}\n')
        f.write(f'#define ADC_MAX_COUNTS {adc_max}\n')
        f.write(f'#define ADC_REF_V {adc_ref}\n')
    print(f"Wrote {out_path}")

if __name__ == '__main__':
    main()


