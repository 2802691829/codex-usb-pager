# Blossom Petals And Instant Running Design

## Scope

This change corrects two behaviors in the RP2040-Zero Codex pager:

1. READY and OFFLINE must use six closed Blossom petals whose proportions and
   ribbon thickness match the canonical Blossom asset.
2. RUNNING must be sent as soon as Codex accepts a user prompt, without waiting
   for the buffered JSONL session event.

The display wiring, ST7789 profile, weekly balance display, buzzer behavior,
USB CDC protocol, and existing state priority remain unchanged.

## Canonical Visual Source

`assets/openai-blossom.svg` is the only geometry source.

The six petal masks are generated from the six outer hole contours in that SVG:

- Preserve each original hole contour without resizing or reshaping it.
- Expand each hole outward by the canonical ribbon width of 15.889 SVG units.
- Subtract the original hole from the expanded region.
- The result is one closed ring with a continuous inner and outer edge.
- Generate all six rings at one shared scale and one shared ribbon width.
- Do not independently fit, crop, or normalize individual petals.

The full assembled RUNNING logo continues to use the canonical complete
Blossom alpha mask. The six ring masks are not permanently overlaid at the
center because that would produce incorrect overlaps.

## State Motion

### READY

- Six green closed petals orbit the center at equal angular spacing.
- All petals use the same source scale and ribbon width.
- Weekly balance remains centered as digits only.

### READY To RUNNING

- The first RUNNING frame changes the petals to the running purple palette.
- The six petals begin moving toward their canonical center positions
  immediately.
- The aggregation lasts 800 ms.
- Near the end of aggregation, the six petal layer fades out while the complete
  canonical Blossom layer fades in at the same position and scale.
- The crossfade must not expose a gap or show six closed rings stacked at full
  opacity.
- Once assembled, the complete Blossom starts the existing faster RUNNING
  rotation.

### RUNNING To READY

- Rotation eases to a stop.
- The complete purple Blossom crossfades to six green closed petals.
- The petals separate to their READY orbit without a size jump.

### OFFLINE To READY

- Offline petals retain their irregular drifting positions.
- They recolor to READY green and settle into the regular orbit.
- They do not assemble into the full Blossom during this transition.

## Immediate RUNNING Detection

The existing JSONL watcher remains useful for completion and fallback events,
but it cannot be the primary prompt-start signal because Codex may buffer its
write for tens of seconds.

The daemon adds an incremental watcher for:

`%USERPROFILE%\.codex\logs_2.sqlite`

The watcher:

- Opens the database read-only and remains compatible with WAL mode.
- Records the current maximum `logs.id` at startup to ignore stale entries.
- Polls only rows with `id > last_id`.
- Detects `target = codex_core::session::handlers` entries whose body contains
  a `Submission` with `op: UserInput`.
- Uses the row's `thread_id` as the task identifier.
- Records `UserPromptSubmit` and sends the aggregate snapshot immediately.
- Advances its cursor even for irrelevant rows.
- Reopens the database after replacement, transient locking, or schema access
  failure.

The target from prompt acceptance to serial write is under 100 ms on the local
machine. The existing JSONL detection remains as a deduplicated fallback.

## Data Flow

1. Codex accepts the user's prompt.
2. Codex writes the submission log row.
3. The SQLite watcher detects the new row.
4. `RuntimeStore` records the task as RUNNING.
5. The daemon sends the aggregate `STATE ...` line over USB CDC.
6. RP2040 changes the first display frame to running purple and starts
   aggregation.

## Error Handling

- Missing or locked log database: continue using JSONL and heartbeat fallback.
- Duplicate SQLite and JSONL prompt events: update the same task row without
  creating an additional task.
- USB temporarily unavailable: retain runtime state and retry on heartbeat.
- Invalid or missing `thread_id`: ignore the row and advance the log cursor.
- Asset generation failure: do not replace the existing generated C asset.

## Verification

Automated checks must prove:

- Six petal masks exist and all are closed rings.
- Every mask uses the same ribbon width within raster tolerance.
- All six masks use a shared global scale.
- The full Blossom remains unchanged.
- Aggregation starts purple at elapsed time zero.
- Aggregation ends on the canonical full mask without a size jump.
- A new SQLite UserInput row produces one immediate RUNNING event.
- Old, irrelevant, duplicate, missing-thread, and locked-database cases are
  handled safely.
- Existing host tests, Python tests, RP2040 build, SRAM size check, and USB
  flash verification pass.
