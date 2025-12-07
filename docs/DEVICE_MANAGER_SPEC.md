# ESP32 Device Manager - Implementation Specification

## Overview

Transform the existing web simulator into a comprehensive **Device Manager** that can:
1. Flash firmware to connected ESP32 devices
2. Display live serial console output
3. Simulate MQTT broker with Home Assistant-like data
4. Pull and display device screenshots
5. Control device settings (sleep interval, diagnostic mode)
6. Show real-time device status

---

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

---

## File Structure

```
web/
├── src/
│   ├── App.jsx                    # Main app with tab navigation
│   ├── components/
│   │   ├── DisplayViewer.jsx      # Screenshot display + refresh
│   │   ├── SerialConsole.jsx      # Live serial output
│   │   ├── FlashManager.jsx       # Flash controls + progress
│   │   ├── MqttInspector.jsx      # MQTT message viewer
│   │   ├── StatusDashboard.jsx    # Device status cards
│   │   ├── ControlPanel.jsx       # Sleep interval, reboot, etc.
│   │   └── DeviceSelector.jsx     # Port/device dropdown
│   ├── hooks/
│   │   └── useWebSocket.js        # WebSocket connection hook
│   ├── api/
│   │   └── deviceApi.js           # REST API calls
│   └── styles/
│       └── manager.css            # Manager-specific styles
│
scripts/
├── device_manager/
│   ├── __init__.py
│   ├── server.py                  # FastAPI main server
│   ├── serial_manager.py          # Serial port handling
│   ├── flash_manager.py           # esptool.py wrapper
│   ├── mqtt_broker.py             # Embedded MQTT broker
│   ├── mqtt_simulator.py          # Fake HA data generator
│   ├── screenshot_handler.py      # Screenshot decode/store
│   ├── websocket_hub.py           # WebSocket broadcast manager
│   └── config.py                  # Server configuration
├── start_device_manager.py        # Entry point script
└── requirements-manager.txt       # Additional dependencies
```

---

## Backend Implementation

### 1. Server Entry Point (`scripts/start_device_manager.py`)

```python
#!/usr/bin/env python3
"""
ESP32 Device Manager - Start the backend server
Usage: python scripts/start_device_manager.py [--port 8080] [--no-broker]
"""
import argparse
import uvicorn

def main():
    parser = argparse.ArgumentParser(description='ESP32 Device Manager')
    parser.add_argument('--port', type=int, default=8080, help='Server port')
    parser.add_argument('--no-broker', action='store_true', help='Disable embedded MQTT broker')
    parser.add_argument('--serial-port', type=str, default=None, help='Serial port (auto-detect if not specified)')
    args = parser.parse_args()
    
    # Start FastAPI server
    uvicorn.run(
        "device_manager.server:app",
        host="0.0.0.0",
        port=args.port,
        reload=False
    )

if __name__ == "__main__":
    main()
```

---

### 2. Main Server (`scripts/device_manager/server.py`)

**Endpoints to implement:**

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/ports` | List available serial ports |
| POST | `/api/serial/connect` | Connect to serial port |
| POST | `/api/serial/disconnect` | Disconnect from serial |
| POST | `/api/serial/send` | Send command to serial |
| GET | `/api/serial/status` | Get serial connection status |
| POST | `/api/flash/start` | Start flash process |
| GET | `/api/flash/status` | Get flash progress |
| POST | `/api/flash/cancel` | Cancel flash in progress |
| GET | `/api/mqtt/status` | Get MQTT broker status |
| POST | `/api/mqtt/publish` | Publish MQTT message |
| GET | `/api/mqtt/subscriptions` | List active subscriptions |
| POST | `/api/device/screenshot` | Request screenshot from device |
| GET | `/api/device/screenshot/latest` | Get latest screenshot (base64 PNG) |
| POST | `/api/device/command` | Send command (reboot, diag_mode, etc.) |
| GET | `/api/device/status` | Get device status (battery, heap, etc.) |
| POST | `/api/config/sleep-interval` | Set device sleep interval |
| WS | `/ws` | WebSocket for live updates |

**WebSocket message types:**

```typescript
// Server -> Client
{ type: "serial", data: "log line here", timestamp: 1234567890 }
{ type: "mqtt", topic: "espsensor/...", payload: "72.3", direction: "in"|"out" }
{ type: "flash_progress", percent: 45, stage: "writing", message: "..." }
{ type: "flash_complete", success: true, message: "..." }
{ type: "screenshot", data: "base64...", width: 250, height: 122 }
{ type: "device_status", battery: 87, heap: 45000, connected: true }
{ type: "error", source: "serial"|"mqtt"|"flash", message: "..." }

