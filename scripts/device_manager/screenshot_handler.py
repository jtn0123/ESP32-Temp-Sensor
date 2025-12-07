"""Screenshot handler for ESP32 display capture"""
import base64
import logging
from typing import Optional, Dict, Any
from io import BytesIO
from PIL import Image
import asyncio

logger = logging.getLogger(__name__)


class ScreenshotHandler:
    """Handles screenshot requests and conversions from ESP32 devices"""

    def __init__(self, mqtt_broker=None, websocket_hub=None, config=None):
        self.mqtt_broker = mqtt_broker
        self.hub = websocket_hub
        self.config = config

        # Latest screenshot data
        self.latest_screenshot: Optional[bytes] = None
        self.latest_metadata: Optional[Dict[str, Any]] = None

        # Display dimensions
        self.display_width = config.display_width if config else 250
        self.display_height = config.display_height if config else 122

        # Register MQTT callback if broker is available
        if self.mqtt_broker:
            self.mqtt_broker.add_message_callback(self._on_mqtt_message)

    def _on_mqtt_message(self, message):
        """Handle incoming MQTT messages"""
        topic = message.topic

        # Check if it's a screenshot metadata message
        if '/debug/screenshot/meta' in topic:
            self._handle_screenshot_meta(message)

        # Check if it's screenshot data
        elif '/debug/screenshot/data' in topic:
            self._handle_screenshot_data(message)

    def _handle_screenshot_meta(self, message):
        """Handle screenshot metadata message"""
        try:
            import json
            metadata = json.loads(message.payload.decode('utf-8'))
            self.latest_metadata = metadata
            logger.info(f"Received screenshot metadata: {metadata}")

            # Broadcast metadata
            if self.hub:
                asyncio.create_task(self.hub.broadcast({
                    'type': 'screenshot_meta',
                    'metadata': metadata
                }))

        except Exception as e:
            logger.error(f"Error parsing screenshot metadata: {e}")

    def _handle_screenshot_data(self, message):
        """Handle screenshot data message"""
        try:
            # Decode base64 data
            data_b64 = message.payload.decode('utf-8')
            data_bytes = base64.b64decode(data_b64)

            logger.info(f"Received screenshot data: {len(data_bytes)} bytes")

            # Use metadata if available, otherwise use defaults
            width = self.display_width
            height = self.display_height

            if self.latest_metadata:
                width = self.latest_metadata.get('width', width)
                height = self.latest_metadata.get('height', height)

            # Convert to PNG
            png_data = self._convert_1bit_to_png(data_bytes, width, height)

            if png_data:
                self.latest_screenshot = png_data

                # Convert to base64 for transmission
                png_b64 = base64.b64encode(png_data).decode('utf-8')

                # Broadcast screenshot
                if self.hub:
                    asyncio.create_task(self.hub.broadcast({
                        'type': 'screenshot',
                        'data': png_b64,
                        'width': width,
                        'height': height,
                        'format': 'png'
                    }))

                logger.info(f"Screenshot converted and broadcasted: {width}x{height}")

        except Exception as e:
            logger.error(f"Error handling screenshot data: {e}")

    def _convert_1bit_to_png(self, data: bytes, width: int, height: int) -> Optional[bytes]:
        """
        Convert 1-bit packed display buffer to PNG.

        The ESP32 sends display data as 1 bit per pixel, packed into bytes.
        Each byte contains 8 pixels, MSB first.
        Black pixels = 1, White pixels = 0 (typical for e-ink displays)

        Args:
            data: Raw 1-bit packed data
            width: Display width in pixels
            height: Display height in pixels

        Returns:
            PNG image as bytes
        """
        try:
            # Calculate expected data size
            expected_bytes = (width * height + 7) // 8  # Round up to nearest byte

            if len(data) < expected_bytes:
                logger.warning(
                    f"Insufficient data: got {len(data)} bytes, "
                    f"expected {expected_bytes} for {width}x{height}"
                )
                return None

            # Create image in mode '1' (1-bit pixels, black and white)
            img = Image.new('1', (width, height), 1)  # Start with white

            # Unpack bits and set pixels
            bit_index = 0
            for y in range(height):
                for x in range(width):
                    # Calculate byte and bit position
                    byte_index = bit_index // 8
                    bit_position = 7 - (bit_index % 8)  # MSB first

                    if byte_index < len(data):
                        # Extract bit
                        byte_val = data[byte_index]
                        pixel_val = (byte_val >> bit_position) & 1

                        # Set pixel (1 = black, 0 = white for e-ink)
                        img.putpixel((x, y), pixel_val)

                    bit_index += 1

            # Convert to RGB for better compatibility
            img_rgb = img.convert('RGB')

            # Save to bytes
            output = BytesIO()
            img_rgb.save(output, format='PNG')
            png_bytes = output.getvalue()

            logger.debug(f"Converted {width}x{height} 1-bit image to PNG ({len(png_bytes)} bytes)")
            return png_bytes

        except Exception as e:
            logger.error(f"Error converting 1-bit to PNG: {e}")
            return None

    def request_screenshot(self, device_id: str = "office"):
        """Request a screenshot from the ESP32 device"""
        if not self.mqtt_broker:
            logger.warning("MQTT broker not available")
            return False

        try:
            # Publish screenshot request command
            topic = f"espsensor/{device_id}/cmd/screenshot"
            self.mqtt_broker.publish(topic, "capture", retain=False)

            logger.info(f"Screenshot requested for device: {device_id}")
            return True

        except Exception as e:
            logger.error(f"Error requesting screenshot: {e}")
            return False

    def get_latest_screenshot(self) -> Optional[Dict[str, Any]]:
        """Get the latest screenshot as base64 PNG"""
        if not self.latest_screenshot:
            return None

        return {
            'data': base64.b64encode(self.latest_screenshot).decode('utf-8'),
            'width': self.latest_metadata.get('width', self.display_width) if self.latest_metadata else self.display_width,
            'height': self.latest_metadata.get('height', self.display_height) if self.latest_metadata else self.display_height,
            'format': 'png',
            'metadata': self.latest_metadata
        }

    def generate_test_screenshot(self) -> bytes:
        """Generate a test screenshot for development/testing"""
        try:
            # Create a test image
            img = Image.new('RGB', (self.display_width, self.display_height), 'white')

            # Draw some test patterns
            from PIL import ImageDraw, ImageFont

            draw = ImageDraw.Draw(img)

            # Draw border
            draw.rectangle(
                [(0, 0), (self.display_width - 1, self.display_height - 1)],
                outline='black',
                width=2
            )

            # Draw text
            try:
                # Try to use a default font
                font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 20)
            except:
                font = ImageFont.load_default()

            draw.text((10, 10), "ESP32 Test Display", fill='black', font=font)
            draw.text((10, 40), "Temperature: 72°F", fill='black', font=font)
            draw.text((10, 70), "Humidity: 45%", fill='black', font=font)

            # Convert to PNG bytes
            output = BytesIO()
            img.save(output, format='PNG')
            return output.getvalue()

        except Exception as e:
            logger.error(f"Error generating test screenshot: {e}")
            return None
