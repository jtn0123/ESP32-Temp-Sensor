# UI Layout Workflow Guide

How to change the ESP32 eInk display layout and see it everywhere (firmware,
web simulator, validation tooling).

## Single source of truth

All layout comes from **`config/ui_spec.json`**. Everything else is generated
from it by `scripts/gen_ui.py`:

| Generated file | Consumer |
| --- | --- |
| `firmware/arduino/src/ui_ops_generated.cpp` | firmware draw ops |
| `firmware/arduino/src/display_layout.h` | firmware rect constants |
| `config/display_geometry.json` | validation tooling, tests |
| `web/sim/ui_generated.js` | web simulator draw spec |
| `web/sim/geometry.json` | simulator overlays / region inspector |

Never hand-edit the generated files — `tests/test_geometry_sync.py` and the
layout drift tests will fail if they diverge from the spec.

## Making a layout change

1. Edit `config/ui_spec.json` (rects, draw ops, fonts, variants).
2. Regenerate: `python3 scripts/gen_ui.py`
3. Preview in the simulator (see below). Use the **Show geometry rects**,
   **Label regions**, and **UI validation overlay** toggles to check
   alignment, and the **Region inspector** panel to inspect rect boxes.
4. Run the layout tests:
   ```bash
   pytest -q -k "web_sim or geometry or layout"
   ```
5. Build/flash firmware as usual — the same spec drives the panel.

## Running the simulator

Serve the **`web/` directory** (not `web/sim/`) so the shared `/icons/` assets
resolve:

```bash
./scripts/start_simulator.sh            # picks a free port, opens the browser
```

or with the device manager backend (adds device/MQTT integration):

```bash
python scripts/start_device_manager.py --port 8080
# then open http://localhost:8080/sim
```

## Simulator debugging aids

- **Preset** dropdown: normal / low battery / no MQTT / extreme temps / long
  city name.
- **Advanced** toggles: stress data, 4px grid, geometry rects, region labels,
  ghosting simulation, validation overlay.
- **UI Validation** panel: runs the collision / overflow / alignment checks
  in-page and lists issues.
- **Advanced Debug Tools** panel: test scenarios, performance metrics, live
  simulation data.
- Set `localStorage.simDebug = "1"` in the browser console to enable verbose
  draw logging.

## History

The simulator previously shipped an interactive drag-and-drop layout editor
(`layout-editor.js` + `scripts/apply_layout_changes.py`). It exported edits to
`display_geometry.json`, which is now a *generated* file — the workflow fought
the spec pipeline and was removed. If you need it for reference, it lives in
git history prior to this file's rewrite.