// Client -> Server
{ type: "serial_send", data: "status\n" }
{ type: "mqtt_publish", topic: "...", payload: "..." }
{ type: "request_screenshot" }
```

---

### 3. Serial Manager (`scripts/device_manager/serial_manager.py`)

**Responsibilities:**
- Auto-detect ESP32 serial ports (look for CP210x, CH340, FTDI)
- Connect/disconnect with configurable baud rate (default 115200)
- Read serial data in background thread
- Broadcast lines to WebSocket hub
- Send commands to device
- Parse structured output (JSON status messages if device sends them)

**Key implementation details:**

```python
class SerialManager:
    def __init__(self, websocket_hub):
        self.port = None
        self.serial = None
        self.reader_thread = None
        self.hub = websocket_hub
    
    def list_ports(self) -> List[dict]:
        """Return list of available ports with metadata"""
        # Use serial.tools.list_ports
        # Filter for likely ESP32 devices
        # Return: [{"port": "/dev/ttyUSB0", "description": "CP2104", "hwid": "..."}]
    
    def connect(self, port: str, baud: int = 115200) -> bool:
        """Connect to specified port"""
        # Open serial connection
        # Start reader thread
        # Return success/failure
    
    def disconnect(self):
        """Disconnect and cleanup"""
    
    def send(self, data: str):
        """Send data to device"""
    
    def _reader_loop(self):
        """Background thread to read serial and broadcast"""
        # Read lines
        # Parse for special markers (JSON status, screenshot data)
        # Broadcast to websocket hub
```

---

### 4. Flash Manager (`scripts/device_manager/flash_manager.py`)

**Responsibilities:**
- Wrap esptool.py or platformio CLI
- Stream progress to WebSocket
- Support cancellation
- Handle different build configurations

**Key implementation details:**

```python
class FlashManager:
    def __init__(self, websocket_hub):
        self.hub = websocket_hub
        self.process = None
        self.is_flashing = False
    
    def flash(self, port: str, firmware_path: str = None, build_config: str = "dev") -> bool:
        """
        Flash firmware to device.
        
        If firmware_path is None, build from source first using platformio.
        build_config: "dev" (DEV_NO_SLEEP), "prod", "battery_test"
        """
        # 1. If no firmware_path, run: pio run -e <config>
        # 2. Run esptool.py with progress parsing
        # 3. Stream progress via websocket
        # 4. Return success/failure
    
    def _run_with_progress(self, cmd: List[str]):
        """Run command and parse/broadcast progress"""
        # Use subprocess.Popen with stdout pipe
        # Parse esptool output for progress percentages
        # Broadcast: { type: "flash_progress", percent: X, stage: "erasing"|"writing"|"verifying" }
    
    def cancel(self):
        """Cancel flash in progress"""
        # Kill subprocess if running
```

**Build configurations to support:**

| Config | Description | PlatformIO Env |
|--------|-------------|----------------|
| `dev` | DEV_NO_SLEEP=1, BOOT_DEBUG=1 | `env:feather_dev` |
| `prod` | Normal operation with sleep | `env:feather` |
| `battery_test` | Verbose battery logging | `env:feather_battery` |

---

### 5. MQTT Broker (`scripts/device_manager/mqtt_broker.py`)

**Responsibilities:**
- Run embedded MQTT broker (use `amqtt` or `hbmqtt` Python library)
- Allow device to connect without external broker
- Capture all messages for inspector
- Support message injection

**Key implementation details:**

```python
class EmbeddedMqttBroker:
    def __init__(self, websocket_hub, port: int = 1883):
        self.hub = websocket_hub
        self.port = port
        self.broker = None
        self.message_log = []  # Last N messages
    
    async def start(self):
        """Start the embedded broker"""
        # Use amqtt or hbmqtt
        # Configure to allow anonymous connections
        # Hook message handler to capture all messages
    
    def on_message(self, topic: str, payload: bytes, direction: str):
        """Called for every message through broker"""
        # Log message
        # Broadcast to websocket: { type: "mqtt", topic, payload, direction }
    
    def publish(self, topic: str, payload: str, retain: bool = False):
        """Publish a message (for injection/simulation)"""
