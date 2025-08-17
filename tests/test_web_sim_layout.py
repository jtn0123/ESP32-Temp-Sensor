import os
import time
import json
import socket
import contextlib
import subprocess
import pytest


def _find_free_port() -> int:
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _start_http_server(root: str, port: int) -> subprocess.Popen:
    return subprocess.Popen([
        "python3", "-m", "http.server", str(port), "--bind", "127.0.0.1"
    ], cwd=root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _canvas_rgba(page, x: int, y: int):
    return page.evaluate(
        "([x,y])=>{const c=document.getElementById('epd');const ctx=c.getContext('2d');return Array.from(ctx.getImageData(x,y,1,1).data);}",
        [x, y],
    )


def _ensure_out_dir() -> str:
    root = os.path.dirname(os.path.dirname(__file__))
    out_dir = os.path.join(root, "out")
    os.makedirs(out_dir, exist_ok=True)
    return out_dir


def _save_artifacts(page, name: str = "sim") -> None:
    out_dir = _ensure_out_dir()
    # Save full page and canvas-only screenshots plus layout metrics JSON
    page.screenshot(path=os.path.join(out_dir, f"{name}_page.png"))
    canvas = page.query_selector('#epd')
    if canvas:
        canvas.screenshot(path=os.path.join(out_dir, f"{name}_canvas.png"))
    metrics = page.evaluate("() => ({ L: window.__layoutMetrics || null, T: window.__tempMetrics || null })")
    with open(os.path.join(out_dir, f"{name}_metrics.json"), 'w') as f:
        json.dump(metrics, f, indent=2)


@pytest.mark.skipif(not bool(__import__("importlib").util.find_spec("playwright")), reason="playwright not installed")
def test_layout_centering_and_clipping():
    from playwright.sync_api import sync_playwright  # type: ignore

    web_root = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web", "sim")
    port = _find_free_port()
    server = _start_http_server(web_root, port)
    try:
        time.sleep(0.4)
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 700, "height": 400})
            page.goto(f"http://127.0.0.1:{port}/index.html", wait_until="load")
            page.wait_for_timeout(300)

            # Ensure canvas logs exist
            assert page.evaluate("() => !!document.getElementById('epd')")

            # Optional always-save screenshots for visual review
            if os.getenv('SIM_SAVE_SHOT') or os.getenv('SAVE_SHOT'):
                _save_artifacts(page, name="boot")

            # Query computed geometry and derived centers from the page context
            metrics = page.evaluate(
                "() => {\n"
                "  const ctx = document.getElementById('epd').getContext('2d');\n"
                "  const M = {};\n"
                "  M.sampleData = window.lastData || null;\n"
                "  M.canvas = {w: ctx.canvas.width, h: ctx.canvas.height};\n"
                "  return M;\n"
                "}"
            )
            assert metrics["canvas"]["w"] == 250 and metrics["canvas"]["h"] == 122

            # Simple smoke: corners must be black (frame)
            for x,y in [(0,0),(249,0),(0,121),(249,121)]:
                r,g,b,a = _canvas_rgba(page, x, y)
                assert (r,g,b) == (0,0,0)

            # Pull exported layout metrics to validate guidelines
            M = page.evaluate("() => window.__layoutMetrics || null")
            assert M is not None

            try:
                # 1) Battery icon centered vertically between first two rows
                by = M['statusLeft']['batteryIcon']['y']
                bh = M['statusLeft']['batteryIcon']['h']
                icon_cy = by + bh/2
                row1y = M['statusLeft']['line1Y']
                row2y = M['statusLeft']['line2Y']
                mid_y = (row1y + row2y + 8) / 2  # approximate text baselines
                assert abs(icon_cy - mid_y) <= 1.5

                # 2) Battery group centered horizontally across left column
                left = M['statusLeft']['left']; right = M['statusLeft']['right']
                group_left = M['statusLeft']['batteryGroup']['x']
                group_w = M['statusLeft']['batteryGroup']['w']
                col_mid = (left + right) / 2
                group_mid = group_left + group_w / 2
                assert abs(col_mid - group_mid) <= 1.5

                # 3) IP row centered within left column
                ipx = M['statusLeft']['ip']['x']; ipw = M['statusLeft']['ip']['w']
                ip_mid = ipx + ipw / 2
                assert abs(ip_mid - col_mid) <= 1.5

                # 4) Weather block (icon + label) is horizontally centered within right quadrant bar
                wx = M['weather']['bar']['x']; ww = M['weather']['bar']['w']
                totalW = M['weather']['totalW']
                block_left = M['weather']['iconBox']['x']
                block_mid = block_left + totalW / 2
                bar_mid = wx + ww/2
                assert abs(block_mid - bar_mid) <= 1.5

                # 5) Temperature groups (inside/outside) roughly centered
                T = page.evaluate("() => window.__tempMetrics || null")
                assert T is not None
                for key in ['inside','outside']:
                    r = T[key]['rect']; contentLeft = T[key]['contentLeft']; totalW = T[key]['totalW']
                    mid = r['x'] + r['w']/2; groupMid = contentLeft + totalW/2
                    assert abs(mid - groupMid) <= 2

                # 6) Section labels centered above their temp blocks
                def _centered_over(rect, label_x, tol=2):
                    mid = rect['x'] + rect['w']/2
                    assert abs(label_x - mid) <= tol
                _centered_over(T['inside']['rect'], M['labels']['inside']['x'])
                _centered_over(T['outside']['rect'], M['labels']['outside']['x'])
            except AssertionError:
                _save_artifacts(page, name="failure")
                raise

            browser.close()
    finally:
        server.terminate(); server.wait(timeout=2)



