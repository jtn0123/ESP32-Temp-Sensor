import { useState, useEffect, useRef } from 'react';
import { deviceApi } from '../api/deviceApi';

export function SerialConsole({ messages, send }) {
  const [filter, setFilter] = useState('');
  const [paused, setPaused] = useState(false);
  const [commandInput, setCommandInput] = useState('');
  const consoleRef = useRef(null);

  // Auto-scroll to bottom unless paused
  useEffect(() => {
    if (!paused && consoleRef.current) {
      consoleRef.current.scrollTop = consoleRef.current.scrollHeight;
    }
  }, [messages, paused]);

  // Filter serial messages
  const serialMessages = messages.filter(m => m.type === 'serial');
  const filteredMessages = filter
    ? serialMessages.filter(m => m.data.toLowerCase().includes(filter.toLowerCase()))
    : serialMessages;

  const handleSendCommand = async (e) => {
    e.preventDefault();
    if (commandInput.trim()) {
      try {
        send({ type: 'serial_send', data: commandInput });
        setCommandInput('');
      } catch (err) {
        console.error('Error sending command:', err);
      }
    }
  };

  const handleClear = () => {
    // This would need to clear the messages state in the parent
    console.log('Clear console');
  };

  const getLineColor = (line) => {
    if (line.includes('[ERROR]') || line.includes('ERROR:')) return 'log-error';
    if (line.includes('[WARN]') || line.includes('WARNING:')) return 'log-warning';
    if (line.includes('[INFO]')) return 'log-info';
    if (line.includes('[DEBUG]')) return 'log-debug';
    return '';
  };

  return (
    <div className="serial-console">
      <div className="console-controls">
        <input
          type="text"
          placeholder="Filter..."
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="filter-input"
        />
        <button onClick={() => setPaused(!paused)}>
          {paused ? '▶ Resume' : '⏸ Pause'}
        </button>
        <button onClick={handleClear}>🗑 Clear</button>
        <span className="message-count">
          {filteredMessages.length} messages
        </span>
      </div>

      <div ref={consoleRef} className="console-output">
        {filteredMessages.map((msg, idx) => {
          const timestamp = new Date(msg.timestamp * 1000).toLocaleTimeString();
          return (
            <div key={idx} className={`log-line ${getLineColor(msg.data)}`}>
              <span className="timestamp">[{timestamp}]</span>
              <span className="log-data">{msg.data}</span>
            </div>
          );
        })}
      </div>

      <form onSubmit={handleSendCommand} className="console-input">
        <input
          type="text"
          placeholder="Send command..."
          value={commandInput}
          onChange={(e) => setCommandInput(e.target.value)}
        />
        <button type="submit">Send</button>
      </form>
    </div>
  );
}
