---
name: Firmware — Sensor driver (SHT4x or BME280)
about: Choose sensor, add PlatformIO deps, read T/RH
labels: firmware, sensor
---

### Goal
Integrate a temp/RH sensor and expose °F/°C and %RH readings to the renderer and publisher.

### Tasks
- Pick SHT4x (recommended) or BME280 and add to `platformio.ini`.
- Implement `read_inside_sensors()` in `firmware/arduino/src/sensors.h`.
- Unit conversion (°C↔°F) and basic smoothing.

### Acceptance Criteria
- Stable readings printed to serial and used in display draw.

