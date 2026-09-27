from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import tomllib

from pager_runtime import RuntimeStore
from pager_transport import send_snapshot


COMMAND_EVENTS = {
    "RUNNING": "UserPromptSubmit",
    "ALERT": "PermissionRequest",
    "WAIT": "PermissionRequest",
    "DONE": "Stop",
}
_USE_CONFIG = object()
AUTO_REVIEW_WAIT_DELAY = 8.0


def event_name_for(command: str, payload: dict) -> str | None:
    return payload.get("hook_event_name") or COMMAND_EVENTS.get(command.upper())


def configured_approvals_reviewer(config_path: Path | None = None) -> str | None:
    path = config_path or Path.home() / ".codex" / "config.toml"
    try:
        with path.open("rb") as handle:
            config = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError):
        return None
    value = config.get("approvals_reviewer")
    return value if isinstance(value, str) else None


def permission_wait_delay(
    approvals_reviewer: str | None | object = _USE_CONFIG,
) -> float:
    reviewer = (
        configured_approvals_reviewer()
        if approvals_reviewer is _USE_CONFIG
        else approvals_reviewer
    )
    return AUTO_REVIEW_WAIT_DELAY if reviewer == "auto_review" else 0.0


def runtime_event_name(command: str, payload: dict) -> str | None:
    event_name = event_name_for(command, payload)
    if event_name == "Stop":
        return None
    return event_name


def runtime_db_path() -> Path:
    return Path(tempfile.gettempdir()) / "codex_pager_runtime.sqlite"


def start_daemon(tools_dir: Path) -> None:
    creationflags = 0
    if os.name == "nt":
        creationflags = 0x08000000 | 0x00000008 | 0x00000200
    subprocess.Popen(
        [sys.executable, str(tools_dir / "pager_daemon.py")],
        cwd=str(tools_dir.parent.parent),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
        creationflags=creationflags,
    )


def main(command: str, raw_payload: str) -> int:
    try:
        payload = json.loads(raw_payload) if raw_payload.strip() else {}
    except json.JSONDecodeError:
        payload = {}

    event_name = runtime_event_name(command, payload)
    session_id = (
        payload.get("session_id")
        or payload.get("thread_id")
        or payload.get("thread-id")
    )
    store = RuntimeStore(runtime_db_path())
    if event_name and session_id:
        now = time.time()
        wait_delay = (
            permission_wait_delay()
            if event_name == "PermissionRequest"
            else 0.0
        )
        store.record(
            session_id,
            event_name,
            now=now,
            wait_event_delay=wait_delay,
        )
        send_snapshot(store.snapshot(now=now))
    start_daemon(Path(__file__).resolve().parent)

    if event_name == "Stop":
        print("{}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else "RUNNING", sys.stdin.read()))
