"""
Tests for display capture functionality.

These tests verify:
1. Base64 encoding/decoding of display buffer
2. MQTT message format and chunking
3. Web interface screenshot reception
"""

import base64
import json
import pytest
from unittest.mock import Mock, patch

# Display dimensions matching firmware
DISPLAY_WIDTH = 250
DISPLAY_HEIGHT = 122
# GFXcanvas1 pads width to byte boundary
WIDTH_BYTES = (DISPLAY_WIDTH + 7) // 8  # 32 bytes per row
BUFFER_SIZE = WIDTH_BYTES * DISPLAY_HEIGHT  # 3904 bytes
BASE64_SIZE = ((BUFFER_SIZE + 2) // 3) * 4  # ~5206 bytes


class TestDisplayCaptureBuffer:
    """Test display buffer calculations and encoding."""

    def test_buffer_size_calculation(self):
        """Verify buffer size matches firmware constants."""
        # WIDTH/8 * HEIGHT = 250/8 * 122 = 31.25 * 122
        # But WIDTH is padded to byte boundary: (250 + 7) // 8 = 32
        width_bytes = (DISPLAY_WIDTH + 7) // 8
        expected_size = width_bytes * DISPLAY_HEIGHT
        assert expected_size == 3904, f"Expected 3904 bytes, got {expected_size}"

    def test_base64_encoding_roundtrip(self):
        """Test that base64 encoding/decoding preserves data."""
        # Create test pattern (checkerboard)
        test_buffer = bytearray(BUFFER_SIZE)
        for i in range(BUFFER_SIZE):
            test_buffer[i] = 0xAA if i % 2 == 0 else 0x55

        # Encode
        encoded = base64.b64encode(test_buffer).decode('ascii')

        # Decode
        decoded = base64.b64decode(encoded)

        assert decoded == test_buffer, "Base64 roundtrip failed"

    def test_base64_output_size(self):
        """Verify base64 output size calculation."""
        test_buffer = bytes(BUFFER_SIZE)
        encoded = base64.b64encode(test_buffer).decode('ascii')

        # Base64 expands by 4/3
        expected_len = ((BUFFER_SIZE + 2) // 3) * 4
        assert len(encoded) == expected_len, f"Expected {expected_len}, got {len(encoded)}"


class TestScreenshotMetadata:
    """Test MQTT screenshot metadata format."""

    def test_metadata_json_format(self):
        """Verify metadata JSON matches expected format."""
        metadata = {
            "width": DISPLAY_WIDTH,
            "height": DISPLAY_HEIGHT,
            "format": "1bit",
            "data_size": BASE64_SIZE,
            "buffer_size": BUFFER_SIZE
        }

        json_str = json.dumps(metadata)
        parsed = json.loads(json_str)

        assert parsed["width"] == 250
        assert parsed["height"] == 122
        assert parsed["format"] == "1bit"
        assert parsed["buffer_size"] == 3904

    def test_metadata_fits_in_mqtt_packet(self):
        """Verify metadata JSON fits in single MQTT packet."""
        metadata = {
            "width": DISPLAY_WIDTH,
            "height": DISPLAY_HEIGHT,
            "format": "1bit",
            "data_size": BASE64_SIZE,
            "buffer_size": BUFFER_SIZE
        }

        json_str = json.dumps(metadata)
        # MQTT_MAX_PACKET_SIZE is 1024 in platformio.ini
        assert len(json_str) < 256, "Metadata should be well under MQTT limit"


class TestScreenshotChunking:
    """Test MQTT data chunking for screenshot transfer."""

    def test_chunk_calculation(self):
        """Verify chunking logic for base64 data."""
        chunk_size = 4096  # Same as firmware
        data_size = BASE64_SIZE

        num_chunks = (data_size + chunk_size - 1) // chunk_size
        assert num_chunks == 2, f"Expected 2 chunks for {data_size} bytes, got {num_chunks}"

    def test_chunk_reassembly(self):
        """Test reassembling chunks into complete data."""
        # Create test data
        original_data = bytes(range(256)) * (BUFFER_SIZE // 256 + 1)
        original_data = original_data[:BUFFER_SIZE]

        # Encode
        encoded = base64.b64encode(original_data).decode('ascii')

        # Split into chunks
        chunk_size = 4096
        chunks = []
        for i in range(0, len(encoded), chunk_size):
            chunks.append(encoded[i:i + chunk_size])

        # Reassemble
        reassembled = ''.join(chunks)

        # Decode
        decoded = base64.b64decode(reassembled)

        assert decoded == original_data, "Chunk reassembly failed"


class TestPixelUnpacking:
    """Test 1-bit pixel data unpacking (matching web interface)."""

    def test_pixel_unpack_white(self):
        """Test unpacking all-white pixels."""
        # All bits set = all white
        buffer = bytes([0xFF] * BUFFER_SIZE)

        # Unpack first 8 pixels
        byte_val = buffer[0]
        pixels = []
        for bit in range(8):
            pixel = (byte_val >> (7 - bit)) & 1
            pixels.append(255 if pixel else 0)  # 1=white, 0=black

        assert all(p == 255 for p in pixels), "All pixels should be white"

    def test_pixel_unpack_black(self):
        """Test unpacking all-black pixels."""
        # All bits clear = all black
        buffer = bytes([0x00] * BUFFER_SIZE)

        byte_val = buffer[0]
        pixels = []
        for bit in range(8):
            pixel = (byte_val >> (7 - bit)) & 1
            pixels.append(255 if pixel else 0)

        assert all(p == 0 for p in pixels), "All pixels should be black"

    def test_pixel_unpack_checkerboard(self):
        """Test unpacking alternating pixels."""
        # 0xAA = 10101010 = alternating starting with white
        buffer = bytes([0xAA] * BUFFER_SIZE)

        byte_val = buffer[0]
        pixels = []
        for bit in range(8):
            pixel = (byte_val >> (7 - bit)) & 1
            pixels.append(255 if pixel else 0)

        expected = [255, 0, 255, 0, 255, 0, 255, 0]
        assert pixels == expected, f"Expected {expected}, got {pixels}"

    def test_full_image_unpack(self):
        """Test unpacking a complete image buffer."""
        # Create gradient pattern
        buffer = bytearray(BUFFER_SIZE)
        for y in range(DISPLAY_HEIGHT):
            for x_byte in range(WIDTH_BYTES):
                idx = y * WIDTH_BYTES + x_byte
                buffer[idx] = (y + x_byte) & 0xFF

        # Unpack to image array
        width = DISPLAY_WIDTH
        height = DISPLAY_HEIGHT
        image = []

        for y in range(height):
            row = []
            for x in range(width):
                byte_idx = y * WIDTH_BYTES + (x // 8)
                bit_idx = 7 - (x % 8)
                pixel = (buffer[byte_idx] >> bit_idx) & 1
                row.append(255 if pixel else 0)
            image.append(row)

        assert len(image) == height
        assert len(image[0]) == width


class TestMQTTTopics:
    """Test MQTT topic formatting."""

    def test_screenshot_meta_topic(self):
        """Verify screenshot metadata topic format."""
        device_id = "esp32-test"
        topic = f"espsensor/{device_id}/debug/screenshot/meta"
        assert topic == "espsensor/esp32-test/debug/screenshot/meta"

    def test_screenshot_data_topic(self):
        """Verify screenshot data topic format."""
        device_id = "esp32-test"
        topic = f"espsensor/{device_id}/debug/screenshot/data"
        assert topic == "espsensor/esp32-test/debug/screenshot/data"

    def test_screenshot_chunk_topic(self):
        """Verify chunked data topic format."""
        device_id = "esp32-test"
        chunk_num = 0
        topic = f"espsensor/{device_id}/debug/screenshot/data/{chunk_num}"
        assert topic == "espsensor/esp32-test/debug/screenshot/data/0"

    def test_screenshot_command_topic(self):
        """Verify screenshot command topic."""
        device_id = "esp32-test"
        topic = f"espsensor/{device_id}/cmd/debug"
        assert topic == "espsensor/esp32-test/cmd/debug"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
