"""Exercise the bridge against the installed WebSocket implementation."""

import asyncio
import json
from unittest.mock import Mock

import pytest
import websockets

from scripts.mqtt_sim_bridge import MQTTWebSocketBridge


@pytest.mark.asyncio
async def test_websocket_client_can_publish_and_receive():
    bridge = MQTTWebSocketBridge("127.0.0.1", 1883, 0)
    bridge.mqtt_client = Mock()
    published = asyncio.Event()
    bridge.mqtt_client.publish.side_effect = lambda *args, **kwargs: published.set()
    async with websockets.serve(bridge.handle_ws_client, "127.0.0.1", 0) as server:
        port = server.sockets[0].getsockname()[1]
        async with websockets.connect(f"ws://127.0.0.1:{port}") as client:
            await client.send(
                json.dumps({"type": "publish", "topic": "test/temp", "payload": "21"})
            )
            await asyncio.wait_for(published.wait(), timeout=2)
            bridge.mqtt_client.publish.assert_called_once_with(
                "test/temp", "21", retain=False, qos=0
            )
            await bridge.broadcast_to_ws("reply")
            assert await asyncio.wait_for(client.recv(), timeout=2) == "reply"
    assert not bridge.ws_clients
