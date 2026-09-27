# Ready And Transition Performance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the avoidable six-layer full-scene work and broad delta transfers that make READY and state transitions visibly slower than RUNNING.

**Architecture:** Add testable 12 x 12 dirty-tile and layer-intersection helpers to the scene module. Render only dirty tiles with compact active-layer lists, then coalesce dirty tile runs for ST7789 transfer while preserving the existing double framebuffer and RUNNING fast path.

**Tech Stack:** RP2040 Pico SDK, C11, PIO/DMA ST7789 transport, CMake/CTest, pytest source-contract tests.

## Global Constraints

- Keep the 16 ms target and elapsed-time animation.
- Preserve all approved visual geometry and timing.
- Keep display SPI at 24 MHz and preserve RGB565 byte order.
- Retain the two existing frame buffers and fit in 264 KB SRAM.
- Use failing tests before production changes.

---

### Task 1: Dirty-Tile Geometry

**Files:**
- Modify: `ports/rp2040-zero/firmware/include/display_scene.h`
- Modify: `ports/rp2040-zero/firmware/src/display_scene.c`
- Test: `ports/rp2040-zero/tests/test_pager_core.c`

**Interfaces:**
- Produces: `pager_scene_tile_map_t`
- Produces: `pager_scene_mark_motion_tiles(previous, current, map)`
- Produces: `pager_scene_tile_layer_mask(model, clips, tile_x, tile_y)`

- [ ] **Step 1: Write failing geometry tests**

Add tests that create a READY model, move one petal, and assert that only tiles
intersecting the old and new clips are dirty. Add a second test asserting that
a corner tile has no petal layers and a tile through one petal has a layer mask
with fewer than six bits.

- [ ] **Step 2: Verify RED**

Run:

```powershell
powershell -ExecutionPolicy Bypass -File tools\run_host_tests.ps1
```

Expected: compilation fails because the tile types and functions do not exist.

- [ ] **Step 3: Implement the geometry helpers**

Use 12 pixel tiles over the 228 pixel region, yielding 19 x 19 tiles. Mark the
inclusive tile range of each old/new clip. Build layer masks by testing clip
intersection against the selected tile rectangle.

- [ ] **Step 4: Verify GREEN**

Run the host tests again. Expected: all tests pass.

### Task 2: Tile Renderer And Compact Layer Sampling

**Files:**
- Modify: `ports/rp2040-zero/firmware/include/display_scene.h`
- Modify: `ports/rp2040-zero/firmware/src/display_scene.c`
- Modify: `ports/rp2040-zero/firmware/src/display_ui.c`
- Test: `ports/rp2040-zero/tests/test_pager_core.c`
- Test: `tools/test_rp2040_display_ui.py`

**Interfaces:**
- Consumes: dirty tile map and per-tile layer masks from Task 1
- Produces: `pager_scene_render_motion_span(...)`

- [ ] **Step 1: Write failing renderer-contract tests**

Assert that the UI renders complete frames only on initialization, and
subsequent petal frames call the span renderer for dirty tile rows. Assert that
RUNNING continues to use a single full-layer sampling path.

- [ ] **Step 2: Verify RED**

Run the focused pytest and C host tests. Expected: failures because the span
renderer and tile-driven UI path are absent.

- [ ] **Step 3: Implement minimal tile rendering**

Copy the previous framebuffer into the working buffer. Rebuild every dirty
tile from background and hexagon, sampling only the layer bits active for that
tile. Keep the existing complete-row renderer for the initial frame and the
RUNNING fast path.

- [ ] **Step 4: Verify GREEN**

Run both focused and complete host suites. Expected: all tests pass and
pixel-level tests remain unchanged.

### Task 3: Coalesced Tile Transfer And Firmware Verification

**Files:**
- Modify: `ports/rp2040-zero/firmware/src/display_ui.c`
- Test: `tools/test_rp2040_display_ui.py`

**Interfaces:**
- Consumes: dirty tile map from Task 1
- Produces: horizontally coalesced ST7789 transfer rectangles

- [ ] **Step 1: Write failing transfer tests**

Add a source-contract test proving separated dirty tile runs are not expanded
into one full-width eight-row band and adjacent tiles are coalesced.

- [ ] **Step 2: Verify RED**

Run:

```powershell
python -m pytest tools\test_rp2040_display_ui.py -q
```

Expected: failure against the existing `DELTA_BAND_ROWS` union transport.

- [ ] **Step 3: Implement tile-run transfer**

For each tile row, merge adjacent dirty tiles into one horizontal run. Set one
ST7789 window per run and send its 12 rows directly from the working
framebuffer. Do not transmit gaps between separated runs.

- [ ] **Step 4: Verify and build**

Run:

```powershell
powershell -ExecutionPolicy Bypass -File tools\run_host_tests.ps1
python -m pytest tools\test_blossom_asset.py tools\test_petal_preview_geometry.py tools\test_rp2040_display_ui.py tools\test_build_rp2040_script.py tools\test_run_host_tests_script.py -q
powershell -ExecutionPolicy Bypass -File tools\build_rp2040.ps1
```

Expected: all host tests pass and the UF2 build reports SRAM below 264 KB.

- [ ] **Step 5: Flash and inspect**

Enter BOOTSEL through the existing 1200-baud reset path, copy the generated
UF2, verify the serial device returns, and inspect READY plus both transition
directions on the physical screen.
