# Ready And Transition Performance Design

## Goal

Make READY, READY-to-RUNNING, RUNNING-to-READY, and OFFLINE-to-READY
animations approach the smoothness of the existing RUNNING fast path without
changing the approved petal artwork, layout, color, motion curve, transition
duration, hexagon, or weekly-balance display.

## Root Cause

RUNNING samples one complete Blossom layer. Petal states currently scan the
entire 228 x 228 scene and advance six petal samplers for every pixel. During
crossfades they may also sample the complete Blossom. The eight-row delta
transport then combines distant changed pixels into wide rectangles, sending
unchanged background between separated petals.

## Selected Architecture

Divide the scene into 12 x 12 pixel tiles. For every frame:

1. Build old and new bounds for every visible layer.
2. Mark only tiles touched by either bound as dirty.
3. Rebuild dirty tiles from the deterministic background and fixed hexagon.
4. For each dirty tile, sample only layers whose bounds intersect that tile.
5. Coalesce horizontally adjacent dirty tiles into transfer rectangles and
   send only those rectangles.

RUNNING keeps its current single-layer fast path. Transitions may contain
petals and the complete Blossom, but each tile receives a compact active-layer
list instead of checking all seven layers at every pixel.

## Constraints

- Preserve the current 16 ms frame target and elapsed-time-based animation.
- Do not modify artwork masks, positions, scale, colors, easing, or duration.
- Preserve exact RGB565 byte order and the verified ST7789 initialization.
- Do not raise the 24 MHz display clock.
- Stay within RP2040 SRAM and retain two existing 228 x 228 frame buffers.
- State changes must still trigger an immediate frame.

## Verification

- Host tests prove tiles outside old/new layer bounds remain clean.
- Host tests prove active-layer lists exclude non-intersecting petals.
- Host tests prove separated petals no longer produce a full-width transfer.
- Existing pixel, geometry, motion, and panel-profile tests remain unchanged.
- Firmware builds within SRAM limits.
- Physical verification compares READY and both transition directions with
  the already-smooth RUNNING state.
