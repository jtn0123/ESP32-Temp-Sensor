import os
import tempfile
import subprocess


def run_parse(content: str, *args: str) -> tuple[int, str]:
    with tempfile.NamedTemporaryFile(mode='w+', delete=False) as tf:
        tf.write(content)
        tf.flush()
        path = tf.name
    try:
        cmd = ["python3", os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts", "parse_awake_log.py"), path, *args]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        return proc.returncode, (proc.stdout + proc.stderr)
    finally:
        os.unlink(path)


def test_parse_ok():
    rc, out = run_parse("""
ESP32 eInk Room Node boot
Awake ms: 31234
Sleeping for 7200s
""", "--max-awake-ms", "45000", "--sleep-s", "7200")
    assert rc == 0
    assert "OK:" in out


def test_parse_fail_awake():
    rc, out = run_parse("Awake ms: 60000\n", "--max-awake-ms", "45000")
    assert rc == 1
    assert "exceeds" in out



