# Multi-Task Running Visual Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve the existing smooth foreground RUNNING Blossom while showing one complete blurred background Blossom for each additional active Codex task, capped at three ghosts.

**Architecture:** Keep `PAGER_MULTI` as the existing priority-selected semantic state, but propagate `pager_snapshot_t.running` into `display_ui`. Store ghost-count transitions independently from `pager_blossom_motion_t` so RUNNING-to-MULTI changes never restart the foreground phase. Extend the prepared full-mask renderer with up to three complete Blossom ghost layers and render those layers with a low-cost 2 x 2 sampling path.

**Tech Stack:** RP2040 Pico SDK C, ST7789 RGB565 renderer, 4-bpp Blossom masks, CMake/CTest host tests, PowerShell UF2 build and Windows RPI-RP2 flashing.

## Global Constraints

- The foreground uses the canonical complete `g_blossom_alpha_4bpp` mask.
- No multi-task path may use `g_blossom_piece_alpha_4bpp`.
- Additional tasks map to `min(running_count - 1, 3)` background ghosts.
- The foreground keeps the existing RUNNING purple, centered rotation, acceleration, and scale pulse.
- Ghosts use deep blue, blue-violet, and cyan-violet in decreasing opacity.
- Ghost direction alternates counter-clockwise, clockwise, counter-clockwise.
- Ghost periods are 5.6 s, 4.8 s, and 6.4 s.
- Ghost scales are 1.08, 1.16, and 1.24 times the foreground scale.
- Ghost base opacities are 30%, 23%, and 17%.
- Ghost-count fades last 320 ms.
- The display frame interval remains 16 ms.
- The white full-screen hex outline remains unchanged.
- GP14 drives the active-low buzzer: HIGH is silent and LOW is active.
- Boot, WAIT, DONE, and ERROR map to 1, 3, 1, and 5 non-blocking pulses.
- Each pulse is 25 ms with 180 ms silent spacing; RUNNING and MULTI are silent.
- WAIT, DONE, ERROR, OFFLINE, balance, USB parsing, and priority behavior remain unchanged.

---

### Task 1: Preserve Running Count Through the Display Boundary

**Files:**
- Modify: `ports/rp2040-zero/firmware/include/display_ui.h`
- Modify: `ports/rp2040-zero/firmware/src/display_ui.c`
- Modify: `ports/rp2040-zero/firmware/include/display_scene.h`
- Modify: `ports/rp2040-zero/firmware/src/display_scene.c`
- Modify: `ports/rp2040-zero/firmware/src/main.c`
- Modify: `ports/rp2040-zero/tests/test_pager_core.c`
- Test: `tools/test_rp2040_display_ui.py`

**Interfaces:**
- Consumes: `pager_snapshot_t.running` from `pager_core.h`.
- Produces: `pager_display_ui_set_snapshot(pager_state_t state, uint32_t running_count, const char *balance, uint32_t now_ms)`.
- Produces: `pager_scene_ghost_count(pager_state_t state, uint32_t running_count) -> uint8_t` for host-testable count mapping.

- [ ] **Step 1: Add failing count-mapping and source-contract tests**

Add to `ports/rp2040-zero/tests/test_pager_core.c`:

```c
static void test_display_ghost_count_caps_additional_tasks(void) {
    assert(pager_scene_ghost_count(PAGER_RUNNING, 1U) == 0U);
    assert(pager_scene_ghost_count(PAGER_MULTI, 2U) == 1U);
    assert(pager_scene_ghost_count(PAGER_MULTI, 3U) == 2U);
    assert(pager_scene_ghost_count(PAGER_MULTI, 4U) == 3U);
    assert(pager_scene_ghost_count(PAGER_MULTI, 99U) == 3U);
    assert(pager_scene_ghost_count(PAGER_WAIT, 3U) == 0U);
}
```

Register it in the existing `main()` test list.

Add to `tools/test_rp2040_display_ui.py`:

