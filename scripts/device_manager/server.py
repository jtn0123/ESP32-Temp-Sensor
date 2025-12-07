"""FastAPI server for ESP32 Device Manager"""
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import asyncio
import os

from .websocket_hub import WebSocketHub
from .serial_manager import SerialManager
from .flash_manager import FlashManager
from .mqtt_broker import SimpleMQTTBroker
from .mqtt_simulator import MqttSimulator
from .screenshot_handler import ScreenshotHandler
from .mdns_discovery import get_discovery, MDNSDiscovery
from .device_tracker import get_tracker, DeviceTracker, DeviceMode, SLEEP_PRESETS
from .config import ManagerConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="ESP32 Device Manager", version="0.1.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global instances
config = ManagerConfig()
hub = WebSocketHub()
serial_manager = SerialManager(websocket_hub=hub)
flash_manager = FlashManager(websocket_hub=hub, config=config)
mqtt_broker = SimpleMQTTBroker(websocket_hub=hub, port=config.mqtt_broker_port)
mqtt_simulator = MqttSimulator(broker=mqtt_broker, config=config)
screenshot_handler = ScreenshotHandler(mqtt_broker=mqtt_broker, websocket_hub=hub, config=config)

# mDNS discovery for finding devices on the network
mdns_discovery = get_discovery()

# Device tracker for activity and wake predictions
device_tracker = get_tracker()

# Currently targeted device (only ONE at a time for safety)
_targeted_device_id: str | None = None


# Pydantic models for request/response
class SerialConnectRequest(BaseModel):
    port: str
    baud: int = 115200


class SerialSendRequest(BaseModel):
    data: str


class DeviceCommandRequest(BaseModel):
    command: str
    params: Optional[Dict[str, Any]] = None


class SleepIntervalRequest(BaseModel):
    interval_sec: int


class FlashRequest(BaseModel):
    port: str
    config: str = "dev"
    firmware_path: Optional[str] = None


class MqttPublishRequest(BaseModel):
    topic: str
    payload: str
    retain: bool = False
    qos: int = 0


class MqttSubscribeRequest(BaseModel):
    topic: str
    qos: int = 0


# API Routes

@app.get("/")
async def root():
    """Root endpoint"""
    return {"name": "ESP32 Device Manager", "version": "0.1.0"}


@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "ok",
        "serial_connected": serial_manager.connected
    }


# Serial endpoints
@app.get("/api/ports")
async def list_ports():
    """List available serial ports"""
    try:
        ports = serial_manager.list_ports()
        return {"ports": ports}
    except Exception as e:
        logger.error(f"Error listing ports: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/serial/connect")
async def connect_serial(request: SerialConnectRequest):
    """Connect to a serial port"""
    try:
        success = serial_manager.connect(request.port, request.baud)
        if success:
            return {"status": "connected", "port": request.port}
        else:
            raise HTTPException(status_code=500, detail="Failed to connect")
    except Exception as e:
        logger.error(f"Error connecting to serial: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/serial/disconnect")
async def disconnect_serial():
    """Disconnect from serial port"""
    try:
        serial_manager.disconnect()
        return {"status": "disconnected"}
    except Exception as e:
        logger.error(f"Error disconnecting: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/serial/send")
async def send_serial(request: SerialSendRequest):
    """Send data to serial port"""
    try:
        success = serial_manager.send(request.data)
        if success:
            return {"status": "sent"}
        else:
            raise HTTPException(status_code=500, detail="Failed to send")
    except Exception as e:
        logger.error(f"Error sending serial data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/serial/status")
