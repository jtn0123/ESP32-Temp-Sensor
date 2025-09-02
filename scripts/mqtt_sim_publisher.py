#!/usr/bin/env python3
"""
Headless MQTT publisher for CI testing.
Publishes simulated sensor data matching web simulator behavior.
"""

import argparse
import json
import os
import sys
import time
import random
from typing import Dict, Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import paho.mqtt.client as mqtt
except ImportError:
    print("Error: paho-mqtt not installed. Install with: pip install paho-mqtt")
    sys.exit(1)

from scripts.mqtt_topics import (
    build_topic,
    build_discovery_topic,
    get_standard_sensors,
    format_sensor_value,
    RETAINED_TOPICS
)


class SimulatorMQTTPublisher:
    """Headless MQTT publisher mimicking web simulator."""
    
    def __init__(self, broker: str, port: int, device_id: str, room_name: str,
                 username: Optional[str] = None, password: Optional[str] = None):
        self.broker = broker
        self.port = port
        self.device_id = device_id
        self.room_name = room_name
        self.is_connected = False
        
        # Create MQTT client
        if hasattr(mqtt, "CallbackAPIVersion"):
            try:
                self.client = mqtt.Client(
                    client_id=device_id,
                    callback_api_version=mqtt.CallbackAPIVersion.VERSION1,
                    protocol=mqtt.MQTTv311
                )
            except TypeError:
                self.client = mqtt.Client(client_id=device_id, protocol=mqtt.MQTTv311)
        else:
            self.client = mqtt.Client(client_id=device_id, protocol=mqtt.MQTTv311)
        
        # Set credentials if provided
        if username:
            self.client.username_pw_set(username, password)
        
        # Set callbacks
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
    
    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.is_connected = True
            print(f"Connected to {self.broker}:{self.port}")
            # Publish availability
            self.publish_availability(True)
            # Publish discovery
            self.publish_discovery()
        else:
            print(f"Connection failed with code {rc}")
    
    def _on_disconnect(self, client, userdata, rc):
        self.is_connected = False
        print(f"Disconnected from broker (rc={rc})")
    
    def connect(self):
        """Connect to MQTT broker."""
        print(f"Connecting to {self.broker}:{self.port}...")
        self.client.connect(self.broker, self.port, keepalive=60)
        self.client.loop_start()
        
        # Wait for connection
        timeout = 10
        start = time.time()
        while not self.is_connected and (time.time() - start) < timeout:
            time.sleep(0.1)
        
        if not self.is_connected:
            raise ConnectionError(f"Failed to connect to {self.broker}:{self.port}")
    
    def disconnect(self):
        """Disconnect from broker."""
        if self.is_connected:
            self.publish_availability(False)
        self.client.loop_stop()
        self.client.disconnect()
    
    def publish_availability(self, online: bool):
        """Publish availability status."""
        topic = build_topic(self.device_id, "availability")
        payload = "online" if online else "offline"
        self.client.publish(topic, payload, retain=False, qos=0)
        print(f"Published: {topic} = {payload}")
    
    def publish_discovery(self):
        """Publish Home Assistant discovery messages."""
        sensors = get_standard_sensors(self.device_id, self.room_name)
        
        for sensor_key, (config, _) in sensors.items():
            topic = build_discovery_topic(self.device_id, sensor_key)
            payload = json.dumps(config)
            self.client.publish(topic, payload, retain=True, qos=1)
            print(f"Published discovery: {sensor_key}")
    
    def publish_sensor_data(self, data: Dict):
        """Publish sensor data matching firmware format."""
        # Temperature (convert F to C)
        if "inside_temp_f" in data:
            temp_c = (data["inside_temp_f"] - 32) * 5 / 9
            topic = build_topic(self.device_id, "inside/temperature")
            value = format_sensor_value(temp_c, "temperature")
            self.client.publish(topic, value, retain=True, qos=0)
            print(f"Published: {topic} = {value}")
        
        # Humidity
        if "inside_hum_pct" in data:
            topic = build_topic(self.device_id, "inside/humidity")
            value = format_sensor_value(data["inside_hum_pct"], "humidity")
            self.client.publish(topic, value, retain=True, qos=0)
            print(f"Published: {topic} = {value}")
        
        # Pressure
        if "pressure_hpa" in data:
            topic = build_topic(self.device_id, "inside/pressure")
            value = format_sensor_value(data["pressure_hpa"], "pressure")
            self.client.publish(topic, value, retain=True, qos=0)
            print(f"Published: {topic} = {value}")
        
        # Battery
        if "battery_percent" in data:
            topic = build_topic(self.device_id, "battery/percent")
            value = format_sensor_value(data["battery_percent"], "battery_percent")
            self.client.publish(topic, value, retain=True, qos=0)
            print(f"Published: {topic} = {value}")
        
        if "battery_voltage" in data:
            topic = build_topic(self.device_id, "battery/voltage")
            value = format_sensor_value(data["battery_voltage"], "battery_voltage")
            self.client.publish(topic, value, retain=True, qos=0)
            print(f"Published: {topic} = {value}")
        
        # WiFi RSSI (simulated)
        topic = build_topic(self.device_id, "wifi/rssi")
        self.client.publish(topic, "-50", retain=True, qos=0)
        print(f"Published: {topic} = -50")
    
    def generate_test_data(self, scenario: str = "normal") -> Dict:
        """Generate test data for different scenarios."""
        base_data = {
            "inside_temp_f": 72.5,
            "inside_hum_pct": 45,
            "pressure_hpa": 1013.2,
            "battery_percent": 85,
            "battery_voltage": 4.05
        }
        
        if scenario == "normal":
            # Add some variation
            base_data["inside_temp_f"] += random.uniform(-2, 2)
            base_data["inside_hum_pct"] += random.uniform(-5, 5)
            base_data["pressure_hpa"] += random.uniform(-2, 2)
        
        elif scenario == "hot":
            base_data["inside_temp_f"] = 95.0
            base_data["inside_hum_pct"] = 65
        
        elif scenario == "cold":
            base_data["inside_temp_f"] = 32.0
            base_data["inside_hum_pct"] = 30
        
        elif scenario == "low_battery":
            base_data["battery_percent"] = 15
            base_data["battery_voltage"] = 3.65
        
        elif scenario == "missing":
            # Simulate missing sensors
            del base_data["pressure_hpa"]
            del base_data["inside_hum_pct"]
        
        return base_data
    
    def run_cycle(self, scenario: str = "normal", count: int = 1, interval: int = 30):
        """Run a publishing cycle."""
        print(f"\nRunning {scenario} scenario, {count} iterations, {interval}s interval")
        
        for i in range(count):
            data = self.generate_test_data(scenario)
            print(f"\nIteration {i+1}/{count}:")
            self.publish_sensor_data(data)
            
            if i < count - 1:
                print(f"Waiting {interval} seconds...")
                time.sleep(interval)