```python
MAIN_SOURCE = (
    ROOT / "ports/rp2040-zero/firmware/src/main.c"
).read_text(encoding="ascii")
UI_HEADER = (
    ROOT / "ports/rp2040-zero/firmware/include/display_ui.h"
).read_text(encoding="ascii")


def test_main_forwards_running_count_to_display_snapshot():
    assert "state, snapshot.running, snapshot.balance, current_ms" in MAIN_SOURCE


def test_snapshot_api_accepts_running_count():
    assert "pager_state_t state, uint32_t running_count," in UI_HEADER
```

- [ ] **Step 2: Run the focused tests and verify failure**

Run:

```powershell
python -m pytest tools/test_rp2040_display_ui.py -q
cmake --build build-rp2040-host
ctest --test-dir build-rp2040-host --output-on-failure
```

Expected: Python source-contract tests fail because the API has no count, and the C test fails to compile because `pager_scene_ghost_count` is undefined.

- [ ] **Step 3: Implement count propagation and capped mapping**

Declare in `display_ui.h`:

```c
void pager_display_ui_set_snapshot(
    pager_state_t state,
    uint32_t running_count,
    const char *balance,
    uint32_t now_ms);
```

Declare in `display_scene.h` and implement in `display_scene.c`:

```c
uint8_t pager_scene_ghost_count(
    pager_state_t state, uint32_t running_count) {
    uint32_t additional;

    if (state != PAGER_MULTI || running_count < 2U) {
        return 0U;
    }
    additional = running_count - 1U;
    return (uint8_t)(additional > 3U ? 3U : additional);
}
```

Use `pager_scene_ghost_count` from `display_ui.c`, store the latest count, and
pass it from `main.c`:

```c
pager_display_ui_set_snapshot(
    state, snapshot.running, snapshot.balance, current_ms);
```

Keep `pager_display_ui_set_state` forwarding the stored count so timeout and legacy callers retain a valid API path.

- [ ] **Step 4: Run focused tests and verify success**

Run the same commands from Step 2.

Expected: all focused Python and C host tests pass.

- [ ] **Step 5: Commit the count boundary**

```powershell
git add ports/rp2040-zero/firmware/include/display_ui.h ports/rp2040-zero/firmware/src/display_ui.c ports/rp2040-zero/firmware/include/display_scene.h ports/rp2040-zero/firmware/src/display_scene.c ports/rp2040-zero/firmware/src/main.c ports/rp2040-zero/tests/test_pager_core.c tools/test_rp2040_display_ui.py
git commit -m "feat: retain running task count in display ui"
```

---

### Task 2: Define Complete Blossom Ghost Layers

**Files:**
- Modify: `ports/rp2040-zero/firmware/include/display_scene.h`
- Modify: `ports/rp2040-zero/firmware/src/display_scene.c`
- Modify: `ports/rp2040-zero/tests/test_pager_core.c`
- Test: `tools/test_rp2040_display_ui.py`

**Interfaces:**
- Consumes: foreground `pager_blossom_model_t`, `ghost_count`, and per-ghost opacity values from `display_ui`.
- Produces: `pager_scene_prepare_render_context(..., uint8_t ghost_count, const uint8_t ghost_opacity[3], uint32_t motion_ms, ...)`.
- Produces: `pager_scene_render_context_t.ghosts[3]` and `.ghost_count`.

- [ ] **Step 1: Add failing context tests for full-mask ghosts**

Add to `ports/rp2040-zero/tests/test_pager_core.c`:

```c
#include "blossom_asset.h"

static void test_multi_context_builds_complete_blossom_ghosts(void) {
    pager_blossom_motion_t motion;
    pager_blossom_model_t model;
    pager_scene_render_context_t context;
    const uint8_t opacity[3] = {77U, 59U, 43U};

    pager_blossom_motion_init(&motion, PAGER_RUNNING, 0U);
    pager_blossom_motion_sample(&motion, 1200U, &model);
    pager_scene_prepare_render_context(
        &model, "NA", 3U, opacity, 1200U, &context);

    assert(context.ghost_count == 3U);
    assert(context.ghosts[0].mask_4bpp == g_blossom_alpha_4bpp);
    assert(context.ghosts[1].mask_4bpp == g_blossom_alpha_4bpp);
    assert(context.ghosts[2].mask_4bpp == g_blossom_alpha_4bpp);
    assert(!context.petals_visible);
    assert(context.ghosts[0].opacity > context.ghosts[1].opacity);
    assert(context.ghosts[1].opacity > context.ghosts[2].opacity);
}
```

