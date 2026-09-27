from __future__ import annotations

import serial

from pager_state import PagerSnapshot
from send_pager import find_port


def send_snapshot(snapshot: PagerSnapshot) -> None:
    port = find_port()
    if not port:
        return
    try:
        with serial.Serial(port, 115200, timeout=0.5, write_timeout=0.5) as ser:
            ser.write(snapshot.to_wire().encode("ascii"))
            ser.flush()
    except serial.SerialException:
        return
