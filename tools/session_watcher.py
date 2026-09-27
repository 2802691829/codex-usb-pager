from __future__ import annotations

import json
from pathlib import Path
import re


SESSION_ID_RE = re.compile(
    r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\.jsonl$",
    re.IGNORECASE,
)
INTERNAL_REVIEW_PREFIXES = (
    "The following is the Codex agent history whose request action you are assessing.",
    "The following is the Codex agent history added since your last approval assessment.",
)


class SessionLogWatcher:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self._offsets: dict[Path, int] = {}
        self._ignored_turns: set[Path] = set()
        for path in self._session_files():
            try:
                self._offsets[path] = path.stat().st_size
            except OSError:
                continue

    def _session_files(self) -> list[Path]:
        if not self.root.exists():
            return []
        return list(self.root.rglob("*.jsonl"))

    @staticmethod
    def _session_id(path: Path) -> str | None:
        match = SESSION_ID_RE.search(path.name)
        return match.group(1) if match else None

    def poll_events(self) -> list[tuple[str, str]]:
        detected: list[tuple[str, str]] = []

        for path in self._session_files():
            start = self._offsets.get(path, 0)
            try:
                size = path.stat().st_size
                if size <= start:
                    self._offsets[path] = size
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

            session_id = self._session_id(path)
            if not session_id:
                continue
            for raw_line in chunk[:complete_length].splitlines():
                try:
                    event = json.loads(raw_line.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    continue
                if event.get("type") != "event_msg":
                    continue
                event_type = event.get("payload", {}).get("type")
                if event_type == "user_message":
                    message = event.get("payload", {}).get("message", "")
                    if (
                        isinstance(message, str)
                        and message.startswith(INTERNAL_REVIEW_PREFIXES)
                    ):
                        self._ignored_turns.add(path)
                        continue
                    self._ignored_turns.discard(path)
                    detected.append((session_id, "UserPromptSubmit"))
                elif event_type in {"task_complete", "turn_aborted"}:
                    if path in self._ignored_turns:
                        self._ignored_turns.discard(path)
                        continue
                    if event_type == "turn_aborted":
                        detected.append((session_id, "TurnAborted"))
                        continue
                    detected.append((session_id, "Stop"))

        return detected

    def poll(self) -> list[str]:
        session_ids: list[str] = []
        for session_id, event_name in self.poll_events():
            if event_name == "UserPromptSubmit" and session_id not in session_ids:
                session_ids.append(session_id)
        return session_ids
