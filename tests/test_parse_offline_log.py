from scripts.parse_offline_log import parse


def test_offline_queue_and_drain_parsing():
    lines = [
        "Offline: queued seq=0 ts=1710000000 (C=21.4 RH=43)",
        "Offline: queued seq=1 ts=1710000180 (C=21.5 RH=43)",
        "Offline: queued seq=2 ts=1710000360 (C=21.6 RH=44)",
        "Offline: draining 2 samples (tail=0 head=3)",
    ]
    evt = parse(lines)
    assert evt.queued == 3
    assert evt.drained == 2
    assert evt.last_tail == 0
    assert evt.last_head == 3


def test_sntp_parse_ok_and_timeout():
    lines = [
        "Time: SNTP sync timeout (continuing)",
        "Time: SNTP sync ok",
    ]
    evt = parse(lines)
    assert evt.saw_sntp_timeout is True
    assert evt.saw_sntp_ok is True


