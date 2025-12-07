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
async def set_sleep_interval(request: SleepIntervalRequest):
    """Set device sleep interval"""
    return {"status": "not_implemented", "interval_sec": request.interval_sec}


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


# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down...")
    serial_manager.disconnect()

    # Stop MQTT services
    await mqtt_simulator.stop()
    await mqtt_broker.stop()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
