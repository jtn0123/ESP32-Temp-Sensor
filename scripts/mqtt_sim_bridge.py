#!/usr/bin/env python3
"""
WebSocket to MQTT bridge for web simulator.
Fallback when broker doesn't support WebSocket directly.
"""

import asyncio
import json
import sys
import argparse
import logging
from typing import Optional

try:
    import websockets
except ImportError:
    print("Error: websockets not installed. Install with: pip install websockets")
    sys.exit(1)

try:
    import paho.mqtt.client as mqtt
except ImportError:
    print("Error: paho-mqtt not installed. Install with: pip install paho-mqtt")
    sys.exit(1)


class MQTTWebSocketBridge:
    """Bridge between WebSocket clients and MQTT broker."""
    
    def __init__(self, mqtt_host: str, mqtt_port: int, ws_port: int,
                 mqtt_user: Optional[str] = None, mqtt_pass: Optional[str] = None):
        self.mqtt_host = mqtt_host
        self.mqtt_port = mqtt_port
        self.ws_port = ws_port
        self.mqtt_user = mqtt_user
        self.mqtt_pass = mqtt_pass
        self.mqtt_client = None
        self.ws_clients = set()
        self.logger = logging.getLogger(__name__)
    
    def setup_mqtt(self):
        """Setup MQTT client."""
        # Create MQTT client
        if hasattr(mqtt, "CallbackAPIVersion"):
            try:
                self.mqtt_client = mqtt.Client(
                    client_id="ws-bridge",
                    callback_api_version=mqtt.CallbackAPIVersion.VERSION1,
                    protocol=mqtt.MQTTv311
                )
            except TypeError:
                self.mqtt_client = mqtt.Client(client_id="ws-bridge", protocol=mqtt.MQTTv311)
        else:
            self.mqtt_client = mqtt.Client(client_id="ws-bridge", protocol=mqtt.MQTTv311)
        
        if self.mqtt_user:
            self.mqtt_client.username_pw_set(self.mqtt_user, self.mqtt_pass)
        
        def on_connect(client, userdata, flags, rc):
            if rc == 0:
                self.logger.info(f"Connected to MQTT broker {self.mqtt_host}:{self.mqtt_port}")
            else:
                self.logger.error(f"MQTT connection failed: {rc}")
        
        def on_message(client, userdata, msg):
            # Forward MQTT messages to WebSocket clients
            message = {
                "type": "mqtt_message",
                "topic": msg.topic,
                "payload": msg.payload.decode('utf-8', 'ignore'),
                "retain": msg.retain
            }
            asyncio.create_task(self.broadcast_to_ws(json.dumps(message)))
        
        self.mqtt_client.on_connect = on_connect
        self.mqtt_client.on_message = on_message
        
        # Connect to MQTT broker
        self.mqtt_client.connect(self.mqtt_host, self.mqtt_port, keepalive=60)
        self.mqtt_client.loop_start()
    
    async def broadcast_to_ws(self, message: str):
        """Broadcast message to all WebSocket clients."""
        if self.ws_clients:
            disconnected = set()
            for client in self.ws_clients:
                try:
                    await client.send(message)
                except:
                    disconnected.add(client)
            
            # Remove disconnected clients
            self.ws_clients -= disconnected
    
    async def handle_ws_client(self, websocket, path):
        """Handle WebSocket client connection."""
        self.ws_clients.add(websocket)
        client_id = id(websocket)
        self.logger.info(f"WebSocket client {client_id} connected")
        
        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    
                    if data.get("type") == "publish":
                        # Publish to MQTT
                        topic = data.get("topic")
                        payload = data.get("payload", "")
                        retain = data.get("retain", False)
                        qos = data.get("qos", 0)
                        
                        if topic:
                            self.mqtt_client.publish(topic, payload, retain=retain, qos=qos)
                            self.logger.debug(f"Published: {topic} = {payload}")
                    
                    elif data.get("type") == "subscribe":
                        # Subscribe to MQTT topic
                        topic = data.get("topic")
                        if topic:
                            self.mqtt_client.subscribe(topic)
                            self.logger.debug(f"Subscribed to: {topic}")
                    
                    elif data.get("type") == "unsubscribe":
                        # Unsubscribe from MQTT topic
                        topic = data.get("topic")
                        if topic:
                            self.mqtt_client.unsubscribe(topic)
                            self.logger.debug(f"Unsubscribed from: {topic}")
                    
                except json.JSONDecodeError:
                    self.logger.error(f"Invalid JSON from client {client_id}")
                except Exception as e:
                    self.logger.error(f"Error handling message from {client_id}: {e}")
        
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self.ws_clients.remove(websocket)
            self.logger.info(f"WebSocket client {client_id} disconnected")
    
    async def start_ws_server(self):
        """Start WebSocket server."""
        self.logger.info(f"Starting WebSocket server on port {self.ws_port}")
        async with websockets.serve(self.handle_ws_client, "0.0.0.0", self.ws_port):
            await asyncio.Future()  # Run forever
    
    def run(self):
        """Run the bridge."""
        self.setup_mqtt()
        asyncio.run(self.start_ws_server())


def main():
    parser = argparse.ArgumentParser(description="WebSocket to MQTT bridge")
    parser.add_argument("--mqtt-host", default="127.0.0.1", help="MQTT broker host")
    parser.add_argument("--mqtt-port", type=int, default=18884, help="MQTT broker port")
    parser.add_argument("--mqtt-user", help="MQTT username")
    parser.add_argument("--mqtt-pass", help="MQTT password")
    parser.add_argument("--ws-port", type=int, default=9002, help="WebSocket server port")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    # Setup logging
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create and run bridge
    bridge = MQTTWebSocketBridge(
        mqtt_host=args.mqtt_host,
        mqtt_port=args.mqtt_port,
        ws_port=args.ws_port,
        mqtt_user=args.mqtt_user,
        mqtt_pass=args.mqtt_pass
    )
    
    print(f"Starting WebSocket to MQTT bridge...")
    print(f"  MQTT: {args.mqtt_host}:{args.mqtt_port}")
    print(f"  WebSocket: 0.0.0.0:{args.ws_port}")
    print(f"Press Ctrl+C to stop")
    
    try:
        bridge.run()
    except KeyboardInterrupt:
        print("\nShutting down...")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())