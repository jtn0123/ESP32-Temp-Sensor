#!/bin/bash
# Launch web simulator with MQTT support
# Starts HTTP server and optionally mosquitto broker

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default values
HTTP_PORT=8000
MQTT_PORT=18884
WS_PORT=9001
USE_LOCAL_BROKER=false

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --broker)
      USE_LOCAL_BROKER=true
      shift
      ;;
    --http-port)
      HTTP_PORT="$2"
      shift 2
      ;;
    --mqtt-port)
      MQTT_PORT="$2"
      shift 2
      ;;
    --ws-port)
      WS_PORT="$2"
      shift 2
      ;;
    -h|--help)
      echo "Usage: $0 [options]"
      echo "Options:"
      echo "  --broker          Start local mosquitto broker"
      echo "  --http-port PORT  HTTP server port (default: 8000)"
      echo "  --mqtt-port PORT  MQTT broker port (default: 18884)"
      echo "  --ws-port PORT    WebSocket port (default: 9001)"
      echo "  -h, --help        Show this help message"
      exit 0
      ;;
    *)
      echo -e "${RED}Unknown option: $1${NC}"
      exit 1
      ;;
  esac
done

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
WEB_SIM_DIR="$PROJECT_ROOT/web/sim"

echo -e "${GREEN}ESP32 Temperature Sensor - Web Simulator with MQTT${NC}"
echo "=================================================="

# Check if mosquitto is running or should be started
MOSQUITTO_PID=""
if [ "$USE_LOCAL_BROKER" = true ]; then
  echo -e "${YELLOW}Starting local mosquitto broker...${NC}"
  
  # Check if mosquitto is installed
  if ! command -v mosquitto &> /dev/null; then
    echo -e "${RED}mosquitto is not installed. Install with: brew install mosquitto${NC}"
    exit 1
  fi
  
  # Start mosquitto with test config
  mosquitto -c "$PROJECT_ROOT/mosquitto_test.conf" -v &
  MOSQUITTO_PID=$!
  echo -e "${GREEN}Mosquitto started (PID: $MOSQUITTO_PID)${NC}"
  echo "  TCP: localhost:$MQTT_PORT"
  echo "  WebSocket: localhost:$WS_PORT"
  sleep 1
else
  echo -e "${YELLOW}Using external MQTT broker${NC}"
  echo "  Configure broker settings in the web UI"
fi

# Function to cleanup on exit
cleanup() {
  echo -e "\n${YELLOW}Shutting down...${NC}"
  
  if [ -n "$MOSQUITTO_PID" ]; then
    echo "Stopping mosquitto..."
    kill $MOSQUITTO_PID 2>/dev/null || true
  fi
  
  # Kill any Python HTTP server we started
  kill $(jobs -p) 2>/dev/null || true
  
  echo -e "${GREEN}Cleanup complete${NC}"
}

# Set trap for cleanup
trap cleanup EXIT INT TERM

# Check if Python is available
if ! command -v python3 &> /dev/null; then
  echo -e "${RED}Python 3 is not installed${NC}"
  exit 1
fi

# Start HTTP server
echo -e "${YELLOW}Starting HTTP server...${NC}"
cd "$WEB_SIM_DIR"

# Try to use Python's http.server
echo -e "${GREEN}HTTP server starting on http://localhost:$HTTP_PORT${NC}"
echo "  Serving: $WEB_SIM_DIR"
echo ""
echo -e "${GREEN}Web Simulator URLs:${NC}"
echo "  Main: http://localhost:$HTTP_PORT/index.html"
echo "  Debug: http://localhost:$HTTP_PORT/debug.html"
echo ""

if [ "$USE_LOCAL_BROKER" = true ]; then
  echo -e "${GREEN}MQTT Settings for Web UI:${NC}"
  echo "  Broker: 127.0.0.1"
  echo "  Port: $WS_PORT"
  echo "  No authentication required"
else
  echo -e "${YELLOW}Configure MQTT broker in the web UI${NC}"
fi

echo ""
echo -e "${GREEN}Press Ctrl+C to stop all services${NC}"
echo "=================================================="

# Start Python HTTP server
python3 -m http.server $HTTP_PORT