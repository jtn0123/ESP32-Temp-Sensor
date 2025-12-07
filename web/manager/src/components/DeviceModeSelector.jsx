import { useState, useEffect } from 'react';
import { deviceApi } from '../api/deviceApi';

/**
 * DeviceModeSelector - Configure device mode and sleep interval
 * 
 * Features:
 * - Toggle between Dev and Production mode
 * - Select sleep interval from presets (3, 5, 10, 60 min)
 * - Shows dev mode timeout countdown
 * - Confirmation dialog for mode changes
 */
export function DeviceModeSelector({ deviceId, onStateChange }) {
  const [state, setState] = useState(null);
  const [presets, setPresets] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [showConfirm, setShowConfirm] = useState(false);
  const [pendingMode, setPendingMode] = useState(null);

  // Fetch device state and presets
  useEffect(() => {
    fetchState();
    fetchPresets();
    
    // Poll for state updates
    const interval = setInterval(fetchState, 5000);
    return () => clearInterval(interval);
  }, [deviceId]);

  const fetchState = async () => {
    if (!deviceId) return;
    
    try {
      const data = await deviceApi.getDeviceState(deviceId);
      setState(data);
    } catch (err) {
      // Device might not exist yet
      if (!err.message.includes('404')) {
        console.error('Error fetching device state:', err);
      }
    }
  };

  const fetchPresets = async () => {
    try {
      const data = await deviceApi.getIntervalPresets();
      setPresets(data.presets || []);
    } catch (err) {
      console.error('Error fetching presets:', err);
    }
  };

  const handleModeChange = (newMode) => {
    if (newMode === 'dev' && state?.mode !== 'dev') {
      // Show confirmation for entering dev mode
      setPendingMode(newMode);
      setShowConfirm(true);
    } else {
      // Direct change for production mode
      applyMode(newMode);
    }
  };

  const applyMode = async (mode) => {
    setShowConfirm(false);
    setPendingMode(null);
    setLoading(true);
    setError(null);
    setSuccess(null);

    try {
      const result = await deviceApi.setDeviceMode(deviceId, mode);
      setState(prev => ({ ...prev, mode }));
      setSuccess(`Mode set to ${mode}`);
      
      if (onStateChange) {
        onStateChange(result);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleIntervalChange = async (intervalSec) => {
    setLoading(true);
    setError(null);
    setSuccess(null);

    try {
      await deviceApi.setDeviceInterval(deviceId, intervalSec);
      setState(prev => ({ ...prev, sleep_interval_sec: intervalSec }));
      setSuccess(`Interval set to ${formatInterval(intervalSec)}`);
      
      if (onStateChange) {
        onStateChange({ interval_sec: intervalSec });
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const formatInterval = (seconds) => {
    if (seconds < 60) return `${seconds}s`;
    if (seconds < 3600) return `${seconds / 60} min`;
    return `${seconds / 3600} hr`;
  };

  const formatTime = (seconds) => {
    if (seconds < 60) return `${Math.round(seconds)}s`;
    const mins = Math.floor(seconds / 60);
    const secs = Math.round(seconds % 60);
    return `${mins}m ${secs}s`;
  };

  if (!deviceId) {
    return (
      <div className="mode-selector disabled">
        <p>Select a target device to configure</p>
      </div>
    );
  }

  const currentMode = state?.mode || 'production';
  const currentInterval = state?.sleep_interval_sec || 600;
  const devModeRemaining = state?.dev_mode_remaining_sec || 0;

  return (
    <div className="mode-selector">
      {/* Mode Selection */}
      <div className="mode-section">
        <h4>Device Mode</h4>
        
        <div className="mode-options">
          <label 
            className={`mode-option ${currentMode === 'production' ? 'selected' : ''}`}
            onClick={() => handleModeChange('production')}
          >
            <input 
              type="radio" 
              name="mode" 
              value="production"
              checked={currentMode === 'production'}
              onChange={() => handleModeChange('production')}
              disabled={loading}
            />
            <div className="mode-content">
              <span className="mode-icon">🔋</span>
              <span className="mode-name">Production Mode</span>
              <span className="mode-desc">Power optimized, for deployment</span>
            </div>
          </label>

          <label 
            className={`mode-option ${currentMode === 'dev' ? 'selected' : ''}`}
            onClick={() => handleModeChange('dev')}
          >
            <input 
              type="radio" 
              name="mode" 
              value="dev"
              checked={currentMode === 'dev'}
              onChange={() => handleModeChange('dev')}
              disabled={loading}
            />
            <div className="mode-content">
              <span className="mode-icon">🔧</span>
              <span className="mode-name">Development Mode</span>
              <span className="mode-desc">Screenshots enabled, fixed intervals</span>
            </div>
          </label>
        </div>

        {currentMode === 'dev' && devModeRemaining > 0 && (
          <div className="dev-mode-warning">
            <span className="warning-icon">⚠️</span>
            <span>Auto-expires in: <strong>{formatTime(devModeRemaining)}</strong></span>
          </div>
        )}
      </div>

      {/* Interval Selection */}
      <div className="interval-section">
        <h4>Sleep Interval</h4>
        <p className="interval-hint">
          Minimum 3 minutes to prevent sensor self-heating
        </p>
        
        <div className="interval-presets">
          {presets.map(preset => (
            <button
              key={preset.value}
              className={`interval-button ${currentInterval === preset.value ? 'selected' : ''}`}
              onClick={() => handleIntervalChange(preset.value)}
              disabled={loading}
            >
              <span className="preset-icon">{preset.icon}</span>
              <span className="preset-name">{preset.name}</span>
            </button>
          ))}
        </div>

        <div className="current-interval">
          Current: <strong>{formatInterval(currentInterval)}</strong>
        </div>
      </div>

      {/* Status Messages */}
      {error && (
        <div className="mode-error">
          <strong>Error:</strong> {error}
        </div>
      )}
      
      {success && (
        <div className="mode-success">
          ✓ {success}
        </div>
      )}

      {/* Confirmation Dialog */}
      {showConfirm && (
        <div className="confirm-overlay">
          <div className="confirm-dialog">
            <h4>⚠️ Enable Development Mode?</h4>
            <p>
              Development mode will:
            </p>
            <ul>
              <li>Enable screenshot capture</li>
              <li>Increase power consumption</li>
              <li>Use fixed sleep intervals</li>
            </ul>
            <p className="confirm-warning">
              Dev mode will <strong>auto-expire in 1 hour</strong> to prevent battery drain.
            </p>
            <div className="confirm-buttons">
              <button 
                onClick={() => setShowConfirm(false)} 
                className="cancel-button"
              >
                Cancel
              </button>
              <button 
                onClick={() => applyMode('dev')} 
                className="confirm-button"
              >
                Enable Dev Mode
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
