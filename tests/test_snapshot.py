import os, sys
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))

import mock_display as md  # type: ignore

GOLDEN_PATH = os.path.join(ROOT, 'tests', 'golden_default.md5')

def test_golden_snapshot():
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
    md5 = md.image_md5(img)
    if not os.path.exists(GOLDEN_PATH):
        # First run creates golden
        with open(GOLDEN_PATH,'w') as f:
            f.write(md5)
        assert True
    else:
        with open(GOLDEN_PATH,'r') as f:
            golden = f.read().strip()
        assert md5 == golden


