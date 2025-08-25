// Simplified simulator to test basic functionality
console.log('sim-simple.js loading...');

// Store globals
window.SIM = window.SIM || {};

// Basic constants
const WIDTH = 250;
const HEIGHT = 122;

// Default data
window.SIM.DEFAULTS = {
  room_name: 'Office',
  time_hhmm: '10:32',
  inside_temp_f: 72.5,
  inside_hum_pct: 47,
  outside_temp_f: 68.4,
  outside_hum_pct: 53,
  weather: 'cloudy',
  wind_mph: 4.2,
  wind_mps: 1.88,
  battery_percent: 76,
  battery_voltage: 4.01,
  days: '128',
  ip: '192.168.1.42',
  pressure_hpa: 1013.2
};

// Simple draw function
window.SIM.draw = function(data) {
  console.log('SIM.draw called with:', data);
  
  const canvas = document.getElementById('epd');
  if (!canvas) {
    console.error('Canvas not found');
    return;
  }
  
  const ctx = canvas.getContext('2d');
  if (!ctx) {
    console.error('Context not available');
    return;
  }
  
  // Merge with defaults
  const displayData = Object.assign({}, window.SIM.DEFAULTS, data || {});
  
  // Clear canvas
  ctx.fillStyle = '#fff';
  ctx.fillRect(0, 0, WIDTH, HEIGHT);
  
  // Draw basic UI
  ctx.fillStyle = '#000';
  ctx.strokeStyle = '#000';
  ctx.font = 'bold 11px monospace';
  
  // Draw borders
  ctx.strokeRect(0, 0, WIDTH, HEIGHT);
  ctx.beginPath();
  ctx.moveTo(0, 18);
  ctx.lineTo(WIDTH, 18);
  ctx.moveTo(125, 18);
  ctx.lineTo(125, HEIGHT);
  ctx.moveTo(0, 84);
  ctx.lineTo(WIDTH, 84);
  ctx.stroke();
  
  // Header
  ctx.fillText(displayData.room_name, 8, 12);
  ctx.fillText(displayData.time_hhmm, WIDTH - 40, 12);
  
  // Inside section
  ctx.font = '10px monospace';
  ctx.fillText('INSIDE', 30, 30);
  ctx.font = 'bold 22px monospace';
  ctx.fillText(displayData.inside_temp_f.toFixed(1), 20, 55);
  ctx.font = '12px monospace';
  ctx.fillText('°F', 75, 50);
  ctx.font = '10px monospace';
  ctx.fillText(displayData.inside_hum_pct + '% RH', 8, 75);
  
  // Outside section
  ctx.font = '10px monospace';
  ctx.fillText('OUTSIDE', 145, 30);
  ctx.font = 'bold 22px monospace';
  ctx.fillText(displayData.outside_temp_f.toFixed(1), 135, 55);
  ctx.font = '12px monospace';
  ctx.fillText('°F', 190, 50);
  ctx.font = '10px monospace';
  ctx.fillText(displayData.outside_hum_pct + '% RH', 133, 75);
  
  // Footer
  ctx.font = '10px monospace';
  ctx.fillText('Batt: ' + displayData.battery_percent + '%', 8, 95);
  ctx.fillText('IP: ' + displayData.ip, 8, 110);
  ctx.fillText(displayData.weather, 170, 95);
  
  console.log('Draw complete');
};

// Auto-init on load
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM ready, drawing default data');
    window.SIM.draw();
  });
} else {
  console.log('DOM already ready, drawing default data');
  window.SIM.draw();
}

console.log('sim-simple.js loaded successfully');

// Expose for testing
window.draw = window.SIM.draw;
window.DEFAULTS = window.SIM.DEFAULTS;