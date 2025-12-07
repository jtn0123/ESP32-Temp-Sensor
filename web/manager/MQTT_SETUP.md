# MQTT Broker Setup

The Device Manager includes MQTT functionality for monitoring device communication and simulating Home Assistant data.

## MQTT Broker Requirement

The MQTT implementation uses `paho-mqtt` client to connect to a local MQTT broker. You need to have one running:

### Option 1: Mosquitto (Recommended)

**Install Mosquitto:**

macOS:
```bash
brew install mosquitto
brew services start mosquitto
```

Ubuntu/Debian:
```bash
sudo apt-get install mosquitto
sudo systemctl start mosquitto
sudo systemctl enable mosquitto
```

Windows:
Download from https://mosquitto.org/download/

**Default Configuration:**
- Host: `localhost` (127.0.0.1)
- Port: `1883`
- No authentication by default

### Option 2: Docker

```bash
docker run -d -p 1883:1883 -p 9001:9001 eclipse-mosquitto
```

### Option 3: Disable MQTT

Start the server with MQTT disabled:
```bash
python scripts/start_device_manager.py --no-broker
```

## MQTT Features

Once the broker is running, the Device Manager provides:

1. **Message Inspector**
   - View all MQTT messages in real-time
   - Filter by topic or payload
   - See incoming/outgoing direction
   - Timestamps for all messages

2. **Message Publishing**
   - Manually publish messages to any topic
   - Support for retained messages
   - QoS level selection

3. **Data Simulator**
   - Generate fake Home Assistant weather data
   - Simulates outdoor temperature, humidity, pressure, wind, weather condition
   - Sine-wave temperature patterns (peaks at 3pm, bottoms at 3am)
   - Updates every 60 seconds by default
   - Perfect for testing ESP32 display without real sensors

## Topics

The simulator publishes to these topics (compatible with the ESP32 firmware):

- `homeassistant/sensor/outside/temp_f` - Temperature in Fahrenheit
- `homeassistant/sensor/outside/temp` - Temperature in Celsius
- `homeassistant/sensor/outside/humidity` - Relative humidity (%)
- `homeassistant/sensor/outside/condition` - Weather condition text
- `homeassistant/sensor/outside/wind_mph` - Wind speed (mph)
- `homeassistant/sensor/outside/pressure_mb` - Barometric pressure (millibars)

ESP32 devices publish to:
- `espsensor/{device_id}/inside/temperature`
- `espsensor/{device_id}/inside/humidity`
- `espsensor/{device_id}/battery/percent`
- And more...

## Testing

1. Start the backend with MQTT enabled (default)
2. Open the Device Manager UI
3. Navigate to the "MQTT" tab
4. Click "Start Simulator" to begin generating fake data
5. Watch messages appear in real-time
6. Try publishing a message manually

## Troubleshooting

**"Could not connect to MQTT broker"**
- Ensure Mosquitto is running: `mosquitto -v`
- Check port 1883 is not in use: `lsof -i :1883` (macOS/Linux)
- Try starting with `--no-broker` to disable MQTT

**Simulator not working**
- Check MQTT status shows "Connected"
- Verify simulator shows "Running" status
- Look at browser console for errors

**No messages appearing**
- Ensure WebSocket is connected (green indicator in header)
- Check MQTT broker is receiving messages: `mosquitto_sub -t '#' -v`
- Try refreshing the page
