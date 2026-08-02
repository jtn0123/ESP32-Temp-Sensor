# Garage Fan Controller — MQTT-Driven Speed Control for the iLiving Shutter Fan

Design doc for replacing the stock "smart" logic on an iLiving BLDC shutter fan with a
delta-T (inside-vs-outside) controller driven by this project's MQTT sensor data.

## The hardware we're working with

- **Fan:** iLiving `ILG8SF12V-DC`, 12" BLDC shutter fan. 120 V AC, 60 Hz, 0.65 A, 45 W,
  1600 RPM, 960 CFM. The AC→DC conversion and the BLDC motor driver live **inside the
  fan unit** — the fan is what plugs into the wall.
- **Controller:** iLiving wall control box with LED display, `+` / `−` / mode / RH
  buttons. Modes: AUTO (target temp/humidity, speeds 8–12), MANUAL (speed 0–12),
  TIMER. None of these fit a hot semi-desert garage — AUTO only knows *room*
  temperature, so it happily pulls in 110 °F outside air.
- **The link between them:** per the owner's manual, the control box connects to the
  fan with a **USB cord**, and iLiving documents extending it with a plain USB Type-A
  cable. That means the "USB" jack is being used as a cheap 4-conductor connector
  (VBUS, GND, D+, D−) — almost certainly **not** actual USB protocol. The controller
  is a passive accessory: the fan supplies it ~5 V over the cable and the controller
  sends speed commands back. The USB-C port visible on the controller is that same
  control link.

This is the key insight: **everything the fan can do (speed 0–12, on/off) is
commanded over one cheap 4-wire cable with a connector we can buy at any parts
drawer.** We don't need to touch mains wiring at all.

## Options for taking control

### Option A — Speak the fan's language directly (recommended end state)

Unplug the iLiving controller, plug an ESP32 into the fan's USB control jack, and send
the same signals the controller sends.

Almost certainly the signal on D+/D− is one of three trivial things:

1. **TTL UART** (most likely for a fan with a 13-step speed value and a display that
   echoes state) — a byte or small frame per speed change, possibly bidirectional so
   the controller can show fan state.
2. **PWM duty cycle** — 13 discrete duty levels; ESP32 `ledcWrite` handles it.
3. **Analog DC level** — 13 voltage steps; ESP32 DAC + op-amp buffer handles it.

All three are directly generatable by a bare ESP32 (the analog case may need one
op-amp). Power is free: the fan pushes 5 V down the cable to run the stock
controller, which can run the ESP32 instead.

**Risk:** unknown until sniffed (Phase 0 below). ~1 evening with a logic analyzer.

### Option B — Puppet the stock controller's buttons (guaranteed fallback)

Keep the iLiving controller in MANUAL mode and wire an ESP32 across the `+`, `−`, and
power/mode button pads through optocouplers (PC817-class, one per button). The ESP32
"presses" buttons; the stock controller does the talking to the fan.

- Speed is tracked in software (0–12). Desync self-heals: pressing `−` 13 times is
  guaranteed to land on 0 from any state, giving an absolute reference — do this on
  boot and once a day.
- The stock display keeps working, and the physical buttons still work for manual
  override (the ESP32 just re-syncs with a walk-down-to-zero).
- No protocol knowledge needed. Works even if Option A's signal turns out to be
  something obnoxious.

**Risk:** low. Cost: 3–4 optocouplers, resistors, soldering fine wires to button pads.

### Option C — Drive the motor directly

Bypass the fan's internal electronics with our own BLDC driver. **Rejected:** it means
opening a mains appliance, discarding working electronics, and re-solving motor
commutation that the fan already does. All downside.

### Option D — Smart plug on/off only

**Rejected:** loses speed control entirely, which is the whole point (quiet cap of
8/12, low-speed trickle modes). Also unclear what speed the fan resumes at
(memory function says "last speed", but that's the stock controller's state).

### Recommended path

**Phase 0 (sniff), then A, with B as the fallback.** Both A and B use the same ESP32
node, same MQTT contract, same control algorithm — only the last-inch actuation layer
differs. The firmware should isolate that behind a tiny `FanActuator` interface
(`set_speed(0..12)`) so the decision doesn't leak into anything else.

## Phase 0 — Sniffing the control link (the one unknown)

1. Make a **pass-through breakout**: USB-C breakout board (fan side) + USB-A/C
   breakout (controller side), all four conductors jumpered straight through, with
   pin headers tapping VBUS, GND, D+, D−.
2. Multimeter first: confirm VBUS ≈ 5 V from the fan, and watch D+/D− DC levels while
   stepping speed 0 → 12 in MANUAL mode. A staircase voltage ⇒ analog. A constant
   ~1.5–3.3 V that a meter can't resolve ⇒ digital, go to step 3.
3. Logic analyzer (any $12 8-channel Saleae clone + sigrok/PulseView) on D+ and D−.
   Press buttons, capture, decode as UART at the usual suspects (9600/19200/115200
   8N1). PWM is instantly obvious on sight.
4. Record: frame bytes per speed 0–12, on/off, and whether the fan talks back
   (temp/humidity readout for the display would prove bidirectional traffic).
5. Save captures + findings to `docs/fan_link_captures/` so the protocol is
   documented in-repo.

Deliverable: a one-page protocol note that turns Option A from "probably" into "known".

## The control algorithm (delta-T ventilation)

Insight the stock controller can't have: **the garage should only be ventilated when
outside air is cooler than inside air.** We have both numbers on MQTT already.

