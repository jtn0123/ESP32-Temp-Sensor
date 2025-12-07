// API client for device manager backend

const API_BASE = '/api';

async function fetchAPI(endpoint, options = {}) {
  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(error || `HTTP ${response.status}`);
  }

  return response.json();
}

export const deviceApi = {
  // Serial endpoints
  async listPorts() {
    return fetchAPI('/ports');
  },

  async connectSerial(port, baud = 115200) {
    return fetchAPI('/serial/connect', {
      method: 'POST',
      body: JSON.stringify({ port, baud }),
    });
  },

  async disconnectSerial() {
    return fetchAPI('/serial/disconnect', {
      method: 'POST',
    });
  },

  async sendSerial(data) {
    return fetchAPI('/serial/send', {
      method: 'POST',
      body: JSON.stringify({ data }),
    });
  },

  async getSerialStatus() {
    return fetchAPI('/serial/status');
  },

  // Flash endpoints
  async startFlash(config = 'dev') {
    return fetchAPI('/flash/start', {
      method: 'POST',
      body: JSON.stringify({ config }),
    });
  },

  async getFlashStatus() {
    return fetchAPI('/flash/status');
  },

  async cancelFlash() {
    return fetchAPI('/flash/cancel', {
      method: 'POST',
    });
  },

  // Flash Queue / Hunt Mode endpoints
  async queueFlash(buildConfig = 'dev', targetPort = null, targetDeviceId = null, timeoutMinutes = 15) {
    return fetchAPI('/flash/queue', {
      method: 'POST',
      body: JSON.stringify({
        build_config: buildConfig,
        target_port: targetPort,
        target_device_id: targetDeviceId,
        timeout_minutes: timeoutMinutes,
      }),
    });
  },

  async cancelQueuedFlash() {
    return fetchAPI('/flash/queue', {
      method: 'DELETE',
    });
  },

  async getQueueStatus() {
    return fetchAPI('/flash/queue');
  },

  // Device endpoints
  async requestScreenshot() {
    return fetchAPI('/device/screenshot', {
      method: 'POST',
    });
  },

  async getLatestScreenshot() {
    return fetchAPI('/device/screenshot/latest');
  },

  async sendCommand(command, params = {}) {
    return fetchAPI('/device/command', {
      method: 'POST',
      body: JSON.stringify({ command, params }),
    });
  },

  async getDeviceStatus() {
    return fetchAPI('/device/status');
  },

  // Config endpoints
  async setSleepInterval(intervalSec, deviceId = 'office') {
    return fetchAPI(`/config/sleep-interval?device_id=${deviceId}`, {
      method: 'POST',
      body: JSON.stringify({ interval_sec: intervalSec }),
    });
  },

  // Discovery endpoints (mDNS)
  async getDiscoveredDevices() {
    return fetchAPI('/discovery/devices');
  },

  async startDiscovery() {
    return fetchAPI('/discovery/start', { method: 'POST' });
  },

  async stopDiscovery() {
    return fetchAPI('/discovery/stop', { method: 'POST' });
  },

  async setTargetDevice(deviceId) {
    return fetchAPI('/discovery/target', {
      method: 'POST',
      body: JSON.stringify({ device_id: deviceId }),
    });
  },

  async getTargetDevice() {
    return fetchAPI('/discovery/target');
  },

  async clearTargetDevice() {
    return fetchAPI('/discovery/target', { method: 'DELETE' });
  },

  // Device tracking & wake prediction
  async getAllDevices() {
    return fetchAPI('/devices');
  },

  async getDeviceState(deviceId) {
    return fetchAPI(`/devices/${deviceId}`);
  },

  async setDeviceMode(deviceId, mode) {
    return fetchAPI(`/devices/${deviceId}/mode`, {
      method: 'POST',
      body: JSON.stringify({ mode }),
    });
  },

  async setDeviceInterval(deviceId, intervalSec) {
    return fetchAPI(`/devices/${deviceId}/interval`, {
      method: 'POST',
      body: JSON.stringify({ interval_sec: intervalSec }),
    });
  },

  async getIntervalPresets() {
    return fetchAPI('/presets/intervals');
  },

  // MQTT endpoints
  async getMqttStatus() {
    return fetchAPI('/mqtt/status');
  },

  async publishMqtt(topic, payload, retain = false, qos = 0) {
    return fetchAPI('/mqtt/publish', {
      method: 'POST',
      body: JSON.stringify({ topic, payload, retain, qos }),
    });
  },

  async getMqttMessages(limit = 100) {
    return fetchAPI(`/mqtt/messages?limit=${limit}`);
  },

  async getSubscriptions() {
    return fetchAPI('/mqtt/subscriptions');
  },

  async subscribe(topic, qos = 0) {
    return fetchAPI('/mqtt/subscribe', {
      method: 'POST',
      body: JSON.stringify({ topic, qos }),
    });
  },

  async unsubscribe(topic) {
    return fetchAPI(`/mqtt/unsubscribe?topic=${encodeURIComponent(topic)}`, {
      method: 'POST',
    });
  },

  async startMqttSimulator() {
    return fetchAPI('/mqtt/simulator/start', {
      method: 'POST',
    });
  },

  async stopMqttSimulator() {
    return fetchAPI('/mqtt/simulator/stop', {
      method: 'POST',
    });
  },

  // Device control endpoints
  async requestScreenshot(deviceId = 'office') {
    return fetchAPI(`/device/screenshot?device_id=${deviceId}`, {
      method: 'POST',
    });
  },

  async getLatestScreenshot() {
    return fetchAPI('/device/screenshot/latest');
  },

  async getTestScreenshot() {
    return fetchAPI('/device/screenshot/test');
  },

  async sendCommand(command, params = {}) {
    return fetchAPI('/device/command', {
      method: 'POST',
      body: JSON.stringify({ command, params }),
    });
  },

  async getDeviceStatus() {
    return fetchAPI('/device/status');
  },
};
