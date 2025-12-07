import { useState, useEffect } from 'react';
import { deviceApi } from '../api/deviceApi';

export function FlashManager({ messages, serialPort }) {
  const [config, setConfig] = useState('dev');
  const [isFlashing, setIsFlashing] = useState(false);
  const [progress, setProgress] = useState(0);
  const [stage, setStage] = useState('');
  const [logs, setLogs] = useState([]);
  const [error, setError] = useState(null);

  // Listen for flash progress messages
  useEffect(() => {
    const flashMessages = messages.filter(
      m => m.type === 'flash_progress' || m.type === 'flash_complete'
    );

    if (flashMessages.length > 0) {
      const latest = flashMessages[flashMessages.length - 1];

      if (latest.type === 'flash_progress') {
        setProgress(latest.percent || 0);
        setStage(latest.stage || '');
        if (latest.message) {
          setLogs(prev => [...prev, latest.message]);
        }
      } else if (latest.type === 'flash_complete') {
        setIsFlashing(false);
        if (!latest.success) {
          setError(latest.message || 'Flash failed');
        } else {
          setLogs(prev => [...prev, latest.message || 'Flash complete!']);
        }
      }
    }
  }, [messages]);

  const handleFlash = async () => {
    if (!serialPort) {
      setError('No serial port selected. Please connect to a device first.');
      return;
    }

    setIsFlashing(true);
    setProgress(0);
    setStage('');
    setLogs([]);
    setError(null);

    try {
      await deviceApi.startFlash(config);
    } catch (err) {
      console.error('Error starting flash:', err);
      setError(err.message);
      setIsFlashing(false);
    }
  };

  const handleCancel = async () => {
    try {
      await deviceApi.cancelFlash();
      setIsFlashing(false);
      setLogs(prev => [...prev, 'Flash cancelled by user']);
    } catch (err) {
      console.error('Error cancelling flash:', err);
    }
  };

  const handleClearLogs = () => {
    setLogs([]);
    setError(null);
  };

  const configOptions = [
    { value: 'dev', label: 'Development (No Sleep)', description: 'DEV_NO_SLEEP=1, BOOT_DEBUG=1' },
    { value: 'prod', label: 'Production', description: 'Normal operation with sleep' },
    { value: 'battery_test', label: 'Battery Test', description: 'Verbose battery logging' },
  ];

  return (
    <div className="flash-manager">
      <div className="flash-controls">
        <div className="config-selector">
          <label htmlFor="build-config">Build Configuration:</label>
          <select
            id="build-config"
            value={config}
            onChange={(e) => setConfig(e.target.value)}
            disabled={isFlashing}
          >
            {configOptions.map(opt => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
          <div className="config-description">
            {configOptions.find(o => o.value === config)?.description}
          </div>
        </div>

        <div className="flash-actions">
          {isFlashing ? (
            <button onClick={handleCancel} className="cancel-button">
              Cancel Flash
            </button>
          ) : (
            <button
              onClick={handleFlash}
              disabled={!serialPort}
              className="flash-button"
            >
              Flash Firmware
            </button>
          )}
          <button onClick={handleClearLogs} disabled={isFlashing}>
            Clear Logs
          </button>
        </div>
      </div>

      {isFlashing && (
        <div className="flash-progress">
          <div className="progress-info">
            <span className="stage">{stage || 'Initializing...'}</span>
            <span className="percent">{progress}%</span>
          </div>
          <div className="progress-bar">
            <div
              className="progress-fill"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      )}

      {error && (
        <div className="flash-error">
          <strong>Error:</strong> {error}
        </div>
      )}

      <div className="flash-logs">
        <div className="logs-header">
          <h3>Flash Log</h3>
          <span className="log-count">{logs.length} lines</span>
        </div>
        <div className="logs-output">
          {logs.map((log, idx) => (
            <div key={idx} className="log-line">
              {log}
            </div>
          ))}
          {logs.length === 0 && (
            <div className="no-logs">
              No flash operations yet. Select a configuration and click "Flash Firmware" to begin.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
