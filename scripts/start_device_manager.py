#!/usr/bin/env python3
"""
ESP32 Device Manager - Start the backend server

Usage: python scripts/start_device_manager.py [--port 8080] [--no-broker]
"""
import argparse
import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    parser = argparse.ArgumentParser(description='ESP32 Device Manager')
    parser.add_argument('--port', type=int, default=8080, help='Server port (default: 8080)')
    parser.add_argument('--host', type=str, default='0.0.0.0', help='Server host (default: 0.0.0.0)')
    parser.add_argument('--no-broker', action='store_true', help='Disable embedded MQTT broker')
    parser.add_argument('--serial-port', type=str, default=None, help='Serial port (auto-detect if not specified)')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    args = parser.parse_args()

    # Configure logging level
    import logging
    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    # Start FastAPI server
    import uvicorn
    from scripts.device_manager.config import ManagerConfig
    from scripts.device_manager import server

    # Update config from args
    server.config = ManagerConfig.from_args(args)

    print(f"Starting ESP32 Device Manager on {args.host}:{args.port}")
    print(f"MQTT Broker: {'Disabled' if args.no_broker else 'Enabled'}")
    print(f"Web UI will be available at: http://localhost:{args.port}")

    uvicorn.run(
        "scripts.device_manager.server:app",
        host=args.host,
        port=args.port,
        reload=False,
        log_level="debug" if args.debug else "info"
    )


if __name__ == "__main__":
    main()
