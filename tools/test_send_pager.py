from types import SimpleNamespace

import serial.tools.list_ports

from send_pager import find_port


def test_find_port_accepts_rp2040(monkeypatch):
    ports = [SimpleNamespace(device="COM9", vid=0x2E8A, pid=0x000A)]
    monkeypatch.setattr(serial.tools.list_ports, "comports", lambda: ports)

    assert find_port() == "COM9"


def test_find_port_keeps_stm32_compatibility(monkeypatch):
    ports = [SimpleNamespace(device="COM5", vid=0x0483, pid=0x5740)]
    monkeypatch.setattr(serial.tools.list_ports, "comports", lambda: ports)

    assert find_port() == "COM5"


def test_find_port_ignores_unrelated_serial_devices(monkeypatch):
    ports = [SimpleNamespace(device="COM7", vid=0x1234, pid=0x5678)]
    monkeypatch.setattr(serial.tools.list_ports, "comports", lambda: ports)

    assert find_port() is None
