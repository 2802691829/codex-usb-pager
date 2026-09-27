import json
from pathlib import Path

from weekly_balance import WeeklyBalanceWatcher, parse_weekly_remaining


def token_event(
    used: object,
    minutes: object = 10080,
    timestamp: str = "2026-07-23T13:43:21.210Z",
) -> dict:
    return {
        "timestamp": timestamp,
        "type": "event_msg",
        "payload": {
            "type": "token_count",
            "rate_limits": {
                "primary": {
                    "used_percent": used,
                    "window_minutes": minutes,
                }
            },
        },
    }


def append_event(path: Path, event: dict, newline: bool = True) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, separators=(",", ":")))
        if newline:
            handle.write("\n")


def test_converts_weekly_used_to_remaining() -> None:
    assert parse_weekly_remaining(token_event(12.0)) == 88
    assert parse_weekly_remaining(token_event(0)) == 100
    assert parse_weekly_remaining(token_event(100)) == 0
    assert parse_weekly_remaining(token_event(-8)) == 100
    assert parse_weekly_remaining(token_event(108)) == 0


def test_rejects_non_weekly_and_malformed_records() -> None:
    assert parse_weekly_remaining(token_event(12, 300)) is None
    assert parse_weekly_remaining(token_event("12")) is None
    assert parse_weekly_remaining(token_event(True)) is None
    assert parse_weekly_remaining({"type": "event_msg", "payload": {}}) is None
    assert parse_weekly_remaining([]) is None


def test_watcher_bootstraps_existing_records_and_then_reads_only_appends(
    tmp_path: Path,
) -> None:
    path = tmp_path / "rollout.jsonl"
    append_event(path, token_event(10))
    watcher = WeeklyBalanceWatcher(tmp_path)

    assert watcher.poll() == 90

    append_event(path, token_event(12))
    assert watcher.poll() == 88
    assert watcher.poll() is None


def test_watcher_ignores_incomplete_line_until_newline_arrives(tmp_path: Path) -> None:
    path = tmp_path / "rollout.jsonl"
    watcher = WeeklyBalanceWatcher(tmp_path)
    append_event(path, token_event(25), newline=False)

    assert watcher.poll() is None

    with path.open("a", encoding="utf-8") as handle:
        handle.write("\n")
    assert watcher.poll() == 75


def test_watcher_uses_newest_timestamp_across_files(tmp_path: Path) -> None:
    older = tmp_path / "older.jsonl"
    newer = tmp_path / "newer.jsonl"
    append_event(
        newer,
        token_event(20, timestamp="2026-07-23T13:44:00.000Z"),
    )
    append_event(
        older,
        token_event(10, timestamp="2026-07-23T13:43:00.000Z"),
    )

    assert WeeklyBalanceWatcher(tmp_path).poll() == 80


def test_watcher_recovers_when_session_file_is_replaced(tmp_path: Path) -> None:
    path = tmp_path / "rollout.jsonl"
    append_event(path, token_event(10))
    watcher = WeeklyBalanceWatcher(tmp_path)
    assert watcher.poll() == 90

    path.write_text(
        json.dumps(token_event(30), separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    assert watcher.poll() == 70
