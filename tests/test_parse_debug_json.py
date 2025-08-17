from scripts.parse_debug_json import parse_debug_payload


def test_parse_full_payload():
    payload = (
        '{"ms_boot_to_wifi":1200,"ms_wifi_to_mqtt":800,'
        '"ms_sensor_read":150,"ms_publish":60,'
        '"sleep_scheduled_ms":1800000,"deep_sleep_us":1800000000,'
        '"timeouts":5,"reset_reason":"ESP_RST_POWERON","wakeup_cause":"TIMER"}'
    )
    rec = parse_debug_payload(payload)
    assert rec is not None
    assert rec.ms_boot_to_wifi == 1200
    assert rec.ms_wifi_to_mqtt == 800
    assert rec.ms_sensor_read == 150
    assert rec.ms_publish == 60
    assert rec.sleep_scheduled_ms == 1800000
    assert rec.deep_sleep_us == 1800000000
    assert rec.timeouts == 5
    assert rec.reset_reason == "ESP_RST_POWERON"
    assert rec.wakeup_cause == "TIMER"


def test_parse_partial_payload():
    payload = '{"timeouts":3}'
    rec = parse_debug_payload(payload)
    assert rec is not None
    assert rec.timeouts == 3
    assert rec.ms_boot_to_wifi is None


def test_parse_invalid_payload():
    assert parse_debug_payload("not json") is None
