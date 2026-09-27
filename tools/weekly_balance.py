from __future__ import annotations

import json
from pathlib import Path


WEEKLY_WINDOW_MINUTES = 10080


def parse_weekly_remaining(event: object) -> int | None:
    if not isinstance(event, dict) or event.get("type") != "event_msg":
        return None

    payload = event.get("payload")
    if not isinstance(payload, dict) or payload.get("type") != "token_count":
        return None

    limits = payload.get("rate_limits")
    primary = limits.get("primary") if isinstance(limits, dict) else None
    if (
        not isinstance(primary, dict)
        or primary.get("window_minutes") != WEEKLY_WINDOW_MINUTES
    ):
        return None

    used = primary.get("used_percent")
    if not isinstance(used, (int, float)) or isinstance(used, bool):
        return None
    return max(0, min(100, 100 - int(round(used))))


class WeeklyBalanceWatcher:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self._offsets: dict[Path, int] = {}
        self._modified_ns: dict[Path, int] = {}

    def _session_files(self) -> list[Path]:
        if not self.root.exists():
            return []
        return list(self.root.rglob("*.jsonl"))

    def poll(self) -> int | None:
        newest: tuple[str, int] | None = None

        for path in self._session_files():
            start = self._offsets.get(path, 0)
            previous_modified = self._modified_ns.get(path)
            try:
                stat = path.stat()
                if stat.st_size < start or (
                    stat.st_size == start
                    and previous_modified is not None
                    and stat.st_mtime_ns != previous_modified
                ):
                    start = 0
                if stat.st_size <= start:
                    self._offsets[path] = start
                    self._modified_ns[path] = stat.st_mtime_ns
                    continue
                with path.open("rb") as handle:
                    handle.seek(start)
                    chunk = handle.read()
            except OSError:
                continue

            complete_length = chunk.rfind(b"\n") + 1
            if complete_length == 0:
                continue
            self._offsets[path] = start + complete_length
            self._modified_ns[path] = stat.st_mtime_ns

            for raw_line in chunk[:complete_length].splitlines():
                try:
                    event = json.loads(raw_line.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    continue
                remaining = parse_weekly_remaining(event)
                timestamp = event.get("timestamp") if isinstance(event, dict) else None
                if remaining is None or not isinstance(timestamp, str):
                    continue
                candidate = (timestamp, remaining)
                if newest is None or candidate[0] >= newest[0]:
                    newest = candidate

        return newest[1] if newest is not None else None
