import { useState, useEffect } from 'react';
import { 
  Cpu, 
  Battery, 
  Thermometer, 
  Droplets, 
  Wifi, 
  Clock,
  Target,
  Activity,
  RefreshCw
} from 'lucide-react';
import { deviceApi } from '../api/deviceApi';
import { DeviceSelector } from './DeviceSelector';
import { DisplayViewer } from './DisplayViewer';
import { WakePrediction } from './WakePrediction';

export function DashboardHome({ 
  serialConnected, 
  wsConnected, 
  targetDevice, 
  messages,
  onConnect,
  onTargetChange 
}) {
  const [deviceStatus, setDeviceStatus] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadDeviceStatus();
    const interval = setInterval(loadDeviceStatus, 5000);
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

  const getBatteryColor = (percent) => {
    if (!percent) return 'var(--color-text-muted)';
    const val = parseInt(percent);
    if (val > 60) return 'var(--color-success)';
    if (val > 30) return 'var(--color-warning)';
    return 'var(--color-error)';
  };

  const StatusCard = ({ icon: Icon, label, value, detail, status }) => (
    <div className={`dashboard-card ${status || ''}`}>
      <div className="card-icon-wrapper">
        <Icon size={24} />
      </div>
      <div className="card-content">
        <span className="card-label">{label}</span>
        <span className="card-value">{value}</span>
        {detail && <span className="card-detail">{detail}</span>}
      </div>
    </div>
  );

  return (
    <div className="dashboard-home">
      {/* Quick Connect Section */}
      <section className="dashboard-section connect-section">
        <div className="section-header">
          <h3>Device Connection</h3>
          {targetDevice && (
            <span className="target-badge">
              <Target size={14} /> {targetDevice}
            </span>
          )}
        </div>
        <DeviceSelector 
          onConnect={onConnect} 
          connected={serialConnected}
          onTargetChange={onTargetChange}
          compact={true}
        />
      </section>

      {/* Status Cards Grid */}
      <section className="dashboard-section">
        <div className="section-header">
          <h3>Device Status</h3>
          <button 
            className="refresh-btn"
            onClick={loadDeviceStatus}
            disabled={loading}
          >
            <RefreshCw size={14} className={loading ? 'spinning' : ''} />
          </button>
        </div>
        
        <div className="status-cards-grid">
          <StatusCard
            icon={Wifi}
            label="Connection"
            value={deviceStatus?.connected ? 'Online' : 'Offline'}
            detail={deviceStatus?.last_seen ? `Last seen: ${formatLastSeen(deviceStatus.last_seen)}` : null}
            status={deviceStatus?.connected ? 'success' : 'muted'}
          />
          <StatusCard
            icon={Battery}
            label="Battery"
            value={deviceStatus?.battery ? `${deviceStatus.battery}%` : 'N/A'}
            status={deviceStatus?.battery > 60 ? 'success' : deviceStatus?.battery > 30 ? 'warning' : 'error'}
          />
          <StatusCard
            icon={Thermometer}
            label="Temperature"
            value={deviceStatus?.temperature ? `${deviceStatus.temperature}°F` : 'N/A'}
          />
          <StatusCard
            icon={Droplets}
            label="Humidity"
            value={deviceStatus?.humidity ? `${deviceStatus.humidity}%` : 'N/A'}
          />
          <StatusCard
            icon={Cpu}
            label="Free Heap"
            value={deviceStatus?.heap ? `${(parseInt(deviceStatus.heap) / 1024).toFixed(1)} KB` : 'N/A'}
          />
          <StatusCard
            icon={Activity}
            label="WebSocket"
            value={wsConnected ? 'Connected' : 'Disconnected'}
            status={wsConnected ? 'success' : 'error'}
          />
        </div>
      </section>

      {/* Wake Prediction & Display */}
      <div className="dashboard-row">
        <section className="dashboard-section flex-1">
          <div className="section-header">
            <h3>Wake Prediction</h3>
          </div>
          <WakePrediction deviceId={targetDevice} />
        </section>
        
        <section className="dashboard-section flex-1">
          <div className="section-header">
            <h3>Display Preview</h3>
          </div>
          <DisplayViewer messages={messages} compact={true} />
        </section>
      </div>
    </div>
  );
}
