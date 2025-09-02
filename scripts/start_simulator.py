#!/usr/bin/env python3
"""
Start the ESP32 Temperature Sensor web simulator on an available port.
Automatically finds a free port and opens the browser.
"""

import http.server
import os
from pathlib import Path
import socket
import socketserver
import sys
import threading
import time
import webbrowser
import subprocess


def find_free_port():
    """Find an available port to use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port


def start_server(port, directory):
    """Start the HTTP server in the specified directory."""
    os.chdir(directory)

    class QuietHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
        """Custom handler to reduce console output."""

        def log_message(self, format, *args):
            # Only log errors, not successful requests
            if args[1] != "200":
                super().log_message(format, *args)

        def end_headers(self):
            # Disable caching to ensure updated JS/JSON are always fetched
            try:
                self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
                self.send_header("Pragma", "no-cache")
                self.send_header("Expires", "0")
            except Exception:
                pass
            super().end_headers()

    with socketserver.TCPServer(("", port), QuietHTTPRequestHandler) as httpd:
        print(f"🚀 Simulator server running at http://localhost:{port}/")
        print(f"📁 Serving files from: {directory}")
        print(f"🌐 Open http://localhost:{port}/index.html in your browser")
        print("Press Ctrl+C to stop the server\n")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n\n✅ Server stopped")
            sys.exit(0)


def main():
    # Get the repository root
    script_path = Path(__file__).resolve()
    repo_root = script_path.parent.parent
    # Serve from web root so absolute paths like /icons/mdi/... resolve
    sim_directory = repo_root / "web"

    if not sim_directory.exists():
        print(f"❌ Error: Simulator directory not found at {sim_directory}")
        sys.exit(1)

    # Proactively (re)generate UI assets so edits to config/ui_spec.json are reflected
    try:
        gen_script = repo_root / "scripts" / "gen_ui.py"
        if gen_script.exists():
            print("🔧 Generating UI assets from config/ui_spec.json…")
            subprocess.run([sys.executable, str(gen_script)], check=False)
        else:
            print(f"⚠️ UI generator not found at {gen_script}")
    except Exception as e:
        print(f"⚠️ Failed to generate UI assets: {e}")

    # Start a lightweight watcher to auto-regenerate on changes to ui_spec.json
    def _watch_and_regen():
        spec_path = repo_root / "config" / "ui_spec.json"
        last_mtime = None
        while True:
            try:
                if spec_path.exists():
                    mtime = spec_path.stat().st_mtime
                    if last_mtime is None:
                        last_mtime = mtime
                    elif mtime != last_mtime:
                        last_mtime = mtime
                        print("🔁 Detected ui_spec.json change, regenerating…")
                        subprocess.run([sys.executable, str(gen_script)], check=False)
                time.sleep(1.0)
            except Exception:
                # Never crash the watcher; wait and retry
                time.sleep(1.0)

    try:
        watcher = threading.Thread(target=_watch_and_regen, daemon=True)
        watcher.start()
        print("👀 Watching config/ui_spec.json for changes…")
    except Exception as e:
        print(f"⚠️ Could not start watcher: {e}")

    # Find a free port
    port = find_free_port()

    # Optional: Auto-open browser after a short delay
    if "--no-browser" not in sys.argv:

        def open_browser():
            time.sleep(1)  # Give server time to start
            # Open simulator index under /sim
            webbrowser.open(f"http://localhost:{port}/sim/index.html")

        browser_thread = threading.Thread(target=open_browser)
        browser_thread.daemon = True
        browser_thread.start()
        print("🔍 Opening browser automatically (use --no-browser to disable)...")

    # Start the server
    try:
        start_server(port, sim_directory)
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
