import json
import os


def test_rects_ui_spec_match_geometry_json():
    root = os.path.dirname(os.path.dirname(__file__))
    ui_spec_path = os.path.join(root, "config", "ui_spec.json")
    geom_path = os.path.join(root, "config", "display_geometry.json")
    with open(ui_spec_path, "r") as f:
        ui = json.load(f)
    with open(geom_path, "r") as f:
        geom = json.load(f)
    rects_spec = ui.get("rects", {})
    rects_geom = geom.get("rects", {})
    assert rects_spec == rects_geom
