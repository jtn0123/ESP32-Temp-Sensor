# Development Mode & Wake Prediction - Implementation Plan

> **Status**: 📋 PROPOSAL - Awaiting Review
> **Created**: December 2024

## Overview

This plan adds two major features to the Device Manager:

1. **Wake Prediction** - Track when sleeping devices will next wake up
2. **Development Mode** - Toggle between power-hungry dev mode and efficient production mode

---

## Feature 1: Wake Prediction

### What It Does
Shows a countdown timer predicting when a sleeping device will next wake up.

```
┌─────────────────────────────────────────────────────────────┐
│  🎯 office                                                  │
│                                                             │
│  Status: 💤 Sleeping                                        │
│  Last seen: 2:34:12 PM                                      │
│  Sleep interval: 10 minutes                                 │
│                                                             │
│  ⏱️ Next wake in: 6m 23s                                   │
│  ████████████░░░░░░░░░░░░░░░░░░  37%                       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### How It Works

1. **Track Activity**
   - Monitor MQTT messages from device (`espsensor/{id}/...`)
   - Monitor serial output (if connected)
   - Record `last_activity_timestamp` per device

2. **Determine Status**
   - **Awake**: Activity within last 30 seconds
   - **Sleeping**: No activity for 30+ seconds
   - **Unknown**: Never seen / no data

3. **Calculate Next Wake**
   ```
   next_wake = last_activity + sleep_interval
   time_remaining = next_wake - now
   progress = (now - last_activity) / sleep_interval * 100
   ```

4. **Handle Edge Cases**
   - Device wakes early (battery critical, rapid temp change)
   - Device misses wake (network issue, crash)
   - Sleep interval changes mid-cycle

### Files to Modify

| File | Changes |
|------|---------|
| `scripts/device_manager/server.py` | Add device activity tracking |
| `scripts/device_manager/device_tracker.py` | **NEW** - Device state management |
| `web/manager/src/components/StatusDashboard.jsx` | Add wake prediction UI |
| `web/manager/src/styles/manager.css` | Progress bar styles |

---

## Feature 2: Development Mode

### Mode Comparison

| Aspect | 🔧 Dev Mode | 🔋 Production Mode |
|--------|-------------|-------------------|
| Sleep interval | Short (user-selected) | Normal (adaptive) |
| Screenshots | Enabled | Disabled |
| Serial verbosity | High | Low |
| MQTT data source | Can use simulator | Real HA data only |
| Auto-timeout | Yes (1 hour default) | N/A |
| Power usage | High | Optimized |

### Sleep Interval Presets

> **Note**: 3 minute minimum to prevent sensor self-heating from affecting readings.

| Preset | Interval | Use Case |
|--------|----------|----------|
| 🔧 Dev | 3 minutes | Active development |
| 📊 Testing | 5 minutes | Integration testing |
| 🔋 Normal | 10 minutes | Standard monitoring |
| 💤 Power Save | 1 hour | Long-term battery test |

These presets are available in **both** Dev and Production modes.

### Safety Features

1. **Auto-Timeout**
   - Dev mode automatically expires after 1 hour
   - Device reverts to production mode
   - Prevents accidental battery drain

2. **Visual Warnings**
   - Red indicator when in dev mode
   - Countdown to auto-timeout
   - Confirmation dialog to enable

3. **Mode Persistence**
   - Mode stored in RTC memory (survives deep sleep)
   - Reset to production on power cycle (safe default)

### UI Design: Flash/Config Tab

```
┌─────────────────────────────────────────────────────────────┐
│  ⚡ Flash & Configuration                                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  BUILD & FLASH                                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Configuration: [Dev ▼]  [Build] [Flash]             │   │
│  │ Progress: ████████████████░░░░ 80% - Uploading...   │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ─────────────────────────────────────────────────────────  │
│                                                             │
│  DEVICE MODE                                                │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                                                     │   │
│  │  ○ 🔋 Production Mode (recommended)                 │   │
│  │     Adaptive sleep, power optimized                 │   │
│  │                                                     │   │
│  │  ● 🔧 Development Mode                              │   │
│  │     Fixed sleep interval, screenshots enabled       │   │
│  │     ⚠️ Auto-expires in: 54m 32s                     │   │
│  │                                                     │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  SLEEP INTERVAL (Dev Mode Only)                            │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                                                     │   │
│  │  ○ ⚡ 1 min   ○ 🔧 3 min   ● 📊 5 min              │   │
│  │  ○ 🔋 10 min  ○ 💤 1 hour                          │   │
│  │                                                     │   │
│  │  [Apply to Device]                                  │   │
│  │                                                     │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### MQTT Commands (Firmware)

```cpp
// Set device mode
// Topic: espsensor/{device_id}/cmd/mode
// Payload: "dev" or "production"
// Response: Device publishes current mode to status topic

// Set sleep interval (only effective in dev mode)
// Topic: espsensor/{device_id}/cmd/sleep_interval  
// Payload: seconds (60-3600)

// Request current status
// Topic: espsensor/{device_id}/cmd/status
// Response: Device publishes full status JSON
```

### Device Status Message