Add source guards to `tools/test_rp2040_display_ui.py`:

```python
def test_multi_ghosts_use_complete_blossom_masks():
    assert "ghosts[PAGER_MULTI_GHOST_MAX]" in SCENE_HEADER
    assert "g_blossom_alpha_4bpp" in SCENE_SOURCE
    assert "context->ghosts" in SCENE_SOURCE


def test_multi_ghost_palette_has_no_yellow_or_ready_petals():
    ghost_helper = SCENE_SOURCE.split(
        "static void prepare_multi_ghosts", 1
    )[1].split("void pager_scene_prepare_render_context", 1)[0]
    assert "PAGER_BLOSSOM_WAIT_COLOR" not in ghost_helper
    assert "g_blossom_piece_alpha_4bpp" not in ghost_helper
```

- [ ] **Step 2: Run focused tests and verify failure**

Run:

```powershell
python -m pytest tools/test_rp2040_display_ui.py -q
cmake --build build-rp2040-host
ctest --test-dir build-rp2040-host --output-on-failure
```

Expected: context signature and ghost fields are missing.

- [ ] **Step 3: Add prepared ghost-layer fields and constants**

Add to `display_scene.h`:

```c
#define PAGER_MULTI_GHOST_MAX 3U
#define PAGER_MULTI_GHOST_FADE_MS 320U

typedef struct {
    pager_scene_prepared_layer_t pieces[BLOSSOM_PIECE_COUNT];
    pager_scene_prepared_layer_t full;
    pager_scene_prepared_layer_t ghosts[PAGER_MULTI_GHOST_MAX];
    char value_text[5];
    uint8_t value_length;
    uint8_t balance_opacity;
    int16_t value_left;
    int16_t value_top;
    uint8_t ghost_count;
    bool petals_visible;
    bool full_visible;
} pager_scene_render_context_t;
```

In `display_scene.c`, define fixed ghost colors and motion:

```c
static const uint16_t ghost_period_ms[PAGER_MULTI_GHOST_MAX] =
    {5600U, 4800U, 6400U};
static const uint16_t ghost_scale_ratio_q12[PAGER_MULTI_GHOST_MAX] =
    {4424U, 4751U, 5079U};
static const uint8_t ghost_base_opacity[PAGER_MULTI_GHOST_MAX] =
    {77U, 59U, 43U};
```

Use `pager_scene_rgb565(64, 92, 238)`,
`pager_scene_rgb565(112, 86, 244)`, and
`pager_scene_rgb565(76, 180, 224)` for the three layers.

Prepare every ghost with `make_mask_layer_at`, center
`PAGER_SCENE_CENTER_X/Y`, and `g_blossom_alpha_4bpp`. Compute angle directly
from `motion_ms`; negate the first and third angles to alternate direction.
Compute each output scale from the current foreground scale:

```c
const uint16_t ghost_scale = (uint16_t)(
    ((uint32_t)model->pieces[0].scale_q12 *
     ghost_scale_ratio_q12[index] + 2048U) >> 12U);
```

Update every existing `pager_scene_prepare_render_context` call site. Pass zero
ghost count and zero opacity for non-MULTI callers so all existing state
rendering remains unchanged.

- [ ] **Step 4: Run focused tests and verify success**

Run the commands from Step 2.

Expected: complete-mask context tests pass and existing rendering tests remain green.

- [ ] **Step 5: Commit complete ghost-layer preparation**

```powershell
git add ports/rp2040-zero/firmware/include/display_scene.h ports/rp2040-zero/firmware/src/display_scene.c ports/rp2040-zero/tests/test_pager_core.c tools/test_rp2040_display_ui.py
git commit -m "feat: prepare complete Blossom multi-task ghosts"
```

---

### Task 3: Add Independent Ghost Fades Without Restarting Foreground Motion

