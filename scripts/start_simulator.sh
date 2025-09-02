#!/bin/bash
# Start the ESP32 Temperature Sensor web simulator

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get script directory and repo root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
# Serve from web root so absolute /icons/... paths work
SIM_DIR="$REPO_ROOT/web"

# Check if simulator directory exists
if [ ! -d "$SIM_DIR" ]; then
    echo -e "${RED}❌ Error: Simulator directory not found at $SIM_DIR${NC}"
    exit 1
fi

# Find an available port
PORT=8000
MAX_PORT=9000

while [ $PORT -le $MAX_PORT ]; do
    # Check if port is available
    if ! lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
        break
    fi
    PORT=$((PORT + 1))
done

if [ $PORT -gt $MAX_PORT ]; then
    echo -e "${RED}❌ Error: No available ports found between 8000-9000${NC}"
    exit 1
fi

# Start the server
echo -e "${GREEN}🚀 Starting ESP32 Temperature Sensor Simulator${NC}"
echo -e "${BLUE}📁 Directory: $SIM_DIR${NC}"
echo -e "${BLUE}🌐 URL: http://localhost:$PORT/sim/index.html${NC}"
echo -e "Press Ctrl+C to stop the server\n"

# Change to simulator directory and start server
cd "$SIM_DIR" || exit 1

# Open browser if not disabled
if [ "$1" != "--no-browser" ]; then
    # Wait a moment then open browser in background
    (sleep 1 && open "http://localhost:$PORT/sim/index.html" 2>/dev/null || xdg-open "http://localhost:$PORT/sim/index.html" 2>/dev/null || echo "Please open http://localhost:$PORT/sim/index.html in your browser") &
fi

# Start Python HTTP server
python3 -m http.server $PORT