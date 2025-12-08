import { useState, useEffect, useCallback } from 'react';
import { deviceApi } from '../api/deviceApi';

/**
 * WakePrediction - Shows countdown to next device wake
 * 
 * Displays:
 * - Current status (Awake/Sleeping/Unknown)
 * - Last activity timestamp
 * - Countdown to next wake
 * - Progress bar through sleep cycle
 */
export function WakePrediction({ deviceId }) {
  const [state, setState] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Fetch device state - memoized to prevent unnecessary re-renders
  const fetchState = useCallback(async () => {
    if (!deviceId) {
      setState(null);
      setLoading(false);
      return;
    }

    try {
      const data = await deviceApi.getDeviceState(deviceId);
      setState(data);
      setError(null);
    } catch (err) {
      // Device might not be tracked yet
      if (err.message.includes('404')) {
        setState(null);
      } else {
        setError(err.message);
      }
    } finally {
      setLoading(false);
    }
  }, [deviceId]);

  // Initial fetch and polling
  useEffect(() => {
    fetchState();
    
    // Poll every second for countdown updates
    const interval = setInterval(fetchState, 1000);
    return () => clearInterval(interval);
  }, [fetchState]);

  // Format seconds as human readable
  const formatTime = (seconds) => {
    if (seconds < 0) return 'Overdue';
    if (seconds < 60) return `${Math.round(seconds)}s`;
    if (seconds < 3600) {
      const mins = Math.floor(seconds / 60);
      const secs = Math.round(seconds % 60);
      return `${mins}m ${secs}s`;
    }
    const hrs = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    return `${hrs}h ${mins}m`;
  };

  // Format timestamp
  const formatTimestamp = (timestamp) => {
    if (!timestamp || timestamp === 0) return 'Never';
    const date = new Date(timestamp * 1000);
    return date.toLocaleTimeString();
  };

  // Get status emoji and text
  const getStatusDisplay = (status) => {
    switch (status) {
      case 'awake':
        return { emoji: '⚡', text: 'Awake', className: 'status-awake' };
      case 'sleeping':
        return { emoji: '💤', text: 'Sleeping', className: 'status-sleeping' };
      default:
        return { emoji: '❓', text: 'Unknown', className: 'status-unknown' };
    }
  };

  if (!deviceId) {
    return (
      <div className="wake-prediction empty">
        <p>Select a target device to see wake predictions</p>
      </div>
    );
  }

  if (loading && !state) {
    return (
      <div className="wake-prediction loading">
        <p>Loading device state...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="wake-prediction error">
        <p>Error: {error}</p>
      </div>
    );
  }

  if (!state) {
    return (
      <div className="wake-prediction empty">
        <p>Waiting for device activity...</p>
        <p className="hint">Device will appear after first MQTT message or serial connection</p>
      </div>
    );
  }

  const statusDisplay = getStatusDisplay(state.status);
  const isOverdue = state.seconds_until_wake < 0 && state.status === 'sleeping';
  const progressCapped = Math.min(state.wake_progress_pct, 100);

  return (
    <div className="wake-prediction">
      <div className="prediction-header">
        <h4>⏱️ Wake Prediction</h4>
        <span className={`device-status ${statusDisplay.className}`}>
          {statusDisplay.emoji} {statusDisplay.text}
        </span>
      </div>

      <div className="prediction-details">
        <div className="detail-row">
          <span className="label">Device:</span>
          <span className="value">{state.reported_room || state.device_id}</span>
        </div>
        
        <div className="detail-row">
          <span className="label">Last seen:</span>
          <span className="value">{formatTimestamp(state.last_activity)}</span>
        </div>
        
        <div className="detail-row">
          <span className="label">Sleep interval:</span>
          <span className="value">{formatTime(state.sleep_interval_sec)}</span>
        </div>
      </div>

      {state.status === 'sleeping' && (
        <div className="countdown-section">
          <div className="countdown-header">
            <span className="label">Next wake in:</span>
            <span className={`countdown-value ${isOverdue ? 'overdue' : ''}`}>
              {isOverdue ? '⚠️ ' : ''}{formatTime(Math.abs(state.seconds_until_wake))}
              {isOverdue ? ' overdue' : ''}
            </span>
          </div>
          
          <div className="progress-bar-container">
            <div 
              className={`progress-bar ${isOverdue ? 'overdue' : ''}`}
              style={{ width: `${progressCapped}%` }}
            />
          </div>
          
          <div className="progress-label">
            {Math.round(state.wake_progress_pct)}% of sleep cycle
          </div>
        </div>
      )}

      {state.status === 'awake' && (
        <div className="awake-section">
          <p className="awake-message">
            ⚡ Device is currently awake and active
          </p>
          <p className="awake-hint">
            Will sleep in ~{formatTime(30 - state.seconds_since_activity)} if no activity
          </p>
        </div>
      )}

      {/* Mode indicator */}
      {state.mode === 'dev' && (
        <div className="mode-warning">
          <span className="warning-icon">🔧</span>
          <span className="warning-text">
            Dev mode - expires in {formatTime(state.dev_mode_remaining_sec)}
          </span>
        </div>
      )}
    </div>
  );
}
