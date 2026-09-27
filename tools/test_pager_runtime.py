from pathlib import Path
import json
import sqlite3

import pager_hook_runtime
from pager_daemon import (
    chatgpt_is_running,
    process_app_presence,
    process_balance_update,
    run_cycle,
)
from pager_hook_runtime import event_name_for, permission_wait_delay, runtime_event_name
from pager_runtime import RuntimeStore


def make_store(tmp_path: Path) -> RuntimeStore:
    return RuntimeStore(tmp_path / "runtime.sqlite")


def test_existing_runtime_database_adds_wait_notify_deadline(tmp_path: Path) -> None:
    path = tmp_path / "runtime.sqlite"
    with sqlite3.connect(path) as con:
        con.executescript(
            """
            CREATE TABLE tasks (
                session_id TEXT PRIMARY KEY,
                state TEXT NOT NULL,
                updated_at REAL NOT NULL,
                done_at REAL,
                wait_pending INTEGER NOT NULL DEFAULT 0,
                done_pending INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE meta (key TEXT PRIMARY KEY, value INTEGER NOT NULL);
            """
        )
    store = RuntimeStore(path)
    with store._connect() as con:
        columns = {row[1] for row in con.execute("PRAGMA table_info(tasks)")}
    assert "wait_notify_at" in columns


