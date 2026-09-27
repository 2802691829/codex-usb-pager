# Weekly Balance Display Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automatically read the remaining Codex seven-day allowance and show it only on the RP2040 pager's idle screen.

**Architecture:** A focused host-side watcher extracts the newest `10080`-minute rate-limit event and persists the remaining integer percentage in the existing SQLite runtime store. The unchanged `BAL` protocol field carries that value to firmware, where a fixed bitmap font is composed into the existing double-buffered scene only for `PAGER_IDLE`.

**Tech Stack:** Python 3, JSONL, SQLite, pytest, C11, Pico SDK, CMake/CTest, RP2040 PIO SPI, ST7789.

## Global Constraints

- Use only `rate_limits.primary` records whose `window_minutes` is exactly `10080`.
- Calculate remaining allowance as `clamp(100 - used_percent, 0, 100)`.
- Keep the existing `STATE ... BAL=<token> ...` wire format.
- Show weekly allowance only in `PAGER_IDLE`.
- Preserve every non-idle scene's existing appearance, motion, and target frame interval.
- Use fixed storage only: no heap allocation, extra frame buffer, or floating-point rendering.
- Show no percentage when no valid current or cached weekly value exists.

---

## File Structure

- Create `tools/weekly_balance.py`: parse rate-limit events and incrementally watch session JSONL files.
- Create `tools/test_weekly_balance.py`: host extraction, precedence, malformed-input, and incremental-read tests.
- Modify `tools/pager_runtime.py`: persist and retrieve the last valid weekly percentage.
- Modify `tools/pager_daemon.py`: poll the weekly watcher and send changed balances immediately.
- Modify `tools/test_pager_runtime.py`: verify cached balance propagation into snapshots.
- Create `ports/rp2040-zero/firmware/include/tiny_font.h`: fixed glyph rendering interface.
- Create `ports/rp2040-zero/firmware/src/tiny_font.c`: glyphs for `WEEK`, digits, and `%`.
- Modify `ports/rp2040-zero/firmware/CMakeLists.txt`: compile the font source.
- Modify `ports/rp2040-zero/firmware/include/display_scene.h`: add balance-aware scene interfaces and an idle layout description.
- Modify `ports/rp2040-zero/firmware/src/display_scene.c`: render the idle label/value and move only the idle Blossom upward.
- Modify `ports/rp2040-zero/firmware/include/display_ui.h`: accept balance updates.
- Modify `ports/rp2040-zero/firmware/src/display_ui.c`: retain the latest balance and invalidate the frame when it changes.
- Modify `ports/rp2040-zero/firmware/src/main.c`: pass parsed `snapshot.balance` to the display.
- Modify `ports/rp2040-zero/tests/test_pager_core.c`: test parsing, idle text layout, and non-idle isolation.
- Modify `ports/rp2040-zero/tests/CMakeLists.txt`: compile the font in host tests.

---

### Task 1: Extract Weekly Remaining Allowance

**Files:**
- Create: `codex_usb_pager/tools/weekly_balance.py`
- Create: `codex_usb_pager/tools/test_weekly_balance.py`

**Interfaces:**
- Produces: `parse_weekly_remaining(event: object) -> int | None`
- Produces: `WeeklyBalanceWatcher(root: Path).poll() -> int | None`

- [ ] **Step 1: Write failing parser and watcher tests**

```python
def token_event(used: object, minutes: object = 10080) -> dict:
    return {
        "timestamp": "2026-07-23T13:43:21.210Z",
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


def test_converts_weekly_used_to_remaining() -> None:
    assert parse_weekly_remaining(token_event(12.0)) == 88
    assert parse_weekly_remaining(token_event(0)) == 100
    assert parse_weekly_remaining(token_event(100)) == 0


def test_rejects_non_weekly_and_malformed_records() -> None:
    assert parse_weekly_remaining(token_event(12, 300)) is None
    assert parse_weekly_remaining(token_event("12")) is None
    assert parse_weekly_remaining({"type": "event_msg", "payload": {}}) is None


def test_watcher_reads_only_new_complete_lines(tmp_path: Path) -> None:
    path = tmp_path / "rollout.jsonl"
    path.write_text(json.dumps(token_event(10)) + "\n", encoding="utf-8")
    watcher = WeeklyBalanceWatcher(tmp_path)
    assert watcher.poll() == 90

    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(token_event(12)) + "\n")
    assert watcher.poll() == 88
    assert watcher.poll() is None
```

