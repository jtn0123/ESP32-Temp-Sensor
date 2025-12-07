import { useState } from 'react';
import { Tab, Tabs, TabList, TabPanel } from 'react-tabs';
import 'react-tabs/style/react-tabs.css';
import { useWebSocket } from './hooks/useWebSocket';
import { DeviceSelector } from './components/DeviceSelector';
import { SerialConsole } from './components/SerialConsole';
import { FlashManager } from './components/FlashManager';
import { MqttInspector } from './components/MqttInspector';
import { DisplayViewer } from './components/DisplayViewer';
import { ControlPanel } from './components/ControlPanel';
import { StatusDashboard } from './components/StatusDashboard';
import { WakePrediction } from './components/WakePrediction';
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

      <main className="app-main">
        <Tabs>
          <TabList>
            <Tab>🔌 Connect</Tab>
            <Tab>📟 Console</Tab>
            <Tab>📊 Dashboard</Tab>
            <Tab>🖼️ Display</Tab>
            <Tab>⚡ Flash</Tab>
            <Tab>📡 MQTT</Tab>
          </TabList>

          <TabPanel>
            <DeviceSelector 
              onConnect={handleConnect} 
              connected={connected}
              onTargetChange={handleTargetChange}
            />
          </TabPanel>

          <TabPanel>
            <SerialConsole messages={messages} send={send} />
          </TabPanel>

          <TabPanel>
            <div className="dashboard-layout">
              <div className="dashboard-main">
                <WakePrediction deviceId={targetDevice} />
                <StatusDashboard
                  serialConnected={connected}
                  mqttConnected={wsConnected}
                />
              </div>
              <ControlPanel />
            </div>
          </TabPanel>

          <TabPanel>
            <DisplayViewer messages={messages} />
          </TabPanel>

          <TabPanel>
            <FlashManager 
              messages={messages} 
              serialPort={serialPort}
              targetDevice={targetDevice}
            />
          </TabPanel>

          <TabPanel>
            <MqttInspector messages={messages} />
          </TabPanel>
        </Tabs>
      </main>
    </div>
  );
}

export default App;
