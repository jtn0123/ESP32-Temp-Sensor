"""Embedded MQTT broker for ESP32 Device Manager"""
import asyncio
import logging
from typing import Dict, Any, List, Optional, Callable
from collections import deque
import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)

# Check paho-mqtt version for API compatibility
_PAHO_V2 = hasattr(mqtt, 'CallbackAPIVersion')


class MQTTMessage:
    """Represents an MQTT message"""
    def __init__(self, topic: str, payload: bytes, direction: str):
        self.topic = topic
        self.payload = payload
        self.direction = direction  # 'in' or 'out'
        self.timestamp = asyncio.get_event_loop().time()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        try:
            payload_str = self.payload.decode('utf-8')
        except UnicodeDecodeError:
            payload_str = self.payload.hex()

        return {
            'topic': self.topic,
            'payload': payload_str,
            'direction': self.direction,
            'timestamp': self.timestamp
        }


class SimpleMQTTBroker:
    """
    Simple MQTT broker using paho-mqtt client as a bridge.
    This creates a local broker by running mosquitto or using an external broker.
    For a true embedded broker, we'd use amqtt/hbmqtt, but that has compatibility issues.
    This approach is more reliable.
    """

    def __init__(self, websocket_hub=None, port: int = 1883, host: str = "127.0.0.1"):
        self.hub = websocket_hub
        self.port = port
        self.host = host
        self.client: Optional[mqtt.Client] = None
        self.running = False
        self.message_log: deque = deque(maxlen=1000)  # Keep last 1000 messages
        self.subscriptions: Dict[str, int] = {}  # topic -> qos
        self.message_callbacks: List[Callable] = []
        self._loop: Optional[asyncio.AbstractEventLoop] = None  # Store event loop reference
    
    def _schedule_async(self, coro):
        """Schedule an async coroutine from a sync callback (thread-safe)"""
        if self._loop and self.hub:
            try:
                asyncio.run_coroutine_threadsafe(coro, self._loop)
            except Exception as e:
                logger.debug(f"Could not schedule async task: {e}")

    async def start(self):
        """Start the MQTT client (connects to external broker or mosquitto)"""
        if self.running:
            logger.warning("MQTT broker already running")
            return

        # Store event loop reference for thread-safe async scheduling
        self._loop = asyncio.get_running_loop()

        try:
            # Create MQTT client (compatible with paho-mqtt v1 and v2)
            if _PAHO_V2:
                # paho-mqtt 2.0+ requires CallbackAPIVersion
                self.client = mqtt.Client(
                    callback_api_version=mqtt.CallbackAPIVersion.VERSION1,
                    client_id="device_manager",
                    protocol=mqtt.MQTTv311
                )
            else:
                # paho-mqtt 1.x
                self.client = mqtt.Client(client_id="device_manager", protocol=mqtt.MQTTv311)

            # Set callbacks
            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect
            self.client.on_message = self._on_message
            self.client.on_publish = self._on_publish

            # Connect to broker (assumes mosquitto or similar is running)
            logger.info(f"Connecting to MQTT broker at {self.host}:{self.port}")

            # Run client loop in background
            self.client.loop_start()

            # Try to connect (non-blocking)
            try:
                self.client.connect(self.host, self.port, keepalive=60)
                self.running = True
                logger.info("MQTT client started successfully")
            except Exception as e:
                logger.warning(f"Could not connect to MQTT broker: {e}")
                logger.info("MQTT broker will retry connection in background")
                self.running = True  # Still mark as running so it keeps trying

        except Exception as e:
            logger.error(f"Failed to start MQTT client: {e}")
            raise

    async def stop(self):
        """Stop the MQTT broker"""
        if not self.running:
            return

        logger.info("Stopping MQTT broker")
        self.running = False

        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
            self.client = None

    def _on_connect(self, client, userdata, flags, rc):
        """Callback when connected to MQTT broker"""
        if rc == 0:
            logger.info("Connected to MQTT broker")

            # Subscribe to all ESP32 topics
            self.client.subscribe("espsensor/#", qos=0)
            self.client.subscribe("homeassistant/#", qos=0)

            # Broadcast connection status (thread-safe)
            self._schedule_async(self.hub.broadcast({
                'type': 'mqtt_status',
                'connected': True,
                'message': 'Connected to MQTT broker'
            }))
        else:
            logger.error(f"Failed to connect to MQTT broker, code: {rc}")

    def _on_disconnect(self, client, userdata, rc):
        """Callback when disconnected from MQTT broker"""
        logger.warning(f"Disconnected from MQTT broker, code: {rc}")

        self._schedule_async(self.hub.broadcast({
            'type': 'mqtt_status',
            'connected': False,
            'message': 'Disconnected from MQTT broker'
        }))

    def _on_message(self, client, userdata, msg):
        """Callback when message is received"""
        logger.debug(f"MQTT message received: {msg.topic} = {msg.payload[:100]}")

        # Create message object
        mqtt_msg = MQTTMessage(
            topic=msg.topic,
            payload=msg.payload,
            direction='in'
        )

        # Add to log
        self.message_log.append(mqtt_msg)

        # Call registered callbacks
        for callback in self.message_callbacks:
            try:
                callback(mqtt_msg)
            except Exception as e:
                logger.error(f"Error in message callback: {e}")

        # Broadcast to WebSocket clients (thread-safe)
        self._schedule_async(self.hub.broadcast({
            'type': 'mqtt',
            **mqtt_msg.to_dict()
        }))

    def _on_publish(self, client, userdata, mid):
        """Callback when message is published"""
        logger.debug(f"MQTT message published, mid: {mid}")

    def publish(self, topic: str, payload: str, retain: bool = False, qos: int = 0):
        """Publish a message to MQTT"""
        if not self.client:
            logger.warning("MQTT client not initialized")
            return False

        try:
            # Convert payload to bytes if string
            if isinstance(payload, str):
                payload_bytes = payload.encode('utf-8')
            else:
                payload_bytes = payload

            # Publish message
            result = self.client.publish(topic, payload_bytes, qos=qos, retain=retain)

            # Log outgoing message
            mqtt_msg = MQTTMessage(
                topic=topic,
                payload=payload_bytes,
                direction='out'
            )
            self.message_log.append(mqtt_msg)

            # Broadcast to WebSocket clients (thread-safe)
            self._schedule_async(self.hub.broadcast({
                'type': 'mqtt',
                **mqtt_msg.to_dict()
            }))

            logger.debug(f"Published to {topic}: {payload_bytes[:100]}")
            return True

        except Exception as e:
            logger.error(f"Error publishing MQTT message: {e}")
            return False

    def subscribe(self, topic: str, qos: int = 0):
        """Subscribe to an MQTT topic"""
        if not self.client:
            logger.warning("MQTT client not initialized")
            return False

        try:
            self.client.subscribe(topic, qos=qos)
            self.subscriptions[topic] = qos
            logger.info(f"Subscribed to topic: {topic}")
            return True
        except Exception as e:
            logger.error(f"Error subscribing to topic {topic}: {e}")
            return False

    def unsubscribe(self, topic: str):
        """Unsubscribe from an MQTT topic"""
        if not self.client:
            logger.warning("MQTT client not initialized")
            return False

        try:
            self.client.unsubscribe(topic)
            self.subscriptions.pop(topic, None)
            logger.info(f"Unsubscribed from topic: {topic}")
            return True
        except Exception as e:
            logger.error(f"Error unsubscribing from topic {topic}: {e}")
            return False

    def get_message_log(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent MQTT messages"""
        messages = list(self.message_log)[-limit:]
        return [msg.to_dict() for msg in messages]

    def get_subscriptions(self) -> List[Dict[str, Any]]:
        """Get active subscriptions"""
        return [
            {'topic': topic, 'qos': qos}
            for topic, qos in self.subscriptions.items()
        ]

    def get_status(self) -> Dict[str, Any]:
        """Get broker status"""
        return {
            'running': self.running,
            'connected': self.client.is_connected() if self.client else False,
            'host': self.host,
            'port': self.port,
            'message_count': len(self.message_log),
            'subscriptions': len(self.subscriptions)
        }

    def add_message_callback(self, callback: Callable[[MQTTMessage], None]):
        """Add a callback to be called when messages are received"""
        self.message_callbacks.append(callback)
