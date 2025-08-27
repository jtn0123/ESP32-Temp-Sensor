# Monitoring & Diagnostics

This document describes the monitoring and diagnostic capabilities of the ESP32 Temperature Sensor, including boot reason reporting, memory monitoring, uptime tracking, and diagnostic mode for field troubleshooting.

## Overview

The device provides comprehensive monitoring and diagnostics through:
- **Boot reason tracking** - Reports why the device restarted
- **Uptime/restart counters** - Tracks device reliability
- **Memory monitoring** - Detects leaks and fragmentation
- **Diagnostic mode** - Detailed troubleshooting mode

All diagnostic data is published via MQTT and integrated with Home Assistant for monitoring and alerting.

## MQTT Topics

### Diagnostic Data Topics (Published)

All diagnostic topics are under `espsensor/<device_id>/diagnostics/`:

| Topic | Description | Retain | Format |
|-------|-------------|--------|--------|
| `boot_reason` | Last boot/reset reason | Yes | String (e.g., "ESP_RST_PANIC") |
| `boot_count` | Total boots since power-on | Yes | Integer |
| `crash_count` | Count of abnormal resets | Yes | Integer |
| `uptime` | Cumulative uptime in seconds | Yes | Integer |
| `wake_count` | Deep sleep wake counter | Yes | Integer |
| `memory` | Memory statistics | Yes | JSON object |
| `diagnostic_mode` | Current mode status | Yes | "active" or "inactive" |

### Command Topics (Subscribed)

Commands are received on `espsensor/<device_id>/command/`:

| Topic | Values | Description |
|-------|--------|-------------|
| `diagnostic_mode` | "on"/"off" | Activate/deactivate diagnostic mode |
| `reset` | "1" | Trigger soft reset |

### Memory JSON Format

The `diagnostics/memory` topic publishes a JSON object:

```json
{
  "free_heap": 45000,
  "min_heap": 32000,
  "largest_block": 28000,
  "fragmentation": 37.8
}
```

## Boot Reason Reporting

The device tracks and reports the reason for each boot/reset:

### Reset Reasons

- `ESP_RST_POWERON` - Power-on reset (counters cleared)
- `ESP_RST_SW` - Software reset
- `ESP_RST_PANIC` - Software panic/exception
- `ESP_RST_INT_WDT` - Interrupt watchdog
- `ESP_RST_TASK_WDT` - Task watchdog
- `ESP_RST_WDT` - Other watchdog
- `ESP_RST_BROWNOUT` - Brownout detector
- `ESP_RST_DEEPSLEEP` - Wake from deep sleep
- `ESP_RST_EXT` - External reset
- `ESP_RST_SDIO` - SDIO reset

### Crash Detection

The following reset reasons are considered crashes and increment the crash counter:
- Panic
- Any watchdog timeout
- Brownout

## Uptime and Restart Counters

### RTC-Persistent Counters

These counters survive deep sleep but reset on power cycle:

- **Boot Count** - Total number of boots since power-on
- **Crash Count** - Number of abnormal resets
- **Wake Count** - Number of deep sleep wakes
- **Cumulative Uptime** - Total seconds the device has been awake

### Counter Reset Policy

- **Power-on reset**: All counters reset to initial values
- **Normal reset**: Boot count increments, others preserved
- **Crash reset**: Both boot and crash counters increment

## Memory Monitoring

### Metrics Tracked

- **Free Heap** - Current available heap memory
- **Minimum Heap** - Lowest heap seen (watermark)
- **Largest Free Block** - Largest contiguous memory block
- **Fragmentation %** - Heap fragmentation percentage

### Fragmentation Calculation

```
fragmentation = ((free_heap - largest_block) / free_heap) * 100
```

High fragmentation (>50%) indicates memory is available but not in contiguous blocks.

### Memory Leak Detection

The device monitors heap trends. Consistently declining free heap across multiple wake cycles may indicate a memory leak.

## Diagnostic Mode

A special mode for detailed troubleshooting that keeps the device awake and publishes diagnostics every 10 seconds.

### Activation Methods

1. **MQTT Command**: Send "on" to `command/diagnostic_mode`
2. **Rapid Resets**: 3+ resets within 10 seconds
3. **Serial Command**: Type "diag" in serial console
4. **GPIO Pin**: Hold BOOT button during startup (if configured)

### Diagnostic Mode Features

- **No Deep Sleep** - Device stays awake
- **Periodic Publishing** - Diagnostics every 10 seconds
- **Verbose Logging** - Detailed serial output
- **Real-time Monitoring** - Continuous memory and sensor updates

### Serial Commands in Diagnostic Mode

| Command | Description |
|---------|-------------|
| `normal` or `exit` | Exit diagnostic mode |
| `memtest` | Display detailed memory analysis |
| `sensortest` | Test all sensors |
| `wifitest` | Scan WiFi networks |
| `displaytest` | Run display test patterns |

