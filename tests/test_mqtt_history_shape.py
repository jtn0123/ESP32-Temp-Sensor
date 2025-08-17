from scripts.parse_history_payload import parse_history_payload


def test_history_payload_valid_minimal():
    payload = '{"ts":1710000000,"tempF":72.5,"rh":47}'
    rec = parse_history_payload(payload)
    assert rec is not None
    assert rec.ts == 1710000000
    assert abs(rec.tempF - 72.5) < 1e-6
    assert abs(rec.rh - 47.0) < 1e-6


def test_history_payload_types_and_bounds():
    # Integers and strings that coerce to numbers should parse
    payloads = [
        '{"ts":1710000123,"tempF":70,"rh":50}',
        '{"ts":"1710000123","tempF":"70.1","rh":"49"}',
    ]
    for p in payloads:
        rec = parse_history_payload(p)
        assert rec is not None
        assert rec.ts >= 1_600_000_000
        assert -100.0 < rec.tempF < 200.0
        assert 0.0 <= rec.rh <= 100.0


