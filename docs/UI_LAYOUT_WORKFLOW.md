# UI Layout Workflow Guide

Interactive visual editing for ESP32 eInk display layouts.

## Overview

The Layout Editor provides a visual, drag-and-drop interface for adjusting display regions in the web simulator. No more manual coordinate editing—just click, drag, and export!

### Features

- **Visual Editing**: Click to select, drag to move, resize with handles
- **Real-time Feedback**: See changes instantly on the display
- **Grid Snapping**: Auto-align to 4px grid for consistent layouts
- **Collision Detection**: Warns when regions overlap
- **Export & Diff**: Download modified JSON with change summary
- **Undo/Reset**: Reset individual regions or entire layout

## Quick Start

### 1. Launch Web Simulator

```bash
cd web/sim
python3 -m http.server 8000
```

Open http://localhost:8000 in your browser.

### 2. Enable Layout Editor

1. Open the **Layout Editor** panel in the right sidebar
2. Check **"Enable Layout Editor"**
3. The badge will turn green: `ON`
4. **You'll see dotted outlines appear** around all regions on the display
5. Text appears: "👆 Click any region to edit"
6. **Hover over the display** - cursor changes to pointer over regions

### 3. Edit Regions

**Select a Region:**
- **Click directly on the display canvas** (the white area showing temperature, weather, etc.)
- Click on any region - they all have dotted outlines when editor is enabled
- Cursor changes to pointer when hovering over clickable regions
- Selected region shows **solid blue outline** with **8 resize handles** (blue squares)

**Move a Region:**
- Click and drag the region
- Coordinates snap to 4px grid (optional)
- Position updates in real-time

**Resize a Region:**
- Drag corner handles to resize proportionally
- Drag edge handles to resize one dimension
- Minimum size: 8×8 pixels

**Manual Coordinates:**
- Use X/Y/W/H inputs for precise positioning
- Click **Apply** to update
- Click **Reset** to restore original position

**JSON Code Viewer:**
- See the exact JSON code for the selected region
- Inline comments explain each value (X, Y, Width, Height)
- **📋 Copy**: Copy code snippet to clipboard
- **✏️ Edit**: Switch to manual JSON editing mode
- **↻ Reset**: Restore region to original values
- **Manual Editing**: Type JSON array directly with live validation
- **Validation**: Shows specific errors (bounds, format, types)
- **Apply Changes**: Updates region when JSON is valid

**Keyboard Shortcuts:**
- **Arrow keys**: Move region by 1px (fine adjustment)
- **Shift+Arrow keys**: Move region by 4px (grid step)
- Works only when a region is selected
- Automatically prevents moving out of bounds

### 4. Export Changes

1. Click **"Export Layout JSON"**
2. File downloads as `display_geometry_modified.json`
3. Click **"Show Changes"** to see what changed

### 5. Apply Changes

```bash
# Validate only
python3 scripts/apply_layout_changes.py display_geometry_modified.json --validate-only

# Dry run (preview)
python3 scripts/apply_layout_changes.py display_geometry_modified.json --dry-run

# Apply changes
python3 scripts/apply_layout_changes.py display_geometry_modified.json
```

The script will:
- ✅ Validate layout (bounds, overlaps)
- 📊 Show change summary
- 💾 Backup original files
- 📝 Update `config/display_geometry.json`
- 🔄 Sync `web/sim/geometry.json`
- 🔧 Regenerate `display_layout.h` firmware header

### 6. Test Changes

**Web Simulator:**
- Reload page: http://localhost:8000
- Verify layout looks correct

**Firmware:**
```bash
cd firmware/arduino
pio run -e feather_esp32s2_display_only
./scripts/flash.sh
```

## Layout Editor UI

### Selection Panel

Shows when a region is selected:

```
Selected: INSIDE_TEMP
X: 6    Y: 36
W: 118  H: 28
[Apply] [Reset] [Deselect]
```

