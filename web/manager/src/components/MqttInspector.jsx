import { useState, useEffect, useRef } from 'react';
import { deviceApi } from '../api/deviceApi';

export function MqttInspector({ messages }) {
  const [topicFilter, setTopicFilter] = useState('');
  const [payloadFilter, setPayloadFilter] = useState('');
  const [publishTopic, setPublishTopic] = useState('espsensor/office/cmd/test');
  const [publishPayload, setPublishPayload] = useState('');
  const [publishRetain, setPublishRetain] = useState(false);
  const [simulatorRunning, setSimulatorRunning] = useState(false);
  const [mqttStatus, setMqttStatus] = useState(null);
  const [error, setError] = useState(null);
  const messagesEndRef = useRef(null);

  // Load MQTT status on mount
  useEffect(() => {
    loadMqttStatus();
    const interval = setInterval(loadMqttStatus, 5000); // Refresh every 5s
    return () => clearInterval(interval);
  }, []);

  const loadMqttStatus = async () => {
    try {
      const status = await deviceApi.getMqttStatus();
      setMqttStatus(status);
      setSimulatorRunning(status.simulator?.running || false);
    } catch (err) {
      console.error('Error loading MQTT status:', err);
    }
  };

  // Filter MQTT messages
  const mqttMessages = messages.filter(m => m.type === 'mqtt');
  const filteredMessages = mqttMessages.filter(msg => {
    if (topicFilter && !msg.topic?.toLowerCase().includes(topicFilter.toLowerCase())) {
      return false;
    }
    if (payloadFilter && !msg.payload?.toLowerCase().includes(payloadFilter.toLowerCase())) {
      return false;
    }
    return true;
  });

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [filteredMessages]);

  const handlePublish = async (e) => {
    e.preventDefault();
    if (!publishTopic || !publishPayload) return;

    setError(null);
    try {
      await deviceApi.publishMqtt(publishTopic, publishPayload, publishRetain);
      setPublishPayload(''); // Clear after publish
    } catch (err) {
      console.error('Error publishing MQTT:', err);
      setError(err.message);
    }
  };

  const handleToggleSimulator = async () => {
    setError(null);
    try {
      if (simulatorRunning) {
        await deviceApi.stopMqttSimulator();
      } else {
        await deviceApi.startMqttSimulator();
      }
      // Status will update on next poll
    } catch (err) {
      console.error('Error toggling simulator:', err);
      setError(err.message);
    }
  };

  const formatTimestamp = (timestamp) => {
    return new Date(timestamp * 1000).toLocaleTimeString();
  };

  const getDirectionIcon = (direction) => {
    return direction === 'in' ? '←' : '→';
  };

  const getDirectionClass = (direction) => {
    return direction === 'in' ? 'mqtt-in' : 'mqtt-out';
  };

  return (
    <div className="mqtt-inspector">
      <div className="mqtt-controls">
        {/* Status section */}
        <div className="mqtt-status-section">
          <h3>MQTT Status</h3>
          <div className="status-grid">
            <div className="status-item">
              <span className="status-label">Broker:</span>
              <span className={`status-value ${mqttStatus?.broker?.connected ? 'connected' : 'disconnected'}`}>
                {mqttStatus?.broker?.connected ? 'Connected' : 'Disconnected'}
              </span>
            </div>
            <div className="status-item">
              <span className="status-label">Messages:</span>
              <span className="status-value">{mqttMessages.length}</span>
            </div>
            <div className="status-item">
              <span className="status-label">Simulator:</span>
              <span className={`status-value ${simulatorRunning ? 'running' : 'stopped'}`}>
                {simulatorRunning ? 'Running' : 'Stopped'}
              </span>
            </div>
          </div>
        </div>

        {/* Simulator controls */}
        <div className="simulator-controls">
          <h3>Simulator</h3>
          <button onClick={handleToggleSimulator} className="simulator-button">
            {simulatorRunning ? 'Stop Simulator' : 'Start Simulator'}
          </button>
          <p className="simulator-description">
            Generate fake Home Assistant weather data for testing
          </p>
        </div>

        {/* Publish form */}
        <form onSubmit={handlePublish} className="publish-form">
          <h3>Publish Message</h3>
          <div className="form-row">
            <input
              type="text"
              placeholder="Topic (e.g., espsensor/office/cmd/test)"
              value={publishTopic}
              onChange={(e) => setPublishTopic(e.target.value)}
              className="topic-input"
            />
          </div>
          <div className="form-row">
            <input
              type="text"
              placeholder="Payload"
              value={publishPayload}
              onChange={(e) => setPublishPayload(e.target.value)}
              className="payload-input"
            />
          </div>
          <div className="form-row">
            <label className="retain-checkbox">
              <input
                type="checkbox"
                checked={publishRetain}
                onChange={(e) => setPublishRetain(e.target.checked)}
              />
              Retain message
            </label>
            <button type="submit" disabled={!publishTopic || !publishPayload}>
              Publish
            </button>
          </div>
        </form>

        {error && <div className="mqtt-error">{error}</div>}
      </div>

      {/* Message filters */}
      <div className="message-filters">
        <input
          type="text"
          placeholder="Filter by topic..."
          value={topicFilter}
          onChange={(e) => setTopicFilter(e.target.value)}
          className="filter-input"
        />
        <input
          type="text"
          placeholder="Filter by payload..."
          value={payloadFilter}
          onChange={(e) => setPayloadFilter(e.target.value)}
          className="filter-input"
        />
        <span className="message-count">
          {filteredMessages.length} / {mqttMessages.length} messages
        </span>
      </div>

      {/* Message log */}
      <div className="mqtt-messages">
        {filteredMessages.length === 0 ? (
          <div className="no-messages">
            No MQTT messages yet. Start the simulator or publish a message to begin.
          </div>
        ) : (
          filteredMessages.map((msg, idx) => (
            <div key={idx} className={`mqtt-message ${getDirectionClass(msg.direction)}`}>
              <span className="message-time">{formatTimestamp(msg.timestamp)}</span>
              <span className="message-direction">{getDirectionIcon(msg.direction)}</span>
              <span className="message-topic">{msg.topic}</span>
              <span className="message-payload">{msg.payload}</span>
            </div>
          ))
        )}
        <div ref={messagesEndRef} />
      </div>
    </div>
  );
}
