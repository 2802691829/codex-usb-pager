from __future__ import annotations

import inspect

import pager_transport
from pager_state import PagerSnapshot


class FakeSerial:
    def __init__(self, *args, **kwargs):
        self.writes = []
        self.flushed = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def write(self, payload):
        self.writes.append(payload)

    def flush(self):
        self.flushed = True


def test_send_snapshot_writes_without_fixed_pre_write_sleep(monkeypatch) -> None:
    opened = []

    def open_serial(*args, **kwargs):
        serial_port = FakeSerial(*args, **kwargs)
        opened.append(serial_port)
        return serial_port

    monkeypatch.setattr(pager_transport, "find_port", lambda: "COM9")
    monkeypatch.setattr(pager_transport.serial, "Serial", open_serial)
    snapshot = PagerSnapshot(
        state="RUNNING",
        running=1,
        waiting=0,
        done=0,
        balance="82",
        event="NONE",
    )

    pager_transport.send_snapshot(snapshot)

    assert opened[0].writes == [snapshot.to_wire().encode("ascii")]
    assert opened[0].flushed is True
    assert "sleep(" not in inspect.getsource(pager_transport.send_snapshot)
