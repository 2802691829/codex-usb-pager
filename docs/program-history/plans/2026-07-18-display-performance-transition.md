# Display Performance And Transition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a stable 35-40 FPS RP2040 display path and a smooth 650 ms transition between all pager states.

**Architecture:** Pack two RGB565 pixels into each PIO FIFO word and transfer the complete animation region with one DMA operation. Keep two scene buffers during state changes and blend them with smoothstep easing while the incoming scene remains animated.

**Tech Stack:** RP2040 Pico SDK 2.2, C11, PIO, DMA, CMake/CTest, pytest

## Global Constraints

- Keep the verified ST7789 vendor initialization and 24 MHz SPI clock.
- Keep USB status parsing and state priority unchanged.
- Use a 25 ms frame target and a 650 ms transition.
- Do not exceed RP2040's 264 KB SRAM.

---

### Task 1: Repair Local Test Environment

**Files:**
- Create: `pytest.ini`
- Remove after ACL reset: `.pytest-rp2040`, `.pytest_tmp_abort_fix`, `.pytest_tmp_runtime_red`

**Interfaces:**
- Produces: a writable ASCII-only pytest base directory used by all Python tests.

- [ ] Reset ACLs only on the three known `.pytest-*` temporary directories.
- [ ] Remove those directories and add `pytest.ini` with `addopts = --basetemp=C:/Temp/codex-pager-pytest`.
- [ ] Run `python -m pytest -q tools/test_session_watcher.py tools/test_pager_runtime.py` and verify all tests pass without ACL warnings.

### Task 2: Pack The Display Transport

**Files:**
- Modify: `ports/rp2040-zero/firmware/src/st7789_spi.pio`
- Modify: `ports/rp2040-zero/firmware/include/st7789.h`
- Modify: `ports/rp2040-zero/firmware/src/st7789.c`
- Modify: `ports/rp2040-zero/tests/test_pager_core.c`

**Interfaces:**
- Produces: `uint32_t st7789_pack_pixel_pair(uint16_t first, uint16_t second)` and `st7789_write_packed_pixels(const uint32_t *words, size_t word_count)`.

- [ ] Add a host test asserting red then green packs as `0xF80007E0`.
- [ ] Run the host test and verify it fails because the packing API is absent.
- [ ] Change the PIO loop to shift 32 bits per pull and implement packed frame DMA.
- [ ] Run CTest and verify the packing test and existing panel-profile tests pass.

### Task 3: Add Transition Math And Faster Background Sampling

**Files:**
- Modify: `ports/rp2040-zero/firmware/include/display_scene.h`
- Modify: `ports/rp2040-zero/firmware/src/display_scene.c`
- Modify: `ports/rp2040-zero/tests/test_pager_core.c`

**Interfaces:**
- Produces: `pager_scene_transition_alpha(uint32_t elapsed_ms)` returning 0..255 and division-free background intensity.

- [ ] Add tests for alpha values at 0 ms, 325 ms, and 650 ms and for monotonic smoothstep behavior.
- [ ] Run the host test and verify it fails because the transition API is absent.
- [ ] Implement fixed-point smoothstep and replace per-pixel background division with fixed-point multiplication.
- [ ] Run CTest and verify all scene tests pass.

### Task 4: Integrate Double-Buffer State Transitions

**Files:**
- Modify: `ports/rp2040-zero/firmware/src/display_ui.c`
- Modify: `ports/rp2040-zero/firmware/include/display_scene.h`
- Modify: `ports/rp2040-zero/tests/test_pager_core.c`

**Interfaces:**
- Consumes: packed display transport and `pager_scene_transition_alpha`.
- Produces: 25 ms paced frames and 650 ms transitions without full-screen state fills.

- [ ] Add tests asserting `PAGER_SCENE_FRAME_MS == 25` and `PAGER_SCENE_TRANSITION_MS == 650`.
- [ ] Run the host test and verify it fails against the old constants.
- [ ] Render incoming state into the back buffer, blend from the frozen outgoing buffer during transition, pack in place, and submit one DMA operation.
- [ ] Build firmware and inspect the linker size output for SRAM overflow.
- [ ] Run all host and Python tests.

### Task 5: Flash And Physical Verification

**Files:**
- Update: `ports/rp2040-zero/README.md`

**Interfaces:**
- Consumes: `build-rp2040/codex_pager_rp2040.uf2`.
- Produces: verified physical display behavior.

- [ ] Record the final UF2 size and SHA-256.
- [ ] Copy UF2 to the RPI-RP2 boot volume and wait for the serial device to return.
- [ ] Send RUNNING, DONE, and IDLE states and visually verify frame rate and transition continuity.
- [ ] Document measured behavior and any remaining hardware limitation.

