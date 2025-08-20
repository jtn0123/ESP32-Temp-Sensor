import json
import os


def test_ui_spec_basic_schema_and_bounds():
    root = os.path.dirname(os.path.dirname(__file__))
    path = os.path.join(root, "config", "ui_spec.json")
    with open(path, "r") as f:
        data = json.load(f)

    # Schema and required top-level keys
    assert data.get("schema") == "ui-spec@1"
    assert isinstance(data.get("canvas"), dict)
    assert isinstance(data.get("fonts"), dict)
    assert isinstance(data.get("rects"), dict) and data["rects"]
    assert isinstance(data.get("components"), dict) and data["components"]
    assert isinstance(data.get("variants"), dict) and data["variants"]

    # Canvas bounds sanity
    canvas = data.get("canvas")
    W, H = int(canvas.get("w", 250)), int(canvas.get("h", 122))
    rects = data.get("rects")
    for k, v in rects.items():
        assert isinstance(v, list) and len(v) == 4, f"{k} must be [x,y,w,h]"
        x, y, w, h = map(int, v)
        assert x >= 0 and y >= 0
        assert x + w <= W and y + h <= H

    # Minimal component presence
    assert "header" in data["components"]
    assert "v1" in data["variants"]


