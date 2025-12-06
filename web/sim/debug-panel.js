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

  // Test data scenarios - expanded with more edge cases
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
        { name: "Decimal precision", data: { 
          inside_temp_f: "72.3456",
          pressure_hpa: "1013.25678",
          battery_voltage: "4.0123456"
        }},
        { name: "Very long version", data: { fw_version: "1.2.3-beta.456+build789" }},
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
    },
    
    // Refresh and power scenarios
    refresh_scenarios: {
      name: "Display Refresh",
      scenarios: [
        { name: "Minimal change", data: { time_hhmm: "10:33" }}, // Only time changes
        { name: "Temperature only", data: { inside_temp_f: "72.6" }},
        { name: "All sensors", data: { 
          inside_temp_f: "73.0", 
          inside_hum_pct: "48",
          outside_temp_f: "69.0",
          pressure_hpa: "1014.0"
        }},
        { name: "Weather change", data: { weather: "rain", wind_mph: "15.5" }},
        { name: "Battery critical", data: { battery_percent: "3", battery_voltage: "3.2" }},
        { name: "Network change", data: { ip: "10.0.0.1" }}
      ]
    },
    
    // Real-world data patterns
    real_world: {
      name: "Real World Data",
      scenarios: [
        { name: "Morning", data: { 
          time_hhmm: "6:30",
          inside_temp_f: "65.2",
          inside_hum_pct: "52",
          outside_temp_f: "48.5",
          weather: "partly-cloudy"
        }},
        { name: "Hot afternoon", data: {
          time_hhmm: "14:45",
          inside_temp_f: "78.5",
          inside_hum_pct: "35",
          outside_temp_f: "95.2",
          weather: "sunny",
          wind_mph: "8.5"
        }},
        { name: "Rainy evening", data: {
          time_hhmm: "19:20",
          inside_temp_f: "72.0",
          inside_hum_pct: "65",
          outside_temp_f: "58.0",
          weather: "rain",
          pressure_hpa: "1008.5"
        }},
        { name: "Winter night", data: {
          time_hhmm: "23:15",
          inside_temp_f: "68.0",
          inside_hum_pct: "28",
          outside_temp_f: "12.5",
          weather: "clear-night",
          wind_mph: "2.0"
        }},
        { name: "Storm warning", data: {
          inside_temp_f: "71.0",
          outside_temp_f: "65.0",
          pressure_hpa: "985.0",
          weather: "thunderstorm",
          wind_mph: "35.5"
        }}
      ]
    },
    
    // Error states
    error_states: {
      name: "Error States",
      scenarios: [
        { name: "Sensor error", data: { inside_temp_f: "ERR", inside_hum_pct: "ERR" }},
        { name: "Network down", data: { ip: "0.0.0.0", mqtt_status: "disconnected" }},
        { name: "Invalid JSON", data: { room_name: null, time_hhmm: undefined }},
        { name: "NaN values", data: { inside_temp_f: NaN, battery_percent: "NaN" }},
        { name: "Empty strings", data: { room_name: "", weather: "", ip: "" }},
        { name: "Negative battery", data: { battery_percent: "-10", battery_voltage: "-1" }}
      ]
    }
  };

  // Create debug panel UI
  function createDebugPanel() {
    const panel = document.createElement('div');
    panel.id = 'advancedDebugPanel';
    panel.innerHTML = `
      <details id="advancedDebugDetails" class="card">
        <summary>🔧 Advanced Debug Tools</summary>
        <div class="debug-body">
          <fieldset class="fieldset">
            <legend>⚡ Performance</legend>
            <div id="perfMonitor" class="muted" style="font-family:monospace;font-size:11px;">
              <div>FPS: <span id="debugFPS">0</span></div>
              <div>Render: <span id="debugRenderTime">0</span>ms</div>
              <div>Frames: <span id="debugFrameCount">0</span></div>
            </div>
            <button id="perfReset">Reset</button>
            <label>
              <input type="checkbox" id="perfAutoLog"> Auto-log
            </label>
          </fieldset>

          <fieldset class="fieldset">
            <legend>🎯 Debug Overlay</legend>
            <label>
              <input type="checkbox" id="debugOverlayEnabled"> Enable Overlay
            </label>
            <label>
              <input type="checkbox" id="debugOverlayBounds" disabled> Region Bounds
            </label>
            <label>
              <input type="checkbox" id="debugOverlayTiming" disabled> Render Timing
            </label>
            <div style="margin-top:4px;font-size:11px;">
              <label>Highlight Data:
                <select id="debugOverlayHighlight" style="width:120px;" disabled>
                  <option value="">None</option>
                  <option value="room_name">Room Name</option>
                  <option value="inside_temp">Inside Temp</option>
                  <option value="outside_temp">Outside Temp</option>
                  <option value="humidity">Humidity</option>
                  <option value="pressure">Pressure</option>
                  <option value="weather">Weather</option>
                  <option value="battery">Battery</option>
                  <option value="time">Time</option>
                </select>
              </label>
            </div>
            <div id="debugOverlayInfo" class="muted" style="font-size:10px;margin-top:4px;display:none;">
              Keyboard: Ctrl+Shift+D to toggle
            </div>
          </fieldset>

          <fieldset class="fieldset">
            <legend>🌡️ Live Simulation</legend>
            <div style="margin-bottom:6px;">
              <button id="liveSimStart" class="sim-btn">▶ Start</button>
              <button id="liveSimStop" class="sim-btn" disabled>⏹ Stop</button>
              <span id="liveSimStatus" class="muted" style="margin-left:8px;">Stopped</span>
            </div>
            <div class="form-row" style="margin-bottom:4px;">
              <label style="font-size:11px;">Speed: 
                <select id="liveSimSpeed" style="width:80px;">
                  <option value="1">1x (Real)</option>
                  <option value="60" selected>60x (1s = 1min)</option>
                  <option value="600">600x (1s = 10min)</option>
                  <option value="3600">3600x (1s = 1hr)</option>
                </select>
              </label>
              <label style="font-size:11px;">Season:
                <select id="liveSimSeason" style="width:80px;">
                  <option value="spring">Spring</option>
                  <option value="summer">Summer</option>
                  <option value="fall">Fall</option>
                  <option value="winter">Winter</option>
                </select>
              </label>
            </div>
            <div class="form-row" style="margin-bottom:4px;">
              <label style="font-size:11px;">Geography:
                <select id="liveSimGeo" style="width:90px;">
                  <option value="midwest">Midwest</option>
                  <option value="coastal">Coastal</option>
                  <option value="desert">Desert</option>
                  <option value="mountain">Mountain</option>
                  <option value="tropical">Tropical</option>
                </select>
              </label>
              <label style="font-size:11px;">Weather:
                <select id="liveSimWeather" style="width:90px;">
                  <option value="sunny">Sunny</option>
                  <option value="partly-cloudy">Partly Cloudy</option>
                  <option value="cloudy">Cloudy</option>
                  <option value="rainy">Rainy</option>
                  <option value="thunderstorm">Thunderstorm</option>
                  <option value="snow">Snow</option>
                  <option value="fog">Fog</option>
                  <option value="windy">Windy</option>
                </select>
              </label>
            </div>
          </fieldset>

          <fieldset class="fieldset">
            <legend>🎬 Realistic Scenarios</legend>
            <select id="realisticPreset" style="width:100%;margin-bottom:4px;">
              <option value="">Select a preset...</option>
              <optgroup label="Time of Day">
                <option value="early_morning">Early Morning (6:15 AM, foggy)</option>
                <option value="hot_afternoon">Hot Afternoon (2:30 PM, desert)</option>
                <option value="rainy_evening">Rainy Evening (7:45 PM)</option>
                <option value="cold_night">Cold Night (11:30 PM, winter)</option>
              </optgroup>
              <optgroup label="Weather Events">
                <option value="thunderstorm">Thunderstorm</option>
                <option value="snow_day">Snow Day (mountain)</option>
                <option value="windy_day">Windy Day</option>
              </optgroup>
              <optgroup label="Battery States">
                <option value="battery_critical">Battery Critical (5%)</option>
                <option value="battery_charging">Battery Charging</option>
              </optgroup>
              <optgroup label="Geographic">
                <option value="coastal_morning">Coastal Morning</option>
                <option value="tropical_afternoon">Tropical Afternoon</option>
                <option value="mountain_cabin">Mountain Cabin</option>
              </optgroup>
              <optgroup label="Extreme Conditions">
                <option value="extreme_cold">Extreme Cold (-35°F)</option>
                <option value="extreme_heat">Extreme Heat (118°F)</option>
                <option value="high_humidity">High Humidity (98%)</option>
              </optgroup>
            </select>
            <button id="applyRealisticPreset">Apply Preset</button>
            <button id="randomRealisticPreset">Random</button>
          </fieldset>

          <fieldset class="fieldset">
            <legend>🧪 Test Scenarios</legend>
            <select id="scenarioCategory" style="width:100%;margin-bottom:4px;">
              <option value="">Select category...</option>
            </select>
            <select id="scenarioList" style="width:100%;margin-bottom:4px;" disabled>
              <option value="">Select scenario...</option>
            </select>
            <button id="applyScenario" disabled>Apply</button>
            <button id="randomScenario">Random</button>
            <button id="cycleScenarios">Cycle All</button>
          </fieldset>

          <fieldset class="fieldset">
            <legend>✏️ Data Editor</legend>
            <div id="dataFields" style="max-height:200px;overflow-y:auto;"></div>
            <button id="applyData">Apply Changes</button>
            <button id="resetData">Reset</button>
            <button id="exportData">Export</button>
            <button id="importData">Import</button>
          </fieldset>

          <fieldset class="fieldset">
            <legend>👁️ Visual Testing</legend>
            <div class="toolbar-row">
              <button id="captureBaseline">Capture Baseline</button>
              <button id="compareVisual">Compare</button>
              <button id="showDiff" disabled>Show Diff</button>
              <button id="downloadBaseline" disabled>Download Baseline</button>
              <button id="downloadCurrent" disabled>Download Current</button>
              <button id="downloadDiff" disabled>Download Diff</button>
            </div>
            <div id="visualGallery"></div>
            <div id="visualDiff" style="display:none"></div>
          </fieldset>

          <fieldset class="fieldset">
            <legend>📷 Device Comparison</legend>
            <div style="margin-bottom:6px;">
              <input type="file" id="deviceScreenshot" accept="image/*" style="font-size:11px;max-width:150px;">
              <button id="clearDeviceScreenshot" disabled>Clear</button>
            </div>
            <div style="margin-bottom:6px;">
              <button id="captureFromDevice" title="Capture screenshot from connected device via MQTT">📸 Capture from Device</button>
              <input type="text" id="targetDeviceId" placeholder="Device ID (optional)" style="font-size:11px;max-width:120px;" title="Leave empty to use current MQTT device ID">
              <span id="captureStatus" style="font-size:11px;margin-left:6px;"></span>
            </div>
            <div id="deviceCompareContainer" style="display:none;">
              <div style="margin-bottom:6px;display:flex;gap:8px;">
                <button id="toggleCompareView">Toggle View</button>
                <button id="compareWithDevice">Compare</button>
                <label style="font-size:11px;display:flex;align-items:center;gap:4px;">
                  <input type="range" id="deviceOpacity" min="0" max="100" value="50" style="width:60px;">
                  Opacity
                </label>
              </div>
              <div id="deviceCompareView" style="position:relative;display:inline-block;border:1px solid #ccc;"></div>
              <div id="deviceCompareResults" style="margin-top:8px;font-size:11px;"></div>
            </div>
          </fieldset>

          <fieldset class="fieldset">
            <legend>📡 Remote Commands</legend>
            <div style="margin-bottom:8px;">
              <select id="remoteCommand" style="max-width:150px;">
                <option value="">Select command...</option>
                <option value="heap">Heap Status</option>
                <option value="sensors">Sensor Readings</option>
                <option value="state">Device State</option>
                <option value="config">Configuration</option>
                <option value="uptime">Uptime</option>
                <option value="network">Network Status</option>
                <option value="perf">Performance Stats</option>
                <option value="bufpool">Buffer Pool</option>
                <option value="crash">Crash Info</option>
                <option value="memory">Memory Tracking</option>
                <option value="features">Features</option>
                <option value="mqtt_batch">MQTT Batching</option>
                <option value="smart_refresh">Smart Refresh</option>
                <option value="screenshot">Screenshot</option>
                <option value="restart">Restart Device</option>
              </select>
              <button id="sendRemoteCommand" disabled>Send</button>
            </div>
            <div id="commandResponseContainer" style="display:none;">
              <label style="font-size:11px;font-weight:bold;">Response:</label>
              <pre id="commandResponse" style="background:#f5f5f5;padding:8px;border:1px solid #ddd;max-height:200px;overflow-y:auto;font-size:10px;margin:4px 0;"></pre>
              <button id="clearResponse">Clear</button>
              <button id="copyResponse">Copy</button>
            </div>
          </fieldset>

          <fieldset class="fieldset">
            <legend>🎨 Icon Tester</legend>
            <div class="icon-grid" style="display:grid;grid-template-columns:repeat(4,1fr);gap:4px;">
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
            <input type="text" id="customWeather" placeholder="Custom weather text">
            <button id="testCustomWeather">Test Custom</button>
          </fieldset>

          <fieldset class="fieldset">
            <legend>📐 Region Metrics</legend>
            <div style="margin-bottom:6px;">
              <label><input type="checkbox" id="showRegionMetrics"> Show metrics overlay</label>
              <label style="margin-left:8px;"><input type="checkbox" id="highlightOverflow"> Highlight overflow</label>
            </div>
            <div id="regionMetricsTable" style="max-height:200px;overflow-y:auto;font-size:10px;font-family:monospace;"></div>
            <div style="margin-top:4px;">
              <button id="refreshMetrics">Refresh</button>
              <button id="exportMetrics">Export JSON</button>
              <button id="copyMetrics">Copy</button>
            </div>
          </fieldset>

          <fieldset class="fieldset">
            <legend>🔍 State Inspector</legend>
            <div id="stateInspector"></div>
            <button id="refreshState">Refresh</button>
            <button id="copyState">Copy</button>
          </fieldset>

          <fieldset class="fieldset">
            <legend>📝 Debug Console</legend>
            <div id="debugConsole" class="console"></div>
            <button id="clearConsole">Clear</button>
            <label>
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
      'outside_temp_f', 'outside_hum_pct', 'outside_pressure_hpa', 'wind_mph', 'weather', 'uv_index', 'rain_mm',
      'battery_percent', 'battery_voltage', 'ip', 'days'
    ];
    
    container.innerHTML = fields.map(field => `
      <div class="data-field">
        <label class="data-label">${field}:</label>
        <input type="text" id="field_${field}" class="data-input" placeholder="${getDefaultValue(field)}">
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
    entry.innerHTML = `<span class="muted">${timestamp}</span> ${typeIcon} ${message}`;
    console.appendChild(entry);
    console.scrollTop = console.scrollHeight;
    
    // Limit to 100 entries
    while (console.children.length > 100) {
      console.removeChild(console.firstChild);
    }
  }

  // Capture baseline for visual testing
  let baselineImage = null;
  let lastDiffImage = null;
  
  function captureBaseline() {
    const canvas = document.getElementById('epd');
    if (!canvas) return;
    
    baselineImage = canvas.toDataURL();
    debugLog('Baseline captured', 'success');
    
    const compareBtn = document.getElementById('compareVisual');
    if (compareBtn) compareBtn.disabled = false;
  }

  // Compare current with baseline with enhanced color-coded diff
  function compareVisual() {
    const canvas = document.getElementById('epd');
    if (!canvas || !baselineImage) return;
    
    const currentImage = canvas.toDataURL();
    
    // Create comparison canvas
    const diffCanvas = document.createElement('canvas');
    diffCanvas.width = canvas.width;
    diffCanvas.height = canvas.height;
    const ctx = diffCanvas.getContext('2d');
    if (!ctx) {
      console.warn('Failed to create 2D context for baseline comparison');
      return;
    }
    
    // Load images
    const baseline = new Image();
    const current = new Image();
    
    // Handle image load errors
    baseline.onerror = () => {
      console.warn('Failed to load baseline image');
    };
    current.onerror = () => {
      console.warn('Failed to load current image');
    };
    
    baseline.onload = () => {
      current.onload = () => {
        // Draw baseline
        ctx.drawImage(baseline, 0, 0);
        const baselineData = ctx.getImageData(0, 0, canvas.width, canvas.height);
        
        // Draw current
        ctx.drawImage(current, 0, 0);
        const currentData = ctx.getImageData(0, 0, canvas.width, canvas.height);
        
        // Validate data arrays exist and match
        if (!baselineData?.data || !currentData?.data) {
          console.warn('Baseline comparison: missing image data');
          return;
        }
        if (baselineData.data.length !== currentData.data.length) {
          console.warn('Baseline comparison: data length mismatch');
          return;
        }
        
        // Guard against zero-dimension canvas
        if (canvas.width === 0 || canvas.height === 0) {
          console.warn('Baseline comparison: canvas has zero dimensions');
          return;
        }
        
        // Calculate diff with intensity tracking
        let differences = 0;
        let slightDiffs = 0;
        let majorDiffs = 0;
        const diffData = ctx.createImageData(canvas.width, canvas.height);
        
        // Track regions with most differences
        const regionDiffs = {};
        const regionSize = 20; // 20x20 pixel regions
        
        for (let i = 0; i < baselineData.data.length; i += 4) {
          const pixelIndex = i / 4;
          const x = pixelIndex % canvas.width;
          const y = Math.floor(pixelIndex / canvas.width);
          const regionKey = `${Math.floor(x / regionSize)},${Math.floor(y / regionSize)}`;
          
          // Calculate color difference (grayscale diff since eInk is 1-bit)
          const baseGray = (baselineData.data[i] + baselineData.data[i+1] + baselineData.data[i+2]) / 3;
          const currGray = (currentData.data[i] + currentData.data[i+1] + currentData.data[i+2]) / 3;
          const diff = Math.abs(baseGray - currGray);
          
          if (diff > 0) {
            differences++;
            regionDiffs[regionKey] = (regionDiffs[regionKey] || 0) + 1;
            
            // Color-code by intensity:
            // Green = match, Yellow = slight diff (1-50), Orange = medium (51-150), Red = major (151+)
            if (diff <= 50) {
              slightDiffs++;
              // Yellow for slight differences
              diffData.data[i] = 255;
              diffData.data[i+1] = 220;
              diffData.data[i+2] = 0;
              diffData.data[i+3] = 180;
            } else if (diff <= 150) {
              // Orange for medium differences
              diffData.data[i] = 255;
              diffData.data[i+1] = 120;
              diffData.data[i+2] = 0;
              diffData.data[i+3] = 200;
            } else {
              majorDiffs++;
              // Red for major differences
              diffData.data[i] = 255;
              diffData.data[i+1] = 0;
              diffData.data[i+2] = 0;
              diffData.data[i+3] = 220;
            }
          } else {
            // Green tint for matching pixels
            diffData.data[i] = Math.floor(currentData.data[i] * 0.7);
            diffData.data[i+1] = Math.floor(currentData.data[i+1] * 0.85 + 40);
            diffData.data[i+2] = Math.floor(currentData.data[i+2] * 0.7);
            diffData.data[i+3] = 180;
          }
        }
        
        // Find hotspot regions (most differences)
        const sortedRegions = Object.entries(regionDiffs)
          .sort((a, b) => b[1] - a[1])
          .slice(0, 5);
        
        ctx.putImageData(diffData, 0, 0);
        
        // Draw hotspot markers on diff canvas
        ctx.strokeStyle = 'rgba(255, 0, 0, 0.8)';
        ctx.lineWidth = 2;
        for (const [regionKey, count] of sortedRegions) {
          if (count > 10) { // Only mark significant hotspots
            const parts = regionKey.split(',').map(n => parseInt(n));
            if (parts.length >= 2 && !isNaN(parts[0]) && !isNaN(parts[1])) {
              const [rx, ry] = parts;
              ctx.strokeRect(rx * regionSize, ry * regionSize, regionSize, regionSize);
            }
          }
        }
        
        // Display gallery (baseline/current/diff) with enhanced stats
        const pixels = canvas.width * canvas.height;
        const percentage = ((differences / pixels) * 100).toFixed(2);
        const matchPercentage = (100 - parseFloat(percentage)).toFixed(2);
        const gallery = document.getElementById('visualGallery');
        lastDiffImage = diffCanvas.toDataURL();
        
        // Build stats HTML
        const statsHtml = `
          <div style="margin-bottom:8px;padding:8px;background:#f8f8f8;border-radius:4px;font-size:11px;">
            <div style="font-weight:bold;margin-bottom:4px;">Comparison Results:</div>
            <div style="display:flex;gap:12px;flex-wrap:wrap;">
              <span style="color:#0a0;">✓ Match: ${matchPercentage}%</span>
              <span style="color:#c00;">✗ Diff: ${differences} px (${percentage}%)</span>
            </div>
            <div style="margin-top:4px;display:flex;gap:12px;flex-wrap:wrap;">
              <span style="color:#db0;">▪ Slight: ${slightDiffs}</span>
              <span style="color:#f80;">▪ Medium: ${differences - slightDiffs - majorDiffs}</span>
              <span style="color:#c00;">▪ Major: ${majorDiffs}</span>
            </div>
            ${sortedRegions.length > 0 ? `
            <div style="margin-top:4px;font-size:10px;color:#666;">
              Hotspots: ${sortedRegions.map(([k, v]) => {
                const [rx, ry] = k.split(',');
                return `(${rx * regionSize},${ry * regionSize}): ${v}px`;
              }).join(', ')}
            </div>` : ''}
          </div>
        `;
        
        if (gallery){
          gallery.innerHTML = statsHtml + `
            <div style="display:flex;gap:8px;flex-wrap:wrap;">
              <div class="shot"><div class="muted">Baseline</div><img src="${baselineImage}" style="border:1px solid #ddd;"></div>
              <div class="shot"><div class="muted">Current</div><img src="${currentImage}" style="border:1px solid #ddd;"></div>
              <div class="shot"><div class="muted">Diff</div><img src="${lastDiffImage}" style="border:1px solid #ddd;"></div>
            </div>
            <div style="margin-top:8px;font-size:10px;color:#666;">
              <span style="display:inline-block;width:12px;height:12px;background:#0c0;margin-right:4px;vertical-align:middle;"></span>Match
              <span style="display:inline-block;width:12px;height:12px;background:#dc0;margin-left:12px;margin-right:4px;vertical-align:middle;"></span>Slight
              <span style="display:inline-block;width:12px;height:12px;background:#f80;margin-left:12px;margin-right:4px;vertical-align:middle;"></span>Medium
              <span style="display:inline-block;width:12px;height:12px;background:#c00;margin-left:12px;margin-right:4px;vertical-align:middle;"></span>Major
            </div>
          `;
        } else {
          // Fallback to legacy container
          const diffContainer = document.getElementById('visualDiff');
          if (diffContainer) {
            diffContainer.style.display = 'block';
            diffContainer.innerHTML = statsHtml + `
              <img src="${lastDiffImage}" style="border:1px solid #ddd;">
            `;
          }
        }
        // Enable downloads
        document.getElementById('downloadBaseline')?.removeAttribute('disabled');
        document.getElementById('downloadCurrent')?.removeAttribute('disabled');
        document.getElementById('downloadDiff')?.removeAttribute('disabled');
        debugLog(`Visual diff: ${percentage}% changed`, differences > 0 ? 'warn' : 'success');
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
    const rows = [
      ['Issues', Array.isArray(state.validationIssues) ? state.validationIssues.length : 0],
      ['Regions visible', state.regionVisible.length],
      ['UI spec keys', state.UI_SPEC.length],
      ['Last render (ms)', (window.__lastRenderMs||0).toFixed ? (window.__lastRenderMs||0).toFixed(1) : window.__lastRenderMs],
    ];
    inspector.innerHTML = `
      <table class="kv-table">
        <tbody>
          ${rows.map(([k,v])=>`<tr><th class="muted">${k}</th><td>${v}</td></tr>`).join('')}
        </tbody>
      </table>
    `;
  }

  // Gather region metrics from rendered content
  function gatherRegionMetrics() {
    const metrics = {
      timestamp: new Date().toISOString(),
      canvas: { width: 250, height: 122 },
      regions: {},
      summary: {
        total: 0,
        withContent: 0,
        withOverflow: 0,
        overflowPixels: 0
      }
    };

    const renderedContent = window.renderedContent || {};
    const geometry = window.__geometry || {};
    const rects = geometry.rects || {};

    for (const [name, rect] of Object.entries(rects)) {
      // Skip internal helper regions
      if (name.includes('_INNER') || name.includes('_BADGE') || name.includes('LABEL_BOX')) {
        continue;
      }

      const [x, y, w, h] = rect;
      const content = renderedContent[name] || {};
      
      const regionMetric = {
        bounds: { x, y, w, h },
        content: {
          text: content.text || null,
          fontSize: content.fontSize || null,
          fontWeight: content.weight || 'normal'
        },
        textMetrics: null,
        overflow: { horizontal: 0, vertical: 0, hasOverflow: false }
      };

      // Calculate text metrics if content exists
      if (content.text && content.fontSize) {
        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');
        const fontStack = 'Menlo, Consolas, "DM Mono", "Roboto Mono", monospace';
        ctx.font = `${content.weight || 'normal'} ${content.fontSize}px ${fontStack}`;
        const textMetrics = ctx.measureText(content.text);
        
        const textWidth = textMetrics.width;
        const textHeight = textMetrics.actualBoundingBoxAscent + textMetrics.actualBoundingBoxDescent || content.fontSize * 1.2;
        
        regionMetric.textMetrics = {
          width: Math.round(textWidth * 10) / 10,
          height: Math.round(textHeight * 10) / 10,
          availableWidth: w,
          availableHeight: h,
          utilizationX: Math.round((textWidth / w) * 1000) / 10,
          utilizationY: Math.round((textHeight / h) * 1000) / 10
        };

        const overflowX = Math.max(0, textWidth - w);
        const overflowY = Math.max(0, textHeight - h);
        
        regionMetric.overflow = {
          horizontal: Math.round(overflowX * 10) / 10,
          vertical: Math.round(overflowY * 10) / 10,
          hasOverflow: overflowX > 0 || overflowY > 0,
          percentX: w > 0 ? Math.round((overflowX / w) * 1000) / 10 : 0,
          percentY: h > 0 ? Math.round((overflowY / h) * 1000) / 10 : 0
        };

        metrics.summary.withContent++;
        if (regionMetric.overflow.hasOverflow) {
          metrics.summary.withOverflow++;
          metrics.summary.overflowPixels += overflowX + overflowY;
        }
      }

      metrics.regions[name] = regionMetric;
      metrics.summary.total++;
    }

    metrics.summary.overflowPixels = Math.round(metrics.summary.overflowPixels * 10) / 10;
    return metrics;
  }

  // Update the region metrics table in the UI
  function updateRegionMetricsTable() {
    const container = document.getElementById('regionMetricsTable');
    if (!container) return;

    const metrics = gatherRegionMetrics();
    
    // Build summary
    let html = `<div style="margin-bottom:6px;padding:4px;background:#f0f0f0;border-radius:2px;">
      <strong>Summary:</strong> ${metrics.summary.withContent}/${metrics.summary.total} regions with content, 
      <span style="color:${metrics.summary.withOverflow > 0 ? '#c00' : '#0a0'}">
        ${metrics.summary.withOverflow} with overflow
      </span>
    </div>`;

    // Build table
    html += `<table style="width:100%;border-collapse:collapse;font-size:9px;">
      <thead>
        <tr style="background:#eee;">
          <th style="text-align:left;padding:2px;">Region</th>
          <th style="text-align:right;padding:2px;">Text W</th>
          <th style="text-align:right;padding:2px;">Avail W</th>
          <th style="text-align:right;padding:2px;">Util %</th>
          <th style="text-align:right;padding:2px;">Overflow</th>
        </tr>
      </thead>
      <tbody>`;

    // Sort regions: overflow first, then by name
    const sortedRegions = Object.entries(metrics.regions)
      .filter(([_, m]) => m.textMetrics !== null)
      .sort((a, b) => {
        const aOverflow = a[1].overflow.hasOverflow ? 1 : 0;
        const bOverflow = b[1].overflow.hasOverflow ? 1 : 0;
        if (bOverflow !== aOverflow) return bOverflow - aOverflow;
        return a[0].localeCompare(b[0]);
      });

    for (const [name, m] of sortedRegions) {
      const tm = m.textMetrics;
      const overflow = m.overflow;
      const rowColor = overflow.hasOverflow ? '#fee' : '#fff';
      const overflowText = overflow.hasOverflow 
        ? `<span style="color:#c00;">${overflow.horizontal}px</span>`
        : '<span style="color:#0a0;">OK</span>';
      
      html += `<tr style="background:${rowColor};">
        <td style="padding:2px;max-width:80px;overflow:hidden;text-overflow:ellipsis;" title="${name}">${name}</td>
        <td style="text-align:right;padding:2px;">${tm.width}</td>
        <td style="text-align:right;padding:2px;">${tm.availableWidth}</td>
        <td style="text-align:right;padding:2px;color:${tm.utilizationX > 100 ? '#c00' : tm.utilizationX > 90 ? '#a50' : '#000'}">
          ${tm.utilizationX}%
        </td>
        <td style="text-align:right;padding:2px;">${overflowText}</td>
      </tr>`;
    }

    html += '</tbody></table>';
    container.innerHTML = html;
    
    // Store metrics globally for the overlay
    window.__regionMetrics = metrics;
  }

  // Expose globally
  window.gatherRegionMetrics = gatherRegionMetrics;
  window.updateRegionMetricsTable = updateRegionMetricsTable;

  // Live simulation state
  let liveSimulation = null;

  // Setup event handlers
  function setupEventHandlers() {
    // Performance reset
    document.getElementById('perfReset')?.addEventListener('click', () => {
      perfMetrics.renderTimes = [];
      perfMetrics.frameCount = 0;
      perfMetrics.fps = 0;
      perfMetrics.avgRenderTime = 0;
      perfMetrics.lastFrameTime = performance.now();
      const fpsEl = document.getElementById('debugFPS');
      const renderEl = document.getElementById('debugRenderTime');
      const countEl = document.getElementById('debugFrameCount');
      if (fpsEl) fpsEl.textContent = '0';
      if (renderEl) renderEl.textContent = '0';
      if (countEl) countEl.textContent = '0';
      debugLog('Performance metrics reset', 'info');
    });

    // Debug Overlay controls
    const debugOverlayEnabled = document.getElementById('debugOverlayEnabled');
    const debugOverlayBounds = document.getElementById('debugOverlayBounds');
    const debugOverlayTiming = document.getElementById('debugOverlayTiming');
    const debugOverlayHighlight = document.getElementById('debugOverlayHighlight');
    const debugOverlayInfo = document.getElementById('debugOverlayInfo');

    if (debugOverlayEnabled) {
      debugOverlayEnabled.addEventListener('change', (e) => {
        const enabled = e.target.checked;
        if (window.DebugOverlay) {
          window.DebugOverlay.enabled = enabled;
          // Enable/disable dependent controls
          if (debugOverlayBounds) debugOverlayBounds.disabled = !enabled;
          if (debugOverlayTiming) debugOverlayTiming.disabled = !enabled;
          if (debugOverlayHighlight) debugOverlayHighlight.disabled = !enabled;
          if (debugOverlayInfo) debugOverlayInfo.style.display = enabled ? 'block' : 'none';
          // Default settings when enabling
          if (enabled) {
            if (debugOverlayBounds && !debugOverlayBounds.checked) {
              debugOverlayBounds.checked = true;
              window.DebugOverlay.showBounds = true;
            }
            if (debugOverlayTiming && !debugOverlayTiming.checked) {
              debugOverlayTiming.checked = true;
              window.DebugOverlay.showTiming = true;
            }
          }
          // Redraw
          if (typeof window.draw === 'function') window.draw(window.lastData);
          debugLog(`Debug overlay ${enabled ? 'enabled' : 'disabled'}`, 'info');
        }
      });
    }

    if (debugOverlayBounds) {
      debugOverlayBounds.addEventListener('change', (e) => {
        if (window.DebugOverlay) {
          window.DebugOverlay.showBounds = e.target.checked;
          if (typeof window.draw === 'function') window.draw(window.lastData);
        }
      });
    }

    if (debugOverlayTiming) {
      debugOverlayTiming.addEventListener('change', (e) => {
        if (window.DebugOverlay) {
          window.DebugOverlay.showTiming = e.target.checked;
          if (typeof window.draw === 'function') window.draw(window.lastData);
        }
      });
    }

    if (debugOverlayHighlight) {
      debugOverlayHighlight.addEventListener('change', (e) => {
        if (window.DebugOverlay) {
          window.DebugOverlay.highlightData = e.target.value || null;
          if (typeof window.draw === 'function') window.draw(window.lastData);
        }
      });
    }

    // Live Simulation controls
    const liveStartBtn = document.getElementById('liveSimStart');
    const liveStopBtn = document.getElementById('liveSimStop');
    const liveStatus = document.getElementById('liveSimStatus');
    const liveSpeedSelect = document.getElementById('liveSimSpeed');
    const liveSeasonSelect = document.getElementById('liveSimSeason');
    const liveGeoSelect = document.getElementById('liveSimGeo');
    const liveWeatherSelect = document.getElementById('liveSimWeather');

    if (liveStartBtn) {
      liveStartBtn.addEventListener('click', () => {
        if (window.LiveSimulation) {
          const season = liveSeasonSelect ? liveSeasonSelect.value : 'summer';
          const geography = liveGeoSelect ? liveGeoSelect.value : 'midwest';
          const weather = liveWeatherSelect ? liveWeatherSelect.value : 'sunny';
          const speed = liveSpeedSelect ? parseInt(liveSpeedSelect.value) : 60;

          liveSimulation = new window.LiveSimulation({
            season,
            geography,
            weather,
            speed,
            onUpdate: (data) => {
              if (window.draw) {
                window.draw(data);
              }
              if (liveStatus) {
                liveStatus.textContent = `Running (${data.time_hhmm}, ${data.weather})`;
              }
            }
          });
          liveSimulation.start();
          
          if (liveStartBtn) liveStartBtn.disabled = true;
          if (liveStopBtn) liveStopBtn.disabled = false;
          debugLog('Live simulation started', 'success');
        } else {
          debugLog('LiveSimulation not available', 'error');
        }
      });
    }

    if (liveStopBtn) {
      liveStopBtn.addEventListener('click', () => {
        if (liveSimulation) {
          liveSimulation.stop();
          liveSimulation = null;
        }
        if (liveStartBtn) liveStartBtn.disabled = false;
        if (liveStopBtn) liveStopBtn.disabled = true;
        if (liveStatus) liveStatus.textContent = 'Stopped';
        debugLog('Live simulation stopped', 'info');
      });
    }

    // Live simulation parameter changes
    if (liveSpeedSelect) {
      liveSpeedSelect.addEventListener('change', () => {
        if (liveSimulation) {
          liveSimulation.setSpeed(parseInt(liveSpeedSelect.value));
          debugLog(`Simulation speed: ${liveSpeedSelect.value}x`, 'info');
        }
      });
    }

    if (liveSeasonSelect) {
      liveSeasonSelect.addEventListener('change', () => {
        if (liveSimulation) {
          liveSimulation.setSeason(liveSeasonSelect.value);
          debugLog(`Season: ${liveSeasonSelect.value}`, 'info');
        }
      });
    }

    if (liveGeoSelect) {
      liveGeoSelect.addEventListener('change', () => {
        if (liveSimulation) {
          liveSimulation.setGeography(liveGeoSelect.value);
          debugLog(`Geography: ${liveGeoSelect.value}`, 'info');
        }
      });
    }

    if (liveWeatherSelect) {
      liveWeatherSelect.addEventListener('change', () => {
        if (liveSimulation) {
          liveSimulation.setWeather(liveWeatherSelect.value);
          debugLog(`Weather: ${liveWeatherSelect.value}`, 'info');
        }
      });
    }

    // Realistic scenario presets
    const realisticPresetSelect = document.getElementById('realisticPreset');
    const applyRealisticBtn = document.getElementById('applyRealisticPreset');
    const randomRealisticBtn = document.getElementById('randomRealisticPreset');

    if (applyRealisticBtn) {
      applyRealisticBtn.addEventListener('click', () => {
        const presetName = realisticPresetSelect ? realisticPresetSelect.value : '';
        if (presetName && window.SCENARIO_PRESETS && window.SCENARIO_PRESETS[presetName]) {
          const data = window.SCENARIO_PRESETS[presetName]();
          if (window.draw) {
            window.draw(data);
            debugLog(`Applied preset: ${presetName}`, 'success');
          }
        } else {
          debugLog('Select a preset first', 'warn');
        }
      });
    }

    if (randomRealisticBtn) {
      randomRealisticBtn.addEventListener('click', () => {
        if (window.SCENARIO_PRESETS) {
          const presetNames = Object.keys(window.SCENARIO_PRESETS);
          const randomName = presetNames[Math.floor(Math.random() * presetNames.length)];
          const data = window.SCENARIO_PRESETS[randomName]();
          if (window.draw) {
            window.draw(data);
            if (realisticPresetSelect) {
              realisticPresetSelect.value = randomName;
            }
            debugLog(`Random preset: ${randomName}`, 'info');
          }
        }
      });
    }
    
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
    document.getElementById('downloadBaseline')?.addEventListener('click', ()=>{ if (baselineImage){ const a=document.createElement('a'); a.href=baselineImage; a.download='baseline.png'; a.click(); } });
    document.getElementById('downloadCurrent')?.addEventListener('click', ()=>{ const c=document.getElementById('epd'); if (c){ const a=document.createElement('a'); a.href=c.toDataURL(); a.download='current.png'; a.click(); }});
    document.getElementById('downloadDiff')?.addEventListener('click', ()=>{ if (lastDiffImage){ const a=document.createElement('a'); a.href=lastDiffImage; a.download='diff.png'; a.click(); }});
    
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

    // Device screenshot comparison
    let deviceImage = null;
    let showDeviceOverlay = false;
    const deviceInput = document.getElementById('deviceScreenshot');
    const clearDeviceBtn = document.getElementById('clearDeviceScreenshot');
    const deviceContainer = document.getElementById('deviceCompareContainer');
    const deviceCompareView = document.getElementById('deviceCompareView');
    const deviceOpacitySlider = document.getElementById('deviceOpacity');
    
    if (deviceInput) {
      deviceInput.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) {
          const reader = new FileReader();
          reader.onload = (ev) => {
            deviceImage = new Image();
            deviceImage.onload = () => {
              if (deviceContainer) deviceContainer.style.display = 'block';
              if (clearDeviceBtn) clearDeviceBtn.disabled = false;
              updateDeviceCompareView();
              debugLog(`Device screenshot loaded: ${file.name} (${deviceImage.width}x${deviceImage.height})`, 'success');
            };
            deviceImage.src = ev.target.result;
          };
          reader.readAsDataURL(file);
        }
      });
    }

    if (clearDeviceBtn) {
      clearDeviceBtn.addEventListener('click', () => {
        deviceImage = null;
        if (deviceInput) deviceInput.value = '';
        if (deviceContainer) deviceContainer.style.display = 'none';
        clearDeviceBtn.disabled = true;
        debugLog('Device screenshot cleared', 'info');
      });
    }

    // Capture screenshot from device via MQTT
    document.getElementById('captureFromDevice')?.addEventListener('click', () => {
      captureScreenshotFromDevice();
    });

    async function captureScreenshotFromDevice() {
      const statusEl = document.getElementById('captureStatus');
      const targetDeviceInput = document.getElementById('targetDeviceId');

      // Get device ID (use target input or current MQTT device ID)
      let targetDeviceId = targetDeviceInput?.value.trim();
      if (!targetDeviceId && window.SimMQTT) {
        targetDeviceId = window.SimMQTT.getDeviceId();
      }

      if (!targetDeviceId) {
        if (statusEl) statusEl.textContent = '⚠️ No device ID specified';
        debugLog('No device ID specified. Enter a device ID or connect via MQTT.', 'error');
        return;
      }

      // Check if we have access to MQTT client
      if (!window.mqtt) {
        if (statusEl) statusEl.textContent = '⚠️ MQTT library not loaded';
        debugLog('MQTT library not available. Include mqtt.min.js in index.html.', 'error');
        return;
      }

      if (statusEl) statusEl.textContent = '📡 Sending command...';
      debugLog(`Requesting screenshot from device: ${targetDeviceId}`, 'info');

      // Create temporary MQTT client for screenshot capture
      const broker = localStorage.getItem('mqttBroker') || '127.0.0.1';
      const port = localStorage.getItem('mqttWsPort') || '9001';
      const url = `ws://${broker}:${port}`;

      const screenshotClient = mqtt.connect(url, {
        clientId: `sim-screenshot-${Date.now()}`,
        clean: true
      });

      let screenshotMeta = null;
      let screenshotChunks = [];
      let expectedChunks = 0;
      let receivedChunks = 0;

      screenshotClient.on('connect', () => {
        debugLog('Connected to MQTT broker for screenshot capture', 'success');

        // Subscribe to screenshot response topics
        const metaTopic = `espsensor/${targetDeviceId}/debug/screenshot/meta`;
        const dataTopic = `espsensor/${targetDeviceId}/debug/screenshot/data/#`;
        const responseTopic = `espsensor/${targetDeviceId}/debug/response`;

        screenshotClient.subscribe([metaTopic, dataTopic, responseTopic], (err) => {
          if (err) {
            debugLog(`Failed to subscribe: ${err.message}`, 'error');
            if (statusEl) statusEl.textContent = '❌ Subscribe failed';
            screenshotClient.end();
            return;
          }

          // Send screenshot command
          const cmdTopic = `espsensor/${targetDeviceId}/cmd/debug`;
          const cmd = JSON.stringify({ cmd: 'screenshot' });

          screenshotClient.publish(cmdTopic, cmd, { qos: 0 }, (err) => {
            if (err) {
              debugLog(`Failed to send command: ${err.message}`, 'error');
              if (statusEl) statusEl.textContent = '❌ Command failed';
              screenshotClient.end();
            } else {
              debugLog('Screenshot command sent', 'info');
              if (statusEl) statusEl.textContent = '⏳ Waiting for response...';
            }
          });
        });
      });

      screenshotClient.on('message', (topic, message) => {
        const msgStr = message.toString();

        // Handle metadata
        if (topic.endsWith('/meta')) {
          try {
            screenshotMeta = JSON.parse(msgStr);
            debugLog(`Received screenshot metadata: ${screenshotMeta.width}x${screenshotMeta.height}, ${screenshotMeta.data_size} bytes`, 'success');

            // Estimate number of chunks (4096 bytes per chunk)
            expectedChunks = Math.ceil(screenshotMeta.data_size / 4096);
            if (statusEl) statusEl.textContent = `⏳ Receiving data (0/${expectedChunks})...`;
          } catch (e) {
            debugLog(`Failed to parse metadata: ${e.message}`, 'error');
          }
        }
        // Handle data chunks
        else if (topic.includes('/screenshot/data')) {
          screenshotChunks.push(msgStr);
          receivedChunks++;

          if (statusEl && expectedChunks > 0) {
            statusEl.textContent = `⏳ Receiving data (${receivedChunks}/${expectedChunks})...`;
          }

          // Check if we've received all chunks (wait a bit for any stragglers)
          setTimeout(() => {
            if (screenshotMeta && screenshotChunks.length > 0) {
              processScreenshotData();
            }
          }, 500);
        }
        // Handle acknowledgment
        else if (topic.endsWith('/debug/response')) {
          try {
            const response = JSON.parse(msgStr);
            if (response.cmd === 'screenshot') {
              debugLog(`Screenshot command acknowledged: ${response.status || 'ok'}`, 'info');
            }
          } catch (e) {
            // Ignore parse errors for non-JSON responses
          }
        }
      });

      screenshotClient.on('error', (err) => {
        debugLog(`MQTT error: ${err.message}`, 'error');
        if (statusEl) statusEl.textContent = '❌ Connection error';
        screenshotClient.end();
      });

      function processScreenshotData() {
        if (!screenshotMeta || screenshotChunks.length === 0) return;

        // Concatenate all chunks
        const base64Data = screenshotChunks.join('');
        debugLog(`Received total ${base64Data.length} bytes of base64 data`, 'info');

        // Decode base64 to binary
        try {
          const binaryString = atob(base64Data);
          const bytes = new Uint8Array(binaryString.length);
          for (let i = 0; i < binaryString.length; i++) {
            bytes[i] = binaryString.charCodeAt(i);
          }

          // Convert 1-bit packed data to image
          const width = screenshotMeta.width;
          const height = screenshotMeta.height;

          // Create canvas
          const canvas = document.createElement('canvas');
          canvas.width = width;
          canvas.height = height;
          const ctx = canvas.getContext('2d');
          if (!ctx) {
            debugLog('Failed to create canvas context', 'error');
            return;
          }

          const imageData = ctx.createImageData(width, height);

          // Unpack 1-bit data (1 = white, 0 = black for eInk)
          for (let y = 0; y < height; y++) {
            for (let x = 0; x < width; x++) {
              const pixelIndex = y * width + x;
              const byteIndex = Math.floor(pixelIndex / 8);
              const bitIndex = 7 - (pixelIndex % 8);

              const bit = (bytes[byteIndex] >> bitIndex) & 1;
              const color = bit ? 255 : 0;  // 1=white, 0=black

              const dataIndex = (y * width + x) * 4;
              imageData.data[dataIndex] = color;     // R
              imageData.data[dataIndex + 1] = color; // G
              imageData.data[dataIndex + 2] = color; // B
              imageData.data[dataIndex + 3] = 255;   // A
            }
          }

          ctx.putImageData(imageData, 0, 0);

          // Convert to data URL and load as device screenshot
          const dataUrl = canvas.toDataURL('image/png');
          deviceImage = new Image();
          deviceImage.onload = () => {
            if (deviceContainer) deviceContainer.style.display = 'block';
            if (clearDeviceBtn) clearDeviceBtn.disabled = false;
            updateDeviceCompareView();
            debugLog(`Device screenshot captured: ${width}x${height}`, 'success');
            if (statusEl) statusEl.textContent = '✅ Captured!';

            // Clear status after a few seconds
            setTimeout(() => {
              if (statusEl) statusEl.textContent = '';
            }, 3000);
          };
          deviceImage.src = dataUrl;

          // Clean up
          screenshotClient.end();
          screenshotChunks = [];
          screenshotMeta = null;

        } catch (e) {
          debugLog(`Failed to process screenshot data: ${e.message}`, 'error');
          if (statusEl) statusEl.textContent = '❌ Processing failed';
          screenshotClient.end();
        }
      }

      // Timeout after 15 seconds
      setTimeout(() => {
        if (screenshotClient.connected) {
          if (!screenshotMeta) {
            debugLog('Screenshot capture timed out - no response from device', 'warn');
            if (statusEl) statusEl.textContent = '⏱️ Timeout';
          }
          screenshotClient.end();
        }
      }, 15000);
    }

    document.getElementById('toggleCompareView')?.addEventListener('click', () => {
      showDeviceOverlay = !showDeviceOverlay;
      updateDeviceCompareView();
    });

    if (deviceOpacitySlider) {
      deviceOpacitySlider.addEventListener('input', () => {
        updateDeviceCompareView();
      });
    }

    document.getElementById('compareWithDevice')?.addEventListener('click', () => {
      compareWithDeviceScreenshot();
    });

    function updateDeviceCompareView() {
      if (!deviceCompareView || !deviceImage) return;
      
      const canvas = document.getElementById('epd');
      if (!canvas) return;
      
      const opacity = deviceOpacitySlider ? deviceOpacitySlider.value / 100 : 0.5;
      
      // Scale device image to match canvas size
      const scaleX = canvas.width / deviceImage.width;
      const scaleY = canvas.height / deviceImage.height;
      const scale = Math.min(scaleX, scaleY);
      const scaledW = Math.round(deviceImage.width * scale);
      const scaledH = Math.round(deviceImage.height * scale);
      
      if (showDeviceOverlay) {
        // Show device image with sim overlay
        deviceCompareView.innerHTML = `
          <div style="position:relative;width:${canvas.width}px;height:${canvas.height}px;">
            <img src="${deviceImage.src}" style="position:absolute;top:0;left:0;width:${scaledW}px;height:${scaledH}px;object-fit:contain;">
            <img src="${canvas.toDataURL()}" style="position:absolute;top:0;left:0;width:${canvas.width}px;height:${canvas.height}px;opacity:${opacity};">
          </div>
          <div style="font-size:10px;color:#666;margin-top:4px;">Device with simulator overlay (${Math.round(opacity * 100)}% opacity)</div>
        `;
      } else {
        // Show side by side
        deviceCompareView.innerHTML = `
          <div style="display:flex;gap:8px;">
            <div>
              <div style="font-size:10px;color:#666;margin-bottom:2px;">Simulator</div>
              <img src="${canvas.toDataURL()}" style="border:1px solid #ddd;width:${canvas.width}px;height:${canvas.height}px;">
            </div>
            <div>
              <div style="font-size:10px;color:#666;margin-bottom:2px;">Device (${deviceImage.width}x${deviceImage.height})</div>
              <img src="${deviceImage.src}" style="border:1px solid #ddd;width:${scaledW}px;height:${scaledH}px;object-fit:contain;">
            </div>
          </div>
        `;
      }
    }

    function compareWithDeviceScreenshot() {
      if (!deviceImage) {
        debugLog('No device screenshot loaded', 'warn');
        return;
      }

      const canvas = document.getElementById('epd');
      if (!canvas) return;

      // Create canvases for comparison
      const simCanvas = document.createElement('canvas');
      simCanvas.width = canvas.width;
      simCanvas.height = canvas.height;
      const simCtx = simCanvas.getContext('2d');
      if (!simCtx) {
        console.warn('Failed to create simulator canvas context');
        return;
      }
      simCtx.drawImage(canvas, 0, 0);

      // Scale device image to match
      const devCanvas = document.createElement('canvas');
      devCanvas.width = canvas.width;
      devCanvas.height = canvas.height;
      const devCtx = devCanvas.getContext('2d');
      if (!devCtx) {
        console.warn('Failed to create device canvas context');
        return;
      }
      devCtx.fillStyle = '#fff';
      devCtx.fillRect(0, 0, canvas.width, canvas.height);
      
      // Center and scale device image
      const scale = Math.min(canvas.width / deviceImage.width, canvas.height / deviceImage.height);
      const scaledW = deviceImage.width * scale;
      const scaledH = deviceImage.height * scale;
      const offsetX = (canvas.width - scaledW) / 2;
      const offsetY = (canvas.height - scaledH) / 2;
      devCtx.drawImage(deviceImage, offsetX, offsetY, scaledW, scaledH);

      // Get image data and compare
      const simData = simCtx.getImageData(0, 0, canvas.width, canvas.height);
      const devData = devCtx.getImageData(0, 0, canvas.width, canvas.height);

      // Validate data exists and has matching lengths
      if (!simData?.data || !devData?.data || simData.data.length !== devData.data.length) {
        console.warn('Device comparison: image data mismatch or missing');
        return;
      }

      // Create diff canvas
      const diffCanvas = document.createElement('canvas');
      diffCanvas.width = canvas.width;
      diffCanvas.height = canvas.height;
      const diffCtx = diffCanvas.getContext('2d');
      if (!diffCtx) {
        console.warn('Failed to create diff canvas context');
        return;
      }
      const diffData = diffCtx.createImageData(canvas.width, canvas.height);

      let differences = 0;
      let totalPixels = canvas.width * canvas.height;

      // Guard against division by zero
      if (totalPixels === 0) {
        console.warn('Device comparison: canvas has zero pixels');
        return;
      }

      for (let i = 0; i < simData.data.length; i += 4) {
        const simGray = (simData.data[i] + simData.data[i+1] + simData.data[i+2]) / 3;
        const devGray = (devData.data[i] + devData.data[i+1] + devData.data[i+2]) / 3;
        const diff = Math.abs(simGray - devGray);

        if (diff > 30) { // Threshold for 1-bit comparison
          differences++;
          diffData.data[i] = 255;
          diffData.data[i+1] = 0;
          diffData.data[i+2] = 0;
          diffData.data[i+3] = 200;
        } else {
          diffData.data[i] = Math.floor((simGray + devGray) / 2);
          diffData.data[i+1] = diffData.data[i];
          diffData.data[i+2] = diffData.data[i];
          diffData.data[i+3] = 128;
        }
      }

      diffCtx.putImageData(diffData, 0, 0);

      const matchPercent = ((1 - differences / totalPixels) * 100).toFixed(2);
      const resultsDiv = document.getElementById('deviceCompareResults');
      if (resultsDiv) {
        resultsDiv.innerHTML = `
          <div style="padding:8px;background:#f8f8f8;border-radius:4px;">
            <div style="font-weight:bold;margin-bottom:4px;">Device vs Simulator Comparison:</div>
            <div style="color:${parseFloat(matchPercent) > 95 ? '#0a0' : parseFloat(matchPercent) > 85 ? '#a50' : '#c00'};">
              Match: ${matchPercent}% (${differences} differing pixels)
            </div>
          </div>
          <div style="margin-top:8px;">
            <div style="font-size:10px;color:#666;margin-bottom:2px;">Diff (red = difference)</div>
            <img src="${diffCanvas.toDataURL()}" style="border:1px solid #ddd;">
          </div>
        `;
      }
      debugLog(`Device comparison: ${matchPercent}% match`, parseFloat(matchPercent) > 90 ? 'success' : 'warn');
    }
    
    // Region metrics
    const showMetricsCheckbox = document.getElementById('showRegionMetrics');
    const highlightOverflowCheckbox = document.getElementById('highlightOverflow');
    
    if (showMetricsCheckbox) {
      showMetricsCheckbox.addEventListener('change', () => {
        window.__showRegionMetrics = showMetricsCheckbox.checked;
        if (window.draw && window.lastData) {
          window.draw(window.lastData);
        }
        updateRegionMetricsTable();
      });
    }
    
    if (highlightOverflowCheckbox) {
      highlightOverflowCheckbox.addEventListener('change', () => {
        window.__highlightOverflow = highlightOverflowCheckbox.checked;
        if (window.draw && window.lastData) {
          window.draw(window.lastData);
        }
      });
    }
    
    document.getElementById('refreshMetrics')?.addEventListener('click', () => {
      updateRegionMetricsTable();
      debugLog('Region metrics refreshed', 'info');
    });
    
    document.getElementById('exportMetrics')?.addEventListener('click', () => {
      const metrics = gatherRegionMetrics();
      const json = JSON.stringify(metrics, null, 2);
      const blob = new Blob([json], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `region-metrics-${Date.now()}.json`;
      a.click();
      URL.revokeObjectURL(url);
      debugLog('Metrics exported', 'success');
    });
    
    document.getElementById('copyMetrics')?.addEventListener('click', () => {
      const metrics = gatherRegionMetrics();
      const text = JSON.stringify(metrics, null, 2);
      navigator.clipboard.writeText(text).then(() => {
        debugLog('Metrics copied to clipboard', 'success');
      }).catch(() => {
        debugLog('Failed to copy metrics', 'error');
      });
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

    // Remote command UI handlers
    const remoteCommandSelect = document.getElementById('remoteCommand');
    const sendRemoteCommandBtn = document.getElementById('sendRemoteCommand');
    const commandResponseEl = document.getElementById('commandResponse');
    const commandResponseContainer = document.getElementById('commandResponseContainer');

    // Enable send button only when command is selected and in control/sync mode
    if (remoteCommandSelect) {
      remoteCommandSelect.addEventListener('change', () => {
        const mode = window.SimMQTT ? window.SimMQTT.getMode() : 'emulate';
        const hasCommand = remoteCommandSelect.value !== '';
        const canSend = (mode === 'control' || mode === 'sync') && hasCommand;

        if (sendRemoteCommandBtn) {
          sendRemoteCommandBtn.disabled = !canSend;
        }
      });
    }

    // Send remote command
    if (sendRemoteCommandBtn) {
      sendRemoteCommandBtn.addEventListener('click', () => {
        const cmd = remoteCommandSelect ? remoteCommandSelect.value : '';
        if (!cmd) return;

        debugLog(`Sending remote command: ${cmd}`, 'info');

        // Subscribe to response topic
        const mode = window.SimMQTT ? window.SimMQTT.getMode() : 'emulate';
        const deviceId = window.SimMQTT ? window.SimMQTT.getMirroredDevice() : null;

        if (!deviceId) {
          debugLog('No device connected', 'error');
          return;
        }

        // Create temporary MQTT client to listen for response
        const broker = localStorage.getItem('mqttBroker') || '127.0.0.1';
        const port = localStorage.getItem('mqttWsPort') || '9001';
        const url = `ws://${broker}:${port}`;

        const responseClient = mqtt.connect(url, {
          clientId: `cmd-response-${Date.now()}`,
          clean: true
        });

        responseClient.on('connect', () => {
          const responseTopic = `espsensor/${deviceId}/debug/response`;

          responseClient.subscribe(responseTopic, (err) => {
            if (err) {
              debugLog(`Failed to subscribe: ${err.message}`, 'error');
              responseClient.end();
              return;
            }

            // Send command using SimMQTT
            if (window.SimMQTT && window.SimMQTT.sendCommand) {
              window.SimMQTT.sendCommand(cmd);
            }
          });
        });

        responseClient.on('message', (topic, message) => {
          const response = message.toString();

          // Display response
          if (commandResponseEl && commandResponseContainer) {
            commandResponseEl.textContent = response;
            commandResponseContainer.style.display = 'block';
            debugLog(`Command response received (${response.length} bytes)`, 'success');
          }

          // Close connection after receiving response
          setTimeout(() => {
            responseClient.end();
          }, 100);
        });

        responseClient.on('error', (err) => {
          debugLog(`MQTT error: ${err.message}`, 'error');
          responseClient.end();
        });

        // Timeout after 10 seconds
        setTimeout(() => {
          if (responseClient.connected) {
            debugLog('Command timed out - no response', 'warn');
            responseClient.end();
          }
        }, 10000);
      });
    }

    // Clear response
    document.getElementById('clearResponse')?.addEventListener('click', () => {
      if (commandResponseEl) commandResponseEl.textContent = '';
      if (commandResponseContainer) commandResponseContainer.style.display = 'none';
    });

    // Copy response
    document.getElementById('copyResponse')?.addEventListener('click', () => {
      if (commandResponseEl) {
        navigator.clipboard.writeText(commandResponseEl.textContent).then(() => {
          debugLog('Response copied to clipboard', 'success');
        }).catch(err => {
          debugLog(`Failed to copy: ${err.message}`, 'error');
        });
      }
    });

    // Update send button state when mode changes
    setInterval(() => {
      const mode = window.SimMQTT ? window.SimMQTT.getMode() : 'emulate';
      const hasCommand = remoteCommandSelect ? remoteCommandSelect.value !== '' : false;
      const canSend = (mode === 'control' || mode === 'sync') && hasCommand;

      if (sendRemoteCommandBtn) {
        sendRemoteCommandBtn.disabled = !canSend;
      }
    }, 1000);
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
      // Restore open-state from storage
      try{
        const suffix = (function(){
          try{
            const variant = (new URLSearchParams(window.location.search)).get('variant') || (window.UI_SPEC && window.UI_SPEC.defaultVariant) || 'v1';
            const specMode = (typeof window !== 'undefined' && window.__specMode) ? String(window.__specMode) : 'v1';
            return `${variant}::${specMode}`;
          }catch(e){ return 'v1::v1'; }
        })();
        const key = `sim_panel_open::advancedDebugDetails::${suffix}`;
        const details = document.getElementById('advancedDebugDetails');
        if (details) {
          const saved = localStorage.getItem(key);
          if (saved !== null) details.open = saved === '1';
          details.addEventListener('toggle', ()=>{
            try{ localStorage.setItem(key, details.open ? '1' : '0'); }catch(e){}
          });
        }
      }catch(e){}
      
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