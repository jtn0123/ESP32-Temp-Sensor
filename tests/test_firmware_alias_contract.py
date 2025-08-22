import os
import re


ROOT = os.path.dirname(os.path.dirname(__file__))


def _read(path: str) -> str:
    with open(path, "r") as f:
        return f.read()


def test_alias_subscriptions_and_callbacks_present():
    # Ensure firmware subscribes to alias topics and handles them in callback
    net_h = os.path.join(ROOT, "firmware", "arduino", "src", "net.h")
    txt = _read(net_h)

    # Subscription checks
    assert 'sub("/temp_f")' in txt
    assert 'sub("/condition")' in txt
    assert 'sub("/condition_code")' in txt

    # Callback checks
    assert 'ends_with(topic, "/temp_f")' in txt
    assert 'ends_with(topic, "/condition")' in txt
    assert 'ends_with(topic, "/condition_code")' in txt


