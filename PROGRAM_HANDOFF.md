# Codex USB Pager Program Handoff

Updated: 2026-08-21

This document is the source of truth for the program side of the finished
Codex pager. The enclosure is complete and is intentionally outside this
handoff.

## 1. Current Hardware

- Controller: RP2040-Zero, RP2040 dual-core Cortex-M0+, 2 MB flash.
- Display: 1.3-inch ST7789 IPS, 240 x 240, seven-pin SPI module.
- Buzzer: three-pin active buzzer module marked `Low level trigger`.
- Onboard status LED: WS2812 on GP16.
- Host connection: USB CDC over the RP2040-Zero USB-C connector.

### Wiring

| Module pin | RP2040-Zero pin | Notes |
| --- | --- | --- |
| Display GND | GND | Common ground |
| Display VCC | 3V3 | Do not use 5 V |
| Display SCL | GP12 | PIO SPI clock |
| Display SDA | GP11 | PIO SPI data |
| Display RES | GP10 | Reset |
| Display DC | GP9 | Command/data |
| Display BLK | GP8 | Backlight, high = on |
| Buzzer GND | GND | Common ground |
| Buzzer IO | GP14 | Active-low trigger |
| Buzzer VCC | 3V3 | Module power |

The bare two-pin passive buzzer is not used.

## 2. USB Protocol

The computer sends one newline-terminated ASCII snapshot over USB CDC:

```text
STATE <state> RUN=<n> WAIT=<n> DONE=<n> BAL=<token> EV=<event>\n
```

Example:

```text
STATE RUNNING RUN=2 WAIT=0 DONE=14 BAL=82 EV=NONE
```

States: `IDLE`, `RUNNING`, `WAIT`, `DONE`, `ERROR`. If no valid snapshot is
received for 8 seconds, the firmware enters `OFFLINE`. `RUNNING` with
`RUN>1` selects the multi-task scene.

Events are edge notifications: `NONE`, `WAIT`, `DONE`, `ERROR`.

## 3. Current Visual Behavior

- `OFFLINE`: six grey Blossom pieces fall and remain irregularly piled near
  the bottom, bounded by the white hexagon.
- `IDLE/READY`: six green pieces are evenly separated around the center and
  orbit slowly. Weekly balance is shown as a number in the center.
- `RUNNING`: assembled purple Blossom rotates with acceleration and a scale
  pulse around a fixed center.
- Multi-task running: the main Blossom remains in front; additional blurred
  colored Blossom layers rotate behind it, capped by the firmware design.
- `WAIT`: amber confirmation scene.
- `DONE`: no check mark; the completed scene pulses every three seconds.
- The white hexagon is the reserved visible boundary used by the finished
  enclosure opening.

Do not redraw the Blossom or change its center, petal proportions, hexagon,
palette, or transition choreography unless the user explicitly requests it.

## 4. Buzzer Rules

- `EV=WAIT`: three quiet short pulses.
- `EV=DONE`: one quiet short pulse.
- `EV=ERROR`: five quiet short pulses.
- `RUNNING`, `IDLE`, `OFFLINE`, heartbeats, and normal tool activity are
  silent.
- The firmware uses 25 ms on and 180 ms gap, non-blocking.

### False-beep fix made on 2026-08-21

The false beeps did not originate in the RP2040 buzzer driver. They came from
host events being interpreted as final completion:

1. A hidden approval-review turn produced `task_complete` while the visible
   user task was still running.
2. Network reconnect/abort produced `turn_aborted`, previously mapped to
   completion.
3. A context-free Stop/notify path duplicated completion notifications.

Current host behavior:

- Hidden internal approval-review messages and their completion are ignored.
- `turn_aborted` changes the task to `IDLE` and emits no buzzer event.
- Stop Hooks and legacy notify-DONE calls do not decide completion.
- Final completion comes from the semantic session JSONL `task_complete`.
- With multiple tasks, an early completion is retained silently. `DONE` is
  emitted once only after no task remains in RUNNING or WAIT.
- `PermissionRequest` remains the only normal source of `EV=WAIT`.

