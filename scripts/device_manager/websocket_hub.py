"""WebSocket Hub for broadcasting messages to all connected clients"""
import json
import asyncio
from typing import Set, Dict, Any
from fastapi import WebSocket
import logging

logger = logging.getLogger(__name__)


class WebSocketHub:
    """Manages WebSocket connections and broadcasts messages"""

    def __init__(self):
        self.clients: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket):
        """Accept a new WebSocket connection"""
        await websocket.accept()
        async with self._lock:
            self.clients.add(websocket)
        logger.info(f"WebSocket client connected. Total clients: {len(self.clients)}")

    async def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection"""
        async with self._lock:
            self.clients.discard(websocket)
        logger.info(f"WebSocket client disconnected. Total clients: {len(self.clients)}")

    async def broadcast(self, message: Dict[str, Any]):
        """Send message to all connected clients"""
        if not self.clients:
            return

        data = json.dumps(message)
        disconnected = set()

        async with self._lock:
            for client in self.clients:
                try:
                    await client.send_text(data)
                except Exception as e:
                    logger.warning(f"Error broadcasting to client: {e}")
                    disconnected.add(client)

            # Remove disconnected clients
            for client in disconnected:
                self.clients.discard(client)

    async def handle_message(self, websocket: WebSocket, message: Dict[str, Any]):
        """Handle incoming message from client"""
        msg_type = message.get('type')
        logger.debug(f"Received message type: {msg_type}")

        # Route messages based on type
        # This will be expanded as we add more features
        return {'status': 'received', 'type': msg_type}
