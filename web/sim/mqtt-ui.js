/**
 * MQTT UI integration for web simulator
 * Handles UI events and connects to MQTT client
 */

(function() {
  'use strict';
  
  // Wait for DOM and dependencies
  document.addEventListener('DOMContentLoaded', function() {
    if (!window.SimMQTT) {
      console.error('MQTT client not loaded');
      return;
    }
    
    // UI elements
    const brokerInput = document.getElementById('mqttBroker');
    const portInput = document.getElementById('mqttPort');
    const userInput = document.getElementById('mqttUser');
    const passInput = document.getElementById('mqttPass');
    const deviceIdInput = document.getElementById('mqttDeviceId');
    const roomNameInput = document.getElementById('mqttRoomName');
    const intervalInput = document.getElementById('mqttInterval');
    
    const connectBtn = document.getElementById('mqttConnect');
    const disconnectBtn = document.getElementById('mqttDisconnect');
    const publishNowBtn = document.getElementById('mqttPublishNow');
    const publishDiscoveryBtn = document.getElementById('mqttPublishDiscovery');
    const startAutoBtn = document.getElementById('mqttStartAuto');
    const stopAutoBtn = document.getElementById('mqttStopAuto');
    
    // Load saved settings
    function loadSettings() {
      const deviceId = window.SimMQTT.getDeviceId();
      const roomName = window.SimMQTT.getRoomName();
      
      if (deviceIdInput) deviceIdInput.value = deviceId;
      if (roomNameInput) roomNameInput.value = roomName;
      
      // Load connection settings from localStorage
      const savedBroker = localStorage.getItem('mqttBroker');
      const savedPort = localStorage.getItem('mqttPort');
      const savedUser = localStorage.getItem('mqttUser');
      
      if (savedBroker && brokerInput) brokerInput.value = savedBroker;
      if (savedPort && portInput) portInput.value = savedPort;
      if (savedUser && userInput) userInput.value = savedUser;
    }
    
    // Save settings (except password)
    function saveSettings() {
      const broker = brokerInput ? brokerInput.value : '127.0.0.1';
      const port = portInput ? portInput.value : '9001';
      const user = userInput ? userInput.value : '';
      
      localStorage.setItem('mqttBroker', broker);
      localStorage.setItem('mqttPort', port);
      if (user) localStorage.setItem('mqttUser', user);
      
      const deviceId = deviceIdInput ? deviceIdInput.value : '';
      const roomName = roomNameInput ? roomNameInput.value : 'WebSim';
      
      if (deviceId) window.SimMQTT.setDeviceId(deviceId);
      if (roomName) window.SimMQTT.setRoomName(roomName);
    }
    
    // Update button states
    function updateButtons() {
      const connected = window.SimMQTT.isConnected();
      
      if (connectBtn) connectBtn.disabled = connected;
      if (disconnectBtn) disconnectBtn.disabled = !connected;
      if (publishNowBtn) publishNowBtn.disabled = !connected;
      if (publishDiscoveryBtn) publishDiscoveryBtn.disabled = !connected;
    }
    
    // Connect button handler
    if (connectBtn) {
      connectBtn.addEventListener('click', function() {
        saveSettings();
        
        const broker = brokerInput ? brokerInput.value : '127.0.0.1';
        const port = portInput ? parseInt(portInput.value) : 9001;
        const user = userInput ? userInput.value : '';
        const pass = passInput ? passInput.value : '';
        
        window.SimMQTT.connect(broker, port, user, pass);
        
        // Update buttons after a delay to allow connection
        setTimeout(updateButtons, 500);
      });
    }
    
    // Disconnect button handler
    if (disconnectBtn) {
      disconnectBtn.addEventListener('click', function() {
        window.SimMQTT.disconnect();
        updateButtons();
      });
    }
    
    // Publish now button
    if (publishNowBtn) {
      publishNowBtn.addEventListener('click', function() {
        if (window.simDataState && window.simDataState.current) {
          window.SimMQTT.publishSensorData(window.simDataState.current);
        }
      });
    }
    
    // Republish discovery button
    if (publishDiscoveryBtn) {
      publishDiscoveryBtn.addEventListener('click', function() {
        // Update device ID and room name if changed
        saveSettings();
        
        // Reconnect to apply new settings
        const broker = brokerInput ? brokerInput.value : '127.0.0.1';
        const port = portInput ? parseInt(portInput.value) : 9001;
        const user = userInput ? userInput.value : '';
        const pass = passInput ? passInput.value : '';
        
        window.SimMQTT.disconnect();
        setTimeout(() => {
          window.SimMQTT.connect(broker, port, user, pass);
        }, 500);
      });
    }
    
    // Auto-publish controls
    if (startAutoBtn) {
      startAutoBtn.addEventListener('click', function() {
        const interval = intervalInput ? parseInt(intervalInput.value) : 30;
        window.SimMQTT.startAutoPublish(interval);
        startAutoBtn.disabled = true;
        stopAutoBtn.disabled = false;
      });
    }
    
    if (stopAutoBtn) {
      stopAutoBtn.addEventListener('click', function() {
        window.SimMQTT.stopAutoPublish();
        startAutoBtn.disabled = false;
        stopAutoBtn.disabled = true;
      });
    }
    
    // Subscribe to data changes for auto-publishing
    if (window.simDataState) {
      let autoPublishEnabled = false;
      let lastPublishTime = 0;
      const minInterval = 1000; // Minimum 1 second between publishes
      
      window.simDataState.subscribe(function(data) {
        // Only auto-publish if connected and enough time has passed
        if (window.SimMQTT.isConnected() && autoPublishEnabled) {
          const now = Date.now();
          if (now - lastPublishTime > minInterval) {
            window.SimMQTT.publishSensorData(data);
            lastPublishTime = now;
          }
        }
      });
    }
    
    // Initialize
    loadSettings();
    updateButtons();
    
    // Update buttons periodically
    setInterval(updateButtons, 2000);
  });
  
})();