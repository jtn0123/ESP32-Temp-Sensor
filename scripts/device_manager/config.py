"""Configuration for Device Manager"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class ManagerConfig:
    """Configuration for the Device Manager server"""

    # Server
    host: str = "0.0.0.0"
    port: int = 8080

    # Serial
    default_baud: int = 115200
    serial_timeout: float = 1.0

    # MQTT (port matches mosquitto_test.conf)
    mqtt_broker_port: int = 18884
    mqtt_broker_enabled: bool = True

    # Simulator
    simulator_enabled: bool = True
    simulator_interval_sec: int = 60
    mqtt_sub_base: str = "homeassistant/sensor/outside"

    # Flash
    platformio_env_dev: str = "feather_esp32s2_display_only_dev"
    platformio_env_prod: str = "feather_esp32s2_display_only"
    firmware_dir: str = ".pio/build"

    # Screenshot
    display_width: int = 250
    display_height: int = 122

    @classmethod
    def from_args(cls, args) -> 'ManagerConfig':
        """Create config from command line arguments"""
        config = cls()
        if hasattr(args, 'port'):
            config.port = args.port
        if hasattr(args, 'no_broker') and args.no_broker:
            config.mqtt_broker_enabled = False
        return config
