from pager_state import PagerAggregator, PagerSnapshot, normalize_status


def test_waiting_task_has_priority_over_running_tasks():
    pager = PagerAggregator(balance="18")

    snapshot = pager.update("task-a", "running", now=10.0)
    snapshot = pager.update("task-b", "wait", now=11.0)

    assert snapshot.state == "WAIT"
    assert snapshot.running == 1
    assert snapshot.waiting == 1
    assert snapshot.done == 0
    assert snapshot.event == "WAIT"


def test_done_event_is_reported_once_when_no_task_is_active():
    pager = PagerAggregator(balance="NA")

    snapshot = pager.update("task-a", "done", now=20.0)
    assert snapshot.state == "DONE"
    assert snapshot.done == 1
    assert snapshot.event == "DONE"

    snapshot = pager.snapshot(now=21.0)
    assert snapshot.state == "IDLE"
    assert snapshot.done == 1
    assert snapshot.event == "NONE"


def test_wait_alert_is_throttled_while_confirmation_remains_pending():
    pager = PagerAggregator(wait_alert_interval=30.0)

    first = pager.update("task-a", "wait", now=0.0)
    second = pager.snapshot(now=10.0)
    third = pager.snapshot(now=31.0)

    assert first.event == "WAIT"
    assert second.event == "NONE"
    assert third.event == "WAIT"


def test_snapshot_formats_wire_line_for_firmware_parser():
    snapshot = PagerSnapshot(
        state="RUNNING",
        running=2,
        waiting=0,
        done=4,
        balance="18",
        event="NONE",
    )

    assert snapshot.to_wire() == "STATE RUNNING RUN=2 WAIT=0 DONE=4 BAL=18 EV=NONE\n"


def test_legacy_status_aliases_are_normalized():
    assert normalize_status("ALERT") == "WAIT"
    assert normalize_status("READY") == "IDLE"
    assert normalize_status("RUNNING") == "RUNNING"
