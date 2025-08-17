from scripts.parse_timeouts_log import parse


def test_sample_serial_has_no_timeouts():
    with open("sample_serial.txt", "r", encoding="utf-8") as f:
        s = parse(f)
    assert s.sensor_count == 0
    assert s.fetch_count == 0
    assert s.display_count == 0
    assert s.publish_count == 0
