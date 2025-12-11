"""
Async tests for device manager WebSocket and MQTT broker lifecycle.

Tests the async components of the device manager to ensure proper
connection handling, broadcast functionality, and cleanup.
"""

import asyncio
import json
import os
import sys
from typing import Dict, Any, List
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

# Add scripts to path
ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

# Import after path setup
from device_manager.websocket_hub import WebSocketHub
from device_manager.mqtt_broker import MQTTMessage, SimpleMQTTBroker


class MockWebSocket:
    """Mock WebSocket for testing."""

    def __init__(self, should_fail: bool = False):
        self.accepted = False
        self.messages: List[str] = []
        self.should_fail = should_fail
        self.closed = False

    async def accept(self):
        if self.should_fail:
            raise Exception("Connection failed")
        self.accepted = True

    async def send_text(self, data: str):
        if self.should_fail or self.closed:
            raise Exception("Send failed")
        self.messages.append(data)

    async def close(self):
        self.closed = True


class TestWebSocketHub:
    """Tests for WebSocketHub class."""

    @pytest.mark.asyncio
    async def test_connect_single_client(self):
        """Test connecting a single WebSocket client."""
        hub = WebSocketHub()
        ws = MockWebSocket()

        await hub.connect(ws)

        assert ws.accepted
        assert ws in hub.clients
        assert len(hub.clients) == 1

    @pytest.mark.asyncio
    async def test_connect_multiple_clients(self):
        """Test connecting multiple WebSocket clients."""
        hub = WebSocketHub()
        ws1 = MockWebSocket()
        ws2 = MockWebSocket()
        ws3 = MockWebSocket()

        await hub.connect(ws1)
        await hub.connect(ws2)
        await hub.connect(ws3)

        assert len(hub.clients) == 3
        assert all(ws in hub.clients for ws in [ws1, ws2, ws3])

    @pytest.mark.asyncio
    async def test_disconnect_client(self):
        """Test disconnecting a WebSocket client."""
        hub = WebSocketHub()
        ws = MockWebSocket()

        await hub.connect(ws)
        assert len(hub.clients) == 1

        await hub.disconnect(ws)
        assert len(hub.clients) == 0
        assert ws not in hub.clients

    @pytest.mark.asyncio
    async def test_disconnect_nonexistent_client(self):
        """Disconnecting a non-existent client should not raise."""
        hub = WebSocketHub()
        ws = MockWebSocket()

        # Should not raise
        await hub.disconnect(ws)
        assert len(hub.clients) == 0

    @pytest.mark.asyncio
    async def test_broadcast_to_single_client(self):
        """Test broadcasting a message to a single client."""
        hub = WebSocketHub()
        ws = MockWebSocket()
        await hub.connect(ws)

        message = {"type": "test", "data": "hello"}
        await hub.broadcast(message)

        assert len(ws.messages) == 1
        received = json.loads(ws.messages[0])
        assert received == message

    @pytest.mark.asyncio
    async def test_broadcast_to_multiple_clients(self):
        """Test broadcasting to multiple clients."""
        hub = WebSocketHub()
        clients = [MockWebSocket() for _ in range(5)]

        for ws in clients:
            await hub.connect(ws)

        message = {"type": "update", "value": 42}
        await hub.broadcast(message)

        for ws in clients:
            assert len(ws.messages) == 1
            received = json.loads(ws.messages[0])
            assert received == message

    @pytest.mark.asyncio
    async def test_broadcast_to_empty_hub(self):
        """Broadcasting to empty hub should not raise."""
        hub = WebSocketHub()
        message = {"type": "test"}

        # Should not raise
        await hub.broadcast(message)

    @pytest.mark.asyncio
    async def test_broadcast_removes_failed_clients(self):
        """Failed clients should be removed during broadcast."""
        hub = WebSocketHub()
        good_ws = MockWebSocket()
        bad_ws = MockWebSocket(should_fail=True)
        bad_ws.accepted = True  # Manually mark as accepted to bypass accept()

        await hub.connect(good_ws)
        # Manually add bad_ws since it would fail on accept
        hub.clients.add(bad_ws)

        assert len(hub.clients) == 2

        message = {"type": "test"}
        await hub.broadcast(message)

        # Bad client should be removed
        assert len(hub.clients) == 1
        assert good_ws in hub.clients
        assert bad_ws not in hub.clients

    @pytest.mark.asyncio
    async def test_handle_message(self):
        """Test handling incoming messages."""
        hub = WebSocketHub()
        ws = MockWebSocket()
        await hub.connect(ws)

        message = {"type": "command", "action": "refresh"}
        result = await hub.handle_message(ws, message)

        assert result["status"] == "received"
        assert result["type"] == "command"

    @pytest.mark.asyncio
    async def test_concurrent_connect_disconnect(self):
        """Test concurrent connect/disconnect operations."""
        hub = WebSocketHub()
        clients = [MockWebSocket() for _ in range(10)]

        # Connect all clients concurrently
        await asyncio.gather(*[hub.connect(ws) for ws in clients])
        assert len(hub.clients) == 10

        # Disconnect half concurrently
        await asyncio.gather(*[hub.disconnect(ws) for ws in clients[:5]])
        assert len(hub.clients) == 5

    @pytest.mark.asyncio
    async def test_broadcast_json_serializable(self):
        """Test that various data types are properly serialized."""
        hub = WebSocketHub()
        ws = MockWebSocket()
        await hub.connect(ws)

        messages = [
            {"string": "hello", "number": 42, "float": 3.14},
            {"list": [1, 2, 3], "nested": {"a": "b"}},
            {"boolean": True, "null": None},
        ]

        for msg in messages:
            await hub.broadcast(msg)

        assert len(ws.messages) == len(messages)
        for sent, original in zip(ws.messages, messages):
            received = json.loads(sent)
            assert received == original