@pytest.mark.skipif(not bool(__import__("importlib").util.find_spec("playwright")), reason="playwright not installed")
def test_web_sim_backend_integration_full_reload():
    from playwright.sync_api import sync_playwright  # type: ignore

    web_root = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web", "sim")
    port = _find_free_port()
    server = _start_http_server(web_root, port)
    try:
        time.sleep(0.4)
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 250, "height": 122})

            # Serve two different backend payloads on successive requests
            payloads = [
                {
                    "room_name": "Office",
                    "inside_temp": "72.5",
                    "inside_hum": "47",
                    "outside_temp": "68.4",
                    "outside_hum": "53",
                    "weather": "Cloudy",
                    "time": "10:32",
                    "ip": "192.168.1.42",
                    "voltage": "4.01",
                    "percent": 76,
                    "days": "128",
                    "wind": "4.2",
                },
                {
                    "room_name": "Office",
                    "inside_temp": "72.5",
                    "inside_hum": "47",
                    "outside_temp": "68.4",
                    "outside_hum": "53",
                    "weather": "Rain",
                    "time": "10:32",
                    "ip": "192.168.1.42",
                    "voltage": "4.01",
                    "percent": 76,
                    "days": "128",
                    "wind": "4.2",
                },
            ]
            idx = {"i": 0}

            def handle_route(route):
                if idx["i"] < len(payloads):
                    data = payloads[idx["i"]]
                    idx["i"] += 1
                else:
                    data = payloads[-1]
                route.fulfill(status=200, content_type="application/json", body=json.dumps(data))

            page.route("**/sample_data.json", handle_route)

            page.goto(f"http://127.0.0.1:{port}/index.html", wait_until="load")
            page.wait_for_timeout(300)

            # Count non-white pixels in the bottom-right weather bar area
            def count_nonwhite(x0, y0, w, h):
                return page.evaluate(
                    "([x0,y0,w,h])=>{const c=document.getElementById('epd');const ctx=c.getContext('2d');const d=ctx.getImageData(x0,y0,w,h).data;let cnt=0;for(let i=0;i<d.length;i+=4){if(!(d[i]===255&&d[i+1]===255&&d[i+2]===255))cnt++;}return cnt;}",
                    [x0, y0, w, h],
                )

            area = (130, 95, 114, 24)
            cnt_cloudy = count_nonwhite(*area)

            # Full reload → second payload (Rain)
            page.reload(wait_until="load")
            page.wait_for_timeout(300)
            cnt_rain = count_nonwhite(*area)

            # Expect a visual change in the weather area between Cloudy and Rain
            assert cnt_cloudy != cnt_rain
            browser.close()
    finally:
        server.terminate(); server.wait(timeout=2)


@pytest.mark.skipif(not bool(__import__("importlib").util.find_spec("playwright")), reason="playwright not installed")
def test_web_sim_partial_refresh_only_updates_header_time():
    from playwright.sync_api import sync_playwright  # type: ignore

    web_root = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web", "sim")
    port = _find_free_port()
    server = _start_http_server(web_root, port)
    try:
        time.sleep(0.4)
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 250, "height": 122})

            # First payload for initial load; second payload changes outside_temp
            payloads = [
                {"outside_temp": "68.4"},
                {"outside_temp": "100.0"},
            ]
            idx = {"i": 0}

            def handle_route(route):
                if idx["i"] < len(payloads):
                    base = {
                        "room_name": "Office",
                        "inside_temp": "72.5",
                        "inside_hum": "47",
                        "outside_hum": "53",
                        "weather": "Cloudy",
                        "time": "10:32",
                        "ip": "192.168.1.42",
                        "voltage": "4.01",
                        "percent": 76,
                        "days": "128",
                        "wind": "4.2",
                    }
                    base.update(payloads[idx["i"]])
                    data = base
                    idx["i"] += 1
                else:
                    data = base  # type: ignore[name-defined]
                route.fulfill(status=200, content_type="application/json", body=json.dumps(data))

            page.route("**/sample_data.json", handle_route)

            page.goto(f"http://127.0.0.1:{port}/index.html", wait_until="load")
            page.wait_for_timeout(300)

            # Capture OUT_TEMP rectangle pixels before refresh
            OUT_TEMP = [131, 36, 90, 28]
            before = page.evaluate(
                "([x,y,w,h])=>{const c=document.getElementById('epd');const ctx=c.getContext('2d');return Array.from(ctx.getImageData(x,y,w,h).data);}",
                OUT_TEMP,
            )

            # Click Refresh → fetches sample_data.json again but only redraws header time region
            page.click('#refresh')
            page.wait_for_timeout(400)

            after = page.evaluate(
                "([x,y,w,h])=>{const c=document.getElementById('epd');const ctx=c.getContext('2d');return Array.from(ctx.getImageData(x,y,w,h).data);}",
                OUT_TEMP,
            )

            # The OUT_TEMP area should be unchanged by the partial refresh
            assert before == after
            browser.close()
    finally:
        server.terminate(); server.wait(timeout=2)


