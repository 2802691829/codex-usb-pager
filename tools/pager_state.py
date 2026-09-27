from __future__ import annotations

from dataclasses import dataclass
import time


STATUS_ALIASES = {
    "ALERT": "WAIT",
    "WAIT": "WAIT",
    "WAITING": "WAIT",
    "WAIT_CONFIRM": "WAIT",
    "CONFIRM": "WAIT",
    "READY": "IDLE",
    "IDLE": "IDLE",
    "RUN": "RUNNING",
    "RUNNING": "RUNNING",
    "DONE": "DONE",
    "ERROR": "ERROR",
}


def normalize_status(status: str) -> str:
    normalized = status.strip().upper()
    try:
        return STATUS_ALIASES[normalized]
    except KeyError as exc:
        allowed = ", ".join(sorted(STATUS_ALIASES))
        raise ValueError(f"unknown pager status {status!r}; expected one of {allowed}") from exc


def _wire_token(value: str, max_len: int = 12) -> str:
    token = "".join(ch if ch.isalnum() or ch in ".%-_" else "_" for ch in value.strip())
    return (token or "NA")[:max_len]


@dataclass(frozen=True)
class PagerSnapshot:
    state: str
    running: int
    waiting: int
    done: int
    balance: str = "NA"
    event: str = "NONE"

    def to_wire(self) -> str:
        balance = _wire_token(self.balance)
        return (
            f"STATE {self.state} RUN={self.running} WAIT={self.waiting} "
            f"DONE={self.done} BAL={balance} EV={self.event}\n"
        )


class PagerAggregator:
    def __init__(self, balance: str = "NA", wait_alert_interval: float = 30.0) -> None:
        self.balance = balance
        self.wait_alert_interval = wait_alert_interval
        self._tasks: dict[str, str] = {}
        self._done_count = 0
        self._pending_done_event = False
        self._pending_error_event = False
        self._last_wait_alert_at: float | None = None

    def update(self, task_id: str, status: str, now: float | None = None) -> PagerSnapshot:
        state = normalize_status(status)
        previous = self._tasks.get(task_id)

        if state == "DONE" and previous != "DONE":
            self._done_count += 1
            self._pending_done_event = True

        if state == "ERROR":
            self._pending_error_event = True

        self._tasks[task_id] = state
        return self.snapshot(now=now)

    def snapshot(self, now: float | None = None) -> PagerSnapshot:
        current_time = time.monotonic() if now is None else now
        running = sum(1 for status in self._tasks.values() if status == "RUNNING")
        waiting = sum(1 for status in self._tasks.values() if status == "WAIT")
        has_error = any(status == "ERROR" for status in self._tasks.values())

        if has_error:
            state = "ERROR"
        elif waiting:
            state = "WAIT"
        elif running:
            state = "RUNNING"
        elif self._pending_done_event:
            state = "DONE"
        else:
            state = "IDLE"

        event = "NONE"
        if self._pending_error_event:
            event = "ERROR"
            self._pending_error_event = False
        elif waiting and self._wait_alert_due(current_time):
            event = "WAIT"
            self._last_wait_alert_at = current_time
        elif state == "DONE" and self._pending_done_event:
            event = "DONE"
            self._pending_done_event = False

        return PagerSnapshot(
            state=state,
            running=running,
            waiting=waiting,
            done=self._done_count,
            balance=self.balance,
            event=event,
        )

    def _wait_alert_due(self, now: float) -> bool:
        return (
            self._last_wait_alert_at is None
            or now - self._last_wait_alert_at >= self.wait_alert_interval
        )
