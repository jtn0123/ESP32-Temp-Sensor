# ESP32 Device Manager

A comprehensive web-based tool for managing ESP32 devices, built with React (frontend) and FastAPI (backend).

## ✨ Features

### ✅ Phase 1 - Serial Console
- Connect to ESP32 devices via serial port
- Real-time serial output monitoring
- Command input to send to device
- Log filtering and color-coded output (ERROR, WARN, INFO, DEBUG)
- Auto-scroll with pause/resume
- Message history (last 1000 messages)

### ✅ Phase 2 - Flash Manager
- Flash firmware to connected ESP32 devices
- Support for multiple build configurations:
  - **Development**: No sleep, boot debug enabled
  - **Production**: Normal operation with sleep
  - **Battery Test**: Verbose battery logging
- Real-time progress tracking with percentage
- Build and flash log output
- Cancel flash operation
- Automatic PlatformIO integration

### ✅ Phase 3 - MQTT Integration
- MQTT broker connectivity (Mosquitto)
- Real-time message inspector with filtering
- Data simulator for Home Assistant weather data
- Manual message publishing with retain and QoS
- Topic subscription management
- Direction indicators (incoming/outgoing)
- 1000 message history
- Auto-refresh status

### ✅ Phase 4 - Display & Device Control
- **Screenshot Viewer**: View ESP32 display in real-time
  - Manual refresh and auto-refresh (5s/10s/30s/1m)
  - 2x scaling with pixel-perfect rendering
  - Test image generator
- **Control Panel**: Remote device management
  - Sleep interval adjustment (1-60 minutes)
  - Reboot device
  - Enable/disable diagnostic mode
  - Force display refresh
- **Status Dashboard**: 8 status cards showing:
  - Serial, MQTT, and device connection status
  - Battery level with visual bar
  - Temperature and humidity
  - Free heap memory
  - Last seen timestamp

## Installation

### Backend

1. Install Python dependencies:
```bash
pip install -r requirements-manager.txt
```

2. Ensure PlatformIO is installed (for flashing):
```bash
pip install platformio
```

### Frontend

1. Navigate to the manager directory:
```bash
cd web/manager
```

2. Install npm dependencies:
```bash
npm install
```

## Usage

### Development Mode

1. Start the backend server:
```bash
python scripts/start_device_manager.py --port 8080 --debug
```

2. In a separate terminal, start the frontend dev server:
```bash
cd web/manager
npm run dev
```

3. Open your browser to `http://localhost:3000`

### Production Mode

Build the frontend:
```bash
cd web/manager
npm run build
```

Start the backend (which serves the built frontend):
```bash
python scripts/start_device_manager.py --port 8080
```

Open your browser to `http://localhost:8080`

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Browser (Vite + React)                       │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│  │ Display  │ │ Serial   │ │  Flash   │ │  MQTT    │ │ Status   │  │
│  │ Viewer   │ │ Console  │ │ Manager  │ │ Inspector│ │ Dashboard│  │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘  │
│       │            │            │            │            │         │
│       └────────────┴────────────┴─────┬──────┴────────────┘         │
│                                       │ WebSocket                   │
└───────────────────────────────────────┼─────────────────────────────┘
                                        │
┌───────────────────────────────────────┼─────────────────────────────┐
│                     Python Backend (FastAPI)                        │
│                                       │                             │
│  ┌────────────────────────────────────┴────────────────────────┐   │
│  │                    WebSocket Hub                             │   │
│  │  (broadcasts serial, mqtt, status to all connected clients)  │   │
│  └──────────────────────────────────────────────────────────────┘   │
│       │            │            │            │                      │
│  ┌────┴────┐ ┌─────┴─────┐ ┌────┴────┐ ┌─────┴─────┐               │
│  │ Serial  │ │   Flash   │ │  MQTT   │ │ Screenshot│               │
│  │ Manager │ │  Manager  │ │ Broker  │ │  Handler  │               │
│  └────┬────┘ └─────┬─────┘ └────┬────┘ └─────┬─────┘               │
│       │            │            │            │                      │
│   pyserial    subprocess     paho-mqtt   base64 decode              │
│              (esptool.py)   (embedded)                              │
└───────────────────────────────────────────────────────────────────────┘
```

## API Endpoints

### Serial
- `GET /api/ports` - List available serial ports
- `POST /api/serial/connect` - Connect to serial port
- `POST /api/serial/disconnect` - Disconnect from serial
- `POST /api/serial/send` - Send command to serial
- `GET /api/serial/status` - Get connection status

### Flash
- `POST /api/flash/start` - Start flash process
- `GET /api/flash/status` - Get flash progress
- `POST /api/flash/cancel` - Cancel flash operation

### WebSocket
- `WS /ws` - WebSocket for real-time updates
  - Message types: `serial`, `flash_progress`, `flash_complete`, `mqtt`, `device_status`

## Development

### Backend Structure
```
scripts/device_manager/
├── __init__.py
├── server.py              # FastAPI main server
├── websocket_hub.py       # WebSocket broadcast manager
├── serial_manager.py      # Serial port handling
├── flash_manager.py       # Firmware flashing
├── mqtt_broker.py         # Embedded MQTT broker (TODO)
├── mqtt_simulator.py      # Fake data generator (TODO)
├── screenshot_handler.py  # Screenshot decode/store (TODO)
└── config.py              # Configuration
```

### Frontend Structure
```
web/manager/src/
├── App.jsx                # Main application
├── main.jsx               # Entry point
├── components/
│   ├── DeviceSelector.jsx # Port selection and connection
│   ├── SerialConsole.jsx  # Serial monitor
│   └── FlashManager.jsx   # Flash controls
├── hooks/
│   └── useWebSocket.js    # WebSocket connection hook
├── api/
│   └── deviceApi.js       # REST API client
└── styles/
    └── manager.css        # Styles
```

## Troubleshooting

### Serial Port Not Found
- Ensure the ESP32 is connected via USB
- Check that drivers are installed (CP210x, CH340, etc.)
- Try refreshing the port list

### Flash Fails
- Verify PlatformIO is installed: `pio --version`
- Check that the correct port is selected
- Ensure no other program is using the serial port
- Try manually with: `pio run -e <env> -t upload --upload-port <port>`

### WebSocket Connection Issues
- Check that the backend is running
- Verify port 8080 is not blocked by firewall
- Check browser console for errors

## Next Steps

See `docs/DEVICE_MANAGER_SPEC.md` for the complete implementation plan, including:
- Phase 3: MQTT broker and simulator
- Phase 4: Screenshot viewer and device controls
- Phase 5: Polish and testing
