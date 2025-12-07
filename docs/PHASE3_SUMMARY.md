# Phase 3 Complete: MQTT Integration

## Overview

Phase 3 of the ESP32 Device Manager is now complete! This phase adds comprehensive MQTT support including broker connectivity, message inspection, and a data simulator.

## What's New

### Backend Components

1. **MQTT Broker Client** (`scripts/device_manager/mqtt_broker.py`)
   - Connects to local MQTT broker (Mosquitto)
   - Subscribes to all ESP32 and Home Assistant topics
   - Captures all messages (last 1000 stored)
   - Broadcasts messages via WebSocket to frontend
   - Supports publishing messages
   - Subscription management

2. **MQTT Simulator** (`scripts/device_manager/mqtt_simulator.py`)
   - Generates realistic Home Assistant weather data
   - Temperature follows sine wave (peaks 3pm, bottoms 3am)
   - Humidity inversely correlated with temperature
   - Weather conditions change gradually
   - Wind speed with occasional gusts
   - Barometric pressure variations
   - Updates every 60 seconds
   - Fully configurable

3. **Server Integration**
   - 10 new MQTT API endpoints
   - Automatic broker connection on startup
   - Graceful shutdown handling
   - Status monitoring

### Frontend Components

1. **MQTT Inspector** (`web/manager/src/components/MqttInspector.jsx`)
   - Real-time message display
   - Direction indicators (incoming ← / outgoing →)
   - Topic and payload filtering
   - Color-coded messages
   - Auto-scroll with history
   - Timestamp display

2. **Simulator Controls**
   - Start/stop button
   - Status display
   - One-click fake data generation

3. **Message Publishing**
   - Topic input with autocomplete hints
   - Payload input
   - Retain message option
   - QoS selection
   - Send button

4. **Status Dashboard**
   - Broker connection status
   - Message count
   - Simulator running state
   - Auto-refresh every 5 seconds

## New API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/mqtt/status` | Get broker and simulator status |
| POST | `/api/mqtt/publish` | Publish MQTT message |
| GET | `/api/mqtt/messages` | Get recent messages (default 100) |
| GET | `/api/mqtt/subscriptions` | List active subscriptions |
| POST | `/api/mqtt/subscribe` | Subscribe to topic |
| POST | `/api/mqtt/unsubscribe` | Unsubscribe from topic |
| POST | `/api/mqtt/simulator/start` | Start data simulator |
| POST | `/api/mqtt/simulator/stop` | Stop data simulator |

## Setup Requirements

### Install Mosquitto

**macOS:**
```bash
brew install mosquitto
brew services start mosquitto
```

**Ubuntu/Debian:**
```bash
sudo apt-get install mosquitto
sudo systemctl start mosquitto
```

**Windows:**
Download from https://mosquitto.org/download/

### Or use Docker:
```bash
docker run -d -p 1883:1883 eclipse-mosquitto
```

### Or disable MQTT:
```bash
python scripts/start_device_manager.py --no-broker
```

## Usage

1. **Start the servers:**
   ```bash
   # Backend
   python scripts/start_device_manager.py --port 8080 --debug

   # Frontend
   cd web/manager && npm run dev
   ```

2. **Open the UI:** `http://localhost:3000`

3. **Navigate to MQTT tab**

4. **Start simulator** to generate fake Home Assistant data

5. **Watch messages** flow in real-time

6. **Publish messages** to test ESP32 device commands

## Simulated Data

The simulator generates realistic patterns:

- **Temperature**: 40-85°F, peaks at 3pm, bottoms at 3am (sine wave)
- **Humidity**: 20-95%, inversely related to temperature
- **Weather**: Sunny, partly cloudy, cloudy, rainy, snowy, fog, windy
- **Wind**: 0-8 mph baseline, occasional 10-20 mph gusts
- **Pressure**: ~1013 mb with slow variations

Topics match Home Assistant format:
- `homeassistant/sensor/outside/temp_f`
- `homeassistant/sensor/outside/humidity`
- `homeassistant/sensor/outside/condition`
- `homeassistant/sensor/outside/wind_mph`
- `homeassistant/sensor/outside/pressure_mb`

## WebSocket Messages

New message types:
```javascript
// MQTT message received/sent
{
  type: "mqtt",
  topic: "espsensor/office/temperature",
  payload: "72.5",
  direction: "in", // or "out"
  timestamp: 1234567890
}

// MQTT broker status
{
  type: "mqtt_status",
  connected: true,
  message: "Connected to MQTT broker"
}
```

## Screenshots

The MQTT tab shows:
- ✅ Connection status (broker + simulator)
- ✅ Start/stop simulator controls
- ✅ Publish message form with topic/payload
- ✅ Real-time message log with filters
- ✅ Direction arrows (← incoming, → outgoing)
- ✅ Color-coded topics and payloads
- ✅ Timestamps for all messages

## Testing

1. Start simulator → messages appear every 60s
2. Publish manual message → appears in log
3. Connect ESP32 device → see its messages
4. Filter by topic: `espsensor/#`
5. Filter by payload: `temperature`

## Next: Phase 4

With Phase 3 complete, Phase 4 will add:
- Screenshot handler (decode 1-bit display buffer)
- Display viewer component
- Control panel (sleep interval, reboot, diagnostics)
- Status dashboard (battery, memory, connectivity)

## Files Changed/Added

### Backend
- ✅ `scripts/device_manager/mqtt_broker.py` (new, 250 lines)
- ✅ `scripts/device_manager/mqtt_simulator.py` (new, 220 lines)
- ✅ `scripts/device_manager/server.py` (updated, +100 lines)

### Frontend
- ✅ `web/manager/src/components/MqttInspector.jsx` (new, 210 lines)
- ✅ `web/manager/src/api/deviceApi.js` (updated, +45 lines)
- ✅ `web/manager/src/App.jsx` (updated, +2 imports)
- ✅ `web/manager/src/styles/manager.css` (updated, +200 lines)

### Documentation
- ✅ `web/manager/MQTT_SETUP.md` (new)
- ✅ `docs/PHASE3_SUMMARY.md` (this file)

## Total Implementation

**Lines of Code Added:**
- Backend: ~470 lines
- Frontend: ~255 lines
- CSS: ~200 lines
- **Total: ~925 lines**

## Status

✅ Phase 1: Serial Console - **Complete**
✅ Phase 2: Flash Manager - **Complete**
✅ Phase 3: MQTT Integration - **Complete**
⏳ Phase 4: Display & Control - In Progress
⏳ Phase 5: Polish & Testing - Pending
