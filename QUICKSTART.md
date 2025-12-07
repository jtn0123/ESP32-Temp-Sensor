# Quick Start Guide - How to Run the Application

This guide will help you get the ESP32 Temperature Sensor application running quickly.

## Prerequisites

- Python 3.8+ installed
- macOS (you're on macOS, so you're good!)
- Optional: Mosquitto MQTT broker (for MQTT features)

## Setup Steps

### 1. Install Python Dependencies

First, set up a Python virtual environment and install dependencies:

```bash
# Navigate to project root
cd /Users/justin/Documents/Github/ESP32-Temp-Sensor

# Create virtual environment (if not already created)
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install all dependencies
pip install -r requirements.txt
pip install -r requirements-manager.txt
```

### 2. Configure Environment (Optional)

If you need MQTT credentials or WiFi settings:

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env with your credentials (WiFi, MQTT, etc.)
# Note: .env is git-ignored for security
```

### 3. Configure Device Settings (Optional)

If you want to customize device settings:

```bash
# Copy the sample config
cp config/device.sample.yaml config/device.yaml

# Edit config/device.yaml with your settings
# (WiFi SSID, MQTT host, room name, etc.)
```

## Running the Application

**You only need to run ONE script** - the Device Manager serves everything!

---

## Option 1: Device Manager (Recommended - Everything in One)

The Device Manager is the **unified way** to run everything. It includes:
- ✅ Web Simulator (test display UI)
- ✅ Device Manager UI (manage ESP32 devices)
- ✅ MQTT Broker (optional)
- ✅ Serial Console
- ✅ Flash Manager
- ✅ All APIs

### Quick Start:
```bash
# Activate virtual environment (if not already active)
source venv/bin/activate

# Start everything (MQTT broker + backend + web UIs)
./scripts/run_device_manager.sh

# OR start backend only (no MQTT broker)
./scripts/run_device_manager.sh --no-broker

# OR start with frontend dev server (hot reload for development)
./scripts/run_device_manager.sh --dev
```

### URLs:
- **Device Manager UI**: http://localhost:8080/manager/index.html
- **Web Simulator**: http://localhost:8080/sim/index.html
- **API Docs**: http://localhost:8080/docs
- **Backend API**: http://localhost:8080/api
- **MQTT Broker**: localhost:1883 (if enabled)

### Manual Start (Python):
```bash
source venv/bin/activate
python3 scripts/start_device_manager.py
# Then visit http://localhost:8080/sim/index.html or http://localhost:8080/manager/index.html
```

---

## Option 2: Standalone Simulator (Quick Testing Only)

If you **only** want to quickly test the display UI without the full backend:

```bash
source venv/bin/activate
python3 scripts/start_simulator.py
```

This is a lightweight option for rapid UI testing, but the Device Manager includes the simulator too.

---

## Option 3: Python Mock Display

Generate a static PNG preview of the display:

```bash
source venv/bin/activate
python scripts/mock_display.py
open out/display_mock.png  # macOS - opens the image
```

---

## Option 5: Flash Firmware to ESP32 (Hardware)

If you have an ESP32 device connected:

```bash
# Install PlatformIO if not already installed
# pip install platformio

# Flash with default settings (1-hour sleep)
python3 scripts/flash.py

# Flash with 2-hour sleep
python3 scripts/flash.py --mode 2h

# Flash with 3-minute sleep (for testing)
python3 scripts/flash.py --mode 3m

# Flash always-on (no sleep, for debugging)
python3 scripts/flash.py --mode always

# Headless build (no display)
python3 scripts/flash.py --headless --mode 1h

# Build only, don't upload
python3 scripts/flash.py --mode always --build-only
```

---

## Troubleshooting

### Port Already in Use
If you get a "port already in use" error:
```bash
# Find what's using the port
lsof -i :8080

# Kill the process or use a different port
python3 scripts/start_device_manager.py --port 8081
```

### Missing Dependencies
```bash
# Reinstall all dependencies
pip install -r requirements.txt -r requirements-manager.txt
```

### MQTT Broker Not Starting
```bash
# Install Mosquitto (macOS)
brew install mosquitto

# Or start without broker
./scripts/run_device_manager.sh --no-broker
```

### Virtual Environment Issues
```bash
# Remove and recreate venv
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt -r requirements-manager.txt
```

---

## What to Run First?

**Recommended**: Start with the **Device Manager** (Option 1)
- ✅ Everything in one place (simulator + manager + APIs)
- ✅ No hardware needed to start
- ✅ Complete backend system
- ✅ MQTT integration
- ✅ Device management features

**For quick UI testing only**: Use **Standalone Simulator** (Option 2)
- Lightweight, fast startup
- Good for rapid UI iteration
- Note: Device Manager includes this too!

**For hardware**: Use **Flash Firmware** (Option 5)
- Requires ESP32 device
- Uploads code to device
- For production deployment

---

## Next Steps

1. **Test the UI**: Run the web simulator and explore the interface
2. **Configure Settings**: Edit `config/device.yaml` for your environment
3. **Connect Hardware**: Flash firmware to your ESP32 device
4. **Monitor**: Use `scripts/monitor.py` to watch device output

For more details, see the main [README.md](README.md).

