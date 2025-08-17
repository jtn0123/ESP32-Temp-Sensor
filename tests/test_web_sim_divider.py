import contextlib
import os
import socket
import subprocess
import time

import pytest


def _find_free_port() -> int:
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _start_http_server(root: str, port: int) -> subprocess.Popen:
    return subprocess.Popen([
        "python3", "-m", "http.server", str(port), "--bind", "127.0.0.1"
    ], cwd=root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


@pytest.mark.skipif(not bool(__import__("importlib").util.find_spec("playwright")), reason="playwright not installed")
def test_center_divider_reaches_bottom():
    from playwright.sync_api import sync_playwright  # type: ignore

    web_root = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web", "sim")
    port = _find_free_port()
    server = _start_http_server(web_root, port)
    try:
        time.sleep(0.4)
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 250, "height": 122})
            page.goto(f"http://127.0.0.1:{port}/index.html", wait_until="load")
            page.wait_for_timeout(300)
            # Divider is drawn at x=125 from y=18 down to HEIGHT-1
            for y in [18, 60, 120-1]:
                r, g, b, a = page.evaluate(
                    "([x,y])=>{const c=document.getElementById('epd');const ctx=c.getContext('2d');return Array.from(ctx.getImageData(x,y,1,1).data);}",
                    [125, y],
                )
                assert (r, g, b) == (0, 0, 0)
            browser.close()
    finally:
        server.terminate(); server.wait(timeout=2)


