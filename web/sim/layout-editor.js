/**
 * Interactive Layout Editor for ESP32 Display Simulator
 *
 * Features:
 * - Click to select regions
 * - Drag to move regions
 * - Resize with corner/edge handles
 * - 4px grid snapping
 * - Real-time collision detection
 * - Export modified layout JSON
 * - Show changes diff
 */

(function() {
  'use strict';

  // Editor state
  const editorState = {
    enabled: false,
    selectedRegion: null,
    hoveredRegion: null, // Track which region mouse is over
    hoverPos: { x: 0, y: 0 }, // Mouse position for tooltip
    isDragging: false,
    isResizing: false,
    resizeHandle: null, // 'nw', 'ne', 'sw', 'se', 'n', 's', 'e', 'w'
    dragStartPos: { x: 0, y: 0 },
    regionStartPos: { x: 0, y: 0, w: 0, h: 0 },
    originalGeometry: null, // Store original for diff
    modifiedGeometry: null,
    snapToGrid: true,
    gridSize: 4,
    showHandles: true,
    collisions: new Set(),
    // Divider dragging
    isDraggingDivider: false,
    hoveredDivider: null, // { type: 'vertical'|'horizontal', position: number, affectedRegions: [...] }
    activeDivider: null,
    dividerStartPos: 0,
    alignmentGuides: [] // Array of { type: 'horizontal'|'vertical', position: number }
  };

  // Handle size in pixels
  const HANDLE_SIZE = 8;
  const HANDLE_HALF = HANDLE_SIZE / 2;

  // Initialize editor
  function initLayoutEditor() {
    console.log('Initializing layout editor...');

    // Wait for canvas to be available
    const canvas = document.getElementById('epd');
    if (!canvas) {
      console.warn('Canvas not ready, deferring editor init');
      setTimeout(initLayoutEditor, 100);
      return;
    }

    // Add UI controls
    addEditorUI();

    // Set up event listeners
    setupEventListeners();

    // Load original geometry
    loadOriginalGeometry();

    console.log('Layout editor initialized');

    // Debug: Log dividers after geometry loads
    setTimeout(() => {
      const vDividers = findVerticalDividers();
      const hDividers = findHorizontalDividers();
      console.log('[Layout Editor Debug] Vertical dividers found:', vDividers.length, vDividers);
      console.log('[Layout Editor Debug] Horizontal dividers found:', hDividers.length, hDividers);
    }, 500);
  }

  // Add editor UI panel to the page
  function addEditorUI() {
    const inspectorPane = document.querySelector('.inspector-pane');
    if (!inspectorPane) return;

    const editorPanel = document.createElement('details');
    editorPanel.id = 'layoutEditor';
    editorPanel.setAttribute('aria-label', 'Layout editor panel');
    editorPanel.open = true;

    editorPanel.innerHTML = `
      <summary>Layout Editor <span id="editorBadge" class="badge">OFF</span></summary>
      <div class="editor-controls">
        <div class="editor-mode">
          <label>
            <input type="checkbox" id="enableEditor"> Enable Layout Editor
          </label>
          <label title="Snap regions to 4px grid">
            <input type="checkbox" id="snapToGrid" checked> Snap to 4px grid
          </label>
        </div>

        <div id="editorInstruction" class="editor-instruction" style="display: none;">
          <div class="instruction-box">
            <span class="instruction-icon">👆</span>
            <span class="instruction-text">Click any region or divider line to edit</span>
          </div>
        </div>

        <div id="selectionInfo" class="selection-info" style="display: none;">
          <h4>Selected: <span id="selectedRegionName"></span></h4>
          <div class="keyboard-hint">
            ⌨️ Arrow keys: move 1px | Shift+Arrow: move 4px
          </div>
          <div class="coord-editor">
            <label>X: <input type="number" id="regionX" step="1" min="0"></label>
            <label>Y: <input type="number" id="regionY" step="1" min="0"></label>
            <label>W: <input type="number" id="regionW" step="1" min="1"></label>
            <label>H: <input type="number" id="regionH" step="1" min="1"></label>
          </div>
          <div class="button-row">
            <button id="applyCoords">Apply</button>
            <button id="resetRegion">Reset</button>
            <button id="deselectRegion">Deselect</button>
          </div>

          <!-- JSON CODE VIEWER -->
          <div id="codeViewer" class="code-viewer">
            <h4>📝 Region Code</h4>
            <div id="codeDisplay">
              <pre id="regionCode" class="code-block"></pre>
              <div class="code-actions">
                <button id="copyCode" title="Copy JSON to clipboard">📋 Copy</button>
                <button id="editCode" title="Edit JSON manually">✏️ Edit</button>
                <button id="resetCodeBtn" title="Reset to original">↻ Reset</button>
              </div>
            </div>
            <div id="codeEditor" class="code-editor-container" style="display: none;">
              <textarea id="codeTextarea" class="code-textarea" rows="8" spellcheck="false"></textarea>
              <div id="codeValidation" class="code-validation"></div>
              <div class="code-actions">
                <button id="applyCode" class="btn-primary">Apply Changes</button>
                <button id="cancelCode">Cancel</button>
              </div>
            </div>
          </div>

        </div>

        <div id="collisionWarning" class="collision-warning" style="display: none;">
          <strong>⚠️ Collision Detected</strong>
          <div id="collisionList"></div>
        </div>

        <div class="editor-actions">
          <button id="exportLayout" disabled>Export Layout JSON</button>
          <button id="showDiff" disabled>Show Changes</button>
          <button id="resetLayout">Reset All Changes</button>
        </div>

        <div id="diffPanel" class="diff-panel" style="display: none;">
          <h4>Layout Changes</h4>
          <div id="diffContent"></div>
          <button id="closeDiff">Close</button>
        </div>
      </div>
    `;

    // Insert after validation panel
    const validationPanel = document.getElementById('validationPanel');
    if (validationPanel) {
      validationPanel.after(editorPanel);
    } else {
      inspectorPane.prepend(editorPanel);
    }
  }

  // Set up event listeners
  function setupEventListeners() {
    const canvas = document.getElementById('epd');
    if (!canvas) return;

    // Editor toggle
    const enableCheckbox = document.getElementById('enableEditor');
    if (enableCheckbox) {
      enableCheckbox.addEventListener('change', (e) => {
        editorState.enabled = e.target.checked;
        updateEditorBadge();
        updateInstructionVisibility();
        if (!editorState.enabled) {
          deselectRegion();
        }

        // Force immediate redraw to show visual feedback
        if (typeof window.draw === 'function') {
          requestAnimationFrame(() => window.draw(window.lastData || {}));
        }
      });
    }

    // Snap to grid toggle
    const snapCheckbox = document.getElementById('snapToGrid');
    if (snapCheckbox) {
      snapCheckbox.addEventListener('change', (e) => {
        editorState.snapToGrid = e.target.checked;
      });
    }

    // Canvas mouse events
    canvas.addEventListener('mousedown', handleMouseDown);
    canvas.addEventListener('mousemove', handleMouseMove);
    canvas.addEventListener('mouseup', handleMouseUp);
    canvas.addEventListener('mouseleave', handleMouseUp);

    // Keyboard events for arrow key adjustments
    document.addEventListener('keydown', handleKeyDown);

    // Manual coordinate input
    const applyButton = document.getElementById('applyCoords');
    if (applyButton) {
      applyButton.addEventListener('click', applyManualCoords);
    }

    // Reset single region
    const resetButton = document.getElementById('resetRegion');
    if (resetButton) {
      resetButton.addEventListener('click', resetSelectedRegion);
    }

    // Deselect
    const deselectButton = document.getElementById('deselectRegion');
    if (deselectButton) {
      deselectButton.addEventListener('click', deselectRegion);
    }

    // Export layout
    const exportButton = document.getElementById('exportLayout');
    if (exportButton) {
      exportButton.addEventListener('click', exportLayout);
    }

    // Show diff
    const diffButton = document.getElementById('showDiff');
    if (diffButton) {
      diffButton.addEventListener('click', showDiffPanel);
    }

    // Reset all changes
    const resetAllButton = document.getElementById('resetLayout');
    if (resetAllButton) {
      resetAllButton.addEventListener('click', resetAllChanges);
    }

    // Close diff
    const closeDiffButton = document.getElementById('closeDiff');
    if (closeDiffButton) {
      closeDiffButton.addEventListener('click', () => {
        document.getElementById('diffPanel').style.display = 'none';
      });
    }

    // JSON Code Viewer buttons
    const copyCodeButton = document.getElementById('copyCode');
    if (copyCodeButton) {
      copyCodeButton.addEventListener('click', copyRegionCode);
    }

    const editCodeButton = document.getElementById('editCode');
    if (editCodeButton) {
      editCodeButton.addEventListener('click', () => toggleCodeEditor(true));
    }

    const resetCodeButton = document.getElementById('resetCodeBtn');
    if (resetCodeButton) {
      resetCodeButton.addEventListener('click', resetRegionCode);
    }

    const applyCodeButton = document.getElementById('applyCode');
    if (applyCodeButton) {
      applyCodeButton.addEventListener('click', applyCodeChanges);
    }

    const cancelCodeButton = document.getElementById('cancelCode');
    if (cancelCodeButton) {
      cancelCodeButton.addEventListener('click', () => toggleCodeEditor(false));
    }
  }

  // Load original geometry for comparison
  function loadOriginalGeometry() {
    fetch('geometry.json')
      .then(res => res.json())
      .then(data => {
        editorState.originalGeometry = JSON.parse(JSON.stringify(data));
        console.log('Original geometry loaded');
      })
      .catch(err => console.error('Failed to load geometry:', err));
  }

  // Get canvas coordinates from mouse event
  function getCanvasCoords(event) {
    const canvas = document.getElementById('epd');
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;

    return {
      x: Math.floor((event.clientX - rect.left) * scaleX),
      y: Math.floor((event.clientY - rect.top) * scaleY)
    };
  }

  // Check if point is inside a region
  function isPointInRegion(point, rect) {
    if (!Array.isArray(rect) || rect.length < 4) return false;
    const [x, y, w, h] = rect;
    return point.x >= x && point.x < x + w &&
           point.y >= y && point.y < y + h;
  }

  // Get resize handle at point (if any)
  function getResizeHandle(point, rect) {
    if (!Array.isArray(rect) || rect.length < 4) return null;
    const [x, y, w, h] = rect;
    const margin = 6; // Detection margin for handles

    // Corners (priority)
    if (Math.abs(point.x - x) <= margin && Math.abs(point.y - y) <= margin) return 'nw';
    if (Math.abs(point.x - (x + w)) <= margin && Math.abs(point.y - y) <= margin) return 'ne';
    if (Math.abs(point.x - x) <= margin && Math.abs(point.y - (y + h)) <= margin) return 'sw';
    if (Math.abs(point.x - (x + w)) <= margin && Math.abs(point.y - (y + h)) <= margin) return 'se';

    // Edges
    if (Math.abs(point.y - y) <= margin && point.x > x + margin && point.x < x + w - margin) return 'n';
    if (Math.abs(point.y - (y + h)) <= margin && point.x > x + margin && point.x < x + w - margin) return 's';
    if (Math.abs(point.x - x) <= margin && point.y > y + margin && point.y < y + h - margin) return 'w';
    if (Math.abs(point.x - (x + w)) <= margin && point.y > y + margin && point.y < y + h - margin) return 'e';

    return null;
  }

  // Find region at point
  function findRegionAtPoint(point) {
    if (!window.GJSON || !window.GJSON.rects) return null;

    // Check in reverse order (top regions first)
    const regions = Object.entries(window.GJSON.rects);
    for (let i = regions.length - 1; i >= 0; i--) {
      const [name, rect] = regions[i];
      if (isPointInRegion(point, rect)) {
        return name;
      }
    }
    return null;
  }

  // Snap value to grid
  function snapToGrid(value) {
    if (!editorState.snapToGrid) return value;
    return Math.round(value / editorState.gridSize) * editorState.gridSize;
  }

  // === DIVIDER LINE DETECTION ===

  /**
   * Find all vertical dividers (shared left/right edges)
   * Returns array of { position: x, leftRegions: [...], rightRegions: [...] }
   */
  function findVerticalDividers() {
    if (!window.GJSON || !window.GJSON.rects) return [];

    const dividers = new Map(); // position -> { left: [], right: [] }
    const regions = Object.entries(window.GJSON.rects);
    const canvas = window.GJSON.canvas;

    for (const [name, rect] of regions) {
      const [x, y, w, h] = rect;
      const rightEdge = x + w;

      // Skip canvas edges
      if (rightEdge > 0 && rightEdge < canvas.w) {
        // Track right edges (potential dividers)
        if (!dividers.has(rightEdge)) {
          dividers.set(rightEdge, { left: [], right: [] });
        }
        dividers.get(rightEdge).left.push(name);
      }
    }

    // Now find regions to the right of each divider
    for (const [position, info] of dividers.entries()) {
      for (const [name, rect] of regions) {
        const [x] = rect;
        // If this region's left edge matches the divider position
        if (x === position && !info.left.includes(name)) {
          info.right.push(name);
        }
      }
    }

    // Only keep dividers that have regions on both sides
    const result = [];
    for (const [position, info] of dividers.entries()) {
      if (info.left.length > 0 && info.right.length > 0) {
        result.push({
          type: 'vertical',
          position,
          leftRegions: info.left,
          rightRegions: info.right
        });
      }
    }

    return result;
  }

  /**
   * Find all horizontal dividers (shared top/bottom edges)
   * Returns array of { position: y, topRegions: [...], bottomRegions: [...] }
   */
  function findHorizontalDividers() {
    if (!window.GJSON || !window.GJSON.rects) return [];

    const dividers = new Map(); // position -> { top: [], bottom: [] }
    const regions = Object.entries(window.GJSON.rects);
    const canvas = window.GJSON.canvas;

    for (const [name, rect] of regions) {
      const [x, y, w, h] = rect;
      const bottomEdge = y + h;

      // Skip canvas edges
      if (bottomEdge > 0 && bottomEdge < canvas.h) {
        // Track bottom edges (potential dividers)
        if (!dividers.has(bottomEdge)) {
          dividers.set(bottomEdge, { top: [], bottom: [] });
        }
        dividers.get(bottomEdge).top.push(name);
      }
    }

    // Now find regions below each divider
    for (const [position, info] of dividers.entries()) {
      for (const [name, rect] of regions) {
        const [,y] = rect;
        // If this region's top edge matches the divider position
        if (y === position && !info.top.includes(name)) {
          info.bottom.push(name);
        }
      }
    }

    // Only keep dividers that have regions on both sides
    const result = [];
    for (const [position, info] of dividers.entries()) {
      if (info.top.length > 0 && info.bottom.length > 0) {
        result.push({
          type: 'horizontal',
          position,
          topRegions: info.top,
          bottomRegions: info.bottom
        });
      }
    }

    return result;
  }

  /**
   * Find divider at mouse point (with tolerance)
   * Returns divider object or null
   */
  function findDividerAtPoint(point) {
    const tolerance = 3; // pixels

    // Check vertical dividers
    const verticalDividers = findVerticalDividers();
    for (const divider of verticalDividers) {
      if (Math.abs(point.x - divider.position) <= tolerance) {
        return divider;
      }
    }

    // Check horizontal dividers
    const horizontalDividers = findHorizontalDividers();
    for (const divider of horizontalDividers) {
      if (Math.abs(point.y - divider.position) <= tolerance) {
        return divider;
      }
    }

    return null;
  }

  // Mouse down - start drag or resize
  function handleMouseDown(event) {
    if (!editorState.enabled) return;

    const point = getCanvasCoords(event);

    // PRIORITY 1: Check for divider (before region selection)
    const divider = findDividerAtPoint(point);
    if (divider) {
      // Start divider dragging
      editorState.isDraggingDivider = true;
      editorState.activeDivider = divider;
      editorState.dividerStartPos = divider.type === 'vertical' ? point.x : point.y;
      editorState.dragStartPos = point;

      // Store original positions of all affected regions
      editorState.regionStartPos = {};
      const affectedRegions = divider.type === 'vertical'
        ? [...divider.leftRegions, ...divider.rightRegions]
        : [...divider.topRegions, ...divider.bottomRegions];

      affectedRegions.forEach(name => {
        const rect = window.GJSON.rects[name];
        if (!Array.isArray(rect) || rect.length < 4) {
          console.warn(`Invalid rect for region ${name}:`, rect);
          return;
        }
        editorState.regionStartPos[name] = {
          x: rect[0], y: rect[1], w: rect[2], h: rect[3]
        };
      });

      event.preventDefault();
      return;
    }

    // PRIORITY 2: Check if clicking on selected region's handle
    if (editorState.selectedRegion && window.GJSON.rects[editorState.selectedRegion]) {
      const rect = window.GJSON.rects[editorState.selectedRegion];
      const handle = getResizeHandle(point, rect);

      if (handle) {
        // Start resize
        editorState.isResizing = true;
        editorState.resizeHandle = handle;
        editorState.dragStartPos = point;
        editorState.regionStartPos = {
          x: rect[0], y: rect[1], w: rect[2], h: rect[3]
        };
        event.preventDefault();
        return;
      }

      if (isPointInRegion(point, rect)) {
        // Start drag
        editorState.isDragging = true;
        editorState.dragStartPos = point;
        editorState.regionStartPos = {
          x: rect[0], y: rect[1], w: rect[2], h: rect[3]
        };
        event.preventDefault();
        return;
      }
    }

    // PRIORITY 3: Select new region
    const regionName = findRegionAtPoint(point);
    if (regionName) {
      selectRegion(regionName);
      editorState.isDragging = true;
      editorState.dragStartPos = point;
      const rect = window.GJSON.rects[regionName];
      editorState.regionStartPos = {
        x: rect[0], y: rect[1], w: rect[2], h: rect[3]
      };
      event.preventDefault();
    } else {
      deselectRegion();
    }
  }

  // Mouse move - perform drag or resize
  function handleMouseMove(event) {
    if (!editorState.enabled) return;

    const canvas = document.getElementById('epd');
    const point = getCanvasCoords(event);

    // Update cursor based on hover
    if (!editorState.isDragging && !editorState.isResizing && !editorState.isDraggingDivider) {
      // PRIORITY 1: Check for divider hover
      const hoveredDivider = findDividerAtPoint(point);
      if (hoveredDivider) {
        canvas.style.cursor = hoveredDivider.type === 'vertical' ? 'ew-resize' : 'ns-resize';
        editorState.hoveredDivider = hoveredDivider;
        requestAnimationFrame(() => window.draw && window.draw(window.lastData));
      } else {
        editorState.hoveredDivider = null;

        // PRIORITY 2: Check for resize handle hover (if region selected)
        if (editorState.selectedRegion) {
          const rect = window.GJSON.rects[editorState.selectedRegion];
          const handle = getResizeHandle(point, rect);

          if (handle) {
            const cursors = {
              'nw': 'nw-resize', 'ne': 'ne-resize',
              'sw': 'sw-resize', 'se': 'se-resize',
              'n': 'n-resize', 's': 's-resize',
              'e': 'e-resize', 'w': 'w-resize'
            };
            canvas.style.cursor = cursors[handle];
          } else if (isPointInRegion(point, rect)) {
            canvas.style.cursor = 'move';
          } else {
            canvas.style.cursor = 'default';
          }
        } else {
          // PRIORITY 3: Check for region hover
          const hoveredRegion = findRegionAtPoint(point);
          canvas.style.cursor = hoveredRegion ? 'pointer' : 'default';

          // Update hover state for tooltip
          editorState.hoveredRegion = hoveredRegion;
          editorState.hoverPos = point;

          // Trigger redraw to show/hide tooltip
          if (hoveredRegion || editorState.hoveredRegion) {
            requestAnimationFrame(() => window.draw && window.draw(window.lastData));
          }
        }
      }
    }

    // Perform divider drag
    if (editorState.isDraggingDivider && editorState.activeDivider) {
      const divider = editorState.activeDivider;
      const canvas = window.GJSON.canvas;
      const minRegionSize = 8; // Minimum region dimension

      if (divider.type === 'vertical') {
        // Dragging vertical divider (changes X positions and widths)
        const newPosition = snapToGrid(point.x);
        const delta = newPosition - divider.position;

        // Validate: ensure all affected regions stay within bounds and above minimum size
        let valid = true;

        // Check left regions (will shrink/grow in width)
        for (const name of divider.leftRegions) {
          const orig = editorState.regionStartPos[name];
          const newW = orig.w + delta;
          if (newW < minRegionSize || orig.x + newW > canvas.w) {
            valid = false;
            break;
          }
        }

        // Check right regions (will shift X and adjust width)
        if (valid) {
          for (const name of divider.rightRegions) {
            const orig = editorState.regionStartPos[name];
            const newX = orig.x + delta;
            const newW = orig.w - delta;
            if (newX < 0 || newW < minRegionSize || newX + newW > canvas.w) {
              valid = false;
              break;
            }
          }
        }

        // Apply changes if valid
        if (valid && newPosition >= 0 && newPosition <= canvas.w) {
          // Update left regions (expand/shrink width)
          for (const name of divider.leftRegions) {
            const orig = editorState.regionStartPos[name];
            window.GJSON.rects[name][2] = orig.w + delta; // width
          }

          // Update right regions (shift X, adjust width)
          for (const name of divider.rightRegions) {
            const orig = editorState.regionStartPos[name];
            window.GJSON.rects[name][0] = orig.x + delta; // x position
            window.GJSON.rects[name][2] = orig.w - delta; // width
          }

          checkCollisions();
          requestAnimationFrame(() => window.draw && window.draw(window.lastData || {}));
        }
      } else {
        // Dragging horizontal divider (changes Y positions and heights)
        const newPosition = snapToGrid(point.y);
        const delta = newPosition - divider.position;

        // Validate: ensure all affected regions stay within bounds and above minimum size
        let valid = true;

        // Check top regions (will shrink/grow in height)
        for (const name of divider.topRegions) {
          const orig = editorState.regionStartPos[name];
          const newH = orig.h + delta;
          if (newH < minRegionSize || orig.y + newH > canvas.h) {
            valid = false;
            break;
          }
        }

        // Check bottom regions (will shift Y and adjust height)
        if (valid) {
          for (const name of divider.bottomRegions) {
            const orig = editorState.regionStartPos[name];
            const newY = orig.y + delta;
            const newH = orig.h - delta;
            if (newY < 0 || newH < minRegionSize || newY + newH > canvas.h) {
              valid = false;
              break;
            }
          }
        }

        // Apply changes if valid
        if (valid && newPosition >= 0 && newPosition <= canvas.h) {
          // Update top regions (expand/shrink height)
          for (const name of divider.topRegions) {
            const orig = editorState.regionStartPos[name];
            window.GJSON.rects[name][3] = orig.h + delta; // height
          }

          // Update bottom regions (shift Y, adjust height)
          for (const name of divider.bottomRegions) {
            const orig = editorState.regionStartPos[name];
            window.GJSON.rects[name][1] = orig.y + delta; // y position
            window.GJSON.rects[name][3] = orig.h - delta; // height
          }

          checkCollisions();
          requestAnimationFrame(() => window.draw && window.draw(window.lastData || {}));
        }
      }

      event.preventDefault();
      return;
    }

    // Perform drag
    if (editorState.isDragging && editorState.selectedRegion) {
      const dx = point.x - editorState.dragStartPos.x;
      const dy = point.y - editorState.dragStartPos.y;

      let newX = snapToGrid(editorState.regionStartPos.x + dx);
      let newY = snapToGrid(editorState.regionStartPos.y + dy);

      // Clamp to canvas bounds
      const canvas = window.GJSON.canvas;
      newX = Math.max(0, Math.min(newX, canvas.w - editorState.regionStartPos.w));
      newY = Math.max(0, Math.min(newY, canvas.h - editorState.regionStartPos.h));

      // Update region
      window.GJSON.rects[editorState.selectedRegion][0] = newX;
      window.GJSON.rects[editorState.selectedRegion][1] = newY;

      updateSelectionInfo();
      checkCollisions();
      requestAnimationFrame(() => window.draw && window.draw(window.lastData || {}));
      event.preventDefault();
    }

    // Perform resize
    if (editorState.isResizing && editorState.selectedRegion) {
      const dx = point.x - editorState.dragStartPos.x;
      const dy = point.y - editorState.dragStartPos.y;

      let newX = editorState.regionStartPos.x;
      let newY = editorState.regionStartPos.y;
      let newW = editorState.regionStartPos.w;
      let newH = editorState.regionStartPos.h;

      const handle = editorState.resizeHandle;

      // Adjust based on handle
      if (handle.includes('w')) {
        newX = snapToGrid(editorState.regionStartPos.x + dx);
        newW = editorState.regionStartPos.w - (newX - editorState.regionStartPos.x);
      }
      if (handle.includes('e')) {
        newW = snapToGrid(editorState.regionStartPos.w + dx);
      }
      if (handle.includes('n')) {
        newY = snapToGrid(editorState.regionStartPos.y + dy);
        newH = editorState.regionStartPos.h - (newY - editorState.regionStartPos.y);
      }
      if (handle.includes('s')) {
        newH = snapToGrid(editorState.regionStartPos.h + dy);
      }

      // Enforce minimum size
      newW = Math.max(8, newW);
      newH = Math.max(8, newH);

      // Clamp to canvas bounds
      const canvas = window.GJSON.canvas;
      newX = Math.max(0, Math.min(newX, canvas.w - newW));
      newY = Math.max(0, Math.min(newY, canvas.h - newH));
      newW = Math.min(newW, canvas.w - newX);
      newH = Math.min(newH, canvas.h - newY);

      // Update region
      window.GJSON.rects[editorState.selectedRegion][0] = newX;
      window.GJSON.rects[editorState.selectedRegion][1] = newY;
      window.GJSON.rects[editorState.selectedRegion][2] = newW;
      window.GJSON.rects[editorState.selectedRegion][3] = newH;

      updateSelectionInfo();
      checkCollisions();
      requestAnimationFrame(() => window.draw && window.draw(window.lastData || {}));
      event.preventDefault();
    }
  }

  // Mouse up - end drag or resize
  function handleMouseUp(event) {
    if (editorState.isDragging || editorState.isResizing || editorState.isDraggingDivider) {
      editorState.isDragging = false;
      editorState.isResizing = false;
      editorState.isDraggingDivider = false;
      editorState.resizeHandle = null;
      editorState.activeDivider = null;
      editorState.hoveredDivider = null;

      const canvas = document.getElementById('epd');
      canvas.style.cursor = 'default';

      updateModifiedState();
      event.preventDefault();
    }
  }

  // Keyboard handler for arrow key adjustments
  function handleKeyDown(event) {
    // Don't interfere if user is typing in an input field
    if (event.target.tagName === 'INPUT' || event.target.tagName === 'TEXTAREA') return;

    // Handle ESC key (works even without selection)
    if (event.key === 'Escape' && editorState.enabled) {
      if (editorState.selectedRegion) {
        event.preventDefault();
        deselectRegion();
      }
      return;
    }

    // Only handle arrow keys if editor is enabled and a region is selected
    if (!editorState.enabled || !editorState.selectedRegion) return;

    const key = event.key;
    if (!['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(key)) return;

    event.preventDefault();

    const rect = window.GJSON.rects[editorState.selectedRegion];
    if (!rect) return;

    // Determine step size: 1px normal, 4px with Shift (grid size)
    const step = event.shiftKey ? editorState.gridSize : 1;

    // Get current position
    let [x, y, w, h] = rect;

    // Apply movement
    switch (key) {
      case 'ArrowUp':
        y = Math.max(0, y - step);
        break;
      case 'ArrowDown':
        y = Math.min(window.GJSON.canvas.h - h, y + step);
        break;
      case 'ArrowLeft':
        x = Math.max(0, x - step);
        break;
      case 'ArrowRight':
        x = Math.min(window.GJSON.canvas.w - w, x + step);
        break;
    }

    // Optional: snap to grid if enabled (only when using Shift)
    if (editorState.snapToGrid && event.shiftKey) {
      x = snapToGrid(x);
      y = snapToGrid(y);
    }

    // Update region
    window.GJSON.rects[editorState.selectedRegion][0] = x;
    window.GJSON.rects[editorState.selectedRegion][1] = y;

    // Update UI and check for collisions
    updateSelectionInfo();
    checkCollisions();
    updateModifiedState();
    requestAnimationFrame(() => window.draw && window.draw(window.lastData || {}));
  }

  // Select a region
  function selectRegion(name) {
    editorState.selectedRegion = name;
    updateSelectionInfo();
    updateInstructionVisibility();
    checkCollisions();
    requestAnimationFrame(() => window.draw && window.draw(window.lastData || {}));
  }

  // Deselect current region
  function deselectRegion() {
    editorState.selectedRegion = null;
    const selectionInfo = document.getElementById('selectionInfo');
    if (selectionInfo) {
      selectionInfo.style.display = 'none';
    }
    updateInstructionVisibility();
    requestAnimationFrame(() => window.draw && window.draw(window.lastData || {}));
  }

  // Update instruction visibility based on editor state
  function updateInstructionVisibility() {
    const instruction = document.getElementById('editorInstruction');
    if (!instruction) return;

    // Show instruction when editor enabled and nothing selected
    instruction.style.display = (editorState.enabled && !editorState.selectedRegion) ? 'block' : 'none';
  }

  // Update selection info panel
  function updateSelectionInfo() {
    const selectionInfo = document.getElementById('selectionInfo');
    if (!selectionInfo || !editorState.selectedRegion) return;

    const rect = window.GJSON?.rects?.[editorState.selectedRegion];
    if (!rect || !Array.isArray(rect) || rect.length < 4) {
      selectionInfo.style.display = 'none';
      return;
    }
    selectionInfo.style.display = 'block';

    document.getElementById('selectedRegionName').textContent = editorState.selectedRegion;
    document.getElementById('regionX').value = rect[0];
    document.getElementById('regionY').value = rect[1];
    document.getElementById('regionW').value = rect[2];
    document.getElementById('regionH').value = rect[3];

    // Update code viewer
    updateCodeViewer();
  }

  // === JSON CODE VIEWER FUNCTIONS ===

  /**
   * Generate formatted JSON code snippet with inline comments
   */
  function getRegionCodeSnippet(regionName) {
    if (!regionName || !window.GJSON || !window.GJSON.rects[regionName]) return '';

    const rect = window.GJSON.rects[regionName];
    const [x, y, w, h] = rect;

    return `"${regionName}": [
  ${x},  // X position (left edge)
  ${y},  // Y position (top edge)
  ${w},  // Width in pixels
  ${h}   // Height in pixels
]`;
  }

  /**
   * Update code viewer display when region is selected
   */
  function updateCodeViewer() {
    const codeBlock = document.getElementById('regionCode');
    const codeViewer = document.getElementById('codeViewer');

    if (!editorState.selectedRegion || !codeBlock || !codeViewer) return;

    // Show code viewer
    codeViewer.style.display = 'block';

    // Update code display
    const codeSnippet = getRegionCodeSnippet(editorState.selectedRegion);
    codeBlock.textContent = codeSnippet;

    // Make sure we're in display mode, not edit mode
    toggleCodeEditor(false);
  }

  /**
   * Copy region code to clipboard
   */
  async function copyRegionCode() {
    if (!editorState.selectedRegion) return;

    const codeSnippet = getRegionCodeSnippet(editorState.selectedRegion);

    try {
      await navigator.clipboard.writeText(codeSnippet);

      // Show visual feedback
      const button = document.getElementById('copyCode');
      const originalText = button.textContent;
      button.textContent = '✓ Copied!';
      button.style.background = '#d1fae5';

      setTimeout(() => {
        button.textContent = originalText;
        button.style.background = '';
      }, 2000);
    } catch (err) {
      console.error('Failed to copy code:', err);
      alert('Failed to copy to clipboard. Please select and copy manually.');
    }
  }

  /**
   * Reset region code to original from geometry
   */
  function resetRegionCode() {
    if (!editorState.selectedRegion || !editorState.originalGeometry) return;

    const originalRect = editorState.originalGeometry.rects[editorState.selectedRegion];
    if (originalRect) {
      window.GJSON.rects[editorState.selectedRegion] = [...originalRect];
      updateSelectionInfo();
      checkCollisions();
      updateModifiedState();
      requestAnimationFrame(() => window.draw && window.draw(window.lastData || {}));
    }
  }

  /**
   * Toggle between code display and edit mode
   */
  function toggleCodeEditor(show) {
    const codeDisplay = document.getElementById('codeDisplay');
    const codeEditor = document.getElementById('codeEditor');
    const codeTextarea = document.getElementById('codeTextarea');
    const codeValidation = document.getElementById('codeValidation');

    if (!codeDisplay || !codeEditor || !codeTextarea) return;

    if (show) {
      // Switch to edit mode
      codeDisplay.style.display = 'none';
      codeEditor.style.display = 'block';

      // Populate textarea with current values
      const rect = window.GJSON.rects[editorState.selectedRegion];
      const jsonString = `[\n  ${rect[0]},\n  ${rect[1]},\n  ${rect[2]},\n  ${rect[3]}\n]`;
      codeTextarea.value = jsonString;

      // Clear validation
      codeValidation.textContent = '';
      codeValidation.className = 'code-validation';

      // Focus textarea
      codeTextarea.focus();
    } else {
      // Switch back to display mode
      codeDisplay.style.display = 'block';
      codeEditor.style.display = 'none';
    }
  }

  /**
   * Validate region JSON input
   */
  function validateRegionJSON(jsonString) {
    const errors = [];

    try {
      const parsed = JSON.parse(jsonString);

      // Must be an array
      if (!Array.isArray(parsed)) {
        errors.push('Must be an array [x, y, w, h]');
        return { valid: false, errors };
      }

      // Must have exactly 4 elements
      if (parsed.length !== 4) {
        errors.push(`Must have exactly 4 values, got ${parsed.length}`);
        return { valid: false, errors };
      }

      // All must be integers
      if (!parsed.every(v => Number.isInteger(v))) {
        errors.push('All values must be integers');
        return { valid: false, errors };
      }

      const [x, y, w, h] = parsed;

      // Validate bounds
      if (x < 0 || y < 0) {
        errors.push('X and Y must be >= 0');
      }

      if (w < 1 || h < 1) {
        errors.push('Width and height must be > 0');
      }

      const canvas = window.GJSON.canvas;
      if (x + w > canvas.w) {
        errors.push(`Right edge (${x}+${w}=${x+w}) exceeds canvas width (${canvas.w})`);
      }

      if (y + h > canvas.h) {
        errors.push(`Bottom edge (${y}+${h}=${y+h}) exceeds canvas height (${canvas.h})`);
      }

      if (errors.length > 0) {
        return { valid: false, errors, parsed };
      }

      return { valid: true, errors: [], parsed };
    } catch (err) {
      errors.push(`Invalid JSON: ${err.message}`);
      return { valid: false, errors };
    }
  }

  /**
   * Apply manually edited code changes
   */
  function applyCodeChanges() {
    if (!editorState.selectedRegion) return;

    const codeTextarea = document.getElementById('codeTextarea');
    const codeValidation = document.getElementById('codeValidation');

    if (!codeTextarea || !codeValidation) return;

    const jsonString = codeTextarea.value.trim();
    const validation = validateRegionJSON(jsonString);

    if (!validation.valid) {
      // Show errors
      codeValidation.className = 'code-validation error';
      codeValidation.innerHTML = '<strong>⚠️ Validation Errors:</strong><ul>' +
        validation.errors.map(e => `<li>${e}</li>`).join('') +
        '</ul>';
      return;
    }

    // Apply changes
    const [x, y, w, h] = validation.parsed;
    window.GJSON.rects[editorState.selectedRegion] = [x, y, w, h];

    // Update UI
    updateSelectionInfo();
    checkCollisions();
    updateModifiedState();
    requestAnimationFrame(() => window.draw && window.draw(window.lastData || {}));

    // Show success and close editor
    codeValidation.className = 'code-validation success';
    codeValidation.innerHTML = '<strong>✓ Applied successfully!</strong>';

    setTimeout(() => {
      toggleCodeEditor(false);
    }, 1000);
  }

  // Apply manual coordinate changes
  function applyManualCoords() {
    if (!editorState.selectedRegion) return;

    const x = parseInt(document.getElementById('regionX').value);
    const y = parseInt(document.getElementById('regionY').value);
    const w = parseInt(document.getElementById('regionW').value);
    const h = parseInt(document.getElementById('regionH').value);

    // Validate parsed values are numbers
    if (isNaN(x) || isNaN(y) || isNaN(w) || isNaN(h)) {
      alert('Invalid input! All coordinates must be numbers.');
      return;
    }

    // Validate canvas exists
    if (!window.GJSON?.canvas) {
      console.warn('Cannot apply coords: GJSON.canvas not loaded');
      return;
    }

    // Validate bounds
    const canvas = window.GJSON.canvas;
    if (x < 0 || y < 0 || w < 1 || h < 1 || x + w > canvas.w || y + h > canvas.h) {
      alert('Invalid coordinates! Must be within canvas bounds.');
      return;
    }

    // Apply with optional snapping
    window.GJSON.rects[editorState.selectedRegion][0] = editorState.snapToGrid ? snapToGrid(x) : x;
    window.GJSON.rects[editorState.selectedRegion][1] = editorState.snapToGrid ? snapToGrid(y) : y;
    window.GJSON.rects[editorState.selectedRegion][2] = editorState.snapToGrid ? snapToGrid(w) : w;
    window.GJSON.rects[editorState.selectedRegion][3] = editorState.snapToGrid ? snapToGrid(h) : h;

    updateSelectionInfo();
    checkCollisions();
    updateModifiedState();
    requestAnimationFrame(() => window.draw && window.draw(window.lastData || {}));
  }

  // Reset selected region to original
  function resetSelectedRegion() {
    if (!editorState.selectedRegion || !editorState.originalGeometry) return;

    const originalRect = editorState.originalGeometry.rects[editorState.selectedRegion];
    if (originalRect) {
      window.GJSON.rects[editorState.selectedRegion] = [...originalRect];
      updateSelectionInfo();
      checkCollisions();
      updateModifiedState();
      requestAnimationFrame(() => window.draw && window.draw(window.lastData || {}));
    }
  }

  // Check for collisions between regions
  function checkCollisions() {
    editorState.collisions.clear();

    if (!window.GJSON || !window.GJSON.rects) return;

    const regions = Object.entries(window.GJSON.rects);

    for (let i = 0; i < regions.length; i++) {
      for (let j = i + 1; j < regions.length; j++) {
        const [name1, rect1] = regions[i];
        const [name2, rect2] = regions[j];

        if (rectsOverlap(rect1, rect2)) {
          editorState.collisions.add(`${name1} ↔ ${name2}`);
        }
      }
    }

    updateCollisionWarning();
  }

  // Check if two rects overlap
  function rectsOverlap(rect1, rect2) {
    const [x1, y1, w1, h1] = rect1;
    const [x2, y2, w2, h2] = rect2;

    return !(x1 + w1 <= x2 || x2 + w2 <= x1 || y1 + h1 <= y2 || y2 + h2 <= y1);
  }

  // Update collision warning display
  function updateCollisionWarning() {
    const warning = document.getElementById('collisionWarning');
    const list = document.getElementById('collisionList');

    if (!warning || !list) return;

    if (editorState.collisions.size > 0) {
      warning.style.display = 'block';
      list.innerHTML = Array.from(editorState.collisions)
        .map(collision => `<div>${collision}</div>`)
        .join('');
    } else {
      warning.style.display = 'none';
    }
  }

  // Update modified state and enable export/diff buttons
  function updateModifiedState() {
    const hasChanges = checkForChanges();

    const exportButton = document.getElementById('exportLayout');
    const diffButton = document.getElementById('showDiff');

    if (exportButton) exportButton.disabled = !hasChanges;
    if (diffButton) diffButton.disabled = !hasChanges;
  }

  // Check if any changes have been made
  function checkForChanges() {
    if (!editorState.originalGeometry || !window.GJSON) return false;

    const original = editorState.originalGeometry.rects;
    const current = window.GJSON.rects;

    for (const name in current) {
      if (!original[name]) return true;
      const currRect = current[name];
      const origRect = original[name];
      // Validate both are arrays with at least 4 elements
      if (!Array.isArray(currRect) || currRect.length < 4) continue;
      if (!Array.isArray(origRect) || origRect.length < 4) return true;
      for (let i = 0; i < 4; i++) {
        if (currRect[i] !== origRect[i]) return true;
      }
    }

    return false;
  }

  // Export modified layout as JSON
  function exportLayout() {
    if (!window.GJSON) return;

    // Create download
    const json = JSON.stringify(window.GJSON, null, 2);
    const blob = new Blob([json], { type: 'application/json' });
    const url = URL.createObjectURL(blob);

    const a = document.createElement('a');
    a.href = url;
    a.download = 'display_geometry_modified.json';
    a.click();

    URL.revokeObjectURL(url);

    // Show toast
    const toast = document.getElementById('globalToast');
    if (toast) {
      toast.textContent = 'Layout exported! Apply with: python3 scripts/apply_layout_changes.py';
      toast.classList.add('show');
      setTimeout(() => toast.classList.remove('show'), 5000);
    }
  }

  // Show diff panel
  function showDiffPanel() {
    if (!editorState.originalGeometry || !window.GJSON) return;

    const diffPanel = document.getElementById('diffPanel');
    const diffContent = document.getElementById('diffContent');

    if (!diffPanel || !diffContent) return;

    const original = editorState.originalGeometry.rects;
    const current = window.GJSON.rects;

    let html = '<table class="diff-table"><thead><tr><th>Region</th><th>Change</th><th>Delta</th></tr></thead><tbody>';

    for (const name in current) {
      const curr = current[name];
      const orig = original[name] || [0, 0, 0, 0];

      if (curr[0] !== orig[0] || curr[1] !== orig[1] || curr[2] !== orig[2] || curr[3] !== orig[3]) {
        const dx = curr[0] - orig[0];
        const dy = curr[1] - orig[1];
        const dw = curr[2] - orig[2];
        const dh = curr[3] - orig[3];

        let changes = [];
        if (dx !== 0 || dy !== 0) changes.push(`moved (${dx > 0 ? '+' : ''}${dx}, ${dy > 0 ? '+' : ''}${dy})`);
        if (dw !== 0 || dh !== 0) changes.push(`resized (${dw > 0 ? '+' : ''}${dw}, ${dh > 0 ? '+' : ''}${dh})`);

        html += `<tr>
          <td><strong>${name}</strong></td>
          <td>[${orig.join(', ')}] → [${curr.join(', ')}]</td>
          <td>${changes.join(', ')}</td>
        </tr>`;
      }
    }

    html += '</tbody></table>';
    diffContent.innerHTML = html;
    diffPanel.style.display = 'block';
  }

  // Reset all changes
  function resetAllChanges() {
    if (!confirm('Reset all layout changes to original?')) return;

    if (editorState.originalGeometry) {
      window.GJSON = JSON.parse(JSON.stringify(editorState.originalGeometry));
      deselectRegion();
      checkCollisions();
      updateModifiedState();
      requestAnimationFrame(() => window.draw && window.draw(window.lastData || {}));
    }
  }

  // Update editor badge
  function updateEditorBadge() {
    const badge = document.getElementById('editorBadge');
    if (badge) {
      badge.textContent = editorState.enabled ? 'ON' : 'OFF';
      badge.className = editorState.enabled ? 'badge badge-success' : 'badge';
    }
  }

  // Draw editor overlays (selection, handles, etc.)
  function drawEditorOverlay(ctx) {
    if (!editorState.enabled) return;

    // DIVIDER HIGHLIGHTS (draw first, underneath everything else)
    if (editorState.hoveredDivider || editorState.isDraggingDivider) {
      const divider = editorState.activeDivider || editorState.hoveredDivider;
      if (divider && window.GJSON && window.GJSON.canvas) {
        ctx.save();

        // Visual style: bright highlight when dragging, subtle when hovering
        const isDragging = editorState.isDraggingDivider;
        ctx.strokeStyle = isDragging ? '#ff6600' : '#0066ff';
        ctx.lineWidth = isDragging ? 3 : 2;
        ctx.setLineDash([]);

        if (divider.type === 'vertical') {
          // Draw vertical line
          const x = divider.position;
          ctx.beginPath();
          ctx.moveTo(x, 0);
          ctx.lineTo(x, window.GJSON.canvas.h);
          ctx.stroke();

          // Add subtle glow effect when dragging
          if (isDragging) {
            ctx.shadowColor = 'rgba(255, 102, 0, 0.5)';
            ctx.shadowBlur = 6;
            ctx.stroke();
          }
        } else {
          // Draw horizontal line
          const y = divider.position;
          ctx.beginPath();
          ctx.moveTo(0, y);
          ctx.lineTo(window.GJSON.canvas.w, y);
          ctx.stroke();

          // Add subtle glow effect when dragging
          if (isDragging) {
            ctx.shadowColor = 'rgba(255, 102, 0, 0.5)';
            ctx.shadowBlur = 6;
            ctx.stroke();
          }
        }

        ctx.restore();
      }
    }

    // HOVER TOOLTIP (draw first, before other overlays)
    if (editorState.hoveredRegion && !editorState.selectedRegion && !editorState.isDragging) {
      const hoverPos = editorState.hoverPos;
      const regionName = editorState.hoveredRegion;

      ctx.save();
      ctx.font = 'bold 11px sans-serif';
      const metrics = ctx.measureText(regionName);
      const tooltipWidth = metrics.width + 16;
      const tooltipHeight = 20;

      // Position tooltip near cursor, but avoid edges
      let tooltipX = hoverPos.x + 12;
      let tooltipY = hoverPos.y - tooltipHeight - 8;

      // Keep tooltip in bounds
      if (tooltipX + tooltipWidth > window.GJSON.canvas.w) {
        tooltipX = hoverPos.x - tooltipWidth - 12;
      }
      if (tooltipY < 0) {
        tooltipY = hoverPos.y + 12;
      }

      // Background with border
      ctx.fillStyle = 'rgba(0, 0, 0, 0.9)';
      ctx.fillRect(tooltipX, tooltipY, tooltipWidth, tooltipHeight);
      ctx.strokeStyle = '#0066ff';
      ctx.lineWidth = 1;
      ctx.strokeRect(tooltipX, tooltipY, tooltipWidth, tooltipHeight);

      // Text
      ctx.fillStyle = '#ffffff';
      ctx.textBaseline = 'middle';
      ctx.fillText(regionName, tooltipX + 8, tooltipY + tooltipHeight/2);

      ctx.restore();
    }

    // If editor is enabled but nothing selected, show all regions as clickable
    if (!editorState.selectedRegion) {
      ctx.save();
      ctx.strokeStyle = 'rgba(0, 102, 255, 0.3)';
      ctx.lineWidth = 1;
      ctx.setLineDash([2, 2]);

      // Draw subtle outlines on all regions to show they're clickable
      for (const [name, rect] of Object.entries(window.GJSON.rects)) {
        const [x, y, w, h] = rect;
        ctx.strokeRect(x, y, w, h);
      }

      ctx.restore();

      return;
    }

    // === ENHANCED SELECTION VISUALS ===

    const rect = window.GJSON.rects[editorState.selectedRegion];
    if (!rect) return;

    const [x, y, w, h] = rect;

    // 1. DIM ALL OTHER REGIONS (focus effect)
    ctx.save();
    ctx.fillStyle = 'rgba(255, 255, 255, 0.6)';
    ctx.fillRect(0, 0, window.GJSON.canvas.w, window.GJSON.canvas.h);
    ctx.restore();

    // 2. SEMI-TRANSPARENT OVERLAY on selected region
    ctx.save();
    ctx.fillStyle = 'rgba(0, 102, 255, 0.12)';
    ctx.fillRect(x, y, w, h);
    ctx.restore();

    // 3. THICK SELECTION OUTLINE (solid, not dashed)
    ctx.save();
    ctx.strokeStyle = '#0066ff';
    ctx.lineWidth = 3;
    ctx.setLineDash([]); // Solid line
    ctx.strokeRect(x, y, w, h);
    ctx.restore();

    // 4. LARGE REGION NAME LABEL (on canvas)
    ctx.save();
    // Measure text to size background properly
    ctx.font = 'bold 12px sans-serif';
    const nameText = editorState.selectedRegion;
    const textMetrics = ctx.measureText(nameText);
    const labelWidth = Math.min(textMetrics.width + 16, w);
    const labelHeight = 18;

    // Position label above region if possible, otherwise inside top
    const labelY = y > labelHeight + 2 ? y - labelHeight - 2 : y;

    // Background bar
    ctx.fillStyle = '#0066ff';
    ctx.fillRect(x, labelY, labelWidth, labelHeight);

    // Text
    ctx.fillStyle = '#ffffff';
    ctx.textBaseline = 'middle';
    ctx.fillText(nameText, x + 8, labelY + labelHeight/2);
    ctx.restore();

    // 5. COORDINATES DISPLAY (bottom right of region)
    ctx.save();
    ctx.font = '10px monospace';
    const coordText = `[${x}, ${y}, ${w}, ${h}]`;
    const coordMetrics = ctx.measureText(coordText);

    // Semi-transparent background
    ctx.fillStyle = 'rgba(0, 0, 0, 0.75)';
    ctx.fillRect(x + w - coordMetrics.width - 8, y + h - 16, coordMetrics.width + 6, 14);

    // Text
    ctx.fillStyle = '#ffffff';
    ctx.textBaseline = 'middle';
    ctx.fillText(coordText, x + w - coordMetrics.width - 5, y + h - 9);
    ctx.restore();

    // 6. RESIZE HANDLES (with subtle glow effect)
    ctx.save();
    ctx.fillStyle = '#0066ff';
    ctx.shadowColor = 'rgba(0, 102, 255, 0.5)';
    ctx.shadowBlur = 4;

    const handles = [
      [x, y],                 // nw
      [x + w, y],             // ne
      [x, y + h],             // sw
      [x + w, y + h],         // se
      [x + w/2, y],           // n
      [x + w/2, y + h],       // s
      [x, y + h/2],           // w
      [x + w, y + h/2]        // e
    ];

    handles.forEach(([hx, hy]) => {
      // Draw handle with white border
      ctx.fillRect(hx - HANDLE_HALF, hy - HANDLE_HALF, HANDLE_SIZE, HANDLE_SIZE);
      ctx.strokeStyle = '#ffffff';
      ctx.lineWidth = 1;
      ctx.strokeRect(hx - HANDLE_HALF, hy - HANDLE_HALF, HANDLE_SIZE, HANDLE_SIZE);
    });

    ctx.restore();

    // 7. DIMENSION LABEL (above region)
    ctx.save();
    ctx.font = 'bold 11px monospace';
    const dimText = `${w}×${h}px`;
    const dimMetrics = ctx.measureText(dimText);

    // Background
    ctx.fillStyle = 'rgba(0, 0, 0, 0.75)';
    ctx.fillRect(x + w/2 - dimMetrics.width/2 - 4, y - 20, dimMetrics.width + 8, 16);

    // Text
    ctx.fillStyle = '#ffffff';
    ctx.textBaseline = 'middle';
    ctx.fillText(dimText, x + w/2 - dimMetrics.width/2, y - 12);
    ctx.restore();
  }

  // Expose editor functions globally
  window.layoutEditor = {
    init: initLayoutEditor,
    state: editorState,
    drawOverlay: drawEditorOverlay
  };

  // Auto-initialize when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initLayoutEditor);
  } else {
    initLayoutEditor();
  }

})();