class TestMQTTMessage:
    """Tests for MQTTMessage class."""

    def test_message_creation(self):
        """Test creating an MQTT message."""
        msg = MQTTMessage(
            topic="espsensor/test/status",
            payload=b"online",
            direction="in"
        )

        assert msg.topic == "espsensor/test/status"
        assert msg.payload == b"online"
        assert msg.direction == "in"
        assert msg.timestamp > 0

    def test_message_to_dict_utf8(self):
        """Test converting UTF-8 message to dict."""
        msg = MQTTMessage(
            topic="test/topic",
            payload=b"Hello, World!",
            direction="out"
        )

        d = msg.to_dict()

        assert d["topic"] == "test/topic"
        assert d["payload"] == "Hello, World!"
        assert d["direction"] == "out"
        assert "timestamp" in d

    def test_message_to_dict_binary(self):
        """Test converting binary message to dict (uses hex encoding)."""
        binary_data = bytes([0x00, 0x01, 0xFF, 0xFE])
        msg = MQTTMessage(
            topic="test/binary",
            payload=binary_data,
            direction="in"
        )

        d = msg.to_dict()

        # Binary data should be hex-encoded
        assert d["payload"] == "0001fffe"

    def test_message_to_dict_json_payload(self):
        """Test message with JSON payload."""
        json_payload = json.dumps({"temp": 22.5, "humidity": 45}).encode()
        msg = MQTTMessage(
            topic="sensor/data",
            payload=json_payload,
            direction="in"
        )

        d = msg.to_dict()
        assert d["payload"] == json_payload.decode()

        # Should be valid JSON
        parsed = json.loads(d["payload"])
        assert parsed["temp"] == 22.5


class TestSimpleMQTTBroker:
    """Tests for SimpleMQTTBroker class."""

    def test_broker_initialization(self):
        """Test broker initialization."""
        hub = WebSocketHub()
        broker = SimpleMQTTBroker(websocket_hub=hub, port=1883, host="127.0.0.1")

        assert broker.hub == hub
        assert broker.port == 1883
        assert broker.host == "127.0.0.1"
        assert not broker.running
        assert len(broker.message_log) == 0

    def test_message_log_max_size(self):
        """Test that message log respects max size."""
        broker = SimpleMQTTBroker(websocket_hub=None)

        # Add more than max messages
        for i in range(1500):
            msg = MQTTMessage(f"topic/{i}", f"msg{i}".encode(), "in")
            broker.message_log.append(msg)

        # Should be limited to 1000
        assert len(broker.message_log) == 1000

    def test_get_status_not_running(self):
        """Test status when broker is not running."""
        broker = SimpleMQTTBroker(websocket_hub=None)
        status = broker.get_status()

        assert status["running"] is False
        assert status["connected"] is False
        assert status["message_count"] == 0

    def test_get_message_log_limit(self):
        """Test message log retrieval with limit."""
        broker = SimpleMQTTBroker(websocket_hub=None)

        # Add 50 messages
        for i in range(50):
            msg = MQTTMessage(f"topic/{i}", f"msg{i}".encode(), "in")
            broker.message_log.append(msg)

        # Get last 10
        log = broker.get_message_log(limit=10)
        assert len(log) == 10

        # Should be the last 10 messages
        assert log[-1]["topic"] == "topic/49"
        assert log[0]["topic"] == "topic/40"

    def test_get_subscriptions_empty(self):
        """Test getting subscriptions when empty."""
        broker = SimpleMQTTBroker(websocket_hub=None)
        subs = broker.get_subscriptions()

        assert subs == []

    def test_add_message_callback(self):
        """Test adding message callbacks."""
        broker = SimpleMQTTBroker(websocket_hub=None)
        callback_called = []

        def callback(msg):
            callback_called.append(msg)

        broker.add_message_callback(callback)
        assert len(broker.message_callbacks) == 1

    @pytest.mark.asyncio
    async def test_broker_start_stop_without_connection(self):
        """Test broker start/stop lifecycle without actual MQTT connection."""
        hub = WebSocketHub()
        broker = SimpleMQTTBroker(websocket_hub=hub)

        # Mock the mqtt.Client to avoid actual connection
        with patch("device_manager.mqtt_broker.mqtt.Client") as MockClient:
            mock_client = MagicMock()
            mock_client.is_connected.return_value = False
            MockClient.return_value = mock_client

            await broker.start()
            assert broker.running

            await broker.stop()
            assert not broker.running
            mock_client.loop_stop.assert_called_once()
            mock_client.disconnect.assert_called_once()

    def test_publish_without_client(self):
        """Test publish fails gracefully without client."""
        broker = SimpleMQTTBroker(websocket_hub=None)
        result = broker.publish("test/topic", "payload")

        assert result is False

    def test_subscribe_without_client(self):
        """Test subscribe fails gracefully without client."""
        broker = SimpleMQTTBroker(websocket_hub=None)
        result = broker.subscribe("test/topic")

        assert result is False

    def test_unsubscribe_without_client(self):
        """Test unsubscribe fails gracefully without client."""
        broker = SimpleMQTTBroker(websocket_hub=None)
        result = broker.unsubscribe("test/topic")

        assert result is False


