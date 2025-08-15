---
name: Firmware — Outside data (ESPHome or MQTT)
about: Read outside temp/RH + weather icon via chosen integration
labels: firmware, integration
---

### Goal
Fetch outdoor conditions either via ESPHome `homeassistant:` or retained MQTT topics, with fallback to last value.

### Tasks
- Decide integration path for v1.
- Implement subscription/read and basic retry/backoff.
- Map weather conditions to icon IDs.

### Acceptance Criteria
- Outside temp/RH/icon present in display and updated when available.

