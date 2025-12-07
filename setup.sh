#!/bin/bash
# ESP32 Temperature Sensor - Automated Setup Script
# Installs all dependencies and prepares the environment

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}"
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║     ESP32 Temperature Sensor - Automated Setup            ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Get project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"
cd "$PROJECT_ROOT"

# Track what we installed
INSTALLED_ITEMS=()

# ─────────────────────────────────────────────────────────────────
# Step 1: Check for Homebrew (macOS)
# ─────────────────────────────────────────────────────────────────
echo -e "${BLUE}[1/5] Checking Homebrew...${NC}"
if [[ "$OSTYPE" == "darwin"* ]]; then
    if ! command -v brew &> /dev/null; then
        echo -e "${YELLOW}  Installing Homebrew...${NC}"
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        INSTALLED_ITEMS+=("Homebrew")
    fi
    echo -e "${GREEN}  ✓ Homebrew available${NC}"
else
    echo -e "${YELLOW}  ⚠ Not macOS, skipping Homebrew${NC}"
fi

# ─────────────────────────────────────────────────────────────────
# Step 2: Install Mosquitto MQTT broker
# ─────────────────────────────────────────────────────────────────
echo -e "${BLUE}[2/5] Checking Mosquitto MQTT broker...${NC}"
if ! command -v mosquitto &> /dev/null; then
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo -e "${YELLOW}  Installing Mosquitto via Homebrew...${NC}"
        brew install mosquitto
        INSTALLED_ITEMS+=("Mosquitto")
    elif command -v apt-get &> /dev/null; then
        echo -e "${YELLOW}  Installing Mosquitto via apt...${NC}"
        sudo apt-get update && sudo apt-get install -y mosquitto mosquitto-clients
        INSTALLED_ITEMS+=("Mosquitto")
    else
        echo -e "${YELLOW}  ⚠ Please install Mosquitto manually${NC}"
    fi
fi
if command -v mosquitto &> /dev/null; then
    echo -e "${GREEN}  ✓ Mosquitto installed${NC}"
else
    echo -e "${YELLOW}  ⚠ Mosquitto not available (MQTT features will be limited)${NC}"
fi

# ─────────────────────────────────────────────────────────────────
# Step 3: Check Python
# ─────────────────────────────────────────────────────────────────
echo -e "${BLUE}[3/5] Checking Python...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}  ❌ Python 3 is not installed${NC}"
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo -e "${YELLOW}  Installing Python via Homebrew...${NC}"
        brew install python3
        INSTALLED_ITEMS+=("Python")
    else
        echo -e "${RED}  Please install Python 3 manually${NC}"
        exit 1
    fi
fi
PYTHON_VERSION=$(python3 --version 2>&1)
echo -e "${GREEN}  ✓ $PYTHON_VERSION${NC}"

# ─────────────────────────────────────────────────────────────────
# Step 4: Create virtual environment and install dependencies
# ─────────────────────────────────────────────────────────────────
echo -e "${BLUE}[4/5] Setting up Python environment...${NC}"

# Create venv if needed
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}  Creating virtual environment...${NC}"
    python3 -m venv venv
    INSTALLED_ITEMS+=("Python venv")
fi

# Activate venv
echo -e "${YELLOW}  Activating virtual environment...${NC}"
source venv/bin/activate

# Upgrade pip
echo -e "${YELLOW}  Upgrading pip...${NC}"
pip install --upgrade pip -q

# Install ALL dependencies
echo -e "${YELLOW}  Installing Python dependencies (this may take a minute)...${NC}"
pip install -q -r requirements.txt 2>/dev/null || true
pip install -q -r requirements-manager.txt 2>/dev/null || true

# Verify critical packages
MISSING_PACKAGES=()
python3 -c "import fastapi" 2>/dev/null || MISSING_PACKAGES+=("fastapi")
python3 -c "import uvicorn" 2>/dev/null || MISSING_PACKAGES+=("uvicorn")
python3 -c "import serial" 2>/dev/null || MISSING_PACKAGES+=("pyserial")
python3 -c "import paho.mqtt" 2>/dev/null || MISSING_PACKAGES+=("paho-mqtt")
python3 -c "import websockets" 2>/dev/null || MISSING_PACKAGES+=("websockets")
python3 -c "import PIL" 2>/dev/null || MISSING_PACKAGES+=("Pillow")

if [ ${#MISSING_PACKAGES[@]} -gt 0 ]; then
    echo -e "${YELLOW}  Installing missing packages: ${MISSING_PACKAGES[*]}${NC}"
    pip install -q "${MISSING_PACKAGES[@]}"
fi

echo -e "${GREEN}  ✓ Python dependencies installed${NC}"

# ─────────────────────────────────────────────────────────────────
# Step 5: Setup configuration files
# ─────────────────────────────────────────────────────────────────
echo -e "${BLUE}[5/5] Checking configuration...${NC}"

# Create .env if it doesn't exist
if [ ! -f ".env" ] && [ -f ".env.example" ]; then
    echo -e "${YELLOW}  Creating .env from example...${NC}"
    cp .env.example .env
    echo -e "${YELLOW}  ⚠ Edit .env with your credentials${NC}"
fi

# Create device.yaml if it doesn't exist
if [ ! -f "config/device.yaml" ] && [ -f "config/device.sample.yaml" ]; then
    echo -e "${YELLOW}  Creating config/device.yaml from sample...${NC}"
    cp config/device.sample.yaml config/device.yaml
    echo -e "${YELLOW}  ⚠ Edit config/device.yaml with your settings${NC}"
fi

echo -e "${GREEN}  ✓ Configuration ready${NC}"

# ─────────────────────────────────────────────────────────────────
# Done!
# ─────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                    Setup Complete!                        ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════════════╝${NC}"
echo ""

if [ ${#INSTALLED_ITEMS[@]} -gt 0 ]; then
    echo -e "${BLUE}Installed:${NC} ${INSTALLED_ITEMS[*]}"
    echo ""
fi

echo -e "${GREEN}To start the Device Manager, run:${NC}"
echo ""
echo -e "   ${BLUE}./scripts/run_device_manager.sh${NC}"
echo ""
echo -e "${GREEN}Then visit:${NC}"
echo -e "   • Simulator:  ${BLUE}http://localhost:8080/sim/index.html${NC}"
echo -e "   • Manager:    ${BLUE}http://localhost:8080/manager/index.html${NC}"
echo -e "   • API Docs:   ${BLUE}http://localhost:8080/docs${NC}"
echo ""
