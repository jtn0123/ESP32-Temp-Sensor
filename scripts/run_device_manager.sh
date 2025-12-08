#!/bin/bash
# ESP32 Device Manager - Automated Startup Script
# 
# Automatically installs dependencies and starts all services.
#
# Usage:
#   ./scripts/run_device_manager.sh              # Start everything
#   ./scripts/run_device_manager.sh --dev        # Start with Vite dev server (hot reload)
#   ./scripts/run_device_manager.sh --no-broker  # Skip MQTT broker
#   ./scripts/run_device_manager.sh --help       # Show help

# Don't exit on error - we handle errors gracefully
set +e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BACKEND_PORT=8080
FRONTEND_PORT=5173
MQTT_PORT=18884  # Matches mosquitto_test.conf

# Parse arguments
DEV_MODE=false
NO_BROKER=false
HELP=false

for arg in "$@"; do
    case $arg in
        --dev)
            DEV_MODE=true
            ;;
        --no-broker)
            NO_BROKER=true
            ;;
        --help|-h)
            HELP=true
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
    echo "  Simulator:   http://localhost:$BACKEND_PORT/sim/index.html"
    echo "  Manager:     http://localhost:$BACKEND_PORT/manager/index.html"
    echo "  API Docs:    http://localhost:$BACKEND_PORT/docs"
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

# Track PIDs for cleanup
MOSQUITTO_PID=""
BACKEND_PID=""
FRONTEND_PID=""

# Function to cleanup on exit
cleanup() {
    # Only show shutdown message if we're actually shutting down (not already done)
    if [ -n "$MOSQUITTO_PID" ] || [ -n "$BACKEND_PID" ] || [ -n "$FRONTEND_PID" ]; then
        echo -e "\n${YELLOW}Shutting down services...${NC}"
    fi
    
    # Kill Mosquitto if we started it
    if [ -n "$MOSQUITTO_PID" ] && kill -0 "$MOSQUITTO_PID" 2>/dev/null; then
        echo -e "${YELLOW}  Stopping Mosquitto...${NC}"
        kill "$MOSQUITTO_PID" 2>/dev/null || true
        wait "$MOSQUITTO_PID" 2>/dev/null || true
    fi
    
    # Kill backend if we started it
    if [ -n "$BACKEND_PID" ] && kill -0 "$BACKEND_PID" 2>/dev/null; then
        echo -e "${YELLOW}  Stopping backend server...${NC}"
        kill "$BACKEND_PID" 2>/dev/null || true
        wait "$BACKEND_PID" 2>/dev/null || true
    fi
    
    # Kill frontend if we started it
    if [ -n "$FRONTEND_PID" ] && kill -0 "$FRONTEND_PID" 2>/dev/null; then
        echo -e "${YELLOW}  Stopping frontend dev server...${NC}"
        kill "$FRONTEND_PID" 2>/dev/null || true
        wait "$FRONTEND_PID" 2>/dev/null || true
    fi
    
    # Kill any remaining background jobs
    jobs -p 2>/dev/null | xargs kill 2>/dev/null || true
    
    if [ -n "$MOSQUITTO_PID" ] || [ -n "$BACKEND_PID" ] || [ -n "$FRONTEND_PID" ]; then
        echo -e "${GREEN}Cleanup complete${NC}"
    fi
}

trap cleanup EXIT INT TERM

# Change to project root
cd "$PROJECT_ROOT"

