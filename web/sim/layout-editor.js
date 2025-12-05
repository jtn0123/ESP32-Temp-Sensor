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
    editMode: 'regions', // 'regions' or 'dividers' - which editing mode is active
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
    alignmentGuides: [], // Array of { type: 'horizontal'|'vertical', position: number }
    // Divider detection settings
    dividerTolerance: 8, // Pixels tolerance for finding edge alignments
    showDividerDebug: false // Show debug info for divider detection
  };

  // Handle size in pixels
  const HANDLE_SIZE = 10;
  const HANDLE_HALF = HANDLE_SIZE / 2;
  
  // Divider hit tolerance (pixels) - increased for easier targeting
  const DIVIDER_TOLERANCE = 6;

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
    
    // Add drag indicator element
    addDragIndicator();

    // Set up event listeners
    setupEventListeners();

    // Load original geometry
    loadOriginalGeometry();

    console.log('Layout editor initialized');

    // Debug: Log dividers after geometry loads
    setTimeout(() => {
      const allLines = getAllUISpecLines();
      const vDividers = findVerticalDividers();
      const hDividers = findHorizontalDividers();
      console.log('[Layout Editor] Lines from UI_SPEC:', allLines.length, allLines.map(l => `${l.source}: (${l.from[0]},${l.from[1]})→(${l.to[0]},${l.to[1]})`));
      console.log('[Layout Editor] Movable dividers: ', vDividers.length, 'vertical,', hDividers.length, 'horizontal');
      if (vDividers.length > 0) {
        console.log('  Vertical lines:', vDividers.map(d => `x=${d.position} (affects ${d.leftRegions.length}L, ${d.rightRegions.length}R regions)`).join(', '));
      }
      if (hDividers.length > 0) {
        console.log('  Horizontal lines:', hDividers.map(d => `y=${d.position} (affects ${d.topRegions.length}T, ${d.bottomRegions.length}B regions)`).join(', '));
      }
    }, 500);
  }
  
  // Add drag indicator element to page
  function addDragIndicator() {
    if (document.getElementById('dragIndicator')) return;
    
    const indicator = document.createElement('div');
    indicator.id = 'dragIndicator';
    indicator.className = 'drag-indicator';
    document.body.appendChild(indicator);
  }
  
  // Update canvas classes for cursor states
  function updateCanvasClasses() {
    const canvas = document.getElementById('epd');
    if (!canvas) return;
    
    // Reset all editor classes
    canvas.classList.remove('editor-enabled', 'region-hover', 'dragging', 'resizing');
    
    if (editorState.enabled) {
      canvas.classList.add('editor-enabled');
      
      if (editorState.isDragging || editorState.isDraggingDivider) {
        canvas.classList.add('dragging');
      } else if (editorState.isResizing) {
        canvas.classList.add('resizing');
      } else if (editorState.hoveredRegion || editorState.hoveredDivider) {
        canvas.classList.add('region-hover');
      }
    }
  }
  
  // Show/hide drag indicator with message
  function showDragIndicator(message) {
    const indicator = document.getElementById('dragIndicator');
    if (indicator) {
      indicator.textContent = message;
      indicator.classList.add('visible');
    }
  }
  
  function hideDragIndicator() {
    const indicator = document.getElementById('dragIndicator');
    if (indicator) {
      indicator.classList.remove('visible');
    }
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
        
        <div id="editModeToggle" class="edit-mode-toggle" style="display: none;">
          <span class="mode-label">Edit Mode:</span>
          <div class="mode-buttons">
            <button id="modeRegions" class="mode-btn active" title="Edit individual regions">📦 Regions</button>
            <button id="modeDividers" class="mode-btn" title="Move divider lines to resize multiple regions at once">📏 Dividers</button>
          </div>
          <div id="dividerStatus" class="divider-status"></div>
        </div>

        <div id="editorInstruction" class="editor-instruction" style="display: none;">
          <div class="instruction-box">
            <span class="instruction-icon">👆</span>
            <span class="instruction-text">Click any region or divider line to edit</span>
          </div>
        </div>

        <div id="selectionInfo" class="selection-info" style="display: none;">
          <h4>Selected: <span id="selectedRegionName"></span></h4>
          <div class="coord-display">
            <span class="coord-group"><span class="coord-label">X</span><input type="number" id="regionX" step="1" min="0"></span>
            <span class="coord-group"><span class="coord-label">Y</span><input type="number" id="regionY" step="1" min="0"></span>
            <span class="coord-group"><span class="coord-label">W</span><input type="number" id="regionW" step="1" min="1"></span>
            <span class="coord-group"><span class="coord-label">H</span><input type="number" id="regionH" step="1" min="1"></span>
          </div>
          <div class="keyboard-hint">
            ⌨️ Arrow: 1px | Shift+Arrow: 4px
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
          <button id="importLayout">Import Layout JSON</button>
          <button id="showDiff" disabled>Show Changes</button>
          <button id="saveToStorage" disabled title="Save current layout to browser storage (persists across page reloads)">Save to Browser</button>
          <button id="resetLayout">Reset All Changes</button>
          <button id="clearStorage" title="Clear saved layout from browser storage">Clear Saved</button>
        </div>
        <div id="storageStatus" class="storage-status" style="display: none;">
          <span class="storage-icon">💾</span>
          <span id="storageStatusText">Layout loaded from browser storage</span>
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
        updateEditModeVisibility();
        
        if (editorState.enabled) {
          // When enabling the editor, ensure we're showing the actual UI content
          // by exiting labels-only mode if it's active
          resetToNormalDisplayMode();
          updateDividerStatus();
        } else {
          deselectRegion();
        }

        // Force immediate redraw to show visual feedback
        if (typeof window.draw === 'function') {
          requestAnimationFrame(() => window.draw(window.lastData || {}));
        }
      });
    }
    
    // Edit mode toggle buttons
    const modeRegionsBtn = document.getElementById('modeRegions');
    const modeDividersBtn = document.getElementById('modeDividers');
    
    if (modeRegionsBtn) {
      modeRegionsBtn.addEventListener('click', () => setEditMode('regions'));
    }
    if (modeDividersBtn) {
      modeDividersBtn.addEventListener('click', () => setEditMode('dividers'));
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

    // Import layout
    const importButton = document.getElementById('importLayout');
    if (importButton) {
      importButton.addEventListener('click', importLayout);
    }

    // Save to localStorage
    const saveStorageButton = document.getElementById('saveToStorage');
    if (saveStorageButton) {
      saveStorageButton.addEventListener('click', saveToLocalStorage);
    }

    // Clear localStorage
    const clearStorageButton = document.getElementById('clearStorage');
    if (clearStorageButton) {
      clearStorageButton.addEventListener('click', clearLocalStorage);
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
        
        // Check if there's a saved layout in localStorage
        const savedLayout = loadFromLocalStorage();
        if (savedLayout) {
          console.log('📁 Found saved layout in browser storage, applying...');
          applyImportedLayout(savedLayout);
          showStorageStatus(true);
        } else {
          showStorageStatus(false);
        }
        
        // Update UI state
        updateModifiedState();
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
  // Dividers are based on ACTUAL lines drawn in UI_SPEC.components.chrome,
  // NOT on region edge alignments.

  /**
   * Get all lines from UI_SPEC components (chrome, header, etc.)
   * Returns array of { from: [x,y], to: [x,y], source: 'chrome'|'header'|etc }
   */
  function getAllUISpecLines() {
    const lines = [];
    const spec = window.UI_SPEC;
    if (!spec || !spec.components) return lines;
    
    // Scan all components for line operations
    for (const [componentName, operations] of Object.entries(spec.components)) {
      if (!Array.isArray(operations)) continue;
      
      for (const op of operations) {
        if (op && op.op === 'line' && Array.isArray(op.from) && Array.isArray(op.to)) {
          lines.push({
            from: [op.from[0], op.from[1]],
            to: [op.to[0], op.to[1]],
            source: componentName
          });
        }
      }
    }
    
    return lines;
  }

  /**
   * Find all vertical dividers from actual UI_SPEC lines
   * Returns array of { type: 'vertical', position: x, line: {...}, affectedRegions: {...} }
   */
  function findVerticalDividers() {
    const lines = getAllUISpecLines();
    const canvas = window.GJSON?.canvas;
    if (!canvas) return [];
    
    const dividers = [];
    const tolerance = editorState.dividerTolerance;
    
    for (const line of lines) {
      const [fx, fy] = line.from;
      const [tx, ty] = line.to;
      
      // Vertical line: same x coordinate
      if (fx === tx) {
        const x = fx;
        
        // Skip canvas border lines (x=0 or x=canvas.w-1)
        if (x <= 1 || x >= canvas.w - 2) continue;
        
        // Find regions affected by this line (touching left or right)
        const affectedRegions = findRegionsTouchingVerticalLine(x, Math.min(fy, ty), Math.max(fy, ty), tolerance);
        
        dividers.push({
          type: 'vertical',
          position: x,
          line: line,
          yStart: Math.min(fy, ty),
          yEnd: Math.max(fy, ty),
          leftRegions: affectedRegions.left,
          rightRegions: affectedRegions.right
        });
      }
    }
    
    return dividers;
  }

  /**
   * Find all horizontal dividers from actual UI_SPEC lines
   * Returns array of { type: 'horizontal', position: y, line: {...}, affectedRegions: {...} }
   */
  function findHorizontalDividers() {
    const lines = getAllUISpecLines();
    const canvas = window.GJSON?.canvas;
    if (!canvas) return [];
    
    const dividers = [];
    const tolerance = editorState.dividerTolerance;
    
    for (const line of lines) {
      const [fx, fy] = line.from;
      const [tx, ty] = line.to;
      
      // Horizontal line: same y coordinate
      if (fy === ty) {
        const y = fy;
        
        // Skip canvas border lines (y=0 or y=canvas.h-1)
        if (y <= 1 || y >= canvas.h - 2) continue;
        
        // Find regions affected by this line (touching top or bottom)
        const affectedRegions = findRegionsTouchingHorizontalLine(y, Math.min(fx, tx), Math.max(fx, tx), tolerance);
        
        dividers.push({
          type: 'horizontal',
          position: y,
          line: line,
          xStart: Math.min(fx, tx),
          xEnd: Math.max(fx, tx),
          topRegions: affectedRegions.top,
          bottomRegions: affectedRegions.bottom
        });
      }
    }
    
    return dividers;
  }

  /**
   * Find regions that touch a vertical line (for moving them with the divider)
   */
  function findRegionsTouchingVerticalLine(x, yStart, yEnd, tolerance) {
    const left = [];   // Regions whose right edge is near the line
    const right = [];  // Regions whose left edge is near the line
    
    if (!window.GJSON?.rects) return { left, right };
    
    for (const [name, rect] of Object.entries(window.GJSON.rects)) {
      const [rx, ry, rw, rh] = rect;
      const rightEdge = rx + rw;
      
      // Check if region overlaps vertically with the line
      const regionBottom = ry + rh;
      const overlapsY = !(regionBottom < yStart || ry > yEnd);
      if (!overlapsY) continue;
      
      // Right edge touches line (region is to the left)
      if (Math.abs(rightEdge - x) <= tolerance) {
        left.push(name);
      }
      // Left edge touches line (region is to the right)
      if (Math.abs(rx - x) <= tolerance) {
        right.push(name);
      }
    }
    
    return { left, right };
  }

  /**
   * Find regions that touch a horizontal line (for moving them with the divider)
   */
  function findRegionsTouchingHorizontalLine(y, xStart, xEnd, tolerance) {
    const top = [];     // Regions whose bottom edge is near the line
    const bottom = [];  // Regions whose top edge is near the line
    
    if (!window.GJSON?.rects) return { top, bottom };
    
    for (const [name, rect] of Object.entries(window.GJSON.rects)) {
      const [rx, ry, rw, rh] = rect;
      const bottomEdge = ry + rh;
      
      // Check if region overlaps horizontally with the line
      const regionRight = rx + rw;
      const overlapsX = !(regionRight < xStart || rx > xEnd);
      if (!overlapsX) continue;
      
      // Bottom edge touches line (region is above)
      if (Math.abs(bottomEdge - y) <= tolerance) {
        top.push(name);
      }
      // Top edge touches line (region is below)
      if (Math.abs(ry - y) <= tolerance) {
        bottom.push(name);
      }
    }
    
    return { top, bottom };
  }

  /**
   * Update a line in UI_SPEC to a new position
   * @param {Object} lineRef - The line object reference from getAllUISpecLines
   * @param {number} newPosition - The new position (x for vertical, y for horizontal)
   * @param {string} type - 'vertical' or 'horizontal'
   */
  function updateUISpecLine(lineRef, newPosition, type) {
    if (!window.UI_SPEC || !lineRef || !lineRef.source) return;
    
    const spec = window.UI_SPEC;
    const component = spec.components?.[lineRef.source];
    if (!Array.isArray(component)) return;
    
    // Find the matching line operation in the component
    for (const op of component) {
      if (op && op.op === 'line' && 
          op.from[0] === lineRef.from[0] && op.from[1] === lineRef.from[1] &&
          op.to[0] === lineRef.to[0] && op.to[1] === lineRef.to[1]) {
        
        if (type === 'vertical') {
          // Update x coordinate for both from and to
          op.from[0] = newPosition;
          op.to[0] = newPosition;
        } else {
          // Update y coordinate for both from and to
          op.from[1] = newPosition;
          op.to[1] = newPosition;
        }
        
        console.log(`📏 Updated ${type} line in ${lineRef.source}: ${type === 'vertical' ? 'x' : 'y'}=${newPosition}`);
        
        // Also update the lineRef so subsequent updates use the new position
        if (type === 'vertical') {
          lineRef.from[0] = newPosition;
          lineRef.to[0] = newPosition;
        } else {
          lineRef.from[1] = newPosition;
          lineRef.to[1] = newPosition;
        }
        
        return;
      }
    }
    
    console.warn('Could not find matching line in UI_SPEC to update');
  }

  /**
   * Find divider at mouse point (with tolerance)
   * Returns divider object or null
   */
  function findDividerAtPoint(point) {
    // Check vertical dividers
    const verticalDividers = findVerticalDividers();
    for (const divider of verticalDividers) {
      if (Math.abs(point.x - divider.position) <= DIVIDER_TOLERANCE) {
        return divider;
      }
    }

    // Check horizontal dividers
    const horizontalDividers = findHorizontalDividers();
    for (const divider of horizontalDividers) {
      if (Math.abs(point.y - divider.position) <= DIVIDER_TOLERANCE) {
        return divider;
      }
    }

    return null;
  }

  // Mouse down - start drag or resize
  function handleMouseDown(event) {
    if (!editorState.enabled) return;

    const point = getCanvasCoords(event);

    // === DIVIDERS MODE ===
    if (editorState.editMode === 'dividers') {
      const divider = findDividerAtPoint(point);
      if (divider) {
        // Start divider dragging
        editorState.isDraggingDivider = true;
        editorState.activeDivider = divider;
        editorState.dividerStartPos = divider.position; // Use actual line position
        editorState.dragStartPos = point;

        // Store original positions of all affected regions
        editorState.regionStartPos = {};
        const affectedRegions = divider.type === 'vertical'
          ? [...divider.leftRegions, ...divider.rightRegions]
          : [...divider.topRegions, ...divider.bottomRegions];

        affectedRegions.forEach(name => {
          const [x, y, w, h] = window.SafeUtils.getRect(window.GJSON?.rects, name);
          editorState.regionStartPos[name] = { x, y, w, h };
        });

        // Store original line position from UI_SPEC for updating
        editorState.originalLinePos = {
          from: [...divider.line.from],
          to: [...divider.line.to]
        };

        // Show visual feedback
        const direction = divider.type === 'vertical' ? '↔' : '↕';
        const regionCount = affectedRegions.length;
        showDragIndicator(`${direction} Drag line at ${divider.type === 'vertical' ? 'x' : 'y'}=${divider.position} (${regionCount} regions)`);
        updateCanvasClasses();

        event.preventDefault();
      }
      return; // In dividers mode, only handle dividers
    }

    // === REGIONS MODE ===
    // PRIORITY 1: Check if clicking on selected region's handle or body FIRST
    // This ensures resize handles take priority over dividers when a region is selected
    if (editorState.selectedRegion && window.GJSON?.rects?.[editorState.selectedRegion]) {
      const rect = window.SafeUtils.getRect(window.GJSON?.rects, editorState.selectedRegion);
      const handle = getResizeHandle(point, rect);

      if (handle) {
        // Start resize
        editorState.isResizing = true;
        editorState.resizeHandle = handle;
        editorState.dragStartPos = point;
        editorState.regionStartPos = {
          x: rect[0], y: rect[1], w: rect[2], h: rect[3]
        };
        showDragIndicator(`⤡ Resizing: ${editorState.selectedRegion}`);
        updateCanvasClasses();
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
        showDragIndicator(`✋ Moving: ${editorState.selectedRegion}`);
        updateCanvasClasses();
        event.preventDefault();
        return;
      }
    }

    // PRIORITY 2: Select new region
    const regionName = findRegionAtPoint(point);
    if (regionName) {
      selectRegion(regionName);
      editorState.isDragging = true;
      editorState.dragStartPos = point;
      const [x, y, w, h] = window.SafeUtils.getRect(window.GJSON?.rects, regionName);
      editorState.regionStartPos = { x, y, w, h };
      showDragIndicator(`✋ Moving: ${regionName}`);
      updateCanvasClasses();
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
      
      // === DIVIDERS MODE ===
      if (editorState.editMode === 'dividers') {
        const hoveredDivider = findDividerAtPoint(point);
        if (hoveredDivider) {
          canvas.style.cursor = hoveredDivider.type === 'vertical' ? 'ew-resize' : 'ns-resize';
          editorState.hoveredDivider = hoveredDivider;
          updateCanvasClasses();
          requestAnimationFrame(() => window.draw && window.draw(window.lastData));
        } else {
          canvas.style.cursor = 'default';
          editorState.hoveredDivider = null;
        }
        return; // In dividers mode, only check dividers
      }
      
      // === REGIONS MODE ===
      // PRIORITY 1: Check for resize handle hover FIRST (if region selected)
      // This ensures handles take visual priority over dividers
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
          editorState.hoveredDivider = null; // Clear divider hover when on handle
          return; // Don't check dividers if on a handle
        } else if (isPointInRegion(point, rect)) {
          canvas.style.cursor = 'grab';
          editorState.hoveredDivider = null;
          return;
        }
      }
      
      // PRIORITY 2: Check for region hover (in regions mode)
      const hoveredRegion = findRegionAtPoint(point);
      const prevHovered = editorState.hoveredRegion;
      editorState.hoveredRegion = hoveredRegion;
      editorState.hoverPos = point;
      editorState.hoveredDivider = null;
      
      if (hoveredRegion) {
        canvas.style.cursor = editorState.selectedRegion ? 'default' : 'pointer';
      } else {
        canvas.style.cursor = 'default';
      }
      
      // Update canvas classes for hover state
      if (hoveredRegion !== prevHovered) {
        updateCanvasClasses();
      }

      // Trigger redraw to show/hide tooltip
      if (hoveredRegion || prevHovered) {
        requestAnimationFrame(() => window.draw && window.draw(window.lastData));
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

          // Update the actual line in UI_SPEC
          updateUISpecLine(divider.line, newPosition, 'vertical');

          checkCollisions();
          updateModifiedState();
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

          // Update the actual line in UI_SPEC
          updateUISpecLine(divider.line, newPosition, 'horizontal');

          checkCollisions();
          updateModifiedState();
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

      // Hide drag indicator and update visual state
      hideDragIndicator();
      updateCanvasClasses();

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
    
    // Ensure focus is not on input fields so arrow keys work for movement
    if (document.activeElement && document.activeElement.tagName === 'INPUT') {
      document.activeElement.blur();
    }
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
  // NOTE: Manual entry does NOT snap to grid - the user typed those specific values intentionally.
  // Grid snapping only applies to mouse-based drag/resize operations.
  function applyManualCoords() {
    if (!editorState.selectedRegion) return;

    const regionName = editorState.selectedRegion;
    const x = window.SafeUtils.safeParseInt(document.getElementById('regionX')?.value, 0);
    const y = window.SafeUtils.safeParseInt(document.getElementById('regionY')?.value, 0);
    const w = window.SafeUtils.safeParseInt(document.getElementById('regionW')?.value, 0);
    const h = window.SafeUtils.safeParseInt(document.getElementById('regionH')?.value, 0);

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

    // Apply the exact values - no snapping for manual entry
    window.GJSON.rects[regionName][0] = x;
    window.GJSON.rects[regionName][1] = y;
    window.GJSON.rects[regionName][2] = w;
    window.GJSON.rects[regionName][3] = h;

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
    const saveStorageButton = document.getElementById('saveToStorage');

    if (exportButton) exportButton.disabled = !hasChanges;
    if (diffButton) diffButton.disabled = !hasChanges;
    if (saveStorageButton) saveStorageButton.disabled = !hasChanges;
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

  // localStorage key for saved geometry
  const STORAGE_KEY = 'sim_layout_geometry';

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
    showToast('Layout exported! To make permanent, run: python3 scripts/apply_layout_changes.py ~/Downloads/display_geometry_modified.json', 'success');
  }

  // Import layout from JSON file
  function importLayout() {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.json,application/json';
    
    input.onchange = (e) => {
      const file = e.target.files[0];
      if (!file) return;
      
      const reader = new FileReader();
      reader.onload = (event) => {
        try {
          const importedData = JSON.parse(event.target.result);
          
          // Validate the imported JSON structure
          const validation = validateLayoutJSON(importedData);
          if (!validation.valid) {
            showToast(`Import failed: ${validation.error}`, 'error');
            return;
          }
          
          // Apply the imported layout
          applyImportedLayout(importedData);
          showToast(`Layout imported successfully! ${validation.regions} regions loaded.`, 'success');
          
        } catch (err) {
          showToast(`Import error: ${err.message}`, 'error');
        }
      };
      reader.readAsText(file);
    };
    
    input.click();
  }

  // Validate imported layout JSON for backwards compatibility
  function validateLayoutJSON(data) {
    // Check basic structure
    if (!data || typeof data !== 'object') {
      return { valid: false, error: 'Invalid JSON structure' };
    }
    
    // Must have rects object
    if (!data.rects || typeof data.rects !== 'object') {
      return { valid: false, error: 'Missing "rects" object' };
    }
    
    // Validate each rect
    const regionCount = Object.keys(data.rects).length;
    if (regionCount === 0) {
      return { valid: false, error: 'No regions defined in "rects"' };
    }
    
    for (const [name, rect] of Object.entries(data.rects)) {
      if (!Array.isArray(rect) || rect.length < 4) {
        return { valid: false, error: `Invalid rect for "${name}": must be array [x, y, w, h]` };
      }
      for (let i = 0; i < 4; i++) {
        if (typeof rect[i] !== 'number' || !Number.isFinite(rect[i])) {
          return { valid: false, error: `Invalid coordinate in "${name}": must be numbers` };
        }
      }
      if (rect[2] <= 0 || rect[3] <= 0) {
        return { valid: false, error: `Invalid size in "${name}": width and height must be > 0` };
      }
    }
    
    // Check for canvas dimensions (optional but helpful)
    if (data.canvas) {
      if (typeof data.canvas.w !== 'number' || typeof data.canvas.h !== 'number') {
        return { valid: false, error: 'Invalid canvas dimensions' };
      }
    }
    
    return { valid: true, regions: regionCount };
  }

  // Apply imported layout to the simulator
  function applyImportedLayout(data) {
    // Preserve canvas and fonts from original if not in imported data
    const mergedData = {
      layout_version: data.layout_version || (window.GJSON?.layout_version) || 1,
      layout_crc: data.layout_crc || 'imported',
      canvas: data.canvas || window.GJSON?.canvas || { w: 250, h: 122 },
      fonts: data.fonts || window.GJSON?.fonts || { big_px: 22, mid_px: 11, small_px: 10 },
      rects: data.rects
    };
    
    // Apply to global
    window.GJSON = mergedData;
    
    // Update state
    deselectRegion();
    checkCollisions();
    updateModifiedState();
    
    // Redraw
    if (typeof window.draw === 'function') {
      requestAnimationFrame(() => window.draw(window.lastData || {}));
    }
  }

  // Save current layout to localStorage
  function saveToLocalStorage() {
    if (!window.GJSON) {
      showToast('No layout to save', 'error');
      return;
    }
    
    try {
      const json = JSON.stringify(window.GJSON);
      localStorage.setItem(STORAGE_KEY, json);
      showStorageStatus(true);
      showToast('Layout saved to browser storage! It will persist across page reloads.', 'success');
    } catch (err) {
      showToast(`Failed to save: ${err.message}`, 'error');
    }
  }

  // Load layout from localStorage (called on init)
  function loadFromLocalStorage() {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) {
        const data = JSON.parse(saved);
        const validation = validateLayoutJSON(data);
        if (validation.valid) {
          return data;
        }
        console.warn('Saved layout invalid, ignoring:', validation.error);
      }
    } catch (err) {
      console.warn('Failed to load saved layout:', err);
    }
    return null;
  }

  // Clear saved layout from localStorage
  function clearLocalStorage() {
    if (!confirm('Clear saved layout from browser storage? This will revert to the default geometry.json on next page load.')) {
      return;
    }
    
    try {
      localStorage.removeItem(STORAGE_KEY);
      showStorageStatus(false);
      showToast('Saved layout cleared. Reload the page to use default geometry.', 'success');
    } catch (err) {
      showToast(`Failed to clear: ${err.message}`, 'error');
    }
  }

  // Show/hide storage status indicator
  function showStorageStatus(hasSaved) {
    const status = document.getElementById('storageStatus');
    const clearBtn = document.getElementById('clearStorage');
    
    if (status) {
      status.style.display = hasSaved ? 'flex' : 'none';
    }
    if (clearBtn) {
      clearBtn.style.display = hasSaved ? 'inline-block' : 'none';
    }
  }

  // Helper to show toast notifications
  function showToast(message, type = 'info') {
    const toast = document.getElementById('globalToast');
    if (toast) {
      toast.textContent = message;
      toast.className = 'toast show';
      if (type === 'error') {
        toast.style.background = '#dc3545';
      } else if (type === 'success') {
        toast.style.background = '#198754';
      } else {
        toast.style.background = '#333';
      }
      setTimeout(() => {
        toast.classList.remove('show');
        toast.style.background = '';
      }, 5000);
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
    if (!confirm('Reset all layout changes to original geometry.json? (This does not clear browser storage - use "Clear Saved" for that)')) return;

    if (editorState.originalGeometry) {
      window.GJSON = JSON.parse(JSON.stringify(editorState.originalGeometry));
      deselectRegion();
      checkCollisions();
      updateModifiedState();
      requestAnimationFrame(() => window.draw && window.draw(window.lastData || {}));
      showToast('Layout reset to original geometry.json', 'success');
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
  
  // Show/hide edit mode toggle based on editor enabled state
  function updateEditModeVisibility() {
    const toggle = document.getElementById('editModeToggle');
    if (toggle) {
      toggle.style.display = editorState.enabled ? 'block' : 'none';
    }
  }
  
  // Set the active edit mode
  function setEditMode(mode) {
    editorState.editMode = mode;
    
    // Update button states
    const regionsBtn = document.getElementById('modeRegions');
    const dividersBtn = document.getElementById('modeDividers');
    
    if (regionsBtn) {
      regionsBtn.classList.toggle('active', mode === 'regions');
    }
    if (dividersBtn) {
      dividersBtn.classList.toggle('active', mode === 'dividers');
    }
    
    // Deselect region when switching to dividers mode
    if (mode === 'dividers') {
      deselectRegion();
    }
    
    // Update status and redraw
    updateDividerStatus();
    if (typeof window.draw === 'function') {
      requestAnimationFrame(() => window.draw(window.lastData || {}));
    }
    
    console.log(`[Layout Editor] Mode switched to: ${mode}`);
  }
  
  // Update divider status display
  function updateDividerStatus() {
    const statusEl = document.getElementById('dividerStatus');
    if (!statusEl) return;
    
    const vDividers = findVerticalDividers();
    const hDividers = findHorizontalDividers();
    
    if (editorState.editMode === 'dividers') {
      if (vDividers.length === 0 && hDividers.length === 0) {
        statusEl.innerHTML = `
          <div class="divider-warning">
            ⚠️ No dividers detected!<br>
            <small>Regions need aligned edges. Try the Regions mode to adjust.</small>
          </div>`;
      } else {
        statusEl.innerHTML = `
          <div class="divider-info">
            Found: ${vDividers.length} vertical, ${hDividers.length} horizontal dividers<br>
            <small>Click and drag a divider line to resize adjacent regions</small>
          </div>`;
      }
    } else {
      statusEl.innerHTML = '';
    }
  }
  
  // Reset to normal display mode (exit labels-only mode)
  // This ensures the layout editor always shows the actual UI content
  function resetToNormalDisplayMode() {
    // Uncheck the "Label regions" and "Show geometry rects" checkboxes
    const labelsCheckbox = document.getElementById('showLabels');
    const rectsCheckbox = document.getElementById('showRects');
    
    if (labelsCheckbox && labelsCheckbox.checked) {
      labelsCheckbox.checked = false;
      // Dispatch change event to trigger the sim.js handler
      labelsCheckbox.dispatchEvent(new Event('change'));
    }
    
    if (rectsCheckbox && rectsCheckbox.checked) {
      rectsCheckbox.checked = false;
      rectsCheckbox.dispatchEvent(new Event('change'));
    }
  }

  // Draw editor overlays (selection, handles, etc.)
  function drawEditorOverlay(ctx) {
    if (!editorState.enabled) return;

    // Draw all divider lines subtly when editor is enabled
    drawAllDividers(ctx);

    // DIVIDER HIGHLIGHTS (draw first, underneath everything else)
    if (editorState.hoveredDivider || editorState.isDraggingDivider) {
      const divider = editorState.activeDivider || editorState.hoveredDivider;
      if (divider && window.GJSON && window.GJSON.canvas) {
        ctx.save();

        // Visual style: bright highlight when dragging, subtle when hovering
        const isDragging = editorState.isDraggingDivider;
        ctx.strokeStyle = isDragging ? '#f97316' : '#3b82f6';
        ctx.lineWidth = isDragging ? 4 : 3;
        ctx.setLineDash([]);

        if (divider.type === 'vertical') {
          // Draw vertical line
          const x = divider.position;
          ctx.beginPath();
          ctx.moveTo(x, 0);
          ctx.lineTo(x, window.GJSON.canvas.h);
          ctx.stroke();

          // Add glow effect
          ctx.shadowColor = isDragging ? 'rgba(249, 115, 22, 0.7)' : 'rgba(59, 130, 246, 0.5)';
          ctx.shadowBlur = isDragging ? 10 : 6;
          ctx.stroke();
          
          // Draw drag handle indicators at top and bottom
          drawDividerHandle(ctx, x, 0, 'vertical', isDragging);
          drawDividerHandle(ctx, x, window.GJSON.canvas.h, 'vertical', isDragging);
        } else {
          // Draw horizontal line
          const y = divider.position;
          ctx.beginPath();
          ctx.moveTo(0, y);
          ctx.lineTo(window.GJSON.canvas.w, y);
          ctx.stroke();

          // Add glow effect
          ctx.shadowColor = isDragging ? 'rgba(249, 115, 22, 0.7)' : 'rgba(59, 130, 246, 0.5)';
          ctx.shadowBlur = isDragging ? 10 : 6;
          ctx.stroke();
          
          // Draw drag handle indicators at left and right
          drawDividerHandle(ctx, 0, y, 'horizontal', isDragging);
          drawDividerHandle(ctx, window.GJSON.canvas.w, y, 'horizontal', isDragging);
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
  
  // Helper: Draw all dividers subtly when editor is enabled
  function drawAllDividers(ctx) {
    if (!window.GJSON || !window.GJSON.canvas) return;
    
    ctx.save();
    ctx.strokeStyle = 'rgba(59, 130, 246, 0.25)';
    ctx.lineWidth = 1;
    ctx.setLineDash([4, 4]);
    
    // Draw vertical dividers
    const vDividers = findVerticalDividers();
    for (const divider of vDividers) {
      ctx.beginPath();
      ctx.moveTo(divider.position, 0);
      ctx.lineTo(divider.position, window.GJSON.canvas.h);
      ctx.stroke();
    }
    
    // Draw horizontal dividers  
    const hDividers = findHorizontalDividers();
    for (const divider of hDividers) {
      ctx.beginPath();
      ctx.moveTo(0, divider.position);
      ctx.lineTo(window.GJSON.canvas.w, divider.position);
      ctx.stroke();
    }
    
    ctx.restore();
  }
  
  // Helper: Draw divider handle indicator at endpoints
  function drawDividerHandle(ctx, x, y, type, isDragging) {
    const size = 10;
    const color = isDragging ? '#f97316' : '#3b82f6';
    
    ctx.save();
    ctx.fillStyle = color;
    ctx.shadowColor = isDragging ? 'rgba(249, 115, 22, 0.5)' : 'rgba(59, 130, 246, 0.5)';
    ctx.shadowBlur = 4;
    
    if (type === 'vertical') {
      // Draw small grab handle at top/bottom
      ctx.beginPath();
      ctx.roundRect(x - size/2, y - 3, size, 6, 2);
      ctx.fill();
    } else {
      // Draw small grab handle at left/right
      ctx.beginPath();
      ctx.roundRect(x - 3, y - size/2, 6, size, 2);
      ctx.fill();
    }
    
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
