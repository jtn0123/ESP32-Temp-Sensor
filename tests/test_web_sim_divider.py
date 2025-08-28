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
    return subprocess.Popen(
        ["python3", "-m", "http.server", str(port), "--bind", "127.0.0.1"],
        cwd=root,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


@pytest.mark.skipif(
    not bool(__import__("importlib").util.find_spec("playwright")),
    reason="playwright not installed",
)
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
            page.wait_for_timeout(500)

            # Ensure canvas is drawn by calling draw function
            # Disable 1-bit mode for testing to avoid threshold issues
            page.evaluate("window.oneBitMode = false")
            page.evaluate(
                "if (typeof window.draw === 'function') window.draw(window.DEFAULTS || {})"
            )
            page.wait_for_timeout(100)

            # Debug: check what's actually at x=125, y=60
            debug_js = """
                () => {
                    const c = document.getElementById('epd');
                    const ctx = c.getContext('2d');
                    
                    // Get actual pixel values around the expected divider
                    let result = {
                        at_125_60: null,
                        black_count_at_125: 0,
                        sample_line: []
                    };
                    
                    // Check the specific pixel
                    const pixel = ctx.getImageData(125, 60, 1, 1).data;
                    result.at_125_60 = [pixel[0], pixel[1], pixel[2]];
                    
                    // Count black pixels along x=125
                    for (let y = 0; y < 122; y++) {
                        const p = ctx.getImageData(125, y, 1, 1).data;
                        if (p[0] === 0 && p[1] === 0 && p[2] === 0) {
                            result.black_count_at_125++;
                        }
                    }
                    
                    // Sample a few points along x=125
                    for (let y of [0, 18, 60, 84, 121]) {
                        const p = ctx.getImageData(125, y, 1, 1).data;
                        result.sample_line.push({y: y, rgb: [p[0], p[1], p[2]]});
                    }
                    
                    return result;
                }
            """
            debug_result = page.evaluate(debug_js)
            print(f"Debug result: {debug_result}")

            # Divider is drawn at x=125 from y=18 down to y=121
            for y in [18, 60, 121]:
                js = (
                    "([x,y])=>{"
                    "const c=document.getElementById('epd');"
                    "const ctx=c.getContext('2d');"
                    "return Array.from(ctx.getImageData(x,y,1,1).data);}"
                )
                r, g, b, a = page.evaluate(js, [125, y])
                assert (r, g, b) == (0, 0, 0), f"Expected black at (125, {y}), got ({r}, {g}, {b})"
            browser.close()
    finally:
        server.terminate()
        server.wait(timeout=2)
