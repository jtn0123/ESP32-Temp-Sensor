import { useState, useEffect } from 'react';
import { deviceApi } from '../api/deviceApi';
import { DeviceModeSelector } from './DeviceModeSelector';

export function FlashManager({ messages, serialPort, targetDevice }) {
  const [config, setConfig] = useState('dev');
  const [isFlashing, setIsFlashing] = useState(false);
  const [progress, setProgress] = useState(0);
  const [stage, setStage] = useState('');
  const [logs, setLogs] = useState([]);
  const [error, setError] = useState(null);

  // Flash Queue / Hunt Mode state
  const [queueStatus, setQueueStatus] = useState(null);
  const [isQueued, setIsQueued] = useState(false);
  const [queueTimeRemaining, setQueueTimeRemaining] = useState(null);
  const [timeoutMinutes, setTimeoutMinutes] = useState(15);

  // Listen for flash progress and queue messages
  useEffect(() => {
    const flashMessages = messages.filter(
      m => m.type === 'flash_progress' || m.type === 'flash_complete' || m.type === 'flash_queue_status'
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
        setIsQueued(false);
        setQueueStatus(null);
        if (!latest.success) {
          setError(latest.message || 'Flash failed');
        } else {
          setLogs(prev => [...prev, latest.message || 'Flash complete!']);
        }
      } else if (latest.type === 'flash_queue_status') {
        handleQueueStatusUpdate(latest);
      }
    }
  }, [messages]);

  // Handle queue status updates from WebSocket
  const handleQueueStatusUpdate = (msg) => {
    setQueueStatus(msg.status);
    
    if (msg.message) {
      setLogs(prev => [...prev, `[Queue] ${msg.message}`]);
    }

    switch (msg.status) {
      case 'building':
        setIsQueued(true);
        setIsFlashing(false);
        setStage('Building firmware...');
        break;
      case 'hunting':
        setIsQueued(true);
        setIsFlashing(false);
        setStage('Hunting for device...');
        if (msg.queue?.time_remaining !== undefined) {
          setQueueTimeRemaining(Math.round(msg.queue.time_remaining));
        }
        break;
      case 'device_detected':
        setIsQueued(false);
        setIsFlashing(true);
        setStage('Device found! Flashing...');
        break;
      case 'expired':
      case 'cancelled':
      case 'failed':
        setIsQueued(false);
        setIsFlashing(false);
        setQueueStatus(null);
        setQueueTimeRemaining(null);
        if (msg.status === 'expired') {
          setError('Flash queue timed out - no device found');
        } else if (msg.status === 'failed') {
          setError(msg.message || 'Queue operation failed');
        }
        break;
      default:
        break;
    }
  };

  // Countdown timer for queue
  useEffect(() => {
    if (queueStatus === 'hunting' && queueTimeRemaining > 0) {
      const timer = setInterval(() => {
        setQueueTimeRemaining(prev => Math.max(0, prev - 1));
      }, 1000);
      return () => clearInterval(timer);
    }
  }, [queueStatus, queueTimeRemaining]);

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

  const handleQueueFlash = async () => {
    setIsQueued(true);
    setProgress(0);
    setStage('Queuing flash...');
    setLogs([]);
    setError(null);

    try {
      await deviceApi.queueFlash(config, null, null, timeoutMinutes);
    } catch (err) {
      console.error('Error queuing flash:', err);
      setError(err.message);
      setIsQueued(false);
    }
  };

  const handleCancel = async () => {
    try {
      if (isQueued) {
        await deviceApi.cancelQueuedFlash();
        setIsQueued(false);
        setQueueStatus(null);
        setQueueTimeRemaining(null);
        setLogs(prev => [...prev, 'Flash queue cancelled by user']);
      } else {
        await deviceApi.cancelFlash();
        setIsFlashing(false);
        setLogs(prev => [...prev, 'Flash cancelled by user']);
      }
    } catch (err) {
      console.error('Error cancelling:', err);
    }
  };

  const handleClearLogs = () => {
    setLogs([]);
    setError(null);
  };

  const formatTime = (seconds) => {
    if (seconds === null || seconds === undefined) return '';
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const configOptions = [
    { value: 'dev', label: 'Development (No Sleep)', description: 'DEV_NO_SLEEP=1, BOOT_DEBUG=1' },
    { value: 'prod', label: 'Production', description: 'Normal operation with sleep' },
    { value: 'battery_test', label: 'Battery Test', description: 'Verbose battery logging' },
  ];

  const timeoutOptions = [
    { value: 5, label: '5 minutes' },
    { value: 15, label: '15 minutes' },
    { value: 30, label: '30 minutes' },
    { value: 60, label: '1 hour' },
    { value: null, label: 'No timeout' },
  ];

  const isBusy = isFlashing || isQueued;

  return (
    <div className="flash-manager">
      {/* Device Mode & Interval Configuration */}
      <div className="flash-section">
        <h3>⚙️ Device Configuration</h3>
        <DeviceModeSelector deviceId={targetDevice} />
      </div>

      <hr className="section-divider" />

      {/* Flash Controls */}
      <div className="flash-section">
        <h3>⚡ Build & Flash</h3>
        <div className="flash-controls">
          <div className="config-selector">
            <label htmlFor="build-config">Build Configuration:</label>
            <select
              id="build-config"
              value={config}
              onChange={(e) => setConfig(e.target.value)}
              disabled={isBusy}
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

          {/* Flash Queue timeout selector */}
          {!serialPort && !isBusy && (
            <div className="config-selector">
              <label htmlFor="queue-timeout">Hunt Timeout:</label>
              <select
                id="queue-timeout"
                value={timeoutMinutes ?? 'null'}
                onChange={(e) => setTimeoutMinutes(e.target.value === 'null' ? null : parseInt(e.target.value))}
                disabled={isBusy}
              >
                {timeoutOptions.map(opt => (
                  <option key={opt.value ?? 'null'} value={opt.value ?? 'null'}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>
          )}

          <div className="flash-actions">
            {isBusy ? (
              <button onClick={handleCancel} className="cancel-button">
                {isQueued ? 'Cancel Queue' : 'Cancel Flash'}
              </button>
            ) : serialPort ? (
              <button
                onClick={handleFlash}
                className="flash-button"
              >
                ⚡ Flash Now
              </button>
            ) : (
              <button
                onClick={handleQueueFlash}
                className="queue-button"
                title="Pre-build firmware and flash when device connects"
              >
                🎯 Queue Flash (Hunt Mode)
              </button>
            )}
            <button onClick={handleClearLogs} disabled={isBusy}>
              Clear Logs
            </button>
          </div>
        </div>

        {/* No device connected hint */}
        {!serialPort && !isBusy && (
          <div className="queue-hint">
            <strong>No device connected.</strong> Use "Queue Flash" to pre-build firmware 
            and automatically flash when your device wakes up or connects via USB.
          </div>
        )}
      </div>

      {/* Queue Status / Hunting indicator */}
      {isQueued && (
        <div className="queue-status">
          <div className="queue-status-header">
            {queueStatus === 'building' && (
              <>
                <span className="status-icon building">🔨</span>
                <span>Building firmware...</span>
              </>
            )}
            {queueStatus === 'hunting' && (
              <>
                <span className="status-icon hunting">🎯</span>
                <span>Hunting for device...</span>
                {queueTimeRemaining !== null && queueTimeRemaining > 0 && (
                  <span className="time-remaining">
                    ({formatTime(queueTimeRemaining)} remaining)
                  </span>
                )}
              </>
            )}
          </div>
          <div className="queue-status-detail">
            {queueStatus === 'hunting' && (
              <p>
                Firmware is ready. Waiting for ESP32 to connect via USB or appear on network.
                <br />
                <small>The device will be flashed automatically as soon as it's detected.</small>
              </p>
            )}
          </div>
        </div>
      )}

      {/* Flash Progress (for active flashing) */}
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
              No flash operations yet. Select a configuration and click "Flash Firmware" or "Queue Flash" to begin.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
