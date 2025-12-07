"""Flash manager for ESP32 devices"""
import subprocess
import re
import asyncio
import logging
import time
import threading
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Callable, List
from pathlib import Path
import serial.tools.list_ports

logger = logging.getLogger(__name__)


@dataclass
class QueuedFlash:
    """Represents a queued flash operation waiting for a device"""
    build_config: str                    # 'dev', 'prod', etc.
    target_port: Optional[str] = None    # Specific port or None for "any USB"
    target_device_id: Optional[str] = None  # mDNS device ID for OTA
    firmware_built: bool = False
    firmware_path: Optional[str] = None
    env_name: Optional[str] = None       # PlatformIO environment name
    created_at: float = field(default_factory=time.time)
    expires_at: Optional[float] = None   # Optional timeout timestamp
    status: str = "pending"              # pending, building, hunting, flashing, completed, failed, cancelled, expired
    sleep_interval_sec: Optional[int] = None  # Sleep interval to apply after flash
    
    def is_expired(self) -> bool:
        """Check if the queued flash has expired"""
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at
    
    def time_remaining(self) -> Optional[float]:
        """Get seconds remaining until expiration, or None if no timeout"""
        if self.expires_at is None:
            return None
        return max(0, self.expires_at - time.time())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "build_config": self.build_config,
            "target_port": self.target_port,
            "target_device_id": self.target_device_id,
            "firmware_built": self.firmware_built,
            "status": self.status,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "time_remaining": self.time_remaining(),
            "is_expired": self.is_expired(),
            "sleep_interval_sec": self.sleep_interval_sec
        }


