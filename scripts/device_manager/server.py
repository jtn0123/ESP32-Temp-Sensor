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


# MQTT endpoints (stubs for now)
@app.get("/api/mqtt/status")
async def get_mqtt_status():
    """Get MQTT broker status"""
    return {"status": "not_implemented"}


@app.post("/api/mqtt/publish")
async def publish_mqtt():
    """Publish MQTT message"""
    return {"status": "not_implemented"}


@app.get("/api/mqtt/subscriptions")
async def get_mqtt_subscriptions():
    """List active MQTT subscriptions"""
    return {"status": "not_implemented"}


# Device control endpoints (stubs for now)
@app.post("/api/device/screenshot")
async def request_screenshot():
    """Request screenshot from device"""
    return {"status": "not_implemented"}


@app.get("/api/device/screenshot/latest")
async def get_latest_screenshot():
    """Get latest screenshot"""
    return {"status": "not_implemented"}


@app.post("/api/device/command")
async def send_device_command(request: DeviceCommandRequest):
    """Send command to device"""
    return {"status": "not_implemented", "command": request.command}


@app.get("/api/device/status")
async def get_device_status():
    """Get device status"""
    return {"status": "not_implemented"}


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


# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down...")
    serial_manager.disconnect()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
