import { useState, useEffect } from 'react';
import { deviceApi } from '../api/deviceApi';

export function DeviceSelector({ onConnect, connected }) {
  const [ports, setPorts] = useState([]);
  const [selectedPort, setSelectedPort] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    loadPorts();
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
      setError('Failed to load ports');
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

  return (
    <div className="device-selector">
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

      {error && <div className="error-message">{error}</div>}
    </div>
  );
}