- [ ] **Step 2: Run the focused test and verify failure**

Run: `python -m pytest tools/test_weekly_balance.py -q`

Expected: collection fails because `weekly_balance` does not exist.

- [ ] **Step 3: Implement strict parsing and incremental offsets**

```python
def parse_weekly_remaining(event: object) -> int | None:
    if not isinstance(event, dict) or event.get("type") != "event_msg":
        return None
    payload = event.get("payload")
    if not isinstance(payload, dict) or payload.get("type") != "token_count":
        return None
    limits = payload.get("rate_limits")
    primary = limits.get("primary") if isinstance(limits, dict) else None
    if not isinstance(primary, dict) or primary.get("window_minutes") != 10080:
        return None
    used = primary.get("used_percent")
    if not isinstance(used, (int, float)) or isinstance(used, bool):
        return None
    return max(0, min(100, 100 - int(round(used))))
```

`WeeklyBalanceWatcher` must retain one byte offset per path, parse only
newline-terminated UTF-8 JSON records, recover when a file shrinks, and return
only the newest valid percentage observed during that poll. Its first poll
reads existing records so a fresh installation can bootstrap without waiting
for another Codex response.

- [ ] **Step 4: Run focused tests**

Run: `python -m pytest tools/test_weekly_balance.py -q`

Expected: all weekly-balance tests pass.

- [ ] **Step 5: Commit**

```powershell
git add -- codex_usb_pager/tools/weekly_balance.py codex_usb_pager/tools/test_weekly_balance.py
git commit -m "feat: read Codex weekly allowance"
```

### Task 2: Cache and Transmit Weekly Balance

**Files:**
- Modify: `codex_usb_pager/tools/pager_runtime.py`
- Modify: `codex_usb_pager/tools/pager_daemon.py`
- Modify: `codex_usb_pager/tools/test_pager_runtime.py`

**Interfaces:**
- Consumes: `WeeklyBalanceWatcher.poll() -> int | None`
- Produces: `RuntimeStore.set_weekly_balance(percent: int) -> None`
- Produces: `RuntimeStore.weekly_balance() -> str`

- [ ] **Step 1: Add failing persistence and daemon tests**

```python
def test_weekly_balance_is_cached_and_added_to_snapshot(tmp_path: Path) -> None:
    path = tmp_path / "runtime.sqlite"
    first = RuntimeStore(path)
    assert first.snapshot(now=100).balance == "NA"
    first.set_weekly_balance(88)

    restarted = RuntimeStore(path)
    assert restarted.weekly_balance() == "88"
    assert restarted.snapshot(now=101).balance == "88"


def test_daemon_sends_immediately_when_balance_changes(tmp_path: Path) -> None:
    store = RuntimeStore(tmp_path / "runtime.sqlite")
    sent = []
    snapshot = process_balance_update(
        store, watcher=lambda: 88, sender=sent.append, now=100
    )
    assert snapshot is not None
    assert snapshot.balance == "88"
    assert sent == [snapshot]
```

- [ ] **Step 2: Verify focused failures**

Run: `python -m pytest tools/test_pager_runtime.py -q`

Expected: failures report missing `set_weekly_balance`,
`weekly_balance`, and `process_balance_update`.

- [ ] **Step 3: Add SQLite metadata and daemon integration**

Add a `weekly_balance` row to the existing integer `meta` table with sentinel
`-1`. `set_weekly_balance` accepts only `0..100`. `weekly_balance` returns
`"NA"` for the sentinel and a decimal string otherwise. When `snapshot` is
called without an explicit `balance`, it reads this cached value.

```python
def process_balance_update(store, watcher, sender, now=None):
    remaining = watcher() if callable(watcher) else watcher.poll()
    if remaining is None:
        return None
    store.set_weekly_balance(remaining)
    return run_cycle(store, sender, now=now)
```

