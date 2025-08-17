import os
import subprocess
import tempfile


def run_parse(content: str) -> tuple[int, str]:
    with tempfile.NamedTemporaryFile(mode='w+', delete=False, newline='') as tf:
        tf.write(content)
        tf.flush()
        path = tf.name
    try:
        cmd = [
            "python3",
            os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts", "parse_timeouts_log.py"),
            path,
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        return proc.returncode, (proc.stdout + proc.stderr)
    finally:
        os.unlink(path)


def test_parse_counts():
    rc, out = run_parse(
        """
Timeout: sensor read exceeded budget ms=420 budget=300
Timeout: retained fetch budget reached ms=800 budget=800 (no outside data)
Timeout: display phase exceeded budget ms=2100 budget=2000
Timeout: publish exceeded budget ms=900 budget=800
"""
    )
    assert rc == 0
    # Expect summary counts in output
    assert "sensor=1" in out
    assert "fetch=1" in out
    assert "display=1" in out
    assert "publish=1" in out


