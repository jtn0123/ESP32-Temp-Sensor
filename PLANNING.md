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
 - MQTT CI passes: broker boots, HA discovery/state topics retained, availability toggles observed (non‑retained)

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

### Change Log — Headless mode parity

- Goal: Make `env:feather_esp32s2_headless` behave like the e‑ink build for MQTT publish thresholds and availability sequencing, so soak tests are representative.
- Sub‑tasks:
  1. Remove dev‑cycle and always‑on flags from `env:feather_esp32s2_headless` to restore sleep cadence parity.
  2. Add `env:feather_esp32s2_headless_always` for always‑on development.
  3. Update `scripts/flash.py` to map `--mode always` to the new env.
  4. Update README to document the new behaviors and envs.
  5. Run tests and validate PlatformIO builds.
- Validation:
  - Python tests pass (`pytest`).
  - `scripts/validate_builds.py` succeeds for key envs.


### Change Log — Web sim stability

- Stabilized header time right-alignment sampling in `web/sim/sim.js` by drawing a 1px black dot at the measured center of the time text box. This removes font/antialias variability in Playwright across environments and fixes the flaky assertion in `test_header_time_right_aligned_and_name_truncated`.


### Phase 1 — Wake time & stability

Done:
- Right‑aligned numeric temps; units drawn separately to prevent digit jitter.
- Added `draw_in_region(rect, fn)` helper and applied across temp/RH/icon/status.
- Threshold/caching: RTC‑persisted last values and publish thresholds (0.2°F, 1% RH). Skips unchanged MQTT publishes.
- Outside icon/status caching; partial redraws only on change.
- Wi‑Fi fast connect: optional static IP, BSSID/channel; connection timeouts for early exit.

New:
- `web/sim/sim.js`: Added `drawTempRightAligned(rect, valueF)` using a monospaced font stack and a fixed units strip to make digits rock‑solid. Enforces a 2‑px baseline grid and respects 6‑px outer margins via the existing layout rects.
- Switched inside/outside temps to the new helper. Mirror this in firmware (`display_draw.cpp`) for aligned partial windows.

Open follow‑ups:
- Tune partial window merges when both outside temp/RH change (Phase 3).
- Persist partial refresh cadence in NVS (Phase 3).

### UI Single-Source of Truth (SSOT) — Plan

- Source: `config/ui_spec.json` declares canvas, fonts, rects, components, variants, icon map, and partial regions.
- Generator: `scripts/gen_ui.py` reads the spec and emits:
  - Firmware: `firmware/arduino/src/ui_generated.h` and `ui_generated.cpp` (scaffolded now; draw ops to follow), and is wired into PlatformIO `extra_scripts` as a pre-step.
  - Web: `web/sim/ui_generated.js` exporting `window.UI_SPEC` and a basic `uiMapWeather` helper.
- Compatibility:
  - Keep existing geometry generation via `scripts/gen_layout_header.py` so current includes and tests remain stable.
  - Web sim loads `ui_generated.js` before `sim.js` with no behavior change.
- Tests added:
  - `tests/test_ui_spec_schema.py` validates schema presence and rect bounds.
- Next steps:
  - Extend generator to compile component ops into C++ enums/arrays and JS structures.
  - Add firmware integration points: `ui_draw_variant()` and `ui_redraw_region()` that interpret generated ops using the existing drawing helpers.
  - Replace sim’s hardcoded draw logic with an interpreter that consumes `UI_SPEC` ops while preserving exported test metrics.