Construct `WeeklyBalanceWatcher(Path.home() / ".codex" / "sessions")` beside
the existing session watcher. Poll it every daemon loop before the periodic
heartbeat; when it yields a value, call `process_balance_update` and advance
the next heartbeat deadline.

- [ ] **Step 4: Run all host tests**

Run: `python -m pytest tools -q`

Expected: all host tests pass, including cached restoration and `BAL=88`.

- [ ] **Step 5: Commit**

```powershell
git add -- codex_usb_pager/tools/pager_runtime.py codex_usb_pager/tools/pager_daemon.py codex_usb_pager/tools/test_pager_runtime.py
git commit -m "feat: cache and transmit weekly balance"
```

### Task 3: Render Weekly Balance Only in Idle

**Files:**
- Create: `codex_usb_pager/ports/rp2040-zero/firmware/include/tiny_font.h`
- Create: `codex_usb_pager/ports/rp2040-zero/firmware/src/tiny_font.c`
- Modify: `codex_usb_pager/ports/rp2040-zero/firmware/CMakeLists.txt`
- Modify: `codex_usb_pager/ports/rp2040-zero/firmware/include/display_scene.h`
- Modify: `codex_usb_pager/ports/rp2040-zero/firmware/src/display_scene.c`
- Modify: `codex_usb_pager/ports/rp2040-zero/firmware/include/display_ui.h`
- Modify: `codex_usb_pager/ports/rp2040-zero/firmware/src/display_ui.c`
- Modify: `codex_usb_pager/ports/rp2040-zero/firmware/src/main.c`
- Modify: `codex_usb_pager/ports/rp2040-zero/tests/CMakeLists.txt`
- Modify: `codex_usb_pager/ports/rp2040-zero/tests/test_pager_core.c`

**Interfaces:**
- Produces: `bool tiny_font_sample(char glyph, uint8_t x, uint8_t y)`
- Produces: `bool pager_scene_idle_text_pixel(const char *balance, int16_t x, int16_t y, uint16_t *color)`
- Produces: `void pager_display_ui_set_snapshot(pager_state_t state, const char *balance, uint32_t now_ms)`

- [ ] **Step 1: Add failing firmware tests**

```c
static void test_balance_parser_boundaries(void) {
    pager_snapshot_t snapshot;
    assert(pager_parse_line(
        "STATE IDLE RUN=0 WAIT=0 DONE=0 BAL=0 EV=NONE", &snapshot));
    assert(strcmp(snapshot.balance, "0") == 0);
    assert(pager_parse_line(
        "STATE IDLE RUN=0 WAIT=0 DONE=0 BAL=100 EV=NONE", &snapshot));
    assert(strcmp(snapshot.balance, "100") == 0);
}

static void test_idle_balance_layout_is_centered(void) {
    pager_idle_layout_t one = pager_scene_idle_layout("8");
    pager_idle_layout_t two = pager_scene_idle_layout("88");
    pager_idle_layout_t three = pager_scene_idle_layout("100");
    assert(one.value_center_x == PAGER_SCENE_CENTER_X);
    assert(two.value_center_x == PAGER_SCENE_CENTER_X);
    assert(three.value_center_x == PAGER_SCENE_CENTER_X);
    assert(three.value_left >= PAGER_SCENE_REGION_X);
    assert(three.value_right <
           PAGER_SCENE_REGION_X + PAGER_SCENE_REGION_SIZE);
}

static void test_non_idle_scene_ignores_balance(void) {
    uint16_t without_balance[PAGER_SCENE_REGION_SIZE];
    uint16_t with_balance[PAGER_SCENE_REGION_SIZE];
    pager_scene_render_row(PAGER_RUNNING, 500U, "NA", 160, without_balance);
    pager_scene_render_row(PAGER_RUNNING, 500U, "88", 160, with_balance);
    assert(memcmp(without_balance, with_balance, sizeof(with_balance)) == 0);
}
```

- [ ] **Step 2: Run C tests and verify failure**

Run:

```powershell
cmake -S ports/rp2040-zero/tests -B build-rp2040-host
cmake --build build-rp2040-host --config Release
ctest --test-dir build-rp2040-host -C Release --output-on-failure
```

Expected: compilation fails because the idle layout and balance-aware render
interfaces are not defined.

- [ ] **Step 3: Implement the fixed bitmap font**

Define five-column, seven-row glyphs for `W`, `E`, `K`, digits `0..9`, and
`%`. `tiny_font_sample` returns false for unsupported glyphs and out-of-range
coordinates. Store glyph rows as compile-time constants; do not allocate or
scale buffers.

- [ ] **Step 4: Implement the idle composition**

Add a `pager_idle_layout_t` containing integer bounds and centers. For known
balances `0..100`, render:

- a smaller Blossom centered above the text;
- `WEEK` at 2x bitmap scale;
- `<balance>%` at 4x bitmap scale;
- neutral `WEEK` color and blue-purple percentage color.

For `NA` or malformed balance text, render the existing idle Blossom with no
text. Pass the balance through each row renderer. Text sampling occurs only
inside the `PAGER_IDLE` branch and only within the text bounds.

`pager_display_ui_set_snapshot` updates the state and a fixed
`char balance[PAGER_BALANCE_CAPACITY]`. It starts the existing state
cross-fade when the state changes; a same-state balance change invalidates
the next frame without starting a transition. `main.c` calls it after every
valid parsed snapshot.

- [ ] **Step 5: Run host C tests**

Run:

```powershell
cmake --build build-rp2040-host --config Release
ctest --test-dir build-rp2040-host -C Release --output-on-failure
```

Expected: `pager_core_tests` passes.

- [ ] **Step 6: Run Python regression tests**

Run: `python -m pytest tools -q`

Expected: all Python tests pass.

- [ ] **Step 7: Commit**

```powershell
git add -- codex_usb_pager/ports/rp2040-zero/firmware codex_usb_pager/ports/rp2040-zero/tests
git commit -m "feat: show weekly balance when idle"
```

### Task 4: Build, Flash, and Live-Verify

**Files:**
- Modify only if verification reveals a scoped defect in files from Tasks 1-3.

**Interfaces:**
- Consumes: RP2040 UF2 firmware and the host daemon's `BAL=<remaining>` snapshot.
- Produces: a physically verified idle weekly balance display.

- [ ] **Step 1: Run the complete host suite**

Run: `python -m pytest tools -q`

Expected: all tests pass.

- [ ] **Step 2: Run the complete C host suite**

Run:

```powershell
cmake --build build-rp2040-host --config Release
ctest --test-dir build-rp2040-host -C Release --output-on-failure
```

Expected: all tests pass.

- [ ] **Step 3: Build RP2040 firmware**

Run:

```powershell
powershell -ExecutionPolicy Bypass -File tools/build_rp2040.ps1
```

Expected: the build emits `codex_pager_rp2040.uf2` and reports flash/SRAM
usage within RP2040 limits.

- [ ] **Step 4: Verify the live host value before flashing**

Run the watcher once against `%USERPROFILE%\.codex\sessions` and print the
newest value.

Expected on the current account: `88`.

- [ ] **Step 5: Flash the mounted RP2040 boot volume**

Copy the verified UF2 to the detected `RPI-RP2` volume. Wait for the volume to
disconnect and for the CDC serial device to reappear.

- [ ] **Step 6: Restart the pager daemon**

Stop only the existing `pager_daemon.py` process and start the daemon from
`C:\Users\28026\Documents\saltyfish\codex_usb_pager\tools`.

- [ ] **Step 7: Verify hardware behavior**

Confirm:

- idle shows `WEEK` and the same remaining percentage as the watcher;
- submitting a Codex task fades the weekly text out and starts the existing
  running animation;
- finishing the task returns through the existing done transition and then
  fades the weekly text back in;
- running animation frame rate and color match the pre-change firmware.

- [ ] **Step 8: Report local environment issues**

Report build locks, stale daemon processes, serial reconnect delays, missing
rate-limit records, or boot-volume behavior encountered during the run, and
state whether each issue should be fixed.
