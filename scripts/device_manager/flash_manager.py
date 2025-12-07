"""Flash manager for ESP32 devices"""
import subprocess
import re
import asyncio
import logging
from typing import Optional, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class FlashManager:
    """Manages firmware flashing operations"""

    def __init__(self, websocket_hub=None, config=None):
        self.hub = websocket_hub
        self.config = config
        self.process: Optional[subprocess.Popen] = None
        self.is_flashing = False
        self.flash_task: Optional[asyncio.Task] = None

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
                'dev': self.config.platformio_env_dev if self.config else 'feather_esp32s2_display_only_dev',
                'prod': self.config.platformio_env_prod if self.config else 'feather_esp32s2_display_only',
                'battery_test': 'feather_esp32s2_battery_test',
            }

            env = env_map.get(build_config, 'feather_esp32s2_display_only_dev')

            # If no firmware path provided, build first
            if not firmware_path:
                await self._broadcast('flash_progress', {
                    'percent': 0,
                    'stage': 'building',
                    'message': f'Building firmware for {env}...'
                })

                build_success = await self._run_build(env)
                if not build_success:
                    await self._broadcast('flash_complete', {
                        'success': False,
                        'message': 'Build failed'
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

    async def _run_build(self, env: str) -> bool:
        """Run PlatformIO build"""
        try:
            cmd = ['pio', 'run', '-e', env]
            logger.info(f"Running build: {' '.join(cmd)}")

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT
            )

            # Stream build output
            async for line in process.stdout:
                text = line.decode('utf-8', errors='replace').strip()
                if text:
                    logger.debug(f"Build: {text}")
                    await self._broadcast('flash_progress', {
                        'percent': 25,
                        'stage': 'building',
                        'message': text[:100]  # Truncate long lines
                    })

            await process.wait()
            success = process.returncode == 0

            if success:
                logger.info("Build successful")
            else:
                logger.error(f"Build failed with code {process.returncode}")

            return success

        except Exception as e:
            logger.error(f"Build error: {e}")
            return False

    async def _run_flash(self, port: str, env: str) -> bool:
        """Run PlatformIO upload"""
        try:
            cmd = ['pio', 'run', '-e', env, '-t', 'upload', '--upload-port', port]
            logger.info(f"Running flash: {' '.join(cmd)}")

            process = await asyncio.create_subprocess_exec(
                *cmd,
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
        }
