# ESP32 Temperature Sensor - Module Architecture

## Overview
This document describes the modular architecture of the ESP32 temperature sensor firmware after the November 2024 refactoring. The codebase was restructured from a monolithic 1700+ line main.cpp into logical, maintainable modules.

## Architecture Principles
- **Separation of Concerns**: Each module has a single, well-defined responsibility
- **Minimal Dependencies**: Modules avoid circular dependencies and minimize coupling
- **State Encapsulation**: RTC memory and state variables are managed centrally
- **Hardware Abstraction**: Hardware interfaces are wrapped in abstraction layers

## Module Dependency Graph
```
main.cpp
    └── app_controller
            ├── state_manager (RTC state)
            ├── system_manager (system utilities)
            ├── sensors (hardware sensors)
            ├── power (battery management)
            ├── wifi_manager (WiFi connectivity)
            ├── mqtt_client (MQTT communication)
            │   └── ha_discovery (Home Assistant)
            ├── display_manager (if USE_DISPLAY)
            │   ├── display_renderer
            │   └── display_updates
            └── metrics_diagnostics (debug metrics)
```

## Module Descriptions

### Core Application Layer

#### main.cpp (~700 lines)
- **Purpose**: Hardware initialization and display driver setup
- **Responsibilities**:
  - Initialize display hardware (GxEPD2)
  - Define display regions and constants
  - Call app_controller for application logic
  - Provide template functions for display operations

#### app_controller (~250 lines)
- **Purpose**: Application orchestration and phase management
- **Responsibilities**:
  - Coordinate startup sequence
  - Manage sensor → network → display → sleep phases
  - Handle timing and deadlines
  - Orchestrate module interactions
- **Key Functions**:
  - `app_setup()`: Initialize all modules in correct order
  - `app_loop()`: Main application loop (usually empty due to deep sleep)
  - `run_sensor_phase()`: Collect sensor readings
  - `run_network_phase()`: Publish data via MQTT
  - `run_display_phase()`: Update eInk display
  - `run_sleep_phase()`: Enter deep sleep

### State Management

#### state_manager (~200 lines)
- **Purpose**: Persist state across deep sleep cycles using RTC memory
- **Responsibilities**:
  - Manage RTC_DATA_ATTR variables
  - Provide getter/setter functions for state
  - Track wake counts and partial update counters
  - Cache last sensor readings for trend detection
- **Key State**:
  - Wake/boot counters
  - Last temperature/humidity/pressure values
  - Display partial update counter
  - Battery percentage cache
  - Weather/status CRC for change detection

#### system_manager (~300 lines)  
- **Purpose**: System-level utilities and diagnostics
- **Responsibilities**:
  - Memory diagnostics and fragmentation analysis
  - Reset reason detection and crash handling
  - NVS (non-volatile storage) cache operations
  - CRC32 calculations for change detection
  - Deep sleep management with wake tracking
- **Key Functions**:
  - `get_memory_diagnostics()`: RAM/PSRAM analysis
  - `get_reset_reason_string()`: Decode ESP32 reset cause
  - `go_deep_sleep_with_tracking()`: Enter sleep with RTC tracking
  - `nvs_store/load_*()`: Persistent configuration cache

### Hardware Interface Layer

#### sensors (~150 lines)
- **Purpose**: Abstract sensor hardware differences
- **Responsibilities**:
  - Initialize BME280/SHT40 sensors
  - Read temperature, humidity, pressure
  - Handle sensor failures gracefully
  - Provide consistent InsideReadings structure
- **Supported Sensors**:
  - BME280: Temperature, humidity, pressure
  - SHT40: High-precision temperature and humidity
  - SGP40: VOC air quality (future)
  - SCD41: CO2 sensing (future)

#### power (~210 lines)
- **Purpose**: Battery and power rail management
- **Responsibilities**:
  - Read battery voltage and percentage
  - Control sensor/display power rails
  - Support MAX17048 and LC709203F fuel gauges
  - Provide BatteryStatus structure
- **Key Functions**:
  - `power_init()`: Initialize fuel gauge
  - `read_battery_status()`: Get voltage and percentage
  - `rail_sensor_on/off()`: Control 3.3V sensor rail
  - `rail_display_on/off()`: Control display power

### Display Layer

#### display_manager (~250 lines)
- **Purpose**: High-level display coordination
- **Responsibilities**:
  - Manage full vs partial refresh strategy
  - Coordinate display regions
  - Draw UI framework (dividers, headers, footers)
  - Handle version and time display
- **Key Functions**:
  - `full_refresh()`: Complete display redraw
  - `draw_header_*()`: Header region rendering
  - `draw_footer_*()`: Footer/status rendering
  - `draw_dividers()`: UI structure lines

#### display_renderer (~480 lines)
- **Purpose**: Low-level rendering and drawing operations
- **Responsibilities**:
  - Render sensor values with formatting
  - Draw weather icons from icon data
  - Implement UI spec rendering
  - Map weather conditions to icons
- **Key Functions**:
  - `draw_inside_all()`: Render indoor sensor data
  - `draw_weather_icon_*()`: Weather icon rendering
  - `map_weather_to_icon()`: Weather text → icon mapping
  - `ui_render_all()`: UI spec-based rendering

#### display_updates (~280 lines)
- **Purpose**: Efficient partial updates for eInk
- **Responsibilities**:
  - Implement region-based partial updates
  - Track update counter for full refresh trigger
  - Minimize eInk ghosting and burn-in
  - Optimize battery life with selective updates
