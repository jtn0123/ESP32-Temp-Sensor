#!/usr/bin/env python3
import contextlib
import os
import socket
import subprocess
import sys
import time


def _find_free_port() -> int:
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _start_http_server(root: str, port: int) -> subprocess.Popen:
    return subprocess.Popen(
        [sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"],
        cwd=root,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except Exception as e:
        print("Playwright not installed:", e)
        return 2

    web_root = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web", "sim")
    port = _find_free_port()
    server = _start_http_server(web_root, port)
    logs = []
    errs = []
    fails = []
    try:
        time.sleep(0.4)
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 250, "height": 122})
            page.on("console", lambda m: logs.append(f"[{m.type}] {m.text}"))
            page.on("pageerror", lambda e: errs.append(str(e)))
            page.on(
                "requestfailed",
                lambda r: fails.append(
                    f"FAIL {r.method} {r.url} {r.failure.error_text if r.failure else ''}"
                ),
            )
            url = f"http://127.0.0.1:{port}/index.html?spec=1&v=4"
            page.goto(url, wait_until="load")
            page.wait_for_timeout(700)
            scripts = page.evaluate(
                "()=>Array.from(document.querySelectorAll('script')).map(s=>s.src||'inline')"
            )
            ui_spec_type = page.evaluate("()=>typeof window.UI_SPEC")
            draw_type = page.evaluate("()=>typeof window.drawFromSpec")
            draw_gen_type = page.evaluate("()=>typeof window.drawFromSpecGen")
            pix = page.evaluate(
                (
                    "()=>{"
                    " const c=document.getElementById('epd');"
                    " const d=c.getContext('2d').getImageData(5,18,1,1).data;"
                    " return [d[0],d[1],d[2]];"
                    " }"
                )
            )
            # Fetch generated JS and print prefix
            text_prefix = page.evaluate(
                (
                    "async ()=>{"
                    " const res=await fetch('ui_generated.js?v=4');"
                    " const txt=await res.text();"
                    " return txt.slice(0,300);"
                    " }"
                )
            )
            out_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "out")
            os.makedirs(out_dir, exist_ok=True)
            snap = os.path.join(out_dir, "spec_only.png")
            page.screenshot(path=snap)
            print("Scripts:")
            for s in scripts:
                print(" ", s)
            print(
                "UI_SPEC:",
                ui_spec_type,
                "draw:",
                draw_type,
                "drawGen:",
                draw_gen_type,
                "pixel[5,18]:",
                tuple(pix),
            )
            print("ui_generated.js prefix:\n" + text_prefix)
            print("Console logs:")
            for line in logs:
                print(line)
            if errs:
                print("Page errors:")
                for e in errs:
                    print(" ", e)
            if fails:
                print("Request failed:")
                for f in fails:
                    print(" ", f)
            ok = tuple(pix) == (0, 0, 0)
            if not ok:
                print("Wrote screenshot:", snap)
                return 1
            browser.close()
            print("Wrote screenshot:", snap)
            return 0
    finally:
        server.terminate()
        with contextlib.suppress(Exception):
            server.wait(timeout=2)


if __name__ == "__main__":
    sys.exit(main())
