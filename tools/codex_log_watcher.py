from __future__ import annotations

from pathlib import Path
import sqlite3


TARGET = "codex_core::session::handlers"


class CodexLogWatcher:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.last_id: int | None = None
        self._identity: tuple[int, int] | None = None

    def _file_identity(self) -> tuple[int, int]:
        stat = self.path.stat()
        return stat.st_dev, stat.st_ino

    def _connect(self) -> sqlite3.Connection:
        uri = self.path.resolve().as_uri() + "?mode=ro"
        connection = sqlite3.connect(uri, uri=True, timeout=0.02)
        connection.execute("PRAGMA query_only = ON")
        connection.execute("PRAGMA busy_timeout = 20")
        return connection

    def poll_events(self) -> list[tuple[str, str]]:
        try:
            identity = self._file_identity()
            if identity != self._identity:
                self._identity = identity
                self.last_id = None
            connection = self._connect()
            try:
                if self.last_id is None:
                    row = connection.execute(
                        "SELECT COALESCE(MAX(id), 0) FROM logs"
                    ).fetchone()
                    self.last_id = int(row[0])
                    return []
                rows = connection.execute(
                    """
                    SELECT id, target, feedback_log_body, thread_id
                    FROM logs
                    WHERE id > ?
                    ORDER BY id
                    """,
                    (self.last_id,),
                ).fetchall()
            finally:
                connection.close()
        except (OSError, sqlite3.Error):
            self._identity = None
            self.last_id = None
            return []

        events: list[tuple[str, str]] = []
        for row_id, target, body, thread_id in rows:
            self.last_id = max(self.last_id, int(row_id))
            if (
                target == TARGET
                and isinstance(body, str)
                and "Submission" in body
                and "op: UserInput" in body
                and isinstance(thread_id, str)
                and thread_id
            ):
                events.append((thread_id, "UserPromptSubmit"))
        return events