- **X/Y**: Top-left corner position
- **W/H**: Width and height
- **Apply**: Update region with manual values
- **Reset**: Restore region to original
- **Deselect**: Clear selection

### Collision Warning

Appears when regions overlap:

```
⚠️ Collision Detected
INSIDE_TEMP ↔ INSIDE_HUMIDITY
OUT_TEMP ↔ WEATHER_ICON
```

Fix by moving or resizing regions until warnings clear.

### Actions

- **Export Layout JSON**: Download modified geometry
- **Show Changes**: View diff table with pixel deltas
- **Reset All Changes**: Restore all regions to original

## Best Practices

### Layout Design Guidelines

1. **4px Grid Alignment**
   - Enable "Snap to 4px grid" for consistency
   - Aligns with eInk partial refresh boundaries
   - Makes measurements cleaner (e.g., 36 vs 37)

2. **Minimum Spacing**
   - Leave 2-4px gap between regions
   - Prevents visual collisions during rendering
   - Allows for font rendering variations

3. **Text Overflow Prevention**
   - Size regions ~20% larger than expected content
   - Account for: max value + units + padding
   - Example: "100%" needs 30-40px, not 20px

4. **Symmetry & Balance**
   - Align related elements vertically/horizontally
   - Use consistent margins (e.g., 6px from edges)
   - Mirror inside/outside sections

### Common Mistakes

❌ **Too tight spacing**
```
INSIDE_TEMP: [6, 36, 118, 28]
INSIDE_HUMIDITY: [6, 64, 118, 14]  ← Only 0px gap!
```

✅ **Proper spacing**
```
INSIDE_TEMP: [6, 36, 118, 28]
INSIDE_HUMIDITY: [6, 66, 118, 14]  ← 2px gap
```

❌ **Unaligned regions**
```
INSIDE_TEMP: [6, 37, 119, 27]     ← Odd numbers
OUT_TEMP: [129, 38, 95, 26]
```

✅ **Grid-aligned regions**
```
INSIDE_TEMP: [6, 36, 118, 28]     ← Multiples of 4
OUT_TEMP: [128, 36, 96, 28]
```

## Workflow Examples

### Example 1: Move Temperature Display Down

**Goal**: Add 4px space above inside temperature

**Method A - Mouse:**
1. Enable Layout Editor
2. Click `INSIDE_TEMP` region
3. Drag down or change Y: `36` → `40`
4. Check no collisions with `INSIDE_HUMIDITY`
5. Export and apply

**Method B - Keyboard (faster!):**
1. Enable Layout Editor
2. Click `INSIDE_TEMP` region
3. Press **Shift+↓** once (moves +4px)
4. Check no collisions
5. Export and apply

**Result**: Temperature moves from Y=36 to Y=40 (+4px)

### Example 2: Make Room Name Wider

**Goal**: Accommodate longer room names

1. Select `HEADER_NAME` region
2. Drag right edge handle to expand width
3. Check it doesn't collide with `HEADER_TIME_CENTER`
4. Manual adjust if needed: W: `160` → `180`
5. Export and apply

**Result**: Room name field now 180px wide (was 160px)

### Example 4: Precise Alignment with Keyboard

**Goal**: Align two regions perfectly

1. Select first region (e.g., `INSIDE_TEMP`)
2. Note its X position: `6`
3. Select second region (e.g., `INSIDE_HUMIDITY`)
4. Use **←/→** arrow keys to fine-tune X position to match: `6`
5. Use **↑/↓** to adjust vertical spacing
6. Visual feedback shows exact alignment

**Pro Tip**: Combine mouse for rough positioning, keyboard for fine-tuning!

### Example 3: Reorganize Footer Layout

**Goal**: Move battery status to right side

1. Select `FOOTER_STATUS` region
2. Note current position: [6, 90, 160, 32]
3. Drag to new position: [180, 90, 64, 32]
4. Adjust `FOOTER_WEATHER` if needed
5. Check collisions
6. Export and apply

