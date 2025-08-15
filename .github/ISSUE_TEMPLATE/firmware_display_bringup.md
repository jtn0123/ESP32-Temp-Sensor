---
name: Firmware — Bring up GxEPD2 with FeatherWing 4195
about: Pin map, panel class, header + inside/outside blocks, partial windows
labels: firmware, display
---

### Goal
Initialize GxEPD2 for the Adafruit 2.13" FeatherWing (PID 4195), render the defined layout regions, and support partial window updates with periodic full refresh.

### Tasks
- Confirm control pins per `hardware/pinmap.md` and Adafruit guide.
- Select correct `GxEPD2_213_*` class for 250×122 panel (SSD1680/UC8151 family).
- Draw frame + header + labels + inside/outside values and icon region.
- Implement partial window updates for value regions; full refresh every N partials.

### Acceptance Criteria
- Boots and draws header + inside/outside values.
- Partial updates only touch designated regions.
- Full refresh cadence configurable.

### Notes
See `firmware/arduino/src/display_layout.h` for region bounds.

