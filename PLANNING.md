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
‑ Implement display partial windows with GxEPD2
‑ Add sensor drivers (SHT40/BME280) and net stack (Wi‑Fi, MQTT/ESPHome)
‑ Implement deep sleep and power math
‑ Integrate icon assets

### Backlog / Do‑Next Checklist
‑ Firmware: bring up GxEPD2 with FeatherWing 4195 (pin map + panel ID; draw header + inside/outside blocks; partial windows).
‑ Firmware: deep sleep loop (RTC wake, Wi‑Fi fast_connect/BSSID, static IP optional).
‑ Firmware: sensor driver (choose SHT4x or BME280; expose °F/°C and RH).
‑ Firmware: outside data (ESPHome `homeassistant:` or MQTT retained subscribe; fallback to last value).
‑ Firmware: status line (IP, V, %, est days).
‑ Firmware: full refresh cadence (every N partials or daily).
‑ Power: gate e‑ink VCC via EN or TPS22910A; verify sleep current.
‑ Tests: UI snapshot — golden PNG compare for typical values.
‑ Docs: `hardware/pinmap.md` exact pins; `hardware/bom.md` purchase links.


### Phase 1 — Wake time & stability

Done:
- Right‑aligned numeric temps; units drawn separately to prevent digit jitter.
- Added `draw_in_region(rect, fn)` helper and applied across temp/RH/icon/status.
- Threshold/caching: RTC‑persisted last values and publish thresholds (0.2°F, 1% RH). Skips unchanged MQTT publishes.
- Outside icon/status caching; partial redraws only on change.
- Wi‑Fi fast connect: optional static IP, BSSID/channel; connection timeouts for early exit.

Open follow‑ups:
- Tune partial window merges when both outside temp/RH change (Phase 3).
- Persist partial refresh cadence in NVS (Phase 3).

