"""MQTT simulator for generating fake Home Assistant data"""
import asyncio
import logging
import math
import random
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


class MqttSimulator:
    """Generates fake Home Assistant-style MQTT data for testing"""

    def __init__(self, broker, config=None):
        self.broker = broker
        self.config = config
        self.running = False
        self.task: Optional[asyncio.Task] = None

        # Simulation parameters
        self.temp_min = 40  # °F
        self.temp_max = 85  # °F
        self.temp_period_hours = 24  # Full sine wave cycle
        self.update_interval_sec = 60  # Update every minute

        self.weather_options = [
            "sunny",
            "partlycloudy",
            "cloudy",
            "rainy",
            "snowy",
            "fog",
            "windy"
        ]

        # Current weather state (changes slowly)
        self.current_weather = "sunny"
        self.weather_change_counter = 0
        self.weather_change_interval = 10  # Change weather every 10 updates

        # MQTT topic base
        self.mqtt_sub_base = config.mqtt_sub_base if config else "homeassistant/sensor/outside"

    async def start(self):
        """Start publishing simulated data"""
        if self.running:
            logger.warning("MQTT simulator already running")
            return

        logger.info("Starting MQTT simulator")
        self.running = True
        self.task = asyncio.create_task(self._simulation_loop())

    async def stop(self):
        """Stop simulation"""
        if not self.running:
            return

        logger.info("Stopping MQTT simulator")
        self.running = False

        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
            self.task = None

    async def _simulation_loop(self):
        """Main simulation loop"""
        logger.info("MQTT simulator loop started")

        while self.running:
            try:
                # Generate and publish data
                await self._publish_cycle()

                # Wait for next update
                await asyncio.sleep(self.update_interval_sec)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in simulation loop: {e}")
                await asyncio.sleep(5)  # Brief pause on error

        logger.info("MQTT simulator loop stopped")

    async def _publish_cycle(self):
        """Publish one cycle of simulated data"""
        # Generate temperature (sine wave based on time of day)
        temp_f = self._generate_temperature()

        # Generate humidity (inversely related to temperature + noise)
        humidity = self._generate_humidity(temp_f)

        # Generate weather condition
        weather = self._generate_weather()

        # Generate wind speed
        wind_mph = self._generate_wind_speed()

        # Generate pressure
        pressure_mb = self._generate_pressure()

        # Publish all values
        self.broker.publish(f"{self.mqtt_sub_base}/temp_f", f"{temp_f:.1f}", retain=True)
        self.broker.publish(f"{self.mqtt_sub_base}/temp", f"{self._f_to_c(temp_f):.1f}", retain=True)
        self.broker.publish(f"{self.mqtt_sub_base}/humidity", f"{humidity}", retain=True)
        self.broker.publish(f"{self.mqtt_sub_base}/condition", weather, retain=True)
        self.broker.publish(f"{self.mqtt_sub_base}/wind_mph", f"{wind_mph:.1f}", retain=True)
        self.broker.publish(f"{self.mqtt_sub_base}/pressure_mb", f"{pressure_mb:.1f}", retain=True)

        logger.debug(
            f"Published simulated data: {temp_f:.1f}°F, {humidity}% RH, "
            f"{weather}, {wind_mph:.1f} mph, {pressure_mb:.1f} mb"
        )

    def _generate_temperature(self) -> float:
        """Generate temperature based on time of day (sine wave)"""
        # Get hour of day (0-23)
        now = datetime.now()
        hour = now.hour + now.minute / 60.0

        # Create sine wave that peaks at 3pm (15:00) and bottoms at 3am (3:00)
        # Shift sine wave so peak is at hour 15
        phase_shift = 15 - 6  # 6 is when sin(x) peaks in a 0-24 cycle
        normalized_hour = (hour - phase_shift) / 24.0 * 2 * math.pi

        # Calculate temperature using sine wave
        temp_range = self.temp_max - self.temp_min
        temp_mid = (self.temp_max + self.temp_min) / 2
        temp = temp_mid + (temp_range / 2) * math.sin(normalized_hour)

        # Add small random noise (±2°F)
        temp += random.uniform(-2, 2)

        return round(temp, 1)

    def _generate_humidity(self, temp_f: float) -> int:
        """Generate humidity (inversely related to temperature with noise)"""
        # Base humidity inversely proportional to temperature
        # Hot = dry, cold = humid
        temp_normalized = (temp_f - self.temp_min) / (self.temp_max - self.temp_min)
        base_humidity = 80 - (temp_normalized * 50)  # 80% at min temp, 30% at max temp

        # Add random variation
        humidity = base_humidity + random.uniform(-10, 10)

        # Clamp to valid range
        return max(20, min(95, int(humidity)))

    def _generate_weather(self) -> str:
        """Generate weather condition (changes slowly)"""
        self.weather_change_counter += 1

        if self.weather_change_counter >= self.weather_change_interval:
            self.weather_change_counter = 0

            # Weighted random selection (sunny more common)
            weights = [30, 20, 15, 10, 5, 5, 15]  # Favor sunny and partly cloudy
            self.current_weather = random.choices(self.weather_options, weights=weights)[0]

        return self.current_weather

    def _generate_wind_speed(self) -> float:
        """Generate wind speed (random with occasional gusts)"""
        # Base wind speed
        base_wind = random.uniform(0, 8)

        # Occasional gusts
        if random.random() < 0.1:  # 10% chance of gust
            base_wind += random.uniform(5, 15)

        return round(base_wind, 1)

    def _generate_pressure(self) -> float:
        """Generate barometric pressure"""
        # Standard pressure with small variations
        base_pressure = 1013.25  # Standard atmospheric pressure in mb

        # Add slow-moving pressure changes
        hour = datetime.now().hour
        pressure_wave = 5 * math.sin(hour / 24.0 * 2 * math.pi)

        # Add small random noise
        noise = random.uniform(-2, 2)

        return round(base_pressure + pressure_wave + noise, 1)

    @staticmethod
    def _f_to_c(temp_f: float) -> float:
        """Convert Fahrenheit to Celsius"""
        return (temp_f - 32) * 5 / 9

    def set_update_interval(self, seconds: int):
        """Change the update interval"""
        self.update_interval_sec = max(1, seconds)
        logger.info(f"MQTT simulator update interval set to {seconds}s")

    def set_weather(self, weather: str):
        """Manually set the weather condition"""
        if weather in self.weather_options:
            self.current_weather = weather
            logger.info(f"Weather manually set to: {weather}")
        else:
            logger.warning(f"Invalid weather condition: {weather}")

    def get_status(self) -> dict:
        """Get simulator status"""
        return {
            'running': self.running,
            'update_interval': self.update_interval_sec,
            'current_weather': self.current_weather,
            'mqtt_base': self.mqtt_sub_base
        }