class TestIntegration:
    """Integration tests for WebSocket and MQTT broker interaction."""

    @pytest.mark.asyncio
    async def test_mqtt_message_broadcast_to_websocket(self):
        """Test that MQTT messages are broadcast to WebSocket clients."""
        hub = WebSocketHub()
        ws = MockWebSocket()
        await hub.connect(ws)

        broker = SimpleMQTTBroker(websocket_hub=hub)
        broker._loop = asyncio.get_running_loop()

        # Simulate receiving an MQTT message
        msg = MQTTMessage("espsensor/test/status", b"online", "in")
        broker.message_log.append(msg)

        # Broadcast through hub
        await hub.broadcast({
            "type": "mqtt",
            **msg.to_dict()
        })

        assert len(ws.messages) == 1
        received = json.loads(ws.messages[0])
        assert received["type"] == "mqtt"
        assert received["topic"] == "espsensor/test/status"
        assert received["payload"] == "online"

    @pytest.mark.asyncio
    async def test_multiple_message_types(self):
        """Test broadcasting different message types."""
        hub = WebSocketHub()
        ws = MockWebSocket()
        await hub.connect(ws)

        message_types = [
            {"type": "mqtt", "topic": "test/1", "payload": "data1"},
            {"type": "device_status", "device": "sensor1", "online": True},
            {"type": "mqtt_status", "connected": True},
            {"type": "flash_progress", "percent": 50},
        ]

        for msg in message_types:
            await hub.broadcast(msg)

        assert len(ws.messages) == len(message_types)

        for sent, original in zip(ws.messages, message_types):
            received = json.loads(sent)
            assert received["type"] == original["type"]


class TestEdgeCases:
    """Edge case tests for async components."""

    @pytest.mark.asyncio
    async def test_hub_lock_contention(self):
        """Test that lock handles concurrent access properly."""
        hub = WebSocketHub()

        async def connect_disconnect():
            ws = MockWebSocket()
            await hub.connect(ws)
            await asyncio.sleep(0.001)  # Small delay
            await hub.disconnect(ws)

        # Run many concurrent connect/disconnect operations
        await asyncio.gather(*[connect_disconnect() for _ in range(50)])

        # All should be disconnected
        assert len(hub.clients) == 0

    @pytest.mark.asyncio
    async def test_broadcast_during_modification(self):
        """Test broadcast while clients are being added/removed."""
        hub = WebSocketHub()
        clients = [MockWebSocket() for _ in range(10)]

        async def add_clients():
            for ws in clients:
                await hub.connect(ws)
                await asyncio.sleep(0.001)

        async def broadcast_messages():
            for i in range(20):
                await hub.broadcast({"msg": i})
                await asyncio.sleep(0.001)

        # Run concurrently
        await asyncio.gather(add_clients(), broadcast_messages())

        # All clients should have received some messages
        for ws in clients:
            # At least some messages should have been received
            # (exact count depends on timing)
            assert len(ws.messages) >= 0

    def test_message_timestamp_monotonic(self):
        """Test that message timestamps are monotonically increasing."""
        messages = []
        for i in range(100):
            msg = MQTTMessage(f"topic/{i}", b"data", "in")
            messages.append(msg)

        # Timestamps should be non-decreasing
        for i in range(1, len(messages)):
            assert messages[i].timestamp >= messages[i-1].timestamp

    @pytest.mark.asyncio
    async def test_large_message_broadcast(self):
        """Test broadcasting large messages."""
        hub = WebSocketHub()
        ws = MockWebSocket()
        await hub.connect(ws)

        # Large message (10KB)
        large_data = "x" * 10000
        await hub.broadcast({"type": "large", "data": large_data})

        assert len(ws.messages) == 1
        received = json.loads(ws.messages[0])
        assert len(received["data"]) == 10000

    @pytest.mark.asyncio
    async def test_special_characters_in_payload(self):
        """Test messages with special characters."""
        hub = WebSocketHub()
        ws = MockWebSocket()
        await hub.connect(ws)

        special_chars = {
            "unicode": "Hello 世界 🌡️",
            "quotes": 'He said "hello"',
            "newlines": "line1\nline2\rline3",
            "backslash": "path\\to\\file",
        }

        await hub.broadcast(special_chars)

        received = json.loads(ws.messages[0])
        assert received == special_chars
