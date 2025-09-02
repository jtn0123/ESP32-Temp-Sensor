/**
 * MQTT client for web simulator
 * Connects directly to mosquitto via WebSocket
 * Mirrors firmware behavior exactly
 */

(function() {
  'use strict';
  
  // MQTT client state
  let mqttClient = null;
  let isConnected = false;
  let deviceId = localStorage.getItem('mqttDeviceId') || `sim-${window.location.hostname.replace(/\./g, '-')}`;
  let roomName = localStorage.getItem('mqttRoomName') || 'WebSim';
  let publishInterval = null;
  let lastPublishedData = {};
  
  // Default connection settings
  const DEFAULT_BROKER = '127.0.0.1';
  const DEFAULT_WS_PORT = 9001;
  const DEFAULT_PUBLISH_INTERVAL = 30; // seconds
  
  // Topic builders matching firmware patterns
  function buildTopic(suffix) {
    return `espsensor/${deviceId}/${suffix}`;
  }
  
  function buildDiscoveryTopic(sensorKey) {
    return `homeassistant/sensor/${deviceId}_${sensorKey}/config`;
  }
  
  // Format sensor values to match firmware (plain text numbers)
  function formatValue(value, sensorType) {
    if (value === null || value === undefined || value === '') return '';
    
    // Match firmware precision
    switch(sensorType) {
      case 'temperature':
      case 'humidity':
      case 'pressure':
        return parseFloat(value).toFixed(1);
      case 'battery_voltage':
        return parseFloat(value).toFixed(2);
      case 'battery_percent':
      case 'rssi':
        return Math.round(value).toString();
      default:
        return value.toString();
    }
  }
  
  // Build discovery config matching ha_discovery.cpp
  function buildDiscoveryConfig(sensorKey, sensorName, unit, deviceClass, stateSuffix, precision = 1) {
    const config = {
      name: sensorName,
      unique_id: `${deviceId}_${sensorKey}`,
      state_topic: buildTopic(stateSuffix),
      availability_topic: buildTopic('availability'),
      payload_available: 'online',
      payload_not_available: 'offline',
      device_class: deviceClass,
      state_class: 'measurement',
      expire_after: 7320, // 2h + 120s
      device: {
        identifiers: [deviceId],
        name: `${roomName} Sensor`,
        model: 'Web Simulator',
        manufacturer: 'DIY',
        sw_version: 'web-sim'
      }
    };
    
    if (unit) {
      config.unit_of_measurement = unit;
    }
    
    if (unit === '°C' || unit === '°F' || unit === 'V') {
      config.suggested_display_precision = precision;
    }
    
    if (deviceClass === 'temperature' || deviceClass === 'humidity' || deviceClass === 'atmospheric_pressure') {
      config.value_template = '{{ value | round(1) }}';
    }
    
    return JSON.stringify(config);
  }
  
  // Publish Home Assistant discovery messages
  function publishDiscovery() {
    if (!mqttClient || !isConnected) return;
    
    // Temperature
    mqttClient.publish(
      buildDiscoveryTopic('temperature'),
      buildDiscoveryConfig('temperature', `${roomName} Temperature`, '°C', 'temperature', 'inside/temperature'),
      { retain: true, qos: 1 }
    );
    
    // Humidity
    mqttClient.publish(
      buildDiscoveryTopic('humidity'),
      buildDiscoveryConfig('humidity', `${roomName} Humidity`, '%', 'humidity', 'inside/humidity'),
      { retain: true, qos: 1 }
    );
    
    // Pressure
    mqttClient.publish(
      buildDiscoveryTopic('pressure'),
      buildDiscoveryConfig('pressure', `${roomName} Pressure`, 'hPa', 'atmospheric_pressure', 'inside/pressure'),
      { retain: true, qos: 1 }
    );
    
    // Battery
    mqttClient.publish(
      buildDiscoveryTopic('battery'),
      buildDiscoveryConfig('battery', `${roomName} Battery`, '%', 'battery', 'battery/percent', 0),
      { retain: true, qos: 1 }
    );
    
    mqttClient.publish(
      buildDiscoveryTopic('battery_voltage'),
      buildDiscoveryConfig('battery_voltage', `${roomName} Battery Voltage`, 'V', 'voltage', 'battery/voltage', 2),
      { retain: true, qos: 1 }
    );
    
    // WiFi RSSI
    mqttClient.publish(
      buildDiscoveryTopic('rssi'),
      buildDiscoveryConfig('rssi', `${roomName} WiFi Signal`, 'dBm', 'signal_strength', 'wifi/rssi', 0),
      { retain: true, qos: 1 }
    );
    
    console.log('MQTT: Published discovery messages');
  }
  
  // Publish sensor data
  function publishSensorData(data) {
    if (!mqttClient || !isConnected) return;
    
    // Convert Fahrenheit to Celsius to match firmware
    let tempC = null;
    if (data.inside_temp_f !== undefined && data.inside_temp_f !== '') {
      tempC = (parseFloat(data.inside_temp_f) - 32) * 5 / 9;
    }
    
    // Publish each sensor value (retained, matching firmware)
    if (tempC !== null) {
      mqttClient.publish(
        buildTopic('inside/temperature'),
        formatValue(tempC, 'temperature'),
        { retain: true, qos: 0 }
      );
    }
    
    if (data.inside_hum_pct !== undefined && data.inside_hum_pct !== '') {
      mqttClient.publish(
        buildTopic('inside/humidity'),
        formatValue(data.inside_hum_pct, 'humidity'),
        { retain: true, qos: 0 }
      );
    }
    
    if (data.pressure_hpa !== undefined && data.pressure_hpa !== '') {
      mqttClient.publish(
        buildTopic('inside/pressure'),
        formatValue(data.pressure_hpa, 'pressure'),
        { retain: true, qos: 0 }
      );
    }
    
    if (data.battery_percent !== undefined && data.battery_percent !== '') {
      mqttClient.publish(
        buildTopic('battery/percent'),
        formatValue(data.battery_percent, 'battery_percent'),
        { retain: true, qos: 0 }
      );
    }
    
    if (data.battery_voltage !== undefined && data.battery_voltage !== '') {
      mqttClient.publish(
        buildTopic('battery/voltage'),
        formatValue(data.battery_voltage, 'battery_voltage'),
        { retain: true, qos: 0 }
      );
    }
    
    // Simulate RSSI (web sim always has good signal)
    mqttClient.publish(
      buildTopic('wifi/rssi'),
      '-50',
      { retain: true, qos: 0 }
    );
    
    lastPublishedData = data;
    updateStatus(`Published sensor data at ${new Date().toLocaleTimeString()}`);
  }
  
  // Update connection status in UI
  function updateStatus(message, isError = false) {
    const statusEl = document.getElementById('mqttStatus');
    if (statusEl) {
      statusEl.textContent = message;
      statusEl.className = isError ? 'mqtt-status error' : 'mqtt-status';
    }
    
    const badge = document.getElementById('mqttBadge');
    if (badge) {
      if (isConnected) {
        badge.textContent = 'Connected';
        badge.className = 'badge success';
      } else {
        badge.textContent = 'Disconnected';
        badge.className = 'badge error';
      }
    }
  }
  
  // Connect to MQTT broker
  function connect(broker, port, username, password) {
    if (mqttClient) {
      mqttClient.end();
    }
    
    const url = `ws://${broker || DEFAULT_BROKER}:${port || DEFAULT_WS_PORT}`;
    const options = {
      clientId: deviceId,
      clean: true,
      reconnectPeriod: 5000
    };
    
    if (username) {
      options.username = username;
      options.password = password;
    }
    
    updateStatus(`Connecting to ${url}...`);
    
    try {
      mqttClient = mqtt.connect(url, options);
      
      mqttClient.on('connect', () => {
        isConnected = true;
        updateStatus(`Connected to ${broker}:${port}`);
        
        // Publish availability as online (not retained, matching firmware)
        mqttClient.publish(buildTopic('availability'), 'online', { retain: false, qos: 0 });
        
        // Publish discovery
        publishDiscovery();
        
        // Subscribe to commands (optional, for future use)
        mqttClient.subscribe(buildTopic('cmd/+'));
      });
      
      mqttClient.on('error', (err) => {
        isConnected = false;
        updateStatus(`Connection error: ${err.message}`, true);
      });
      
      mqttClient.on('offline', () => {
        isConnected = false;
        updateStatus('Offline', true);
      });
      
      mqttClient.on('close', () => {
        isConnected = false;
        updateStatus('Disconnected');
      });
      
      mqttClient.on('message', (topic, message) => {
        console.log(`MQTT message: ${topic} = ${message.toString()}`);
        // Handle commands if needed
      });
      
    } catch (err) {
      updateStatus(`Failed to connect: ${err.message}`, true);
    }
  }
  
  // Disconnect from broker
  function disconnect() {
    if (mqttClient) {
      // Publish offline availability (not retained)
      if (isConnected) {
        mqttClient.publish(buildTopic('availability'), 'offline', { retain: false, qos: 0 });
      }
      
      mqttClient.end();
      mqttClient = null;
      isConnected = false;
      updateStatus('Disconnected');
    }
    
    if (publishInterval) {
      clearInterval(publishInterval);
      publishInterval = null;
    }
  }
  
  // Start auto-publishing
  function startAutoPublish(intervalSec) {
    stopAutoPublish();
    
    if (intervalSec > 0) {
      publishInterval = setInterval(() => {
        if (window.simDataState && window.simDataState.current) {
          publishSensorData(window.simDataState.current);
        }
      }, intervalSec * 1000);
    }
  }
  
  // Stop auto-publishing
  function stopAutoPublish() {
    if (publishInterval) {
      clearInterval(publishInterval);
      publishInterval = null;
    }
  }
  
  // Export API
  window.SimMQTT = {
    connect,
    disconnect,
    publishSensorData,
    startAutoPublish,
    stopAutoPublish,
    isConnected: () => isConnected,
    setDeviceId: (id) => {
      deviceId = id;
      localStorage.setItem('mqttDeviceId', id);
    },
    setRoomName: (name) => {
      roomName = name;
      localStorage.setItem('mqttRoomName', name);
    },
    getDeviceId: () => deviceId,
    getRoomName: () => roomName
  };
  
})();