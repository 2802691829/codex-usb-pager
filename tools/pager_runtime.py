from __future__ import annotations

from pathlib import Path
import sqlite3

from pager_state import PagerSnapshot


EVENT_STATES = {
    "UserPromptSubmit": "RUNNING",
    "PreToolUse": "RUNNING",
    "PostToolUse": "RUNNING",
    "PermissionRequest": "WAIT",
    "Stop": "DONE",
    "TurnAborted": "IDLE",
}


class RuntimeStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as con:
            con.executescript(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    session_id TEXT PRIMARY KEY,
                    state TEXT NOT NULL,
                    updated_at REAL NOT NULL,
                    done_at REAL,
                    wait_pending INTEGER NOT NULL DEFAULT 0,
                    done_pending INTEGER NOT NULL DEFAULT 0,
                    wait_notify_at REAL
                );
                CREATE TABLE IF NOT EXISTS meta (
                    key TEXT PRIMARY KEY,
                    value INTEGER NOT NULL
                );
                INSERT OR IGNORE INTO meta(key, value) VALUES ('done_count', 0);
                INSERT OR IGNORE INTO meta(key, value) VALUES ('weekly_balance', -1);
                """
            )
            columns = {row[1] for row in con.execute("PRAGMA table_info(tasks)")}
            if "wait_notify_at" not in columns:
                con.execute("ALTER TABLE tasks ADD COLUMN wait_notify_at REAL")

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.path, timeout=3.0)
        con.execute("PRAGMA busy_timeout = 3000")
        return con

    def record(
        self,
        session_id: str,
        event_name: str,
        now: float,
        wait_event_delay: float = 0.0,
    ) -> bool:
        state = EVENT_STATES.get(event_name)
        if not state or not session_id:
            return False

        with self._connect() as con:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute(
                "SELECT state, wait_pending, done_pending, wait_notify_at FROM tasks WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            previous = row[0] if row else None
            wait_pending = row[1] if row else 0
            done_pending = row[2] if row else 0
            wait_notify_at = row[3] if row else None
            if previous == state and state == "RUNNING":
                con.execute(
                    "UPDATE tasks SET updated_at = ? WHERE session_id = ?",
                    (now, session_id),
                )
                return False
            changed = previous != state

            if state == "WAIT":
                wait_pending = int(previous != "WAIT")
                if wait_pending:
                    wait_notify_at = now + max(0.0, wait_event_delay)
                done_pending = 0
            elif state == "DONE":
                if previous != "DONE":
                    con.execute("UPDATE meta SET value = value + 1 WHERE key = 'done_count'")
                    done_pending = 1
                wait_pending = 0
                wait_notify_at = None
            else:
                wait_pending = 0
                done_pending = 0
                wait_notify_at = None

            con.execute(
                """
                INSERT INTO tasks(session_id, state, updated_at, done_at, wait_pending, done_pending, wait_notify_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    state = excluded.state,
                    updated_at = excluded.updated_at,
                    done_at = excluded.done_at,
                    wait_pending = excluded.wait_pending,
                    done_pending = excluded.done_pending,
                    wait_notify_at = excluded.wait_notify_at
                """,
                (
                    session_id,
                    state,
                    now,
                    now if state == "DONE" else None,
                    wait_pending,
                    done_pending,
                    wait_notify_at,
                ),
            )
            return changed

    def set_weekly_balance(self, percent: int) -> None:
        if not isinstance(percent, int) or isinstance(percent, bool):
            raise TypeError("weekly balance must be an integer")
        if percent < 0 or percent > 100:
            raise ValueError("weekly balance must be between 0 and 100")
        with self._connect() as con:
            con.execute(
                "UPDATE meta SET value = ? WHERE key = 'weekly_balance'",
                (percent,),
            )

    def weekly_balance(self) -> str:
        with self._connect() as con:
            row = con.execute(
                "SELECT value FROM meta WHERE key = 'weekly_balance'"
            ).fetchone()
        if row is None or row[0] < 0:
            return "NA"
        return str(row[0])

    def clear_active_tasks(self) -> None:
        with self._connect() as con:
            con.execute(
                "DELETE FROM tasks WHERE state IN ('RUNNING', 'WAIT')"
            )

    def snapshot(
        self,
        now: float,
        active_ttl: float = 900.0,
        done_hold: float = 5.0,
        balance: str | None = None,
    ) -> PagerSnapshot:
        with self._connect() as con:
            con.execute("BEGIN IMMEDIATE")
            con.execute(
                "DELETE FROM tasks WHERE state != 'DONE' AND updated_at < ?",
                (now - active_ttl,),
            )
            rows = con.execute(
                "SELECT session_id, state, done_at, wait_pending, done_pending, wait_notify_at FROM tasks"
            ).fetchall()
            done_count = con.execute(
                "SELECT value FROM meta WHERE key = 'done_count'"
            ).fetchone()[0]

            running = sum(row[1] == "RUNNING" for row in rows)
            waiting = sum(row[1] == "WAIT" for row in rows)
            recent_done = any(
                row[1] == "DONE" and row[2] is not None and now - row[2] <= done_hold
                for row in rows
            )

            event = "NONE"
            ready_wait_ids = [
                row[0]
                for row in rows
                if row[3] and (row[5] is None or row[5] <= now)
            ]
            if ready_wait_ids:
                event = "WAIT"
                con.executemany(
                    "UPDATE tasks SET wait_pending = 0 WHERE session_id = ?",
                    ((session_id,) for session_id in ready_wait_ids),
                )
            elif not running and not waiting and any(row[4] for row in rows):
                event = "DONE"
                con.execute("UPDATE tasks SET done_pending = 0 WHERE done_pending = 1")

            if waiting:
                state = "WAIT"
            elif running:
                state = "RUNNING"
            elif recent_done:
                state = "DONE"
            else:
                state = "IDLE"

            return PagerSnapshot(
                state=state,
                running=running,
                waiting=waiting,
                done=done_count,
                balance=self.weekly_balance() if balance is None else balance,
                event=event,
            )
