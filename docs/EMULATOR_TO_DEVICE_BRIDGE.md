# Emulator-to-Device Bridge: Implementation Plan

This document outlines the plan to evolve the web simulator from a pure emulator into a bidirectional device control and monitoring tool. The goal is to enable:

1. **Live sensor data** pulled from connected devices
2. **Display screenshots** captured from the real device  
3. **Remote commands** sent to control device behavior
4. **Device discovery** to find and connect to devices on the network

> **Note**: OTA firmware updates are out of scope for this phase. USB flashing via `scripts/flash.py` remains the update method.

---

## ✅ Implementation Status

### Completed Features

| Feature | Status | Notes |
|---------|--------|-------|
| **Screenshot Command** | ✅ Done | `{"cmd": "screenshot"}` added to debug commands |
| **Display Capture** | ✅ Done | `display_capture.h/cpp` with GFXcanvas1 shadow buffer |
| **Base64 Encoding** | ✅ Done | Chunked MQTT transfer (~5KB in 2 chunks) |
| **Device Bridge JS** | ✅ Done | `device-bridge.js` for discovery and control |
| **MQTT Mirror Mode** | ✅ Done | Emulate/Mirror/Control/Sync modes in UI |
| **Remote Screenshot UI** | ✅ Done | "Capture from Device" button in debug panel |
| **mDNS Discovery** | ✅ Done | Device advertises `_espsensor._tcp` service |
| **Discovery Publishing** | ✅ Done | Device publishes to `espsensor/discovery/<id>` |
| **Python Tests** | ✅ Done | `tests/test_display_capture.py` (15 tests) |

### Known Limitations

1. **Shadow Buffer Sync**: The GFXcanvas1 shadow buffer captures `fillScreen()` calls but doesn't automatically capture all drawing operations. For full screenshot fidelity, the spec-based drawing (`draw_from_spec_full_impl`) would need to also draw to the canvas.

2. **GxEPD2 Buffer Access**: GxEPD2 doesn't expose its internal framebuffer publicly. The implementation uses a separate GFXcanvas1 as a shadow buffer instead of reading directly from the display.

### Build Status
```
RAM:   [==        ]  19.0% (used 62332 bytes)
Flash: [======    ]  61.9% (used 892246 bytes)
```

---

## Current State Analysis

### ✅ Features Already Implemented

#### Web Simulator (`web/sim/`)
- Canvas-based 250×122 pixel display emulation
- Screenshot capture and clipboard copy (`#screenshot`, `#copyShot` buttons)
- Device screenshot comparison in debug panel (`deviceScreenshot` file input)
- Visual diff/baseline comparison with color-coded overlays
- MQTT integration via WebSocket (`mqtt-client.js`)
- State management with subscribe/update pattern (`simDataState`)
- Extensive debug panel with test scenarios

#### MQTT Communication
- **Browser → Broker**: WebSocket connection on port 9001
- **Device ← Broker**: TCP connection, subscribes to command topics
- **Existing Command Topics** (`espsensor/<device_id>/cmd/debug`):
  - `heap`, `state`, `config`, `restart`, `modules`, `uptime`
  - `network`, `sensors`, `perf`, `perf_reset`, `bufpool`
  - `crash`, `crash_clear`, `memory`, `memory_reset`
  - `sleep`, `features`, `mqtt_batch`, `smart_refresh`
- **Response Topic**: `espsensor/<device_id>/debug/response`

#### Monitoring Infrastructure
- Serial monitor (`scripts/monitor.py`) with colored output
- MQTT monitoring (`scripts/mqtt_monitor.py`)
- Diagnostics published via MQTT (boot reason, memory, crash info)
- Home Assistant discovery protocol implementation

#### Firmware Flashing
- USB flashing via PlatformIO (`scripts/flash.py`)
- ESPHome has OTA baked in (`ota: platform: esphome`)
- Arduino firmware: **No OTA yet** (listed in `MODULE_ARCHITECTURE.md` as future)

### 🔴 Gaps to Address

| Feature | Current State | Needed |
|---------|--------------|--------|
| Live Data Pull | Partial (MQTT subscribe) | Full bidirectional sync |
| Device Screenshots | Manual upload only | Remote capture command |
| Device Discovery | None | mDNS/MQTT-based discovery |
| Unified Control UI | Separate tools | Integrated control panel |

---

## Implementation Architecture

### High-Level Data Flow

```
┌────────────────────────────────────────────────────────────────┐
│                     WEB SIMULATOR                               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────────┐  │
│  │ Emulator │  │ Device   │  │ Screenshot│  │ Live Data     │  │
│  │ Canvas   │  │ Control  │  │ Viewer   │  │ Sync          │  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └───────┬───────┘  │
└───────┼─────────────┼─────────────┼────────────────┼──────────┘
        │             │             │                │
        │             └─────────────┴────────────────┘
        │                           │
        │               WebSocket (MQTT)
        │                           │
        ▼                           ▼
┌───────────────────────────────────────────────────────────────┐
│                    MQTT BROKER (mosquitto)                     │
│          TCP:18884 / WebSocket:9001                            │
└───────────────────────────────────────────────────────────────┘
                                │
                                │
                                ▼
┌───────────────────────────────────────────────────────────────┐
│                       ESP32 DEVICE                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────────────┐  │
│  │ Display  │  │ Debug    │  │ Display  │  │ MQTT Publisher│  │
│  │ Driver   │  │ Commands │  │ Capture  │  │ (sensor data) │  │
│  └──────────┘  └──────────┘  └──────────┘  └───────────────┘  │
└───────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Device Screenshot Capture

### 1.1 Firmware Changes

#### New File: `firmware/arduino/src/display_capture.h`

```cpp
#pragma once