**Files:**
- Modify: `ports/rp2040-zero/firmware/src/display_ui.c`
- Modify: `ports/rp2040-zero/firmware/src/display_scene.c`
- Modify: `ports/rp2040-zero/firmware/include/display_scene.h`
- Modify: `ports/rp2040-zero/tests/test_pager_core.c`
- Test: `tools/test_rp2040_display_ui.py`

**Interfaces:**
- Consumes: capped ghost count from Task 1 and prepared layers from Task 2.
- Produces: `pager_scene_ghost_opacity(uint8_t from_count, uint8_t to_count, uint32_t elapsed_ms, uint8_t output[3])`.
- Preserves: `pager_blossom_motion_t` target and phase when only RUNNING/MULTI classification changes.

- [ ] **Step 1: Add failing fade and phase-continuity tests**

Add host-testable fade assertions:

```c
static void test_ghost_count_transition_fades_only_changed_layers(void) {
    uint8_t opacity[3];

    pager_scene_ghost_opacity(1U, 3U, 0U, opacity);
    assert(opacity[0] == 255U);
    assert(opacity[1] == 0U);
    assert(opacity[2] == 0U);

    pager_scene_ghost_opacity(1U, 3U, 160U, opacity);
    assert(opacity[0] == 255U);
    assert(opacity[1] > 0U && opacity[1] < 255U);
    assert(opacity[2] > 0U && opacity[2] < 255U);

    pager_scene_ghost_opacity(1U, 3U, 320U, opacity);
    assert(opacity[0] == 255U);
    assert(opacity[1] == 255U);
    assert(opacity[2] == 255U);
}
```

Add a source-contract test:

```python
def test_running_multi_switch_does_not_retarget_foreground_motion():
    assert "running_family_change" in UI_SOURCE
    assert "if (!running_family_change)" in UI_SOURCE
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
python -m pytest tools/test_rp2040_display_ui.py -q
cmake --build build-rp2040-host
ctest --test-dir build-rp2040-host --output-on-failure
```

Expected: fade helper and running-family guard are absent.

- [ ] **Step 3: Implement independent ghost transition state**

Add to `display_ui.c`:

```c
static uint8_t ghost_from_count;
static uint8_t ghost_to_count;
static uint32_t ghost_transition_started_ms;

static bool is_running_family(pager_state_t state) {
    return state == PAGER_RUNNING || state == PAGER_MULTI;
}
```

Declare in `display_scene.h` and implement
`pager_scene_ghost_opacity` in `display_scene.c` with smoothstep progress:

```c
void pager_scene_ghost_opacity(
    uint8_t from_count,
    uint8_t to_count,
    uint32_t elapsed_ms,
    uint8_t output[PAGER_MULTI_GHOST_MAX]) {
    const uint32_t t = elapsed_ms >= PAGER_MULTI_GHOST_FADE_MS
        ? 32768U
        : (elapsed_ms * 32768U) / PAGER_MULTI_GHOST_FADE_MS;
    const uint32_t smooth =
        (t * t >> 15U) * (3U * 32768U - 2U * t) >> 15U;
    uint8_t index;

    for (index = 0U; index < PAGER_MULTI_GHOST_MAX; ++index) {
        const bool was_visible = index < from_count;
        const bool is_visible = index < to_count;
        output[index] = was_visible == is_visible
            ? (was_visible ? 255U : 0U)
            : (is_visible
                ? (uint8_t)((smooth * 255U + 16384U) >> 15U)
                : (uint8_t)(255U -
                    ((smooth * 255U + 16384U) >> 15U)));
    }
}
```

When a snapshot changes ghost count, snapshot the current effective visibility,
set the new target, record `now_ms`, and force the next frame.

When switching only between `PAGER_RUNNING` and `PAGER_MULTI`, update
`current_state` but do not call `pager_blossom_motion_set_target`. Other state
changes retain the existing transition call.

- [ ] **Step 4: Render ghosts with true 2 x 2 sampling**

Add `pager_scene_render_prepared_row_pair` to `display_scene.h/.c`. It accepts
two destination rows for adjacent screen rows:

