# Blossom State Transition Design

## Goal

Replace generic scene cross-fades between `OFFLINE`, `READY`, and `RUNNING`
with continuous Blossom motion that communicates the state change itself.
The animation must remain responsive to Codex events, preserve the official
Blossom geometry, and avoid visible seams, image swaps, or paused rotation.

This design also defines the return to `READY` after a run or the existing
completion hold finishes.

## Steady States

### OFFLINE

- The Blossom is separated into six complete woven pieces.
- The pieces use a restrained blue-gray color: logical RGB `#738094`.
- Position, angle, drift phase, and drift period differ for every piece.
- Motion is slow and irregular. The pieces never gather while offline.
- Weekly balance is hidden.

### READY

- The same six pieces are evenly spaced around the center.
- All pieces use green: logical RGB `#39D298`.
- The six-piece group revolves slowly around the center at a constant speed.
- Each piece preserves its orientation relative to the revolving group.
- The weekly remaining value is centered as an integer without a percent sign.

### RUNNING

- The six pieces form one exact, seamless official Blossom.
- The complete Blossom uses a deeper purple: logical RGB `#6449E0`.
- It rotates continuously with the existing subtle scale breathing.
- Rotation uses elapsed time rather than frame count, so a slow frame cannot
  permanently alter speed or introduce an intentional pause.
- Weekly balance is hidden.

## Lossless Six-Piece Asset

The asset generator derives six mutually exclusive masks from the existing
official Blossom mask. Every lit source pixel belongs to exactly one piece.
At the assembled origin:

`piece_0 | piece_1 | ... | piece_5 == official_blossom`

The six masks may touch but cannot overlap or leave uncovered pixels. Their
union is the running-state image. Firmware does not replace the assembled
pieces with a second logo bitmap at the end of a transition.

This invariant removes the seam and geometry jump seen when independent
outlined petals were cross-faded into a separate full-logo image.

## State Transitions

All timings start immediately when the new host state is accepted. Smoothstep
or smootherstep easing is used for position, orientation, scale, color, and
text opacity. No transition begins with a stationary delay.

### READY To RUNNING

1. Over 900 ms, the green pieces leave the ready orbit and follow continuous
   curved paths into their exact assembled positions. The weekly value fades
   out during the first 650 ms.
2. The seamless green Blossom holds for 150 ms. It does not rotate yet.
3. Over 400 ms, the complete Blossom changes from `#39D298` to `#6449E0`.
4. Rotation starts only after the color transition completes and then remains
   continuous for the entire running state.

Total time to steady `RUNNING` is 1,450 ms. Visual response begins on the first
rendered frame after the state event.

### RUNNING Or DONE To READY

1. Over 350 ms, the complete Blossom decelerates smoothly and stops at the
   nearest visually balanced orientation.
2. Over 350 ms, purple changes to ready green while the Blossom remains whole.
3. Over 800 ms, the six masks separate from their exact assembled positions
   and move to the six evenly spaced ready-orbit positions.
4. The weekly value fades in during the final 550 ms. Slow ready revolution
   begins as the separation finishes, with matched angular velocity at the
   handoff.

The existing `DONE` presentation and hold remain intact. When that hold ends,
the same whole-Blossom-to-ready separation sequence is used.

### OFFLINE To READY

1. Each gray piece immediately reduces its independent drift and angular
   wobble.
2. Over 1,200 ms, all six pieces follow separate curved paths to the evenly
   spaced ready ring, correct their orientations, and change from `#738094`
   to `#39D298`.
3. The weekly value fades in over the final 500 ms.
4. Ready revolution begins with continuous phase and velocity as the pieces
   reach their destinations.

This path does not assemble the full Blossom. It directly converts irregular
offline scatter into the ordered ready orbit.

### READY To OFFLINE

When the host heartbeat expires or the desktop bridge exits, the ready orbit
loses synchronization over 900 ms. The pieces change from green to blue-gray,
separate toward their offline anchor positions, and acquire their individual
drift phases. The weekly value fades out during the first 450 ms.

## State And Event Flow

The host continues to send the existing state snapshot and heartbeat. A newly
received state updates the transition target immediately. Firmware owns all
animation time and does not require per-frame USB traffic.

If a new state arrives during a transition, the next transition starts from
the currently rendered pose, color, angular velocity, and text opacity. It
must not restart from a canned endpoint. Priority and multi-task state
selection remain controlled by the existing pager core.

Heartbeat timeout remains the source of `OFFLINE`. A valid snapshot received
while offline starts `OFFLINE -> READY`, or transitions directly toward a
higher-priority active state when Codex is already running.

## Rendering And Performance

- Reuse the existing packed RGB565 double-buffered scene and DMA transport.
- Precompute the six source masks at build time. Do not allocate per frame.
- Use fixed-point interpolation for transforms and RGB565 color changes.
- Clear and redraw only the established animated scene region.
- Frame timing remains elapsed-time based with a 25 ms target.
- No transition may add a deliberate wait, full-screen clear, row-by-row DMA
  restart, or second full-resolution transition buffer.

## Verification

Host and firmware tests must cover:

- every official Blossom pixel belongs to exactly one of the six masks;
- the assembled six-mask union equals the official Blossom byte for byte;
- no uncovered seam exists at the `READY -> RUNNING` endpoint;
- state color endpoints match the three logical RGB values;
- position, rotation, scale, and opacity are continuous at every phase
  boundary;
- running rotation begins after recoloring and never intentionally pauses;
- running or done returns through the green separation animation;
- offline recovery reaches the ordered ready orbit without full assembly;
- a state interruption continues from the current rendered pose;
- weekly balance fades only on transitions that enter or leave `READY`;
- the host build, RP2040 firmware build, and existing transport tests pass.

Physical verification on the 240 x 240 ST7789 panel must confirm:

- green and deep purple are clearly distinguishable;
- the assembled Blossom has no visible gaps;
- no horizontal refresh band or full-frame flash appears;
- transitions begin promptly when a Codex state changes;
- steady running animation remains smooth at the achieved frame rate.