class FlashManager:
    """Manages firmware flashing operations"""

    def __init__(self, websocket_hub=None, config=None):
        self.hub = websocket_hub
        self.config = config
        self.process: Optional[subprocess.Popen] = None
        self.is_flashing = False
        self.flash_task: Optional[asyncio.Task] = None
        
        # Flash queue / hunt mode
        self.queued_flash: Optional[QueuedFlash] = None
        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._known_ports: set = set()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._on_device_callback: Optional[Callable[[str], None]] = None

    async def flash(
        self,
        port: str,
        firmware_path: Optional[str] = None,
        build_config: str = "dev"
    ) -> bool:
        """
        Flash firmware to device.

        Args:
            port: Serial port path
            firmware_path: Path to compiled firmware (if None, build first)
            build_config: Build configuration ('dev', 'prod', 'battery_test')

        Returns:
            bool: Success status
        """
        if self.is_flashing:
            logger.warning("Flash operation already in progress")
            return False

        self.is_flashing = True

        try:
            # Map build config to PlatformIO environment
            env_map = {
                'dev': self.config.platformio_env_dev if self.config else 'dev_display',
                'prod': self.config.platformio_env_prod if self.config else 'feather_esp32s2_display_only',
                'battery_test': 'feather_esp32s2_battery_test',
            }

            env = env_map.get(build_config, 'dev_display')

            # If no firmware path provided, build first
            if not firmware_path:
                await self._broadcast('flash_progress', {
                    'percent': 0,
                    'stage': 'building',
                    'message': f'Building firmware for {env}...'
                })

                build_success, build_error = await self._run_build(env)
                if not build_success:
                    error_msg = f'Build failed: {build_error}' if build_error else 'Build failed'
                    await self._broadcast('flash_complete', {
                        'success': False,
                        'message': error_msg
                    })
                    return False

            # Flash the firmware
            await self._broadcast('flash_progress', {
                'percent': 50,
                'stage': 'flashing',
                'message': 'Flashing firmware...'
            })

            flash_success = await self._run_flash(port, env)

            await self._broadcast('flash_complete', {
                'success': flash_success,
                'message': 'Flash successful!' if flash_success else 'Flash failed'
            })

            return flash_success

        except Exception as e:
            logger.error(f"Flash error: {e}")
            await self._broadcast('flash_complete', {
                'success': False,
                'message': f'Error: {str(e)}'
            })
            return False

        finally:
            self.is_flashing = False

    async def _run_build(self, env: str) -> tuple[bool, Optional[str]]:
        """Run PlatformIO build. Returns (success, error_message)."""
        try:
            # Find the firmware directory
            script_dir = Path(__file__).parent.parent.parent  # Up to project root
            firmware_dir = script_dir / "firmware" / "arduino"
            
            if not firmware_dir.exists():
                return False, f"Firmware directory not found: {firmware_dir}"
            
            cmd = ['pio', 'run', '-e', env]
            logger.info(f"Running build in {firmware_dir}: {' '.join(cmd)}")

            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(firmware_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT
            )

            # Collect output for error reporting
            output_lines: List[str] = []
            error_lines: List[str] = []

            # Stream build output
            async for line in process.stdout:
                text = line.decode('utf-8', errors='replace').strip()
                if text:
                    output_lines.append(text)
                    logger.debug(f"Build: {text}")
                    
                    # Capture error-related lines
                    text_lower = text.lower()
                    if any(x in text_lower for x in ['error:', 'error[', 'fatal:', 'undefined reference', 'no such file']):
                        error_lines.append(text)
                    
                    await self._broadcast('flash_progress', {
                        'percent': 25,
                        'stage': 'building',
                        'message': text[:100]  # Truncate long lines
                    })

            await process.wait()
            success = process.returncode == 0

            if success:
                logger.info("Build successful")
                return True, None
            else:
                # Extract useful error info
                error_msg = None
                if error_lines:
                    error_msg = error_lines[-1][:200]  # Last error, truncated
                elif output_lines:
                    # Look for the last few lines that might have useful info
                    for line in reversed(output_lines[-10:]):
                        if line and not line.startswith('='):
                            error_msg = line[:200]
                            break
                
                logger.error(f"Build failed with code {process.returncode}: {error_msg}")
                return False, error_msg

        except FileNotFoundError:
            error_msg = "PlatformIO (pio) not found. Install with: pip install platformio"
            logger.error(f"Build error: {error_msg}")
            return False, error_msg
        except Exception as e:
            logger.error(f"Build error: {e}")
            return False, str(e)

    async def _run_flash(self, port: str, env: str) -> bool:
        """Run PlatformIO upload"""
        try:
            # Find the firmware directory
            script_dir = Path(__file__).parent.parent.parent  # Up to project root
            firmware_dir = script_dir / "firmware" / "arduino"
            
            cmd = ['pio', 'run', '-e', env, '-t', 'upload', '--upload-port', port]
            logger.info(f"Running flash in {firmware_dir}: {' '.join(cmd)}")

            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(firmware_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT
            )

            # Parse flash progress
            async for line in process.stdout:
                text = line.decode('utf-8', errors='replace').strip()
                if text:
                    logger.debug(f"Flash: {text}")

                    # Try to parse esptool progress
                    percent = self._parse_flash_progress(text)
                    if percent is not None:
                        await self._broadcast('flash_progress', {
                            'percent': 50 + (percent // 2),  # Map to 50-100%
                            'stage': 'writing',
                            'message': text[:100]
                        })
                    else:
                        await self._broadcast('flash_progress', {
                            'percent': 75,
                            'stage': 'writing',
                            'message': text[:100]
                        })

            await process.wait()
            success = process.returncode == 0

            if success:
                logger.info("Flash successful")
            else:
                logger.error(f"Flash failed with code {process.returncode}")

            return success

        except Exception as e:
            logger.error(f"Flash error: {e}")
            return False

    def _parse_flash_progress(self, line: str) -> Optional[int]:
        """Parse progress percentage from esptool output"""
        # Look for patterns like: "Writing at 0x00010000... (50 %)"
        match = re.search(r'\((\d+)\s*%\)', line)
        if match:
            return int(match.group(1))

        # Look for "Wrote XXXXX bytes"
        if "Wrote" in line and "bytes" in line:
            return 90

        return None

    async def cancel(self):
        """Cancel flash in progress"""
        if self.process and self.process.poll() is None:
            logger.info("Cancelling flash operation")
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()

            self.is_flashing = False

            await self._broadcast('flash_complete', {
                'success': False,
                'message': 'Flash cancelled by user'
            })

    async def _broadcast(self, msg_type: str, data: Dict[str, Any]):
        """Broadcast message via WebSocket hub"""
        if self.hub:
            message = {'type': msg_type, **data}
            await self.hub.broadcast(message)

    def get_status(self) -> Dict[str, Any]:
        """Get current flash status"""
        return {
            'is_flashing': self.is_flashing,
            'queue': self.queued_flash.to_dict() if self.queued_flash else None,
            'is_hunting': self._monitoring and self.queued_flash is not None
        }
    
    # ─────────────────────────────────────────────────────────────────
    # Flash Queue / Hunt Mode
    # ─────────────────────────────────────────────────────────────────
    
    async def queue_flash(
        self,
        build_config: str = "dev",
        target_port: Optional[str] = None,
        target_device_id: Optional[str] = None,
        timeout_minutes: Optional[int] = 15,
        sleep_interval_sec: Optional[int] = None
    ) -> tuple[bool, Optional[str]]:
        """
        Queue a flash operation and start hunting for device.
        
        Pre-builds firmware immediately, then monitors for device connection.
        
        Args:
            build_config: Build configuration ('dev', 'prod', 'battery_test')
            target_port: Specific port to watch, or None for any new port
            target_device_id: mDNS device ID for OTA flashing
            timeout_minutes: Minutes until queue expires, or None for no timeout
            sleep_interval_sec: Sleep interval to apply after flash (via MQTT)
            
        Returns:
            tuple: (success: bool, error_message: Optional[str])
        """
        if self.queued_flash is not None:
            logger.warning("Flash already queued - cancel first")
            return False, "Flash already queued - cancel first"
        
        if self.is_flashing:
            logger.warning("Flash operation in progress")
            return False, "Flash operation already in progress"
        
        # Store event loop for thread-safe callbacks
        self._loop = asyncio.get_running_loop()
        
        # Calculate expiration time
        expires_at = None
        if timeout_minutes is not None:
            expires_at = time.time() + (timeout_minutes * 60)
        
        # Map build config to environment
        env_map = {
            'dev': self.config.platformio_env_dev if self.config else 'dev_display',
            'prod': self.config.platformio_env_prod if self.config else 'feather_esp32s2_display_only',
            'battery_test': 'feather_esp32s2_battery_test',
        }
        env_name = env_map.get(build_config, 'dev_display')
        
        # Create queued flash
        self.queued_flash = QueuedFlash(
            build_config=build_config,
            target_port=target_port,
            target_device_id=target_device_id,
            expires_at=expires_at,
            env_name=env_name,
            status="building",
            sleep_interval_sec=sleep_interval_sec
        )
        
        logger.info(f"Flash queued: config={build_config}, target_port={target_port}, timeout={timeout_minutes}min, sleep={sleep_interval_sec}s")
        
        # Broadcast queue started
        await self._broadcast('flash_queue_status', {
            'status': 'building',
            'message': f'Building firmware ({build_config})...',
            'queue': self.queued_flash.to_dict()
        })
        
        # Pre-build firmware
        build_success, build_error = await self._run_build(env_name)
        
        if not build_success:
            self.queued_flash.status = "failed"
            error_msg = f"Build failed: {build_error}" if build_error else "Build failed"
            await self._broadcast('flash_queue_status', {
                'status': 'failed',
                'message': error_msg,
                'queue': self.queued_flash.to_dict()
            })
            self.queued_flash = None
            return False, error_msg
        
        # Mark as built and ready to hunt
        self.queued_flash.firmware_built = True
        self.queued_flash.status = "hunting"
        
        logger.info("Build complete, starting device hunt")
        
        await self._broadcast('flash_queue_status', {
            'status': 'hunting',
            'message': 'Hunting for device...',
            'queue': self.queued_flash.to_dict()
        })
        
        # Start monitoring for devices
        self._start_port_monitoring()
        
        # Start timeout checker
        if expires_at:
            asyncio.create_task(self._check_queue_timeout())
        
        return True, None
    
    async def cancel_queued_flash(self) -> bool:
        """Cancel the queued flash operation"""
        if self.queued_flash is None:
            return False
        
        logger.info("Cancelling queued flash")
        
        self._stop_port_monitoring()
        self.queued_flash.status = "cancelled"
        
        await self._broadcast('flash_queue_status', {
            'status': 'cancelled',
            'message': 'Flash queue cancelled',
            'queue': self.queued_flash.to_dict()
        })
        
        self.queued_flash = None
        return True
    
    def get_queue_status(self) -> Optional[Dict[str, Any]]:
        """Get current queue status"""
        if self.queued_flash is None:
            return None
        return self.queued_flash.to_dict()
    
    def _start_port_monitoring(self):
        """Start background thread to monitor for new USB ports"""
        if self._monitoring:
            return
        
        # Capture current ports
        self._known_ports = set(p.device for p in serial.tools.list_ports.comports())
        self._monitoring = True
        
        self._monitor_thread = threading.Thread(target=self._port_monitor_loop, daemon=True)
        self._monitor_thread.start()
        
        logger.info(f"Port monitoring started. Known ports: {self._known_ports}")
    
    def _stop_port_monitoring(self):
        """Stop port monitoring"""
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=2.0)
            self._monitor_thread = None
        logger.info("Port monitoring stopped")
    
    def _port_monitor_loop(self):
        """Background thread that monitors for new USB ports"""
        while self._monitoring and self.queued_flash is not None:
            try:
                # Check for expiration
                if self.queued_flash and self.queued_flash.is_expired():
                    logger.info("Flash queue expired")
                    if self._loop:
                        asyncio.run_coroutine_threadsafe(
                            self._handle_queue_expired(),
                            self._loop
                        )
                    break
                
                # Check for new ports
                current_ports = set(p.device for p in serial.tools.list_ports.comports())
                new_ports = current_ports - self._known_ports
                
                for port in new_ports:
                    logger.info(f"New port detected: {port}")
                    
                    # Check if this matches our target
                    if self._port_matches_target(port):
                        logger.info(f"Target device found on {port}!")
                        if self._loop:
                            asyncio.run_coroutine_threadsafe(
                                self._handle_device_detected(port),
                                self._loop
                            )
                        return  # Stop monitoring after finding device
                
                # Update known ports (track removals too)
                self._known_ports = current_ports
                
                time.sleep(0.5)  # Check every 500ms
                
            except Exception as e:
                logger.error(f"Error in port monitor: {e}")
                time.sleep(1.0)
        
        logger.debug("Port monitor loop ended")
    
    def _port_matches_target(self, port: str) -> bool:
        """Check if a port matches the target criteria"""
        if self.queued_flash is None:
            return False
        
        # If specific port is set, must match exactly
        if self.queued_flash.target_port:
            return port == self.queued_flash.target_port
        
        # Otherwise, accept any new USB serial port
        # Filter to likely ESP32 ports (USB modems, etc.)
        port_lower = port.lower()
        if any(x in port_lower for x in ['usbmodem', 'usbserial', 'ttyusb', 'ttyacm', 'cu.slab']):
            return True
        
        return False
    
    async def _handle_device_detected(self, port: str):
        """Handle when target device is detected"""
        if self.queued_flash is None:
            return
        
        self._stop_port_monitoring()
        
        logger.info(f"Device detected on {port}, starting flash")
        self.queued_flash.status = "flashing"
        
        await self._broadcast('flash_queue_status', {
            'status': 'device_detected',
            'message': f'Device found on {port}! Flashing...',
            'port': port,
            'queue': self.queued_flash.to_dict()
        })
        
        # Small delay to let device fully enumerate
        await asyncio.sleep(1.0)
        
        # Send keep-awake command if possible
        await self._send_keep_awake(port)
        
        # Flash using the pre-built firmware
        env = self.queued_flash.env_name
        build_config = self.queued_flash.build_config
        sleep_interval = self.queued_flash.sleep_interval_sec
        
        # Clear the queue before flashing (so we don't re-trigger)
        self.queued_flash = None
        
        # Use existing flash method (firmware already built)
        success = await self.flash(port, firmware_path=None, build_config=build_config)
        
        if success:
            logger.info("Queued flash completed successfully")
            
            # Apply sleep interval if specified
            if sleep_interval is not None:
                await self._apply_sleep_interval(sleep_interval)
        else:
            logger.error("Queued flash failed")
    
    async def _apply_sleep_interval(self, interval_sec: int):
        """Apply sleep interval to device via MQTT after flash"""
        if self.hub is None:
            logger.warning("No WebSocket hub available to apply sleep interval")
            return
        
        try:
            # Import here to avoid circular dependency
            from .mqtt_broker import SimpleMQTTBroker
            
            # Find mqtt_broker from app context - we'll broadcast the config
            # and let the server apply it when the device comes online
            logger.info(f"Will apply sleep interval {interval_sec}s when device connects")
            
            await self._broadcast('flash_progress', {
                'percent': 100,
                'stage': 'configuring',
                'message': f'Flash complete. Sleep interval: {interval_sec}s will apply on next boot.'
            })
            
            # Also broadcast for any listeners
            await self._broadcast('config_pending', {
                'type': 'sleep_interval',
                'interval_sec': interval_sec,
                'message': f'Sleep interval of {interval_sec}s will be applied when device connects'
            })
            
        except Exception as e:
            logger.error(f"Error applying sleep interval: {e}")
    
    async def _handle_queue_expired(self):
        """Handle queue timeout expiration"""
        if self.queued_flash is None:
            return
        
        self._stop_port_monitoring()
        self.queued_flash.status = "expired"
        
        await self._broadcast('flash_queue_status', {
            'status': 'expired',
            'message': 'Flash queue timed out - no device found',
            'queue': self.queued_flash.to_dict()
        })
        
        self.queued_flash = None
    
    async def _check_queue_timeout(self):
        """Async task to check for queue timeout"""
        while self.queued_flash is not None and not self.queued_flash.is_expired():
            await asyncio.sleep(5.0)  # Check every 5 seconds
            
            # Broadcast remaining time
            if self.queued_flash and self.queued_flash.status == "hunting":
                remaining = self.queued_flash.time_remaining()
                if remaining is not None:
                    await self._broadcast('flash_queue_status', {
                        'status': 'hunting',
                        'message': f'Hunting for device... ({int(remaining)}s remaining)',
                        'queue': self.queued_flash.to_dict()
                    })
    
    async def _send_keep_awake(self, port: str):
        """Send keep-awake command to prevent device from sleeping during flash"""
        try:
            import serial
            with serial.Serial(port, 115200, timeout=1) as ser:
                # Send a command to keep device awake
                # This assumes firmware supports a "stay" or similar command
                ser.write(b"stay\n")
                await asyncio.sleep(0.5)
                logger.info("Sent keep-awake command")
        except Exception as e:
            logger.debug(f"Could not send keep-awake (device may not support it): {e}")
    
    def on_mdns_device_found(self, device_id: str, ip_address: str):
        """
        Callback for mDNS discovery when a device wakes up.
        Called from the mDNS discovery module.
        """
        if self.queued_flash is None:
            return
        
        if self.queued_flash.target_device_id is None:
            return  # Not targeting OTA
        
        if self.queued_flash.target_device_id == device_id:
            logger.info(f"Target mDNS device found: {device_id} at {ip_address}")
            if self._loop:
                asyncio.run_coroutine_threadsafe(
                    self._handle_ota_device_detected(device_id, ip_address),
                    self._loop
                )
    
    async def _handle_ota_device_detected(self, device_id: str, ip_address: str):
        """Handle OTA device detection for wireless flashing"""
        if self.queued_flash is None:
            return
        
        self._stop_port_monitoring()
        
        logger.info(f"OTA device detected: {device_id} at {ip_address}")
        self.queued_flash.status = "flashing"
        
        await self._broadcast('flash_queue_status', {
            'status': 'device_detected',
            'message': f'Device {device_id} found at {ip_address}! Flashing OTA...',
            'device_id': device_id,
            'ip_address': ip_address,
            'queue': self.queued_flash.to_dict()
        })
        
        # OTA flash using PlatformIO
        env = self.queued_flash.env_name
        self.queued_flash = None
        
        success = await self._run_ota_flash(ip_address, env)
        
        await self._broadcast('flash_complete', {
            'success': success,
            'message': 'OTA flash successful!' if success else 'OTA flash failed'
        })
    
    async def _run_ota_flash(self, ip_address: str, env: str) -> bool:
        """Run OTA flash to a device"""
        try:
            # Find the firmware directory
            script_dir = Path(__file__).parent.parent.parent  # Up to project root
            firmware_dir = script_dir / "firmware" / "arduino"
            
            cmd = ['pio', 'run', '-e', env, '-t', 'upload', '--upload-port', ip_address]
            logger.info(f"Running OTA flash in {firmware_dir}: {' '.join(cmd)}")
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(firmware_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT
            )
            
            async for line in process.stdout:
                text = line.decode('utf-8', errors='replace').strip()
                if text:
                    logger.debug(f"OTA Flash: {text}")
                    await self._broadcast('flash_progress', {
                        'percent': 75,
                        'stage': 'ota_upload',
                        'message': text[:100]
                    })
            
            await process.wait()
            return process.returncode == 0
            
        except Exception as e:
            logger.error(f"OTA flash error: {e}")
            return False
