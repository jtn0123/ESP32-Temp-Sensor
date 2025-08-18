from scripts.monitor_usb import Metrics, format_metrics, parse_metrics_line


def test_parse_metrics_line_valid():
    line = (
        '{"event":"metrics","ip":"192.168.0.10","tempC":21.5,'
        '"rhPct":40,"wifi":true,"mqtt":false,'
        '"v":3.98,"pct":76}'
    )
    m = parse_metrics_line(line)
    assert m is not None
    assert isinstance(m, Metrics)
    assert m.ip == "192.168.0.10"
    assert abs(m.tempC - 21.5) < 1e-6
    assert abs(m.rhPct - 40.0) < 1e-6
    assert m.wifi is True
    assert m.mqtt is False
    assert abs(m.v - 3.98) < 1e-6
    assert m.pct == 76


def test_parse_metrics_line_ignores_non_metrics():
    line = '{"event":"log","msg":"hello"}'
    assert parse_metrics_line(line) is None


def test_parse_metrics_line_handles_missing_fields():
    line = '{"event":"metrics","ip":"0.0.0.0"}'
    m = parse_metrics_line(line)
    assert m is not None
    assert m.ip == "0.0.0.0"
    assert m.tempC is None
    assert m.rhPct is None
    assert m.v is None
    assert m.pct is None


def test_format_metrics_rounds_and_composes():
    m = Metrics(ip="1.2.3.4", tempC=20.0, rhPct=41.0, wifi=True, mqtt=False, v=4.08, pct=87)
    s = format_metrics(m)
    assert "ip=1.2.3.4" in s
    assert "tempC=20.00" in s
    assert "tempF=68.00" in s
    assert "rh%=41" in s
    assert "wifi=up" in s
    assert "mqtt=down" in s
    assert "battV=4.08" in s
    assert "batt%=87" in s


def test_parse_metrics_with_pressure_and_format_includes_it():
    line = (
        '{"event":"metrics","ip":"10.0.0.5","tempC":22.0,'
        '"rhPct":38,"pressHPa":1013.7,"wifi":true,"mqtt":true,'
        '"v":4.01,"pct":80}'
    )
    m = parse_metrics_line(line)
    assert m is not None
    assert abs(m.pressHPa - 1013.7) < 1e-6
    s = format_metrics(m)
    assert "press=1013.7hPa" in s