def test_auto_review_wait_beep_is_deferred_and_emitted_once(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store.record("task-a", "UserPromptSubmit", now=100.0)
    store.record("task-a", "PermissionRequest", now=101.0, wait_event_delay=8.0)

    early = store.snapshot(now=108.9)
    due = store.snapshot(now=109.0)
    repeated = store.snapshot(now=110.0)

    assert early.state == "WAIT"
    assert early.event == "NONE"
    assert due.event == "WAIT"
    assert repeated.event == "NONE"


def test_auto_review_resolution_cancels_deferred_wait_beep(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store.record("task-a", "UserPromptSubmit", now=100.0)
    store.record("task-a", "PermissionRequest", now=101.0, wait_event_delay=8.0)
    assert store.snapshot(now=102.0).event == "NONE"

    store.record("task-a", "PreToolUse", now=105.0)
    resumed = store.snapshot(now=110.0)
    assert resumed.state == "RUNNING"
    assert resumed.event == "NONE"


def test_running_hook_keeps_heartbeat_running(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store.record("task-a", "UserPromptSubmit", now=100.0)

    first = store.snapshot(now=101.0)
    later = store.snapshot(now=120.0)

    assert first.state == "RUNNING"
    assert first.running == 1
    assert later.state == "RUNNING"
    assert later.running == 1


def test_wait_has_priority_and_post_tool_clears_it(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store.record("task-a", "UserPromptSubmit", now=100.0)
    store.record("task-b", "UserPromptSubmit", now=100.0)
    store.record("task-b", "PermissionRequest", now=101.0)

    waiting = store.snapshot(now=102.0)
    store.record("task-b", "PostToolUse", now=103.0)
    running = store.snapshot(now=104.0)

    assert waiting.state == "WAIT"
    assert waiting.running == 1
    assert waiting.waiting == 1
    assert waiting.event == "WAIT"
    assert running.state == "RUNNING"
    assert running.running == 2
    assert running.waiting == 0


def test_pre_tool_clears_wait_before_long_command_starts(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store.record("task-a", "UserPromptSubmit", now=100.0)
    store.record("task-a", "PermissionRequest", now=101.0)

    waiting = store.snapshot(now=102.0)
    store.record("task-a", "PreToolUse", now=103.0)
    running = store.snapshot(now=104.0)

    assert waiting.state == "WAIT"
    assert running.state == "RUNNING"
    assert running.running == 1
    assert running.waiting == 0


def test_global_hook_config_registers_pre_tool_running_event() -> None:
    config_path = Path(__file__).with_name("global_hooks.json")
    config = json.loads(config_path.read_text(encoding="utf-8"))

    hooks = config["hooks"]["PreToolUse"]
    assert hooks[0]["hooks"][0]["command"].endswith("codex_pager.py RUNNING")


def test_stop_emits_done_once_then_becomes_idle(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store.record("task-a", "UserPromptSubmit", now=100.0)
    store.record("task-a", "Stop", now=110.0)

    done = store.snapshot(now=111.0)
    repeated = store.snapshot(now=112.0)
    idle = store.snapshot(now=116.0)

    assert done.state == "DONE"
    assert done.done == 1
    assert done.event == "DONE"
    assert repeated.event == "NONE"
    assert idle.state == "IDLE"


def test_duplicate_stop_does_not_double_count(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store.record("task-a", "UserPromptSubmit", now=100.0)
    store.record("task-a", "Stop", now=110.0)
    store.record("task-a", "Stop", now=111.0)

    assert store.snapshot(now=112.0).done == 1


def test_done_beep_waits_until_every_running_task_finishes(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store.record("task-a", "UserPromptSubmit", now=100.0)
    store.record("task-b", "UserPromptSubmit", now=100.0)

    store.record("task-a", "Stop", now=110.0)
    still_running = store.snapshot(now=111.0)

    assert still_running.state == "RUNNING"
    assert still_running.running == 1
    assert still_running.event == "NONE"

    store.record("task-b", "Stop", now=112.0)
    all_done = store.snapshot(now=113.0)
    repeated = store.snapshot(now=114.0)

    assert all_done.state == "DONE"
    assert all_done.running == 0
    assert all_done.event == "DONE"
    assert repeated.event == "NONE"


def test_duplicate_running_event_reports_no_change_but_refreshes_timestamp(
    tmp_path: Path,
) -> None:
    store = make_store(tmp_path)

    assert store.record("thread-a", "UserPromptSubmit", now=10.0) is True
    assert store.record("thread-a", "UserPromptSubmit", now=10.1) is False

    with store._connect() as con:
        updated_at = con.execute(
            "SELECT updated_at FROM tasks WHERE session_id = ?",
            ("thread-a",),
        ).fetchone()[0]

    assert updated_at == 10.1
    assert store.snapshot(now=10.2).running == 1


def test_refreshed_running_task_blocks_deferred_done_beep_past_ttl(
    tmp_path: Path,
) -> None:
    store = make_store(tmp_path)
    store.record("task-a", "UserPromptSubmit", now=0.0)
    store.record("task-b", "UserPromptSubmit", now=0.0)
    store.record("task-a", "Stop", now=10.0)

    assert store.snapshot(now=11.0).event == "NONE"

    assert store.record("task-b", "PostToolUse", now=905.0) is False
    still_running = store.snapshot(now=910.0)

    assert still_running.state == "RUNNING"
    assert still_running.running == 1
    assert still_running.event == "NONE"


def test_hook_event_prefers_official_stdin_payload() -> None:
    assert event_name_for("RUNNING", {"hook_event_name": "PermissionRequest"}) == "PermissionRequest"
    assert event_name_for("ALERT", {}) == "PermissionRequest"


def test_auto_review_permission_request_uses_eight_second_delay() -> None:
    assert permission_wait_delay("auto_review") == 8.0


def test_manual_permission_request_keeps_immediate_wait_alert() -> None:
    assert permission_wait_delay(None) == 0.0


def test_stop_hook_is_ignored_in_favor_of_semantic_session_event() -> None:
    assert runtime_event_name("DONE", {"hook_event_name": "Stop"}) is None


def test_daemon_cycle_sends_current_aggregate(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store.record("task-a", "UserPromptSubmit", now=100.0)
    sent = []

    snapshot = run_cycle(store, sent.append, now=101.0)

    assert snapshot.state == "RUNNING"
    assert sent == [snapshot]


def test_daemon_sends_nothing_and_clears_active_tasks_when_app_closes(
    tmp_path: Path,
) -> None:
    store = make_store(tmp_path)
    store.record("task-a", "UserPromptSubmit", now=100.0)
    sent = []

    assert process_app_presence(store, app_running=False, sender=sent.append) is None
    assert sent == []
    assert store.snapshot(now=101.0).state == "IDLE"


def test_daemon_resumes_with_idle_snapshot_when_app_reopens(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store.record("task-a", "UserPromptSubmit", now=100.0)
    store.clear_active_tasks()
    sent = []

    snapshot = process_app_presence(
        store,
        app_running=True,
        sender=sent.append,
        now=101.0,
    )

    assert snapshot is not None
    assert snapshot.state == "IDLE"
    assert sent == [snapshot]


def test_app_probe_requires_chatgpt_process_not_codex_worker() -> None:
    assert chatgpt_is_running(["ChatGPT.exe", "codex.exe"])
    assert not chatgpt_is_running(["codex.exe", "python.exe"])


def test_weekly_balance_is_cached_and_added_to_snapshot(tmp_path: Path) -> None:
    path = tmp_path / "runtime.sqlite"
    first = RuntimeStore(path)
    assert first.snapshot(now=100.0).balance == "NA"
    first.set_weekly_balance(88)

    restarted = RuntimeStore(path)
    assert restarted.weekly_balance() == "88"
    assert restarted.snapshot(now=101.0).balance == "88"


def test_weekly_balance_rejects_out_of_range_values(tmp_path: Path) -> None:
    store = make_store(tmp_path)

    for invalid in (-1, 101):
        try:
            store.set_weekly_balance(invalid)
        except ValueError:
            pass
        else:
            raise AssertionError(f"accepted invalid weekly balance {invalid}")


def test_daemon_sends_immediately_when_balance_changes(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    sent = []

    snapshot = process_balance_update(
        store,
        watcher=lambda: 88,
        sender=sent.append,
        now=100.0,
    )

    assert snapshot is not None
    assert snapshot.balance == "88"
    assert sent == [snapshot]


def test_daemon_does_not_send_when_watcher_has_no_new_balance(
    tmp_path: Path,
) -> None:
    store = make_store(tmp_path)
    sent = []

    assert (
        process_balance_update(
            store,
            watcher=lambda: None,
            sender=sent.append,
            now=100.0,
        )
        is None
    )
    assert sent == []


def test_daemon_does_not_resend_unchanged_balance(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store.set_weekly_balance(88)
    sent = []

    assert (
        process_balance_update(
            store,
            watcher=lambda: 88,
            sender=sent.append,
            now=100.0,
        )
        is None
    )
    assert sent == []


def test_hook_sends_running_immediately_but_defers_done_to_session_log(
    tmp_path: Path, monkeypatch
) -> None:
    sent = []
    db_path = tmp_path / "runtime.sqlite"

    monkeypatch.setattr(pager_hook_runtime, "runtime_db_path", lambda: db_path)
    monkeypatch.setattr(pager_hook_runtime, "send_snapshot", sent.append, raising=False)
    monkeypatch.setattr(pager_hook_runtime, "start_daemon", lambda _tools_dir: None)

    payload = json.dumps({"thread-id": "task-a"})
    assert pager_hook_runtime.main("RUNNING", payload) == 0
    assert [snapshot.state for snapshot in sent] == ["RUNNING"]

    assert pager_hook_runtime.main("DONE", payload) == 0
    assert [snapshot.state for snapshot in sent] == ["RUNNING"]
    assert RuntimeStore(db_path).snapshot(now=100.0).state == "RUNNING"


def test_hook_records_auto_review_wait_without_immediate_beep(
    tmp_path: Path, monkeypatch
) -> None:
    sent = []
    db_path = tmp_path / "runtime.sqlite"
    payload = json.dumps(
        {"hook_event_name": "PermissionRequest", "thread_id": "task-a"}
    )
    monkeypatch.setattr(pager_hook_runtime, "runtime_db_path", lambda: db_path)
    monkeypatch.setattr(pager_hook_runtime, "send_snapshot", sent.append)
    monkeypatch.setattr(pager_hook_runtime, "start_daemon", lambda _tools_dir: None)
    monkeypatch.setattr(pager_hook_runtime.time, "time", lambda: 100.0)
    monkeypatch.setattr(
        pager_hook_runtime,
        "configured_approvals_reviewer",
        lambda _path=None: "auto_review",
    )

    assert pager_hook_runtime.main("ALERT", payload) == 0
    assert sent[0].state == "WAIT"
    assert sent[0].event == "NONE"
    assert RuntimeStore(db_path).snapshot(now=108.0).event == "WAIT"


def test_hook_without_task_id_does_not_create_manual_running_state(
    tmp_path: Path, monkeypatch
) -> None:
    sent = []
    db_path = tmp_path / "runtime.sqlite"

    monkeypatch.setattr(pager_hook_runtime, "runtime_db_path", lambda: db_path)
    monkeypatch.setattr(pager_hook_runtime, "send_snapshot", sent.append, raising=False)
    monkeypatch.setattr(pager_hook_runtime, "start_daemon", lambda _tools_dir: None)

    assert pager_hook_runtime.main("RUNNING", "{}") == 0
    assert sent == []
    assert RuntimeStore(db_path).snapshot(now=100.0).state == "IDLE"