**Result**: Battery status moved to right edge

### Example 5: Using JSON Code Viewer for Precision

**Goal**: Make exact adjustments using JSON code

**Method A - Copy Code for Reference:**
1. Select region (e.g., `INSIDE_TEMP`)
2. JSON Code Viewer shows:
   ```json
   "INSIDE_TEMP": [
     6,   // X position (left edge)
     36,  // Y position (top edge)
     118, // Width in pixels
     28   // Height in pixels
   ]
   ```
3. Click **📋 Copy** to copy to clipboard
4. Paste into notes or documentation
5. Use as reference for other tools

**Method B - Manual JSON Editing:**
1. Select region
2. Click **✏️ Edit** in JSON Code Viewer
3. Textarea opens with editable JSON:
   ```json
   [
     6,
     36,
     118,
     28
   ]
   ```
4. Edit values directly (e.g., change to `[8, 40, 120, 30]`)
5. Click **Apply Changes**
6. Validation runs automatically:
   - ✓ Valid JSON format
   - ✓ Exactly 4 integer values
   - ✓ Within canvas bounds (250×122)
   - ❌ Shows specific errors if invalid
7. Region updates if valid

**When to Use JSON Code Viewer:**
- Need exact pixel values for documentation
- Copying layout between projects
- Bulk edits (export full JSON, edit in text editor)
- Precision adjustments without dragging
- Learning the layout structure
- Debugging layout issues

## Testing Layouts

### Visual Regression Testing

```bash
# Capture baseline
python3 scripts/mock_display.py -o baseline.png

# Make layout changes...

# Capture new version
python3 scripts/mock_display.py -o modified.png

# Compare visually or with image diff tools
```

### Automated Tests

```bash
# Run layout validation tests
pytest tests/test_geometry_sync.py -v

# Check for layout issues
pytest tests/test_layout_compliance.py -v

# Full test suite
pytest tests/test_*.py -k layout
```

## Troubleshooting

### "I enabled the editor but can't click anything"

**Problem**: Layout Editor is enabled but regions aren't selectable

**Solution**:
1. Check the badge says `ON` (green)
2. Look for **dotted blue outlines** around all regions on the display
3. Look for text at bottom: "👆 Click any region to edit"
4. If you don't see these:
   - Hard refresh: Ctrl+Shift+R (Cmd+Shift+R on Mac)
   - Check browser console (F12) for errors
   - Make sure you're clicking on the **canvas** (white display area), not the sidebar

5. **Hover test**: Move mouse over display - cursor should change to **pointer** (finger icon) over regions

**Still not working?**
- Clear browser cache
- Try in incognito/private browsing mode
- Check `web/sim/geometry.json` exists and is valid JSON

### "Region exceeds canvas bounds"

**Problem**: Region extends beyond 250×122 display

**Solution**:
- Check X+W ≤ 250
- Check Y+H ≤ 122
- Reduce size or move closer to origin

### "Collision detected"

**Problem**: Two regions overlap

**Solution**:
- Move one region away from the other
- Resize to make smaller
- Check if overlap is intentional (rare)

### "Export button disabled"

**Problem**: No changes made yet

**Solution**:
- Make at least one modification
- Button enables when layout differs from original

### "Changes not showing in firmware"

**Problem**: Firmware still uses old layout

**Solution**:
1. Verify `config/display_geometry.json` was updated
2. Run `python3 scripts/gen_layout_header.py`
3. Rebuild firmware: `pio run`
4. Flash to device: `./scripts/flash.sh`

### "Simulator shows old layout after export"

**Problem**: Browser cached old geometry.json

**Solution**:
- Hard reload: Ctrl+Shift+R (or Cmd+Shift+R on Mac)
- Clear browser cache
- Check `web/sim/geometry.json` was updated

### "JSON Code Viewer shows validation errors"

**Problem**: Manual JSON edit has errors