```

---

### 6. MQTT Simulator (`scripts/device_manager/mqtt_simulator.py`)

**Responsibilities:**
- Generate fake Home Assistant-style data
- Simulate outside weather conditions
- Configurable patterns (sine wave temp, random weather, etc.)

**Key implementation details:**

```python
class MqttSimulator:
    def __init__(self, broker: EmbeddedMqttBroker):
        self.broker = broker
        self.running = False
        self.config = {
            "temp_min": 40,
            "temp_max": 85,
            "temp_period_hours": 24,  # Full sine wave cycle
            "weather_options": ["sunny", "partly cloudy", "cloudy", "rain", "snow"],
            "update_interval_sec": 60
        }
    
    def start(self):
        """Start publishing simulated data"""
        # Background task to publish every update_interval_sec
    
    def stop(self):
        """Stop simulation"""
    
    def _generate_temperature(self) -> float:
        """Generate temperature based on time of day (sine wave)"""
        # Peak at 3pm, low at 3am
        # Add small random noise
    
    def _generate_weather(self) -> str:
        """Generate weather condition"""
        # Weighted random, or follow a pattern
    
    def _publish_cycle(self):
        """Publish one cycle of simulated data"""
        # Publish to: homeassistant/sensor/outside/temp_f
        # Publish to: homeassistant/sensor/outside/condition
        # Publish to: homeassistant/sensor/outside/humidity
```

**MQTT Topics to simulate (matching firmware expectations):**

| Topic | Example Payload | Notes |
|-------|-----------------|-------|
| `{MQTT_SUB_BASE}/temp_f` | `72.5` | Outside temperature °F |
| `{MQTT_SUB_BASE}/temp` | `22.5` | Outside temperature °C (legacy) |
| `{MQTT_SUB_BASE}/condition` | `sunny` | Weather condition text |
| `{MQTT_SUB_BASE}/humidity` | `45` | Outside humidity % |
| `{MQTT_SUB_BASE}/wind_mph` | `5.2` | Wind speed |

---

### 7. Screenshot Handler (`scripts/device_manager/screenshot_handler.py`)

**Responsibilities:**
- Request screenshot from device via MQTT command
- Receive base64 screenshot data from device
- Decode and store latest screenshot
- Convert 1-bit display buffer to PNG

**Key implementation details:**

```python
class ScreenshotHandler:
    def __init__(self, mqtt_broker, websocket_hub):
        self.broker = mqtt_broker
        self.hub = websocket_hub
        self.latest_screenshot = None
        self.latest_metadata = None
        
        # Subscribe to screenshot topics
        # espsensor/+/debug/screenshot/meta
        # espsensor/+/debug/screenshot/data
    
    def request_screenshot(self, device_id: str):
        """Request screenshot from device"""
        # Publish to: espsensor/{device_id}/cmd/screenshot
        # Payload: "capture"
    
    def on_screenshot_meta(self, device_id: str, meta: dict):
        """Handle incoming metadata"""
        # meta: { width, height, format, data_size }
    
    def on_screenshot_data(self, device_id: str, data: str):
        """Handle incoming base64 data"""
        # Decode base64
        # Convert 1-bit buffer to PNG
        # Store and broadcast
    
    def _convert_1bit_to_png(self, data: bytes, width: int, height: int) -> bytes:
        """Convert 1-bit packed display buffer to PNG"""
        # Use PIL/Pillow
        # 1 bit per pixel, MSB first
        # Return PNG bytes
```

---

### 8. WebSocket Hub (`scripts/device_manager/websocket_hub.py`)

**Responsibilities:**
- Manage connected WebSocket clients
- Broadcast messages to all clients
- Handle client-to-server messages

```python
class WebSocketHub:
    def __init__(self):
        self.clients: Set[WebSocket] = set()
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.clients.add(websocket)
    
    def disconnect(self, websocket: WebSocket):
        self.clients.discard(websocket)
    
    async def broadcast(self, message: dict):
        """Send message to all connected clients"""
        data = json.dumps(message)
        for client in self.clients:
            try:
                await client.send_text(data)
            except:
                self.disconnect(client)
    
    async def handle_message(self, websocket: WebSocket, message: dict):
        """Handle incoming message from client"""
        # Route based on message type
```

---

## Frontend Implementation

### 1. App Layout (`web/src/App.jsx`)

**Structure:**
```jsx
<div className="device-manager">
  <header>
    <h1>ESP32 Device Manager</h1>
    <DeviceSelector />  {/* Port dropdown + connect button */}
  </header>
  
  <main>
    <Tabs>
      <Tab label="Dashboard">
        <StatusDashboard />
        <ControlPanel />
      </Tab>
      <Tab label="Display">
        <DisplayViewer />
      </Tab>
      <Tab label="Console">
        <SerialConsole />
      </Tab>
      <Tab label="Flash">
        <FlashManager />
      </Tab>
      <Tab label="MQTT">
        <MqttInspector />
      </Tab>
    </Tabs>
  </main>
