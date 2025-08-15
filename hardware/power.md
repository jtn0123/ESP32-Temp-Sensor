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
