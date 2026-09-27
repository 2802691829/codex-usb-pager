import argparse
import sys
import time

import serial
import serial.tools.list_ports

from pager_state import PagerSnapshot, normalize_status


SUPPORTED_USB_IDS = (
    (0x2E8A, 0x000A),  # Raspberry Pi Pico SDK USB CDC
    (0x0483, 0x5740),  # STM32 USB CDC reference firmware
)


def find_port() -> str | None:
    for port in serial.tools.list_ports.comports():
        if (port.vid, port.pid) in SUPPORTED_USB_IDS:
            return port.device
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Send a Codex pager command over USB CDC.")
    parser.add_argument(
        "command",
        choices=["ALERT", "WAIT", "DONE", "READY", "IDLE", "ERROR", "RUNNING"],
        help="Pager state or legacy alias.",
    )
    parser.add_argument("--run", type=int, default=0, help="Number of running Codex tasks.")
    parser.add_argument("--wait", type=int, default=0, help="Number of tasks waiting for confirmation.")
    parser.add_argument("--done", type=int, default=0, help="Number of completed tasks.")
    parser.add_argument("--balance", default="NA", help="Balance or usage token, no spaces recommended.")
    parser.add_argument(
        "--event",
        choices=["NONE", "WAIT", "DONE", "ERROR"],
        help="Buzzer event override. Defaults from command.",
    )
    parser.add_argument("--port", help="COM port override, for example COM5")
    args = parser.parse_args()

    port = args.port or find_port()
    if not port:
        print("No Codex pager USB CDC port found.", file=sys.stderr)
        return 2

    state = normalize_status(args.command)
    default_event = "NONE"
    if state in {"WAIT", "DONE", "ERROR"}:
        default_event = state
    event = args.event or default_event
    snapshot = PagerSnapshot(
        state=state,
        running=max(0, args.run),
        waiting=max(0, args.wait),
        done=max(0, args.done),
        balance=args.balance,
        event=event,
    )

    try:
        with serial.Serial(port, 115200, timeout=1, write_timeout=1) as ser:
            time.sleep(0.2)
            ser.write(snapshot.to_wire().encode("ascii"))
            ser.flush()
    except serial.SerialException as exc:
        print(f"Failed to write {snapshot.to_wire().strip()} to {port}: {exc}", file=sys.stderr)
        return 1

    print(f"sent {snapshot.to_wire().strip()} to {port}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