- **Key Functions**:
  - `partial_update_inside_temp()`: Update temperature only
  - `partial_update_weather_icon()`: Update weather icon
  - `should_partial_update()`: Determine update strategy

### Network Layer

#### wifi_manager (~180 lines)
- **Purpose**: WiFi connection management
- **Responsibilities**:
  - Connect to configured WiFi network
  - Handle connection timeouts
  - Manage WiFi provisioning mode
  - Report RSSI signal strength
- **Key Functions**:
  - `wifi_begin()`: Initialize WiFi with credentials
  - `wifi_connect_with_timeout()`: Connect with deadline
  - `wifi_is_connected()`: Check connection status
  - `wifi_get_rssi_dbm()`: Get signal strength

#### mqtt_client (~290 lines)
- **Purpose**: MQTT communication and subscriptions
- **Responsibilities**:
  - Connect to MQTT broker
  - Subscribe to outdoor weather topics
  - Handle command topics for diagnostics
  - Publish sensor data with retain flags
  - Process outdoor data aliases (temp_f, condition)
- **Key Functions**:
  - `mqtt_connect()`: Connect with LWT
  - `mqtt_publish_inside()`: Publish indoor data
  - `mqtt_publish_battery()`: Publish power status
  - MQTT callback: Process subscribed topics

#### ha_discovery (~190 lines)
- **Purpose**: Home Assistant MQTT discovery protocol
- **Responsibilities**:
  - Publish discovery messages for all sensors
  - Configure device metadata
  - Set up appropriate units and icons
  - Enable auto-discovery in Home Assistant
- **Discovery Topics**:
  - Temperature sensors (°C/°F)
  - Humidity sensors (%)
  - Pressure sensor (hPa)
  - Battery sensor (V and %)
  - Diagnostic sensors (WiFi RSSI, uptime, memory)

#### metrics_diagnostics (~140 lines)
- **Purpose**: System metrics and debugging
- **Responsibilities**:
  - Publish memory diagnostics
  - Track boot/crash counts
  - Monitor wake cycles
  - Report system health via MQTT
- **Diagnostic Metrics**:
  - Free heap and fragmentation
  - Boot reason and crash detection
  - Wake count persistence
  - Uptime tracking

## Data Flow

### Startup Sequence
1. **main.cpp**: Initialize hardware (display, serial)
2. **app_controller**: Call `app_setup()`
3. **state_manager**: Load RTC memory state
4. **system_manager**: Print boot diagnostics
5. **power**: Initialize battery gauge
6. **sensors**: Initialize temperature/humidity sensors
7. **wifi_manager**: Connect to WiFi network
8. **mqtt_client**: Connect to broker, subscribe topics

### Sensor Reading Phase
1. **sensors**: Read BME280/SHT40 values
2. **state_manager**: Compare with cached values for trends
3. **power**: Read battery status
4. **metrics_diagnostics**: Collect system metrics

### Network Phase
1. **mqtt_client**: Publish sensor readings
2. **ha_discovery**: Send discovery if needed
3. **metrics_diagnostics**: Publish debug metrics
4. **mqtt_client**: Process any received outdoor data

### Display Phase (if enabled)
1. **display_manager**: Determine full vs partial refresh
2. **display_renderer**: Draw sensor values
3. **display_updates**: Execute partial updates if applicable
4. **state_manager**: Update display state counters

### Sleep Phase
1. **state_manager**: Save critical state to RTC memory
2. **mqtt_client**: Disconnect cleanly
3. **wifi_manager**: Disconnect WiFi
4. **system_manager**: Enter deep sleep with wake timer

## Configuration

### Compile-Time Configuration
- `USE_DISPLAY`: Enable/disable eInk display
- `USE_BATTERY`: Enable battery monitoring
- `USE_SHT`/`USE_BME`: Select sensor type
- `LOG_ENABLED`: Enable debug logging
- `SLEEP_SEC`: Deep sleep duration

### Runtime Configuration (device.yaml)
- WiFi credentials
- MQTT broker settings
- Device name and room
- Sleep intervals
- Feature flags

### Display Configuration (display_geometry.json)
- Region definitions (x, y, width, height)
- Layout version for compatibility
- CRC validation between firmware and simulator

## Testing Strategy

### Unit Tests (PlatformIO)
- `test_state_manager`: RTC memory operations
- `test_system_manager`: System utilities, CRC
- `test_app_controller`: Phase sequencing
- `test_rounding`: Mathematical operations

### Integration Tests (Python)
- MQTT subscription and publishing
- Home Assistant discovery format
- Configuration generation
- Display layout validation

### Hardware-in-Loop Tests
- Flash firmware and monitor serial
- Verify MQTT messages with mosquitto_sub
- Check Home Assistant entity creation
- Validate power consumption in sleep

## Future Improvements

### Planned Enhancements
- [ ] OTA (Over-The-Air) updates
- [ ] Multiple sensor node support
- [ ] Weather forecast display
- [ ] Touch button interactions
- [ ] BLE provisioning

### Technical Debt
- [ ] Further reduce main.cpp size
- [ ] Improve test coverage
- [ ] Add performance metrics
- [ ] Document power optimization

## Migration Guide

### For Developers
When adding new features:
1. Identify the appropriate module based on functionality
2. Add functions to the module's header file
3. Implement in the corresponding .cpp file
4. Update app_controller if phase changes needed
5. Add unit tests in test/ directory
6. Update this documentation

### For Users
The refactoring is transparent to end users. All functionality remains the same:
- Same MQTT topics
- Same Home Assistant entities
- Same configuration files
- Same flashing procedure

---
*Last Updated: November 2024*
*Refactoring completed to improve maintainability and enable future enhancements*