---
name: Firmware — Deep sleep loop
about: RTC wake, Wi‑Fi fast reconnect, optional static IP
labels: firmware, power
---

### Goal
Implement deep sleep with short wake window to read sensors, draw partial updates, publish, then return to sleep.

### Tasks
- Configure RTC wake (timer) based on `config/device.yaml`.
- Wi‑Fi fast reconnect (BSSID, optional static IP).
- Sleep current measurement and documentation in `hardware/power.md`.

### Acceptance Criteria
- Wake → read → draw → publish → sleep cycle works reliably.
- Sleep current ~80–100 µA on Feather ESP32‑S2 (or documented variance).