# ─────────────────────────────────────────────────────────────────
# Step 1: MQTT Broker
# ─────────────────────────────────────────────────────────────────
if [ "$NO_BROKER" = false ]; then
    echo -e "${BLUE}[1/3] Setting up MQTT broker...${NC}"
    
    if check_port $MQTT_PORT; then
        echo -e "${GREEN}  ✓ MQTT broker already running on port $MQTT_PORT${NC}"
    else
        # Auto-install Mosquitto if missing
        if ! command -v mosquitto &> /dev/null; then
            echo -e "${YELLOW}  Installing Mosquitto...${NC}"
            if [[ "$OSTYPE" == "darwin"* ]] && command -v brew &> /dev/null; then
                brew install mosquitto 2>/dev/null || true
            elif command -v apt-get &> /dev/null; then
                sudo apt-get update -qq && sudo apt-get install -y -qq mosquitto mosquitto-clients 2>/dev/null || true
            fi
        fi
        
        if command -v mosquitto &> /dev/null; then
            echo -e "${YELLOW}  Starting Mosquitto...${NC}"
            
            # Start Mosquitto as background job (not daemon) so we can track and kill it
            if [ -f "$PROJECT_ROOT/mosquitto_test.conf" ]; then
                mosquitto -c "$PROJECT_ROOT/mosquitto_test.conf" >/dev/null 2>&1 &
                MOSQUITTO_PID=$!
            else
                mosquitto -p $MQTT_PORT >/dev/null 2>&1 &
                MOSQUITTO_PID=$!
            fi
            
            sleep 1
            
            if check_port $MQTT_PORT; then
                echo -e "${GREEN}  ✓ Mosquitto started on port $MQTT_PORT (PID: $MOSQUITTO_PID)${NC}"
            else
                echo -e "${YELLOW}  ⚠ Mosquitto didn't start (continuing without MQTT)${NC}"
                MOSQUITTO_PID=""
                NO_BROKER=true
            fi
        else
            echo -e "${YELLOW}  ⚠ Mosquitto not available (continuing without MQTT)${NC}"
            NO_BROKER=true
        fi
    fi
else
    echo -e "${YELLOW}[1/3] Skipping MQTT broker (--no-broker)${NC}"
fi

# ─────────────────────────────────────────────────────────────────
# Step 2: Python environment
# ─────────────────────────────────────────────────────────────────
echo -e "${BLUE}[2/3] Setting up Python environment...${NC}"

# Create venv if needed
if [ ! -d "$PROJECT_ROOT/venv" ]; then
    echo -e "${YELLOW}  Creating virtual environment...${NC}"
    python3 -m venv "$PROJECT_ROOT/venv"
fi

# Activate venv
source "$PROJECT_ROOT/venv/bin/activate" 2>/dev/null || {
    source "$PROJECT_ROOT/venv/Scripts/activate" 2>/dev/null || {
        echo -e "${RED}  ❌ Failed to activate virtual environment${NC}"
        echo -e "${YELLOW}  Run ./setup.sh first${NC}"
        exit 1
    }
}

# Install dependencies if needed
NEED_INSTALL=false
python3 -c "import fastapi" 2>/dev/null || NEED_INSTALL=true
python3 -c "import uvicorn" 2>/dev/null || NEED_INSTALL=true
python3 -c "import serial" 2>/dev/null || NEED_INSTALL=true

if [ "$NEED_INSTALL" = true ]; then
    echo -e "${YELLOW}  Installing dependencies...${NC}"
    pip install --upgrade pip -q 2>/dev/null
    pip install -q -r "$PROJECT_ROOT/requirements.txt" 2>/dev/null || true
    pip install -q -r "$PROJECT_ROOT/requirements-manager.txt" 2>/dev/null || true
    
    # Ensure critical packages
    pip install -q fastapi uvicorn websockets pyserial paho-mqtt Pillow zeroconf python-multipart 2>/dev/null || true
fi

echo -e "${GREEN}  ✓ Python environment ready${NC}"

# ─────────────────────────────────────────────────────────────────
# Step 2.5: Build Manager UI if needed (and not in dev mode)
# ─────────────────────────────────────────────────────────────────
if [ "$DEV_MODE" = false ]; then
    MANAGER_DIR="$PROJECT_ROOT/web/manager"
    if [ ! -d "$MANAGER_DIR/dist" ] && [ -f "$MANAGER_DIR/package.json" ]; then
        if command -v npm &> /dev/null; then
            echo -e "${BLUE}[2.5/3] Building Manager UI...${NC}"
            cd "$MANAGER_DIR"
            if [ ! -d "node_modules" ]; then
                echo -e "${YELLOW}  Installing npm dependencies...${NC}"
                npm install --silent 2>/dev/null || npm install 2>/dev/null || true
            fi
            echo -e "${YELLOW}  Building production bundle...${NC}"
            npm run build 2>/dev/null || {
                echo -e "${YELLOW}  ⚠ Manager build failed (use --dev for hot reload)${NC}"
            }
            cd "$PROJECT_ROOT"
            if [ -d "$MANAGER_DIR/dist" ]; then
                echo -e "${GREEN}  ✓ Manager UI built${NC}"
            fi
        else
            echo -e "${YELLOW}  ⚠ npm not found - Manager UI won't be available${NC}"
            echo -e "${YELLOW}    Install Node.js or use: ./scripts/run_device_manager.sh --dev${NC}"
        fi
    elif [ -d "$MANAGER_DIR/dist" ]; then
        echo -e "${GREEN}  ✓ Manager UI already built${NC}"
    fi
