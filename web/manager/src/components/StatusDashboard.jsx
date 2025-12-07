import { useState, useEffect } from 'react';
import { deviceApi } from '../api/deviceApi';

export function StatusDashboard({ serialConnected, mqttConnected }) {
  const [deviceStatus, setDeviceStatus] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadDeviceStatus();
    const interval = setInterval(loadDeviceStatus, 5000); // Update every 5s
    return () => clearInterval(interval);
  }, []);

  const loadDeviceStatus = async () => {
    try {
      const status = await deviceApi.getDeviceStatus();
      setDeviceStatus(status);
      setLoading(false);
    } catch (err) {
      console.error('Error loading device status:', err);
      setLoading(false);
    }
  };

  const formatLastSeen = (timestamp) => {
    if (!timestamp) return 'Never';
    const now = Date.now() / 1000;
    const diff = Math.floor(now - timestamp);

    if (diff < 60) return `${diff}s ago`;
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    return `${Math.floor(diff / 86400)}d ago`;
  };

  const formatHeap = (heap) => {
    if (!heap) return 'N/A';
    const kb = parseInt(heap) / 1024;
    return `${kb.toFixed(1)} KB`;
  };

  const getBatteryColor = (percent) => {
    if (!percent) return '#888';
    const val = parseInt(percent);
    if (val > 60) return '#4ade80';
    if (val > 30) return '#fbbf24';
    return '#f87171';
  };

  return (
    <div className="status-dashboard">
      <div className="status-cards">
        {/* Serial Connection Card */}
        <div className={`status-card ${serialConnected ? 'connected' : 'disconnected'}`}>
          <div className="card-icon">🔌</div>
          <div className="card-content">
            <h3>Serial</h3>
            <div className="card-status">
              {serialConnected ? 'Connected' : 'Disconnected'}
            </div>
          </div>
        </div>

        {/* MQTT Connection Card */}
        <div className={`status-card ${mqttConnected ? 'connected' : 'disconnected'}`}>
          <div className="card-icon">📡</div>
          <div className="card-content">
            <h3>MQTT</h3>
            <div className="card-status">
              {mqttConnected ? 'Connected' : 'Disconnected'}
            </div>
          </div>
        </div>

        {/* Device Connection Card */}
        <div className={`status-card ${deviceStatus?.connected ? 'connected' : 'disconnected'}`}>
          <div className="card-icon">📱</div>
          <div className="card-content">
            <h3>Device</h3>
            <div className="card-status">
              {deviceStatus?.connected ? 'Online' : 'Offline'}
            </div>
            {deviceStatus?.last_seen && (
              <div className="card-detail">
                Last seen: {formatLastSeen(deviceStatus.last_seen)}
              </div>
            )}
          </div>
        </div>

        {/* Battery Card */}
        <div className="status-card">
          <div className="card-icon">🔋</div>
          <div className="card-content">
            <h3>Battery</h3>
            <div className="card-status" style={{ color: getBatteryColor(deviceStatus?.battery) }}>
              {deviceStatus?.battery ? `${deviceStatus.battery}%` : 'N/A'}
            </div>
            {deviceStatus?.battery && (
              <div className="battery-bar">
                <div
                  className="battery-fill"
                  style={{
                    width: `${deviceStatus.battery}%`,
                    backgroundColor: getBatteryColor(deviceStatus.battery)
                  }}
                />
              </div>
            )}
          </div>
        </div>

        {/* Temperature Card */}
        <div className="status-card">
          <div className="card-icon">🌡️</div>
          <div className="card-content">
            <h3>Temperature</h3>
            <div className="card-status">
              {deviceStatus?.temperature ? `${deviceStatus.temperature}°F` : 'N/A'}
            </div>
          </div>
        </div>

        {/* Humidity Card */}
        <div className="status-card">
          <div className="card-icon">💧</div>
          <div className="card-content">
            <h3>Humidity</h3>
            <div className="card-status">
              {deviceStatus?.humidity ? `${deviceStatus.humidity}%` : 'N/A'}
            </div>
          </div>
        </div>

        {/* Memory Card */}
        <div className="status-card">
          <div className="card-icon">💾</div>
          <div className="card-content">
            <h3>Free Heap</h3>
            <div className="card-status">
              {formatHeap(deviceStatus?.heap)}
            </div>
          </div>
        </div>

        {/* Refresh Info */}
        <div className="status-card info">
          <div className="card-icon">ℹ️</div>
          <div className="card-content">
            <h3>Status</h3>
            <div className="card-detail">
              {loading ? 'Loading...' : 'Auto-refresh: 5s'}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