Inputs (all already published, retained, by this project):

| Signal | Topic | Source |
| --- | --- | --- |
| Garage temp/RH | `espsensor/<garage-node>/inside/temperature`, `.../inside/humidity` | this repo's room node in the garage |
| Outside temp/RH | `home/outdoor/temp`, `home/outdoor/hum` | HA automation (`homeassistant/mqtt_outdoor_publish.yaml`) |

Definitions: `delta = T_inside − T_outside` (positive ⇒ outside is cooler ⇒ venting
helps).

State machine, evaluated on each sample (with hysteresis and dwell, below):

| State | Condition (enter) | Fan speed |
| --- | --- | --- |
| **LOCKOUT** (day, outside hotter) | `delta ≤ 0 °F` | `0`, or `standby_speed` (1–2) if a minimum trickle is wanted |
| **TRICKLE** (small win) | `0 < delta < delta_on` | `min_speed` (1–2) |
| **VENT** (outside meaningfully cooler) | `delta ≥ delta_on` (default 3 °F) | proportional ramp: `min_speed → max_speed_cap` as delta goes `delta_on → delta_full` (default 10 °F) |
| **TARGET REACHED** | `T_inside ≤ target_temp` | `0` — done for the day, don't run the fan for sport |

Stability rules (the part that keeps it from hunting):

- **Hysteresis:** exit VENT at `delta_on − 1 °F`, not `delta_on`. Enter LOCKOUT at
  `delta ≤ 0`, exit at `delta ≥ +1 °F`.
- **Dwell:** minimum 5 min between state changes; speed steps limited to ±2 per
  minute so ramps are gradual, not lurching. Entering LOCKOUT or the failsafe
  state is exempt from both — the fan stops immediately when the delta flips
  hot or the data goes bad; only spinning *up* is damped.
- **Quiet cap:** `max_speed_cap` (default **8** of 12) is a first-class setting,
  changeable over MQTT — noise is the real ceiling, not the motor.
- **Optional quiet hours:** a schedule that lowers `max_speed_cap` further at night.
- **Stale data = safe state:** if either temperature is older than `stale_after`
  (default 10 min) or the broker is unreachable, go to `failsafe_speed` (default 0).
  The fan must never run on frozen data.

All tunables (`delta_on`, `delta_full`, `min_speed`, `max_speed_cap`, `target_temp`,
`standby_speed`, quiet hours, `stale_after`) live in retained MQTT config topics under
`espsensor/<fan-node>/fan/config/#`, so they're adjustable from HA without reflashing.

The pure logic (state machine + ramp math) should be a header-only module like the
existing `power_pure.h` / `system_pure.h`, unit-tested natively with the same
harness this repo already runs in CI.

## Node architecture

A **dedicated ESP32 fan node** (any spare Feather/DevKit) rather than piggybacking on
the e-ink room node:

- It sits at the fan/controller location, powered by the fan's own 5 V over the
  control cable (Option A) or USB (Option B).
- The room node stays a battery-friendly sensor; the fan node is always-on mains-fed —
  this repo already has an always-on profile (`docs/ALWAYS_ON_AND_OTA.md`) with OTA,
  link recovery, and MQTT infrastructure to reuse.
- It subscribes to the two temp topics, runs the state machine, actuates the fan, and
  publishes its own state for HA:
  - `espsensor/<fan-node>/fan/speed` (current 0–12, retained)
  - `espsensor/<fan-node>/fan/state` (LOCKOUT / TRICKLE / VENT / TARGET / FAILSAFE)
  - `espsensor/<fan-node>/fan/delta` (current delta, for graphing)
  - `espsensor/<fan-node>/fan/set` (manual override: `auto` or a fixed 0–12)
- HA discovery: publish a `fan` entity (13-step percentage) plus the state/delta
  sensors, same discovery pattern as `ha_discovery.cpp`.

## Parts list (Phase 0 + either option)

| Item | For | ~Cost |
| --- | --- | --- |
| USB-C breakout board ×2 (or C + A) | pass-through sniff tap, later the permanent plug | $6 |
| 8-ch logic analyzer (sigrok-compatible) | decoding the link | $12 |
| Spare ESP32 dev board | the fan node | on hand |
| PC817 optocouplers ×4 + resistors | only if Option B | $3 |
| Buck/LDO (only if fan's 5 V rail is weak) | powering ESP32 from fan | $2 |

## Safety notes

- Never open the fan housing while plugged in; the mains supply lives in the fan.
  All work described here happens on the isolated 5 V control cable — that's the
  attraction of Options A/B.
- Keep the stock controller in a drawer, not the trash: it's the recovery path and
  the reference transmitter for future captures.
- The manual's warning against "solid-state speed control devices" refers to putting
  a triac dimmer on the mains feed — not applicable here; we only ever use the
  fan's own control input.

## Implementation order

1. **Phase 0:** build the pass-through tap, capture the protocol, commit findings.
2. **Firmware:** `fan_control_pure.h` state machine + native tests (no hardware
   needed — this can be written and CI-tested before Phase 0 even finishes).
3. **Actuator layer:** `FanActuator` impl per Phase 0's answer (UART/PWM/DAC — or
   the optocoupler button-walker if we fall back to Option B).
4. **Node bring-up:** always-on profile, MQTT contract above, HA discovery.
5. **Tune in place:** watch `fan/delta` and `fan/state` graphs in HA for a week,
   adjust `delta_on`/`delta_full` from retained config topics.
