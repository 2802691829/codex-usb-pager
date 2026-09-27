# Exact Reference Petal Firmware Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task.

**Goal:** Replace the obsolete inferred petal rings with the user-approved exact reference petal, apply the approved READY geometry, preserve smooth state transitions, and build a flashable RP2040 UF2.

**Architecture:** Keep the existing full SVG mask as the RUNNING fast path. Generate one canonical 4bpp petal sprite directly from the approved PNG and expose it through the existing six-piece asset interface without changing its geometry. The motion model owns all six positions and orientations; READY uses the validated 68-pixel orbit and a single counterclockwise 90-degree orientation offset. Rendering remains time-based and moves to a 16 ms target interval.

**Tech Stack:** Python 3, Pillow, pytest, C11, CMake/NMake, Raspberry Pi Pico SDK, ST7789 SPI/DMA.

---

### Task 1: Lock the exact reference asset contract

**Files:**
- Modify: `tools/test_blossom_asset.py`
- Modify: `tools/generate_blossom_asset.py`
- Reference: `assets/reference-petal-exact.png`

**Step 1: Write the failing tests**

Add tests that require the generated canonical petal to equal the thresholded/cropped black reference, require six emitted masks to be byte-identical, and reject the old SVG-hole expansion path.

**Step 2: Run the tests to verify they fail**

Run: `python -m pytest tools/test_blossom_asset.py -q`

Expected: FAIL because `rasterize_petals()` still derives six rings from SVG holes.

**Step 3: Implement the minimal generator**

Add `rasterize_reference_petal()` that loads the PNG, thresholds black foreground, crops once, scales once into the 128x128 canonical canvas, quantizes to 4bpp, and returns six independent copies of the same bytes. Add `--petal` to the CLI and make it the default source for piece masks.

**Step 4: Run the tests to verify they pass**

Run: `python -m pytest tools/test_blossom_asset.py tools/test_petal_preview_geometry.py -q`

Expected: all tests pass.

**Step 5: Regenerate the C asset**

Run: `python tools/generate_blossom_asset.py`

Expected: `Core/Inc/blossom_asset.h` and `Core/Src/blossom_asset.c` update atomically.

### Task 2: Encode the approved READY geometry and transitions

**Files:**
- Modify: `ports/rp2040-zero/tests/test_pager_core.c`
- Modify: `ports/rp2040-zero/firmware/src/blossom_motion.c`
- Modify if required: `ports/rp2040-zero/firmware/include/blossom_motion.h`

**Step 1: Write the failing motion tests**

Require READY piece centers to lie on a 67-68 pixel orbit, all pieces to keep `FULL_SCALE_Q12`, the base orientation to be exactly counterclockwise 90 degrees plus the common orbit phase, and the first READY-to-RUNNING frame to start both gathering and green-to-purple interpolation.

**Step 2: Run host tests to verify they fail**

Run: `powershell -ExecutionPolicy Bypass -File tools/run_host_tests.ps1`

Expected: FAIL on the old 20-pixel READY radius and old color transition.

**Step 3: Implement the minimal motion changes**

Set the approved orbit radius, apply one 90-degree counterclockwise orientation offset, retain one shared scale, and interpolate color and position on the same transition timeline. Keep RUNNING continuous and faster than READY.

**Step 4: Run host tests**

Run: `powershell -ExecutionPolicy Bypass -File tools/run_host_tests.ps1`

Expected: `pager core tests passed`.

### Task 3: Raise the frame target and keep bounded rendering

**Files:**
- Modify: `ports/rp2040-zero/tests/test_pager_core.c`
- Modify: `ports/rp2040-zero/firmware/include/display_scene.h`
- Modify if required: `ports/rp2040-zero/firmware/src/display_scene.c`
- Modify if required: `ports/rp2040-zero/src/main.cpp`

**Step 1: Write the failing timing test**

Require `PAGER_SCENE_FRAME_MS == 16U` and verify every piece clip remains inside the 240x240 scene for a full READY orbit.

**Step 2: Run host tests to verify failure**

Run: `powershell -ExecutionPolicy Bypass -File tools/run_host_tests.ps1`

Expected: FAIL while the frame target remains 25 ms.

**Step 3: Implement the minimal scheduler/render change**

Change the target interval to 16 ms, preserve time-based sampling, and keep the generated rotation-safe clip bounds. Do not add full-frame per-pixel work to READY.

**Step 4: Run all focused tests**

Run: `python -m pytest tools/test_blossom_asset.py tools/test_petal_preview_geometry.py tools/test_rp2040_display_ui.py -q`

Run: `powershell -ExecutionPolicy Bypass -File tools/run_host_tests.ps1`

Expected: all tests pass.

### Task 4: Build and flash

**Files:**
- Verify: `tools/build_rp2040.ps1`
- Output: `build-rp2040/codex_usb_pager_rp2040.uf2`

**Step 1: Build with the ASCII staging script**

Run: `powershell -ExecutionPolicy Bypass -File tools/build_rp2040.ps1`

Expected: the UF2 is generated without a lingering compiler or PDB process.

**Step 2: Verify the artifact**

Check the UF2 exists, has nonzero size, and has a fresh timestamp.

**Step 3: Detect BOOTSEL**

Check mounted volumes for `RPI-RP2`. If present, copy the UF2 directly. If absent, ask the user to enter BOOTSEL once.

**Step 4: Verify flashing completed**

Confirm the `RPI-RP2` volume disappears after the copy and report the exact UF2 path, test results, and any local environment issue with a repair recommendation.