Relevant files:

- `tools/session_watcher.py`
- `tools/pager_hook_runtime.py`
- `tools/pager_runtime.py`
- `tools/pager_daemon.py`
- `ports/rp2040-zero/firmware/src/buzzer.c`

## 5. Host Signal Pipeline

The active host hook is:

```text
C:\Users\28026\.codex\hooks\codex_pager.py
```

It locates this project at:

```text
C:\Users\28026\Documents\saltyfish\codex_usb_pager\tools
```

The active configuration has two compatible notification entry points:

- `C:\Users\28026\.codex\hooks.json` for prompt, tool, permission, and Stop
  hooks.
- `notify` in `C:\Users\28026\.codex\config.toml` calling
  `codex_notify_pager.py` after a turn.

Both eventually pass through `pager_hook_runtime.py`. Stop is deliberately
ignored there, so duplicate DONE notifications cannot reach the buzzer.

The daemon also watches:

- `C:\Users\28026\.codex\logs_2.sqlite` for prompt-start activity.
- `C:\Users\28026\.codex\sessions\*.jsonl` for semantic turn events.
- Codex usage data for weekly balance updates.

Runtime aggregation is stored in:

```text
%TEMP%\codex_pager_runtime.sqlite
```

Only one `pager_daemon.py` process should run.

## 6. Important Source Files

- `ports/rp2040-zero/firmware/`: active RP2040 firmware.
- `ports/rp2040-zero/tests/`: native firmware behavior tests.
- `ports/rp2040-zero/README.md`: build, protocol, wiring, and acceptance notes.
- `tools/`: host hooks, daemon, USB transport, balance reader, and tests.
- `assets/openai-blossom.svg`: canonical Blossom source.
- `Core/Inc/blossom_asset.h` and `Core/Src/blossom_asset.c`: generated packed
  Blossom mask used by the RP2040 target.
- `docs/superpowers/plans` and `docs/superpowers/specs`: program design history.

## 7. Build, Test, and Flash

Build the RP2040 firmware through the ASCII-path helper:

```powershell
powershell -ExecutionPolicy Bypass -File tools/build_rp2040.ps1
```

Output:

```text
build-rp2040\codex_pager_rp2040.uf2
```

Current packaged UF2 SHA-256:

```text
BEA1BA1EAFFA862EFF384F55C65FCB4C9D2883CC2602B250E1D0FD3D482FAD3A
```

To flash: hold BOOT while connecting or resetting the RP2040-Zero, wait for
the `RPI-RP2` drive, then copy the UF2 to that drive. The drive disappears
after a successful flash. Host-only hook fixes do not require reflashing.

Host regression command:

```powershell
python -m pytest tools/test_pager_runtime.py tools/test_session_watcher.py tools/test_pager_state.py tools/test_codex_log_watcher.py tools/test_pager_transport.py -q
```

Latest result on 2026-08-21: 50 tests passed.

## 8. Known Local Environment Issues

- Some old pytest temporary folders have Windows permission residue. Use a
  fresh unique `--basetemp` or elevated test run. This does not affect pager
  runtime behavior. Cleanup is recommended later.
- The primary Codex session JSONL was about 536 MB during the last diagnosis.
  Archive/rotate it only after fully closing Codex. This is recommended to
  prevent future watcher slowdown.
- The working tree contains many uncommitted and untracked project files.
  Do not reset, clean, or delete them automatically.
- Build through `tools/build_rp2040.ps1`; older toolchains failed on paths with
  Chinese characters and occasionally left PDB/build processes behind.

## 9. First Checks in a New Session

1. Read this file and `ports/rp2040-zero/README.md` before editing.
2. Confirm the pager appears as USB CDC and only one daemon is alive.
3. Read the runtime snapshot; during work it must be `RUNNING` with
   `EV=NONE`.
4. Run the host regression tests before modifying the hook pipeline.
5. For a buzzer complaint, first log the received host event and snapshot.
   Do not change the firmware buzzer timings until the host source is proven.
6. Preserve multi-task aggregation: individual task completion must stay
   silent until the last active task finishes.

