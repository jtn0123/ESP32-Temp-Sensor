from scripts.parse_wifi_log import parse, WifiJoin


def test_parse_wifi_log_basic_with_bssid():
    lines = [
        "WiFi: connecting to MySSID...",
        "WiFi: preferring BSSID AA:BB:CC:DD:EE:FF",
        "WiFi: connected, IP 192.168.1.10 RSSI -70 dBm",
    ]
    evt = parse(lines)
    assert isinstance(evt, WifiJoin)
    assert evt.ssid == "MySSID"
    assert evt.preferred_bssid == "aa:bb:cc:dd:ee:ff"
    assert evt.fell_back is False
    assert evt.ip == "192.168.1.10"
    assert evt.rssi_dbm == -70


def test_parse_wifi_log_with_fallback_and_timestamps():
    lines = [
        "100: WiFi: connecting to MySSID...",
        "150: WiFi: preferring BSSID 11:22:33:44:55:66",
        "3500: WiFi: BSSID join slow; falling back to SSID-only",
        "5200: WiFi: connected, IP 192.168.1.42 RSSI -63 dBm",
    ]
    evt = parse(lines)
    assert evt.ssid == "MySSID"
    assert evt.preferred_bssid == "11:22:33:44:55:66"
    assert evt.fell_back is True
    assert evt.ip == "192.168.1.42"
    assert evt.rssi_dbm == -63
    assert evt.started_ms == 100
    assert evt.connected_ms == 5200
    assert evt.join_ms == 5100