```c
void pager_scene_render_prepared_row_pair(
    pager_state_t state,
    uint32_t elapsed_ms,
    const pager_scene_render_context_t *context,
    int16_t x_start,
    int16_t y,
    uint16_t pixel_count,
    uint16_t *top_pixels,
    uint16_t *bottom_pixels);
```

For each ghost and each even horizontal offset:

1. sample the ghost mask once at `(x, y)`;
2. reuse that alpha for `(x + 1, y)`, `(x, y + 1)`, and
   `(x + 1, y + 1)`;
3. blend ghosts in back-to-front order;
4. sample and blend the foreground separately at all four pixels.

Change `render_scene` in `display_ui.c` to advance by two rows and call this
pair renderer. When either the current or previously rendered state is MULTI,
select the full-frame/delta transport branch so MULTI never enters the
piece-oriented dirty-tile path. Non-MULTI dirty-tile rendering remains
unchanged.

Add this source-contract test to `tools/test_rp2040_display_ui.py`:

```python
def test_multi_ghosts_are_sampled_once_per_two_by_two_block():
    pair = SCENE_SOURCE.split(
        "void pager_scene_render_prepared_row_pair", 1
    )[1].split("void pager_scene_render_motion_span", 1)[0]
    assert "pixel += 2U" in pair
    assert "top_pixels[pixel + 1U]" in pair
    assert "bottom_pixels[pixel]" in pair
    assert "bottom_pixels[pixel + 1U]" in pair
```

- [ ] **Step 5: Run focused and full host tests**

Run:

```powershell
python -m pytest tools -q
cmake --build build-rp2040-host
ctest --test-dir build-rp2040-host --output-on-failure
```

Expected: all tests pass; no legacy MULTI READY-petal path is selected.

- [ ] **Step 6: Commit motion continuity and rendering**

```powershell
git add ports/rp2040-zero/firmware/src/display_ui.c ports/rp2040-zero/firmware/src/display_scene.c ports/rp2040-zero/firmware/include/display_scene.h ports/rp2040-zero/tests/test_pager_core.c tools/test_rp2040_display_ui.py
git commit -m "feat: animate multi-task Blossom ghost layers"
```

---

### Task 4: Add the Active-Low Non-Blocking Buzzer

**Files:**
- Create: `ports/rp2040-zero/firmware/include/buzzer.h`
- Create: `ports/rp2040-zero/firmware/src/buzzer.c`
- Modify: `ports/rp2040-zero/firmware/src/main.c`
- Modify: `ports/rp2040-zero/firmware/CMakeLists.txt`
- Modify: `ports/rp2040-zero/tests/CMakeLists.txt`
- Modify: `ports/rp2040-zero/tests/test_pager_core.c`
- Test: `tools/test_rp2040_display_ui.py`

**Interfaces:**
- Consumes: `pager_event_t` from `pager_core.h` and `PAGER_BUZZER_PIN` from `board_config.h`.
- Produces: `pager_buzzer_event_pulses(pager_event_t event) -> uint8_t`.
- Produces: `pager_buzzer_start(pager_buzzer_t *buzzer, uint8_t pulses, uint32_t now_ms)` and `pager_buzzer_update(pager_buzzer_t *buzzer, uint32_t now_ms) -> bool`.

- [ ] **Step 1: Write failing scheduler and source-contract tests**

Add to `ports/rp2040-zero/tests/test_pager_core.c`:

```c
static void test_buzzer_event_pulse_counts_and_nonblocking_timing(void) {
    pager_buzzer_t buzzer;

    assert(pager_buzzer_event_pulses(PAGER_EVENT_NONE) == 0U);
    assert(pager_buzzer_event_pulses(PAGER_EVENT_WAIT) == 3U);
    assert(pager_buzzer_event_pulses(PAGER_EVENT_DONE) == 1U);
    assert(pager_buzzer_event_pulses(PAGER_EVENT_ERROR) == 5U);

    pager_buzzer_init(&buzzer, 0U);
    pager_buzzer_start(&buzzer, 3U, 0U);
    assert(pager_buzzer_is_active(&buzzer));
    assert(!pager_buzzer_update(&buzzer, 24U));
    assert(pager_buzzer_update(&buzzer, 25U));
    assert(!pager_buzzer_is_active(&buzzer));
    assert(!pager_buzzer_update(&buzzer, 204U));
    assert(pager_buzzer_update(&buzzer, 205U));
    assert(pager_buzzer_is_active(&buzzer));
}
```