</div>
```

---

### 2. WebSocket Hook (`web/src/hooks/useWebSocket.js`)

```javascript
export function useWebSocket(url) {
  const [connected, setConnected] = useState(false);
  const [messages, setMessages] = useState([]);
  const wsRef = useRef(null);
  
  useEffect(() => {
    const ws = new WebSocket(url);
    
    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      setMessages(prev => [...prev.slice(-1000), msg]); // Keep last 1000
    };
    
    wsRef.current = ws;
    return () => ws.close();
  }, [url]);
  
  const send = (message) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message));
    }
  };
  
  return { connected, messages, send };
}
```

---

### 3. Serial Console Component (`web/src/components/SerialConsole.jsx`)

**Features:**
- Auto-scrolling log view
- Line coloring based on log level ([ERROR] = red, [WARN] = yellow)
- Filter input to search/filter lines
- Command input to send to device
- Clear button
- Pause/resume auto-scroll
- Copy button

**Props/State:**
```javascript
// Filter serial messages from WebSocket
const serialMessages = messages.filter(m => m.type === 'serial');

// State
const [filter, setFilter] = useState('');
const [paused, setPaused] = useState(false);
const [commandInput, setCommandInput] = useState('');
```

---

### 4. Flash Manager Component (`web/src/components/FlashManager.jsx`)

**Features:**
- Build config selector (dev/prod/battery_test)
- Flash button with confirmation
- Progress bar during flash
- Log output from flash process
- Cancel button during flash

**API calls:**
```javascript
// Start flash
await fetch('/api/flash/start', {
  method: 'POST',
  body: JSON.stringify({ port, config: 'dev' })
});

// Progress comes via WebSocket: { type: "flash_progress", percent, stage, message }
```

---

### 5. Display Viewer Component (`web/src/components/DisplayViewer.jsx`)

**Features:**
- Display screenshot image (scaled 2x or 3x for visibility)
- "Refresh" button to request new screenshot
- Auto-refresh toggle with interval selector
- Side-by-side with simulator render (optional)
- Timestamp of last screenshot

**Layout:**
```
┌─────────────────────────────────────────┐
│  [Refresh] [Auto: ▼ Off/5s/10s/30s]    │
├─────────────────────────────────────────┤
│                                         │
│     ┌───────────────────────┐           │
│     │      72°F             │           │
│     │      OFFICE           │           │
│     │      45% RH           │           │
│     └───────────────────────┘           │
│                                         │
│     Last updated: 12:34:56              │
└─────────────────────────────────────────┘
```

---

### 6. MQTT Inspector Component (`web/src/components/MqttInspector.jsx`)

**Features:**
- Message log (topic, payload, direction, timestamp)
- Direction indicators (→ outgoing, ← incoming)
- Topic filter
- Payload search
- Manual publish form (topic + payload inputs)
- Simulation controls (start/stop fake data)

**Message display:**
```
12:34:56 → espsensor/office/inside/temperature  72.3
12:34:56 → espsensor/office/battery/percent     87
12:34:57 ← homeassistant/sensor/outside/temp_f  58.0
```

---

### 7. Control Panel Component (`web/src/components/ControlPanel.jsx`)

**Features:**
- Sleep interval slider (1min to 60min)
- Reboot button
- Diagnostic mode toggle
- Force full refresh button

**API calls:**
```javascript
// Set sleep interval
await fetch('/api/config/sleep-interval', {
  method: 'POST',
  body: JSON.stringify({ interval_sec: 300 })
});

// Send command
await fetch('/api/device/command', {
  method: 'POST',
  body: JSON.stringify({ command: 'reboot' })
});
```

---

### 8. Status Dashboard Component (`web/src/components/StatusDashboard.jsx`)

**Features:**
- Connection status cards (Serial, MQTT, WiFi)
- Battery status (voltage, percent, estimated days)
- Memory stats (heap, fragmentation)
- Last wake info
- Error counts

**Layout:**
```
┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
│ SERIAL   │ │  MQTT    │ │ BATTERY  │ │  MEMORY  │
│   ✅     │ │   ✅     │ │   87%    │ │  45KB    │
│ ttyUSB0  │ │ 12 msgs  │ │  4.1V    │ │  12% frag│
└──────────┘ └──────────┘ └──────────┘ └──────────┘
```

---

## Dependencies

### Python (`requirements-manager.txt`)
```
fastapi>=0.100.0
uvicorn>=0.23.0
websockets>=11.0
pyserial>=3.5
paho-mqtt>=1.6.0
amqtt>=0.11.0  # Embedded MQTT broker
Pillow>=10.0.0  # Screenshot conversion
esptool>=4.6.0
```

### Frontend (add to existing `package.json`)
```json
{
  "dependencies": {
    "react-tabs": "^6.0.0"  // Or use existing tab solution
  }
}
```

---

## Configuration

### Server config (`scripts/device_manager/config.py`)

```python
from dataclasses import dataclass

