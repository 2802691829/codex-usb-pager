# Blossom State Transitions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement seamless six-piece Blossom animations for OFFLINE, READY, RUNNING, and the transitions between them on the RP2040 pager.

**Architecture:** Extend the generated Blossom asset with a packed six-piece ownership map whose union is the existing official alpha mask. Add a fixed-point scene-motion model that captures the current six-piece pose when a state changes, then renders state-specific continuous transitions without replacing the assembled pieces or freezing a frame. Keep the existing RGB565 scene buffer, 25 ms pacing, PIO, DMA, USB protocol, and non-Blossom status priority.

**Tech Stack:** Python 3, Pillow, C11, RP2040 Pico SDK, CMake/CTest, pytest, ST7789 RGB565 renderer.

## Global Constraints

- OFFLINE color is logical RGB `#738094`.
- READY color is logical RGB `#39D298`.
- RUNNING color is logical RGB `#6449E0`.
- READY to RUNNING uses 900 ms gather, 150 ms whole-logo hold, and 400 ms recolor before rotation begins.
- RUNNING or DONE to READY uses 350 ms deceleration, 350 ms recolor, and 800 ms separation.
- OFFLINE to READY lasts 1,200 ms and does not assemble the full Blossom.
- The weekly balance is an integer without a percent sign and appears only in READY.
- Six assembled piece masks must equal the official Blossom mask byte for byte.
- Animation uses elapsed time, fixed-point math, no per-frame heap allocation, and a 25 ms target frame interval.
- The verified ST7789 profile, 24 MHz display transport, 172 x 172 scene region, GPIO mapping, and USB protocol remain unchanged.

---

### Task 1: Generate A Lossless Six-Piece Blossom Asset

**Files:**
- Modify: `tools/generate_blossom_asset.py`
- Modify: `tools/test_blossom_asset.py`
- Regenerate: `Core/Inc/blossom_asset.h`
- Regenerate: `Core/Src/blossom_asset.c`

**Interfaces:**
- Produces: `partition_blossom(svg_path: Path, mask: Image.Image) -> Image.Image`
- Produces: `pack_piece_ids(piece_ids: Image.Image) -> bytes`
- Produces: `g_blossom_piece_id_4bpp[BLOSSOM_PIECE_ID_BYTES]`
- Produces: IDs `0` for background and `1..6` for the six woven pieces.

- [ ] **Step 1: Add failing asset-partition tests**

```python
def test_piece_partition_is_lossless():
    mask = rasterize_svg(SVG, size=128, supersample=4)
    pieces = partition_blossom(SVG, mask)
    mask_values = list(mask.getdata())
    piece_values = list(pieces.getdata())

    assert set(piece_values) <= set(range(7))
    assert all(
        (alpha == 0 and piece == 0) or (alpha > 0 and 1 <= piece <= 6)
        for alpha, piece in zip(mask_values, piece_values)
    )
    assert {piece for piece in piece_values if piece} == set(range(1, 7))


def test_piece_ids_pack_two_pixels_per_byte():
    mask = rasterize_svg(SVG, size=128, supersample=4)
    pieces = partition_blossom(SVG, mask)
    packed = pack_piece_ids(pieces)
    assert len(packed) == 128 * 128 // 2
```

- [ ] **Step 2: Run the focused tests and verify failure**

Run:

```powershell
python -m pytest tools/test_blossom_asset.py -q
```

Expected: collection fails because `partition_blossom` and
`pack_piece_ids` do not exist.

- [ ] **Step 3: Implement six-piece ownership**

Parse the official SVG subpaths, identify the six non-central interior holes,
rasterize each hole at the mask resolution, and calculate a two-pass chamfer
distance map for each hole. Assign every nonzero Blossom alpha pixel to the
nearest outer-hole map, sorting holes by polar angle so piece IDs are stable.
Pack two four-bit IDs per byte:

```python
def pack_piece_ids(piece_ids):
    values = list(piece_ids.getdata())
    if len(values) % 2:
        values.append(0)
    return bytes(
        ((values[index] & 0x0F) << 4) | (values[index + 1] & 0x0F)
        for index in range(0, len(values), 2)
    )
```

Update `emit_c` so the header declares:

```c
#define BLOSSOM_PIECE_COUNT 6U
#define BLOSSOM_PIECE_ID_BYTES 8192U
extern const uint8_t
    g_blossom_piece_id_4bpp[BLOSSOM_PIECE_ID_BYTES];
```

- [ ] **Step 4: Regenerate and test the assets**

Run:

```powershell
python tools/generate_blossom_asset.py
python -m pytest tools/test_blossom_asset.py -q
```

