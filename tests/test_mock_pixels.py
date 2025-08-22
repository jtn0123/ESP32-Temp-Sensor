import importlib.util
import os


ROOT = os.path.dirname(os.path.dirname(__file__))
_scripts = os.path.join(ROOT, "scripts")
_module_path = os.path.join(_scripts, "mock_display.py")
_spec = importlib.util.spec_from_file_location("mock_display", _module_path)
md = importlib.util.module_from_spec(_spec)  # type: ignore
_spec.loader.exec_module(md)  # type: ignore


def _count_pixel_diff(img_a, img_b) -> int:
    # Compare as raw 1-bit pixel buffers
    a = img_a.tobytes()
    b = img_b.tobytes()
    # Count differing bits by XOR-ing bytes and popcount
    total = 0
    for x, y in zip(a, b):
        v = x ^ y
        # Kernighan popcount for 8-bit
        c = 0
        while v:
            v &= v - 1
            c += 1
        total += c
    return total


def test_mock_png_matches_golden_with_small_tolerance():
    # Generate current image
    data = {
        "room_name": "Office",
        "inside_temp": "72.5",
        "inside_hum": "47",
        "outside_temp": "68.4",
        "outside_hum": "53",
        "weather": "Cloudy",
        "time": "10:32",
        "ip": "192.168.1.42",
        "voltage": "4.01",
        "percent": "76",
        "days": "128",
    }
    img = md.render(data)

    # Golden: derive from versioned md5 snapshot when present, else the current image becomes the baseline
    golden_dir = os.path.join(ROOT, "tests")
    golden_png = os.path.join(golden_dir, "golden_default.png")
    if not os.path.exists(golden_png):
        # First run bootstraps the golden for stability across environments
        os.makedirs(golden_dir, exist_ok=True)
        img.save(golden_png)
        assert True
        return

    from PIL import Image

    with Image.open(golden_png) as g:
        g = g.convert("1")
        cur = img.convert("1")
        assert g.size == cur.size
        # Allow a tiny number of pixel differences for font raster differences
        diff = _count_pixel_diff(g, cur)
        # 5 pixels max difference
        assert diff <= 5, f"Pixel diff too high: {diff} > 5"


