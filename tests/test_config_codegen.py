import os
import re
import shutil
import subprocess
import tempfile


ROOT = os.path.dirname(os.path.dirname(__file__))


def _run(cmd: list[str], env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, env=env)


def _read(path: str) -> str:
    with open(path, "r") as f:
        return f.read()


def test_layout_header_is_deterministic(tmp_path):
    # Ensure running the generator twice yields identical bytes
    gen = ["python3", os.path.join(ROOT, "scripts", "gen_layout_header.py")]
    r1 = _run(gen)
    assert r1.returncode == 0, r1.stdout + r1.stderr
    out_path = os.path.join(ROOT, "firmware", "arduino", "src", "display_layout.h")
    content1 = _read(out_path)

    r2 = _run(gen)
    assert r2.returncode == 0, r2.stdout + r2.stderr
    content2 = _read(out_path)

    assert content1 == content2


def _gen_device_header_with_env(env_overrides: dict[str, str]) -> str:
    # Run generator with a clean environment overriding only what we need
    base_env = os.environ.copy()
    base_env.update(env_overrides)
    r = _run(["python3", os.path.join(ROOT, "scripts", "gen_device_header.py")], env=base_env)
    assert r.returncode == 0, r.stdout + r.stderr
    hdr = os.path.join(ROOT, "firmware", "arduino", "src", "generated_config.h")
    return _read(hdr)


def _extract_define(text: str, name: str) -> str | None:
    m = re.search(rf"^#define\\s+{re.escape(name)}\\s+(.+)$", text, re.M)
    return m.group(1).strip() if m else None


def test_flash_modes_drive_wake_interval_define():
    # 3 minutes
    h3 = _gen_device_header_with_env({"WAKE_INTERVAL": "3m"})
    assert _extract_define(h3, "WAKE_INTERVAL_SEC") == "180"

    # 1 hour
    h1 = _gen_device_header_with_env({"WAKE_INTERVAL": "1h"})
    assert _extract_define(h1, "WAKE_INTERVAL_SEC") == "3600"

    # 2 hours
    h2 = _gen_device_header_with_env({"WAKE_INTERVAL": "2h"})
    assert _extract_define(h2, "WAKE_INTERVAL_SEC") == "7200"


def test_flash_mode_always_sets_no_sleep_flag(tmp_path):
    # Create a small harness that patches flash.run() to print env and exit without running pio
    harness = tmp_path / "capture_env.py"
    harness.write_text(
        (
            "import os, sys\n"
            "sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))\n"
            "from scripts import flash\n"
            "def fake_run(cmd):\n"
            "    print('EXTRA_FLAGS=' + os.environ.get('EXTRA_FLAGS',''))\n"
            "    print('WAKE_INTERVAL=' + os.environ.get('WAKE_INTERVAL',''))\n"
            "    return 0\n"
            "flash.run = fake_run\n"
            "sys.argv = ['flash.py', '--mode', 'always', '--build-only']\n"
            "raise SystemExit(flash.main())\n"
        )
    )
    proc = subprocess.run(["python3", str(harness)], cwd=ROOT, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    # Verify the always mode programs no-sleep via EXTRA_FLAGS
    lines = proc.stdout.strip().splitlines()
    env_map = {}
    for ln in lines:
        if "=" in ln:
            k, v = ln.split("=", 1)
            env_map[k.strip()] = v.strip()
    assert env_map.get("EXTRA_FLAGS", "").find("-DDEV_NO_SLEEP=1") >= 0
    # WAKE_INTERVAL should be empty in always mode
    assert env_map.get("WAKE_INTERVAL", "") == ""