#include <Arduino.h>

// Display framebuffer capture
class DisplayCapture {
public:
    static DisplayCapture& getInstance();
    
    // Capture current display to buffer (1-bit packed)
    // Returns pointer to static buffer and sets size
    const uint8_t* capture(size_t* out_size);
    
    // Get as base64 string (for MQTT)
    // Returns length of base64 string, 0 on error
    size_t captureBase64(char* out_buffer, size_t buffer_size);
    
    // Dimensions
    static constexpr uint16_t WIDTH = 250;
    static constexpr uint16_t HEIGHT = 122;
    static constexpr size_t BUFFER_SIZE = (WIDTH * HEIGHT + 7) / 8;  // ~3815 bytes
    
private:
    DisplayCapture() = default;
    uint8_t buffer_[BUFFER_SIZE];
};

// C linkage for MQTT command
extern "C" void display_capture_handle(const char* payload, size_t length);
```

#### Implementation Notes

- GxEPD2 provides `display.getBuffer()` for framebuffer access
- Compress with RLE if MQTT packet size is a concern
- Alternatively, serve via HTTP endpoint for larger transfers

### 1.2 MQTT Command Extension

Add to `debug_commands.cpp`:

```cpp
// New command:
// - {"cmd": "screenshot"}  -> Captures display and publishes to screenshot topic
```

Response published to: `espsensor/<device_id>/debug/screenshot`
- Format: `{"width":250,"height":122,"format":"1bit","data":"<base64>"}`

### 1.3 Web Interface Integration

Enhance `web/sim/debug-panel.js`:

```javascript
// Add "Capture from Device" button in Device Comparison section
// When clicked:
// 1. Send {"cmd": "screenshot"} to device
// 2. Subscribe to screenshot response topic
// 3. Decode base64 and render to comparison canvas
// 4. Enable visual diff comparison
```

---

## Phase 2: Live Data Synchronization

### 2.1 Current Sensor Data Topics

The device already publishes to these topics (retained):
- `espsensor/<device_id>/inside/temperature`
- `espsensor/<device_id>/inside/humidity`  
- `espsensor/<device_id>/inside/pressure`
- `espsensor/<device_id>/battery/percent`
- `espsensor/<device_id>/battery/voltage`
- `espsensor/<device_id>/wifi/rssi`

### 2.2 Web Simulator Enhancement

Modify `web/sim/mqtt-client.js` to add **receive mode**:

```javascript
// Current: publish-only (simulates device → Home Assistant)
// New: also subscribe to real device topics and update display

window.SimMQTT = {
    // ... existing methods ...
    
    // New: Subscribe to real device and mirror display
    mirrorDevice(deviceId) {
        const topics = [
            `espsensor/${deviceId}/inside/+`,
            `espsensor/${deviceId}/outside/+`,
            `espsensor/${deviceId}/battery/+`,
            `espsensor/${deviceId}/wifi/+`,
            `espsensor/${deviceId}/debug/+`
        ];
        
        topics.forEach(t => mqttClient.subscribe(t));
        
        mqttClient.on('message', (topic, message) => {
            // Parse topic and update simDataState
            // Trigger display redraw
        });
    },
    
    stopMirror() {
        // Unsubscribe from device topics
    }
};
```

### 2.3 Bidirectional Sync Modes

| Mode | Description | Use Case |
|------|-------------|----------|
| **Emulate** | Local simulation only | Design/testing |
| **Mirror** | Read-only from device | Monitoring |
| **Control** | Send commands to device | Debugging |
| **Sync** | Mirror + Control | Full integration |

Add UI toggle in MQTT panel for mode selection.

---

## Phase 3: Device Discovery

### 3.1 mDNS Announcement (Firmware)

Add to firmware initialization:

```cpp
#include <ESPmDNS.h>

void setup_mdns() {
    if (MDNS.begin(DEVICE_NAME)) {
        MDNS.addService("espsensor", "tcp", 80);
        MDNS.addServiceTxt("espsensor", "tcp", "device_id", CLIENT_ID);
        MDNS.addServiceTxt("espsensor", "tcp", "version", FW_VERSION);
    }
}
```

### 3.2 MQTT-Based Discovery

Devices publish presence on connect:
- Topic: `espsensor/discovery/<device_id>`
- Payload: `{"device_id":"...","ip":"...","version":"...","uptime":...}`
- Retain: false (cleared on disconnect via LWT)

### 3.3 Web Interface: Device Selector

```html
<div class="device-selector">
    <select id="activeDevice">
        <option value="">Simulator Only</option>
        <!-- Populated dynamically -->
    </select>
    <button id="refreshDevices">🔄 Refresh</button>
    <span id="deviceStatus" class="connection-indicator"></span>
