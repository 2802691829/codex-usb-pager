from __future__ import annotations

import argparse
import msvcrt
from pathlib import Path
import sqlite3
import tempfile
import time

import psutil

from codex_log_watcher import CodexLogWatcher
from pager_hook_runtime import runtime_db_path
from pager_runtime import RuntimeStore
from pager_state import PagerSnapshot
from pager_transport import send_snapshot
from session_watcher import SessionLogWatcher
from weekly_balance import WeeklyBalanceWatcher


EVENT_POLL_INTERVAL = 0.5
APP_POLL_INTERVAL = 30.0


def run_cycle(store: RuntimeStore, sender, now: float | None = None) -> PagerSnapshot:
    current_time = time.time() if now is None else now
    snapshot = store.snapshot(now=current_time)
    sender(snapshot)
    return snapshot


def chatgpt_is_running(process_names=None) -> bool:
    if process_names is None:
        try:
            process_names = (
                process.info.get("name")
                for process in psutil.process_iter(["name"])
            )
        except (OSError, psutil.Error):
            return True
    return any(
        isinstance(name, str) and name.casefold() == "chatgpt.exe"
        for name in process_names
    )


def process_app_presence(
    store: RuntimeStore,
    app_running: bool,
    sender,
    now: float | None = None,
) -> PagerSnapshot | None:
    if not app_running:
        store.clear_active_tasks()
        return None
    return run_cycle(store, sender, now=now)


def process_prompt_events(
    store: RuntimeStore, watcher, sender, now: float | None = None
) -> PagerSnapshot | None:
    session_ids = watcher() if callable(watcher) else watcher.poll()
    if not session_ids:
        return None

    current_time = time.time() if now is None else now
    changed = False
    for session_id in session_ids:
        changed = (
            store.record(session_id, "UserPromptSubmit", now=current_time)
            or changed
        )
    if not changed:
        return None
    return run_cycle(store, sender, now=current_time)


def process_session_events(
    store: RuntimeStore, watcher, sender, now: float | None = None
) -> PagerSnapshot | None:
    events = watcher() if callable(watcher) else watcher.poll_events()
    if not events:
        return None

    current_time = time.time() if now is None else now
    changed = False
    for session_id, event_name in events:
        changed = store.record(session_id, event_name, now=current_time) or changed
    if not changed:
        return None
    return run_cycle(store, sender, now=current_time)


def poll_event_sources(
    store: RuntimeStore,
    prompt_watcher,
    session_watcher,
    sender,
    now: float | None = None,
) -> list[PagerSnapshot]:
    snapshots = []
    for watcher in (prompt_watcher, session_watcher):
        try:
            snapshot = process_session_events(store, watcher, sender, now=now)
        except (OSError, sqlite3.Error):
            continue
        if snapshot is not None:
            snapshots.append(snapshot)
    return snapshots


def process_balance_update(
    store: RuntimeStore, watcher, sender, now: float | None = None
) -> PagerSnapshot | None:
    remaining = watcher() if callable(watcher) else watcher.poll()
    if remaining is None or store.weekly_balance() == str(remaining):
        return None

    store.set_weekly_balance(remaining)
    return run_cycle(store, sender, now=now)


def acquire_lock():
    lock_path = Path(tempfile.gettempdir()) / "codex_pager_daemon.lock"
    handle = lock_path.open("a+b")
    if handle.tell() == 0:
        handle.write(b"0")
        handle.flush()
    handle.seek(0)
    try:
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        handle.close()
        return None
    return handle


def main() -> int:
    parser = argparse.ArgumentParser(description="Continuously send Codex pager heartbeats.")
    parser.add_argument("--once", action="store_true", help="Send one aggregate snapshot and exit.")
    parser.add_argument("--interval", type=float, default=2.0)
    args = parser.parse_args()

    lock = acquire_lock()
    if lock is None:
        return 0

    store = RuntimeStore(runtime_db_path())
    prompt_watcher = CodexLogWatcher(Path.home() / ".codex" / "logs_2.sqlite")
    watcher = SessionLogWatcher(Path.home() / ".codex" / "sessions")
    balance_watcher = WeeklyBalanceWatcher(Path.home() / ".codex" / "sessions")
    interval = max(0.5, args.interval)
    next_heartbeat = 0.0
    next_app_probe = 0.0
    app_running = True
    while True:
        current_monotonic = time.monotonic()
        if not args.once and current_monotonic >= next_app_probe:
            detected = chatgpt_is_running()
            if detected != app_running:
                app_running = detected
                if app_running:
                    next_heartbeat = 0.0
                else:
                    store.clear_active_tasks()
            next_app_probe = current_monotonic + APP_POLL_INTERVAL
        if not app_running:
            time.sleep(EVENT_POLL_INTERVAL)
            continue
        event_snapshots = poll_event_sources(
            store, prompt_watcher, watcher, send_snapshot
        )
        if event_snapshots:
            next_heartbeat = current_monotonic + interval
        balance_snapshot = process_balance_update(
            store, balance_watcher, send_snapshot
        )
        if balance_snapshot is not None:
            next_heartbeat = current_monotonic + interval
        elif current_monotonic >= next_heartbeat:
            run_cycle(store, send_snapshot)
            next_heartbeat = current_monotonic + interval
        if args.once:
            return 0
        time.sleep(EVENT_POLL_INTERVAL)


if __name__ == "__main__":
    raise SystemExit(main())
