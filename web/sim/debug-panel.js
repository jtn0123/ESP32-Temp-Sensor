/**
 * Enhanced Debug Panel for ESP32 Display Simulator
 * Provides comprehensive testing, debugging, and performance monitoring
 */

(function() {
  'use strict';

  // Performance metrics
  const perfMetrics = {
    renderTimes: [],
    fps: 0,
    avgRenderTime: 0,
    lastFrameTime: performance.now(),
    frameCount: 0
  };

  // Test data scenarios
  const testScenarios = {
    // Edge cases for text overflow
    text_overflow: {
      name: "Text Overflow Tests",
      scenarios: [
        { name: "Long room name", data: { room_name: "Conference Room Building A Floor 3 West Wing" }},
        { name: "Max temperature", data: { inside_temp_f: "999.9", outside_temp_f: "-999.9" }},
        { name: "Long weather", data: { weather: "Thunderstorms with heavy rain and strong winds" }},
        { name: "Max pressure", data: { pressure_hpa: "9999.9" }},
        { name: "Long IP", data: { ip: "192.168.100.200" }},
        { name: "All max values", data: { 
          room_name: "Very Long Room Name Test",
          inside_temp_f: "999.9",
          outside_temp_f: "-99.9",
          inside_hum_pct: "100",
          outside_hum_pct: "100",
          pressure_hpa: "9999",
          wind_mph: "999.9",
          co2_ppm: "9999",
          battery_percent: "100"
        }}
      ]
    },
    
    // Battery states
    battery_states: {
      name: "Battery States",
      scenarios: [
        { name: "Critical (5%)", data: { battery_percent: 5, battery_voltage: 3.3 }},
        { name: "Low (15%)", data: { battery_percent: 15, battery_voltage: 3.5 }},
        { name: "Medium (50%)", data: { battery_percent: 50, battery_voltage: 3.7 }},
        { name: "High (85%)", data: { battery_percent: 85, battery_voltage: 4.0 }},
        { name: "Full (100%)", data: { battery_percent: 100, battery_voltage: 4.2 }},
        { name: "Charging", data: { battery_percent: 75, battery_voltage: 4.1, charging: true }},
        { name: "Unknown", data: { battery_percent: -1, battery_voltage: 0 }}
      ]
    },
    
    // Weather conditions
    weather_conditions: {
      name: "Weather Icons",
      scenarios: [
        { name: "Sunny", data: { weather: "sunny", outside_temp_f: "75" }},
        { name: "Partly Cloudy", data: { weather: "partly-cloudy", outside_temp_f: "68" }},
        { name: "Cloudy", data: { weather: "cloudy", outside_temp_f: "62" }},
        { name: "Rainy", data: { weather: "rain", outside_temp_f: "55" }},
        { name: "Pouring", data: { weather: "pouring rain", outside_temp_f: "50" }},
        { name: "Thunderstorm", data: { weather: "thunderstorm", outside_temp_f: "65" }},
        { name: "Snow", data: { weather: "snow", outside_temp_f: "28" }},
        { name: "Fog", data: { weather: "fog", outside_temp_f: "45" }},
        { name: "Windy", data: { weather: "windy", wind_mph: "25.5" }},
        { name: "Night Clear", data: { weather: "clear-night", outside_temp_f: "60" }},
        { name: "Night Cloudy", data: { weather: "cloudy-night", outside_temp_f: "58" }},
        { name: "Hail", data: { weather: "hail", outside_temp_f: "35" }}
      ]
    },
    
    // Missing data scenarios
    missing_data: {
      name: "Missing Data",
      scenarios: [
        { name: "No inside data", data: { inside_temp_f: "", inside_hum_pct: "" }},
        { name: "No outside data", data: { outside_temp_f: "", outside_hum_pct: "", weather: "" }},
        { name: "No weather", data: { weather: "" }},
        { name: "No network", data: { ip: "", mqtt_status: "disconnected" }},
        { name: "Partial sensors", data: { inside_temp_f: "72", inside_hum_pct: "", pressure_hpa: "" }},
        { name: "All missing", data: { 
          inside_temp_f: "", outside_temp_f: "", 
          inside_hum_pct: "", outside_hum_pct: "",
          weather: "", ip: ""
        }}
      ]
    },
    
    // Sensor edge values
    sensor_edges: {
      name: "Sensor Limits",
      scenarios: [
        { name: "Freezing", data: { inside_temp_f: "32", outside_temp_f: "0" }},
        { name: "Below zero", data: { inside_temp_f: "-10", outside_temp_f: "-40" }},
        { name: "Extreme heat", data: { inside_temp_f: "120", outside_temp_f: "140" }},
        { name: "Dry conditions", data: { inside_hum_pct: "5", outside_hum_pct: "0" }},
        { name: "Saturated", data: { inside_hum_pct: "100", outside_hum_pct: "100" }},
        { name: "High pressure", data: { pressure_hpa: "1080" }},
        { name: "Low pressure", data: { pressure_hpa: "950" }},
        { name: "Hurricane winds", data: { wind_mph: "155" }},
        { name: "High CO2", data: { co2_ppm: "5000" }},
        { name: "Extreme UV", data: { uv_index: "15" }}
      ]
    },
    
    // Time formats
    time_formats: {
      name: "Time Display",
      scenarios: [
        { name: "Morning", data: { time_hhmm: "6:30" }},
        { name: "Noon", data: { time_hhmm: "12:00" }},
        { name: "Afternoon", data: { time_hhmm: "3:45" }},
        { name: "Evening", data: { time_hhmm: "8:15" }},
        { name: "Midnight", data: { time_hhmm: "12:00" }},
        { name: "24-hour", data: { time_hhmm: "23:59" }},
        { name: "Single digit", data: { time_hhmm: "9:05" }}
      ]
    },
    
    // Special characters
    special_chars: {
      name: "Special Characters",
      scenarios: [
        { name: "Unicode room", data: { room_name: "Café ñ École 日本" }},
        { name: "Symbols", data: { room_name: "Lab #3 & Testing @ 50%" }},
        { name: "Degrees", data: { inside_temp_f: "72.5°", outside_temp_f: "68.4°" }},
        { name: "Quotes", data: { weather: "light 'rain' expected" }},
        { name: "Math symbols", data: { room_name: "Room > 100 < 200" }}
      ]
    }
  };

  // Create debug panel UI
  function createDebugPanel() {
    const panel = document.createElement('div');
    panel.id = 'advancedDebugPanel';
    panel.innerHTML = `
      <details style="margin-top:8px;">
        <summary>🔧 Advanced Debug Tools</summary>
        
        <div style="margin-top:10px;">
          <!-- Performance Monitor -->
          <fieldset style="margin-bottom:10px;padding:8px;">
            <legend>⚡ Performance</legend>
            <div id="perfMonitor" style="font-family:monospace;font-size:11px;">
              <div>FPS: <span id="debugFPS">0</span></div>
              <div>Render: <span id="debugRenderTime">0</span>ms</div>
              <div>Frames: <span id="debugFrameCount">0</span></div>
            </div>
            <button id="perfReset" style="margin-top:4px;">Reset</button>
            <label style="margin-left:8px;">
              <input type="checkbox" id="perfAutoLog"> Auto-log
            </label>
          </fieldset>
          
          <!-- Test Scenarios -->
          <fieldset style="margin-bottom:10px;padding:8px;">
            <legend>🧪 Test Scenarios</legend>
            <select id="scenarioCategory" style="width:100%;margin-bottom:4px;">
              <option value="">Select category...</option>
            </select>
            <select id="scenarioList" style="width:100%;margin-bottom:4px;" disabled>
              <option value="">Select scenario...</option>
            </select>
            <button id="applyScenario" disabled>Apply</button>
            <button id="randomScenario" style="margin-left:4px;">Random</button>
            <button id="cycleScenarios" style="margin-left:4px;">Cycle All</button>
          </fieldset>
          
          <!-- Data Editor -->
          <fieldset style="margin-bottom:10px;padding:8px;">
            <legend>✏️ Data Editor</legend>
            <div id="dataFields" style="max-height:200px;overflow-y:auto;">
              <!-- Dynamic fields will be added here -->
            </div>
            <button id="applyData" style="margin-top:4px;">Apply Changes</button>
            <button id="resetData" style="margin-left:4px;">Reset</button>
            <button id="exportData" style="margin-left:4px;">Export</button>
            <button id="importData" style="margin-left:4px;">Import</button>
          </fieldset>
          
          <!-- Visual Testing -->
          <fieldset style="margin-bottom:10px;padding:8px;">
            <legend>👁️ Visual Testing</legend>
            <button id="captureBaseline">Capture Baseline</button>
            <button id="compareVisual" style="margin-left:4px;">Compare</button>
            <button id="showDiff" style="margin-left:4px;" disabled>Show Diff</button>
            <div id="visualDiff" style="margin-top:8px;"></div>
          </fieldset>
          
          <!-- Icon Tester -->
          <fieldset style="margin-bottom:10px;padding:8px;">
            <legend>🎨 Icon Tester</legend>
            <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:4px;">
              <button class="icon-test" data-weather="sunny">☀️</button>
              <button class="icon-test" data-weather="partly-cloudy">⛅</button>
              <button class="icon-test" data-weather="cloudy">☁️</button>
              <button class="icon-test" data-weather="rain">🌧️</button>
              <button class="icon-test" data-weather="pouring">🌧️</button>
              <button class="icon-test" data-weather="thunderstorm">⛈️</button>
              <button class="icon-test" data-weather="snow">❄️</button>
              <button class="icon-test" data-weather="fog">🌫️</button>
              <button class="icon-test" data-weather="windy">💨</button>
              <button class="icon-test" data-weather="night">🌙</button>
              <button class="icon-test" data-weather="night-cloudy">☁️🌙</button>
              <button class="icon-test" data-weather="hail">🧊</button>
            </div>
            <input type="text" id="customWeather" placeholder="Custom weather text" style="width:100%;margin-top:4px;">
            <button id="testCustomWeather" style="margin-top:4px;">Test Custom</button>
          </fieldset>
          
          <!-- State Inspector -->
          <fieldset style="margin-bottom:10px;padding:8px;">
            <legend>🔍 State Inspector</legend>
            <div id="stateInspector" style="font-family:monospace;font-size:10px;max-height:150px;overflow-y:auto;">
              <!-- State will be displayed here -->
            </div>
            <button id="refreshState">Refresh</button>
            <button id="copyState" style="margin-left:4px;">Copy</button>
          </fieldset>
          
          <!-- Console -->
          <fieldset style="margin-bottom:10px;padding:8px;">
            <legend>📝 Debug Console</legend>
            <div id="debugConsole" style="font-family:monospace;font-size:10px;max-height:100px;overflow-y:auto;background:#f0f0f0;padding:4px;">
              <!-- Log messages here -->
            </div>
            <button id="clearConsole">Clear</button>
            <label style="margin-left:8px;">
              <input type="checkbox" id="verboseLogging"> Verbose
            </label>
          </fieldset>
        </div>
      </details>
    `;
    
    return panel;
  }

  // Initialize data fields
  function initDataFields() {
    const container = document.getElementById('dataFields');
    if (!container) return;
    
    const fields = [
      'room_name', 'time_hhmm', 'fw_version',
      'inside_temp_f', 'inside_hum_pct', 'pressure_hpa', 'co2_ppm',
      'outside_temp_f', 'outside_hum_pct', 'wind_mph', 'weather', 'uv_index', 'rain_mm',
      'battery_percent', 'battery_voltage', 'ip', 'days'
    ];
    
    container.innerHTML = fields.map(field => `
      <div style="margin-bottom:4px;">
        <label style="display:inline-block;width:120px;font-size:11px;">${field}:</label>
        <input type="text" id="field_${field}" style="width:120px;font-size:11px;" 
               placeholder="${getDefaultValue(field)}">
      </div>
    `).join('');
  }

  // Get default value for field
  function getDefaultValue(field) {
    const defaults = window.DEFAULTS || {};
    return defaults[field] || '';
  }

  // Update performance metrics
  function updatePerformance() {
    const now = performance.now();
    const frameTime = now - perfMetrics.lastFrameTime;
    
    perfMetrics.frameCount++;
    perfMetrics.renderTimes.push(frameTime);
    
    // Keep last 60 frames
    if (perfMetrics.renderTimes.length > 60) {
      perfMetrics.renderTimes.shift();
    }
    
    // Calculate metrics
    perfMetrics.fps = Math.round(1000 / frameTime);
    perfMetrics.avgRenderTime = perfMetrics.renderTimes.reduce((a, b) => a + b, 0) / perfMetrics.renderTimes.length;
    
    // Update display
    const fpsEl = document.getElementById('debugFPS');
    const renderEl = document.getElementById('debugRenderTime');
    const countEl = document.getElementById('debugFrameCount');
    
    if (fpsEl) fpsEl.textContent = perfMetrics.fps;
    if (renderEl) renderEl.textContent = perfMetrics.avgRenderTime.toFixed(2);
    if (countEl) countEl.textContent = perfMetrics.frameCount;
    
    perfMetrics.lastFrameTime = now;
  }

  // Log to debug console
  function debugLog(message, type = 'info') {
    const console = document.getElementById('debugConsole');
    if (!console) return;
    
    const timestamp = new Date().toISOString().split('T')[1].split('.')[0];
    const typeIcon = {
      info: 'ℹ️',
      warn: '⚠️',
      error: '❌',
      success: '✅'
    }[type] || 'ℹ️';
    
    const entry = document.createElement('div');
    entry.innerHTML = `<span style="color:#666;">${timestamp}</span> ${typeIcon} ${message}`;
    console.appendChild(entry);
    console.scrollTop = console.scrollHeight;
    
    // Limit to 100 entries
    while (console.children.length > 100) {
      console.removeChild(console.firstChild);
    }
  }

  // Capture baseline for visual testing
  let baselineImage = null;
  
  function captureBaseline() {
    const canvas = document.getElementById('epd');
    if (!canvas) return;
    
    baselineImage = canvas.toDataURL();
    debugLog('Baseline captured', 'success');
    
    const compareBtn = document.getElementById('compareVisual');
    if (compareBtn) compareBtn.disabled = false;
  }

  // Compare current with baseline
  function compareVisual() {
    const canvas = document.getElementById('epd');
    if (!canvas || !baselineImage) return;
    
    const currentImage = canvas.toDataURL();
    
    // Create comparison canvas
    const diffCanvas = document.createElement('canvas');
    diffCanvas.width = canvas.width;
    diffCanvas.height = canvas.height;
    const ctx = diffCanvas.getContext('2d');
    
    // Load images
    const baseline = new Image();
    const current = new Image();
    
    baseline.onload = () => {
      current.onload = () => {
        // Draw baseline
        ctx.drawImage(baseline, 0, 0);
        const baselineData = ctx.getImageData(0, 0, canvas.width, canvas.height);
        
        // Draw current
        ctx.drawImage(current, 0, 0);
        const currentData = ctx.getImageData(0, 0, canvas.width, canvas.height);
        
        // Calculate diff
        let differences = 0;
        const diffData = ctx.createImageData(canvas.width, canvas.height);
        
        for (let i = 0; i < baselineData.data.length; i += 4) {
          const diff = Math.abs(baselineData.data[i] - currentData.data[i]) +
                       Math.abs(baselineData.data[i+1] - currentData.data[i+1]) +
                       Math.abs(baselineData.data[i+2] - currentData.data[i+2]);
          
          if (diff > 0) {
            differences++;
            // Highlight differences in red
            diffData.data[i] = 255;
            diffData.data[i+1] = 0;
            diffData.data[i+2] = 0;
            diffData.data[i+3] = 128;
          } else {
            // Show unchanged in gray
            diffData.data[i] = currentData.data[i];
            diffData.data[i+1] = currentData.data[i+1];
            diffData.data[i+2] = currentData.data[i+2];
            diffData.data[i+3] = 64;
          }
        }
        
        ctx.putImageData(diffData, 0, 0);
        
        // Display diff
        const diffContainer = document.getElementById('visualDiff');
        if (diffContainer) {
          const pixels = canvas.width * canvas.height;
          const percentage = ((differences / pixels) * 100).toFixed(2);
          
          diffContainer.innerHTML = `
            <div style="margin-bottom:4px;">Differences: ${differences} pixels (${percentage}%)</div>
            <img src="${diffCanvas.toDataURL()}" style="width:250px;border:1px solid #ccc;">
          `;
          
          debugLog(`Visual diff: ${percentage}% changed`, differences > 0 ? 'warn' : 'success');
        }
      };
      current.src = currentImage;
    };
    baseline.src = baselineImage;
  }

  // Update state inspector
  function updateStateInspector() {
    const inspector = document.getElementById('stateInspector');
    if (!inspector) return;
    
    const state = {
      lastData: window.lastData || {},
      UI_SPEC: window.UI_SPEC ? Object.keys(window.UI_SPEC) : [],
      validationIssues: window.validationIssues || [],
      regionVisible: window.regionVisible ? Array.from(window.regionVisible) : [],
      metrics: window.__layoutMetrics || {}
    };
    
    inspector.innerHTML = `<pre>${JSON.stringify(state, null, 2)}</pre>`;
  }

  // Setup event handlers
  function setupEventHandlers() {
    // Performance reset
    document.getElementById('perfReset')?.addEventListener('click', () => {
      perfMetrics.renderTimes = [];
      perfMetrics.frameCount = 0;
      debugLog('Performance metrics reset', 'info');
    });
    
    // Scenario selection
    const categorySelect = document.getElementById('scenarioCategory');
    const scenarioSelect = document.getElementById('scenarioList');
    const applyBtn = document.getElementById('applyScenario');
    
    if (categorySelect) {
      // Populate categories
      categorySelect.innerHTML = '<option value="">Select category...</option>' +
        Object.keys(testScenarios).map(key => 
          `<option value="${key}">${testScenarios[key].name}</option>`
        ).join('');
      
      categorySelect.addEventListener('change', (e) => {
        const category = e.target.value;
        if (category && testScenarios[category]) {
          scenarioSelect.disabled = false;
          scenarioSelect.innerHTML = '<option value="">Select scenario...</option>' +
            testScenarios[category].scenarios.map((s, i) => 
              `<option value="${i}">${s.name}</option>`
            ).join('');
        } else {
          scenarioSelect.disabled = true;
          applyBtn.disabled = true;
        }
      });
    }
    
    if (scenarioSelect) {
      scenarioSelect.addEventListener('change', (e) => {
        applyBtn.disabled = !e.target.value;
      });
    }
    
    if (applyBtn) {
      applyBtn.addEventListener('click', () => {
        const category = categorySelect.value;
        const index = scenarioSelect.value;
        if (category && index !== '' && testScenarios[category]) {
          const scenario = testScenarios[category].scenarios[index];
          if (scenario && window.draw) {
            window.draw(scenario.data);
            debugLog(`Applied scenario: ${scenario.name}`, 'success');
          }
        }
      });
    }
    
    // Random scenario
    document.getElementById('randomScenario')?.addEventListener('click', () => {
      const categories = Object.keys(testScenarios);
      const category = categories[Math.floor(Math.random() * categories.length)];
      const scenarios = testScenarios[category].scenarios;
      const scenario = scenarios[Math.floor(Math.random() * scenarios.length)];
      
      if (scenario && window.draw) {
        window.draw(scenario.data);
        debugLog(`Random scenario: ${category} - ${scenario.name}`, 'info');
      }
    });
    
    // Cycle scenarios
    let cycleInterval = null;
    document.getElementById('cycleScenarios')?.addEventListener('click', (e) => {
      if (cycleInterval) {
        clearInterval(cycleInterval);
        cycleInterval = null;
        e.target.textContent = 'Cycle All';
        debugLog('Stopped scenario cycling', 'info');
      } else {
        e.target.textContent = 'Stop Cycling';
        let index = 0;
        const allScenarios = [];
        
        Object.values(testScenarios).forEach(cat => {
          cat.scenarios.forEach(s => allScenarios.push(s));
        });
        
        cycleInterval = setInterval(() => {
          const scenario = allScenarios[index % allScenarios.length];
          if (scenario && window.draw) {
            window.draw(scenario.data);
            debugLog(`Cycle: ${scenario.name}`, 'info');
          }
          index++;
        }, 2000);
      }
    });
    
    // Data editor
    document.getElementById('applyData')?.addEventListener('click', () => {
      const data = {};
      const inputs = document.querySelectorAll('#dataFields input');
      inputs.forEach(input => {
        const field = input.id.replace('field_', '');
        if (input.value) {
          // Parse numeric values properly
          const value = input.value;
          if (field.includes('temp') || field.includes('hum') || field.includes('percent') || 
              field.includes('voltage') || field.includes('mph') || field.includes('hpa') || 
              field.includes('ppm') || field.includes('index') || field.includes('mm')) {
            const num = parseFloat(value);
            data[field] = isNaN(num) ? value : num;
          } else {
            data[field] = value;
          }
        }
      });
      
      if (window.draw) {
        window.draw(data);
        debugLog(`Applied custom data: ${JSON.stringify(data)}`, 'success');
      } else {
        debugLog('Error: draw function not available', 'error');
      }
    });
    
    document.getElementById('resetData')?.addEventListener('click', () => {
      document.querySelectorAll('#dataFields input').forEach(input => {
        input.value = '';
      });
      if (window.draw) {
        window.draw({});
        debugLog('Reset to defaults', 'info');
      }
    });
    
    // Visual testing
    document.getElementById('captureBaseline')?.addEventListener('click', captureBaseline);
    document.getElementById('compareVisual')?.addEventListener('click', compareVisual);
    
    // Icon testing
    document.querySelectorAll('.icon-test').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const weather = e.target.dataset.weather;
        if (window.draw) {
          window.draw({ weather });
          debugLog(`Testing icon: ${weather}`, 'info');
        }
      });
    });
    
    document.getElementById('testCustomWeather')?.addEventListener('click', () => {
      const input = document.getElementById('customWeather');
      if (input && input.value && window.draw) {
        window.draw({ weather: input.value });
        debugLog(`Testing custom weather: ${input.value}`, 'info');
      }
    });
    
    // State inspector
    document.getElementById('refreshState')?.addEventListener('click', updateStateInspector);
    
    document.getElementById('copyState')?.addEventListener('click', () => {
      const inspector = document.getElementById('stateInspector');
      if (inspector) {
        navigator.clipboard.writeText(inspector.textContent);
        debugLog('State copied to clipboard', 'success');
      }
    });
    
    // Console
    document.getElementById('clearConsole')?.addEventListener('click', () => {
      const console = document.getElementById('debugConsole');
      if (console) console.innerHTML = '';
    });
    
    // Export/Import data
    document.getElementById('exportData')?.addEventListener('click', () => {
      const data = window.lastData || {};
      const json = JSON.stringify(data, null, 2);
      const blob = new Blob([json], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `display-data-${Date.now()}.json`;
      a.click();
      debugLog('Data exported', 'success');
    });
    
    document.getElementById('importData')?.addEventListener('click', () => {
      const input = document.createElement('input');
      input.type = 'file';
      input.accept = '.json';
      input.onchange = (e) => {
        const file = e.target.files[0];
        if (file) {
          const reader = new FileReader();
          reader.onload = (e) => {
            try {
              const data = JSON.parse(e.target.result);
              if (window.draw) {
                window.draw(data);
                debugLog('Data imported', 'success');
              }
            } catch (err) {
              debugLog(`Import error: ${err.message}`, 'error');
            }
          };
          reader.readAsText(file);
        }
      };
      input.click();
    });
  }

  // Hook into draw function for performance monitoring
  function wrapDrawFunction() {
    if (window.draw && !window.draw._wrapped) {
      const originalDraw = window.draw;
      window.draw = function(data) {
        const startTime = performance.now();
        originalDraw.call(this, data);
        const endTime = performance.now();
        
        // Update performance metrics
        updatePerformance();
        
        // Log if verbose
        if (document.getElementById('verboseLogging')?.checked) {
          debugLog(`Draw completed in ${(endTime - startTime).toFixed(2)}ms`, 'info');
        }
      };
      window.draw._wrapped = true;
    }
  }

  // Initialize when DOM is ready
  function init() {
    // Find insertion point
    const validationPanel = document.getElementById('validationPanel');
    if (validationPanel) {
      const debugPanel = createDebugPanel();
      validationPanel.parentNode.insertBefore(debugPanel, validationPanel.nextSibling);
      
      initDataFields();
      setupEventHandlers();
      updateStateInspector();
      
      // Wrap draw function for monitoring
      wrapDrawFunction();
      
      debugLog('Debug panel initialized', 'success');
      
      // Start performance monitoring
      setInterval(updatePerformance, 1000);
      
      // Check if draw function is available
      if (!window.draw) {
        debugLog('Warning: draw function not yet available', 'warn');
        // Try to wrap it later
        setTimeout(wrapDrawFunction, 500);
      }
    } else {
      // Retry after a delay
      setTimeout(init, 100);
    }
  }

  // Start initialization
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();