Expected: all Blossom asset tests pass and the generated C file contains
exactly `8192` alpha bytes plus `8192` piece-ID bytes.

- [ ] **Step 5: Commit the asset work**

```powershell
git add tools/generate_blossom_asset.py tools/test_blossom_asset.py Core/Inc/blossom_asset.h Core/Src/blossom_asset.c
git commit -m "feat: generate lossless blossom pieces"
```

### Task 2: Add The Fixed-Point Blossom Motion Model

**Files:**
- Create: `ports/rp2040-zero/firmware/include/blossom_motion.h`
- Create: `ports/rp2040-zero/firmware/src/blossom_motion.c`
- Modify: `ports/rp2040-zero/firmware/CMakeLists.txt`
- Modify: `ports/rp2040-zero/tests/CMakeLists.txt`
- Modify: `ports/rp2040-zero/tests/test_pager_core.c`

**Interfaces:**
- Produces: `pager_blossom_piece_pose_t`
- Produces: `pager_blossom_model_t`
- Produces: `pager_blossom_motion_t`
- Produces: `void pager_blossom_motion_init(...)`
- Produces: `void pager_blossom_motion_set_target(...)`
- Produces: `void pager_blossom_motion_sample(...)`

- [ ] **Step 1: Add failing motion tests**

Add tests that assert:

```c
assert(PAGER_READY_TO_RUNNING_MS == 1450U);
assert(PAGER_RUNNING_TO_READY_MS == 1500U);
assert(PAGER_OFFLINE_TO_READY_MS == 1200U);
```

Sample READY to RUNNING at `0`, `900`, `1050`, and `1450` ms and verify:

- position starts separated and ends assembled;
- balance opacity reaches zero before recolor;
- all six pieces are green at 1050 ms;
- all six pieces are deep purple at 1450 ms;
- running angular velocity is zero before 1450 ms and positive afterward.

Sample RUNNING to READY and OFFLINE to READY endpoints and verify their piece
positions, colors, balance opacity, and ordered-orbit flags.

- [ ] **Step 2: Run the C host tests and verify failure**

Run:

```powershell
cmake -S ports/rp2040-zero/tests -B build-rp2040-host
cmake --build build-rp2040-host
ctest --test-dir build-rp2040-host --output-on-failure
```

Expected: compilation fails because `blossom_motion.h` is absent.

- [ ] **Step 3: Implement the motion data structures**

Use these public structures:

```c
typedef struct {
    int16_t center_x_q8;
    int16_t center_y_q8;
    int16_t angle_q8;
    uint16_t scale_q12;
    uint16_t color;
    uint8_t opacity;
} pager_blossom_piece_pose_t;

typedef struct {
    pager_blossom_piece_pose_t pieces[BLOSSOM_PIECE_COUNT];
    uint8_t balance_opacity;
    int16_t angular_velocity_q8;
    bool assembled;
} pager_blossom_model_t;

typedef struct {
    pager_state_t source;
    pager_state_t target;
    uint32_t started_ms;
    pager_blossom_model_t start;
    pager_blossom_model_t current;
} pager_blossom_motion_t;
```

Use Q15 smoothstep interpolation and the existing sine table. READY targets
are six evenly spaced positions on the orbit. OFFLINE targets use six fixed,
asymmetric anchors plus independent sine phases. RUNNING targets share the
display center and zero relative piece angles.

- [ ] **Step 4: Implement interruption from the current pose**

`pager_blossom_motion_set_target` first samples the active motion at `now_ms`,
copies `current` to `start`, and then changes `source`, `target`, and
`started_ms`. It must never reset pieces to a canned source endpoint.

- [ ] **Step 5: Run motion tests**

Run the host configure, build, and CTest commands from Step 2.

Expected: all existing tests and the new motion tests pass.

- [ ] **Step 6: Commit the motion model**

```powershell
git add ports/rp2040-zero/firmware/include/blossom_motion.h ports/rp2040-zero/firmware/src/blossom_motion.c ports/rp2040-zero/firmware/CMakeLists.txt ports/rp2040-zero/tests/CMakeLists.txt ports/rp2040-zero/tests/test_pager_core.c
git commit -m "feat: add blossom state motion"
```

### Task 3: Render Six Pieces And Integrate State Changes

**Files:**
- Modify: `ports/rp2040-zero/firmware/include/display_scene.h`
- Modify: `ports/rp2040-zero/firmware/src/display_scene.c`
- Modify: `ports/rp2040-zero/firmware/src/display_ui.c`
- Modify: `tools/test_rp2040_display_ui.py`
- Modify: `ports/rp2040-zero/tests/test_pager_core.c`

