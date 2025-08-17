import os
import subprocess
import tempfile


def run_parse(content: str, *args: str) -> tuple[int, str]:
    with tempfile.NamedTemporaryFile(mode='w+', delete=False, newline='') as tf:
        tf.write(content)
        tf.flush()
        path = tf.name
    try:
        cmd = [
            "python3",
            os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts", "parse_awake_log.py"),
            path,
            *args,
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        return proc.returncode, (proc.stdout + proc.stderr)
    finally:
        os.unlink(path)


def test_missing_awake_line():
    rc, out = run_parse("Sleeping for 7200s\n")
    assert rc == 1
    assert "No 'Awake ms:'" in out


def test_sleep_mismatch():
    rc, out = run_parse("Awake ms: 100\nSleeping for 3600s\n", "--sleep-s", "7200")
    assert rc == 1
    assert "Sleep seconds" in out


def test_crlf_and_noise():
    rc, out = run_parse("\r\nNOISE\r\nAwake ms: 1234\r\nnoise\r\nSleeping for 7200s\r\n", "--max-awake-ms", "2000")
    assert rc == 0
    assert "OK:" in out


def test_multiple_matches_last_wins():
    content = """
Awake ms: 40000
Sleeping for 3600s
Awake ms: 20000
Sleeping for 7200s
"""
    rc, out = run_parse(content, "--max-awake-ms", "45000", "--sleep-s", "7200")
    assert rc == 0
    assert "OK:" in out


