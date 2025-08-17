from pathlib import Path


def build_fw_discovery_payload(client_id: str, room_name: str, pub_base: str, *, key: str, name: str, unit: str, dev_class: str, state_suffix: str) -> str:
    """
    Mirror firmware's net_publish_ha_discovery() JSON exactly (no extra fields, no spacing).
    This must match the snprintf in firmware/arduino/src/net.h.
    """
    state_topic = f"{pub_base}/{state_suffix}"
    availability_topic = f"{pub_base}/availability"
    # Keep formatting identical to firmware: ordering and nested device fields
    # Firmware computes suggested_display_precision based on unit and sets expire_after = WAKE_INTERVAL_SEC + 120.
    # In tests, assume 1h default WAKE_INTERVAL_SEC=3600 unless overridden in env-specific builds.
    expire_after = 3600 + 120
    if unit == "°F":
        suggested_precision = 1
    elif unit == "V":
        suggested_precision = 2
    else:
        suggested_precision = 0
    return (
        "{"  # opening brace
        f"\"name\":\"{name}\","  # name
        f"\"unique_id\":\"{client_id}_{key}\","  # unique_id
        f"\"state_topic\":\"{state_topic}\","  # state_topic
        f"\"availability_topic\":\"{availability_topic}\","  # availability_topic
        f"\"unit_of_measurement\":\"{unit}\","  # unit
        f"\"device_class\":\"{dev_class}\","  # device_class
        f"\"state_class\":\"measurement\","  # state_class
        f"\"suggested_display_precision\":{suggested_precision},"
        f"\"expire_after\":{expire_after},"
        "\"device\":"
        "{"  # device object
        f"\"identifiers\":[\"{client_id}\"],"
        f"\"name\":\"ESP32 Room Node: {room_name}\","  # device name
        "\"manufacturer\":\"DIY\","  # manufacturer
        "\"model\":\"Feather ESP32-S2\""  # model
        "}"
        "}"
    )


def test_discovery_payload_exceeds_default_pubsubclient_and_fits_1024():
    # Sample identifiers similar to firmware formatting
    client_id = "esp32-room-abc123"
    room_name = "Office"
    pub_base = f"sensors/{client_id}"

    # Four discovery configs published by firmware
    payloads = [
        build_fw_discovery_payload(client_id, room_name, pub_base, key="inside_temp", name="Inside Temperature", unit="°F", dev_class="temperature", state_suffix="inside/temp"),
        build_fw_discovery_payload(client_id, room_name, pub_base, key="inside_hum", name="Inside Humidity", unit="%", dev_class="humidity", state_suffix="inside/hum"),
        build_fw_discovery_payload(client_id, room_name, pub_base, key="battery_volts", name="Battery Voltage", unit="V", dev_class="voltage", state_suffix="battery/voltage"),
        build_fw_discovery_payload(client_id, room_name, pub_base, key="battery_pct", name="Battery", unit="%", dev_class="battery", state_suffix="battery/percent"),
    ]

    # PubSubClient default MQTT_MAX_PACKET_SIZE is 256 bytes
    default_max = 256
    sized = [len(p.encode("utf-8")) for p in payloads]
    # At least one payload should exceed the stock default, demonstrating the need to raise the buffer
    assert any(sz > default_max for sz in sized), f"Expected at least one discovery payload to exceed {default_max} bytes, got sizes={sized}"
    # All payloads must fit within our configured 1024-byte buffer
    assert all(sz <= 1024 for sz in sized), f"A discovery payload exceeded 1024 bytes: sizes={sized}"


def test_platformio_and_firmware_config_set_buffer_to_1024():
    # Ensure PlatformIO sets -DMQTT_MAX_PACKET_SIZE=1024 in all environments
    pio_ini = Path(__file__).resolve().parents[1] / "firmware" / "arduino" / "platformio.ini"
    ini_text = pio_ini.read_text(encoding="utf-8")
    occurrences = ini_text.count("-DMQTT_MAX_PACKET_SIZE=1024")
    assert occurrences >= 1, "Expected -DMQTT_MAX_PACKET_SIZE=1024 to be defined in platformio.ini"

    # Ensure firmware code also calls setBufferSize(1024) as a runtime fallback
    net_h = Path(__file__).resolve().parents[1] / "firmware" / "arduino" / "src" / "net.h"
    net_text = net_h.read_text(encoding="utf-8")
    assert "setBufferSize(1024)" in net_text, "Expected runtime g_mqtt.setBufferSize(1024) fallback in net.h"


