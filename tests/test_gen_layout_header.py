import importlib.util
import os

ROOT = os.path.dirname(os.path.dirname(__file__))
_scripts = os.path.join(ROOT, "scripts")
_module_path = os.path.join(_scripts, "gen_layout_header.py")
_spec = importlib.util.spec_from_file_location("gen_layout_header", _module_path)
glh = importlib.util.module_from_spec(_spec)  # type: ignore
_spec.loader.exec_module(glh)  # type: ignore


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
