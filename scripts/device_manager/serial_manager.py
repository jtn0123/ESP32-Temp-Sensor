"""Serial port management for ESP32 devices"""
import serial
import serial.tools.list_ports
import threading
import time
import logging
from typing import List, Dict, Optional, Callable
import json
import asyncio

logger = logging.getLogger(__name__)


class SerialManager:
    """Manages serial port connections and communication"""

    def __init__(self, websocket_hub=None):
        self.port: Optional[str] = None
        self.serial: Optional[serial.Serial] = None
        self.reader_thread: Optional[threading.Thread] = None
        self.hub = websocket_hub
        self.running = False
        self.connected = False

    def list_ports(self) -> List[Dict[str, str]]:
        """Return list of available serial ports with metadata"""
        ports = []
        for port in serial.tools.list_ports.comports():
            # Filter for likely ESP32 devices
            description = port.description.lower()
            is_esp32 = any(chip in description for chip in [
                'cp210', 'ch340', 'ftdi', 'usb serial', 'uart'
            ])

            ports.append({
                'port': port.device,
                'description': port.description,
                'hwid': port.hwid,
                'likely_esp32': is_esp32
            })

        logger.info(f"Found {len(ports)} serial ports")
        return ports

    def connect(self, port: str, baud: int = 115200) -> bool:
        """Connect to specified serial port"""
        try:
            if self.connected:
                self.disconnect()

            logger.info(f"Connecting to {port} at {baud} baud")
            self.serial = serial.Serial(
                port=port,
                baudrate=baud,
                timeout=1.0,
                write_timeout=1.0
            )

            self.port = port
            self.connected = True
            self.running = True

            # Start reader thread
            self.reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
            self.reader_thread.start()

            logger.info(f"Connected to {port}")

            # Broadcast connection status
            if self.hub:
                asyncio.create_task(self.hub.broadcast({
                    'type': 'serial_status',
                    'connected': True,
                    'port': port,
                    'baud': baud
                }))

            return True

        except Exception as e:
            logger.error(f"Failed to connect to {port}: {e}")
            self.connected = False
            return False

    def disconnect(self):
        """Disconnect from serial port and cleanup"""
        logger.info(f"Disconnecting from {self.port}")
        self.running = False
        self.connected = False

        if self.reader_thread and self.reader_thread.is_alive():
            self.reader_thread.join(timeout=2.0)

        if self.serial and self.serial.is_open:
            self.serial.close()

        self.serial = None
        self.port = None

        # Broadcast disconnection
        if self.hub:
            asyncio.create_task(self.hub.broadcast({
                'type': 'serial_status',
                'connected': False
            }))

    def send(self, data: str):
        """Send data to device"""
        if not self.connected or not self.serial:
            logger.warning("Cannot send: not connected")
            return False

        try:
            if not data.endswith('\n'):
                data += '\n'
            self.serial.write(data.encode('utf-8'))
            logger.debug(f"Sent: {data.strip()}")
            return True
        except Exception as e:
            logger.error(f"Error sending data: {e}")
            return False

    def _reader_loop(self):
        """Background thread to read serial data and broadcast"""
        logger.info("Serial reader thread started")

        while self.running and self.serial and self.serial.is_open:
            try:
                if self.serial.in_waiting:
                    line = self.serial.readline()
                    if line:
                        try:
                            text = line.decode('utf-8', errors='replace').strip()
                            if text:
                                self._process_line(text)
                        except Exception as e:
                            logger.warning(f"Error decoding serial data: {e}")
                else:
                    time.sleep(0.01)  # Small sleep to avoid busy waiting

            except serial.SerialException as e:
                logger.error(f"Serial error: {e}")
                self.connected = False
                break
            except Exception as e:
                logger.error(f"Unexpected error in reader loop: {e}")

        logger.info("Serial reader thread stopped")
        self.connected = False

    def _process_line(self, line: str):
        """Process a line of serial data"""
        # Try to parse as JSON for structured data
        structured_data = None
        try:
            if line.startswith('{') and line.endswith('}'):
                structured_data = json.loads(line)
        except json.JSONDecodeError:
            pass

        # Broadcast to WebSocket clients
        if self.hub:
            message = {
                'type': 'serial',
                'data': line,
                'timestamp': time.time()
            }

            if structured_data:
                message['structured'] = structured_data

            asyncio.create_task(self.hub.broadcast(message))

    def get_status(self) -> Dict[str, Any]:
        """Get current serial connection status"""
        return {
            'connected': self.connected,
            'port': self.port,
            'is_open': self.serial.is_open if self.serial else False
        }
