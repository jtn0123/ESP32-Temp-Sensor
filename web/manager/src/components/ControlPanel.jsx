import { useState } from 'react';
import { deviceApi } from '../api/deviceApi';

export function ControlPanel() {
  const [sleepInterval, setSleepInterval] = useState(300); // 5 minutes default
  const [deviceId, setDeviceId] = useState('office');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  const handleSetSleepInterval = async () => {
    setLoading(true);
    setError(null);
    setSuccess(null);

    try {
      // Send sleep interval command via MQTT
      const result = await deviceApi.setSleepInterval(sleepInterval, deviceId);
      setSuccess(`Sleep interval set to ${formatSleepTime(sleepInterval)} (will apply on next wake)`);
    } catch (err) {
      console.error('Error setting sleep interval:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleReboot = async () => {
    if (!confirm('Are you sure you want to reboot the device?')) {
      return;
    }

    setLoading(true);
    setError(null);
    setSuccess(null);

    try {
      await deviceApi.sendCommand('reboot', { device_id: deviceId });
      setSuccess('Reboot command sent');
    } catch (err) {
      console.error('Error rebooting device:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleDiagnosticMode = async (enable) => {
    setLoading(true);
    setError(null);
    setSuccess(null);

    try {
      await deviceApi.sendCommand('diagnostic', {
        device_id: deviceId,
        payload: enable ? '1' : '0'
      });
      setSuccess(`Diagnostic mode ${enable ? 'enabled' : 'disabled'}`);
    } catch (err) {
      console.error('Error toggling diagnostic mode:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleForceRefresh = async () => {
    setLoading(true);
    setError(null);
    setSuccess(null);

    try {
      await deviceApi.sendCommand('refresh', { device_id: deviceId });
      setSuccess('Refresh command sent');
    } catch (err) {
      console.error('Error forcing refresh:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const formatSleepTime = (seconds) => {
    if (seconds < 60) return `${seconds}s`;
    if (seconds < 3600) return `${seconds / 60}m`;
    return `${seconds / 3600}h`;
  };

  return (
    <div className="control-panel">
      <div className="control-section">
        <h3>Device Selection</h3>
        <input
          type="text"
          value={deviceId}
          onChange={(e) => setDeviceId(e.target.value)}
          placeholder="Device ID"
          className="device-id-input"
        />
      </div>

      <div className="control-section">
        <h3>Sleep Interval</h3>
        <div className="sleep-controls">
          <input
            type="range"
            min="60"
            max="3600"
            step="60"
            value={sleepInterval}
            onChange={(e) => setSleepInterval(Number(e.target.value))}
            className="sleep-slider"
          />
          <span className="sleep-value">{formatSleepTime(sleepInterval)}</span>
        </div>
        <button
          onClick={handleSetSleepInterval}
          disabled={loading}
          className="control-button"
        >
          Set Sleep Interval
        </button>
      </div>

      <div className="control-section">
        <h3>Device Commands</h3>
        <div className="command-buttons">
          <button
            onClick={handleReboot}
            disabled={loading}
            className="control-button danger"
          >
            🔄 Reboot Device
          </button>

          <button
            onClick={handleForceRefresh}
            disabled={loading}
            className="control-button"
          >
            ⚡ Force Refresh
          </button>

          <button
            onClick={() => handleDiagnosticMode(true)}
            disabled={loading}
            className="control-button"
          >
            🔍 Enable Diagnostics
          </button>

          <button
            onClick={() => handleDiagnosticMode(false)}
            disabled={loading}
            className="control-button"
          >
            ❌ Disable Diagnostics
          </button>
        </div>
      </div>

      {error && (
        <div className="control-error">
          <strong>Error:</strong> {error}
        </div>
      )}

      {success && (
        <div className="control-success">
          <strong>Success:</strong> {success}
        </div>
      )}
    </div>
  );
}
