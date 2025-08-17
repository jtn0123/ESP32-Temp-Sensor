import contextlib
import os
import socket
import subprocess
import sys
import time

import pytest


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


def _canvas_rgba(page, x: int, y: int):
    js = (
        "([x,y])=>{"
        "const c=document.getElementById('epd');"
        "const ctx=c.getContext('2d');"
        "return Array.from(ctx.getImageData(x,y,1,1).data);}"
    )
    return page.evaluate(js, [x, y])


@pytest.mark.skipif(
    not bool(__import__("importlib").util.find_spec("playwright")),
    reason="playwright not installed",
)
def test_web_sim_basic_pixels():
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
            # allow icons fetch & draw
            page.wait_for_timeout(300)

            # Corners should be black border
            for x, y in [(0, 0), (249, 0), (0, 121), (249, 121)]:
                r, g, b, a = _canvas_rgba(page, x, y)
                assert (r, g, b) == (0, 0, 0)

            # Header underline at y=18 should be black
            r, g, b, a = _canvas_rgba(page, 5, 18)
            assert (r, g, b) == (0, 0, 0)

            # In split3 layout, a horizontal rule above the status stack
            # is drawn around y≈92
            r, g, b, a = _canvas_rgba(page, 5, 92)
            assert (r, g, b) == (0, 0, 0)

            # Bottom-right weather area (split3) should contain some non-white pixels
            any_black = False
            for y in range(95, 120):
                for x in range(130, 244):
                    r, g, b, a = _canvas_rgba(page, x, y)
                    if (r, g, b) != (255, 255, 255):
                        any_black = True
                        break
                if any_black:
                    break
            assert any_black

            browser.close()
    finally:
        server.terminate()
        server.wait(timeout=2)
