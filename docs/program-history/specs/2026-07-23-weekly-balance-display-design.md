# Weekly Balance Display Design

## Goal

Show the remaining Codex weekly allowance on the RP2040 pager while it is
idle. The value must come from Codex's local authenticated event stream,
require no manual input, and disappear whenever an active status is shown.

## Data Source

The host daemon scans Codex session JSONL events below
`%USERPROFILE%\.codex\sessions`. It accepts only `token_count` events whose
`rate_limits.primary.window_minutes` equals `10080`, the seven-day window.

The displayed value is:

`remaining_percent = clamp(100 - used_percent, 0, 100)`

When several sessions contain a weekly limit, the daemon uses the event with
the newest timestamp. The last valid value is cached in the pager runtime
database so restarting the daemon does not temporarily erase the display.
Malformed, partial, and non-weekly rate-limit records are ignored.

If no valid weekly value has ever been observed, the protocol continues to
send `BAL=NA` and the idle screen shows no percentage. A stale cached value is
allowed because it remains the last value reported by Codex; the next
`token_count` event replaces it.

## Protocol

The existing wire format remains unchanged:

`STATE <state> RUN=<n> WAIT=<n> DONE=<n> BAL=<token> EV=<event>`

For a known weekly balance, `BAL` contains the remaining integer percentage,
for example `BAL=88`. This preserves compatibility with the existing parser
and avoids a firmware protocol migration.

## Idle Display

Only `PAGER_IDLE` renders the weekly allowance:

- The existing dark background and surrounding geometry remain unchanged.
- The Blossom mark becomes smaller and moves upward.
- `WEEK` appears beneath the mark in restrained neutral text.
- The remaining value, such as `88%`, appears below `WEEK` in a larger
  blue-purple accent.
- The percentage is horizontally centered and supports values from `0%` to
  `100%` without clipping.

Running, multi-task, waiting, done, error, and offline scenes do not show the
weekly allowance. Their existing appearance and motion remain unchanged.

State transitions use the existing scene cross-fade, so the idle text fades
in and out with the rest of the scene rather than appearing abruptly.

## Performance

The daemon checks appended session data incrementally and does not rescan full
session files on every heartbeat. It sends a snapshot immediately when the
weekly value changes and otherwise keeps the existing heartbeat interval.

The firmware uses a small fixed bitmap font and renders text into the existing
double-buffered scene. No heap allocation, additional frame buffer, floating
point, or per-frame host traffic is introduced. Non-idle frame rate must not
regress.

## Verification

Host tests cover:

- extraction of the newest valid seven-day rate limit;
- conversion from used percentage to remaining percentage;
- rejection of malformed and non-weekly windows;
- cached-value restoration;
- `BAL=NA` when no value exists.

Firmware tests cover:

- parsing `BAL=0`, `BAL=88`, and `BAL=100`;
- idle-only percentage rendering;
- centered layout for one-, two-, and three-digit values;
- unchanged non-idle scene output outside transition frames.

The final build must fit RP2040 flash and SRAM limits. After flashing, a live
Codex event must update the idle display to the same remaining percentage
reported in the local event stream.
