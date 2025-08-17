import importlib.util
import os

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(__file__))
_scripts = os.path.join(ROOT, 'scripts')
_module_path = os.path.join(_scripts, 'mock_display.py')
_spec = importlib.util.spec_from_file_location('mock_display', _module_path)
md = importlib.util.module_from_spec(_spec)  # type: ignore
_spec.loader.exec_module(md)  # type: ignore


def _count_nonwhite(img: Image.Image, rect):
    x0,y0,x1,y1 = rect
    px = img.load()
    cnt = 0
    for y in range(y0, y1):
        for x in range(x0, x1):
            if px[x,y] == 0:
                cnt += 1
    return cnt


def test_vector_icon_fallback_draws_pixels_when_png_missing(monkeypatch):
    # Force PNG loading to fail
    monkeypatch.setenv("NO_PNG_ICONS", "1")
    def no_png(_):
        return None
    monkeypatch.setattr(md, 'try_load_icon_png', no_png)

    data = {"weather": "Cloudy"}
    img = md.render(data)

    # Determine OUT_ICON rect from geometry
    rects = md.load_geometry()
    r = rects.get('OUT_ICON', [210,22,28,28])
    x,y,w,h = r
    cnt = _count_nonwhite(img, (x, y, x+w, y+h))
    assert cnt > 0


