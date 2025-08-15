# Power Budget & Duty Cycle Notes

Targets
- Sleep current: ≤ 0.09 mA (LEDs/rails off)
- Awake current: 60–100 mA during Wi‑Fi + draw
- Awake duration: 30–120 s depending on network and fetch path

Duty Cycle Estimate (example)
- 2 h interval, 45 s awake @ 80 mA, rest at 0.09 mA
- Average current ≈ (80 mA * 45 s + 0.09 mA * 7170 s) / 7200 s ≈ 0.59 mA
- 3500 mAh pack → ~3500 / 0.59 ≈ 5932 h ≈ 247 days (idealized; add margin)

Use `scripts/power_estimator.py` to explore intervals and currents.

## Sleep‑Current Checklist

- Disable onboard NeoPixel / status LEDs
- Turn off I²C power rail if your board provides a controllable rail (document the pin you use)
- Ensure no sensor or peripheral is back‑powering through GPIOs during sleep
- Optional: drive the Wing’s `EN` low to power‑gate the panel/SRAM/SD; on wake, re‑init the display before use

## DMM Procedure

1. Power the board from the Li‑ion battery through your multimeter in series
2. Disconnect USB data (avoid 5V back‑power skewing readings)
3. Let the device enter deep sleep and note the mA reading (target ≤ ~0.09 mA)
4. Wake the device and observe peak/average awake current and duration
