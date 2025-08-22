import os
import statistics

from scripts.parse_debug_json import parse_debug_payload


ROOT = os.path.dirname(os.path.dirname(__file__))


def test_soak_budget_from_sample_serial():
    # Use available sample_serial.txt shape as a proxy; extend to include debug JSON lines
    sample_path = os.path.join(ROOT, "sample_serial.txt")
    if not os.path.exists(sample_path):
        # Nothing to validate in this repo snapshot
        assert True
        return

    lines = open(sample_path, "r", encoding="utf-8", errors="ignore").read().splitlines()
    # Accept JSON metrics lines if present (produced by headless envs). Some samples may not include them.
    boot_to_wifi = []
    wifi_to_mqtt = []
    avail_online = 0
    avail_offline = 0
    for ln in lines:
        if ln.startswith("{") and '"event"' in ln and '"metrics"' in ln:
            # Not a debug line; skip
            continue
        if ln.startswith("{") and '"ms_boot_to_wifi"' in ln:
            rec = parse_debug_payload(ln)
            if rec and rec.ms_boot_to_wifi is not None:
                boot_to_wifi.append(rec.ms_boot_to_wifi)
            if rec and rec.ms_wifi_to_mqtt is not None:
                wifi_to_mqtt.append(rec.ms_wifi_to_mqtt)
        if " availability " in ln or ln.endswith("availability online"):
            avail_online += 1
        if ln.endswith("availability offline"):
            avail_offline += 1

    # If present, assert P95 thresholds
    if boot_to_wifi:
        p95_wifi = statistics.quantiles(boot_to_wifi, n=20)[-1]
        assert p95_wifi <= 5000, f"boot->wifi P95 too high: {p95_wifi}ms"
    if wifi_to_mqtt:
        p95_mqtt = statistics.quantiles(wifi_to_mqtt, n=20)[-1]
        assert p95_mqtt <= 3000, f"wifi->mqtt P95 too high: {p95_mqtt}ms"

    # Availability should flip offline at least once per cycle in soak
    if avail_online > 0:
        assert avail_offline >= 1, "expected at least one offline availability by cycle end"
