"""
mDNS Discovery for ESP32 Sensor Devices

Discovers devices advertising the _espsensor._tcp service on the local network.
Each device advertises:
  - hostname: <room-name>.local
  - service txt: version=<fw_version>, room=<room_name>
"""

import asyncio
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

try:
    from zeroconf import ServiceBrowser, ServiceListener, Zeroconf, ServiceInfo
    ZEROCONF_AVAILABLE = True
except ImportError:
    ZEROCONF_AVAILABLE = False

logger = logging.getLogger(__name__)

SERVICE_TYPE = "_espsensor._tcp.local."


@dataclass
class DiscoveredDevice:
    """Represents a discovered ESP32 sensor device"""
    name: str                    # Service name (e.g., "office")
    hostname: str                # Full hostname (e.g., "office.local")
    ip_address: str              # IP address
    port: int                    # Service port
    room: str = ""               # Room name from TXT record
    version: str = ""            # Firmware version from TXT record
    last_seen: float = field(default_factory=time.time)
    
    @property
    def device_id(self) -> str:
        """Device ID used for MQTT topics (matches room name, lowercase)"""
        return self.room.lower().replace(" ", "_") if self.room else self.name
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "hostname": self.hostname,
            "ip_address": self.ip_address,
            "port": self.port,
            "room": self.room,
            "version": self.version,
            "device_id": self.device_id,
            "last_seen": self.last_seen,
            "age_seconds": int(time.time() - self.last_seen)
        }


class DeviceListener(ServiceListener):
    """Listener for mDNS service events"""
    
    def __init__(
        self, 
        on_change: Optional[Callable[[], None]] = None,
        on_device_added: Optional[Callable[['DiscoveredDevice'], None]] = None
    ):
        self.devices: dict[str, DiscoveredDevice] = {}
        self.on_change = on_change
        self.on_device_added = on_device_added  # Callback when new device appears
        self._lock = threading.Lock()
    
    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        """Called when a service is discovered"""
        info = zc.get_service_info(type_, name)
        if info:
            self._process_service_info(name, info)
    
    def update_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        """Called when a service is updated"""
        info = zc.get_service_info(type_, name)
        if info:
            self._process_service_info(name, info)
    
    def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        """Called when a service is removed"""
        with self._lock:
            # Extract device name from service name (e.g., "office._espsensor._tcp.local.")
            device_name = name.replace(f".{SERVICE_TYPE}", "").replace("._espsensor._tcp.local.", "")
            if device_name in self.devices:
                logger.info(f"Device removed: {device_name}")
                del self.devices[device_name]
                if self.on_change:
                    self.on_change()
    
    def _process_service_info(self, name: str, info: ServiceInfo) -> None:
        """Process service info and update device list"""
        # Extract device name
        device_name = name.replace(f".{SERVICE_TYPE}", "").replace("._espsensor._tcp.local.", "")
        
        # Get IP address
        addresses = info.parsed_addresses()
        ip_address = addresses[0] if addresses else ""
        
        # Parse TXT records
        properties = {}
        if info.properties:
            for key, value in info.properties.items():
                if isinstance(key, bytes):
                    key = key.decode('utf-8')
                if isinstance(value, bytes):
                    value = value.decode('utf-8')
                properties[key] = value
        
        device = DiscoveredDevice(
            name=device_name,
            hostname=info.server or f"{device_name}.local",
            ip_address=ip_address,
            port=info.port,
            room=properties.get("room", device_name),
            version=properties.get("version", "unknown"),
            last_seen=time.time()
        )
        
        with self._lock:
            is_new = device_name not in self.devices
            self.devices[device_name] = device
            
            if is_new:
                logger.info(f"Device discovered: {device.room} ({device.ip_address}) v{device.version}")
                # Notify about new device (for flash queue)
                if self.on_device_added:
                    self.on_device_added(device)
            else:
                logger.debug(f"Device updated: {device.room} ({device.ip_address})")
            
            if self.on_change:
                self.on_change()
    
    def get_devices(self) -> list[DiscoveredDevice]:
        """Get list of all discovered devices"""
        with self._lock:
            return list(self.devices.values())


class MDNSDiscovery:
    """
    mDNS Discovery Manager
    
    Continuously scans for ESP32 sensor devices on the network.
    Thread-safe and designed for long-running operation.
    """
    
    def __init__(
        self, 
        on_devices_changed: Optional[Callable[[], None]] = None,
        on_device_added: Optional[Callable[['DiscoveredDevice'], None]] = None
    ):
        self.on_devices_changed = on_devices_changed
        self.on_device_added = on_device_added  # Callback when new device appears
        self._zeroconf: Zeroconf | None = None
        self._browser: ServiceBrowser | None = None
        self._listener: DeviceListener | None = None
        self._running = False
    
    @property
    def available(self) -> bool:
        """Check if zeroconf library is available"""
        return ZEROCONF_AVAILABLE
    
    def start(self) -> bool:
        """Start mDNS discovery. Returns True if started successfully."""
        if not ZEROCONF_AVAILABLE:
            logger.warning("zeroconf library not available - mDNS discovery disabled")
            return False
        
        if self._running:
            return True
        
        try:
            self._zeroconf = Zeroconf()
            self._listener = DeviceListener(
                on_change=self.on_devices_changed,
                on_device_added=self.on_device_added
            )
            self._browser = ServiceBrowser(self._zeroconf, SERVICE_TYPE, self._listener)
            self._running = True
            logger.info(f"mDNS discovery started, scanning for {SERVICE_TYPE}")
            return True
        except Exception as e:
            logger.error(f"Failed to start mDNS discovery: {e}")
            self.stop()
            return False
    
    def stop(self) -> None:
        """Stop mDNS discovery"""
        if not self._running:
            return
        
        self._running = False
        
        if self._browser:
            try:
                self._browser.cancel()
            except Exception as e:
                logger.debug(f"Error canceling browser: {e}")
            self._browser = None
        
        if self._zeroconf:
            try:
                # Close zeroconf in a way that doesn't block
                # Use unregister_all_services() first if available, then close
                self._zeroconf.close()
            except Exception as e:
                logger.debug(f"Error closing zeroconf: {e}")
            self._zeroconf = None
        
        self._listener = None
        logger.info("mDNS discovery stopped")
    
    def get_devices(self) -> list[DiscoveredDevice]:
        """Get all discovered devices"""
        if self._listener:
            return self._listener.get_devices()
        return []
    
    def get_device_by_id(self, device_id: str) -> DiscoveredDevice | None:
        """Get a specific device by its ID"""
        for device in self.get_devices():
            if device.device_id == device_id or device.name == device_id:
                return device
        return None
    
    def is_running(self) -> bool:
        """Check if discovery is running"""
        return self._running
    
    def set_device_added_callback(self, callback: Optional[Callable[['DiscoveredDevice'], None]]):
        """Set the callback for when a new device is discovered (for flash queue integration)"""
        self.on_device_added = callback
        if self._listener:
            self._listener.on_device_added = callback


# Singleton instance
_discovery: MDNSDiscovery | None = None


def get_discovery() -> MDNSDiscovery:
    """Get the singleton discovery instance"""
    global _discovery
    if _discovery is None:
        _discovery = MDNSDiscovery()
    return _discovery
