# ESP32 Device Manager

A comprehensive tool for managing ESP32 temperature sensor devices, including:
- **Serial Console** - Live serial output with filtering and command input
- **Flash Manager** - One-click firmware flashing with progress tracking
- **MQTT Inspector** - View/send MQTT messages, run data simulator
- **Display Viewer** - Pull and view device screenshots
- **Control Panel** - Set sleep interval, reboot, diagnostic mode

## Quick Start

### Option 1: Combined Script (Recommended)
```bash
# From project root
./scripts/run_device_manager.sh

# With frontend hot-reload (for development)
./scripts/run_device_manager.sh --dev
```

### Option 2: Manual Start

1. **Start MQTT Broker** (if not already running):
```bash
mosquitto -c mosquitto_test.conf
```

2. **Start Backend**:
```bash
python scripts/start_device_manager.py --port 8080
```

3. **Start Frontend** (optional, for development):
```bash
cd web/manager
npm install
npm run dev
```

## URLs

| Service | URL |
|---------|-----|
| Backend API | http://localhost:8080 |
| Frontend (dev) | http://localhost:5173 |
| API Docs | http://localhost:8080/docs |
| MQTT Broker | localhost:1883 |

## Features

### Serial Console
- Live serial output from connected device
- Color-coded log levels (ERROR, WARN, INFO, DEBUG)
- Filter/search logs
- Send commands to device
- Pause/resume auto-scroll

### Flash Manager
- Build configurations: Dev, Prod, Battery Test
- Progress bar with stage indication
- Build output log
- Cancel flash operation

### MQTT Inspector
- View all MQTT messages (incoming/outgoing)
- Filter by topic or payload
- Publish custom messages
- Start/stop weather data simulator
- Simulator generates:
  - Temperature (sine wave based on time of day)
  - Humidity (inversely related to temperature)
  - Weather conditions (sunny, cloudy, rain, etc.)
  - Wind speed with occasional gusts
  - Barometric pressure

### Display Viewer
- Request screenshot from device
- Auto-refresh option (5s, 10s, 30s, 60s intervals)
- Test image for development
- 2x scaling for visibility

### Control Panel
- **Sleep Interval**: Slider from 1 minute to 1 hour
- **Reboot**: Remote device restart
- **Diagnostic Mode**: Enable/disable verbose logging
- **Force Refresh**: Trigger display update

## API Endpoints

### Serial
- `GET /api/ports` - List serial ports
- `POST /api/serial/connect` - Connect to port
- `POST /api/serial/disconnect` - Disconnect
- `POST /api/serial/send` - Send data
- `GET /api/serial/status` - Connection status

### Flash
- `POST /api/flash/start` - Start flash
- `GET /api/flash/status` - Get progress
- `POST /api/flash/cancel` - Cancel flash

### MQTT
- `GET /api/mqtt/status` - Broker/simulator status
- `POST /api/mqtt/publish` - Publish message
- `GET /api/mqtt/messages` - Recent messages
- `POST /api/mqtt/simulator/start` - Start simulator
- `POST /api/mqtt/simulator/stop` - Stop simulator

### Device
- `POST /api/device/screenshot` - Request screenshot
- `GET /api/device/screenshot/latest` - Get latest
- `POST /api/device/command` - Send command
- `GET /api/device/status` - Device status

### Config
- `POST /api/config/sleep-interval` - Set sleep interval

## WebSocket

Connect to `ws://localhost:8080/ws` for real-time updates:

```javascript
// Message types received:
{ type: "serial", data: "log line", timestamp: 1234567890 }
{ type: "mqtt", topic: "...", payload: "...", direction: "in"|"out" }
{ type: "flash_progress", percent: 45, stage: "writing", message: "..." }
{ type: "flash_complete", success: true, message: "..." }
{ type: "screenshot", data: "base64...", width: 250, height: 122 }
{ type: "device_status", battery: 87, heap: 45000 }
```

## Development

### Backend
```bash
# Install dependencies
pip install fastapi uvicorn websockets pyserial paho-mqtt pillow

# Run with auto-reload
uvicorn scripts.device_manager.server:app --reload --port 8080
```

### Frontend
```bash
cd web/manager
npm install
npm run dev
```

## Firmware Commands

The device responds to these MQTT commands:

| Topic | Payload | Description |
|-------|---------|-------------|
| `.../cmd/sleep_interval` | `60`-`3600` | Set sleep seconds |
| `.../cmd/reboot` | (any) | Reboot device |
| `.../cmd/diagnostic_mode` | `0` or `1` | Toggle diagnostics |
| `.../cmd/screenshot` | (any) | Capture display |

## Troubleshooting

### "MQTT broker not connected"
- Ensure Mosquitto is running: `mosquitto -c mosquitto_test.conf`
- Check port 1883 is available: `lsof -i :1883`

### "No serial ports found"
- Connect ESP32 via USB
- Check USB drivers (CP210x, CH340)
- On macOS: `ls /dev/tty.usb*`

### "Flash failed"
- Ensure device is in bootloader mode (hold BOOT, press RESET)
- Check serial port permissions
- Try a different USB cable
