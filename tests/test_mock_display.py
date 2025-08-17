import json
import os
import importlib.util

ROOT = os.path.dirname(os.path.dirname(__file__))
_scripts = os.path.join(ROOT, 'scripts')
_spec = importlib.util.spec_from_file_location('mock_display', os.path.join(_scripts, 'mock_display.py'))
md = importlib.util.module_from_spec(_spec)  # type: ignore
_spec.loader.exec_module(md)  # type: ignore


def test_render_dimensions():
    img = md.render({})
    assert img.size == (md.WIDTH, md.HEIGHT)
    assert img.mode == '1'

def test_header_and_frame_nonwhite_pixels():
    img = md.render({"room_name":"Test"})
    px = img.load()
    # Corners should be black frame
    assert px[0,0] == 0
    assert px[md.WIDTH-1,0] == 0
    assert px[0,md.HEIGHT-1] == 0
    assert px[md.WIDTH-1,md.HEIGHT-1] == 0

def test_icon_changes_image_hash():
    a = md.image_md5(md.render({"weather":"Clear"}))
    b = md.image_md5(md.render({"weather":"Cloudy"}))
    assert a != b

def test_png_icon_loads_and_renders_centered():
    # uses generated 24x24 icons if present
    img = md.render({"weather":"cloudy"})
    # Load geometry JSON for icon box
    gpaths = [
        os.path.join(ROOT, 'config', 'display_geometry.json'),
        os.path.join(ROOT, 'web', 'sim', 'geometry.json'),
    ]
    G = None
    for p in gpaths:
        if os.path.exists(p):
            with open(p,'r') as f:
                G = json.load(f)
            break
    assert G is not None
    rects = G.get('rects', G)
    icon = rects.get('OUT_ICON', [210,22,28,28])
    x,y,w,h = icon
    x0,y0,x1,y1 = x, y, x+w, y+h
    px = img.load()
    has_black = any(px[i,j] == 0 for i in range(x0,x1) for j in range(y0,y1))
    assert has_black