### Diagnostic Mode JSON

Published to `diagnostics/debug` every 10 seconds:

```json
{
  "diag_mode": true,
  "free_heap": 45000,
  "min_heap": 32000,
  "fragmentation": 37.8,
  "rssi": -65,
  "uptime": 3600,
  "boot_count": 42,
  "crash_count": 3,
  "wake_count": 100
}
```

## Home Assistant Integration

### Discovery Configuration

The device publishes Home Assistant discovery messages for all diagnostic entities:

```yaml
# Example HA entity created via discovery
sensor.esp32_room_boot_count:
  name: "ESP32 Room Boot Count"
  device_class: None
  state_topic: "espsensor/esp32-abc123/diagnostics/boot_count"
  availability_topic: "espsensor/esp32-abc123/availability"
```

### Automation Examples

#### Alert on Crashes

```yaml
automation:
  - alias: "ESP32 Crash Alert"
    trigger:
      - platform: state
        entity_id: sensor.esp32_room_crash_count
    condition:
      - condition: template
        value_template: "{{ trigger.to_state.state|int > trigger.from_state.state|int }}"
    action:
      - service: notify.mobile_app
        data:
          message: "ESP32 sensor crashed! Reason: {{ states('sensor.esp32_room_boot_reason') }}"
```

#### Low Memory Warning

```yaml
automation:
  - alias: "ESP32 Low Memory"
    trigger:
      - platform: numeric_state
        entity_id: sensor.esp32_room_memory
        value_template: "{{ state.attributes.free_heap }}"
        below: 20000
    action:
      - service: notify.mobile_app
        data:
          message: "ESP32 low memory: {{ state.attributes.free_heap }} bytes free"
```

#### Activate Diagnostic Mode

```yaml
script:
  esp32_diagnostic_mode:
    sequence:
      - service: mqtt.publish
        data:
          topic: "espsensor/esp32-abc123/command/diagnostic_mode"
          payload: "on"
          retain: false
```

## Testing

### Running Tests

```bash
# Unit tests for boot diagnostics
pytest tests/test_boot_diagnostics.py -v

# Unit tests for memory monitoring
pytest tests/test_memory_diagnostics.py -v

# Integration tests for MQTT diagnostics
pytest tests/test_diagnostics_mqtt_integration.py -v -m integration
```

### Test Coverage

- Boot reason mapping and crash detection
- Counter persistence and incrementing
- Memory fragmentation calculations
- Rapid reset detection
- MQTT command handling
- Home Assistant discovery
- Diagnostic mode behavior

## Troubleshooting Guide

### Common Issues

#### Device Keeps Rebooting

1. Check `diagnostics/boot_reason` for crash type
2. Monitor `diagnostics/crash_count` for frequency
3. Activate diagnostic mode to prevent sleep
4. Check memory usage for leaks

#### Memory Issues

1. Monitor `diagnostics/memory` for fragmentation
2. Check if free_heap is declining over time
3. Look for largest_block becoming too small
4. Use diagnostic mode `memtest` command

#### Diagnostic Mode Won't Activate

1. Ensure MQTT connection is established
2. Check command topic subscription
3. Try rapid reset method (reset 3 times quickly)
4. Use serial console as fallback

### Field Diagnostics Procedure

1. **Remote Activation**
   ```bash
   mosquitto_pub -t "espsensor/device/command/diagnostic_mode" -m "on"
   ```

2. **Monitor Diagnostics**
   ```bash
   mosquitto_sub -t "espsensor/device/diagnostics/#" -v
   ```

3. **Check Memory**
   - Watch free_heap trend
   - Note fragmentation percentage
   - Compare to min_heap watermark

4. **Analyze Boot History**
   - Review boot_count for stability
   - Check crash_count for issues
   - Examine boot_reason for patterns

5. **Exit Diagnostic Mode**
   ```bash
   mosquitto_pub -t "espsensor/device/command/diagnostic_mode" -m "off"
   ```

## Performance Impact

### Normal Operation

- Diagnostic publishing adds ~5ms to wake time
- Memory monitoring: <1ms overhead
- Counter updates: Negligible impact

### Diagnostic Mode

- Prevents deep sleep (higher power consumption)
- Publishes every 10 seconds
- WiFi/MQTT stay active
- Current draw: ~80mA vs <100µA in sleep

## Future Enhancements

Potential improvements for future versions:

- [ ] Historical data retention in flash
- [ ] Configurable diagnostic thresholds
- [ ] Stack usage monitoring
- [ ] Task-specific memory tracking
- [ ] Network diagnostics (packet loss, latency)
- [ ] Sensor calibration drift tracking
- [ ] OTA update success/failure tracking
- [ ] Environmental stress monitoring