Device publishes to `espsensor/{device_id}/status`:
```json
{
  "mode": "dev",
  "sleep_interval_sec": 300,
  "dev_mode_timeout_sec": 3272,
  "uptime_sec": 45,
  "awake_reason": "timer",
  "next_sleep_sec": 15,
  "battery_pct": 87,
  "heap_free": 45000,
  "fw_version": "1.2.3"
}
```

---

## Implementation Plan

### Phase 1: Backend Infrastructure (No Firmware Changes)

**Files to create/modify:**

1. **`scripts/device_manager/device_tracker.py`** (NEW)
   ```python
   class DeviceTracker:
       """Tracks device state, activity, and wake predictions"""
       
       def record_activity(device_id, source="mqtt")
       def get_device_state(device_id) -> DeviceState
       def get_all_devices() -> List[DeviceState]
       def set_expected_interval(device_id, seconds)
   ```

2. **`scripts/device_manager/server.py`** (MODIFY)
   - Add `/api/devices` endpoint for all tracked devices
   - Add `/api/devices/{id}/state` for single device state
   - Integrate DeviceTracker with MQTT message handler
   - Broadcast state updates via WebSocket

3. **`web/manager/src/api/deviceApi.js`** (MODIFY)
   - Add `getDeviceState(deviceId)`
   - Add `getAllDevices()`

### Phase 2: Wake Prediction UI

**Files to modify:**

1. **`web/manager/src/components/WakePrediction.jsx`** (NEW)
   - Countdown timer component
   - Progress bar
   - Status indicator (Awake/Sleeping/Unknown)

2. **`web/manager/src/components/StatusDashboard.jsx`** (MODIFY)
   - Integrate WakePrediction component
   - Show for targeted device

3. **`web/manager/src/styles/manager.css`** (MODIFY)
   - Wake prediction styles
   - Progress bar animation

### Phase 3: Device Mode UI

**Files to modify:**

1. **`web/manager/src/components/DeviceModeSelector.jsx`** (NEW)
   - Radio buttons for Dev/Production mode
   - Sleep interval presets
   - Auto-timeout countdown
   - Confirmation dialog

2. **`web/manager/src/components/FlashManager.jsx`** (MODIFY)
   - Integrate DeviceModeSelector
   - Show mode in build output

### Phase 4: Firmware Changes

**Files to modify:**

1. **`firmware/arduino/src/mqtt_client.cpp`** (MODIFY)
   - Add `mode` command handler
   - Add `status` command handler
   - Publish status on wake

2. **`firmware/arduino/src/power.cpp`** (MODIFY)
   - Add `g_device_mode` (dev/production)
   - Add `g_dev_mode_start_time` for timeout tracking
   - Modify `calculate_optimal_sleep_interval()` to respect dev mode

3. **`firmware/arduino/src/power.h`** (MODIFY)
   - Add `DeviceMode` enum
   - Add mode getter/setter functions

4. **`firmware/arduino/src/state_manager.cpp`** (MODIFY)
   - Store mode in RTC memory
   - Reset to production on power cycle

---

## File-by-File Changes

### New Files

| File | Lines (est.) | Purpose |
|------|--------------|---------|
| `scripts/device_manager/device_tracker.py` | ~150 | Device state tracking |
| `web/manager/src/components/WakePrediction.jsx` | ~100 | Wake countdown UI |
| `web/manager/src/components/DeviceModeSelector.jsx` | ~200 | Mode/interval selection |

### Modified Files

| File | Changes | Risk |
|------|---------|------|
| `server.py` | Add tracker integration, new endpoints | Low |
| `deviceApi.js` | Add new API calls | Low |
| `StatusDashboard.jsx` | Add wake prediction | Low |
| `FlashManager.jsx` | Add mode selector | Low |
| `manager.css` | New styles | Low |
| `mqtt_client.cpp` | Add command handlers | Medium |
| `power.cpp` | Add mode logic | Medium |
| `power.h` | Add types | Low |
| `state_manager.cpp` | RTC storage | Low |

---

## Testing Checklist

### Wake Prediction
- [ ] Countdown updates in real-time
- [ ] Progress bar animates smoothly
- [ ] Status changes to "Awake" on activity
- [ ] Status changes to "Sleeping" after 30s silence
- [ ] Handles device missing a wake (shows "Overdue")
- [ ] Handles early wake (resets countdown)

### Development Mode
- [ ] Can enable dev mode from UI
- [ ] Confirmation dialog appears
- [ ] Device receives mode command
- [ ] Sleep interval changes take effect
- [ ] Auto-timeout warning shows
- [ ] Auto-timeout triggers revert to production
- [ ] Mode persists through deep sleep
- [ ] Mode resets on power cycle

### Flash Manager Integration
- [ ] Mode selector visible in Flash tab
- [ ] Interval presets work correctly
- [ ] Cannot set interval in production mode (disabled)
- [ ] Apply button sends command to device

---

## Questions - RESOLVED

1. **Auto-timeout duration**: ✅ 1 hour default

2. **Minimum interval**: ✅ 3 minutes (prevents sensor self-heating)

3. **Production mode intervals**: ✅ Same presets for both modes (3, 5, 10, 60 min)

4. **Status publish frequency**: ✅ Device publishes status on every wake

5. **Mode indicator in header**: ✅ Show device ID badge pulled from device

---

## Approval

- [x] Plan reviewed
- [x] Questions resolved
- [x] Ready to implement

---

*Estimated implementation time: 4-6 hours*