def main():
    parser = argparse.ArgumentParser(description="Headless MQTT simulator publisher")
    parser.add_argument("--broker", default="127.0.0.1", help="MQTT broker address")
    parser.add_argument("--port", type=int, default=18884, help="MQTT broker port")
    parser.add_argument("--device-id", default="sim-cli-test", help="Device ID")
    parser.add_argument("--room", default="CLISim", help="Room name")
    parser.add_argument("--user", help="MQTT username")
    parser.add_argument("--password", help="MQTT password")
    parser.add_argument("--scenario", default="normal",
                       choices=["normal", "hot", "cold", "low_battery", "missing"],
                       help="Test scenario")
    parser.add_argument("--count", type=int, default=1, help="Number of publish cycles")
    parser.add_argument("--interval", type=int, default=30, help="Interval between cycles (seconds)")
    parser.add_argument("--continuous", action="store_true", help="Run continuously")
    
    args = parser.parse_args()
    
    # Create publisher
    publisher = SimulatorMQTTPublisher(
        broker=args.broker,
        port=args.port,
        device_id=args.device_id,
        room_name=args.room,
        username=args.user,
        password=args.password
    )
    
    try:
        # Connect
        publisher.connect()
        
        # Run cycles
        if args.continuous:
            print("Running continuously (Ctrl+C to stop)...")
            while True:
                publisher.run_cycle(args.scenario, 1, args.interval)
        else:
            publisher.run_cycle(args.scenario, args.count, args.interval)
        
        # Keep connection alive for a moment to ensure delivery
        time.sleep(2)
        
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    except Exception as e:
        print(f"Error: {e}")
        return 1
    finally:
        publisher.disconnect()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())