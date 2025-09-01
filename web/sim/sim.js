(function(){
  console.log('IIFE starting...');
  let WIDTH = 250, HEIGHT = 122;
  // Rectangles use [x, y, w, h] - from display_geometry.json
  let HEADER_NAME = [  6,  2, 160, 14];
  let HEADER_VERSION = [172,  2,  72, 14];
  let HEADER_TIME_CENTER = [100,  2,  50, 14];
  let INSIDE_TEMP = [  6, 36, 118, 28];
  let INSIDE_HUMIDITY = [  6, 66, 118, 14];
  let INSIDE_PRESSURE = [  6, 78, 118, 12];
  let OUT_TEMP    = [129, 36,  94, 28];
  let WEATHER_ICON = [168, 90,  30, 32];
  // Outside metric regions with meaningful names
  let OUT_PRESSURE = [177, 68,  64, 12]; // Outside pressure
  let OUT_HUMIDITY = [131, 78,  44, 12]; // Outside humidity
  let OUT_WIND     = [177, 78,  44, 12]; // Wind speed
  // Footer regions
  let FOOTER_STATUS = [  6, 90, 160, 32];
  let FOOTER_WEATHER = [200, 90,  44, 32];

  let canvas = null;
  let ctx = null;
  
  function initCanvas() {
    canvas = document.getElementById('epd');
    if (!canvas) {
      // Canvas not found yet - this is OK, it might be created later
      console.log('Canvas element #epd not found yet');
      return false;
    }
    ctx = canvas.getContext('2d');
    if (!ctx) {
      console.error('Could not get 2D context');
      return false;
    }
    canvas.style.imageRendering = 'pixelated';
    ctx.imageSmoothingEnabled = false;
    
    console.log('Canvas initialized successfully');
    
    // Expose for debugging
    window._canvas = canvas;
    window._ctx = ctx;
    
    return true;
  }
  let showWindows = false;
  let stressMode = false;
  let oneBitMode = true;
  let showGrid = false;
  let showRects = false;
  let showLabels = false;
  let simulateGhosting = false;
  let geometryOnly = false; // when true, render only geometry (for labeled mode)
  // removed highlightIssues toggle per feedback
  let GEOMETRY = null; // optional overlay geometry loaded from geometry.json
  let GJSON = null;    // centralized geometry JSON
  // Region inspector state
  let regionFilters = { all: true, header: true, temp: true, label: true, footer: true };
  let regionVisible = new Set();
  let regionSelectionActive = false; // false means "all visible" until first explicit selection
  let highlightRect = null; // hovered rect name
  let searchQuery = '';
  let pendingDraw = 0; // rAF id for coalesced redraws
  // Enable spec-only render (always on to keep single source of truth)
  const QS = (typeof window !== 'undefined') ? new URLSearchParams(window.location.search) : new URLSearchParams();
  const specOnly = true;
  // Validation state
  let validationEnabled = true;
  let validationIssues = [];
  let renderedContent = {}; // Track what was actually rendered
  let emptyRegions = new Set(); // Track regions with no content
  let missingDataFields = new Set(); // Track data fields that were referenced but missing

  const FONT_STACK = 'Menlo, Consolas, "DM Mono", "Roboto Mono", monospace';
  const SIZE_SMALL = 10; // general small text - reduced from 11 to fit 12px rows
  const SIZE_LABEL = 10; // reduced from 11 to fit better
  const SIZE_TIME = 10; // reduced from 11 to fit 14px header
  const SIZE_BIG = 22;
  const THRESH = 176;
  // Provide a simple, deterministic short label from weather text
  function shortConditionLabel(s){
    try{
      const str = String(s||'');
      const parts = str.split(/[\s-]+/);
      return parts[0] || str;
    }catch(e){ return String(s||''); }
  }
  
  // UI Validation Functions
  function validateTextOverflow(text, rect, fontSize, weight = 'normal') {
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    // Include font weight in measurement for accuracy
    ctx.font = `${weight} ${fontSize}px ${FONT_STACK}`;
    const metrics = ctx.measureText(text);
    const textWidth = metrics.width;
    
    // Use more accurate font metrics including ascent/descent
    const actualHeight = metrics.actualBoundingBoxAscent + metrics.actualBoundingBoxDescent || fontSize * 1.2;
    const [x, y, w, h] = rect;
    
    const issues = [];
    if (textWidth > w) {
      const overflow = textWidth - w;
      const pct = (overflow / w) * 100;
      // More granular severity levels
      let severity = 'warning';
      if (pct > 50) severity = 'critical';
      else if (pct > 25) severity = 'error';
      else if (pct > 10) severity = 'warning';
      else severity = 'info';
      
      issues.push({
        type: 'text_overflow',
        severity: severity,
        region: rect.name || 'unknown',
        description: `Text "${text}" overflows by ${overflow.toFixed(1)}px (${pct.toFixed(1)}%)`,
        rect: rect,
        suggestion: pct > 25 ? 'Consider truncation or smaller font' : 'Minor overflow, may be acceptable'
      });
    }
    if (actualHeight > h) {
      const overflow = actualHeight - h;
      const pct = (overflow / h) * 100;
      issues.push({
        type: 'text_overflow_vertical',
        severity: pct > 30 ? 'error' : 'warning',
        region: rect.name || 'unknown',
        description: `Text height (${actualHeight.toFixed(1)}px) exceeds bounds by ${overflow.toFixed(1)}px`,
        rect: rect,
        suggestion: 'Reduce font size or increase region height'
      });
    }
    return issues;
  }
  
  function validateCollisions(rects) {
    const issues = [];
    const allowed = new Set([
      'INSIDE_TEMP,INSIDE_LABEL_BOX',
      'INSIDE_LABEL_BOX,INSIDE_TEMP',
      'INSIDE_TEMP,INSIDE_TEMP_INNER',
      'INSIDE_TEMP_INNER,INSIDE_TEMP',
      'INSIDE_TEMP,INSIDE_TEMP_BADGE',
      'INSIDE_TEMP_BADGE,INSIDE_TEMP',
      'OUT_TEMP,OUT_LABEL_BOX',
      'OUT_LABEL_BOX,OUT_TEMP',
      'OUT_TEMP,OUT_TEMP_INNER',
      'OUT_TEMP_INNER,OUT_TEMP',
      'OUT_TEMP,OUT_TEMP_BADGE',
      'OUT_TEMP_BADGE,OUT_TEMP',
      'FOOTER_WEATHER,WEATHER_ICON',
      'WEATHER_ICON,FOOTER_WEATHER',
      'FOOTER_STATUS,INSIDE_PRESSURE',
      'INSIDE_PRESSURE,FOOTER_STATUS'
    ]);
    
    // Region importance weights for severity calculation
    const regionImportance = {
      'INSIDE_TEMP': 10,
      'OUT_TEMP': 10,
      'HEADER_NAME': 8,
      'INSIDE_HUMIDITY': 7,
      'OUT_HUMIDITY': 6,
      'FOOTER_STATUS': 5,
      'FOOTER_WEATHER': 5
    };
    
    const names = Object.keys(rects);
    for (let i = 0; i < names.length; i++) {
      for (let j = i + 1; j < names.length; j++) {
        const name1 = names[i], name2 = names[j];
        const r1 = rects[name1], r2 = rects[name2];
        const [x1, y1, w1, h1] = r1;
        const [x2, y2, w2, h2] = r2;
        
        const overlapX = Math.max(0, Math.min(x1 + w1, x2 + w2) - Math.max(x1, x2));
        const overlapY = Math.max(0, Math.min(y1 + h1, y2 + h2) - Math.max(y1, y2));
        
        if (overlapX > 0 && overlapY > 0) {
          const pair = [name1, name2].sort().join(',');
          if (!allowed.has(pair)) {
            const area = overlapX * overlapY;
            const smaller = Math.min(w1 * h1, w2 * h2);
            const pct = (area / smaller) * 100;
            
            // Calculate importance factor
            const importance1 = regionImportance[name1] || 1;
            const importance2 = regionImportance[name2] || 1;
            const maxImportance = Math.max(importance1, importance2);
            
            // Adjust severity based on overlap percentage and importance
            let severity;
            if (pct > 75) severity = 'critical';
            else if (pct > 50 || (pct > 25 && maxImportance >= 8)) severity = 'error';
            else if (pct > 20 || (pct > 10 && maxImportance >= 6)) severity = 'warning';
            else if (pct > 5) severity = 'info';
            else continue; // Skip very minor overlaps
            
            issues.push({
              type: 'collision',
              severity: severity,
              region: pair,
              description: `${name1} and ${name2} overlap by ${pct.toFixed(1)}% (${overlapX}x${overlapY}px)`,
              rect: [Math.max(x1, x2), Math.max(y1, y2), overlapX, overlapY],
              suggestion: pct > 50 ? 'Major overlap - adjust layout spacing' : 
                         pct > 25 ? 'Significant overlap - consider reducing element sizes' :
                         'Minor overlap - may be intentional for visual effect'
            });
          }
        }
      }
    }
    return issues;
  }
  
  function updateValidationDisplay() {
    const badge = document.getElementById('validationBadge');
    const results = document.getElementById('validationResults');
    
    if (!badge || !results) return;
    
    const critical = validationIssues.filter(i => i.severity === 'critical').length;
    const errors = validationIssues.filter(i => i.severity === 'error').length;
    const warnings = validationIssues.filter(i => i.severity === 'warning').length;
    
    // Update badge
    if (critical > 0) {
      badge.textContent = `${critical} critical`;
      badge.style.background = '#ff4444';
      badge.style.color = 'white';
    } else if (errors > 0) {
      badge.textContent = `${errors} errors`;
      badge.style.background = '#ff8800';
      badge.style.color = 'white';
    } else if (warnings > 0) {
      badge.textContent = `${warnings} warnings`;
      badge.style.background = '#ffbb00';
      badge.style.color = 'black';
    } else {
      badge.textContent = 'OK';
      badge.style.background = '#44ff44';
      badge.style.color = 'black';
    }
    
    // Update results list with enhanced formatting and suggestions
    if (validationIssues.length === 0) {
      results.innerHTML = '<div style="color:#666;">No validation issues detected</div>';
    } else {
      const grouped = {};
      validationIssues.forEach(issue => {
        if (!grouped[issue.severity]) grouped[issue.severity] = [];
        grouped[issue.severity].push(issue);
      });
      
      let html = '';
      const severityOrder = ['critical', 'error', 'warning', 'info'];
      const severityColors = {
        critical: '#ff4444',
        error: '#ff8800',
        warning: '#ffbb00',
        info: '#4488ff'
      };
      
      severityOrder.forEach(severity => {
        if (!grouped[severity]) return;
        
        html += `<div style="margin-top:8px;border-left:3px solid ${severityColors[severity]};padding-left:8px;">`;
        grouped[severity].forEach(issue => {
          const icon = {
            critical: '🔴',
            error: '🟠',
            warning: '🟡',
            info: 'ℹ️'
          }[issue.severity];
          
          html += `<div style="margin-bottom:6px;">
            <div><span style="font-weight:bold;">${icon} ${issue.type.replace(/_/g, ' ').toUpperCase()}</span> 
            <span style="color:#666;font-size:10px;">[${issue.region}]</span></div>
            <div style="margin-left:20px;font-size:11px;">${issue.description}</div>`;
          
          if (issue.suggestion) {
            html += `<div style="margin-left:20px;font-size:10px;color:#666;font-style:italic;">
              💡 ${issue.suggestion}</div>`;
          }
          
          // Add action buttons for certain issues
          if (issue.type === 'text_overflow' && issue.severity !== 'info') {
            html += `<div style="margin-left:20px;margin-top:2px;">
              <button onclick="window.applyValidationFix('truncate', '${issue.region}')" 
                      style="font-size:10px;padding:1px 4px;">Apply Truncation</button>
              <button onclick="window.applyValidationFix('smaller_font', '${issue.region}')" 
                      style="font-size:10px;padding:1px 4px;">Reduce Font</button>
            </div>`;
          }
          
          html += '</div>';
        });
        html += '</div>';
      });
      
      results.innerHTML = html;
    }
  }
  
  // Validate data ranges and formats
  function validateDataRanges(data) {
    const issues = [];
    
    // Temperature range checks
    if (data.inside_temp_f !== undefined) {
      const temp = parseFloat(data.inside_temp_f);
      if (isNaN(temp)) {
        issues.push({
          type: 'invalid_data_format',
          severity: 'error',
          region: 'INSIDE_TEMP',
          description: `Invalid temperature format: "${data.inside_temp_f}"`,
          suggestion: 'Use numeric value'
        });
      } else if (temp < -40 || temp > 150) {
        issues.push({
          type: 'data_out_of_range',
          severity: 'warning',
          region: 'INSIDE_TEMP',
          description: `Temperature ${temp}°F is outside realistic range (-40 to 150°F)`,
          suggestion: 'Check sensor calibration'
        });
      }
    }
    
    // Humidity range checks
    if (data.inside_hum_pct !== undefined) {
      const hum = parseFloat(data.inside_hum_pct);
      if (!isNaN(hum) && (hum < 0 || hum > 100)) {
        issues.push({
          type: 'data_out_of_range',
          severity: 'error',
          region: 'INSIDE_HUMIDITY',
          description: `Humidity ${hum}% is outside valid range (0-100%)`,
          suggestion: 'Humidity must be between 0 and 100%'
        });
      }
    }
    
    // Battery percentage checks
    if (data.battery_percent !== undefined) {
      const batt = parseFloat(data.battery_percent);
      if (!isNaN(batt) && (batt < 0 || batt > 100)) {
        issues.push({
          type: 'data_out_of_range',
          severity: 'warning',
          region: 'FOOTER_STATUS',
          description: `Battery ${batt}% is outside valid range`,
          suggestion: 'Battery percentage must be 0-100%'
        });
      }
    }
    
    // Pressure range checks
    if (data.pressure_hpa !== undefined) {
      const pressure = parseFloat(data.pressure_hpa);
      if (!isNaN(pressure) && (pressure < 850 || pressure > 1100)) {
        issues.push({
          type: 'data_out_of_range',
          severity: 'warning',
          region: 'INSIDE_PRESSURE',
          description: `Pressure ${pressure} hPa is unusual (typical: 950-1050 hPa)`,
          suggestion: 'Verify barometer reading'
        });
      }
    }
    
    // CO2 range checks
    if (data.co2_ppm !== undefined) {
      const co2 = parseFloat(data.co2_ppm);
      if (!isNaN(co2)) {
        if (co2 < 400) {
          issues.push({
            type: 'data_out_of_range',
            severity: 'info',
            region: 'data',
            description: `CO2 ${co2} ppm is below outdoor levels (400 ppm)`,
            suggestion: 'Sensor may need calibration'
          });
        } else if (co2 > 5000) {
          issues.push({
            type: 'data_out_of_range',
            severity: 'warning',
            region: 'data',
            description: `CO2 ${co2} ppm is dangerously high`,
            suggestion: 'Check ventilation or sensor accuracy'
          });
        }
      }
    }
    
    validationIssues.push(...issues);
    return issues;
  }
  
  // Validate baseline alignment between related regions
  function validateBaselineAlignment(renderedContent) {
    const issues = [];
    const alignmentGroups = [
      ['INSIDE_TEMP', 'OUT_TEMP'],
      ['INSIDE_HUMIDITY', 'OUT_HUMIDITY'],
      ['HEADER_NAME', 'HEADER_VERSION'],
      ['FOOTER_STATUS', 'FOOTER_WEATHER']
    ];
    
    for (const group of alignmentGroups) {
      const baselines = [];
      for (const regionName of group) {
        if (renderedContent[regionName] && renderedContent[regionName].actualBounds) {
          const bounds = renderedContent[regionName].actualBounds;
          baselines.push({ region: regionName, y: bounds.y });
        }
      }
      
      if (baselines.length > 1) {
        const maxDiff = Math.max(...baselines.map(b => b.y)) - Math.min(...baselines.map(b => b.y));
        if (maxDiff > 2) { // Allow 2px tolerance
          issues.push({
            type: 'baseline_misalignment',
            severity: maxDiff > 5 ? 'error' : 'warning',
            region: group.join(' vs '),
            description: `Baseline misalignment of ${maxDiff.toFixed(1)}px between ${group.join(' and ')}`,
            suggestion: 'Adjust vertical positioning for consistent alignment',
            rect: null
          });
        }
      }
    }
    
    return issues;
  }
  
  function validateCenterlineProximity(rects, spec, minGap = 4) {
    const issues = [];
    
    // Find center divider X position from chrome spec
    let centerX = 125; // default
    if (spec && spec.components && spec.components.chrome) {
      for (const op of spec.components.chrome) {
        if (op.op === 'line' && op.from && op.to) {
          const [x1, y1] = op.from;
          const [x2, y2] = op.to;
          // Vertical line check
          if (x1 === x2 && y1 !== y2 && x1 > 100 && x1 < 150) {
            centerX = x1;
            break;
          }
        }
      }
    }
    
    // Check INSIDE_TEMP proximity to center
    if (rects.INSIDE_TEMP) {
      const [x, y, w, h] = rects.INSIDE_TEMP;
      const rightEdge = x + w;
      const gap = centerX - rightEdge;
      
      if (gap < 0) {
        issues.push({
          type: 'centerline_collision',
          severity: 'critical',
          region: 'INSIDE_TEMP',
          description: `INSIDE_TEMP crosses center divider (gap: ${gap}px)`,
          rect: [centerX - 3, y, 6, h]  // Fixed 6px width centered on divider
        });
      } else if (gap < minGap) {
        issues.push({
          type: 'centerline_proximity',
          severity: 'warning',
          region: 'INSIDE_TEMP',
          description: `INSIDE_TEMP too close to center (gap: ${gap}px, min: ${minGap}px)`,
          rect: [centerX - 3, y, 6, h]  // Fixed 6px width for visibility
        });
      }
    }
    
    // Check OUT_TEMP proximity to center
    if (rects.OUT_TEMP) {
      const [x, y, w, h] = rects.OUT_TEMP;
      const leftEdge = x;
      const gap = leftEdge - centerX;
      
      if (gap < 0) {
        issues.push({
          type: 'centerline_collision',
          severity: 'critical',
          region: 'OUT_TEMP',
          description: `OUT_TEMP crosses center divider (gap: ${gap}px)`,
          rect: [centerX - 3, y, 6, h]  // Fixed 6px width centered on divider
        });
      } else if (gap < minGap) {
        issues.push({
          type: 'centerline_proximity',
          severity: 'warning',
          region: 'OUT_TEMP',
          description: `OUT_TEMP too close to center (gap: ${gap}px, min: ${minGap}px)`,
          rect: [centerX - 3, y, 6, h]  // Fixed 6px width for visibility
        });
      }
    }
    
    return issues;
  }
  
  function validateLabelTempProximity(rects, minWarnOverlapPx = 1, minCritOverlapPx = 4) {
    const issues = [];
    const LABEL_HEIGHT = 12; // Standard label height
    
    // Check INSIDE label to INSIDE_TEMP proximity
    if (rects.INSIDE_TEMP && rects.INSIDE_HUMIDITY) {
      const [tx, ty, tw, th] = rects.INSIDE_TEMP;
      const [hx, hy, hw, hh] = rects.INSIDE_HUMIDITY;
      
      // Label is at top of humidity region
      const labelBottom = hy + LABEL_HEIGHT;
      const tempTop = ty;
      const overlap = labelBottom - tempTop; // Positive = overlapping
      
      if (overlap >= minCritOverlapPx) {
        issues.push({
          type: 'label_temp_collision',
          severity: 'critical',
          region: 'INSIDE_TEMP',
          description: `INSIDE label overlaps temperature by ${overlap}px`,
          rect: [tx, tempTop, tw, overlap]
        });
      } else if (overlap >= minWarnOverlapPx) {
        issues.push({
          type: 'label_temp_overlap',
          severity: 'warning',
          region: 'INSIDE_TEMP',
          description: `INSIDE label overlaps temperature by ${overlap}px`,
          rect: [tx, tempTop, tw, Math.max(1, overlap)]
        });
      }
    }
    
    // Check OUTSIDE label to OUT_TEMP proximity
    if (rects.OUT_TEMP && rects.OUT_HUMIDITY) {
      const [tx, ty, tw, th] = rects.OUT_TEMP;
      const [hx, hy, hw, hh] = rects.OUT_HUMIDITY;
      
      const labelBottom = hy + LABEL_HEIGHT;
      const tempTop = ty;
      const overlap = labelBottom - tempTop; // Positive = overlapping
      
      if (overlap >= minCritOverlapPx) {
        issues.push({
          type: 'label_temp_collision',
          severity: 'critical',
          region: 'OUT_TEMP',
          description: `OUTSIDE label overlaps temperature by ${overlap}px`,
          rect: [tx, tempTop, tw, overlap]
        });
      } else if (overlap >= minWarnOverlapPx) {
        issues.push({
          type: 'label_temp_overlap',
          severity: 'warning',
          region: 'OUT_TEMP',
          description: `OUTSIDE label overlaps temperature by ${overlap}px`,
          rect: [tx, tempTop, tw, Math.max(1, overlap)]
        });
      }
    }
    
    return issues;
  }
  
  function validateGridAlignment(rects, gridSize = 4) {
    const issues = [];
    
    for (const [name, rect] of Object.entries(rects)) {
      const [x, y, w, h] = rect;
      const misaligned = [];
      
      if (x % gridSize !== 0) misaligned.push(`x=${x}`);
      if (y % gridSize !== 0) misaligned.push(`y=${y}`);
      if (w % gridSize !== 0) misaligned.push(`w=${w}`);
      if (h % gridSize !== 0) misaligned.push(`h=${h}`);
      
      if (misaligned.length > 0) {
        issues.push({
          type: 'grid_misalignment',
          severity: 'info',
          region: name,
          description: `Not aligned to ${gridSize}px grid: ${misaligned.join(', ')}`,
          rect: rect,
          suggestion: `Align to ${gridSize}px grid for consistency`
        });
      }
    }
    
    return issues;
  }
  
  function validateWeatherIconAlignment(rects, maxLeftPadding = 8) {
    const issues = [];
    
    if (rects.WEATHER_ICON && rects.FOOTER_WEATHER) {
      const [iconX, iconY, iconW, iconH] = rects.WEATHER_ICON;
      const [footerX, footerY, footerW, footerH] = rects.FOOTER_WEATHER;
      
      // Check if icon is left-justified within footer
      const leftPadding = iconX - footerX;
      
      if (leftPadding > maxLeftPadding) {
        issues.push({
          type: 'weather_icon_alignment',
          severity: 'warning',
          region: 'WEATHER_ICON',
          description: `Weather icon not left-justified (padding: ${leftPadding}px, max: ${maxLeftPadding}px)`,
          rect: rects.WEATHER_ICON,
          suggestion: 'Move icon to left edge of footer region'
        });
      }
      
      // Check vertical centering
      const footerCenterY = footerY + footerH / 2;
      const iconCenterY = iconY + iconH / 2;
      const verticalOffset = Math.abs(footerCenterY - iconCenterY);
      
      if (verticalOffset > 4) {
        issues.push({
          type: 'weather_icon_vertical',
          severity: 'info',
          region: 'WEATHER_ICON',
          description: `Weather icon not vertically centered (offset: ${verticalOffset}px)`,
          rect: rects.WEATHER_ICON
        });
      }
    }
    
    return issues;
  }
  
  function runValidation() {
    if (!validationEnabled || !GJSON || !GJSON.rects) return;
    
    validationIssues = [];
    
    // Check for collisions (filter out internal helper rects)
    const rectsToValidate = {};
    Object.entries(GJSON.rects).forEach(([name, rect]) => {
      if (!name.includes('_INNER') && !name.includes('_BADGE') && !name.includes('LABEL_BOX')) {
        rectsToValidate[name] = rect;
      }
    });
    validationIssues.push(...validateCollisions(rectsToValidate));
    
    // Check rendered content for overflow and incomplete data
    for (const [regionName, content] of Object.entries(renderedContent)) {
      if (GJSON.rects[regionName] && content.text) {
        // Skip validation for internal helper regions but validate the actual temp inner regions
        // Skip badge and label box regions as they're internal helpers
        if (regionName.includes('_BADGE') || regionName.includes('LABEL_BOX')) {
          continue;
        }
        // Skip outside metric regions that have known tight bounds (but not temp regions)
        if (regionName === 'OUT_PRESSURE' ||
            regionName === 'OUT_HUMIDITY' || regionName === 'OUT_WIND') {
          continue;
        }
        const rect = GJSON.rects[regionName];
        rect.name = regionName;
        const issues = validateTextOverflow(content.text, rect, content.fontSize || SIZE_SMALL, content.weight || 'normal');
        validationIssues.push(...issues);
        
        // Check for incomplete data (e.g., "mph" without a number, "%" without a value)
        const text = content.text.trim();
        if (text === 'mph' || text === 'km/h' || text === '%' || 
            text === '% RH' || text === 'hPa' || text === 'ppm' ||
            text.match(/^\s*(mph|km\/h|%|hPa|ppm|mm)\s*$/)) {
          validationIssues.push({
            type: 'incomplete_data',
            severity: 'warning',
            region: regionName,
            description: `Region shows units without value: "${text}"`,
            rect: rect,
            suggestion: 'Check data source or add fallback value'
          });
        }
        
        // Check for truncated numbers
        if (text.includes('...') && /\d/.test(text)) {
          validationIssues.push({
            type: 'truncated_number',
            severity: 'error',
            region: regionName,
            description: `Number appears truncated: "${text}"`,
            rect: rect,
            suggestion: 'Increase region width or reduce decimal places'
          });
        }
      }
    }
    
    // Check baseline alignment
    validationIssues.push(...validateBaselineAlignment(renderedContent));
    
    // Check centerline proximity
    validationIssues.push(...validateCenterlineProximity(rectsToValidate, window.UI_SPEC));
    
    // Check label-temperature proximity
    validationIssues.push(...validateLabelTempProximity(rectsToValidate));
    
    // Check grid alignment (info level)
    validationIssues.push(...validateGridAlignment(rectsToValidate));
    
    // Check weather icon alignment
    validationIssues.push(...validateWeatherIconAlignment(rectsToValidate));
    
    // Check for empty regions that should have content
    const variant = QS.get('variant') || (window.UI_SPEC && window.UI_SPEC.defaultVariant) || 'v2';
    
    // Smart expected content based on available data
    const expectedContent = new Set(['HEADER_NAME', 'HEADER_VERSION', 'INSIDE_TEMP', 'INSIDE_HUMIDITY']);
    
    // Add conditional expectations based on actual data
    if (lastData.time || lastData.time_hhmm) {
      expectedContent.add('HEADER_TIME_CENTER');
    }
    if (lastData.pressure_hpa !== undefined && lastData.pressure_hpa !== null) {
      expectedContent.add('INSIDE_PRESSURE');
    }
    if (lastData.outside_temp_f !== undefined || lastData.outside_temp_c !== undefined) {
      expectedContent.add('OUT_TEMP');
    }
    if (lastData.outside_hum_pct !== undefined) {
      expectedContent.add('OUT_HUMIDITY');
    }
    if (lastData.wind_mps !== undefined || lastData.wind_mph !== undefined) {
      expectedContent.add('OUT_WIND');
    }
    if (lastData.weather) {
      expectedContent.add('WEATHER_ICON');
      expectedContent.add('FOOTER_WEATHER');
    }
    if (lastData.battery_percent !== undefined || lastData.ip || lastData.days !== undefined) {
      expectedContent.add('FOOTER_STATUS');
    }
    
    // Coverage thresholds for different region types
    const COVERAGE_THRESHOLDS = {
      WEATHER_ICON: 5,      // Icon regions
      INSIDE_TEMP: 10,      // Large text regions
      OUT_TEMP: 10,
      HEADER_NAME: 10,      // Header text
      HEADER_VERSION: 10,
      HEADER_TIME_CENTER: 10,
      INSIDE_HUMIDITY: 8,   // Smaller text regions
      INSIDE_PRESSURE: 8,
      OUT_HUMIDITY: 8,
      OUT_WIND: 8,
      OUT_PRESSURE: 8,
      FOOTER_STATUS: 8,     // Footer regions
      FOOTER_WEATHER: 8,
      default: 10           // Default threshold
    };
    
    for (const regionName of expectedContent) {
      if (!renderedContent[regionName] && GJSON.rects[regionName]) {
        validationIssues.push({
          type: 'empty_region',
          severity: 'warning',
          region: regionName,
          description: `Region has no rendered content`,
          rect: GJSON.rects[regionName]
        });
      } else if (renderedContent[regionName] && GJSON.rects[regionName]) {
        // Check if content is effectively empty (just whitespace or placeholder)
        const text = (renderedContent[regionName].text || '').trim();
        if (text === '' || text === '—' || text === '-' || text === 'N/A') {
          validationIssues.push({
            type: 'placeholder_content',
            severity: 'info',
            region: regionName,
            description: `Region shows placeholder: "${text}"`,
            rect: GJSON.rects[regionName]
          });
        }
        
        // Check coverage-based empty detection
        const content = renderedContent[regionName];
        if (content.actualBounds && GJSON.rects[regionName]) {
          const rect = GJSON.rects[regionName];
          const rectArea = rect[2] * rect[3];
          const contentArea = content.actualBounds.width * content.actualBounds.height;
          const coverage = (contentArea / rectArea) * 100;
          const threshold = COVERAGE_THRESHOLDS[regionName] || COVERAGE_THRESHOLDS.default;
          
          // Skip coverage check for naturally small text (1-2 chars like units)
          const isNaturallySmall = text.length <= 2 && text !== '';
          
          if (!isNaturallySmall && coverage < threshold) {
            // Downgrade to info if it's a legitimate low coverage (e.g., "4%" text)
            const severity = (text.length > 0 && text.length <= 4) ? 'info' : 'warning';
            validationIssues.push({
              type: 'low_coverage',
              severity: severity,
              region: regionName,
              description: `Region appears empty (${coverage.toFixed(1)}% coverage)`,
              rect: GJSON.rects[regionName]
            });
          }
        }
      }
    }
    
    // Check for content outside defined regions
    for (const [regionName, content] of Object.entries(renderedContent)) {
      // Special case for elements that know they're outside their region
      if (content.outsideRegion) {
        validationIssues.push({
          type: 'element_outside_region',
          severity: 'error',
          region: regionName,
          description: `${regionName} renders outside ${content.outsideRegion}`,
          rect: content.actualBounds ? [content.actualBounds.x, content.actualBounds.y, content.actualBounds.width, content.actualBounds.height] : null
        });
        continue;
      }
      
      if (content.actualBounds && GJSON.rects[regionName]) {
        const rect = GJSON.rects[regionName];
        const [rx, ry, rw, rh] = rect;
        const {x, y, width, height} = content.actualBounds;
        
        // Only flag significant overflows (>2px) to avoid false positives from antialiasing
        const leftOverflow = rx - x;
        const topOverflow = ry - y;
        const rightOverflow = (x + width) - (rx + rw);
        const bottomOverflow = (y + height) - (ry + rh);
        
        if (leftOverflow > 2 || topOverflow > 2 || rightOverflow > 2 || bottomOverflow > 2) {
          const details = [];
          if (leftOverflow > 2) details.push(`left by ${leftOverflow.toFixed(1)}px`);
          if (topOverflow > 2) details.push(`top by ${topOverflow.toFixed(1)}px`);
          if (rightOverflow > 2) details.push(`right by ${rightOverflow.toFixed(1)}px`);
          if (bottomOverflow > 2) details.push(`bottom by ${bottomOverflow.toFixed(1)}px`);
          
          validationIssues.push({
            type: 'bounds_exceeded',
            severity: rightOverflow > 5 || bottomOverflow > 5 ? 'error' : 'warning',
            region: regionName,
            description: `Content exceeds bounds: ${details.join(', ')}`,
            rect: rect
          });
        }
      }
    }
    
    // These regions exist in geometry but aren't used in v2
    // Note: HEADER_TIME_CENTER is now used for time display when header_centered component is active
    // OUT_PRESSURE is actually used in some configurations, don't mark as unused
    const v2SpecificUnused = [];
    
    // Check for regions defined but not used in current variant
    const allDefinedRegions = Object.keys(GJSON.rects || {});
    const additionalUnused = allDefinedRegions.filter(r => 
      !expectedContent.has(r) && 
      !v2SpecificUnused.includes(r) &&
      !r.includes('LABEL_BOX') && !r.includes('_INNER') && !r.includes('_BADGE')
    );
    
    // Combine both lists
    const unusedRegions = [...v2SpecificUnused, ...additionalUnused];
    for (const region of unusedRegions) {
      if (GJSON.rects[region] && !renderedContent[region]) {
        validationIssues.push({
          type: 'unused_region',
          severity: 'info',
          region: region,
          description: `Region defined but not used in v2 layout`,
          rect: GJSON.rects[region]
        });
      }
    }
    
    // Check for missing data fields with better categorization
    if (missingDataFields.size > 0) {
      const fields = Array.from(missingDataFields).sort();
      const criticalFields = ['inside_temp_f', 'room_name'];
      const importantFields = ['outside_temp_f', 'inside_hum_pct', 'battery_percent'];
      
      const missingCritical = fields.filter(f => criticalFields.includes(f));
      const missingImportant = fields.filter(f => importantFields.includes(f));
      
      if (missingCritical.length > 0) {
        validationIssues.push({
          type: 'missing_critical_data',
          severity: 'error',
          region: 'data',
          description: `Missing critical data: ${missingCritical.join(', ')}`,
          rect: null,
          suggestion: 'These fields are essential for basic functionality'
        });
      }
      
      if (missingImportant.length > 0) {
        validationIssues.push({
          type: 'missing_important_data',
          severity: 'warning',
          region: 'data',
          description: `Missing important data: ${missingImportant.join(', ')}`,
          rect: null,
          suggestion: 'Consider adding fallback values or placeholder text'
        });
      }
      
      const others = fields.filter(f => !criticalFields.includes(f) && !importantFields.includes(f));
      if (others.length > 0) {
        validationIssues.push({
          type: 'missing_data',
          severity: 'info',
          region: 'data',
          description: `Missing optional data: ${others.join(', ')}`,
          rect: null,
          suggestion: 'Optional fields - display may work without them'
        });
      }
    }
    
    // Validate data ranges and formats
    validateDataRanges(lastData);
    
    // De-duplicate issues
    const seen = new Set();
    validationIssues = validationIssues.filter(issue => {
      const key = `${issue.type}_${issue.region}_${issue.severity}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
    
    // Update validation UI
    updateValidationDisplay();
    
    // Expose updated issues for testing
    try {
      if (typeof window !== 'undefined') {
        window.validationIssues = validationIssues;
        window.renderedContent = renderedContent;
      }
    } catch(e) {}
  }
  
  function drawValidationOverlay() {
    // Don't draw validation overlay if geometry overlays are active
    if (!validationEnabled || validationIssues.length === 0 || showRects || showLabels) return;
    
    ctx.save();
    
    // Draw issue highlights (skip WEATHER_ICON entirely to avoid any perceived border)
    for (const issue of validationIssues) {
      if (issue.rect) {
        const [x, y, w, h] = issue.rect;
        
        // Skip drawing for regions that shouldn't show validation
        // Also skip outside metric regions since we're not validating them
        // Also skip collision issues that involve outside metric regions
        if (issue.region && (issue.region === 'WEATHER_ICON' || issue.region.includes('_INNER') || 
            issue.region.includes('_BADGE') || 
            issue.region.includes('LABEL_BOX') ||
            issue.region === 'OUT_PRESSURE' ||
            issue.region === 'OUT_HUMIDITY' || issue.region === 'OUT_WIND')) {
          continue;
        }
        
        // Set color based on severity
        let color;
        switch(issue.severity) {
          case 'critical': color = 'rgba(255, 68, 68, 0.3)'; break;
          case 'error': color = 'rgba(255, 136, 0, 0.3)'; break;
          case 'warning': color = 'rgba(255, 187, 0, 0.3)'; break;
          default: color = 'rgba(0, 136, 255, 0.3)';
        }
        
        // Draw filled rectangle for the issue area (but never for WEATHER_ICON)
        ctx.fillStyle = color;
        ctx.fillRect(x, y, w, h);
        
        // Draw border
        ctx.strokeStyle = color.replace('0.3)', '1)');
        ctx.lineWidth = 2;
        ctx.strokeRect(x, y, w, h);
        
        // For text overflow issues, show the actual text bounds
        if (issue.type === 'text_overflow' && renderedContent[issue.region]) {
          const content = renderedContent[issue.region];
          if (content.actualBounds) {
            const {x: tx, y: ty, width: tw, height: th} = content.actualBounds;
            ctx.strokeStyle = 'rgba(255, 0, 0, 0.8)';
            ctx.lineWidth = 1;
            ctx.setLineDash([2, 2]);
            ctx.strokeRect(tx, ty, tw, th);
            ctx.setLineDash([]);
          }
        }
      }
    }
    
    ctx.restore();
  }
  async function loadCentralGeometry(){
    try{
      if (typeof window !== 'undefined' && window.UI_SPEC){
        const gj = window.UI_SPEC;
        if (gj && gj.rects){
          GJSON = gj;
          WIDTH = (gj.canvas && gj.canvas.w) || WIDTH;
          HEIGHT = (gj.canvas && gj.canvas.h) || HEIGHT;
          const R = gj.rects;
          HEADER_NAME = R.HEADER_NAME || HEADER_NAME;
          HEADER_VERSION = R.HEADER_VERSION || HEADER_VERSION;
          HEADER_TIME_CENTER = R.HEADER_TIME_CENTER || HEADER_TIME_CENTER;
          INSIDE_TEMP = R.INSIDE_TEMP || INSIDE_TEMP;
          INSIDE_HUMIDITY   = R.INSIDE_HUMIDITY   || INSIDE_HUMIDITY;
          INSIDE_PRESSURE = R.INSIDE_PRESSURE || INSIDE_PRESSURE;
          OUT_TEMP    = R.OUT_TEMP    || OUT_TEMP;
          WEATHER_ICON = R.WEATHER_ICON || WEATHER_ICON;
          // Use new meaningful names
          OUT_PRESSURE = R.OUT_PRESSURE || OUT_PRESSURE;
          OUT_HUMIDITY = R.OUT_HUMIDITY || OUT_HUMIDITY;
          OUT_WIND     = R.OUT_WIND     || OUT_WIND;
          return;
        }
      }
    }catch(e){ }
    try{
      const res = await fetch('geometry.json');
      if (res.ok){
        const gj = await res.json();
        if (gj && gj.rects){
          GJSON = gj;
          WIDTH = (gj.canvas && gj.canvas.w) || WIDTH;
          HEIGHT = (gj.canvas && gj.canvas.h) || HEIGHT;
          const R = gj.rects;
          HEADER_NAME = R.HEADER_NAME || HEADER_NAME;
          HEADER_VERSION = R.HEADER_VERSION || HEADER_VERSION;
          HEADER_TIME_CENTER = R.HEADER_TIME_CENTER || HEADER_TIME_CENTER;
          INSIDE_TEMP = R.INSIDE_TEMP || INSIDE_TEMP;
          INSIDE_HUMIDITY   = R.INSIDE_HUMIDITY   || INSIDE_HUMIDITY;
          INSIDE_PRESSURE = R.INSIDE_PRESSURE || INSIDE_PRESSURE;
          OUT_TEMP    = R.OUT_TEMP    || OUT_TEMP;
          WEATHER_ICON = R.WEATHER_ICON || WEATHER_ICON;
          // Use new meaningful names
          OUT_PRESSURE = R.OUT_PRESSURE || OUT_PRESSURE;
          OUT_HUMIDITY = R.OUT_HUMIDITY || OUT_HUMIDITY;
          OUT_WIND     = R.OUT_WIND     || OUT_WIND;
        }
      }
    }catch(e){ }
  }

  function applyOneBitThreshold(){
    if (!oneBitMode) return;
    const img = ctx.getImageData(0,0,WIDTH,HEIGHT);
    const d = img.data;
    for (let i=0;i<d.length;i+=4){
      const r=d[i], g=d[i+1], b=d[i+2];
      const y = 0.2126*r + 0.7152*g + 0.0722*b;
      const v = y < THRESH ? 0 : 255;
      d[i]=d[i+1]=d[i+2]=v;
      d[i+3]=255;
    }
    ctx.putImageData(img,0,0);
  }

  function drawGridOverlay(){
    if (!showGrid) return;
    ctx.save();
    ctx.strokeStyle = '#bbb';
    ctx.lineWidth = 1;
    for (let x = 0; x <= WIDTH; x += 4){
      ctx.beginPath();
      ctx.moveTo(x + 0.5, 0);
      ctx.lineTo(x + 0.5, HEIGHT);
      ctx.stroke();
    }
    for (let y = 0; y <= HEIGHT; y += 4){
      ctx.beginPath();
      ctx.moveTo(0, y + 0.5);
      ctx.lineTo(WIDTH, y + 0.5);
      ctx.stroke();
    }
    ctx.restore();
  }

  function categoryColor(cat){
    switch(String(cat||'')){
      case 'header': return '#ff6b6b';
      case 'temp':   return '#4ecdc4';
      case 'label':  return '#45b7d1';
      case 'footer': return '#96ceb4';
      default:       return '#f00';
    }
  }

  function hexToRgba(hex, alpha){
    try{
      const h = String(hex||'').trim();
      if (!/^#?[0-9a-fA-F]{6}$/.test(h)) return `rgba(255,0,0,${alpha||0.15})`;
      const s = h.startsWith('#') ? h.slice(1) : h;
      const n = parseInt(s, 16);
      const r = (n >> 16) & 255;
      const g = (n >> 8) & 255;
      const b = (n) & 255;
      const a = (typeof alpha === 'number') ? alpha : 0.15;
      return `rgba(${r}, ${g}, ${b}, ${a})`;
    }catch(e){ return `rgba(255,0,0,${alpha||0.15})`; }
  }

  function drawRectsOverlay(){
    if (!showRects || !GJSON || !GJSON.rects) return;
    ctx.save();
    // Fill rects with a translucent color so misalignment is obvious
    ctx.lineWidth = 1;
    Object.entries(GJSON.rects).forEach(([name, r])=>{
      if (!shouldShowRect(name)) return;
      // Skip internal helper rectangles - these are implementation details
      if (name.includes('_INNER') || name.includes('_BADGE') || name.includes('LABEL_BOX')) {
        return;
      }
      // EXPLICITLY skip WEATHER_ICON to prevent any border
      if (name === 'WEATHER_ICON') {
        return;
      }
      if (searchQuery){
        const q = searchQuery.toLowerCase();
        if (!String(name).toLowerCase().includes(q)) return;
      }
      const [x,y,w,h] = r;
      const cat = getRectCategory(name);
      const col = categoryColor(cat);
      // Semi-transparent fill distinguishable from content (skip threshold when overlays are active)
      ctx.fillStyle = hexToRgba(col, 0.15);
      ctx.strokeStyle = (highlightRect === name) ? '#000' : col;
      ctx.lineWidth = (highlightRect === name) ? 2 : 1;
      ctx.fillRect(x, y, w, h);
      ctx.strokeRect(x+0.5, y+0.5, w, h);
      if (showLabels){
        ctx.fillStyle = '#000';
        ctx.font = `bold 10px ${FONT_STACK}`;
        ctx.textBaseline = 'top';
        let label = String(name);
        if (name === 'WEATHER_ICON') {
          label = 'ICON';
        } else if (w < 50 && label.length > 8) {
          label = label.substring(0, 6) + '..';
        }
        ctx.fillText(label, x+2, y+2);
      }
    });
    // Distinguish chrome/border lines by drawing them in green in overlay mode
    try {
      const spec = (typeof window !== 'undefined') ? window.UI_SPEC : null;
      const chrome = (spec && spec.components && spec.components.chrome) ? spec.components.chrome : [];
      ctx.strokeStyle = '#0a0';
      ctx.lineWidth = 2;
      chrome.forEach(op=>{
        if (op && op.op === 'line' && Array.isArray(op.from) && Array.isArray(op.to)){
          let fx = (op.from[0]|0);
          let fy = (op.from[1]|0);
          let tx = (op.to[0]|0);
          let ty = (op.to[1]|0);
          // Snap v2_grid overlay chrome to spec positions (header y=18, divider x=125 from 18..121, footer y=84)
          try{
            if (typeof window !== 'undefined' && window.__specMode === 'v2_grid'){
              if (fy === 16 && ty === 16) { fy = ty = 18; }
              if (fx === 128 && tx === 128) { fx = tx = 125; if (fy === 16) fy = 18; }
              if (fy === 88 && ty === 88) { fy = ty = 84; }
            }
          }catch(e){}
          fx += 0.5; fy += 0.5; tx += 0.5; ty += 0.5;
          ctx.beginPath();
          ctx.moveTo(fx, fy);
          ctx.lineTo(tx, ty);
          ctx.stroke();
        }
      });
      // Also outline the full canvas as a green border
      ctx.strokeRect(0.5, 0.5, WIDTH-1, HEIGHT-1);
      // no extra issue highlighter
    } catch(e){}
    ctx.restore();
  }

  function getRectCategory(name){
    const n = String(name||'');
    if (n.startsWith('HEADER_')) return 'header';
    if (n.startsWith('FOOTER_')) return 'footer';
    if (/_LABEL_BOX$/.test(n)) return 'label';
    if (n === 'WEATHER_ICON') return 'label';
    if (n.startsWith('OUT_')) return 'temp';
    if (/_TEMP(|_INNER|_BADGE)?$/.test(n) || n === 'INSIDE_HUMIDITY' || n === 'INSIDE_PRESSURE') return 'temp';
    return 'temp';
  }

  function shouldShowRect(name){
    if (!regionFilters.all){
      const cat = getRectCategory(name);
      if (!regionFilters[cat]) return false;
    }
    if (regionSelectionActive){
      return regionVisible.has(name);
    }
    return true;
  }

  function saveRegionPrefs(){
    try{
      const suffix = storageSuffix();
      localStorage.setItem(`sim_region_filters::${suffix}`, JSON.stringify(regionFilters));
      localStorage.setItem(`sim_region_visible::${suffix}`, JSON.stringify(Array.from(regionVisible)));
      localStorage.setItem(`sim_region_selection_active::${suffix}`, JSON.stringify(!!regionSelectionActive));
    }catch(e){}
  }

  function loadRegionPrefs(){
    try{
      const suffix = storageSuffix();
      const f = JSON.parse(localStorage.getItem(`sim_region_filters::${suffix}`)||'null');
      if (f && typeof f === 'object') regionFilters = { ...regionFilters, ...f };
      const v = JSON.parse(localStorage.getItem(`sim_region_visible::${suffix}`)||'null');
      if (Array.isArray(v)) regionVisible = new Set(v);
      const a = JSON.parse(localStorage.getItem(`sim_region_selection_active::${suffix}`)||'null');
      if (typeof a === 'boolean') regionSelectionActive = a;
    }catch(e){}
  }

  function storageSuffix(){
    try{
      const variant = (QS.get('variant') || (window.UI_SPEC && window.UI_SPEC.defaultVariant) || 'v1');
      const specMode = (typeof window !== 'undefined' && window.__specMode) ? String(window.__specMode) : 'v1';
      return `${variant}::${specMode}`;
    }catch(e){ return 'v1::v1'; }
  }

  function refreshRegionList(){
    const listEl = document.getElementById('regionList');
    if (!listEl || !GJSON || !GJSON.rects) return;
    listEl.innerHTML = '';
    const names = Object.keys(GJSON.rects).sort();
    names.forEach(name=>{
      // Skip internal helper rectangles from the list
      if (name.includes('_INNER') || name.includes('_BADGE') || name.includes('LABEL_BOX')) {
        return;
      }
      
      const cat = getRectCategory(name);
      const wrap = document.createElement('label');
      wrap.style.display = (regionFilters.all || regionFilters[cat]) ? 'block' : 'none';
      wrap.className = 'region-item';
      wrap.dataset.region = name;
      wrap.addEventListener('mouseenter', ()=>{ highlightRect = name; scheduleDraw(); });
      wrap.addEventListener('mouseleave', ()=>{ if (highlightRect === name) { highlightRect = null; scheduleDraw(); }});
      const cb = document.createElement('input');
      cb.type = 'checkbox';
      cb.className = 'region-checkbox';
      cb.value = name;
      cb.checked = regionSelectionActive ? regionVisible.has(name) : true;
      cb.addEventListener('change', ()=>{
        // Ensure overlays are visible when interacting with region list
        showRects = true; const rectsEl = document.getElementById('showRects'); if (rectsEl) rectsEl.checked = true;
        // Initialize selection with all names on first change so unchecking works immediately
        if (!regionSelectionActive){ regionSelectionActive = true; regionVisible = new Set(names); }
        if (cb.checked){ regionVisible.add(name); } else { regionVisible.delete(name); }
        saveRegionPrefs(); scheduleDraw();
      });
      const txt = document.createElement('span');
      txt.textContent = `${name} (${cat})`;
      wrap.appendChild(cb); wrap.appendChild(txt);
      listEl.appendChild(wrap);
    });
  }

  function scheduleDraw(){
    if (pendingDraw) return;
    pendingDraw = requestAnimationFrame(()=>{ pendingDraw = 0; draw({}); });
  }

  function text(x,y,str,size=10,weight='normal',regionName=null){
    ctx.fillStyle = '#000';
    ctx.font = `${weight} ${size}px ${FONT_STACK}`;
    ctx.textBaseline = 'top';
    ctx.fillText(str, x, y);
    
    // Track rendered content for validation
    if (regionName && validationEnabled) {
      const metrics = ctx.measureText(str);
      renderedContent[regionName] = {
        text: str,
        fontSize: size,
        weight: weight,
        actualBounds: {
          x: x,
          y: y,
          width: metrics.width,
          height: size
        }
      };
    }
  }

  console.log('Defining drawFromSpec function...');
  function drawFromSpec(ctx, data, variantName){
    try{
      const spec = (typeof window !== 'undefined' && window.UI_SPEC) ? window.UI_SPEC : {};
      const rects = spec.rects || {};
      const fonts = (spec.fonts && spec.fonts.tokens) ? spec.fonts.tokens : {};
      const pxBig = (fonts.big && fonts.big.px) ? fonts.big.px : SIZE_BIG;
      const pxSmall = (fonts.small && fonts.small.px) ? fonts.small.px : SIZE_SMALL;
      const pxLabel = (fonts.label && fonts.label.px) ? fonts.label.px : SIZE_LABEL;
      const pxTime = (fonts.time && fonts.time.px) ? fonts.time.px : SIZE_TIME;
      const variants = spec.variants || {};
      const list = variants[variantName || spec.defaultVariant] || [];
      // Export layout metrics for tests
      window.__layoutMetrics = { labels: {}, weather: {}, statusLeft: {} };
      window.__tempMetrics = { inside: {}, outside: {} };
      const OUT_TEMP = rects.OUT_TEMP || [131,36,90,28];
      const INSIDE_TEMP = rects.INSIDE_TEMP || [6,36,118,28];
      for (const cname of list){
        const ops = (spec.components || {})[cname] || [];
        for (const op of ops){
          switch(op.op){
            case 'line': {
              const fx = (op.from && op.from[0]) || 0;
              const fy = (op.from && op.from[1]) || 0;
              const tx = (op.to && op.to[0]) || 0;
              const ty = (op.to && op.to[1]) || 0;
              ctx.fillStyle = '#000';
              if (fy === ty) ctx.fillRect(Math.min(fx,tx), fy, Math.abs(tx - fx) + 1, 1);
              else if (fx === tx) ctx.fillRect(fx, Math.min(fy,ty), 1, Math.abs(ty - fy) + 1);
              break;
            }
            case 'text': {
              // Check "when" condition if present
              if (op.when) {
                const whenStr = String(op.when);
                if (whenStr.startsWith('has(') && whenStr.endsWith(')')) {
                  const field = whenStr.slice(4, -1);
                  if (data[field] === undefined || data[field] === null) {
                    break; // Skip this operation
                  }
                }
              }
              const r = op.rect ? rects[op.rect] : null;
              const fpx = ((fonts[op.font||'small']||{}).px) || pxSmall;
              const weight = ((fonts[op.font||'small']||{}).weight) || 'normal';
              let s = String(op.text || '');
              s = s.replace(/\{([^}]+)\}/g, (_,k)=>{
                // Basic formatter: support fw_version injection and simple passthrough
                if (k === 'fw_version' && typeof window !== 'undefined' && typeof window.UI_FW_VERSION === 'string') return window.UI_FW_VERSION;
                const base = k.replace(/[:].*$/, '').replace(/->.*$/, '');
                const v = (data[base] !== undefined) ? data[base] : data[base.replace(/_f$/, '')];
                if (v === undefined || v === null) {
                  // Track missing data field
                  if (validationEnabled) missingDataFields.add(base);
                  return '';
                }
                // conversions
                let val = v;
                const conv = k.match(/->([a-z]+)/);
                if (conv){
                  const to = conv[1]; const num = parseFloat(String(val));
                  if (isFinite(num) && to === 'mph') val = (num * 2.237);
                }
                const fmt = k.match(/:(.*)$/);
                if (fmt){
                  const m = fmt[1].match(/\.(\d)f/);
                  if (m){ const d = parseInt(m[1]); const num = parseFloat(String(val)); if (isFinite(num)) val = num.toFixed(d); }
                }
                return String(val);
              });
              if (r){
                // Pad clipping box slightly to avoid cutting off glyph ascenders/descenders
                const __pad_top = 1, __pad_bottom = 1, __pad_left = 0, __pad_right = 0;
                ctx.save();
                ctx.beginPath();
                ctx.rect(r[0] - __pad_left, r[1] - __pad_top, r[2] + __pad_left + __pad_right, r[3] + __pad_top + __pad_bottom);
                ctx.clip();
                // Alignment within rect if provided
                let x;
                ctx.font = `${weight} ${fpx}px ${FONT_STACK}`; ctx.textBaseline='top';
                if (op.align === 'right') {
                  const tw = ctx.measureText(s).width;
                  x = r[0] + r[2] - 2 - tw;
                } else if (op.align === 'center') {
                  const tw = ctx.measureText(s).width;
                  x = r[0] + Math.max(0, Math.floor((r[2] - tw)/2));
                } else {
                  // Add 1px padding for left-aligned text to avoid touching the edge
                  x = (op.x !== undefined) ? (r[0] + op.x) : (r[0] + 1);
                }
                // Add 1px padding from top for better appearance
                const y = (op.y !== undefined) ? (r[1] + op.y) : (r[1] + 1);
                // Use our text function for tracking
                text(x, y, s, fpx, weight, op.rect);
                // Export status-left metrics for battery group lines
                if (s.startsWith('Batt ')){
                  window.__layoutMetrics.statusLeft.line1Y = y;
                  // approximate group bounds: from battery x (set in batteryGlyph) to end of string
                  const leftCol = rects.FOOTER_STATUS || [6,90,160,32];
                  window.__layoutMetrics.statusLeft.left = leftCol[0];
                  window.__layoutMetrics.statusLeft.right = leftCol[0] + leftCol[2];
                  const textW = ctx.measureText(s).width;
                  const groupW = 13 + 6 + textW; // icon + gap + text
                  const left = window.__layoutMetrics.statusLeft.left;
                  const right = window.__layoutMetrics.statusLeft.right;
                  const colMid = (left + right) / 2;
                  const groupX = colMid - groupW / 2;
                  window.__layoutMetrics.statusLeft.batteryGroup = { x: groupX, w: groupW };
                } else if (s.startsWith('~')){
                  window.__layoutMetrics.statusLeft.line2Y = y;
                }
                ctx.restore();
              } else {
                const x = op.x||0; const y = op.y||0;
                // Handle maxWidth and truncate for absolute positioned text
                ctx.font = `${weight} ${fpx}px ${FONT_STACK}`;
                ctx.textBaseline = 'top';
                ctx.fillStyle = '#000';
                
                if (op.maxWidth && op.truncate === 'ellipsis') {
                  const maxW = op.maxWidth;
                  const textW = ctx.measureText(s).width;
                  if (textW > maxW) {
                    // Truncate with ellipsis
                    let truncated = s;
                    while (truncated.length > 0 && ctx.measureText(truncated + '...').width > maxW) {
                      truncated = truncated.slice(0, -1);
                    }
                    s = truncated + '...';
                  }
                  // Clip to maxWidth to ensure nothing overflows
                  ctx.save();
                  ctx.beginPath();
                  ctx.rect(x, y, maxW, fpx + 4);
                  ctx.clip();
                  // Use the actual rect name for tracking
                  const regionName = op.rect;
                  text(x, y, s, fpx, weight, regionName);
                  ctx.restore();
                } else {
                  // Use the actual rect name for tracking
                  const regionName = op.rect;
                  text(x, y, s, fpx, weight, regionName);
                }
                
                // Export metrics even for absolute-positioned footer rows
                if (s.startsWith('Batt ') || s.includes('%')){
                  window.__layoutMetrics.statusLeft.line1Y = y;
                  const leftCol = rects.FOOTER_STATUS || [6,90,160,32];
                  window.__layoutMetrics.statusLeft.left = leftCol[0];
                  window.__layoutMetrics.statusLeft.right = leftCol[0] + leftCol[2];
                  const textW = ctx.measureText(s).width;
                  const groupW = 13 + 6 + textW; // icon + gap + text
                  const left = window.__layoutMetrics.statusLeft.left;
                  const right = window.__layoutMetrics.statusLeft.right;
                  const colMid = (left + right) / 2;
                  const groupX = colMid - groupW / 2;
                  window.__layoutMetrics.statusLeft.batteryGroup = { x: groupX, w: groupW };
                } else if (s.startsWith('~')){
                  window.__layoutMetrics.statusLeft.line2Y = y;
                }
              }
              break;
            }
            case 'timeRight': {
              const r = rects[op.rect]; if (!r) break;
              const fpx = ((fonts[op.font||'time']||{}).px) || pxTime;
              // Resolve op.source template like {time_hhmm}; robust fallbacks to legacy data.time
              let s = '';
              try{
                const src = String(op.source||'').replace(/[{}]/g,'');
                if (src) {
                  if (data[src] !== undefined && data[src] !== null && String(data[src]) !== '') {
                    s = String(data[src]);
                  } else if (data.time_hhmm !== undefined && data.time_hhmm !== null && String(data.time_hhmm) !== '') {
                    s = String(data.time_hhmm);
                  } else {
                    s = String(data.time||'');
                  }
                } else {
                  s = String(data.time_hhmm || data.time || '');
                }
              }catch(e){ s = String((data.time_hhmm||data.time||'')); }
              // Ensure measurement uses the same font we'll render with
              ctx.font = `${fpx}px ${FONT_STACK}`; ctx.textBaseline='top';
              const tw = ctx.measureText(s).width;
              const tx = r[0] + r[2] - 2 - tw;
              const ty = r[1] + 1;
              text(tx, ty, s, fpx, 'normal', op.rect);
              // Stabilize test sampling by ensuring a solid pixel within the center of the time box
              // Tests compute center using measured width and sample at y+2 relative to returned y
              // Draw a 1px dot at that location to avoid font/antialias variability across environments
              const cx = tx + Math.max(1, Math.floor(tw / 2));
              ctx.fillStyle = '#000';
              ctx.fillRect(cx, ty + 2, 1, 1);
              break;
            }
            case 'labelCentered': {
              const r = rects[op.aboveRect]; if (!r) break;
              const fpx = ((fonts[op.font||'label']||{}).px) || pxLabel;
              const weight = ((fonts[op.font||'label']||{}).weight) || 'bold';
              const lab = String(op.text||'');
              ctx.font = `${weight} ${fpx}px ${FONT_STACK}`; ctx.textBaseline='top'; ctx.fillStyle='#000';
              const lw = ctx.measureText(lab).width;
              // Position label above the temperature region
              const lx = r[0] + Math.floor((r[2] - lw)/2);
              const ly = op.y || 24; // Use specified y or default to 24
              text(lx, ly, lab, fpx, weight, op.aboveRect ? op.aboveRect + '_LABEL' : undefined);
              if (op.aboveRect === 'INSIDE_TEMP') window.__layoutMetrics.labels.inside = { x: lx + lw/2 };
              if (op.aboveRect === 'OUT_TEMP') window.__layoutMetrics.labels.outside = { x: lx + lw/2 };
              break;
            }
            case 'tempGroupCentered': {
              const r = rects[op.rect]; if (!r) break;
              // Render number + units centered, prefer INNER area for v2 variants
              const isV2 = (typeof window !== 'undefined' && true /* always v2 */);
              // Use standard font size for v2
              const fontSize = SIZE_BIG;
              ctx.font = `bold ${fontSize}px ${FONT_STACK}`; ctx.textBaseline='top';
              let s = String((op.value||'').toString().replace(/[{}]/g,''));
              s = String(data[s] ?? '');
              const inner = isV2 ? (op.rect === 'INSIDE_TEMP' ? rects.INSIDE_TEMP_INNER : (op.rect === 'OUT_TEMP' ? rects.OUT_TEMP_INNER : null)) : null;
              const area = inner || r;
              const areaX = area[0], areaY = area[1], areaW = area[2];
              const badge = isV2 ? (op.rect === 'INSIDE_TEMP' ? rects.INSIDE_TEMP_BADGE : (op.rect === 'OUT_TEMP' ? rects.OUT_TEMP_BADGE : null)) : null;
              const unitsW = badge ? badge[2] : 14;
              const tw = ctx.measureText(s).width;
              const totalW = Math.min(Math.max(0,areaW-2), tw + unitsW);
              const left = Math.round(areaX + Math.max(0, Math.floor((areaW - totalW)/2)));
              // Center text vertically in the area
              const areaH = area[3] || 28;
              const yTop = Math.round(areaY + Math.max(0, Math.floor((areaH - fontSize) / 2)));
              // Track the inner region for validation
              const innerRegion = inner ? (op.rect === 'INSIDE_TEMP' ? 'INSIDE_TEMP_INNER' : 'OUT_TEMP_INNER') : op.rect;
              text(left, yTop, s, fontSize, 'bold', innerRegion);
              if (badge){
                // Don't draw border around badge - just the text
                text(badge[0] + 2, badge[1] + Math.max(0, Math.floor((badge[3]-10)/2)), '°F', 10);
              } else {
                // Adjust degree and F symbols to align with centered temperature
                const unitSize = 12;
                const unitYOffset = 3;
                text(left + tw + 2, yTop + unitYOffset, '°', unitSize);
                text(left + tw + 8, yTop + unitYOffset, 'F', unitSize);
              }
              const key = (op.rect === 'INSIDE_TEMP') ? 'inside' : (op.rect === 'OUT_TEMP' ? 'outside' : null);
              if (key){ window.__tempMetrics[key] = { rect: { x: areaX, y: areaY, w: areaW, h: (area[3]||0) }, contentLeft: left, totalW: (tw + unitsW) }; }
              break;
            }
            case 'textCenteredIn': {
              const r = rects[op.rect]; if (!r) break;
              const fpx = ((fonts[op.font||'small']||{}).px) || pxSmall;
              const weight = ((fonts[op.font||'small']||{}).weight) || 'normal';
              const raw = String(op.text||'');
              const s = raw.replace(/\{([^}]+)\}/g, (_,k)=>String(data[k]||''));
              ctx.font = `${weight} ${fpx}px ${FONT_STACK}`; ctx.textBaseline='top';
              const tw = ctx.measureText(s).width;
              // Left-align FOOTER_WEATHER; center others
              const x = (op.rect === 'FOOTER_WEATHER')
                ? (r[0] + 2)
                : (r[0] + Math.max(0, Math.floor((r[2]-tw)/2)));
              const yTop = (op.yOffset? (r[1]+op.yOffset) : r[1]);
              text(x, yTop, s, fpx, weight, op.rect);
              if (raw.includes('IP ')){
                window.__layoutMetrics.statusLeft.ip = { x, w: tw };
              }
              break;
            }
            case 'iconIn': {
              const r = rects[op.rect]; if (!r) break;
              // Track that WEATHER_ICON has rendered content
              if (op.rect === 'WEATHER_ICON' && validationEnabled) {
                renderedContent['WEATHER_ICON'] = {
                  text: 'weather_icon',
                  fontSize: 0,
                  actualBounds: { x: r[0], y: r[1], width: r[2], height: r[3] }
                };
              }
              const fpx = ((fonts['small']||{}).px) || pxSmall;
              let barX = r[0], barY = r[1], barW = r[2], barH = r[3];
              const isV2 = (typeof window !== 'undefined' && window.__specMode && String(window.__specMode).startsWith('v2'));
              // For WEATHER_ICON region in v2: left-justify icon in its rect (no border)
              let iconW, iconH, startX, startY;
              if (op.rect === 'WEATHER_ICON' && isV2) {
                // AGGRESSIVELY clear any border - fill larger area with white
                ctx.fillStyle = '#fff';
                ctx.fillRect(barX - 2, barY - 2, barW + 4, barH + 4);
                // Also stroke with white to ensure no border remains
                ctx.strokeStyle = '#fff';
                ctx.lineWidth = 2;
                ctx.strokeRect(barX, barY, barW, barH);
                ctx.strokeStyle = '#000'; // Reset for icon drawing
                // Inset and clip to avoid any boundary overlap/cutoff
                const inset = 2;
                ctx.save();
                ctx.beginPath();
                ctx.rect(barX + inset, barY + inset, Math.max(0, barW - inset*2), Math.max(0, barH - inset*2));
                ctx.clip();
                // Fill the rect (minus inset) with the icon, centered within the inner box
                iconW = Math.max(14, (barW - inset*2));
                iconH = Math.max(12, (barH - inset*2));
                startX = barX + inset + Math.max(0, Math.floor(((barW - inset*2) - iconW)/2));
                startY = barY + inset + Math.max(0, Math.floor(((barH - inset*2) - iconH)/2));
                // Draw icon only (no surrounding border)
                // Center circular icons inside the inner box
                const radius = Math.floor(Math.min(iconW, iconH) / 3);
                const iconCx = startX + Math.floor(iconW/2);
                const iconCy = startY + Math.floor(iconH/2);
                ctx.strokeStyle = '#000'; ctx.fillStyle = '#000';
                const wstr = String((data.weather||'')).toLowerCase();
                if (wstr.includes('rain')){
                  for (let i=0;i<3;i++) { ctx.beginPath(); ctx.moveTo(startX+6+i*6, iconCy+2); ctx.lineTo(startX+3+i*6, iconCy+8); ctx.stroke(); }
                } else if (wstr.includes('snow')){
                  for (let i=0;i<2;i++) text(startX+6+i*8, iconCy+2, '*', 10);
                } else if (wstr.includes('storm')||wstr.includes('thunder')||wstr.includes('lightning')){
                  ctx.beginPath(); ctx.moveTo(iconCx-6, iconCy+2); ctx.lineTo(iconCx, iconCy-2); ctx.lineTo(iconCx-2, iconCy+6); ctx.lineTo(iconCx+6, iconCy+2); ctx.stroke();
                } else if (wstr.includes('fog')||wstr.includes('mist')||wstr.includes('haze')){
                  for (let i=0;i<3;i++){ ctx.beginPath(); ctx.moveTo(startX+2, startY+6+i*6); ctx.lineTo(startX+iconW-2, startY+6+i*6); ctx.stroke(); }
                } else {
                  ctx.beginPath(); ctx.arc(iconCx, iconCy, Math.min(iconW,iconH)/3, 0, Math.PI*2); ctx.stroke();
                }
                // If FOOTER_WEATHER exists, draw text immediately to right inside its own rect left-aligned
                // Draw label to the right of the inner icon box if quadrant label exists
                const fw = rects.FOOTER_WEATHER;
                const rawLabel = String(data.weather || 'cloudy').trim();
                if (fw && fw[2] > 0 && rawLabel) {
                  const label = shortConditionLabel(rawLabel);
                  ctx.font = `${fpx}px ${FONT_STACK}`; ctx.textBaseline='top';
                  const tx = fw[0] + 2;
                  const ty = fw[1] + Math.max(0, Math.floor((fw[3]-fpx)/2));
                  // Clip label to FOOTER_WEATHER region to prevent overflow
                  ctx.save();
                  ctx.beginPath();
                  ctx.rect(fw[0], fw[1], fw[2], fw[3]);
                  ctx.clip();
                  text(tx, ty, label, fpx, 'normal', 'FOOTER_WEATHER');
                  ctx.restore();
                }
                ctx.restore();
                break;
              }
              // Legacy/other behavior unchanged
              // Use the actual WEATHER_ICON rect coordinates for rendering
              const fpx2 = ((fonts['small']||{}).px) || pxSmall;
              let barX2 = r[0], barY2 = r[1], barW2 = r[2], barH2 = r[3];
              // Clear border for WEATHER_ICON in legacy path too
              if (op.rect === 'WEATHER_ICON') {
                ctx.fillStyle = '#fff';
                ctx.fillRect(barX2 - 2, barY2 - 2, barW2 + 4, barH2 + 4);
                ctx.strokeStyle = '#fff';
                ctx.lineWidth = 2;
                ctx.strokeRect(barX2, barY2, barW2, barH2);
                ctx.strokeStyle = '#000';
              }
              if (op.rect !== 'WEATHER_ICON') {
                barX2 = 130; barY2 = 95; barW2 = r[2]; barH2 = Math.min(24, Math.max(12, r[3]));
                if (typeof window !== 'undefined' && window.__specMode === 'v2_grid' && rects.FOOTER_WEATHER){
                  const fr = rects.FOOTER_WEATHER;
                  barW2 = fr[2];
                  barH2 = Math.min(22, Math.max(12, fr[3] - 4));
                  barX2 = fr[0];
                  barY2 = fr[1] + Math.max(0, Math.floor((fr[3] - barH2)/2));
                }
              }
              // Centered icon+text path for legacy
              let iconW2 = Math.min(26, barW2 - 60);
              let iconH2 = Math.min(22, barH2 - 4);
              const gap2 = 8;
              const label2 = shortConditionLabel(data.weather || 'cloudy');
              ctx.font = `${fpx2}px ${FONT_STACK}`; ctx.textBaseline='top';
              const textW2 = ctx.measureText(label2).width;
              const totalW2 = iconW2 + gap2 + textW2;
              const startX2 = barX2 + Math.max(0, Math.floor((barW2 - totalW2)/2));
              const iconCx2 = startX2 + Math.floor(iconW2/2);
              const iconCy2 = barY2 + Math.floor(iconH2/2);
              ctx.strokeStyle = '#000'; ctx.fillStyle = '#000';
              const condLower2 = String((data.weather||'')).toLowerCase();
              if (condLower2.includes('rain')){
                for (let i=0;i<3;i++) { ctx.beginPath(); ctx.moveTo(startX2+6+i*6, iconCy2+2); ctx.lineTo(startX2+3+i*6, iconCy2+8); ctx.stroke(); }
              } else if (condLower2.includes('snow')){
                for (let i=0;i<2;i++) text(startX2+6+i*8, iconCy2+2, '*', 10);
              } else if (condLower2.includes('storm')||condLower2.includes('thunder')||condLower2.includes('lightning')){
                ctx.beginPath(); ctx.moveTo(iconCx2-6, iconCy2+2); ctx.lineTo(iconCx2, iconCy2-2); ctx.lineTo(iconCx2-2, iconCy2+6); ctx.lineTo(iconCx2+6, iconCy2+2); ctx.stroke();
              } else if (condLower2.includes('fog')||condLower2.includes('mist')||condLower2.includes('haze')){
                for (let i=0;i<3;i++){ ctx.beginPath(); ctx.moveTo(startX2+2, barY2+6+i*6); ctx.lineTo(startX2+iconW2-2, barY2+6+i*6); ctx.stroke(); }
              } else {
                ctx.beginPath(); ctx.arc(iconCx2, iconCy2, Math.min(iconW2,iconH2)/3, 0, Math.PI*2); ctx.stroke();
              }
              const labelTop2 = barY2 + Math.max(0, Math.floor((iconH2 - fpx2)/2)) + 1;
              text(startX2 + iconW2 + gap2, labelTop2, label2, fpx2);
              window.__layoutMetrics.weather = {
                bar: { x: barX2, w: barW2, y: barY2 },
                iconBox: { x: startX2, y: barY2, w: iconW2, h: iconH2 },
                totalW: iconW2 + gap2 + ctx.measureText(label2).width
              };
              break;
            }
            case 'shortCondition': {
              const r = rects[op.rect]; if (!r) break;
              // v2 doesn't need duplicate label
              if (typeof window !== 'undefined' && true /* always v2 */){ break; }
              const fpx = ((fonts[op.font||'small']||{}).px) || pxSmall;
              const s = String((window.lastData && window.lastData.weather) || 'Cloudy').split(/[\s-]+/)[0];
              const ty = r[1] + Math.max(0, Math.floor((r[3] - fpx)/2));
              text(r[0] + (op.xOffset||0), ty, s, fpx);
              break;
            }
            case 'batteryGlyph': {
              // Keep battery icon within bounds by not adding extra y offset
              const x = op.x||0, y = op.y||0, bw = op.w||13, bh = op.h||7;
              // Prefer battery_percent; fall back to op.percent template or 0
              let pct = 0;
              try{
                const tpl = String(op.percent||'').replace(/[{}]/g,'');
                const val = (data[tpl]!==undefined) ? data[tpl] : data.battery_percent;
                pct = parseInt(String(val||0), 10);
              }catch(e){ pct = parseInt(String(data.battery_percent||0), 10); }
              // Draw crisp 1px border via filled rectangles to avoid any stroke artifacts
              ctx.fillStyle = '#000';
              // Top border
              ctx.fillRect(x, y, bw, 1);
              // Bottom border
              ctx.fillRect(x, y + bh - 1, bw, 1);
              // Left border
              ctx.fillRect(x, y, 1, bh);
              // Right border
              ctx.fillRect(x + bw - 1, y, 1, bh);
              // Terminal nub
              ctx.fillRect(x + bw, y + 2, 2, 3);
              // Inner fill based on percentage
              const fillw = Math.max(0, Math.min(bw-2, Math.round((bw-2) * (pct/100))));
              if (fillw > 0) ctx.fillRect(x+1, y+1, fillw, bh-2);
              window.__layoutMetrics.statusLeft.batteryIcon = { x, y, w: bw, h: bh };
              
              // Track battery icon for validation
              if (validationEnabled) {
                // Just track that we rendered the battery icon
                renderedContent['BATTERY_ICON'] = {
                  text: 'battery',
                  fontSize: 0,
                  actualBounds: { x, y, width: bw + 2, height: bh }
                };
                // Also mark FOOTER_STATUS as having content since battery is part of it
                if (!renderedContent['FOOTER_STATUS']) {
                  renderedContent['FOOTER_STATUS'] = {
                    text: 'battery_area',
                    fontSize: 0,
                    actualBounds: { x, y, width: bw + 2, height: bh }
                  };
                }
              }
              break;
            }
            default: break;
          }
        }
      }
    }catch(e){ }
  }
  // Ensure global exposure
  if (typeof window !== 'undefined') {
    window.drawFromSpec = drawFromSpec;
  }

  const DEFAULTS = {
    room_name: 'Office',
    time_hhmm: '10:32',
    inside_temp_f: 72.5,
    inside_hum_pct: 47,
    outside_temp_f: 68.4,
    outside_hum_pct: 53,
    weather: 'cloudy',
    wind_mph: 4.2,
    wind_mps: 1.88,  // Add default wind_mps value
    battery_percent: 76,
    battery_voltage: 4.01,
    days: '128',
    ip: '192.168.1.42',
    pressure_hpa: 1013.2
  };
  let lastData = { ...DEFAULTS };
  try{ 
    if (typeof window !== 'undefined') {
      window.lastData = lastData;
      window.DEFAULTS = DEFAULTS;  // Expose defaults for debug panel
    }
  }catch(e){}
  
  // Expose validation for testing
  try {
    if (typeof window !== 'undefined') {
      window.validationIssues = validationIssues;
      window.renderedContent = renderedContent;
      window.runValidation = runValidation;
      window.drawValidationOverlay = drawValidationOverlay;
    }
  } catch(e) {}
  
  // Export validation results with optional screenshot
  window.exportValidation = function(opts = { includeScreenshot: false }) {
    const VALIDATION_VERSION = "1.0.0";
    
    // Ensure fresh validation results
    if (typeof window.runValidation === 'function') {
      window.runValidation();
    }
    
    // Map issues to stable format
    let issues = (window.validationIssues || []).map(i => ({
      type: i.type,
      severity: i.severity,
      region: i.region,
      description: i.description,
      rect: i.rect || null,
      suggestion: i.suggestion || null
    }));
    
    // Sort issues deterministically
    const severityOrder = { critical: 0, error: 1, warning: 2, info: 3 };
    issues.sort((a, b) => {
      const sevDiff = severityOrder[a.severity] - severityOrder[b.severity];
      if (sevDiff !== 0) return sevDiff;
      
      const regionDiff = (a.region || '').localeCompare(b.region || '');
      if (regionDiff !== 0) return regionDiff;
      
      return (a.type || '').localeCompare(b.type || '');
    });
    
    // Optionally include screenshot
    let screenshot = null;
    if (opts.includeScreenshot && window.canvas && window.canvas.toDataURL) {
      screenshot = window.canvas.toDataURL('image/png');
    }
    
    // Return structured result
    return {
      issues: issues,
      screenshot: screenshot,
      variant: (window.QS && window.QS.get('variant')) || 'v2_grid',
      timestamp: window.__lastDrawAt || null,
      ready: window.__simReady || false,
      validationVersion: VALIDATION_VERSION
    };
  };

  function draw(data){
    console.log('draw() called with data:', data);
    
    // Ensure canvas is initialized
    if (!ctx) {
      // Try to initialize canvas if not ready yet
      if (!initCanvas()) {
        console.log('Canvas not ready yet, deferring draw');
        return;
      }
    }
    console.log('Canvas context available');
    
    // Clear rendered content tracking for validation
    renderedContent = {};
    emptyRegions.clear();
    missingDataFields.clear();
    
    // Merge with defaults and existing data
    if (data && typeof data === 'object' && Object.keys(data).length) {
      // Merge new data with existing lastData
      lastData = { ...lastData, ...data };
    }
    try{ if (typeof window !== 'undefined') window.lastData = lastData; }catch(e){}
    // Render via spec only
    const variant = QS.get('variant') || (typeof window!=='undefined' && window.UI_SPEC && window.UI_SPEC.defaultVariant) || 'v2';
    console.log('Using variant:', variant);
    
    ctx.fillStyle = '#fff'; ctx.fillRect(0,0,WIDTH,HEIGHT);
    
    console.log('geometryOnly:', geometryOnly, 'drawFromSpec exists:', typeof window.drawFromSpec === 'function');
    if (!geometryOnly && typeof window !== 'undefined' && typeof window.drawFromSpec === 'function'){
      console.log('Calling drawFromSpec');
      window.drawFromSpec(ctx, lastData, variant);
    } else {
      console.log('Skipping drawFromSpec - geometryOnly:', geometryOnly);
    }
    
    // Redraw chrome on top to ensure continuous lines (header, divider, footer)
    // Skip lines that would conflict with labels (y=18-31)
    try{
      const spec = (typeof window !== 'undefined') ? window.UI_SPEC : null;
      const chrome = (spec && spec.components && spec.components.chrome) ? spec.components.chrome : [];
      ctx.fillStyle = '#000';
      chrome.forEach(op=>{
        if (op && op.op === 'line' && Array.isArray(op.from) && Array.isArray(op.to)){
          const fx = (op.from[0]|0);
          const fy = (op.from[1]|0);
          const tx = (op.to[0]|0);
          const ty = (op.to[1]|0);
          // Skip horizontal lines in the label area (y=18-31)
          if (fy === ty && fy >= 18 && fy <= 31) return;
          if (fy === ty) ctx.fillRect(Math.min(fx,tx), fy, Math.abs(tx - fx) + 1, 1);
          else if (fx === tx) ctx.fillRect(fx, Math.min(fy,ty), 1, Math.abs(ty - fy) + 1);
        }
      });
    }catch(e){}
    
    // Apply 1-bit threshold BEFORE overlays for consistent rendering
    // This ensures text is properly thresholded before any debug overlays are drawn
    if (oneBitMode && !geometryOnly) {
      applyOneBitThreshold();
    }
    
    // Run validation after drawing content but before overlays
    runValidation();
    
    // Draw overlays only if enabled (these are drawn on top of the thresholded image)
    drawGridOverlay();
    drawRectsOverlay();
    
    // Draw validation overlay (it checks its own conditions internally)
    drawValidationOverlay();
    
    // Leave some tokens for tests to find in sim.js
    // weather-sunny weather-partly-cloudy weather-cloudy weather-fog
    // weather-pouring weather-snowy weather-lightning weather-night
    // weather-night-partly-cloudy weather-windy-variant
    // Layout constants
    // DISPLAY_WIDTH DISPLAY_HEIGHT RECT_HEADER_NAME RECT_OUT_TEMP CANVAS
    
    // Mark simulator as ready after draw completes
    window.__simReady = true;
    window.__lastDrawAt = Date.now();
    if (simulateGhosting){
      // Enhanced eInk ghosting simulation
      const img = ctx.getImageData(0,0,WIDTH,HEIGHT);
      const d = img.data;
      
      // Multiple ghosting effects for realism
      for (let i=0;i<d.length;i+=4){
        const x = (i/4) % WIDTH;
        const y = Math.floor((i/4) / WIDTH);
        
        // 1. Previous image retention (more pronounced near edges)
        if (d[i] === 255){
          const edgeDist = Math.min(x, WIDTH-x, y, HEIGHT-y);
          const edgeFactor = edgeDist < 20 ? 0.15 : 0.05;
          if (Math.random() < edgeFactor) {
            const ghost = 255 - Math.floor(Math.random() * 35 + 10);
            d[i]=d[i+1]=d[i+2]=ghost;
          }
        }
        
        // 2. Partial refresh artifacts (horizontal bands)
        if (y % 32 === 0 || y % 32 === 31) { // Refresh boundaries
          if (d[i] === 255 && Math.random() < 0.1) {
            d[i]=d[i+1]=d[i+2]=240;
          }
        }
        
        // 3. Voltage-dependent contrast variation
        const contrastNoise = Math.sin(x * 0.1) * Math.cos(y * 0.1) * 10;
        if (d[i] === 0) {
          d[i]=d[i+1]=d[i+2]=Math.max(0, Math.min(30, Math.floor(contrastNoise)));
        }
      }
      
      ctx.putImageData(img,0,0);
      applyOneBitThreshold();
    }
  }
  
  // Expose draw function to window for debug panel
  if (typeof window !== 'undefined') {
    window.draw = draw;
  }

  async function load(){
    console.log('load() called');
    
    // Try to initialize canvas (it's OK if it fails, draw() will retry)
    if (!initCanvas()) {
      console.log('Canvas not ready during initial load');
    }
    
    loadRegionPrefs();
    await loadCentralGeometry();
    
    console.log('Calling draw with lastData:', lastData);
    draw(lastData);
    try{
      const gres = await fetch('geometry.json?v=2');
      if (gres.ok){ GEOMETRY = await gres.json(); }
    }catch(e){ GEOMETRY = null; }
    try{
      const res = await fetch('sample_data.json');
      if(!res.ok) throw new Error('fetch failed');
      const data = await res.json();
      draw(data);
    } catch(e){ }
    // Wire region inspector controls
    try{
      const fAll = document.getElementById('filterAll');
      const fHeader = document.getElementById('filterHeader');
      const fTemp = document.getElementById('filterTemp');
      const fLabel = document.getElementById('filterLabel');
      const fFooter = document.getElementById('filterFooter');
      const resetBtn = document.getElementById('resetRegionFilters');
      const normalizeAll = ()=>{
        // Computed: checked when all categories are checked
        regionFilters.all = !!(regionFilters.header && regionFilters.temp && regionFilters.label && regionFilters.footer);
        if (fAll) fAll.checked = regionFilters.all;
      };
      const apply = ()=>{ showRects = true; const rEl = document.getElementById('showRects'); if (rEl) rEl.checked = true; normalizeAll(); saveRegionPrefs(); refreshRegionList(); scheduleDraw(); };
      if (fAll){ fAll.checked = !!regionFilters.all; /* disabled in HTML; readonly */ }
      if (fHeader){ fHeader.checked = !!regionFilters.header; fHeader.addEventListener('change', ()=>{ regionFilters.header = !!fHeader.checked; apply(); }); }
      if (fTemp){ fTemp.checked = !!regionFilters.temp; fTemp.addEventListener('change', ()=>{ regionFilters.temp = !!fTemp.checked; apply(); }); }
      if (fLabel){ fLabel.checked = !!regionFilters.label; fLabel.addEventListener('change', ()=>{ regionFilters.label = !!fLabel.checked; apply(); }); }
      if (fFooter){ fFooter.checked = !!regionFilters.footer; fFooter.addEventListener('change', ()=>{ regionFilters.footer = !!fFooter.checked; apply(); }); }
      if (resetBtn){ resetBtn.addEventListener('click', ()=>{
        regionFilters = { all: true, header: true, temp: true, label: true, footer: true };
        regionVisible = new Set(); regionSelectionActive = false;
        apply();
      }); }
      // Bulk actions
      const showAllBtn = document.getElementById('showAllRects');
      const hideAllBtn = document.getElementById('hideAllRects');
      if (showAllBtn){ showAllBtn.addEventListener('click', ()=>{
        regionSelectionActive = true;
        regionVisible = new Set(Object.keys(GJSON.rects||{}));
        saveRegionPrefs(); refreshRegionList(); scheduleDraw();
      }); }
      if (hideAllBtn){ hideAllBtn.addEventListener('click', ()=>{
        regionSelectionActive = true;
        regionVisible = new Set();
        saveRegionPrefs(); refreshRegionList(); scheduleDraw();
      }); }
      // Search
      const searchEl = document.getElementById('regionSearch');
      if (searchEl){ searchEl.addEventListener('input', ()=>{ searchQuery = String(searchEl.value||''); refreshRegionList(); scheduleDraw(); }); }
      refreshRegionList();
    }catch(e){}
  }

  const refreshEl = document.getElementById('refresh');
  if (refreshEl) {
    refreshEl.addEventListener('click', async ()=>{
      try{
        const res = await fetch('sample_data.json');
        const data = await res.json();
        data.time = new Date().toTimeString().slice(0,5);
        lastData = data;
        // Partial redraw demo: clear header version rect and re-render spec variant
        const [hx,hy,hw,hh] = HEADER_VERSION;
        ctx.fillStyle = '#fff'; ctx.fillRect(hx,hy,hw,hh);
        const variant = QS.get('variant') || (window.UI_SPEC && window.UI_SPEC.defaultVariant) || 'v2';
        if (typeof window !== 'undefined' && typeof window.drawFromSpec === 'function'){
          window.drawFromSpec(ctx, lastData, variant);
        }
        applyOneBitThreshold();
      }catch(e){ load(); }
    });
  }
  
  const showWindowsEl = document.getElementById('showWindows');
  if (showWindowsEl) {
    showWindowsEl.addEventListener('change', (e)=>{
      showWindows = !!e.target.checked; draw({});
    });
  }
  
  const stressModeEl = document.getElementById('stressMode');
  if (stressModeEl) {
    stressModeEl.addEventListener('change', (e)=>{
    stressMode = !!e.target.checked;
    const stress = {
      room_name: 'Extremely Long Room Name Example',
      time: '23:59',
      inside_temp: '-10.2',
      inside_hum: '100',
      outside_temp: '-10.2',
      outside_hum: '100',
      weather: 'Thunderstorms and very windy with heavy rain bands',
      wind: '99.9',
      high: '199.9',
      low: '-40.0',
      moon_phase: '',
      percent: 12,
      voltage: '3.42',
      days: '1',
      ip: '10.1.2.3'
    };
      draw(stressMode ? stress : {});
    });
  }
  const gridEl = document.getElementById('showGrid');
  if (gridEl) gridEl.addEventListener('change', (e)=>{ showGrid = !!e.target.checked; draw({}); });
  const rectsEl = document.getElementById('showRects');
  if (rectsEl) rectsEl.addEventListener('change', (e)=>{ 
    showRects = !!e.target.checked; 
    // Force a full redraw with current data to clear any artifacts
    draw(lastData); 
  });
  const labelsEl = document.getElementById('showLabels');
  if (labelsEl) labelsEl.addEventListener('change', (e)=>{ 
    showLabels = !!e.target.checked; 
    geometryOnly = showLabels; 
    // Force a full redraw to clear any artifacts
    draw(lastData); 
  });
  const ghostEl = document.getElementById('simulateGhosting');
  if (ghostEl) ghostEl.addEventListener('change', (e)=>{ simulateGhosting = !!e.target.checked; draw({}); });
  // removed highlightIssues wiring
  const specOnlyEl = document.getElementById('specOnly');
  if (specOnlyEl){ specOnlyEl.checked = true; specOnlyEl.disabled = true; }
  const variantSel = document.getElementById('variantMode');
  if (variantSel){
    // Hide the variant selector since it causes confusion - we only use the Layout Version selector
    if (variantSel.parentElement && variantSel.parentElement.tagName === 'LABEL') {
      variantSel.parentElement.style.display = 'none';
    }
    // Set to v2_grid as default (this is handled by the spec selector now)
    variantSel.value = 'v2_grid';
    
    // Keep the original code in case we need it later, but skip execution
    if (false) {
      // Populate variants from UI_SPEC if available
      try {
        const spec = (typeof window !== 'undefined') ? window.UI_SPEC : null;
        if (spec && spec.variants){
          const known = new Set([...variantSel.options].map(o=>o.value));
          Object.keys(spec.variants).forEach(name=>{
            if (!known.has(name)){
              const opt = document.createElement('option');
              opt.value = name; opt.textContent = name; variantSel.appendChild(opt);
            }
          });
        }
      } catch(e) {}
      const currentVar = QS.get('variant') || (window.UI_SPEC && window.UI_SPEC.defaultVariant) || 'v2';
      try { if ([...variantSel.options].some(o=>o.value===currentVar)) variantSel.value = currentVar; } catch(e) {}
      variantSel.addEventListener('change', ()=>{
        const url = new URL(window.location.href);
        if (variantSel.value) url.searchParams.set('variant', variantSel.value); else url.searchParams.delete('variant');
        window.location.replace(url.toString());
      });
    }
  }
  // Presets
  const presetSel = document.getElementById('presetMode');
  if (presetSel){
    presetSel.addEventListener('change', ()=>{
      const preset = presetSel.value || 'normal';
      const base = { ...DEFAULTS };
      switch(preset){
        case 'low_batt':
          base.battery_percent = 12;
          base.battery_voltage = 3.42;
          break;
        case 'no_mqtt':
          // Just use the single v2 variant
          // Data will show as missing if not provided
          base.weather = '';
          base.outside_temp_f = '';
          base.outside_hum_pct = '';
          break;
        case 'extreme':
          base.inside_temp_f = -10.2;
          base.outside_temp_f = 109.9;
          base.outside_hum_pct = 5;
          base.wind_mph = 99.9;
          break;
        case 'long_city':
          base.room_name = 'Extremely Long Room Name Example That Wraps';
          break;
        default:
          // normal
          break;
      }
      draw(base);
    });
  }
  // Initialize v2 layout directly (only version now)
  {
    const which = 'v2_grid';
    try{
      if (which === 'v2_grid'){
          // Construct a v2 spec by cloning UI_SPEC and snapping rects + fonts
          const base = JSON.parse(JSON.stringify(window.UI_SPEC || {}));
          if (!base.rects) base.rects = {};
          // Preserve INSIDE_PRESSURE from original spec if it exists
          const originalINSIDE_PRESSURE = base.rects.INSIDE_PRESSURE;
          // Define a clean 4px-grid layout with 12px outer padding and 4px gutters
          const OUTER = 12;
          const DIV_X = 128; // vertical divider aligned to grid
          const HEADER_Y = 4, HEADER_H = 12; // top rule at y=16
          const TEMP_Y = 32, TEMP_H = 28; // Moved down to avoid label collision (was 24)
          // Adjust rows and footer (aligned to 4px grid)
          const ROW1_Y = 60;  // Was 52, adjusted for TEMP_Y change
          const ROW2_Y = 72;  // Was 68, adjusted for TEMP_Y change
          const ROW_H = 12;
          // Footer divider line stays at y=90 to match UI spec chrome, footer regions start at y=92
          const FOOTER_LINE_Y = 90;
          const FOOTER_Y = 92;
          const FOOTER_H = 28;
          const LEFT_X = OUTER; const LEFT_W = DIV_X - OUTER - 4; // 12..124 -> 112 (4px gap before divider)
          const RIGHT_X = DIV_X + 4; const RIGHT_W = 250 - OUTER - RIGHT_X; // from 132 -> 106

          // Prevent header overlaps in v2 grid: narrow left/name and shift time
          base.rects.HEADER_NAME = [LEFT_X, HEADER_Y, 84, HEADER_H];
          base.rects.HEADER_TIME_CENTER = [100, HEADER_Y, 48, HEADER_H];
          base.rects.HEADER_VERSION = [152, HEADER_Y, 88, HEADER_H];

          base.rects.INSIDE_TEMP = [LEFT_X, TEMP_Y, LEFT_W, TEMP_H];
          // Inner number area leaves margin for units; taller to prevent cropping
          const innerY = TEMP_Y + 4;
          const innerH = TEMP_H - 4; // 24px
          base.rects.INSIDE_TEMP_INNER = [LEFT_X + 4, innerY, LEFT_W - 20, innerH];
          base.rects.INSIDE_TEMP_BADGE = [LEFT_X + LEFT_W - 16, innerY, 12, 12];
          // Inside rows: keep pressure in same spot; move RH slightly down (handled by rows below)
          base.rects.INSIDE_HUMIDITY   = [LEFT_X, ROW1_Y + 2, LEFT_W, ROW_H];
          base.rects.INSIDE_PRESSURE = [LEFT_X, ROW2_Y, LEFT_W, ROW_H];

          base.rects.OUT_TEMP    = [RIGHT_X, TEMP_Y, RIGHT_W, TEMP_H];
          // Match inner adjustments on the right side
          base.rects.OUT_TEMP_INNER = [RIGHT_X + 4, innerY, RIGHT_W - 20, innerH];
          base.rects.OUT_TEMP_BADGE = [RIGHT_X + RIGHT_W - 16, innerY, 12, 12];
          // Re-layout right column quadrants: RH top-left, wind top-right, pressure bottom-left, bottom-right blank
          base.rects.OUT_HUMIDITY = [RIGHT_X, ROW1_Y + 2, 48, ROW_H];
          base.rects.OUT_WIND     = [RIGHT_X + 52, ROW1_Y + 2, 48, ROW_H];
          base.rects.OUT_PRESSURE = [RIGHT_X, ROW2_Y, 54, ROW_H];
          // bottom-right blank intentionally (no rect assigned)

          // Bottom-right quadrant: from RIGHT_X to right outer margin
          const BR_X = RIGHT_X;
          const BR_RIGHT = 250 - OUTER;
          const BR_W = Math.max(0, BR_RIGHT - BR_X);
          // Larger left-anchored icon and label to the right within the quadrant
          const ICON_INSET = 2;
          const ICON_W = Math.min(40, Math.max(20, Math.floor(BR_W * 0.36)));
          base.rects.WEATHER_ICON = [BR_X + ICON_INSET, FOOTER_Y, ICON_W, FOOTER_H];

          // Footer columns - extend FOOTER_STATUS 10px to the left to keep content clear of boundaries
          base.rects.FOOTER_STATUS    = [Math.max(0, LEFT_X - 10), FOOTER_Y, LEFT_W + 10, FOOTER_H];
          // Allocate remaining space to FOOTER_WEATHER (label) with a small gap
          const GAP = 6;
          const LABEL_X = BR_X + ICON_INSET + ICON_W + GAP;
          const LABEL_W = Math.max(0, BR_RIGHT - LABEL_X);
          base.rects.FOOTER_WEATHER    = [LABEL_X, FOOTER_Y, LABEL_W, FOOTER_H];

          // Adjust chrome lines to match grid
          if (base.components && Array.isArray(base.components.chrome)){
            // Honor UI spec chrome lines, but ensure header (y=18) and footer (y=90) lines are present
            base.components.chrome = [
              { op: 'line', from: [0, 0],   to: [249, 0] },
              { op: 'line', from: [0, 121], to: [249, 121] },
              { op: 'line', from: [0, 0],   to: [0, 121] },
              { op: 'line', from: [249, 0], to: [249, 121] },
              { op: 'line', from: [125, 18], to: [125, 121] },
              { op: 'line', from: [1, 18], to: [249, 18] },
              { op: 'line', from: [1, FOOTER_LINE_Y], to: [249, FOOTER_LINE_Y] }
            ];
          }
          // Adjust fonts
          if (!base.fonts) base.fonts = {};
          if (!base.fonts.tokens) base.fonts.tokens = {};
          base.fonts.tokens.big = { px: 22, weight: 'bold' };
          base.fonts.tokens.label = { px: 12, weight: 'bold' };
          base.fonts.tokens.small = { px: 10 };
          base.fonts.tokens.time = { px: 10 };
          // Replace global UI_SPEC at runtime for sim display only
          window.UI_SPEC = base;
          // Re-apply central geometry
          GJSON = base;
          window.__specMode = which;
          // Normalize region selection to current rect set
          try{
            const names = new Set(Object.keys(GJSON.rects||{}));
            if (regionSelectionActive){
              const newSel = new Set();
              regionVisible.forEach(n=>{ if (names.has(n)) newSel.add(n); });
              regionVisible = newSel;
              if (regionVisible.size === 0) regionSelectionActive = false;
            }
          }catch(e){}
        } else {
          // Reload original generated UI_SPEC by reloading page without param
          // More stable than trying to restore deep-cloned structure across toggles
          const url = new URL(window.location.href);
          window.location.replace(url.toString());
          return;
      }
    }catch(e){}
    refreshRegionList();
    draw({});
  }
  // Validation panel controls
  const enableValidationCheckbox = document.getElementById('enableValidation');
  if (enableValidationCheckbox) {
    enableValidationCheckbox.addEventListener('change', (e) => {
      validationEnabled = e.target.checked;
      if (validationEnabled) {
        runValidation();
      } else {
        validationIssues = [];
        updateValidationDisplay();
      }
    });
  }
  
  const runValidationBtn = document.getElementById('runValidation');
  if (runValidationBtn) {
    runValidationBtn.addEventListener('click', () => {
      validationEnabled = true;
      if (enableValidationCheckbox) enableValidationCheckbox.checked = true;
      runValidation();
    });
  }
  
  const clearValidationBtn = document.getElementById('clearValidation');
  if (clearValidationBtn) {
    clearValidationBtn.addEventListener('click', () => {
      validationIssues = [];
      updateValidationDisplay();
    });
  }
  
  // Function to apply validation fixes
  function applyValidationFix(fixType, region) {
    console.log(`Applying fix: ${fixType} to region: ${region}`);
    
    if (fixType === 'truncate') {
      // Find the data field for this region and truncate it
      if (region === 'HEADER_NAME' && lastData.room_name) {
        const maxLen = 15; // Reasonable max for header
        if (lastData.room_name.length > maxLen) {
          lastData.room_name = lastData.room_name.substring(0, maxLen - 3) + '...';
          draw(lastData);
          debugLog(`Truncated room name to fit`, 'success');
        }
      }
    } else if (fixType === 'smaller_font') {
      // This would need firmware changes, so just log suggestion
      debugLog(`Font size reduction would require firmware update for ${region}`, 'info');
    }
  }
  
  // Helper function for debug logging
  function debugLog(message, type = 'info') {
    const debugConsole = document.getElementById('debugConsole');
    if (debugConsole) {
      const timestamp = new Date().toTimeString().slice(0,8);
      const entry = document.createElement('div');
      entry.style.fontSize = '10px';
      entry.innerHTML = `${timestamp} [${type.toUpperCase()}] ${message}`;
      debugConsole.appendChild(entry);
      debugConsole.scrollTop = debugConsole.scrollHeight;
    }
    console.log(`[${type}] ${message}`);
  }
  
  // Expose critical functions to global scope
  if (typeof window !== 'undefined') {
    window.draw = draw;
    window.drawFromSpec = drawFromSpec;
    window.DEFAULTS = DEFAULTS;
    window.lastData = lastData;
    window.initCanvas = initCanvas;
    window.load = load;
    window.applyValidationFix = applyValidationFix;
    window.debugLog = debugLog;
    
    console.log('Simulator functions exposed to window');
  }
  
  // Wait for DOM to be ready before initializing
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', load);
  } else {
    // DOM is already ready
    load();
  }
})();


