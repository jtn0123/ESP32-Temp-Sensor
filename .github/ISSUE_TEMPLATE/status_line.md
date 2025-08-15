---
name: Firmware — Status line (IP, V, %, est days)
about: Render bottom status with battery telemetry and network info
labels: firmware, ui
---

### Goal
Display IP address, battery voltage and percentage, and estimated days remaining in the status region.

### Tasks
- Read Vbat or fuel gauge (MAX17048 if present) and compute %.
- Estimate days based on wake schedule and measured currents.
- Render compact status string within `STATUS_` window.

### Acceptance Criteria
- Status line fits within region and updates on change.

