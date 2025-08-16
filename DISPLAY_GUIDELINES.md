## Display UI Guidelines (eInk 250×122)

Scope: Visual and layout rules for the device display and the web simulator. These apply to the shared geometry in `config/display_geometry.json` and the renderer in `web/sim/sim.js`.

### Geometry and grid
- **Canvas**: 250×122 px, 1 px frame on all sides; 1 px center divider at x=125 from y=18 to bottom.
- **Baseline**: Align text to an even‑pixel vertical baseline to avoid anti‑aliasing. Favor 2 px vertical increments between stacked rows.
- **Partial windows**: All content must be drawn within these named rectangles from the geometry file:
  - `HEADER_NAME`, `HEADER_TIME`
  - `INSIDE_TEMP`, `INSIDE_RH`, `INSIDE_TIME`
  - `OUT_TEMP`, `OUT_ICON`, `OUT_ROW1_L`, `OUT_ROW1_R`, `OUT_ROW2_L`, `OUT_ROW2_R`
  - `STATUS` (status band area that hosts the 3 rows + right weather quadrant)

### Header
- **Room name**: Left‑aligned, truncated with ellipsis to keep a fixed gap before the time.
- **Time**: Right‑aligned in `HEADER_TIME`. Maintain a minimum 4 px gap between room name and time block.

### Inside / Outside columns
- **Section labels**: `INSIDE` and `OUTSIDE` must be horizontally centered within their respective temperature rectangles (`INSIDE_TEMP`, `OUT_TEMP`).
- **Temperature value + unit**: The combination of number, degree symbol, and `F` must be **horizontally centered** within `INSIDE_TEMP` and `OUT_TEMP`.
  - Prefer dropping the fractional part before truncating integral digits.
  - Units are compact and should not force the number off‑center.

### Outside detail rows (left half under OUTSIDE temp)
- Two rows: Row 1 = **Relative Humidity** (`% RH`), Row 2 = **Wind** (`mph`).
- **No clipping**: Descenders must not be cut off; adjust baseline or row height as needed.
- **Tight spacing**: Keep rows visually tight but non‑overlapping. Avoid collisions with a secondary right column.
- **Truncation**: If truncation is required, use ellipsis; do not truncate units (e.g., show `mph` fully).

### Status band (bottom area)
- **Three rows on the left**: Battery line, days/percent line, IP line.
- **Battery icon vertical centering**: Battery glyph is vertically centered between the first two text rows.
- **IP row horizontal centering**: The `IP` text is horizontally centered across the entire left status column (from left frame through the battery area to the center divider).

### Right weather quadrant (within the status band)
- Contains icon + short text label.
- **Centering**: The combined block (icon + label) is centered both horizontally and vertically within the right status area.
- **Icon size**: Weather icon is rendered ~20% larger than the previous baseline size. Label truncates with ellipsis if needed, while keeping the block centered.

### Fonts and rendering
- Use a fixed/monospace stack for numbers; bold for temperatures.
- After drawing, apply a 1‑bit threshold so there is no grayscale/AA.

### Validation checklist (for UI reviews and tests)
- [ ] `INSIDE` / `OUTSIDE` labels are horizontally centered over their temperature blocks.
- [ ] Temperature number + `°F` is horizontally centered in `INSIDE_TEMP` and `OUT_TEMP` at typical and extreme values.
- [ ] Outside `% RH` and `mph` rows are fully visible (no clipping) and have tight, consistent spacing.
- [ ] Battery icon is vertically centered between the first two status text rows.
- [ ] IP line is horizontally centered across the entire left status column width.
- [ ] Weather icon + label are centered both horizontally and vertically in the right status quadrant; icon ~20% larger than baseline.
- [ ] No text collides with the center divider or spills outside its assigned rectangle.

### Key implementation touchpoints
- Geometry: `config/display_geometry.json` (overrides also in `web/sim/geometry.json` for sim overlay/testing).
- Renderer helpers: `drawTextInRect`, `drawTempRightAligned`, `shortConditionLabel` in `web/sim/sim.js`.

### Notes / current status
- Wind `mph` descender clipping addressed by nudging the row baseline and row placement.
- Battery icon centering and IP centering implemented in the simulator.
- Weather icon enlarged by ~20% in the simulator and kept centered with its label.
- Remaining alignment work: ensure the temperature value + unit block is horizontally centered (both inside and outside) and verify weather block vertical centering across icon sizes.