fi

# ─────────────────────────────────────────────────────────────────
# Step 3: Start Backend
# ─────────────────────────────────────────────────────────────────
echo -e "${BLUE}[3/3] Starting backend server...${NC}"

# Kill any stale process on the port
if check_port $BACKEND_PORT; then
    echo -e "${YELLOW}  Port $BACKEND_PORT in use, killing existing process...${NC}"
    lsof -ti :$BACKEND_PORT | xargs kill -9 2>/dev/null || true
    sleep 1
    if check_port $BACKEND_PORT; then
        echo -e "${RED}  ❌ Could not free port $BACKEND_PORT${NC}"
        echo -e "${YELLOW}  Another application may be using it. Try a different port.${NC}"
        exit 1
    fi
    echo -e "${GREEN}  ✓ Port freed${NC}"
fi

if ! check_port $BACKEND_PORT; then
    # Build the command with appropriate flags
    BACKEND_CMD="python3 $SCRIPT_DIR/start_device_manager.py --port $BACKEND_PORT"
    if [ "$NO_BROKER" = true ]; then
        BACKEND_CMD="$BACKEND_CMD --no-broker"
    fi
    
    # Start backend and capture output
    $BACKEND_CMD 2>&1 &
    BACKEND_PID=$!
    
    # Wait for server to start (check multiple times)
    echo -e "${YELLOW}  Waiting for server to start...${NC}"
    for i in {1..10}; do
        sleep 1
        if check_port $BACKEND_PORT; then
            break
        fi
        # Check if process died
        if ! kill -0 $BACKEND_PID 2>/dev/null; then
            echo -e "${RED}  ❌ Backend process died${NC}"
            echo -e "${YELLOW}  Checking for errors...${NC}"
            # Try running directly to see error
            $BACKEND_CMD 2>&1 | head -30
            exit 1
        fi
    done
    
    if check_port $BACKEND_PORT; then
        echo -e "${GREEN}  ✓ Backend running on port $BACKEND_PORT${NC}"
    else
        echo -e "${RED}  ❌ Backend failed to start${NC}"
        echo -e "${YELLOW}  Trying to show error...${NC}"
        # Kill the hung process
        kill $BACKEND_PID 2>/dev/null || true
        # Run directly to see error
        timeout 5 $BACKEND_CMD 2>&1 || true
        exit 1
    fi
fi

# ─────────────────────────────────────────────────────────────────
# Step 4: Frontend (dev mode only)
# ─────────────────────────────────────────────────────────────────
if [ "$DEV_MODE" = true ]; then
    echo -e "${BLUE}[4/4] Starting frontend dev server...${NC}"
    
    cd "$PROJECT_ROOT/web/manager"
    
    # Check for npm
    if ! command -v npm &> /dev/null; then
        echo -e "${RED}  ❌ npm not found. Install Node.js first.${NC}"
    else
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
            echo -e "${YELLOW}  ⚠ Frontend may still be starting...${NC}"
        fi
    fi
    
    cd "$PROJECT_ROOT"
fi

# ─────────────────────────────────────────────────────────────────
# Print summary
# ─────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Device Manager is ready!${NC}"
echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "  ${BLUE}Simulator:${NC}    http://localhost:$BACKEND_PORT/sim/index.html"
echo -e "  ${BLUE}Manager:${NC}      http://localhost:$BACKEND_PORT/manager/index.html"
echo -e "  ${BLUE}API Docs:${NC}     http://localhost:$BACKEND_PORT/docs"
if [ "$NO_BROKER" = false ]; then
    echo -e "  ${BLUE}MQTT Broker:${NC}  localhost:$MQTT_PORT"
fi
if [ "$DEV_MODE" = true ]; then
    echo -e "  ${BLUE}Frontend Dev:${NC} http://localhost:$FRONTEND_PORT"
fi
echo ""
echo -e "  ${YELLOW}Press Ctrl+C to stop all services${NC}"
echo ""

# Keep script running and wait for interrupt
wait
