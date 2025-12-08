import { useState, useEffect } from 'react';
import { Wifi, WifiOff, Plug, Radio, Target, Activity } from 'lucide-react';
import { deviceApi } from '../api/deviceApi';

export function StatusBar({ wsConnected, serialConnected, serialPort, targetDevice }) {
  const [mqttStatus, setMqttStatus] = useState({ connected: false });
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    loadMqttStatus();
    const interval = setInterval(loadMqttStatus, 5000);
    return () => clearInterval(interval);
  }, []);

  const loadMqttStatus = async () => {
    try {
      const status = await deviceApi.getMqttStatus();
      setMqttStatus(status.broker || { connected: false });
    } catch (err) {
      console.error('Error loading MQTT status:', err);
    }
  };

  const StatusIndicator = ({ connected, label, icon: Icon, detail }) => (
    <div className={`status-item ${connected ? 'connected' : 'disconnected'}`}>
      <span className="status-dot" />
      <Icon size={14} className="status-icon" />
      <span className="status-label">{label}</span>
      {detail && <span className="status-detail">{detail}</span>}
    </div>
  );

  return (
    <footer className={`status-bar ${expanded ? 'expanded' : ''}`}>
      <div className="status-bar-main" onClick={() => setExpanded(!expanded)}>
        <div className="status-group">
          <StatusIndicator
            connected={wsConnected}
            label="WebSocket"
            icon={Activity}
          />
          <StatusIndicator
            connected={mqttStatus.connected}
            label="MQTT"
            icon={Radio}
          />
          <StatusIndicator
            connected={serialConnected}
            label="Serial"
            icon={Plug}
            detail={serialConnected ? serialPort : null}
          />
        </div>

        <div className="status-group">
          {targetDevice ? (
            <div className="status-item target-device">
              <Target size={14} className="status-icon" />
              <span className="status-label">Target:</span>
              <span className="status-value">{targetDevice}</span>
            </div>
          ) : (
            <div className="status-item no-target">
              <Target size={14} className="status-icon" />
              <span className="status-label">No device targeted</span>
            </div>
          )}
        </div>

        <div className="status-expand-hint">
          {expanded ? 'Click to collapse' : 'Click for details'}
        </div>
      </div>

      {expanded && (
        <div className="status-bar-details">
          <div className="detail-section">
            <h4>Connection Details</h4>
            <div className="detail-grid">
              <div className="detail-item">
                <span className="detail-label">WebSocket</span>
                <span className={`detail-value ${wsConnected ? 'ok' : 'error'}`}>
                  {wsConnected ? 'Connected' : 'Disconnected'}
                </span>
              </div>
              <div className="detail-item">
                <span className="detail-label">MQTT Broker</span>
                <span className={`detail-value ${mqttStatus.connected ? 'ok' : 'error'}`}>
                  {mqttStatus.connected ? `Connected (${mqttStatus.host || 'localhost'}:${mqttStatus.port || 18884})` : 'Disconnected'}
                </span>
              </div>
              <div className="detail-item">
                <span className="detail-label">Serial Port</span>
                <span className={`detail-value ${serialConnected ? 'ok' : 'warn'}`}>
                  {serialConnected ? serialPort : 'Not connected'}
                </span>
              </div>
              <div className="detail-item">
                <span className="detail-label">Target Device</span>
                <span className={`detail-value ${targetDevice ? 'ok' : 'warn'}`}>
                  {targetDevice || 'None selected'}
                </span>
              </div>
            </div>
          </div>
        </div>
      )}
    </footer>
  );
}
