import json
import os


def test_geometry_json_schema_shape():
    # Minimal JSON Schema-like validation without external lib
    root = os.path.dirname(os.path.dirname(__file__))
    path = os.path.join(root, "config", "display_geometry.json")
    with open(path, "r") as f:
        data = json.load(f)
    assert isinstance(data.get("canvas"), dict)
    assert isinstance(data.get("rects"), dict)
    W = int((data.get("canvas") or {}).get("w", 250))
    H = int((data.get("canvas") or {}).get("h", 122))
    for k, v in (data.get("rects") or {}).items():
        assert isinstance(v, list) and len(v) == 4
        x, y, w, h = map(int, v)
        assert x >= 0 and y >= 0
        assert x + w <= W and y + h <= H


def test_layout_identity_present_and_types():
    root = os.path.dirname(os.path.dirname(__file__))
    path = os.path.join(root, "config", "display_geometry.json")
    with open(path, "r") as f:
        data = json.load(f)
    assert isinstance(data.get("layout_version", data.get("version", 1)), int)
    crc = data.get("layout_crc")
    assert isinstance(crc, str) and crc.startswith("0x") and len(crc) == 10


def test_display_geometry_schema_and_bounds():
    root = os.path.dirname(os.path.dirname(__file__))
    path = os.path.join(root, "config", "display_geometry.json")
    with open(path, "r") as f:
        data = json.load(f)
    rects = data.get("rects") or {}
    assert isinstance(rects, dict) and rects, "rects must be present"
    canvas = data.get("canvas") or {"w": 250, "h": 122}
    W, H = int(canvas.get("w", 250)), int(canvas.get("h", 122))
    for k, v in rects.items():
        assert isinstance(v, list) and len(v) == 4, f"{k} must be [x,y,w,h]"
        x, y, w, h = map(int, v)
        assert x >= 0 and y >= 0
        assert x + w <= W and y + h <= H
