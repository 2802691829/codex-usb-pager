from pathlib import Path
import sqlite3

from codex_log_watcher import CodexLogWatcher


CREATE_LOGS = """
CREATE TABLE logs (
    id INTEGER PRIMARY KEY,
    ts TEXT,
    ts_nanos INTEGER,
    level TEXT,
    target TEXT,
    feedback_log_body TEXT,
    module_path TEXT,
    file TEXT,
    line INTEGER,
    thread_id TEXT,
    process_uuid TEXT,
    estimated_bytes INTEGER
)
"""


def insert_log(
    path: Path,
    *,
    target: str,
    body: str,
    thread_id: str | None,
) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            INSERT INTO logs(target, feedback_log_body, thread_id)
            VALUES (?, ?, ?)
            """,
            (target, body, thread_id),
        )


def test_ignores_stale_rows_and_emits_new_user_input(tmp_path: Path) -> None:
    path = tmp_path / "logs_2.sqlite"
    with sqlite3.connect(path) as connection:
        connection.execute(CREATE_LOGS)
    insert_log(
        path,
        target="codex_core::session::handlers",
        body="Submission op: UserInput stale",
        thread_id="old",
    )
    watcher = CodexLogWatcher(path)
    assert watcher.poll_events() == []

    insert_log(path, target="other", body="noise", thread_id="noise")
    insert_log(
        path,
        target="codex_core::session::handlers",
        body="session_loop Submission sub=Submission op: UserInput text",
        thread_id="thread-7",
    )
    assert watcher.poll_events() == [("thread-7", "UserPromptSubmit")]
    assert watcher.poll_events() == []


def test_missing_thread_is_ignored_but_cursor_advances(tmp_path: Path) -> None:
    path = tmp_path / "logs_2.sqlite"
    with sqlite3.connect(path) as connection:
        connection.execute(CREATE_LOGS)
    watcher = CodexLogWatcher(path)
    assert watcher.poll_events() == []
    insert_log(
        path,
        target="codex_core::session::handlers",
        body="Submission op: UserInput",
        thread_id=None,
    )
    assert watcher.poll_events() == []
    assert watcher.poll_events() == []


def test_missing_database_recovers_after_creation(tmp_path: Path) -> None:
    path = tmp_path / "logs_2.sqlite"
    watcher = CodexLogWatcher(path)
    assert watcher.poll_events() == []
    with sqlite3.connect(path) as connection:
        connection.execute(CREATE_LOGS)
    assert watcher.poll_events() == []
    insert_log(
        path,
        target="codex_core::session::handlers",
        body="Submission op: UserInput",
        thread_id="thread-new",
    )
    assert watcher.poll_events() == [("thread-new", "UserPromptSubmit")]


def test_database_replacement_reinitializes_without_replaying(tmp_path: Path) -> None:
    path = tmp_path / "logs_2.sqlite"
    with sqlite3.connect(path) as connection:
        connection.execute(CREATE_LOGS)
    watcher = CodexLogWatcher(path)
    assert watcher.poll_events() == []
    connection.close()
    path.unlink()
    with sqlite3.connect(path) as connection:
        connection.execute(CREATE_LOGS)
    insert_log(
        path,
        target="codex_core::session::handlers",
        body="Submission op: UserInput replacement-stale",
        thread_id="stale-after-replace",
    )
    assert watcher.poll_events() == []