**Interfaces:**
- Consumes: `pager_blossom_model_t`
- Produces: `pager_scene_render_model_row(...)`
- Produces: piece-aware `sampler_alpha_for_piece(...)`

- [ ] **Step 1: Add failing renderer and UI tests**

Add host tests that reconstruct the assembled frame with all six piece IDs and
compare it with the existing official full-mask frame. Add source-contract
tests that assert the specialized Blossom path does not call
`blend_from_frozen`, and that state changes call
`pager_blossom_motion_set_target`.

- [ ] **Step 2: Run focused tests and verify failure**

Run:

```powershell
python -m pytest tools/test_rp2040_display_ui.py -q
ctest --test-dir build-rp2040-host --output-on-failure
```

Expected: new assertions fail against the generic frozen-frame transition.

- [ ] **Step 3: Add piece-aware sampling**

Decode `g_blossom_piece_id_4bpp` alongside the alpha nibble:

```c
static uint8_t piece_id_value(int16_t x, int16_t y);
static uint8_t sampler_alpha_for_piece(
    logo_sampler_t *sampler, uint8_t piece_id);
```

Render six transformed piece layers from `pager_blossom_model_t`. In steady
RUNNING, use the existing single full-logo sampler for performance. In READY,
OFFLINE, and specialized transitions, use piece masks and skip sampling rows
outside each transformed piece bound.

- [ ] **Step 4: Render READY balance without a percent sign**

Change `format_balance` to return the validated one-to-three digit string
unchanged. Draw it at the scene center with opacity from the motion model.
Remove `WEEK` from READY. Preserve `BAL=NA` behavior.

- [ ] **Step 5: Replace specialized frozen-frame cross-fades**

`display_ui.c` owns one `pager_blossom_motion_t`. On every state update it
captures the current model and sets the new target. `render_frame` passes the
sampled model into the scene renderer for transitions involving OFFLINE,
READY, RUNNING, MULTI, or the end of DONE. Generic frozen-frame blending
remains only for WAIT and ERROR transitions.

- [ ] **Step 6: Run all host tests**

Run:

```powershell
python -m pytest tools/test_blossom_asset.py tools/test_rp2040_display_ui.py -q
cmake --build build-rp2040-host
ctest --test-dir build-rp2040-host --output-on-failure
```

Expected: all Python and C host tests pass.

- [ ] **Step 7: Commit renderer integration**

```powershell
git add ports/rp2040-zero/firmware/include/display_scene.h ports/rp2040-zero/firmware/src/display_scene.c ports/rp2040-zero/firmware/src/display_ui.c tools/test_rp2040_display_ui.py ports/rp2040-zero/tests/test_pager_core.c
git commit -m "feat: animate blossom state transitions"
```

### Task 4: Build, Flash, And Verify The Device

**Files:**
- Modify if required: `ports/rp2040-zero/README.md`
- Output: `build-rp2040/codex_usb_pager_rp2040.uf2`

**Interfaces:**
- Consumes: completed firmware and the existing RPI-RP2 mass-storage bootloader.
- Produces: flashed RP2040 pager with the approved state animations.

- [ ] **Step 1: Run the complete regression suite**

Run:

```powershell
python -m pytest -q
cmake --build build-rp2040-host
ctest --test-dir build-rp2040-host --output-on-failure
```

Expected: all tests pass.

- [ ] **Step 2: Build RP2040 firmware**

Run:

```powershell
powershell -ExecutionPolicy Bypass -File tools/build_rp2040.ps1
```

Expected: the UF2 is produced, flash and SRAM fit RP2040 limits, and no PDB
service remains locked.

- [ ] **Step 3: Flash the UF2**

Detect the mounted `RPI-RP2` volume and copy the generated UF2 to it. Wait for
the volume to disappear and the serial device to return. Do not ask the user
to press BOOT unless the volume is absent.

- [ ] **Step 4: Exercise live transitions**

Send or trigger, in order:

```text
OFFLINE -> READY -> RUNNING -> DONE -> READY
```

Verify on the physical panel:

- offline scatter becomes the ordered green ready orbit;
- the balance appears in the ready center;
- ready gathers into a gap-free green Blossom;
- green changes to deep purple before rotation starts;
- running rotation never intentionally pauses;
- completion returns through the green separation animation;
- no black band, square shadow, full-frame flash, or row refresh wave appears.

- [ ] **Step 5: Document verified behavior and commit**

Update the RP2040 README with the three colors, transition order, and automatic
flashing behavior, then commit:

```powershell
git add ports/rp2040-zero/README.md
git commit -m "docs: record blossom transition behavior"
```