@dataclass
class ManagerConfig:
    # Server
    host: str = "0.0.0.0"
    port: int = 8080
    
    # Serial
    default_baud: int = 115200
    serial_timeout: float = 1.0
    
    # MQTT
    mqtt_broker_port: int = 1883
    mqtt_broker_enabled: bool = True
    
    # Simulator
    simulator_enabled: bool = True
    simulator_interval_sec: int = 60
    mqtt_sub_base: str = "homeassistant/sensor/outside"
    
    # Flash
    platformio_env_dev: str = "feather_dev"
    platformio_env_prod: str = "feather"
    firmware_dir: str = ".pio/build"
    
    # Screenshot
    display_width: int = 250
    display_height: int = 122
```

---

## Implementation Order

### Phase 1: Foundation (Day 1)
1. [ ] Create `scripts/device_manager/` directory structure
2. [ ] Implement `server.py` with basic FastAPI app
3. [ ] Implement `websocket_hub.py`
4. [ ] Implement `serial_manager.py` (list ports, connect, read)
5. [ ] Create basic frontend with serial console only
6. [ ] Test serial communication end-to-end

### Phase 2: Flash Support (Day 2)
1. [ ] Implement `flash_manager.py`
2. [ ] Add flash progress parsing
3. [ ] Create `FlashManager.jsx` component
4. [ ] Test flash workflow end-to-end

### Phase 3: MQTT (Day 3)
1. [ ] Implement `mqtt_broker.py` (embedded broker)
2. [ ] Implement `mqtt_simulator.py` (fake data)
3. [ ] Create `MqttInspector.jsx` component
4. [ ] Test device connecting to embedded broker

### Phase 4: Screenshots & Control (Day 4)
1. [ ] Implement `screenshot_handler.py`
2. [ ] Create `DisplayViewer.jsx` component
3. [ ] Create `ControlPanel.jsx` component
4. [ ] Create `StatusDashboard.jsx` component
5. [ ] Test screenshot capture end-to-end

### Phase 5: Polish (Day 5)
1. [ ] Add error handling throughout
2. [ ] Add loading states to UI
3. [ ] Add configuration UI
4. [ ] Write startup script with CLI args
5. [ ] Test full workflow
6. [ ] Update documentation

---

## Testing Checklist

- [ ] Serial: Can list available ports
- [ ] Serial: Can connect to device
- [ ] Serial: Live output appears in console
- [ ] Serial: Can send commands to device
- [ ] Flash: Can flash dev firmware
- [ ] Flash: Progress bar updates
- [ ] Flash: Can cancel flash
- [ ] MQTT: Embedded broker starts
- [ ] MQTT: Device connects to embedded broker
- [ ] MQTT: Messages appear in inspector
- [ ] MQTT: Can inject messages
- [ ] MQTT: Simulator generates fake data
- [ ] Screenshot: Can request screenshot
- [ ] Screenshot: Screenshot displays correctly
- [ ] Control: Can change sleep interval
- [ ] Control: Can reboot device
- [ ] Status: Shows correct battery level
- [ ] Status: Shows correct memory stats

---

## Notes for Implementer

1. **Start simple**: Get serial console working first, then add features incrementally.

2. **Reuse existing code**: The `web/` directory already has a working Vite+React setup and the display simulator. Extend it rather than replace.

3. **Error handling**: Serial ports are flaky. Handle disconnections gracefully and allow reconnection.

4. **Threading**: Serial reading must be in a background thread. Use `asyncio` for the rest.

5. **State management**: Consider using React Context or Zustand for shared state (connection status, device info).

6. **Firmware commands**: The device already supports MQTT commands for diagnostic mode. Check `mqtt_client.cpp` for the command format.

7. **Screenshot format**: Device sends 1-bit packed buffer. Check `display_capture.cpp` for the exact format.

---

## Questions to Resolve During Implementation

1. Should we support multiple simultaneous devices?
2. Should MQTT messages persist across page refreshes?
3. Should we add authentication for the web UI?
4. Should flash configs be editable in the UI or just presets?
