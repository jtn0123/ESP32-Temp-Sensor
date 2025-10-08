"""
Test MQTT integration for web simulator.
Verifies that simulator publishes data matching firmware format.
"""

import json
import os
import sys
import time
import pytest

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.mqtt_sim_publisher import SimulatorMQTTPublisher
from scripts.mqtt_topics import build_topic, build_discovery_topic, format_sensor_value
from scripts.test_mqtt_integration import MqttTestClient


def test_simulator_discovery_format(mosquitto_broker):
    """Test that simulator publishes correct discovery format."""
    host, port = mosquitto_broker
    
    device_id = "test_sim_001"
    room_name = "TestRoom"
    
    # Create publisher
    publisher = SimulatorMQTTPublisher(
        broker=host,
        port=port,
        device_id=device_id,
        room_name=room_name
    )
    
    # Create subscriber to verify
    subscriber = MqttTestClient(host, port, client_id="test_sub")
    subscriber.connect()
    
    # Subscribe to discovery topics
    temp_discovery = build_discovery_topic(device_id, "temperature")
    hum_discovery = build_discovery_topic(device_id, "humidity")
    
    messages = {}
    def on_message(client, userdata, msg):
        messages[msg.topic] = json.loads(msg.payload.decode())
    
    subscriber.client.on_message = on_message
    # Subscribe to all discovery topics (+ wildcard must be entire level, not part of device_id)
    subscriber.subscribe_and_confirm("homeassistant/sensor/+/config")
    
    # Connect publisher and wait for discovery
    publisher.connect()
    time.sleep(2)
    
    # Verify discovery messages
    assert temp_discovery in messages, "Temperature discovery not published"
    assert hum_discovery in messages, "Humidity discovery not published"
    
    # Check temperature discovery format
    temp_config = messages[temp_discovery]
    assert temp_config["unique_id"] == f"{device_id}_temperature"
    assert temp_config["device_class"] == "temperature"
    assert temp_config["unit_of_measurement"] == "°C"
    assert temp_config["state_topic"] == build_topic(device_id, "inside/temperature")
    assert temp_config["availability_topic"] == build_topic(device_id, "availability")
    assert temp_config["device"]["identifiers"] == [device_id]
    assert room_name in temp_config["device"]["name"]
    
    # Cleanup
    publisher.disconnect()
    subscriber.disconnect()


def test_simulator_sensor_data_format(mosquitto_broker):
    """Test that simulator publishes sensor data in correct format."""
    host, port = mosquitto_broker
    
    device_id = "test_sim_002"
    room_name = "TestRoom"
    
    publisher = SimulatorMQTTPublisher(
        broker=host,
        port=port,
        device_id=device_id,
        room_name=room_name
    )
    
    subscriber = MqttTestClient(host, port, client_id="test_sub2")
    subscriber.connect()
    
    # Subscribe to sensor topics
    messages = {}
    def on_message(client, userdata, msg):
        messages[msg.topic] = msg.payload.decode()
    
    subscriber.client.on_message = on_message
    subscriber.subscribe_and_confirm(f"espsensor/{device_id}/+/+")
    
    # Connect and publish test data
    publisher.connect()
    test_data = {
        "inside_temp_f": 77.0,  # 25°C
        "inside_hum_pct": 50,
        "pressure_hpa": 1013.2,
        "battery_percent": 75,
        "battery_voltage": 3.95
    }
    publisher.publish_sensor_data(test_data)
    
    # Wait for messages
    time.sleep(2)
    
    # Verify data format (plain text numbers, not JSON)
    temp_topic = build_topic(device_id, "inside/temperature")
    assert temp_topic in messages
    temp_value = float(messages[temp_topic])
    assert 24.5 < temp_value < 25.5, f"Temperature conversion error: {temp_value}"
    
    hum_topic = build_topic(device_id, "inside/humidity")
    assert hum_topic in messages
    assert messages[hum_topic] == "50.0"
    
    pressure_topic = build_topic(device_id, "inside/pressure")
    assert pressure_topic in messages
    assert messages[pressure_topic] == "1013.2"
    
    battery_topic = build_topic(device_id, "battery/percent")
    assert battery_topic in messages
    assert messages[battery_topic] == "75"
    
    voltage_topic = build_topic(device_id, "battery/voltage")
    assert voltage_topic in messages
    assert messages[voltage_topic] == "3.95"
    
    # Cleanup
    publisher.disconnect()
    subscriber.disconnect()


