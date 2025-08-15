## Planning Document — ESP32 eInk Room Node

### Goals
- Scaffold a repo for a battery‑friendly ESP32 e‑ink room node with inside/outside data and HA/MQTT integration.

### Assumptions
- Start with Arduino/PlatformIO for fastest stable display bring‑up.
- Provide ESPHome and Rust skeletons for later.
- CI builds Arduino env only.

### Sub‑Tasks
1) Repo structure, README, license, planning doc
2) Config sample (`config/device.sample.yaml`) and icons folder
3) Arduino/PlatformIO skeleton (`platformio.ini`, `src/main.cpp`, headers placeholders)
4) ESPHome YAML skeleton
5) Rust skeleton (optional)
6) Hardware docs (`bom.md`, `pinmap.md`, `power.md`)
7) Enclosure stub
8) Script for power estimation
9) GitHub Actions CI for Arduino build; issue/PR templates

### Validation Criteria
- `pio run` succeeds in `firmware/arduino/` (CI green)
- README contains getting‑started info and config example
- Power estimator script runs locally

### Next Steps (after scaffold)
- Implement display partial windows with GxEPD2
- Add sensor drivers (SHT40/BME280) and net stack (Wi‑Fi, MQTT/ESPHome)
- Implement deep sleep and power math
- Integrate icon assets


