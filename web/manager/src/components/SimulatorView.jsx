import { useRef, useState } from 'react';

// The device manager backend mounts web/sim at /sim (see
// scripts/device_manager/server.py), so the simulator is already a served page.
// This view frames it rather than reimplementing the rendering pipeline, which
// keeps a single source of truth for the display output.
const SIM_URL = '/sim/index.html';

export function SimulatorView() {
  const frameRef = useRef(null);
  const [reloadKey, setReloadKey] = useState(0);

  const handleReload = () => {
    // Remounting the iframe is more reliable than touching contentWindow —
    // same-origin is not guaranteed when the manager is served from a dev
    // server while /sim is proxied.
    setReloadKey((key) => key + 1);
  };

  return (
    <div className="view-container">
      <div className="view-header">
        <h2>Simulator</h2>
        <p className="view-description">
          Live preview of the e-paper display rendered by the web simulator
        </p>
      </div>

      <div className="sim-frame-controls">
        <button onClick={handleReload} className="refresh-button">
          🔄 Reload
        </button>
        <a
          href={SIM_URL}
          target="_blank"
          rel="noreferrer"
          className="sim-frame-link"
        >
          Open in new tab ↗
        </a>
      </div>

      <div className="sim-frame-wrapper">
        <iframe
          key={reloadKey}
          ref={frameRef}
          src={SIM_URL}
          title="ESP32 display simulator"
          className="sim-frame"
        />
      </div>
    </div>
  );
}
