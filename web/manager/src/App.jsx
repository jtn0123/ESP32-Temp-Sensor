import { useState, useEffect } from 'react';
import { useWebSocket } from './hooks/useWebSocket';
import { Sidebar } from './components/Sidebar';
import { StatusBar } from './components/StatusBar';
import { DashboardHome } from './components/DashboardHome';
import { SimulatorView } from './components/SimulatorView';
import { DeviceSelector } from './components/DeviceSelector';
import { SerialConsole } from './components/SerialConsole';
import { FlashManager } from './components/FlashManager';
import { MqttInspector } from './components/MqttInspector';
import { DisplayViewer } from './components/DisplayViewer';
import { StatusDashboard } from './components/StatusDashboard';
import { WakePrediction } from './components/WakePrediction';
import './styles/manager.css';

function App() {
  const [activeView, setActiveView] = useState('dashboard');
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
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

  // Render the active view content
  const renderContent = () => {
    switch (activeView) {
      case 'dashboard':
        return (
          <DashboardHome
            serialConnected={connected}
            wsConnected={wsConnected}
            targetDevice={targetDevice}
            messages={messages}
            onConnect={handleConnect}
            onTargetChange={handleTargetChange}
          />
        );
      
      case 'simulator':
        return <SimulatorView />;
      
      case 'flash':
        return (
          <div className="view-container">
            <div className="view-header">
              <h2>Build & Flash</h2>
              <p className="view-description">Configure and flash firmware to your ESP32 device</p>
            </div>
            <FlashManager 
              messages={messages} 
              serialPort={serialPort}
              targetDevice={targetDevice}
            />
          </div>
        );
      
      case 'serial':
        return (
          <div className="view-container">
            <div className="view-header">
              <h2>Serial Console</h2>
              <p className="view-description">Monitor serial output and send commands</p>
            </div>
            <SerialConsole messages={messages} send={send} />
          </div>
        );
      
      case 'mqtt':
        return (
          <div className="view-container">
            <div className="view-header">
              <h2>MQTT Debug</h2>
              <p className="view-description">Monitor MQTT messages and test the simulator</p>
            </div>
            <MqttInspector messages={messages} />
          </div>
        );
      
      case 'settings':
        return (
          <div className="view-container">
            <div className="view-header">
              <h2>Settings</h2>
              <p className="view-description">Configure device connections and preferences</p>
            </div>
            <DeviceSelector 
              onConnect={handleConnect} 
              connected={connected}
              onTargetChange={handleTargetChange}
            />
          </div>
        );
      
      default:
        return <DashboardHome />;
    }
  };

  return (
    <div className={`app-layout ${sidebarCollapsed ? 'sidebar-collapsed' : ''}`}>
      <Sidebar
        activeView={activeView}
        onViewChange={setActiveView}
        collapsed={sidebarCollapsed}
        onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
      />
      
      <main className="main-content">
        {renderContent()}
      </main>
      
      <StatusBar
        wsConnected={wsConnected}
        serialConnected={connected}
        serialPort={serialPort}
        targetDevice={targetDevice}
      />
    </div>
  );
}

export default App;
