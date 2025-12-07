import { useState } from 'react';
import { useWebSocket } from './hooks/useWebSocket';
import { DeviceSelector } from './components/DeviceSelector';
import { SerialConsole } from './components/SerialConsole';
import { FlashManager } from './components/FlashManager';
import { MqttInspector } from './components/MqttInspector';
import { DisplayViewer } from './components/DisplayViewer';
import { StatusDashboard } from './components/StatusDashboard';
import { WakePrediction } from './components/WakePrediction';
import { CollapsibleSection } from './components/CollapsibleSection';
import './styles/manager.css';

function App() {
  const [connected, setConnected] = useState(false);
  const [serialPort, setSerialPort] = useState(null);
  const [targetDevice, setTargetDevice] = useState(null);
  const { connected: wsConnected, messages, send } = useWebSocket();

  const handleConnect = (isConnected, port) => {
    setConnected(isConnected);
    if (isConnected && port) {
      setSerialPort(port);
    } else {
      setSerialPort(null);
    }
  };

  const handleTargetChange = (deviceId) => {
    setTargetDevice(deviceId);
  };

  return (
    <div className="device-manager">
      <header className="app-header">
        <h1>ESP32 Device Manager</h1>
        <div className="connection-status">
          <span className={`status-indicator ${wsConnected ? 'connected' : 'disconnected'}`}>
            {wsConnected ? '🟢' : '🔴'} WebSocket
          </span>
          <span className={`status-indicator ${connected ? 'connected' : 'disconnected'}`}>
            {connected ? '🟢' : '🔴'} Serial
          </span>
          {targetDevice && (
            <span className="status-indicator connected">
              🎯 {targetDevice}
            </span>
          )}
        </div>
      </header>

      <main className="app-main single-page">
        <CollapsibleSection title="Device Connection" icon="🔌" defaultOpen={true}>
          <DeviceSelector 
            onConnect={handleConnect} 
            connected={connected}
            onTargetChange={handleTargetChange}
          />
        </CollapsibleSection>

        <CollapsibleSection title="Build & Flash" icon="⚡" defaultOpen={true}>
          <FlashManager 
            messages={messages} 
            serialPort={serialPort}
            targetDevice={targetDevice}
          />
        </CollapsibleSection>

        <CollapsibleSection title="Monitor" icon="📊" defaultOpen={false}>
          <div className="monitor-section">
            <WakePrediction deviceId={targetDevice} />
            <StatusDashboard
              serialConnected={connected}
              mqttConnected={wsConnected}
            />
            <DisplayViewer messages={messages} />
          </div>
        </CollapsibleSection>

        <CollapsibleSection title="Serial Console" icon="📟" defaultOpen={false}>
          <SerialConsole messages={messages} send={send} />
        </CollapsibleSection>

        <CollapsibleSection title="MQTT Debug" icon="📡" defaultOpen={false}>
          <MqttInspector messages={messages} />
        </CollapsibleSection>
      </main>
    </div>
  );
}

export default App;