</div>
```

---

## Phase 4: Unified Control Panel

### 4.1 New Panel Structure

Reorganize `web/sim/index.html` aside panel:

```
├── Device Connection (new)
│   ├── Device selector (dropdown)
│   ├── Connection status
│   └── Mode toggle (Emulate/Mirror/Control/Sync)
│
├── Region Inspector (existing)
│
├── UI Validation (existing)
│
├── Device Control (new)
│   ├── Remote Commands (dropdown: restart, heap, sensors, etc.)
│   ├── Command Response viewer
│   └── Screenshot capture button
│
├── MQTT Integration (existing, enhanced)
│
└── Advanced Debug Tools (existing)
```

### 4.2 New File: `web/sim/device-bridge.js`

Central manager for device communication:

```javascript
const DeviceBridge = {
    activeDevice: null,
    mode: 'emulate',  // 'emulate', 'mirror', 'control', 'sync'
    
    // Device discovery
    async scanDevices() { /* ... */ },
    
    // Connection management
    connectToDevice(deviceId) { /* ... */ },
    disconnectFromDevice() { /* ... */ },
    
    // Command sending
    sendCommand(cmd, params = {}) { /* ... */ },
    
    // Screenshot capture from device
    async captureDeviceScreenshot() { /* ... */ },
    
    // Event handling
    onDeviceMessage(topic, payload) { /* ... */ },
    onDeviceConnected() { /* ... */ },
    onDeviceDisconnected() { /* ... */ }
};

window.DeviceBridge = DeviceBridge;
```

---

## Implementation Checklist

### Phase 1: Device Screenshots
- [ ] Create `display_capture.h` and `display_capture.cpp`
- [ ] Add `screenshot` debug command
- [ ] Implement base64 encoding for framebuffer
- [ ] Add MQTT response handling in `debug-panel.js`
- [ ] Integrate with existing device comparison UI
- [ ] Test capture and comparison

### Phase 2: Live Data Sync
- [ ] Extend `mqtt-client.js` with subscribe/mirror functionality
- [ ] Add mode selector UI
- [ ] Implement bidirectional data flow
- [ ] Add connection status indicators
- [ ] Test with real device publishing

### Phase 3: Device Discovery
- [ ] Add mDNS advertisement to firmware
- [ ] Add discovery topic publishing
- [ ] Implement discovery in `device-bridge.js`
- [ ] Add device selector dropdown
- [ ] Handle device online/offline events

### Phase 4: Control Panel
- [ ] Create `device-bridge.js`
- [ ] Reorganize panel structure
- [ ] Add remote command UI
- [ ] Add command response viewer
- [ ] Integrate all components
- [ ] Write user documentation

---

## Testing Strategy

### Unit Tests (PlatformIO Native)
- Base64 encoding correctness for framebuffer
- Command parsing

### Integration Tests (Python + MQTT)
- Screenshot capture command/response cycle
- Device discovery messages
- Live data sync topics

### End-to-End Tests (Playwright)
- Device selector functionality
- Screenshot comparison workflow
- Live data sync display update
- Remote command execution

---

## Security Considerations

1. **Command Authorization**: Consider rate limiting debug commands
2. **Network Isolation**: Device bridge should work on local network only
3. **MQTT Authentication**: Use broker credentials when available

---

## Files to Create/Modify

### New Files
- `firmware/arduino/src/display_capture.h`
- `firmware/arduino/src/display_capture.cpp`
- `web/sim/device-bridge.js`
- `tests/test_display_capture.py`

### Modified Files
- `firmware/arduino/src/debug_commands.h` (new commands)
- `firmware/arduino/src/debug_commands.cpp` (new handlers)
- `firmware/arduino/src/main.cpp` (mDNS setup)
- `web/sim/index.html` (new panels)
- `web/sim/mqtt-client.js` (mirror mode)
- `web/sim/debug-panel.js` (screenshot integration)
- `web/sim/style.css` (new panel styles)

---

## Estimated Effort

| Phase | Effort | Dependencies |
|-------|--------|--------------|
| Phase 1: Screenshots | 1-2 days | GxEPD2 buffer access |
| Phase 2: Live Sync | 1 day | Existing MQTT infrastructure |
| Phase 3: Discovery | 1 day | mDNS library |
| Phase 4: Control Panel | 1-2 days | All previous phases |

**Total: ~4-6 days**

---

## Quick Start for Implementer

1. Start with **Phase 1** (Screenshots) - it's self-contained and provides immediate value
2. Use `scripts/run_sim_with_mqtt.sh --broker` to test MQTT locally
3. Reference `debug_commands.cpp` for command handling patterns
4. Reference `mqtt-client.js` for browser MQTT patterns
5. Test firmware changes with `dev_display` PlatformIO environment
6. The existing debug panel already has device screenshot comparison UI - leverage it

---

*Document created: December 2024*
*Last updated: December 2024*