Add to `tools/test_rp2040_display_ui.py`:

```python
def test_main_configures_active_low_buzzer_on_gp14():
    assert "gpio_init(PAGER_BUZZER_PIN)" in MAIN_SOURCE
    assert "gpio_put(PAGER_BUZZER_PIN, true)" in MAIN_SOURCE
    assert "gpio_put(PAGER_BUZZER_PIN, !pager_buzzer_is_active" in MAIN_SOURCE


def test_multi_task_state_does_not_trigger_buzzer():
    assert "pager_buzzer_event_pulses(snapshot.event)" in MAIN_SOURCE
    assert "PAGER_MULTI" not in MAIN_SOURCE.split(
        "pager_buzzer_event_pulses", 1
    )[1].split("pager_display_ui_update", 1)[0]
```

- [ ] **Step 2: Run focused tests and verify failure**

Run:

```powershell
python -m pytest tools/test_rp2040_display_ui.py -q
cmake --build build-rp2040-host
ctest --test-dir build-rp2040-host --output-on-failure
```

Expected: the buzzer scheduler types and source hooks are missing.

- [ ] **Step 3: Implement the pure buzzer scheduler**

Create `buzzer.h`:

```c
#ifndef CODEX_BUZZER_H
#define CODEX_BUZZER_H

#include "pager_core.h"

#include <stdbool.h>
#include <stdint.h>

#define PAGER_BUZZER_ON_MS 25U
#define PAGER_BUZZER_GAP_MS 180U

typedef struct {
    uint8_t remaining;
    bool active;
    uint32_t changed_ms;
} pager_buzzer_t;

uint8_t pager_buzzer_event_pulses(pager_event_t event);
void pager_buzzer_init(pager_buzzer_t *buzzer, uint32_t now_ms);
void pager_buzzer_start(
    pager_buzzer_t *buzzer, uint8_t pulses, uint32_t now_ms);
bool pager_buzzer_update(pager_buzzer_t *buzzer, uint32_t now_ms);
bool pager_buzzer_is_active(const pager_buzzer_t *buzzer);

#endif
```

Implement `buzzer.c` so `pager_buzzer_start` begins the first active pulse
immediately, `pager_buzzer_update` changes state only after the configured
duration, and returns true only on an output change. Map WAIT/DONE/ERROR to
3/1/5 and all other events to zero.

- [ ] **Step 4: Connect GP14 in the RP2040 entry point**

In `main.c`, include `buzzer.h`, configure GP14 as a GPIO output before the
main loop, and set it HIGH before starting USB:

```c
gpio_init(PAGER_BUZZER_PIN);
gpio_set_dir(PAGER_BUZZER_PIN, GPIO_OUT);
gpio_put(PAGER_BUZZER_PIN, true);
```

Start the boot pulse once after initialization:

```c
pager_buzzer_init(&buzzer, last_valid_snapshot_ms);
pager_buzzer_start(&buzzer, 1U, last_valid_snapshot_ms);
```

For every parsed snapshot, trigger only a newly observed non-NONE event. Keep
`last_buzzer_event`; clear it when `snapshot.event` returns to NONE. In the
main loop write the active-low pin only when the scheduler changes:

```c
if (pager_buzzer_update(&buzzer, current_ms)) {
    gpio_put(PAGER_BUZZER_PIN, !pager_buzzer_is_active(&buzzer));
}
```

Add `src/buzzer.c` to both RP2040 firmware and host-test CMake source lists.

- [ ] **Step 5: Run focused and full host tests**

Run:

```powershell
python -m pytest tools/test_rp2040_display_ui.py -q
cmake --build build-rp2040-host
ctest --test-dir build-rp2040-host --output-on-failure
python -m pytest tools -q
```

