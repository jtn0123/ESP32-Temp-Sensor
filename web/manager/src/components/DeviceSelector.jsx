import { useState, useEffect, useCallback } from 'react';
import { deviceApi } from '../api/deviceApi';

export function DeviceSelector({ onConnect, connected, onTargetChange }) {
  // Serial port state
  const [ports, setPorts] = useState([]);
  const [selectedPort, setSelectedPort] = useState('');
  
  // mDNS discovery state
  const [discoveredDevices, setDiscoveredDevices] = useState([]);
  const [discoveryRunning, setDiscoveryRunning] = useState(false);
  const [discoveryAvailable, setDiscoveryAvailable] = useState(false);
  
  // Target device state (SAFETY: only ONE device at a time)
  const [targetedDeviceId, setTargetedDeviceId] = useState(null);
  const [pendingTarget, setPendingTarget] = useState(null);
  const [showConfirmDialog, setShowConfirmDialog] = useState(false);
  
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Load ports and discovered devices
  useEffect(() => {
    loadPorts();
    loadDiscoveredDevices();
    
    // Poll for discovered devices every 5 seconds
    const interval = setInterval(loadDiscoveredDevices, 5000);
    return () => clearInterval(interval);
  }, []);

  const loadPorts = async () => {
    try {
      const result = await deviceApi.listPorts();
      setPorts(result.ports || []);

      // Auto-select first likely ESP32 port
      const esp32Port = result.ports?.find(p => p.likely_esp32);
      if (esp32Port && !selectedPort) {
        setSelectedPort(esp32Port.port);
      }
    } catch (err) {
      console.error('Error loading ports:', err);
    }
  };

  const loadDiscoveredDevices = async () => {
    try {
      const result = await deviceApi.getDiscoveredDevices();
      setDiscoveredDevices(result.devices || []);
      setDiscoveryRunning(result.discovery_running);
      setDiscoveryAvailable(result.discovery_available);
      setTargetedDeviceId(result.targeted_device_id);
      
      // Notify parent of target change
      if (onTargetChange && result.targeted_device_id !== targetedDeviceId) {
        onTargetChange(result.targeted_device_id);
      }
    } catch (err) {
      console.error('Error loading discovered devices:', err);
    }
  };

  const handleConnect = async () => {
    if (!selectedPort) return;

    setLoading(true);
    setError(null);

    try {
      await deviceApi.connectSerial(selectedPort);
      onConnect(true, selectedPort);
    } catch (err) {
      console.error('Error connecting:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleDisconnect = async () => {
    setLoading(true);
    try {
      await deviceApi.disconnectSerial();
      onConnect(false, null);
    } catch (err) {
      console.error('Error disconnecting:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // SAFETY: Request to change target device
  const requestTargetChange = (deviceId) => {
    if (deviceId === targetedDeviceId) return;
    
    // If currently connected or have a target, ask for confirmation
    if (connected || targetedDeviceId) {
      setPendingTarget(deviceId);
      setShowConfirmDialog(true);
    } else {
      // No current target, safe to switch
      confirmTargetChange(deviceId);
    }
  };

  const confirmTargetChange = async (deviceId) => {
    setShowConfirmDialog(false);
    setPendingTarget(null);
    setLoading(true);
    setError(null);

    try {
      const result = await deviceApi.setTargetDevice(deviceId);
      setTargetedDeviceId(result.device_id);
      if (onTargetChange) {
        onTargetChange(result.device_id);
      }
    } catch (err) {
      console.error('Error setting target device:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const cancelTargetChange = () => {
    setShowConfirmDialog(false);
    setPendingTarget(null);
  };

  const clearTarget = async () => {
    setLoading(true);
    try {
      await deviceApi.clearTargetDevice();
      setTargetedDeviceId(null);
      if (onTargetChange) {
        onTargetChange(null);
      }
    } catch (err) {
      console.error('Error clearing target:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const toggleDiscovery = async () => {
    setLoading(true);
    try {
      if (discoveryRunning) {
        await deviceApi.stopDiscovery();
      } else {
        await deviceApi.startDiscovery();
      }
      await loadDiscoveredDevices();
    } catch (err) {
      console.error('Error toggling discovery:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="device-selector">
      {/* Target Device Section */}
      <div className="target-section">
        <h4>🎯 Target Device</h4>
        <p className="target-help">
          All commands go to this device only. Select one device to target.
        </p>
        
        {/* Discovered Devices */}
        {discoveryAvailable && (
          <div className="discovered-devices">
            <div className="discovery-header">
              <span>Discovered via mDNS:</span>
              <button 
                onClick={toggleDiscovery}
                disabled={loading}
                className="discovery-toggle"
                title={discoveryRunning ? "Stop scanning" : "Start scanning"}
              >
                {discoveryRunning ? '⏹️ Stop' : '▶️ Scan'}
              </button>
            </div>
            
            {discoveredDevices.length === 0 ? (
              <div className="no-devices">
                {discoveryRunning 
                  ? "Scanning for devices..." 
                  : "No devices found. Click Scan to search."}
              </div>
            ) : (
              <div className="device-list">
                {discoveredDevices.map(device => (
                  <div 
                    key={device.device_id}
                    className={`device-card ${targetedDeviceId === device.device_id ? 'targeted' : ''}`}
                    onClick={() => requestTargetChange(device.device_id)}
                  >
                    <div className="device-name">
                      {targetedDeviceId === device.device_id && <span className="target-badge">✓</span>}
                      {device.room || device.name}
                    </div>
                    <div className="device-details">
                      <span className="device-ip">{device.ip_address}</span>
                      <span className="device-version">v{device.version}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
        
        {/* Manual Device ID Entry */}
        <div className="manual-target">
          <label>Or enter device ID manually:</label>
          <div className="manual-input-row">
            <input
              type="text"
              placeholder="e.g., office"
              value={targetedDeviceId || ''}
              onChange={(e) => {
                if (e.target.value) {
                  requestTargetChange(e.target.value);
                }
              }}
              className="device-id-input"
            />
            {targetedDeviceId && (
              <button onClick={clearTarget} className="clear-target" title="Clear target">
                ✕
              </button>
            )}
          </div>
        </div>
        
        {/* Current Target Display */}
        {targetedDeviceId && (
          <div className="current-target">
            <strong>Active Target:</strong> {targetedDeviceId}
          </div>
        )}
      </div>

      {/* Serial Port Section */}
      <div className="serial-section">
        <h4>🔌 Serial Connection</h4>
        <div className="port-row">
          <select
            value={selectedPort}
            onChange={(e) => setSelectedPort(e.target.value)}
            disabled={connected || loading}
            className="port-select"
          >
            <option value="">Select Port...</option>
            {ports.map(port => (
              <option key={port.port} value={port.port}>
                {port.port} - {port.description}
                {port.likely_esp32 ? ' ⭐' : ''}
              </option>
            ))}
          </select>

          <button
            onClick={loadPorts}
            disabled={connected || loading}
            className="refresh-button"
            title="Refresh port list"
          >
            🔄
          </button>

          {connected ? (
            <button
              onClick={handleDisconnect}
              disabled={loading}
              className="disconnect-button"
            >
              Disconnect
            </button>
          ) : (
            <button
              onClick={handleConnect}
              disabled={!selectedPort || loading}
              className="connect-button"
            >
              {loading ? 'Connecting...' : 'Connect'}
            </button>
          )}
        </div>
      </div>

      {error && <div className="error-message">{error}</div>}

      {/* Confirmation Dialog */}
      {showConfirmDialog && (
        <div className="confirm-overlay">
          <div className="confirm-dialog">
            <h4>⚠️ Change Target Device?</h4>
            <p>
              You are about to switch from <strong>{targetedDeviceId || 'no device'}</strong> to <strong>{pendingTarget}</strong>.
            </p>
            <p className="confirm-warning">
              All commands will now go to the new device.
            </p>
            <div className="confirm-buttons">
              <button onClick={cancelTargetChange} className="cancel-button">
                Cancel
              </button>
              <button 
                onClick={() => confirmTargetChange(pendingTarget)} 
                className="confirm-button"
              >
                Yes, Switch Target
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
