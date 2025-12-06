/**
 * Device Bridge - Central manager for device communication
 * Integrates device discovery, command sending, and screenshot capture
 */

(function() {
  'use strict';

  const DeviceBridge = {
    activeDevice: null,
    discoveredDevices: new Map(),
    discoveryClient: null,
    commandResponses: [],

    // Initialize the device bridge
    init() {
      console.log('DeviceBridge: Initializing...');
      this.startDiscoveryListener();
    },

    // Start listening for device discovery messages
    startDiscoveryListener() {
      if (!window.mqtt) {
        console.warn('DeviceBridge: MQTT library not available');
        return;
      }

      const broker = localStorage.getItem('mqttBroker') || '127.0.0.1';
      const port = localStorage.getItem('mqttWsPort') || '9001';
      const url = `ws://${broker}:${port}`;

      this.discoveryClient = mqtt.connect(url, {
        clientId: `bridge-discovery-${Date.now()}`,
        clean: true
      });

      this.discoveryClient.on('connect', () => {
        console.log('DeviceBridge: Connected to MQTT for discovery');

        // Subscribe to all discovery topics
        this.discoveryClient.subscribe('espsensor/discovery/+', (err) => {
          if (err) {
            console.error('DeviceBridge: Failed to subscribe to discovery', err);
          } else {
            console.log('DeviceBridge: Subscribed to device discovery');
          }
        });
      });

      this.discoveryClient.on('message', (topic, message) => {
        this.handleDiscoveryMessage(topic, message.toString());
      });

      this.discoveryClient.on('error', (err) => {
        console.error('DeviceBridge: Discovery client error:', err);
      });
    },

    // Handle incoming discovery messages
    handleDiscoveryMessage(topic, message) {
      try {
        const parts = topic.split('/');
        const deviceId = parts[parts.length - 1];

        const deviceInfo = JSON.parse(message);
        deviceInfo.device_id = deviceId;
        deviceInfo.last_seen = new Date();

        this.discoveredDevices.set(deviceId, deviceInfo);
        console.log(`DeviceBridge: Discovered device ${deviceId}:`, deviceInfo);

        // Notify UI
        this.notifyDeviceDiscovered(deviceInfo);
      } catch (e) {
        console.error('DeviceBridge: Failed to parse discovery message:', e);
      }
    },

    // Notify UI of discovered device
    notifyDeviceDiscovered(deviceInfo) {
      const event = new CustomEvent('device-discovered', { detail: deviceInfo });
      window.dispatchEvent(event);
    },

    // Scan for devices (request them to republish discovery)
    async scanDevices() {
      console.log('DeviceBridge: Scanning for devices...');

      // Clear old devices
      this.discoveredDevices.clear();

      // Devices publish discovery on connect, so just wait for messages
      // In a real implementation, we could send a broadcast command to trigger republishing

      return new Promise((resolve) => {
        setTimeout(() => {
          const devices = Array.from(this.discoveredDevices.values());
          console.log(`DeviceBridge: Scan complete, found ${devices.length} devices`);
          resolve(devices);
        }, 3000); // Wait 3 seconds for devices to respond
      });
    },

    // Get list of discovered devices
    getDiscoveredDevices() {
      return Array.from(this.discoveredDevices.values());
    },

    // Connect to a specific device
    connectToDevice(deviceId) {
      const deviceInfo = this.discoveredDevices.get(deviceId);
      if (!deviceInfo) {
        console.warn(`DeviceBridge: Device ${deviceId} not found`);
        return false;
      }

      this.activeDevice = deviceInfo;
      console.log(`DeviceBridge: Connected to device ${deviceId}`);

      // Notify UI
      const event = new CustomEvent('device-connected', { detail: deviceInfo });
      window.dispatchEvent(event);

      return true;
    },

    // Disconnect from active device
    disconnectFromDevice() {
      if (!this.activeDevice) return;

      const deviceId = this.activeDevice.device_id;
      this.activeDevice = null;

      console.log(`DeviceBridge: Disconnected from device ${deviceId}`);

      // Notify UI
      const event = new CustomEvent('device-disconnected', { detail: { device_id: deviceId } });
      window.dispatchEvent(event);
    },

    // Send command to active device
    sendCommand(cmd, params = {}) {
      if (!this.activeDevice) {
        console.error('DeviceBridge: No active device');
        return false;
      }

      // Use SimMQTT if available and in control/sync mode
      if (window.SimMQTT && window.SimMQTT.sendCommand) {
        return window.SimMQTT.sendCommand(cmd, params);
      }

      console.error('DeviceBridge: SimMQTT not available');
      return false;
    },

    // Capture screenshot from active device
    async captureDeviceScreenshot() {
      if (!this.activeDevice) {
        throw new Error('No active device');
      }

      // Delegate to existing screenshot capture functionality
      if (window.captureScreenshotFromDevice) {
        return window.captureScreenshotFromDevice();
      }

      throw new Error('Screenshot capture not available');
    },

    // Get active device info
    getActiveDevice() {
      return this.activeDevice;
    },

    // Subscribe to command responses
    onCommandResponse(callback) {
      if (!this.discoveryClient) return;

      // Subscribe to debug response topic for active device
      if (this.activeDevice) {
        const topic = `espsensor/${this.activeDevice.device_id}/debug/response`;
        this.discoveryClient.subscribe(topic);
      }
    },

    // Event handling
    onDeviceConnected(callback) {
      window.addEventListener('device-connected', (e) => callback(e.detail));
    },

    onDeviceDisconnected(callback) {
      window.addEventListener('device-disconnected', (e) => callback(e.detail));
    },

    onDeviceDiscovered(callback) {
      window.addEventListener('device-discovered', (e) => callback(e.detail));
    },

    // Cleanup
    destroy() {
      if (this.discoveryClient) {
        this.discoveryClient.end();
        this.discoveryClient = null;
      }
      this.discoveredDevices.clear();
      this.activeDevice = null;
    }
  };

  // Export to global scope
  window.DeviceBridge = DeviceBridge;

  // Auto-initialize on DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => DeviceBridge.init());
  } else {
    DeviceBridge.init();
  }

})();
