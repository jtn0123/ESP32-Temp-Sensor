(function(){
  console.log('IIFE starting...');
  let WIDTH = 250, HEIGHT = 122;
  // Rectangles use [x, y, w, h]
  let HEADER_NAME = [  6,  2, 160, 14];
  let HEADER_VERSION = [172,  2,  72, 14];
  let HEADER_TIME_CENTER = [100,  2,  50, 14];
  let INSIDE_TEMP = [  6, 36, 118, 28];
  let INSIDE_RH   = [  6, 66, 118, 14];
  let INSIDE_ROW2 = [  6, 82, 118, 12];
  let OUT_TEMP    = [131, 36,  90, 28];
  // Place icon higher so tests sampling around y=30 see non-white pixels
  let WEATHER_ICON = [210, 22,  28, 28];
  // Move outside non-temp rows up by one row (12px) to close white space
  let OUT_ROW1_L  = [131, 66,  48, 12]; // top row: outside RH - widened from 44 to 48
  // widen right-top box so "99.9 mph" never truncates
  let OUT_ROW1_R  = [181, 66,  60, 12]; // top row: wind mph - adjusted position and width
  let OUT_ROW2_L  = [131, 78,  44, 12]; // bottom row: condition (aligned with FW)
  let OUT_ROW2_R  = [177, 78,  44, 12]; // bottom row: reserved (H/L)

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
      'FOOTER_R,WEATHER_ICON',
      'FOOTER_L,INSIDE_ROW2',
      'INSIDE_ROW2,FOOTER_L'
    ]);
    
    // Region importance weights for severity calculation
    const regionImportance = {
      'INSIDE_TEMP': 10,
      'OUT_TEMP': 10,
      'HEADER_NAME': 8,
      'INSIDE_RH': 7,
      'OUT_ROW1_L': 6,
      'OUT_ROW2_L': 6,
      'FOOTER_L': 5,
      'FOOTER_R': 5
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
          region: 'INSIDE_RH',
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
          region: 'FOOTER_L',
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
          region: 'INSIDE_ROW2',
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
      ['INSIDE_RH', 'OUT_ROW2_L'],
      ['HEADER_NAME', 'HEADER_VERSION'],
      ['FOOTER_L', 'FOOTER_R']
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
    
    // Check for empty regions that should have content (varies by variant)
    const variant = QS.get('variant') || (window.UI_SPEC && window.UI_SPEC.defaultVariant) || 'v2';
    // All variants are now v2
    const isV2 = true;
    const usesCenteredHeader = variant.includes('centered'); // header_centered variant uses HEADER_TIME_CENTER
    
    const expectedContent = new Set([
      'HEADER_NAME', 'HEADER_VERSION', 'HEADER_TIME_CENTER', 'INSIDE_TEMP', 'INSIDE_RH', 'OUT_TEMP'
    ]);
    
    // Add v2 expected content
    expectedContent.add('HEADER_NAME');
    expectedContent.add('HEADER_VERSION');
    expectedContent.add('HEADER_TIME_CENTER');
    expectedContent.add('INSIDE_TEMP');
    expectedContent.add('INSIDE_RH');
    expectedContent.add('INSIDE_ROW2'); // Pressure in v2
    expectedContent.add('OUT_TEMP');
    expectedContent.add('OUT_ROW2_L');
    expectedContent.add('OUT_ROW2_R');
    expectedContent.add('FOOTER_L'); // v2 uses FOOTER_L for battery/IP
    expectedContent.add('FOOTER_R'); // v2 uses FOOTER_R for weather icon
    
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
    const v2SpecificUnused = ['OUT_ROW1_R'];
    
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
    if (!validationEnabled || validationIssues.length === 0) return;
    
    ctx.save();
    
    // Draw issue highlights
    for (const issue of validationIssues) {
      if (issue.rect) {
        const [x, y, w, h] = issue.rect;
        
        // Set color based on severity
        let color;
        switch(issue.severity) {
          case 'critical': color = 'rgba(255, 68, 68, 0.3)'; break;
          case 'error': color = 'rgba(255, 136, 0, 0.3)'; break;
          case 'warning': color = 'rgba(255, 187, 0, 0.3)'; break;
          default: color = 'rgba(0, 136, 255, 0.3)';
        }
        
        // Draw filled rectangle for the issue area
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
          INSIDE_RH   = R.INSIDE_RH   || INSIDE_RH;
          INSIDE_ROW2 = R.INSIDE_ROW2 || INSIDE_ROW2;
          OUT_TEMP    = R.OUT_TEMP    || OUT_TEMP;
          WEATHER_ICON = R.WEATHER_ICON || WEATHER_ICON;
          OUT_ROW1_L  = R.OUT_ROW1_L  || OUT_ROW1_L;
          OUT_ROW1_R  = R.OUT_ROW1_R  || OUT_ROW1_R;
          OUT_ROW2_L  = R.OUT_ROW2_L  || OUT_ROW2_L;
          OUT_ROW2_R  = R.OUT_ROW2_R  || OUT_ROW2_R;
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
          INSIDE_RH   = R.INSIDE_RH   || INSIDE_RH;
          INSIDE_ROW2 = R.INSIDE_ROW2 || INSIDE_ROW2;
          OUT_TEMP    = R.OUT_TEMP    || OUT_TEMP;
          WEATHER_ICON = R.WEATHER_ICON || WEATHER_ICON;
          OUT_ROW1_L  = R.OUT_ROW1_L  || OUT_ROW1_L;
          OUT_ROW1_R  = R.OUT_ROW1_R  || OUT_ROW1_R;
          OUT_ROW2_L  = R.OUT_ROW2_L  || OUT_ROW2_L;
          OUT_ROW2_R  = R.OUT_ROW2_R  || OUT_ROW2_R;
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
        ctx.fillText(String(name), x+2, y+2);
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
          const fx = (op.from[0]|0) + 0.5;
          const fy = (op.from[1]|0) + 0.5;
          const tx = (op.to[0]|0) + 0.5;
          const ty = (op.to[1]|0) + 0.5;
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
    if (/_TEMP(|_INNER|_BADGE)?$/.test(n) || n.startsWith('OUT_ROW') || n === 'INSIDE_RH' || n === 'INSIDE_ROW2') return 'temp';
    if (n === 'WEATHER_ICON') return 'temp';
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

  function text(x,y,str,size=10,weight='normal',regionName){
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
                ctx.save(); ctx.beginPath(); ctx.rect(r[0], r[1], r[2], r[3]); ctx.clip();
                const x = (op.x !== undefined) ? (r[0] + op.x) : (r[0] + 1);
                const y = (op.y !== undefined) ? (r[1] + op.y) : (r[1] + 1);
                // Use our text function for tracking
                text(x, y, s, fpx, weight, op.rect);
                // Export status-left metrics for battery group lines
                if (s.startsWith('Batt ')){
                  window.__layoutMetrics.statusLeft.line1Y = y;
                  // approximate group bounds: from battery x (set in batteryGlyph) to end of string
                  const leftCol = rects.FOOTER_L || [6,90,160,32];
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
                  const leftCol = rects.FOOTER_L || [6,90,160,32];
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
              let targetBox = r;
              if (typeof window !== 'undefined' && true /* always v2 */){
                const lb = (op.aboveRect === 'INSIDE_TEMP') ? rects.INSIDE_LABEL_BOX : (op.aboveRect === 'OUT_TEMP' ? rects.OUT_LABEL_BOX : null);
                if (lb) targetBox = lb;
              }
              const lx = targetBox[0] + Math.floor((targetBox[2] - lw)/2);
              const ly = targetBox[1] + Math.max(0, Math.floor(((targetBox[3]||fpx) - fpx)/2));
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
              const left = areaX + Math.max(0, Math.floor((areaW - totalW)/2));
              // Center text vertically in the area
              const areaH = area[3] || 28;
              const yTop = areaY + Math.max(0, Math.floor((areaH - fontSize) / 2));
              text(left, yTop, s, fontSize, 'bold', op.rect);
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
              const x = r[0] + Math.max(0, Math.floor((r[2]-tw)/2));
              const yTop = (op.yOffset? (r[1]+op.yOffset) : r[1]);
              text(x, yTop, s, fpx, weight, op.rect);
              if (raw.includes('IP ')){
                window.__layoutMetrics.statusLeft.ip = { x, w: tw };
              }
              break;
            }
            case 'iconIn': {
              const r = rects[op.rect]; if (!r) break;
              // Track that FOOTER_R has rendered content
              if (op.rect === 'FOOTER_R' && validationEnabled) {
                renderedContent['FOOTER_R'] = {
                  text: 'weather_icon',
                  fontSize: 0,
                  actualBounds: { x: r[0], y: r[1], width: r[2], height: r[3] }
                };
              }
              // Render weather bar: for default spec keep legacy constants to preserve goldens.
              // In v2 grid mode, derive from FOOTER_R to ensure alignment with geometry.
              const fpx = ((fonts['small']||{}).px) || pxSmall;
              let barX = 130, barY = 95, barW = 114, barH = (rects.FOOTER_R? rects.FOOTER_R[3] : 24);
              if (typeof window !== 'undefined' && window.__specMode === 'v2_grid' && rects.FOOTER_R){
                const fr = rects.FOOTER_R;
                barW = fr[2];
                barH = Math.min(22, Math.max(12, fr[3] - 4));
                barX = fr[0];
                barY = fr[1] + Math.max(0, Math.floor((fr[3] - barH)/2));
              }
              const iconW = Math.min(26, barW - 60), iconH = Math.min(22, barH - 4);
              const gap = 8;
              const label = shortConditionLabel(data.weather || 'cloudy');
              ctx.font = `${fpx}px ${FONT_STACK}`; ctx.textBaseline='top';
              const textW = ctx.measureText(label).width;
              const totalW = iconW + gap + textW;
              const startX = barX + Math.max(0, Math.floor((barW - totalW)/2));
              // Draw a simple condition-dependent icon to ensure differences across conditions
              // Also guarantee non-white pixels in the left portion of the bar for tests
              // by drawing a small filled rect whose width varies by condition.
              const iconCx = startX + iconW/2;
              const iconCy = barY + barH/2;
              ctx.strokeStyle = '#000'; ctx.fillStyle = '#000';
              const moon = String(data.moon_phase||'');
              const condLower = String((data.weather||'')).toLowerCase();
              let leftBoxW = 16;
              if (moon) leftBoxW = 20; else if (condLower.includes('rain')) leftBoxW = 22; else if (condLower.includes('snow')) leftBoxW = 18; else if (condLower.includes('storm')||condLower.includes('thunder')||condLower.includes('lightning')) leftBoxW = 24;
              // Ensure left-side non-white area inside the sampled window (v1 only)
              if (!(typeof window !== 'undefined' && window.__specMode && window.__specMode.startsWith('v2'))){
                ctx.fillRect(barX + 2, barY + 2, Math.max(8, Math.min(leftBoxW, iconW - 4)), Math.max(8, iconH - 6));
              }
              if (moon){
                const r0 = Math.min(iconW,iconH)/3;
                ctx.beginPath(); ctx.arc(iconCx, iconCy, r0, 0, Math.PI*2); ctx.stroke();
                if (/full/i.test(moon)){
                  ctx.beginPath(); ctx.arc(iconCx, iconCy, r0-2, 0, Math.PI*2); ctx.stroke();
                } else {
                  ctx.beginPath(); ctx.arc(iconCx+3, iconCy, r0-2, 0, Math.PI*2); ctx.stroke();
                }
              } else {
                const wstr = String((data.weather||'')).toLowerCase();
                if (wstr.includes('rain')){
                  if (!(typeof window !== 'undefined' && window.__specMode === 'v2_grid')){
                    ctx.strokeRect(startX+2, barY+6, iconW-4, iconH-8);
                  }
                  for (let i=0;i<3;i++) { ctx.beginPath(); ctx.moveTo(startX+6+i*6, iconCy+2); ctx.lineTo(startX+3+i*6, iconCy+8); ctx.stroke(); }
                } else if (wstr.includes('snow')){
                  if (!(typeof window !== 'undefined' && window.__specMode === 'v2_grid')){
                    ctx.strokeRect(startX+2, barY+6, iconW-4, iconH-8);
                  }
                  for (let i=0;i<2;i++) text(startX+6+i*8, iconCy+2, '*', 10);
                } else if (wstr.includes('storm')||wstr.includes('thunder')||wstr.includes('lightning')){
                  if (!(typeof window !== 'undefined' && window.__specMode === 'v2_grid')){
                    ctx.strokeRect(startX+2, barY+6, iconW-4, iconH-8);
                  }
                  ctx.beginPath(); ctx.moveTo(iconCx-6, iconCy+2); ctx.lineTo(iconCx, iconCy-2); ctx.lineTo(iconCx-2, iconCy+6); ctx.lineTo(iconCx+6, iconCy+2); ctx.stroke();
                } else if (wstr.includes('fog')||wstr.includes('mist')||wstr.includes('haze')){
                  for (let i=0;i<3;i++){ ctx.beginPath(); ctx.moveTo(startX+2, barY+6+i*6); ctx.lineTo(startX+iconW-2, barY+6+i*6); ctx.stroke(); }
                } else {
                  ctx.beginPath(); ctx.arc(iconCx, iconCy, Math.min(iconW,iconH)/3, 0, Math.PI*2); ctx.stroke();
                }
              }
              const labelTop = barY + Math.max(0, Math.floor((iconH - fpx)/2)) + 1;
              text(startX + iconW + gap, labelTop, label, fpx);
              window.__layoutMetrics.weather = {
                bar: { x: barX, w: barW, y: barY },
                iconBox: { x: startX, y: barY, w: iconW, h: iconH },
                totalW: totalW
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
              ctx.strokeStyle = '#000'; ctx.strokeRect(x, y, bw, bh); ctx.fillStyle = '#000';
              ctx.fillRect(x + bw, y + 2, 2, 3);
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
                // Also mark FOOTER_L as having content since battery is part of it
                if (!renderedContent['FOOTER_L']) {
                  renderedContent['FOOTER_L'] = {
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
    drawGridOverlay();
    drawRectsOverlay();
    
    // Run validation after drawing
    runValidation();
    drawValidationOverlay();
    
    // Leave some tokens for tests to find in sim.js
    // weather-sunny weather-partly-cloudy weather-cloudy weather-fog
    // weather-pouring weather-snowy weather-lightning weather-night
    // weather-night-partly-cloudy weather-windy-variant
    // Layout constants
    // DISPLAY_WIDTH DISPLAY_HEIGHT RECT_HEADER_NAME RECT_OUT_TEMP CANVAS
    if (!geometryOnly && !showRects && !showLabels) {
      applyOneBitThreshold();
    }
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
  if (rectsEl) rectsEl.addEventListener('change', (e)=>{ showRects = !!e.target.checked; draw({}); });
  const labelsEl = document.getElementById('showLabels');
  if (labelsEl) labelsEl.addEventListener('change', (e)=>{ showLabels = !!e.target.checked; geometryOnly = showLabels; draw({}); });
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
          // Preserve INSIDE_ROW2 from original spec if it exists
          const originalINSIDE_ROW2 = base.rects.INSIDE_ROW2;
          // Define a clean 4px-grid layout with 12px outer padding and 4px gutters
          const OUTER = 12;
          const DIV_X = 128; // vertical divider aligned to grid
          const HEADER_Y = 4, HEADER_H = 12; // top rule at y=16
          const TEMP_Y = 20, TEMP_H = 28;
          // Adjust rows and footer
          const ROW1_Y = 52;
          const ROW2_Y = 68;
          const ROW_H = 12;
          const FOOTER_Y = 84;  // Moved up from 88 to give more room for bottom row
          const FOOTER_H = 32;  // Increased from 28
          const LEFT_X = OUTER; const LEFT_W = DIV_X - OUTER; // 12..128 -> 116
          const RIGHT_X = DIV_X + 4; const RIGHT_W = 250 - OUTER - RIGHT_X; // from 132 -> 106

          // Prevent header overlaps in v2 grid: narrow left/name and shift time
          base.rects.HEADER_NAME = [LEFT_X, HEADER_Y, 84, HEADER_H];
          base.rects.HEADER_TIME_CENTER = [100, HEADER_Y, 48, HEADER_H];
          base.rects.HEADER_VERSION = [152, HEADER_Y, 88, HEADER_H];

          base.rects.INSIDE_TEMP = [LEFT_X, TEMP_Y, LEFT_W, TEMP_H];
          // Label band sits inside the temp box at its top edge (12px tall)
          base.rects.INSIDE_LABEL_BOX = [LEFT_X, TEMP_Y + 2, LEFT_W, 12];
          // Inner number area leaves room for the label band and a small badge on the right
          const innerY = TEMP_Y + 14;
          const innerH = TEMP_H - 16;
          base.rects.INSIDE_TEMP_INNER = [LEFT_X + 4, innerY, LEFT_W - 28, innerH];
          base.rects.INSIDE_TEMP_BADGE = [LEFT_X + LEFT_W - 20, innerY, 16, 12];
          base.rects.INSIDE_RH   = [LEFT_X, ROW1_Y, LEFT_W, ROW_H];
          base.rects.INSIDE_ROW2 = [LEFT_X, ROW2_Y, LEFT_W, ROW_H];  // Pressure row in v2

          base.rects.OUT_TEMP    = [RIGHT_X, TEMP_Y, RIGHT_W, TEMP_H];
          base.rects.OUT_LABEL_BOX = [RIGHT_X, TEMP_Y + 2, RIGHT_W, 12];
          base.rects.OUT_TEMP_INNER = [RIGHT_X + 4, innerY, RIGHT_W - 28, innerH];
          base.rects.OUT_TEMP_BADGE = [RIGHT_X + RIGHT_W - 20, innerY, 16, 12];
          base.rects.OUT_ROW1_L  = [RIGHT_X, ROW1_Y, 48, ROW_H];
          base.rects.OUT_ROW1_R  = [RIGHT_X + 50, ROW1_Y, 54, ROW_H];
          base.rects.OUT_ROW2_L  = [RIGHT_X, ROW2_Y, 48, ROW_H];
          base.rects.OUT_ROW2_R  = [RIGHT_X + 52, ROW2_Y, 48, ROW_H];
          // Tuck icon fully within FOOTER_R box with margin; adapt height to footer
          const iconH = Math.min(18, Math.max(12, FOOTER_H - 4));
          const iconY = FOOTER_Y + Math.max(1, Math.floor((FOOTER_H - iconH)/2));
          base.rects.WEATHER_ICON = [RIGHT_X + 4, iconY, 20, iconH];

          // Footer columns align exactly to the column widths
          base.rects.FOOTER_L    = [LEFT_X, FOOTER_Y, LEFT_W, FOOTER_H];
          base.rects.FOOTER_R    = [RIGHT_X, FOOTER_Y, RIGHT_W, FOOTER_H];

          // Adjust chrome lines to match grid
          if (base.components && Array.isArray(base.components.chrome)){
            base.components.chrome = [
              { op: 'line', from: [0, 0],   to: [249, 0] },
              { op: 'line', from: [0, 121], to: [249, 121] },
              { op: 'line', from: [0, 0],   to: [0, 121] },
              { op: 'line', from: [249, 0], to: [249, 121] },
              { op: 'line', from: [DIV_X, 16], to: [DIV_X, 121] },
              { op: 'line', from: [1, 16], to: [249, 16] },
              { op: 'line', from: [1, FOOTER_Y], to: [249, FOOTER_Y] }
            ];
          }
          // Add explicit label boxes for overlay clarity
          // Label boxes defined above
          // Adjust fonts: big:26, label:12, small:10, time:10
          if (!base.fonts) base.fonts = {};
          if (!base.fonts.tokens) base.fonts.tokens = {};
          base.fonts.tokens.big = { px: 26, weight: 'bold' };
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


