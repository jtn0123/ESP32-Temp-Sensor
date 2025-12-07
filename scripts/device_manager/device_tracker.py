"""
Device Tracker - Tracks device state, activity, and wake predictions

Monitors MQTT and serial activity to determine device status and predict
when sleeping devices will next wake up.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any, Callable

logger = logging.getLogger(__name__)


class DeviceStatus(Enum):
    """Device activity status"""
    UNKNOWN = "unknown"      # Never seen or no data
    AWAKE = "awake"          # Activity within last 30 seconds
    SLEEPING = "sleeping"    # No activity for 30+ seconds


class DeviceMode(Enum):
    """Device operating mode"""
    PRODUCTION = "production"  # Power-efficient, adaptive sleep
    DEVELOPMENT = "dev"        # Fixed interval, screenshots enabled


# Sleep interval presets (seconds)
# Minimum 3 minutes to prevent sensor self-heating
SLEEP_PRESETS = {
    "dev": 180,        # 3 minutes
    "testing": 300,    # 5 minutes  
    "normal": 600,     # 10 minutes
    "power_save": 3600 # 1 hour
}

# Auto-timeout for dev mode (1 hour)
DEV_MODE_TIMEOUT_SEC = 3600

# Time after last activity to consider device sleeping
AWAKE_THRESHOLD_SEC = 30


@dataclass
class DeviceState:
    """Complete state for a tracked device"""
    device_id: str
    
    # Activity tracking
    last_activity: float = 0.0          # Unix timestamp
    last_activity_source: str = ""       # "mqtt", "serial", "discovery"
    
    # Mode and interval
    mode: DeviceMode = DeviceMode.PRODUCTION
    sleep_interval_sec: int = 600        # Default 10 minutes
    dev_mode_started: float = 0.0        # When dev mode was enabled
    
    # Device-reported status (from MQTT)
    reported_battery_pct: int = -1
    reported_heap_free: int = -1
    reported_fw_version: str = ""
    reported_room: str = ""
    
    # Discovery info
    ip_address: str = ""
    hostname: str = ""
    
    @property
    def status(self) -> DeviceStatus:
        """Determine current device status based on activity"""
        if self.last_activity == 0:
            return DeviceStatus.UNKNOWN
        
        elapsed = time.time() - self.last_activity
        if elapsed < AWAKE_THRESHOLD_SEC:
            return DeviceStatus.AWAKE
        return DeviceStatus.SLEEPING
    
    @property
    def seconds_since_activity(self) -> float:
        """Seconds since last activity"""
        if self.last_activity == 0:
            return -1
        return time.time() - self.last_activity
    
    @property
    def next_wake_estimate(self) -> float:
        """Estimated Unix timestamp of next wake"""
        if self.last_activity == 0 or self.sleep_interval_sec <= 0:
            return 0
        return self.last_activity + self.sleep_interval_sec
    
    @property
    def seconds_until_wake(self) -> float:
        """Seconds until estimated next wake (negative if overdue)"""
        if self.next_wake_estimate == 0:
            return -1
        return self.next_wake_estimate - time.time()
    
    @property
    def wake_progress_pct(self) -> float:
        """Progress through sleep cycle (0-100, >100 if overdue)"""
        if self.last_activity == 0 or self.sleep_interval_sec <= 0:
            return 0
        elapsed = time.time() - self.last_activity
        return min((elapsed / self.sleep_interval_sec) * 100, 150)  # Cap at 150%
    
    @property
    def dev_mode_remaining_sec(self) -> float:
        """Seconds remaining in dev mode before auto-timeout"""
        if self.mode != DeviceMode.DEVELOPMENT or self.dev_mode_started == 0:
            return 0
        elapsed = time.time() - self.dev_mode_started
        remaining = DEV_MODE_TIMEOUT_SEC - elapsed
        return max(0, remaining)
    
    @property
    def dev_mode_expired(self) -> bool:
        """Check if dev mode has auto-expired"""
        return (self.mode == DeviceMode.DEVELOPMENT and 
                self.dev_mode_remaining_sec <= 0 and 
                self.dev_mode_started > 0)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "device_id": self.device_id,
            "status": self.status.value,
            "mode": self.mode.value,
            "sleep_interval_sec": self.sleep_interval_sec,
            "last_activity": self.last_activity,
            "last_activity_source": self.last_activity_source,
            "seconds_since_activity": round(self.seconds_since_activity, 1),
            "next_wake_estimate": self.next_wake_estimate,
            "seconds_until_wake": round(self.seconds_until_wake, 1),
            "wake_progress_pct": round(self.wake_progress_pct, 1),
            "dev_mode_remaining_sec": round(self.dev_mode_remaining_sec, 0),
            "dev_mode_expired": self.dev_mode_expired,
            "reported_battery_pct": self.reported_battery_pct,
            "reported_heap_free": self.reported_heap_free,
            "reported_fw_version": self.reported_fw_version,
            "reported_room": self.reported_room,
            "ip_address": self.ip_address,
            "hostname": self.hostname,
        }


class DeviceTracker:
    """
    Tracks device state, activity, and wake predictions.
    
    Thread-safe singleton that monitors MQTT and serial activity
    to maintain current state for all known devices.
    """
    
    def __init__(self, on_state_changed: Optional[Callable[[str, DeviceState], None]] = None):
        self._devices: Dict[str, DeviceState] = {}
        self._on_state_changed = on_state_changed
        self._lock = asyncio.Lock()
    
    async def record_activity(self, device_id: str, source: str = "mqtt") -> DeviceState:
        """
        Record activity for a device.
        
        Args:
            device_id: Device identifier
            source: Activity source ("mqtt", "serial", "discovery")
        
        Returns:
            Updated device state
        """
        async with self._lock:
            device = self._get_or_create(device_id)
            device.last_activity = time.time()
            device.last_activity_source = source
            
            # Check for dev mode expiry
            if device.dev_mode_expired:
                logger.info(f"Device {device_id} dev mode expired, reverting to production")
                device.mode = DeviceMode.PRODUCTION
                device.dev_mode_started = 0
            
            logger.debug(f"Device {device_id} activity from {source}")
            
            if self._on_state_changed:
                self._on_state_changed(device_id, device)
            
            return device
    
    async def update_from_mqtt(self, device_id: str, topic: str, payload: str) -> DeviceState:
        """
        Update device state from MQTT message.
        
        Parses various MQTT topics to extract device information.
        """
        async with self._lock:
            device = self._get_or_create(device_id)
            device.last_activity = time.time()
            device.last_activity_source = "mqtt"
            
            # Parse topic for data type
            topic_lower = topic.lower()
            
            try:
                if "battery" in topic_lower:
                    device.reported_battery_pct = int(float(payload))
                elif "heap" in topic_lower:
                    device.reported_heap_free = int(payload)
                elif "version" in topic_lower or "fw" in topic_lower:
                    device.reported_fw_version = payload.strip()
                elif "status" in topic_lower:
                    # Try to parse JSON status
                    import json
                    try:
                        status = json.loads(payload)
                        if "mode" in status:
                            device.mode = DeviceMode(status["mode"])
                        if "sleep_interval_sec" in status:
                            device.sleep_interval_sec = int(status["sleep_interval_sec"])
                        if "battery_pct" in status:
                            device.reported_battery_pct = int(status["battery_pct"])
                        if "heap_free" in status:
                            device.reported_heap_free = int(status["heap_free"])
                        if "fw_version" in status:
                            device.reported_fw_version = status["fw_version"]
                        if "room" in status:
                            device.reported_room = status["room"]
                    except json.JSONDecodeError:
                        pass
            except (ValueError, TypeError) as e:
                logger.debug(f"Error parsing MQTT payload: {e}")
            
            # Check for dev mode expiry
            if device.dev_mode_expired:
                device.mode = DeviceMode.PRODUCTION
                device.dev_mode_started = 0
            
            if self._on_state_changed:
                self._on_state_changed(device_id, device)
            
            return device
    
    async def set_mode(self, device_id: str, mode: DeviceMode) -> DeviceState:
        """Set device operating mode"""
        async with self._lock:
            device = self._get_or_create(device_id)
            old_mode = device.mode
            device.mode = mode
            
            if mode == DeviceMode.DEVELOPMENT:
                device.dev_mode_started = time.time()
                logger.info(f"Device {device_id} entering dev mode (1hr timeout)")
            else:
                device.dev_mode_started = 0
                logger.info(f"Device {device_id} entering production mode")
            
            if self._on_state_changed:
                self._on_state_changed(device_id, device)
            
            return device
    
    async def set_sleep_interval(self, device_id: str, interval_sec: int) -> DeviceState:
        """Set device sleep interval"""
        async with self._lock:
            device = self._get_or_create(device_id)
            
            # Enforce minimum 3 minutes
            interval_sec = max(180, interval_sec)
            device.sleep_interval_sec = interval_sec
            
            logger.info(f"Device {device_id} sleep interval set to {interval_sec}s")
            
            if self._on_state_changed:
                self._on_state_changed(device_id, device)
            
            return device
    
    async def update_from_discovery(self, device_id: str, ip: str, hostname: str, 
                                     room: str = "", version: str = "") -> DeviceState:
        """Update device info from mDNS discovery"""
        async with self._lock:
            device = self._get_or_create(device_id)
            device.ip_address = ip
            device.hostname = hostname
            if room:
                device.reported_room = room
            if version:
                device.reported_fw_version = version
            device.last_activity = time.time()
            device.last_activity_source = "discovery"
            
            return device
    
    def get_device(self, device_id: str) -> Optional[DeviceState]:
        """Get state for a specific device"""
        return self._devices.get(device_id)
    
    def get_all_devices(self) -> list[DeviceState]:
        """Get all tracked devices"""
        return list(self._devices.values())
    
    def _get_or_create(self, device_id: str) -> DeviceState:
        """Get existing device or create new one"""
        if device_id not in self._devices:
            self._devices[device_id] = DeviceState(device_id=device_id)
            logger.info(f"Now tracking device: {device_id}")
        return self._devices[device_id]


# Singleton instance
_tracker: Optional[DeviceTracker] = None


def get_tracker() -> DeviceTracker:
    """Get the singleton tracker instance"""
    global _tracker
    if _tracker is None:
        _tracker = DeviceTracker()
    return _tracker
