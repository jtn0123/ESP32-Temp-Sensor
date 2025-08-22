import os
import shutil
import subprocess
import sys
import time

import pytest

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from scripts.test_mqtt_integration import MqttTestClient, _now_ms  # noqa: E402


@pytest.fixture(scope="session")
def mosquitto_broker():
    mosq = shutil.which("mosquitto")
    if not mosq:
        pytest.skip("mosquitto not installed; skipping MQTT tests")

    conf = os.path.join(ROOT, "mosquitto_test.conf")
    port = 18884

    proc = subprocess.Popen(
        [mosq, "-c", conf, "-v"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    )

    host = "127.0.0.1"
    deadline = time.time() + 5.0
    last_err = None
    while time.time() < deadline:
        try:
            probe = MqttTestClient(host, port, client_id=f"probe-{_now_ms()}")
            probe.connect()
            probe.disconnect()
            break
        except Exception as e:  # pragma: no cover - timing dependent
            last_err = e
            time.sleep(0.05)
    else:
        try:
            proc.terminate()
        except Exception:
            pass
        try:
            proc.kill()
        except Exception:
            pass
        pytest.skip(f"Failed to start mosquitto: {last_err}")

    try:
        yield (host, port)
    finally:  # pragma: no cover - teardown
        try:
            proc.terminate()
            proc.wait(timeout=2)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
