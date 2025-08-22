#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
import sys


def run(cmd: list[str], cwd: str | None = None) -> int:
    print("$", " ".join(cmd))
    try:
        p = subprocess.run(cmd, cwd=cwd, check=False)
        return p.returncode
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 127


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate PlatformIO builds for all envs")
    ap.add_argument(
        "--project-dir",
        default=os.path.join(os.path.dirname(__file__), "..", "firmware", "arduino"),
    )
    ap.add_argument(
        "--environments",
        nargs="*",
        default=[
            "feather_esp32s2_display_only",
            "feather_esp32s2_headless",
        ],
    )
    args = ap.parse_args()

    proj = os.path.abspath(args.project_dir)
    rc_all = 0
    # Gate: ensure generated display_layout.h is up-to-date with spec
    try:
        repo = os.path.abspath(os.path.join(proj, "..", ".."))
        # Run UI generator (which also regenerates layout header) and fail if it changed files
        # First, capture a pre-diff snapshot
        pre = subprocess.check_output(["git", "status", "--porcelain"], cwd=repo).decode()
        subprocess.check_call([sys.executable, os.path.join(repo, "scripts", "gen_ui.py")])
        post = subprocess.check_output(["git", "status", "--porcelain"], cwd=repo).decode()
        # If running in CI with a clean tree, any change indicates out-of-date generated files
        if pre.strip() == "" and post.strip() != "":
            print(
                "ERROR: Generated headers are out-of-date. Run scripts/gen_ui.py and commit.",
                file=sys.stderr,
            )
            return 2
    except Exception as e:
        # Non-fatal locally; still proceed with builds
        print(f"WARN: header up-to-date check skipped: {e}", file=sys.stderr)
    for env in args.environments:
        rc = run(["pio", "run", "-e", env], cwd=proj)
        if rc != 0:
            print(f"Build failed for env {env}", file=sys.stderr)
            rc_all = rc
    return rc_all


if __name__ == "__main__":
    raise SystemExit(main())
