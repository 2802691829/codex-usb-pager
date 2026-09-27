# Multi-Task Running Visual Design

Date: 2026-07-28

## Goal

Add a dedicated multi-task running scene that preserves the existing smooth
single-task RUNNING animation while visually representing the number of
concurrent Codex tasks.

The design replaces the current incorrect composition of a yellow foreground
Blossom and scattered cyan READY petals.

## Confirmed Visual

- One complete foreground Blossom represents the primary running task.
- Each additional running task adds one complete, blurred-looking background
  Blossom.
- At most three background Blossoms are shown.
- Two running tasks therefore show one foreground Blossom and one background
  Blossom.
- Three running tasks show one foreground Blossom and two background Blossoms.
- Four or more running tasks show one foreground Blossom and three background
  Blossoms.
- The foreground Blossom keeps the existing RUNNING purple, centered rotation,
  acceleration curve, and scale pulse.
- Background Blossoms use, from front to back:
  - deep blue;
  - blue-violet;
  - cyan-violet.
- Background opacity decreases with depth.
- Background scale increases slightly with depth so the silhouettes remain
  visible behind the foreground Blossom.
- Every layer rotates around the exact same screen center.
- Background layers use different angular speeds and alternating directions to
  create depth without making the composition look like duplicated foreground
  logos.
- The white hexagonal enclosure-alignment outline remains unchanged.
- No READY petal masks, yellow foreground color, task-number text, or separate
  petal pieces appear in the steady multi-task scene.

## Task Count Data Flow

The host already sends `RUN=<count>` in each snapshot and `pager_parse_line`
stores it in `pager_snapshot_t.running`.

The RP2040 application must retain that count after state selection:

1. `main.c` passes both selected state and `snapshot.running` to the display UI.
2. `display_ui` stores the latest running count.
3. The render context derives `ghost_count` as:

   ```text
   0                              when state is not MULTI
   min(running_count - 1, 3)      when state is MULTI
   ```

4. Repeated snapshots with the same state but a changed running count must
   invalidate the scene immediately.

The semantic `PAGER_MULTI` state remains responsible for priority selection;
the count is additional rendering data, not a new state enum.

## Rendering Architecture

The multi-task scene must use the same prepared full-Blossom mask renderer as
the smooth RUNNING scene.

- The foreground is the canonical `g_blossom_alpha_4bpp` full layer.
- Every background ghost is another prepared full-Blossom layer.
- Ghosts never use `g_blossom_piece_alpha_4bpp`.
- The render context contains one foreground layer and up to three ghost
  layers.
- Per-row samplers advance incrementally across the scanline.
- Ghost opacity and color blending are performed in RGB565.
- The renderer must not return to the obsolete separate
  `pager_scene_render_row` multi-task path.

To preserve frame rate, ghost layers use the existing low-cost sampling
strategy: one mask sample per 2 x 2 output block with duplicated neighboring
pixels. The foreground remains full-resolution. This gives the background a
deliberately softened appearance while keeping the foreground sharp.

## Motion

The foreground motion is identical to RUNNING.

Each ghost receives a continuous angle derived directly from elapsed time.
There are no pauses, frame-index resets, or piece-level transforms.

Recommended initial motion table:

| Ghost | Direction | Period | Scale relative to foreground | Opacity |
|---|---:|---:|---:|---:|
| 1 | Counter-clockwise | 5.6 s | 1.08 | 30% |
| 2 | Clockwise | 4.8 s | 1.16 | 23% |
| 3 | Counter-clockwise | 6.4 s | 1.24 | 17% |

These values may be tuned after physical-screen inspection, but the ordering,
alternating direction, and decreasing opacity remain fixed.

## Transitions

- `RUNNING -> MULTI`: keep the foreground phase continuous; fade in only the
  newly required ghost layers over 320 ms.
- `MULTI -> RUNNING`: keep the foreground phase continuous; fade out all ghost
  layers over 320 ms.
- `MULTI count increase`: fade in only the new ghost.
- `MULTI count decrease`: fade out only surplus ghosts.
- `READY -> MULTI`: use the existing READY-to-RUNNING gather transition for the
  foreground, then fade the required ghosts in during the final 320 ms.
- `MULTI -> READY`: fade ghosts out first while the foreground follows the
  existing RUNNING-to-READY separation path.
- WAIT, DONE, ERROR, and OFFLINE retain their existing priority and visuals.

Changing between RUNNING and MULTI must not restart the foreground Blossom
angle or scale cycle.

## Buzzer Rules

The RP2040-Zero drives the existing three-pin active-low buzzer module through
GP14. HIGH is silent and LOW activates the module. Buzzer scheduling is
non-blocking and must never delay USB parsing, the display update, or WS2812
updates.

- Boot: one short pulse.
- `EV=WAIT`: three short pulses.
- `EV=DONE`: one short pulse.
- `EV=ERROR`: five short pulses.
- RUNNING, MULTI, IDLE, and OFFLINE: silent.
- Each active-low pulse lasts 25 ms; the silent spacing between pulses is
  180 ms.
- Only event tokens trigger buzzer sequences. Repeated snapshots with the same
  non-NONE event must not restart the sequence.
- MULTI remains silent even when the running count changes.

## Performance Requirements

- Target frame interval remains 16 ms.
- Foreground quality and smoothness must remain indistinguishable from current
  RUNNING.
- Two-task rendering is the primary acceptance case.
- Four-or-more-task rendering must remain responsive with three capped ghosts.
- No full-frame READY-petal renderer may be activated in steady MULTI.
- Task-count changes must become visible on the first scheduled display frame
  after the USB snapshot is parsed.

## Tests

Host tests must cover:

- `RUN=2`, `RUN=3`, `RUN=4`, and a larger count map to 1, 2, 3, and 3 ghosts.
- A count change while state remains `PAGER_MULTI` invalidates rendering.
- RUNNING and MULTI share the same foreground pose at the same elapsed phase.
- MULTI prepared contexts use full Blossom masks for every ghost.
- No MULTI path enables individual READY petals.
- Ghost colors, scales, opacity order, and alternating directions match the
  design table.
- RUNNING-to-MULTI and MULTI-to-RUNNING preserve foreground motion phase.
- Buzzer maps WAIT, DONE, and ERROR events to 3, 1, and 5 pulses; it stays
  silent for RUNNING and MULTI snapshots.
- Buzzer GPIO begins HIGH and a 25 ms pulse does not block display rendering.
- Existing parser, priority, WAIT, DONE, OFFLINE, balance, and display tests
  continue to pass.

Physical verification must confirm:

- two simultaneous Codex tasks show one purple foreground Blossom and one
  blue-toned blurred background Blossom;
- the foreground remains sharp and centered;
- no yellow logo or cyan scattered petals appear;
- adding and removing tasks produces smooth ghost fades;
- frame rate remains visually close to single-task RUNNING.
