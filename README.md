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
 - Panel driver (GxEPD2): start with `GxEPD2_213_B74` (SSD1680 122×250). If your Wing revision differs, try `GxEPD2_213_DEPG0213BN` and other 122×250 classes listed in `GxEPD2_display_selection.h`.

### Shared Display Geometry (single source of truth)

- `config/display_geometry.json` defines the canvas size and all drawing rectangles.
- Consumers:
  - Web simulator loads it at runtime (falls back to `web/sim/geometry.json`).
  - Python PNG mock reads it to render a matching 250×122 preview.
  - Firmware header is generated from it.
- Regenerate the firmware header from JSON before building firmware:

```bash
python3 scripts/gen_layout_header.py
```

- Tests validate that the mock and sim are in sync (snapshot + pixel checks).

### Power & Duty Cycle (example)

- Deep sleep: ~**0.09 mA** (board LEDs/rails off).
- Awake (Wi‑Fi + draw): **60–100 mA** for **30–120 s**.
- Hourly / 2‑hourly / 4‑hourly wakes supported; see `/scripts/power_estimator.py`.

### Home Assistant Integration

- **ESPHome path**: uses `homeassistant:` to read outdoor entities and native sensors to publish.
- **MQTT path**: subscribe to retained `home/outdoor/...` topics; publish inside readings to `sensors/<room>/...`.
  - Supports optional MQTT auth: set `mqtt.user` and `mqtt.password` in `config/device.yaml`.
  - Example HA automation to publish outdoor values is provided in `homeassistant/mqtt_outdoor_publish.yaml`.

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
  adafruit/Adafruit BME280 Library @ ^2.2.4
  adafruit/Adafruit Unified Sensor @ ^1.1.14
  adafruit/Adafruit MAX1704X @ ^1.0.3   ; optional, set USE_MAX17048 1
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

Both simulators read the same `config/display_geometry.json`, so they match the firmware layout.

#### Weather Icons (24×24 PNG)

- Generated into `config/icons/` via:

```bash
source .venv/bin/activate 2>/dev/null || true
python scripts/gen_icons.py
```

#### Simulator Tests

Run Python tests (image checks + snapshot):

```bash
source .venv/bin/activate 2>/dev/null || true
python -m pip install -U pytest pillow
pytest -q
```

Optional: Web simulator pixel test (requires Playwright):

```bash
python -m pip install -U playwright pytest-playwright
python -m playwright install --with-deps chromium
pytest -q -k web_sim
```

### ESPHome (optional path)

See `firmware/esphome/room_node.yaml` for a starting YAML.

ESPHome Quickstart:

1. Install ESPHome and add a new device using board `featheresp32-s2`.
2. Copy `firmware/esphome/room_node.yaml` into your ESPHome configuration.
3. If the e‑ink renders incorrectly, change `display.model:` between `2.13in`, `2.13in-ttgo`, or `2.13in_v2`.
4. Provide `secrets.yaml` with `wifi_ssid` and `wifi_password`.
5. Optionally set `ota_password` in `secrets.yaml`.
6. Flash and verify the layout matches the Arduino build (250×122).

See `firmware/esphome/secrets.example.yaml` for a sample secrets file.

### Rust (optional path)

See `firmware/rust/` for a sketch `Cargo.toml` and `src/main.rs`.

### Pin Map

See `hardware/pinmap.md` for Feather ESP32‑S2 + 2.13" FeatherWing.

### License

MIT (see `LICENSE`).

### Headless mode + Developer 3/3 cycle

- A headless firmware build (no display required) is provided as a separate PlatformIO environment.

```ini
[env:feather_esp32s2_headless]
platform = espressif32
board = featheresp32-s2
framework = arduino
monitor_speed = 115200
lib_deps = ${env:feather_esp32s2.lib_deps}
build_flags =
  -DCORE_DEBUG_LEVEL=1
  -DUSE_DISPLAY=0
  -DDEV_CYCLE_MODE=1 -DDEV_ACTIVE_SEC=180 -DDEV_SLEEP_SEC=180
  -DEINK_WIDTH=250 -DEINK_HEIGHT=122
extra_scripts = ${env:feather_esp32s2.extra_scripts}
```

- Use this environment for quick testing without a screen. It stays awake for ~3 minutes (pumping Wi‑Fi/MQTT), then deep sleeps for ~3 minutes to let the MCU cool down.

Commands:

```bash
# Build headless dev cycle
pio run -e feather_esp32s2_headless

# Upload (put board in bootloader if needed). Replace PORT with your /dev/cu.usbmodem*
pio run -t upload -e feather_esp32s2_headless --upload-port PORT

# Serial monitor
pio device monitor -p PORT -b 115200
```

Expected serial lines:

```
ESP32 eInk Room Node boot
Dev cycle: staying awake for 180s
Awake ms: <...>
Dev cycle: sleeping for 180s
```

- Disable the 3/3 cycle by switching back to the normal env `env:feather_esp32s2`, or by removing `-DDEV_CYCLE_MODE=1` from headless build flags.

### Switching wake interval (1h / 2h / 4h)

- Long‑term duty cycle is configured in `config/device.yaml`:

```yaml
wake_interval: "2h"   # examples: "1h", "2h", "4h", or a number of seconds like "3600"
```

- After editing, rebuild and upload the normal environment:

```bash
pio run -e feather_esp32s2
pio run -t upload -e feather_esp32s2 --upload-port PORT
```

- The build step generates `firmware/arduino/src/generated_config.h` with `WAKE_INTERVAL_SEC` based on your YAML.


