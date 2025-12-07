import { useState } from 'react';
import { Tab, Tabs, TabList, TabPanel } from 'react-tabs';
import 'react-tabs/style/react-tabs.css';
import { useWebSocket } from './hooks/useWebSocket';
import { DeviceSelector } from './components/DeviceSelector';
import { SerialConsole } from './components/SerialConsole';
import { FlashManager } from './components/FlashManager';
import './styles/manager.css';

function App() {
  const [connected, setConnected] = useState(false);
  const [serialPort, setSerialPort] = useState(null);
  const { connected: wsConnected, messages, send } = useWebSocket();

  const handleConnect = (isConnected, port) => {
    setConnected(isConnected);
    if (isConnected && port) {
      setSerialPort(port);
    } else {
      setSerialPort(null);
    }
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
        </div>
        <DeviceSelector onConnect={handleConnect} connected={connected} />
      </header>

      <main className="app-main">
        <Tabs>
          <TabList>
            <Tab>Console</Tab>
            <Tab>Dashboard</Tab>
            <Tab>Display</Tab>
            <Tab>Flash</Tab>
            <Tab>MQTT</Tab>
          </TabList>

          <TabPanel>
            <SerialConsole messages={messages} send={send} />
          </TabPanel>

          <TabPanel>
            <div className="placeholder-panel">
              <h2>Status Dashboard</h2>
              <p>Coming soon: Device status, battery, memory stats</p>
            </div>
          </TabPanel>

          <TabPanel>
            <div className="placeholder-panel">
              <h2>Display Viewer</h2>
              <p>Coming soon: Screenshot display and refresh controls</p>
            </div>
          </TabPanel>

          <TabPanel>
            <FlashManager messages={messages} serialPort={serialPort} />
          </TabPanel>

          <TabPanel>
            <div className="placeholder-panel">
              <h2>MQTT Inspector</h2>
              <p>Coming soon: MQTT message viewer and publisher</p>
            </div>
          </TabPanel>
        </Tabs>
      </main>
    </div>
  );
}

export default App;
