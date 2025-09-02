#!/usr/bin/env python3
"""
Centralized MQTT topic and discovery configuration.
Single source of truth matching firmware implementation.
"""

import json
import os
import re
from math import isfinite


def build_topic(device_id: str, suffix: str) -> str:
    """Build MQTT topic matching firmware pattern."""
    return f"espsensor/{device_id}/{suffix}"


def build_discovery_topic(device_id: str, sensor_key: str) -> str:
    """Build Home Assistant discovery topic."""
    return f"homeassistant/sensor/{device_id}_{sensor_key}/config"


def get_wake_interval_sec() -> int:
    """Read wake interval from generated config header."""
    header_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "firmware", "arduino", "src", "generated_config.h"
    )
    try:
        with open(header_path, 'r') as f:
            content = f.read()
        match = re.search(r'#define\s+WAKE_INTERVAL_SEC\s+(\d+)', content)
        return int(match.group(1)) if match else 7200
    except (FileNotFoundError, AttributeError):
        return 7200  # Default 2 hours


def build_discovery_config(
    device_id: str,
    sensor_key: str,
    sensor_name: str,
    room_name: str,
    unit: str,
    device_class: str,
    state_topic_suffix: str,
    precision: int = 1
) -> dict:
    """
    Build Home Assistant discovery payload matching firmware ha_discovery.cpp.
    
    Args:
        device_id: Unique device identifier
        sensor_key: Sensor key for unique_id (e.g., "temperature")
        sensor_name: Human-readable sensor name
        room_name: Room/location name
        unit: Unit of measurement
        device_class: HA device class
        state_topic_suffix: Topic suffix for state (e.g., "inside/temperature")
        precision: Suggested display precision
    """
    availability_topic = build_topic(device_id, "availability")
    state_topic = build_topic(device_id, state_topic_suffix)
    expire_after = get_wake_interval_sec() + 120
    
    config = {
        "name": sensor_name,
        "unique_id": f"{device_id}_{sensor_key}",
        "state_topic": state_topic,
        "availability_topic": availability_topic,
        "payload_available": "online",
        "payload_not_available": "offline",
        "device_class": device_class,
        "state_class": "measurement",
        "expire_after": expire_after,
        "device": {
            "identifiers": [device_id],
            "name": f"{room_name} Sensor",
            "model": "ESP32 Environmental Sensor",
            "manufacturer": "DIY",
            "sw_version": "web-sim"
        }
    }
    
    # Add unit if specified
    if unit:
        config["unit_of_measurement"] = unit
        
    # Add precision hint if relevant
    if unit in ["°C", "°F", "V"]:
        config["suggested_display_precision"] = precision
    
    # Add value template for rounding (matching firmware)
    if device_class in ["temperature", "humidity", "atmospheric_pressure"]:
        config["value_template"] = "{{ value | round(1) }}"
    
    return config


def get_standard_sensors(device_id: str, room_name: str) -> dict:
    """
    Get standard sensor configurations matching firmware.
    
    Returns dict of sensor_key -> (discovery_config, state_topic_suffix)
    """
    sensors = {
        "temperature": (
            build_discovery_config(
                device_id=device_id,
                sensor_key="temperature",
                sensor_name=f"{room_name} Temperature",
                room_name=room_name,
                unit="°C",
                device_class="temperature",
                state_topic_suffix="inside/temperature",
                precision=1
            ),
            "inside/temperature"
        ),
        "humidity": (
            build_discovery_config(
                device_id=device_id,
                sensor_key="humidity",
                sensor_name=f"{room_name} Humidity",
                room_name=room_name,
                unit="%",
                device_class="humidity",
                state_topic_suffix="inside/humidity",
                precision=1
            ),
            "inside/humidity"
        ),
        "pressure": (
            build_discovery_config(
                device_id=device_id,
                sensor_key="pressure",
                sensor_name=f"{room_name} Pressure",
                room_name=room_name,
                unit="hPa",
                device_class="atmospheric_pressure",
                state_topic_suffix="inside/pressure",
                precision=1
            ),
            "inside/pressure"
        ),
        "battery_voltage": (
            build_discovery_config(
                device_id=device_id,
                sensor_key="battery_voltage",
                sensor_name=f"{room_name} Battery Voltage",
                room_name=room_name,
                unit="V",
                device_class="voltage",
                state_topic_suffix="battery/voltage",
                precision=2
            ),
            "battery/voltage"
        ),
        "battery_percent": (
            build_discovery_config(
                device_id=device_id,
                sensor_key="battery",
                sensor_name=f"{room_name} Battery",
                room_name=room_name,
                unit="%",
                device_class="battery",
                state_topic_suffix="battery/percent",
                precision=0
            ),
            "battery/percent"
        ),
        "rssi": (
            build_discovery_config(
                device_id=device_id,
                sensor_key="rssi",
                sensor_name=f"{room_name} WiFi Signal",
                room_name=room_name,
                unit="dBm",
                device_class="signal_strength",
                state_topic_suffix="wifi/rssi",
                precision=0
            ),
            "wifi/rssi"
        )
    }
    
    return sensors


def format_sensor_value(value: float, sensor_type: str) -> str:
    """
    Format sensor value to match firmware output.
    Firmware sends plain text numbers, not JSON.
    """
    if value is None or (isinstance(value, float) and not isfinite(value)):
        return ""
    
    # Match firmware precision
    if sensor_type in ["temperature", "humidity", "pressure"]:
        return f"{value:.1f}"
    elif sensor_type == "battery_voltage":
        return f"{value:.2f}"
    elif sensor_type in ["battery_percent", "rssi"]:
        return str(int(value))
    else:
        return str(value)


# Retention rules matching firmware
RETAINED_TOPICS = {
    "discovery": True,    # HA discovery configs
    "sensor_data": True,  # Sensor readings
    "availability": False # Online/offline status
}


if __name__ == "__main__":
    # Example usage
    device_id = "web_sim_test"
    room_name = "WebSim"
    
    print("=== MQTT Topics for Web Simulator ===\n")
    
    # Discovery topics
    sensors = get_standard_sensors(device_id, room_name)
    for key, (config, suffix) in sensors.items():
        discovery_topic = build_discovery_topic(device_id, key)
        state_topic = build_topic(device_id, suffix)
        print(f"{key.upper()}:")
        print(f"  Discovery: {discovery_topic}")
        print(f"  State:     {state_topic}")
        print()
    
    # Availability
    print("AVAILABILITY:")
    print(f"  Topic: {build_topic(device_id, 'availability')}")
    print(f"  Retained: {RETAINED_TOPICS['availability']}")