async def get_serial_status():
    """Get serial connection status"""
    try:
        status = serial_manager.get_status()
        return status
    except Exception as e:
        logger.error(f"Error getting serial status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Flash endpoints
@app.post("/api/flash/start")
async def start_flash(request: FlashRequest):
    """Start flash process"""
    try:
        # Run flash in background task
        asyncio.create_task(
            flash_manager.flash(
                port=request.port,
                firmware_path=request.firmware_path,
                build_config=request.config
            )
        )
        return {"status": "started"}
    except Exception as e:
        logger.error(f"Error starting flash: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/flash/status")
async def get_flash_status():
    """Get flash progress"""
    try:
        status = flash_manager.get_status()
        return status
    except Exception as e:
        logger.error(f"Error getting flash status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/flash/cancel")
async def cancel_flash():
    """Cancel flash in progress"""
    try:
        await flash_manager.cancel()
        return {"status": "cancelled"}
    except Exception as e:
        logger.error(f"Error cancelling flash: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# MQTT endpoints
@app.get("/api/mqtt/status")
async def get_mqtt_status():
    """Get MQTT broker status"""
    try:
        broker_status = mqtt_broker.get_status()
        simulator_status = mqtt_simulator.get_status()
        return {
            'broker': broker_status,
            'simulator': simulator_status
        }
    except Exception as e:
        logger.error(f"Error getting MQTT status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/mqtt/publish")
async def publish_mqtt(request: MqttPublishRequest):
    """Publish MQTT message"""
    try:
        success = mqtt_broker.publish(
            topic=request.topic,
            payload=request.payload,
            retain=request.retain,
            qos=request.qos
        )
        if success:
            return {"status": "published"}
        else:
            raise HTTPException(status_code=500, detail="Failed to publish")
    except Exception as e:
        logger.error(f"Error publishing MQTT message: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/mqtt/subscriptions")
async def get_mqtt_subscriptions():
    """List active MQTT subscriptions"""
    try:
        subscriptions = mqtt_broker.get_subscriptions()
        return {"subscriptions": subscriptions}
    except Exception as e:
        logger.error(f"Error getting subscriptions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/mqtt/subscribe")
async def subscribe_mqtt(request: MqttSubscribeRequest):
    """Subscribe to MQTT topic"""
    try:
        success = mqtt_broker.subscribe(request.topic, request.qos)
        if success:
            return {"status": "subscribed", "topic": request.topic}
        else:
            raise HTTPException(status_code=500, detail="Failed to subscribe")
    except Exception as e:
        logger.error(f"Error subscribing to topic: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/mqtt/unsubscribe")
async def unsubscribe_mqtt(topic: str):
    """Unsubscribe from MQTT topic"""
    try:
        success = mqtt_broker.unsubscribe(topic)
        if success:
            return {"status": "unsubscribed", "topic": topic}
        else:
            raise HTTPException(status_code=500, detail="Failed to unsubscribe")
    except Exception as e:
        logger.error(f"Error unsubscribing from topic: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/mqtt/messages")
async def get_mqtt_messages(limit: int = 100):
    """Get recent MQTT messages"""
    try:
        messages = mqtt_broker.get_message_log(limit)
        return {"messages": messages}
    except Exception as e:
        logger.error(f"Error getting MQTT messages: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/mqtt/simulator/start")
async def start_mqtt_simulator():
    """Start MQTT simulator"""
    try:
        await mqtt_simulator.start()
        return {"status": "started"}
    except Exception as e:
        logger.error(f"Error starting MQTT simulator: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/mqtt/simulator/stop")
async def stop_mqtt_simulator():
    """Stop MQTT simulator"""
    try:
        await mqtt_simulator.stop()
        return {"status": "stopped"}
    except Exception as e:
        logger.error(f"Error stopping MQTT simulator: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Device control endpoints
@app.post("/api/device/screenshot")
async def request_screenshot(device_id: str = "office"):
    """Request screenshot from device"""
    try:
        success = screenshot_handler.request_screenshot(device_id)
        if success:
            return {"status": "requested", "device_id": device_id}
        else:
            raise HTTPException(status_code=500, detail="Failed to request screenshot")
    except Exception as e:
        logger.error(f"Error requesting screenshot: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/device/screenshot/latest")
async def get_latest_screenshot():
    """Get latest screenshot"""
    try:
        screenshot = screenshot_handler.get_latest_screenshot()
        if screenshot:
            return screenshot
        else:
            return {"data": None, "message": "No screenshot available"}
    except Exception as e:
        logger.error(f"Error getting screenshot: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/device/screenshot/test")
async def get_test_screenshot():
    """Generate a test screenshot for development"""
    try:
        import base64
        test_image = screenshot_handler.generate_test_screenshot()
        if test_image:
            return {
                'data': base64.b64encode(test_image).decode('utf-8'),
                'width': config.display_width,
                'height': config.display_height,
                'format': 'png',
                'test': True
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to generate test screenshot")
    except Exception as e:
        logger.error(f"Error generating test screenshot: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/device/command")
async def send_device_command(request: DeviceCommandRequest):
    """Send command to device via MQTT"""
    try:
        device_id = request.params.get('device_id', 'office') if request.params else 'office'
        topic = f"espsensor/{device_id}/cmd/{request.command}"

        payload = request.params.get('payload', '') if request.params else ''

        success = mqtt_broker.publish(topic, payload)

        if success:
            return {"status": "sent", "command": request.command, "device_id": device_id}
        else:
            raise HTTPException(status_code=500, detail="Failed to send command")
    except Exception as e:
        logger.error(f"Error sending device command: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/device/status")
async def get_device_status():
    """Get device status from recent MQTT messages"""
    try:
        # Get recent messages and extract device status
        messages = mqtt_broker.get_message_log(100)

        # Parse for device status information
        status = {
            'connected': False,
            'last_seen': None,
            'battery': None,
            'temperature': None,
            'humidity': None,
            'heap': None,
        }

        # Look for relevant topics in recent messages
        for msg in reversed(messages):
            topic = msg.get('topic', '')

            if 'battery/percent' in topic:
                status['battery'] = msg.get('payload')
                status['connected'] = True
            elif 'inside/temperature' in topic:
                status['temperature'] = msg.get('payload')
                status['connected'] = True
            elif 'inside/humidity' in topic:
                status['humidity'] = msg.get('payload')
                status['connected'] = True
            elif 'heap' in topic:
                status['heap'] = msg.get('payload')
                status['connected'] = True

            if msg.get('timestamp'):
                if not status['last_seen'] or msg['timestamp'] > status['last_seen']:
                    status['last_seen'] = msg['timestamp']

        return status
    except Exception as e:
        logger.error(f"Error getting device status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/config/sleep-interval")
async def set_sleep_interval(request: SleepIntervalRequest, device_id: str = "office"):
    """Set device sleep interval via MQTT command"""
    try:
        # Validate interval (60 seconds to 1 hour)
        if request.interval_sec < 60 or request.interval_sec > 3600:
            raise HTTPException(
                status_code=400, 
                detail="Interval must be between 60 and 3600 seconds"
            )
        
        # Send MQTT command to device
        topic = f"espsensor/{device_id}/cmd/sleep_interval"
        payload = str(request.interval_sec)
        
        success = mqtt_broker.publish(topic, payload)
        
        if success:
            return {
                "status": "sent",
                "device_id": device_id,
                "interval_sec": request.interval_sec
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to send command")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error setting sleep interval: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Device Discovery Endpoints (mDNS)
# ============================================================================

@app.get("/api/discovery/devices")
async def get_discovered_devices():
    """Get all devices discovered via mDNS"""
    global _targeted_device_id
    
    devices = mdns_discovery.get_devices()
    return {
        "devices": [d.to_dict() for d in devices],
        "discovery_running": mdns_discovery.is_running(),
        "discovery_available": mdns_discovery.available,
        "targeted_device_id": _targeted_device_id
    }


@app.post("/api/discovery/start")
async def start_discovery():
    """Start mDNS device discovery"""
    if not mdns_discovery.available:
        raise HTTPException(
            status_code=503,
            detail="mDNS discovery not available (zeroconf library not installed)"
        )
    
    success = mdns_discovery.start()
    return {
        "status": "started" if success else "failed",
        "running": mdns_discovery.is_running()
    }


@app.post("/api/discovery/stop")
async def stop_discovery():
    """Stop mDNS device discovery"""
    mdns_discovery.stop()
    return {"status": "stopped", "running": False}


class TargetDeviceRequest(BaseModel):
    device_id: str


@app.post("/api/discovery/target")
async def set_target_device(request: TargetDeviceRequest):
    """
    Set the targeted device for all commands.
    
    SAFETY: Only ONE device can be targeted at a time. All commands
    (sleep interval, reboot, screenshot, etc.) will go to this device.
    """
    global _targeted_device_id
    
    # Verify device exists (if discovery is running)
    if mdns_discovery.is_running():
        device = mdns_discovery.get_device_by_id(request.device_id)
        if not device:
            # Allow manual device IDs even if not discovered
            logger.warning(f"Targeting device '{request.device_id}' not found via mDNS")
    
    old_target = _targeted_device_id
    _targeted_device_id = request.device_id
    
    logger.info(f"Target device changed: {old_target} -> {_targeted_device_id}")
    
    # Notify connected clients
    await hub.broadcast({
        "type": "target_changed",
        "device_id": _targeted_device_id,
        "previous_device_id": old_target
    })
    
    return {
        "status": "targeted",
        "device_id": _targeted_device_id,
        "previous_device_id": old_target
    }


@app.get("/api/discovery/target")
async def get_target_device():
    """Get the currently targeted device"""
    global _targeted_device_id
    
    device_info = None
    if _targeted_device_id and mdns_discovery.is_running():
        device = mdns_discovery.get_device_by_id(_targeted_device_id)
        if device:
            device_info = device.to_dict()
    
    return {
        "device_id": _targeted_device_id,
        "device_info": device_info
    }


@app.delete("/api/discovery/target")
async def clear_target_device():
    """Clear the targeted device (no device selected)"""
    global _targeted_device_id
    
    old_target = _targeted_device_id
    _targeted_device_id = None
    
    logger.info(f"Target device cleared (was: {old_target})")
    
    await hub.broadcast({
        "type": "target_changed",
        "device_id": None,
        "previous_device_id": old_target
    })
    
    return {"status": "cleared", "previous_device_id": old_target}


# ============================================================================
# Device Tracking & Wake Prediction Endpoints
# ============================================================================

@app.get("/api/devices")
async def get_all_tracked_devices():
    """Get all tracked devices with their state and wake predictions"""
    devices = device_tracker.get_all_devices()
    return {
        "devices": [d.to_dict() for d in devices],
        "sleep_presets": SLEEP_PRESETS
    }


@app.get("/api/devices/{device_id}")
async def get_device_state(device_id: str):
    """Get state for a specific device"""
    device = device_tracker.get_device(device_id)
    if not device:
        raise HTTPException(status_code=404, detail=f"Device {device_id} not found")
    return device.to_dict()


class SetModeRequest(BaseModel):
    mode: str  # "dev" or "production"


@app.post("/api/devices/{device_id}/mode")
async def set_device_mode(device_id: str, request: SetModeRequest):
    """
    Set device operating mode (dev or production).
    
    Dev mode enables screenshots and fixed sleep intervals.
    Auto-expires after 1 hour to prevent battery drain.
    """
    try:
        mode = DeviceMode(request.mode)
    except ValueError:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid mode. Must be 'dev' or 'production'"
        )
    
    # Update local tracker
    state = await device_tracker.set_mode(device_id, mode)
    
    # Send command to device via MQTT
    topic = f"espsensor/{device_id}/cmd/mode"
    payload = request.mode
    mqtt_broker.publish(topic, payload)
    
    # Broadcast state change
    await hub.broadcast({
        "type": "device_state",
        "device_id": device_id,
        "state": state.to_dict()
    })
    
    return {
        "status": "success",
        "device_id": device_id,
        "mode": mode.value,
        "dev_mode_timeout_sec": state.dev_mode_remaining_sec if mode == DeviceMode.DEVELOPMENT else 0
    }


class SetIntervalRequest(BaseModel):
    interval_sec: int


@app.post("/api/devices/{device_id}/interval")
async def set_device_interval(device_id: str, request: SetIntervalRequest):
    """
    Set device sleep interval.
    
    Minimum 180 seconds (3 minutes) to prevent sensor self-heating.
    Presets: 180 (3min), 300 (5min), 600 (10min), 3600 (1hr)
    """
    interval = request.interval_sec
    
    # Enforce minimum 3 minutes
    if interval < 180:
        raise HTTPException(
            status_code=400,
            detail="Minimum interval is 180 seconds (3 minutes) to prevent sensor heating"
        )
    
    # Enforce maximum 1 hour
    if interval > 3600:
        raise HTTPException(
            status_code=400,
            detail="Maximum interval is 3600 seconds (1 hour)"
        )
    
    # Update local tracker
    state = await device_tracker.set_sleep_interval(device_id, interval)
    
    # Send command to device via MQTT
    topic = f"espsensor/{device_id}/cmd/sleep_interval"
    payload = str(interval)
    mqtt_broker.publish(topic, payload)
    
    # Broadcast state change
    await hub.broadcast({
        "type": "device_state",
        "device_id": device_id,
        "state": state.to_dict()
    })
    
    return {
        "status": "success",
        "device_id": device_id,
        "interval_sec": interval
    }


@app.get("/api/presets/intervals")
async def get_interval_presets():
    """Get available sleep interval presets"""
    return {
        "presets": [
            {"name": "Dev (3 min)", "value": 180, "icon": "🔧"},
            {"name": "Testing (5 min)", "value": 300, "icon": "📊"},
            {"name": "Normal (10 min)", "value": 600, "icon": "🔋"},
            {"name": "Power Save (1 hr)", "value": 3600, "icon": "💤"},
        ],
        "min_sec": 180,
        "max_sec": 3600
    }


# WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates"""
    await hub.connect(websocket)
    try:
        while True:
            # Receive messages from client
            data = await websocket.receive_text()
            try:
                import json
                message = json.loads(data)
                response = await hub.handle_message(websocket, message)

                # Handle specific message types
                msg_type = message.get('type')
                if msg_type == 'serial_send':
                    serial_manager.send(message.get('data', ''))
                elif msg_type == 'request_screenshot':
                    # TODO: Implement screenshot request
                    pass
                elif msg_type == 'mqtt_publish':
                    # TODO: Implement MQTT publish
                    pass

            except json.JSONDecodeError:
                logger.warning("Received invalid JSON from WebSocket client")

    except WebSocketDisconnect:
        await hub.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await hub.disconnect(websocket)


# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    logger.info("Starting up...")

    # Start MQTT broker if enabled
    if config.mqtt_broker_enabled:
        try:
            await mqtt_broker.start()
            logger.info("MQTT broker started")
        except Exception as e:
            logger.error(f"Failed to start MQTT broker: {e}")
            logger.warning("MQTT features will be unavailable")
    
    # Start mDNS discovery
    if mdns_discovery.available:
        if mdns_discovery.start():
            logger.info("mDNS discovery started - scanning for devices")
        else:
            logger.warning("mDNS discovery failed to start")
    else:
        logger.info("mDNS discovery not available (install zeroconf: pip install zeroconf)")


# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down...")
    serial_manager.disconnect()

    # Stop mDNS discovery
    mdns_discovery.stop()

    # Stop MQTT services
    await mqtt_simulator.stop()
    await mqtt_broker.stop()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