**Common Validation Errors**:
- `"Must be an array [x, y, w, h]"` → Use square brackets: `[6, 36, 118, 28]`
- `"Must have exactly 4 values"` → Check you have all 4 numbers
- `"All values must be integers"` → Remove decimals: use `6` not `6.5`
- `"X and Y must be >= 0"` → Use positive numbers only
- `"Width and height must be > 0"` → Must be at least 1 pixel
- `"Right edge exceeds canvas width"` → Reduce X or Width (max X+W = 250)
- `"Bottom edge exceeds canvas height"` → Reduce Y or Height (max Y+H = 122)
- `"Invalid JSON"` → Check syntax (commas, brackets, no trailing comma)

**Solution**:
- Read the specific error message
- Fix the JSON in the textarea
- Click **Apply Changes** again
- Or click **Cancel** to abandon edits

## Advanced Usage

### Batch Editing

For complex changes across multiple regions:

1. Export current layout as `original.json`
2. Make all visual edits in simulator
3. Export as `modified.json`
4. Run diff: `diff -u original.json modified.json`
5. Review all changes before applying
6. Apply: `python3 scripts/apply_layout_changes.py modified.json`

### Programmatic Adjustments

For mathematical adjustments (e.g., "move everything down 4px"):

```python
import json

with open('config/display_geometry.json') as f:
    data = json.load(f)

# Move all regions down 4px
for name, rect in data['rects'].items():
    rect[1] += 4  # Y coordinate

with open('display_geometry_modified.json', 'w') as f:
    json.dump(data, f, indent=2)
```

Then apply: `python3 scripts/apply_layout_changes.py display_geometry_modified.json`

### Layout Templates

Save common layouts for different use cases:

```bash
# Save current layout as template
cp config/display_geometry.json layouts/default.json

# Switch to two-column layout
cp layouts/two-column.json display_geometry_modified.json
python3 scripts/apply_layout_changes.py display_geometry_modified.json
```

## File Structure

```
├── config/
│   ├── display_geometry.json       # Source of truth for layout
│   └── ui_spec.json                # UI rendering specification
├── web/sim/
│   ├── geometry.json               # Must match config/ (auto-synced)
│   ├── layout-editor.js            # Interactive editor logic
│   └── index.html                  # Simulator UI
├── firmware/arduino/src/
│   └── display_layout.h            # Generated C++ header
├── scripts/
│   ├── apply_layout_changes.py     # Apply exported changes
│   └── gen_layout_header.py        # Generate firmware header
└── tests/
    └── test_geometry_sync.py       # Validate files stay in sync
```

## Keyboard Shortcuts

**Currently Available:**

- **Arrow keys**: Move selected region by 1px (fine-tuning)
- **Shift+Arrow keys**: Move selected region by 4px (grid-aligned steps)

Shortcuts only work when:
- Layout Editor is enabled
- A region is selected
- Focus is not in an input field

**Example Usage:**
```
1. Click INSIDE_TEMP to select
2. Press ↓ three times → moves down 3px
3. Press Shift+→ twice → moves right 8px (grid-aligned)
```

**Future Enhancements:**
- Delete: Reset selected region
- Ctrl+Z: Undo last change
- Ctrl+S: Export layout
- Ctrl+Arrow: Resize instead of move

## Getting Help

- **Visual issues**: Check collision warnings, verify bounds
- **Export problems**: Check browser console for errors
- **Apply script fails**: Read error message, validate JSON syntax
- **Layout not updating**: Clear caches, regenerate headers, rebuild

## See Also

- [CLAUDE.md](../CLAUDE.md) - Project development guide
- [test_geometry_sync.py](../tests/test_geometry_sync.py) - Layout validation tests
- [gen_layout_header.py](../scripts/gen_layout_header.py) - Header generation
- [ui_validation_engine.py](../scripts/ui_validation_engine.py) - Visual validation

---

**Pro Tip**: Start with small adjustments (2-4px), test frequently, and keep backups of working layouts!
