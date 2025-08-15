## ESP32 eInk Room Node — Battery‑Friendly Wi‑Fi Sensor with 2.13" e‑ink

"ESP32 eInk Room Node" — battery‑efficient Wi‑Fi sensor node with a 2.13" mono e‑ink display. Wakes on a schedule, reads inside sensors, pulls outside stats (from Home Assistant or MQTT), renders to e‑ink (partial), publishes to HA, and deep‑sleeps.

### Hardware

- **MCU**: Adafruit **Feather ESP32‑S2** (USB‑C, Li‑ion charge). Alternatives: XIAO ESP32‑C3, LILYGO T5.
- **Display**: Adafruit **2.13" mono e‑ink FeatherWing**, **250×122** px (partial refresh supported).
- **Sensors**: SHT40 or BME280 (I2C). Optional SGP40 (VOC), SCD41 (CO₂ single‑shot).
- **Battery**: 1S Li‑ion/LiPo (1000/3500/7000 mAh). JST‑PH 2.0.
- **Cables**: If your pack uses micro JST 1.25, use a 1.25F→PH2.0M adapter.

### Display & Layout

- Resolution: **250×122**, mono 1‑bit.
- Regions & partial windows: see `firmware/arduino/src/display_layout.h`.
- Refresh: **partial** each wake; **full** every N cycles to clear ghosting.

### Power & Duty Cycle (example)

- Deep sleep: ~**0.09 mA** (board LEDs/rails off).
- Awake (Wi‑Fi + draw): **60–100 mA** for **30–120 s**.
- Hourly / 2‑hourly / 4‑hourly wakes supported; see `/scripts/power_estimator.py`.

### Home Assistant Integration

- **ESPHome path**: uses `homeassistant:` to read outdoor entities and native sensors to publish.
- **MQTT path**: subscribe to retained `home/outdoor/...` topics; publish inside readings to `sensors/<room>/...`.

### Configuration

Create `config/device.yaml` from the sample:

```yaml
room_name: "Office"
wake_interval: "2h"           # 1h|2h|4h
full_refresh_every: 12         # partials between full clears
outside_source: "ha"          # ha|mqtt
ha_entities:
  outdoor_temp: sensor.outdoor_temperature
  outdoor_hum:  sensor.outdoor_humidity
  weather:      weather.home
mqtt:
  host: 192.168.1.10
  base_topics:
    publish: sensors/office
    subscribe: home/outdoor
wifi:
  ssid: YOUR_SSID
  password: YOUR_PASS
thresholds:
  temp_degC: 0.1
  rh_pct: 1
battery:
  capacity_mAh: 3500
  sleep_current_mA: 0.09
  active_current_mA: 80
```

### Build — Arduino / PlatformIO

See `firmware/arduino/platformio.ini`:

```ini
[env:feather_esp32s2]
platform = espressif32
board = featheresp32-s2
framework = arduino
monitor_speed = 115200
lib_deps =
  ZinggJM/GxEPD2 @ ^1.5.0
  adafruit/Adafruit GFX Library @ ^1.11.9
  adafruit/Adafruit BusIO @ ^1.16.1
  bblanchon/ArduinoJson @ ^7
  knolleary/PubSubClient @ ^2.8
build_flags =
  -DCORE_DEBUG_LEVEL=1
  -DEINK_WIDTH=250 -DEINK_HEIGHT=122
```

Minimal `src/main.cpp` skeleton:

```cpp
#include <Arduino.h>

void setup() {
  Serial.begin(115200);
  delay(100);
  Serial.println("ESP32 eInk Room Node boot");
}

void loop() {
  // placeholder loop
  delay(1000);
}
```

### Display Simulators

- Python PNG mock: renders a 250×122 preview to `out/display_mock.png`.

```bash
# optional: use the repo venv if created
source .venv/bin/activate 2>/dev/null || true
python scripts/mock_display.py
open out/display_mock.png  # macOS
```

- Web Canvas simulator: static page drawing the layout.

```bash
cd web/sim
python3 -m http.server 8080
# open http://localhost:8080 in your browser
```

### ESPHome (optional path)

See `firmware/esphome/room_node.yaml` for a starting YAML.

### Rust (optional path)

See `firmware/rust/` for a sketch `Cargo.toml` and `src/main.rs`.

### Pin Map

See `hardware/pinmap.md` for Feather ESP32‑S2 + 2.13" FeatherWing.

### License

MIT (see `LICENSE`).


