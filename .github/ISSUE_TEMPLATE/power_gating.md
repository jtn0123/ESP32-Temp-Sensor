---
name: Power — Gate e‑ink VCC (optional)
about: Use EN or load switch to power down e‑ink between updates
labels: power, hardware
---

### Goal
Reduce sleep current by disabling the e‑ink power rail between updates.

### Tasks
- Identify EN/regulator control on FeatherWing 4195 or add TPS22910A.
- Control GPIO to cut power before sleep; re‑enable before draw.
- Measure sleep current impact and document.

### Acceptance Criteria
- Verified sleep current reduction and no boot/draw regressions.

