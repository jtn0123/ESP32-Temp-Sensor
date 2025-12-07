#!/bin/bash
# ESP32 Device Manager - Combined Startup Script
# 
# This script starts all required services:
# 1. Mosquitto MQTT broker (if not already running)
# 2. Python FastAPI backend
# 3. Vite frontend dev server (optional)
#
# Usage:
#   ./scripts/run_device_manager.sh              # Start backend only (serves static files)
#   ./scripts/run_device_manager.sh --dev        # Start with Vite dev server (hot reload)
#   ./scripts/run_device_manager.sh --no-broker  # Skip starting Mosquitto
#   ./scripts/run_device_manager.sh --help       # Show help

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BACKEND_PORT=8080
FRONTEND_PORT=5173
MQTT_PORT=1883

# Parse arguments
DEV_MODE=false
NO_BROKER=false
HELP=false

for arg in "$@"; do
    case $arg in
        --dev)
            DEV_MODE=true
            shift
            ;;
        --no-broker)
            NO_BROKER=true
            shift
            ;;
        --help|-h)
            HELP=true
            shift
            ;;
    esac
done

# Show help
if [ "$HELP" = true ]; then
    echo "ESP32 Device Manager - Startup Script"
    echo ""
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  --dev        Start Vite dev server for frontend hot-reload"
    echo "  --no-broker  Don't start Mosquitto MQTT broker"
    echo "  --help, -h   Show this help message"
    echo ""
    echo "URLs:"
    echo "  Backend API: http://localhost:$BACKEND_PORT"
    echo "  Frontend:    http://localhost:$FRONTEND_PORT (with --dev)"
    echo "  MQTT Broker: localhost:$MQTT_PORT"
    exit 0
fi

# Print banner
echo -e "${BLUE}"
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║           ESP32 Device Manager                            ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Function to check if a port is in use
check_port() {
    lsof -i :$1 >/dev/null 2>&1
}

# Function to cleanup on exit
cleanup() {
    echo -e "\n${YELLOW}Shutting down...${NC}"
    
    # Kill background jobs
    jobs -p | xargs -r kill 2>/dev/null || true
    
    echo -e "${GREEN}Cleanup complete${NC}"
}

trap cleanup EXIT

# Change to project root
cd "$PROJECT_ROOT"

# 1. Check/Start Mosquitto MQTT Broker
if [ "$NO_BROKER" = false ]; then
    echo -e "${BLUE}[1/3] Checking MQTT broker...${NC}"
    
    if check_port $MQTT_PORT; then
        echo -e "${GREEN}  ✓ MQTT broker already running on port $MQTT_PORT${NC}"
    else
        if command -v mosquitto &> /dev/null; then
            echo -e "${YELLOW}  Starting Mosquitto...${NC}"
            
            # Use project config if available
            if [ -f "$PROJECT_ROOT/mosquitto_test.conf" ]; then
                mosquitto -c "$PROJECT_ROOT/mosquitto_test.conf" -d
            else
                mosquitto -p $MQTT_PORT -d
            fi
            
            sleep 1
            
            if check_port $MQTT_PORT; then
                echo -e "${GREEN}  ✓ Mosquitto started on port $MQTT_PORT${NC}"
            else
                echo -e "${RED}  ✗ Failed to start Mosquitto${NC}"
                echo -e "${YELLOW}  Install with: brew install mosquitto${NC}"
            fi
        else
            echo -e "${YELLOW}  ⚠ Mosquitto not installed${NC}"
            echo -e "${YELLOW}  Install with: brew install mosquitto${NC}"
            echo -e "${YELLOW}  MQTT features will be unavailable${NC}"
        fi
    fi
else
    echo -e "${YELLOW}[1/3] Skipping MQTT broker (--no-broker)${NC}"
fi

# 2. Install Python dependencies if needed
echo -e "${BLUE}[2/3] Checking Python dependencies...${NC}"

if [ ! -d "$PROJECT_ROOT/venv" ]; then
    echo -e "${YELLOW}  Creating virtual environment...${NC}"
    python3 -m venv venv
fi

# Activate venv
source "$PROJECT_ROOT/venv/bin/activate" 2>/dev/null || source "$PROJECT_ROOT/venv/Scripts/activate" 2>/dev/null || true

# Check if FastAPI is installed
if ! python3 -c "import fastapi" 2>/dev/null; then
    echo -e "${YELLOW}  Installing dependencies...${NC}"
    pip install -q fastapi uvicorn websockets pyserial paho-mqtt pillow
fi
echo -e "${GREEN}  ✓ Python dependencies ready${NC}"

# 3. Start Backend
echo -e "${BLUE}[3/3] Starting backend server...${NC}"

if check_port $BACKEND_PORT; then
    echo -e "${YELLOW}  ⚠ Port $BACKEND_PORT already in use${NC}"
    echo -e "${YELLOW}  Trying to use existing server...${NC}"
else
    # Start backend in background
    python3 "$SCRIPT_DIR/start_device_manager.py" --port $BACKEND_PORT &
    BACKEND_PID=$!
    
    # Wait for server to start
    sleep 2
    
    if check_port $BACKEND_PORT; then
        echo -e "${GREEN}  ✓ Backend running on http://localhost:$BACKEND_PORT${NC}"
    else
        echo -e "${RED}  ✗ Failed to start backend${NC}"
        exit 1
    fi
fi

# 4. Start Frontend (dev mode only)
if [ "$DEV_MODE" = true ]; then
    echo -e "${BLUE}[4/4] Starting frontend dev server...${NC}"
    
    cd "$PROJECT_ROOT/web/manager"
    
    # Install npm dependencies if needed
    if [ ! -d "node_modules" ]; then
        echo -e "${YELLOW}  Installing npm dependencies...${NC}"
        npm install
    fi
    
    # Start Vite dev server
    npm run dev &
    FRONTEND_PID=$!
    
    sleep 3
    
    if check_port $FRONTEND_PORT; then
        echo -e "${GREEN}  ✓ Frontend running on http://localhost:$FRONTEND_PORT${NC}"
    else
        echo -e "${RED}  ✗ Failed to start frontend${NC}"
    fi
    
    cd "$PROJECT_ROOT"
fi

# Print summary
echo ""
echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Device Manager is ready!${NC}"
echo ""
echo -e "  ${BLUE}Backend API:${NC}  http://localhost:$BACKEND_PORT"
if [ "$DEV_MODE" = true ]; then
    echo -e "  ${BLUE}Frontend:${NC}     http://localhost:$FRONTEND_PORT"
fi
echo -e "  ${BLUE}MQTT Broker:${NC}  localhost:$MQTT_PORT"
echo ""
echo -e "  ${YELLOW}Press Ctrl+C to stop all services${NC}"
echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
echo ""

# Keep script running and wait for interrupt
wait

