# MQTT Integration for Web Simulator

The web simulator now includes MQTT publishing capability, allowing it to mirror the ESP32 device's behavior and publish sensor data to Home Assistant for validation and testing.

## Features

- **Direct Browser MQTT**: Connects directly from browser to mosquitto via WebSocket (primary method)
- **Python Bridge Fallback**: Optional WebSocket-to-TCP bridge when broker doesn't support WebSocket
- **Home Assistant Discovery**: Publishes discovery messages matching firmware format exactly
- **State-Based Publishing**: Decoupled from rendering for clean architecture
- **Headless CLI Mode**: Publish without browser for CI/CD testing

## Quick Start

### 1. Start Simulator with MQTT Support

```bash
# Start with local mosquitto broker
./scripts/run_sim_with_mqtt.sh --broker

# Or use external broker
./scripts/run_sim_with_mqtt.sh
```

Then open: http://localhost:8000/index.html

### 2. Configure MQTT in Web UI

1. Open the "MQTT Integration" panel
2. Enter broker details:
   - Broker: 127.0.0.1 (or your broker IP)
   - Port: 9001 (WebSocket port)
   - Username/Password: (if required)
3. Set Device ID (default: `sim-hostname`)
4. Set Room Name (default: `WebSim`)
5. Click "Connect"

### 3. Publish Data

- **Manual**: Click "Publish Now" to send current display data
- **Auto**: Set interval and click "Start Auto" for periodic publishing

## MQTT Topics

The simulator uses identical topic structure as firmware:

```
# Discovery (retained)
homeassistant/sensor/{device_id}_temperature/config
homeassistant/sensor/{device_id}_humidity/config
homeassistant/sensor/{device_id}_pressure/config
homeassistant/sensor/{device_id}_battery/config

# Sensor Data (retained)
espsensor/{device_id}/inside/temperature    # °C as "72.5"
espsensor/{device_id}/inside/humidity       # % as "45"
espsensor/{device_id}/inside/pressure       # hPa as "1013.2"
espsensor/{device_id}/battery/percent       # % as "85"
espsensor/{device_id}/battery/voltage       # V as "4.05"
espsensor/{device_id}/wifi/rssi            # dBm as "-50"

# Availability (not retained)
espsensor/{device_id}/availability         # "online"/"offline"
```

## Headless CLI Publisher

For CI/CD and automated testing:

```bash
# Basic usage
python3 scripts/mqtt_sim_publisher.py --broker 127.0.0.1 --port 18884

# Run specific scenario
python3 scripts/mqtt_sim_publisher.py --scenario hot --count 5 --interval 10

# Continuous mode
python3 scripts/mqtt_sim_publisher.py --continuous --scenario normal

# Available scenarios:
# - normal: Typical room conditions with slight variations
# - hot: High temperature (95°F)
# - cold: Low temperature (32°F)
# - low_battery: Battery at 15%
# - missing: Simulates missing sensors
```

## Mosquitto Configuration

The project includes WebSocket support in `mosquitto_test.conf`:

```conf
# TCP listener for regular MQTT
listener 18884 127.0.0.1
allow_anonymous true
persistence false

# WebSocket listener for browser
listener 9001 127.0.0.1
protocol websockets
```

## Python Bridge (Fallback)

If your broker doesn't support WebSocket, use the bridge:

```bash
# Start bridge
python3 scripts/mqtt_sim_bridge.py \
  --mqtt-host 192.168.1.100 \
  --mqtt-port 1883 \
  --ws-port 9002

# Configure browser to connect to bridge on port 9002
```

## Testing

Run tests to verify MQTT integration:

```bash
# Test MQTT functionality
pytest tests/test_web_sim_mqtt.py -v

# Test with local mosquitto
mosquitto -c mosquitto_test.conf &
pytest tests/test_web_sim_mqtt.py
```

## Architecture

### Data Flow
1. Simulator renders display based on data
2. Data state manager updates with new values
3. MQTT client subscribes to state changes
4. On change, publishes to configured broker
5. Home Assistant receives and processes data

### Key Components
- `mqtt-client.js`: Browser MQTT client using MQTT.js
- `mqtt-ui.js`: UI event handlers and controls
- `mqtt_topics.py`: Centralized topic/discovery configuration
- `mqtt_sim_publisher.py`: Headless CLI publisher
- `mqtt_sim_bridge.py`: WebSocket-to-TCP bridge (fallback)

## Home Assistant Integration

The simulator appears as a device in Home Assistant with:
- Device name: `{Room} Sensor`
- Model: `Web Simulator`
- Sensors: Temperature, Humidity, Pressure, Battery, WiFi Signal

Configure automations and dashboards exactly as with real devices.

## Troubleshooting

### Connection Issues
- Verify mosquitto is running: `ps aux | grep mosquitto`
- Check WebSocket port is open: `netstat -an | grep 9001`
- Try fallback bridge if WebSocket fails

### No Data in Home Assistant
- Check MQTT Explorer to verify messages
- Ensure discovery prefix matches HA config (default: `homeassistant`)
- Verify retained flags on sensor data

### Browser Console Errors
- Check MQTT.js loaded from CDN
- Verify WebSocket support in browser
- Check CORS if using external broker