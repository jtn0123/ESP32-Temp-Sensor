import { useState, useEffect } from 'react';
import { deviceApi } from '../api/deviceApi';

export function DisplayViewer({ messages }) {
  const [screenshot, setScreenshot] = useState(null);
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [refreshInterval, setRefreshInterval] = useState(10);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Listen for screenshot messages from WebSocket
  useEffect(() => {
    const screenshotMessages = messages.filter(m => m.type === 'screenshot');
    if (screenshotMessages.length > 0) {
      const latest = screenshotMessages[screenshotMessages.length - 1];
      setScreenshot(latest);
      setLastUpdate(new Date());
      setLoading(false);
    }
  }, [messages]);

  // Auto-refresh timer
  useEffect(() => {
    if (!autoRefresh) return;

    const interval = setInterval(() => {
      handleRefresh();
    }, refreshInterval * 1000);

    return () => clearInterval(interval);
  }, [autoRefresh, refreshInterval]);

  const handleRefresh = async () => {
    setLoading(true);
    setError(null);

    try {
      await deviceApi.requestScreenshot();
      // Screenshot will arrive via WebSocket
    } catch (err) {
      console.error('Error requesting screenshot:', err);
      setError(err.message);
      setLoading(false);
    }
  };

  const handleLoadTest = async () => {
    setLoading(true);
    setError(null);

    try {
      const testImage = await deviceApi.getTestScreenshot();
      setScreenshot(testImage);
      setLastUpdate(new Date());
    } catch (err) {
      console.error('Error loading test screenshot:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleToggleAutoRefresh = () => {
    setAutoRefresh(!autoRefresh);
    if (!autoRefresh && !screenshot) {
      handleRefresh();
    }
  };

  const formatLastUpdate = () => {
    if (!lastUpdate) return 'Never';
    const now = new Date();
    const diff = Math.floor((now - lastUpdate) / 1000);

    if (diff < 60) return `${diff}s ago`;
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    return lastUpdate.toLocaleTimeString();
  };

  return (
    <div className="display-viewer">
      <div className="viewer-controls">
        <button
          onClick={handleRefresh}
          disabled={loading}
          className="refresh-button"
        >
          {loading ? '⏳ Refreshing...' : '🔄 Refresh'}
        </button>

        <button
          onClick={handleLoadTest}
          disabled={loading}
          className="test-button"
        >
          📊 Load Test Image
        </button>

        <div className="auto-refresh-controls">
          <label className="auto-refresh-checkbox">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={handleToggleAutoRefresh}
            />
            Auto-refresh
          </label>

          {autoRefresh && (
            <select
              value={refreshInterval}
              onChange={(e) => setRefreshInterval(Number(e.target.value))}
              className="interval-select"
            >
              <option value={5}>Every 5s</option>
              <option value={10}>Every 10s</option>
              <option value={30}>Every 30s</option>
              <option value={60}>Every 1m</option>
            </select>
          )}
        </div>

        <span className="last-update">
          Last update: {formatLastUpdate()}
        </span>
      </div>

      {error && (
        <div className="viewer-error">
          <strong>Error:</strong> {error}
        </div>
      )}

      <div className="screenshot-container">
        {screenshot ? (
          <div className="screenshot-wrapper">
            <img
              src={`data:image/png;base64,${screenshot.data}`}
              alt="ESP32 Display"
              className="screenshot-image"
              style={{
                width: screenshot.width * 2, // Scale 2x for visibility
                height: screenshot.height * 2,
                imageRendering: 'pixelated' // Keep sharp edges
              }}
            />
            <div className="screenshot-info">
              {screenshot.width}x{screenshot.height}
              {screenshot.test && ' (Test Image)'}
            </div>
          </div>
        ) : (
          <div className="no-screenshot">
            <p>No screenshot available</p>
            <p>Click "Refresh" to request a screenshot from the device</p>
            <p>or "Load Test Image" to see a sample</p>
          </div>
        )}
      </div>
    </div>
  );
}