Expected: all existing tests pass and the host buzzer timing test proves that
the 25 ms/180 ms sequence advances without sleeps or blocking calls.

- [ ] **Step 6: Commit buzzer support**

```powershell
git add ports/rp2040-zero/firmware/include/buzzer.h ports/rp2040-zero/firmware/src/buzzer.c ports/rp2040-zero/firmware/src/main.c ports/rp2040-zero/firmware/CMakeLists.txt ports/rp2040-zero/tests/CMakeLists.txt ports/rp2040-zero/tests/test_pager_core.c tools/test_rp2040_display_ui.py
git commit -m "feat: add nonblocking active-low buzzer"
```

---

### Task 5: Build, Flash, and Verify Two-Conversation Behavior

**Files:**
- Inspect after measured evidence: `ports/rp2040-zero/firmware/src/display_scene.c`
- Build output: `build-rp2040/codex_pager_rp2040.uf2`
- Update: `ports/rp2040-zero/README.md`

**Interfaces:**
- Consumes: completed host-tested firmware.
- Produces: flashed RP2040-Zero and physical acceptance results.

- [ ] **Step 1: Run the complete verification suite**

Run:

```powershell
powershell -ExecutionPolicy Bypass -File tools/run_host_tests.ps1
```

Expected: Python tests and RP2040 host C tests all pass.

- [ ] **Step 2: Build a release UF2**

Run:

```powershell
powershell -ExecutionPolicy Bypass -File tools/build_rp2040.ps1
```

Expected: `build-rp2040/codex_pager_rp2040.uf2` exists, has a non-zero size,
and the build completes without PDB-server hangs.

- [ ] **Step 3: Flash when RPI-RP2 is present**

Verify the boot drive:

```powershell
Get-Volume | Where-Object FileSystemLabel -eq 'RPI-RP2'
```

Copy the UF2 to the returned drive:

```powershell
Copy-Item -LiteralPath build-rp2040/codex_pager_rp2040.uf2 -Destination 'D:\codex_pager_rp2040.uf2'
```

Use the actual detected drive letter rather than assuming `D:`.

Expected: the RPI-RP2 drive disconnects after copying and the firmware starts.

- [ ] **Step 4: Run state-level smoke tests**

Send:

```powershell
python tools/send_pager.py RUNNING --run 1
python tools/send_pager.py RUNNING --run 2
python tools/send_pager.py RUNNING --run 3
python tools/send_pager.py RUNNING --run 4
python tools/send_pager.py WAIT --wait 1 --event WAIT
python tools/send_pager.py DONE --done 1 --event DONE
python tools/send_pager.py ERROR --event ERROR
python tools/send_pager.py READY --run 0
```

Expected:

- RUN=1: sharp purple foreground only.
- RUN=2: one deep-blue softened ghost.
- RUN=3: two softened ghosts.
- RUN=4: three softened ghosts.
- WAIT: three quiet, short active-low buzzer pulses.
- DONE: one quiet, short active-low buzzer pulse.
- ERROR: five quiet, short active-low buzzer pulses.
- READY: all ghosts fade out and the existing READY design returns.

- [ ] **Step 5: Verify real concurrent Codex tasks**

Start two Codex conversations simultaneously.

Expected:

- the second task produces one ghost on the first display frame after the
  snapshot reaches the board;
- the foreground does not jump, restart, turn yellow, or split into petals;
- completing either task fades the surplus ghost out over 320 ms;
- completing all tasks returns through the existing RUNNING-to-READY path.
- entering or leaving MULTI does not produce a buzzer pulse.

- [ ] **Step 6: Record physical tuning and update documentation**

Document observed frame rate, visibility, and any color adjustment in
`ports/rp2040-zero/README.md`. Only tune ghost RGB565 constants or opacity after
physical evidence; do not alter the foreground Blossom or hex geometry.

- [ ] **Step 7: Commit verified firmware documentation**

```powershell
git add ports/rp2040-zero/README.md
git commit -m "docs: record multi-task display verification"
```