def test_simulator_availability_not_retained(mosquitto_broker):
    """Test that availability messages are not retained."""
    host, port = mosquitto_broker
    
    device_id = "test_sim_003"
    
    publisher = SimulatorMQTTPublisher(
        broker=host,
        port=port,
        device_id=device_id,
        room_name="Test"
    )
    
    # Connect and publish availability
    publisher.connect()
    time.sleep(1)
    publisher.disconnect()
    time.sleep(1)
    
    # New subscriber should not receive availability
    subscriber = MqttTestClient(host, port, client_id="test_sub3")
    subscriber.connect()
    
    messages = []
    def on_message(client, userdata, msg):
        messages.append((msg.topic, msg.payload.decode(), msg.retain))
    
    subscriber.client.on_message = on_message
    availability_topic = build_topic(device_id, "availability")
    subscriber.subscribe_and_confirm(availability_topic)
    
    # Wait briefly
    time.sleep(1)
    
    # Should not receive retained availability
    availability_messages = [m for m in messages if m[0] == availability_topic]
    assert len(availability_messages) == 0, "Availability should not be retained"
    
    subscriber.disconnect()


def test_simulator_matches_firmware_topics():
    """Test that simulator uses same topic structure as firmware."""
    device_id = "test_device"
    
    # These should match firmware patterns from mqtt_client.cpp
    expected_topics = {
        "temperature": f"espsensor/{device_id}/inside/temperature",
        "humidity": f"espsensor/{device_id}/inside/humidity",
        "pressure": f"espsensor/{device_id}/inside/pressure",
        "battery_pct": f"espsensor/{device_id}/battery/percent",
        "battery_volt": f"espsensor/{device_id}/battery/voltage",
        "availability": f"espsensor/{device_id}/availability",
        "rssi": f"espsensor/{device_id}/wifi/rssi"
    }
    
    # Verify topic builder matches
    assert build_topic(device_id, "inside/temperature") == expected_topics["temperature"]
    assert build_topic(device_id, "inside/humidity") == expected_topics["humidity"]
    assert build_topic(device_id, "availability") == expected_topics["availability"]


def test_value_formatting():
    """Test that value formatting matches firmware."""
    # Temperature - 1 decimal place
    assert format_sensor_value(23.456, "temperature") == "23.5"
    assert format_sensor_value(23.444, "temperature") == "23.4"
    
    # Humidity - 1 decimal place
    assert format_sensor_value(45.678, "humidity") == "45.7"
    
    # Pressure - 1 decimal place
    assert format_sensor_value(1013.234, "pressure") == "1013.2"
    
    # Battery percent - integer
    assert format_sensor_value(75.6, "battery_percent") == "76"
    assert format_sensor_value(75.4, "battery_percent") == "75"
    
    # Battery voltage - 2 decimal places
    assert format_sensor_value(3.956, "battery_voltage") == "3.96"
    assert format_sensor_value(3.954, "battery_voltage") == "3.95"
    
    # RSSI - integer
    assert format_sensor_value(-50.7, "rssi") == "-51"


if __name__ == "__main__":
    # For manual testing
    import subprocess
    
    print("Starting mosquitto for testing...")
    proc = subprocess.Popen(["mosquitto", "-c", "mosquitto_test.conf"])
    time.sleep(1)
    
    try:
        pytest.main([__file__, "-v"])
    finally:
        proc.terminate()