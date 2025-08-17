import os
import sys
import json

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))

import gen_layout_header as glh  # type: ignore


def test_generate_header_basic_contents():
    data = {
        "canvas": {"w": 250, "h": 122},
        "rects": {
            "HEADER_NAME": [6, 2, 160, 14],
            "HEADER_TIME": [172, 2, 72, 14],
            "STATUS": [6, 112, 238, 10],
        },
    }
    out = glh.generate_header(data)
    assert "#define EINK_WIDTH 250" in out
    assert "#define EINK_HEIGHT 122" in out
    # STATUS is renamed to STATUS_
    assert "static constexpr int STATUS_[4]" in out
    # md5 line present
    assert "// md5:" in out
    # sanity checks emitted for windows
    assert "static_assert(" in out


