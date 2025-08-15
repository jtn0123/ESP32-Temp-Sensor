import os
import sys
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))

import mock_display as md  # type: ignore

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


