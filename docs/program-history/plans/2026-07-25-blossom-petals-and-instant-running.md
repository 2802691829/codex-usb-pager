# Blossom Petals And Instant Running Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render READY/OFFLINE from six canonical, equal-width closed Blossom petals, crossfade them cleanly into the full rotating Blossom, and send RUNNING to the RP2040 within 100 ms of Codex accepting a prompt.

**Architecture:** Asset generation derives all six closed petal rings from the six outer hole contours in `assets/openai-blossom.svg` at one global scale and emits both masks and clipping metadata. Firmware motion keeps the six-petal layer and full-Blossom layer separate so transitions can move petals and crossfade masks without a geometry jump. The Windows daemon adds a read-only incremental watcher for Codex's SQLite diagnostic log while retaining JSONL for completion and fallback.

**Tech Stack:** Python 3.11, Pillow, standard-library SQLite, pytest, C11, CMake, Raspberry Pi Pico SDK, RP2040 PIO SPI, ST7789 RGB565.

## Global Constraints

- `assets/openai-blossom.svg` is the only geometry source.
- Canonical ribbon width is exactly `15.889` SVG units before raster scaling.
- All six petal rings use one global transform; never crop, fit, or normalize a petal independently.
- READY petals are green; RUNNING is a visibly deeper purple.
- READY to RUNNING aggregation lasts exactly `800 ms`.
- The first sampled RUNNING transition frame is purple.
- READY balance is centered and contains digits only.
- Existing display wiring, ST7789 profile, weekly balance, buzzer, USB CDC protocol, and state priority remain unchanged.
- SQLite prompt detection is read-only, WAL-compatible, cursor-based, and targets less than `100 ms` from log insertion to serial send.
- JSONL remains the completion source and a deduplicated prompt-start fallback.
- Do not replace generated C assets when generation fails.
- Do not stage or revert unrelated files in the existing dirty worktree.

## File Structure

- `tools/generate_blossom_asset.py`: canonical SVG rasterization, six outward petal-ring masks, packed asset data, and generated clip metadata.
- `tools/test_blossom_asset.py`: geometry, ring closure, width consistency, shared transform, and generated-output regression tests.
- `Core/Inc/blossom_asset.h`: generated asset declarations shared by STM32 and RP2040 builds.
- `Core/Src/blossom_asset.c`: generated full mask, six ring masks, and mask-bound metadata.
- `ports/rp2040-zero/firmware/include/blossom_motion.h`: transition durations and the two-layer render model.
- `ports/rp2040-zero/firmware/src/blossom_motion.c`: READY, OFFLINE, RUNNING, aggregation, separation, and recolor timelines.
- `ports/rp2040-zero/firmware/src/display_scene.c`: simultaneous petal/full-mask rendering with independent opacity.
- `ports/rp2040-zero/tests/test_pager_core.c`: host-side motion contract tests.
- `tools/codex_log_watcher.py`: focused read-only SQLite cursor and UserInput parser.
- `tools/test_codex_log_watcher.py`: temporary SQLite integration tests.
- `tools/pager_daemon.py`: combine immediate SQLite starts with JSONL completion/fallback.
- `tools/test_session_watcher.py`: daemon event integration and deduplication tests.
- `tools/render_blossom_partition_preview.py`: preview utility updated to call the production generator rather than carrying separate geometry logic.

---

### Task 1: Generate Canonical Closed Petal Rings

**Files:**
- Modify: `tools/test_blossom_asset.py`
- Modify: `tools/generate_blossom_asset.py`
- Modify: `tools/render_blossom_partition_preview.py`
- Regenerate: `Core/Inc/blossom_asset.h`
- Regenerate: `Core/Src/blossom_asset.c`

**Interfaces:**
- Consumes: `rasterize_svg(svg_path, size) -> PIL.Image.Image` and the six SVG hole contours.
- Produces: `rasterize_petals(svg_path, size, ribbon_width_svg=15.889) -> list[PIL.Image.Image]`.
- Produces: generated arrays `g_blossom_piece_min_x`, `g_blossom_piece_min_y`, `g_blossom_piece_max_x`, `g_blossom_piece_max_y`, and `g_blossom_piece_radius`.

- [ ] **Step 1: Add failing tests for shared-scale closed rings**

Add these helpers and tests to `tools/test_blossom_asset.py`:

```python
from PIL import Image


def mask_bbox(mask: Image.Image) -> tuple[int, int, int, int]:
    box = mask.getbbox()
    assert box is not None
    return box


def ring_width_samples(mask: Image.Image) -> list[int]:
    pixels = mask.load()
    widths: list[int] = []
    for y in range(mask.height):
        runs: list[int] = []
        current = 0
        for x in range(mask.width):
            if pixels[x, y] >= 8:
                current += 1
            elif current:
                runs.append(current)
                current = 0
        if current:
            runs.append(current)
        widths.extend(run for run in runs if 3 <= run <= 32)
    return widths


def test_petals_are_six_closed_equal_width_rings() -> None:
    petals = generator.rasterize_petals(SVG, size=128)
    assert len(petals) == 6
    medians = []
    for petal in petals:
        widths = sorted(ring_width_samples(petal))
        assert widths
        medians.append(widths[len(widths) // 2])
        box = mask_bbox(petal)
        assert box[0] >= 0 and box[1] >= 0
        assert box[2] <= 128 and box[3] <= 128
    assert max(medians) - min(medians) <= 1


def test_petals_keep_one_global_scale() -> None:
    small = generator.rasterize_petals(SVG, size=128)
    large = generator.rasterize_petals(SVG, size=192)
    for small_mask, large_mask in zip(small, large, strict=True):
        sw = mask_bbox(small_mask)[2] - mask_bbox(small_mask)[0]
        lw = mask_bbox(large_mask)[2] - mask_bbox(large_mask)[0]
        assert abs(lw / sw - 1.5) < 0.08


def test_full_blossom_mask_is_unchanged_by_petal_generation() -> None:
    before = generator.rasterize_svg(SVG, size=128).tobytes()
    generator.rasterize_petals(SVG, size=128)
    after = generator.rasterize_svg(SVG, size=128).tobytes()
    assert after == before
```

- [ ] **Step 2: Run the new tests and verify RED**

Run:

```powershell
python -m pytest tools/test_blossom_asset.py -k "petals_are_six or petals_keep_one or full_blossom_mask" -v --basetemp "$env:TEMP\saltyfish-petal-red"
```

Expected: the first two tests fail because `rasterize_petals` does not exist; the full-mask test may also error at the same missing call.

- [ ] **Step 3: Implement outward-only ring rasterization**

In `tools/generate_blossom_asset.py`, preserve the existing SVG contour parser and add:

```python
CANONICAL_RIBBON_WIDTH_SVG = 15.889


def _binary_dilate_outward(
    hole: Image.Image,
    radius_px: float,
) -> Image.Image:
    source = hole.convert("L")
    width, height = source.size
    values = list(source.getdata())
    distance = _chamfer_distance(
        [1 if value else 0 for value in values],
        width,
        height,
    )
    threshold = int(round(radius_px * 1000.0))
    output = Image.new("L", source.size, 0)
    output.putdata(
        255 if not values[index] and distance[index] <= threshold else 0
        for index in range(width * height)
    )
    return output


def rasterize_petals(
    svg_path: Path,
    size: int = 128,
    supersample: int = 4,
    ribbon_width_svg: float = CANONICAL_RIBBON_WIDTH_SVG,
) -> list[Image.Image]:
    view_box, contours = _outer_lobes(svg_path)
    high_size = size * supersample
    min_x, min_y, view_width, view_height = view_box
    scale = min(high_size / view_width, high_size / view_height)
    offset_x = (high_size - view_width * scale) / 2.0 - min_x * scale
    offset_y = (high_size - view_height * scale) / 2.0 - min_y * scale
    radius_px = ribbon_width_svg * scale
    petals: list[Image.Image] = []
    for contour in contours:
        hole = Image.new("L", (high_size, high_size), 0)
        draw = ImageDraw.Draw(hole)
        points = [
            (x * scale + offset_x, y * scale + offset_y)
            for x, y in contour
        ]
        draw.polygon(points, fill=255)
        expanded = _binary_dilate_outward(hole, radius_px)
        ring = ImageChops.subtract(expanded, hole)
        ring = ring.resize((size, size), Image.Resampling.LANCZOS)
        petals.append(
            ring.point(
                lambda value: min(15, max(0, (value * 15 + 127) // 255))
            )
        )
    if len(petals) != 6:
        raise ValueError(f"expected six Blossom holes, found {len(petals)}")
    return petals
```

Import `ImageChops` from Pillow. Replace the old `rasterize_piece_strokes(...)` call in `main()` with `rasterize_petals(...)`; `_outer_lobes(...)` remains the single contour parser.

- [ ] **Step 4: Emit clip metadata from the generated masks**

Add:

```python
def petal_bounds(
    masks: list[Image.Image],
) -> tuple[list[int], list[int], list[int], list[int], list[int]]:
    minimum_x: list[int] = []
    minimum_y: list[int] = []
    maximum_x: list[int] = []
    maximum_y: list[int] = []
    radius: list[int] = []
    for mask in masks:
        box = mask.getbbox()
        if box is None:
            raise ValueError("generated Blossom petal is empty")
        left, top, right, bottom = box
        right -= 1
        bottom -= 1
        minimum_x.append(left)
        minimum_y.append(top)
        maximum_x.append(right)
        maximum_y.append(bottom)
        radius.append(max(right - left, bottom - top) // 2 + 2)
    return minimum_x, minimum_y, maximum_x, maximum_y, radius
```

Extend generated declarations with:

```c
extern const uint8_t g_blossom_piece_min_x[BLOSSOM_PIECE_COUNT];
extern const uint8_t g_blossom_piece_min_y[BLOSSOM_PIECE_COUNT];
extern const uint8_t g_blossom_piece_max_x[BLOSSOM_PIECE_COUNT];
extern const uint8_t g_blossom_piece_max_y[BLOSSOM_PIECE_COUNT];
extern const uint8_t g_blossom_piece_radius[BLOSSOM_PIECE_COUNT];
```

Emit the five arrays after `g_blossom_piece_alpha_4bpp` in `Core/Src/blossom_asset.c`.

- [ ] **Step 5: Make the preview use production geometry**

Replace the preview-only dilation code in `tools/render_blossom_partition_preview.py` with:

```python
piece_masks = rasterize_petals(
    ROOT / "assets" / "openai-blossom.svg",
    size=128,
)
```

Remove the `skimage` import and `uniform_ribbon_pieces()` so the accepted preview and firmware assets cannot diverge.

- [ ] **Step 6: Run asset tests and regenerate assets**

Run:

```powershell
python -m pytest tools/test_blossom_asset.py -v --basetemp "$env:TEMP\saltyfish-petal-green"
python tools/generate_blossom_asset.py --svg assets/openai-blossom.svg --header Core/Inc/blossom_asset.h --source Core/Src/blossom_asset.c
python tools/render_blossom_partition_preview.py
```

Expected: all asset tests pass, generator exits `0`, and `outputs/blossom_partition_preview.png` contains six equal-width closed rings matching the accepted preview.

- [ ] **Step 7: Commit only the asset task**

```powershell
git add tools/test_blossom_asset.py tools/generate_blossom_asset.py tools/render_blossom_partition_preview.py Core/Inc/blossom_asset.h Core/Src/blossom_asset.c outputs/blossom_partition_preview.png
git commit -m "fix: generate canonical Blossom petal rings"
```

---

### Task 2: Crossfade Petal And Full-Blossom Layers

**Files:**
- Modify: `ports/rp2040-zero/firmware/include/blossom_motion.h`
- Modify: `ports/rp2040-zero/firmware/src/blossom_motion.c`
- Modify: `ports/rp2040-zero/firmware/src/display_scene.c`
- Modify: `ports/rp2040-zero/tests/test_pager_core.c`

**Interfaces:**
- Consumes: six generated petal masks and clip arrays from Task 1.
- Produces: `pager_blossom_model_t.petal_layer_opacity` and `pager_blossom_model_t.full_layer_opacity`.
- Produces: an `800 ms` READY-to-RUNNING transition whose first frame is purple.

- [ ] **Step 1: Replace old assembled tests with failing two-layer contracts**

In `ports/rp2040-zero/tests/test_pager_core.c`, replace assertions based on `assembled` with:

```c
static void test_ready_to_running_crossfades_without_pause(void) {
    pager_blossom_motion_t motion;
    pager_blossom_model_t start;
    pager_blossom_model_t middle;
    pager_blossom_model_t finish;

    pager_blossom_motion_init(&motion, PAGER_IDLE, 1000U);
    pager_blossom_motion_set_target(&motion, PAGER_RUNNING, 1000U);
    pager_blossom_motion_sample(&motion, 1000U, &start);
    pager_blossom_motion_sample(&motion, 1640U, &middle);
    pager_blossom_motion_sample(&motion, 1800U, &finish);

    assert(PAGER_READY_TO_RUNNING_MS == 800U);
    assert(start.pieces[0].color == PAGER_BLOSSOM_RUNNING_COLOR);
    assert(start.petal_layer_opacity == 255U);
    assert(start.full_layer_opacity == 0U);
    assert(middle.petal_layer_opacity > 0U);
    assert(middle.full_layer_opacity > 0U);
    assert(finish.petal_layer_opacity == 0U);
    assert(finish.full_layer_opacity == 255U);
    assert(finish.pieces[0].scale_q12 == start.pieces[0].scale_q12);
}

static void test_running_to_ready_reverses_crossfade(void) {
    pager_blossom_motion_t motion;
    pager_blossom_model_t middle;
    pager_blossom_model_t finish;

    pager_blossom_motion_init(&motion, PAGER_RUNNING, 2000U);
    pager_blossom_motion_set_target(&motion, PAGER_IDLE, 2000U);
    pager_blossom_motion_sample(&motion, 2700U, &middle);
    pager_blossom_motion_sample(
        &motion, 2000U + PAGER_RUNNING_TO_READY_MS, &finish);

    assert(middle.petal_layer_opacity > 0U);
    assert(middle.full_layer_opacity > 0U);
    assert(finish.petal_layer_opacity == 255U);
    assert(finish.full_layer_opacity == 0U);
    assert(finish.balance_opacity == 255U);
    assert(finish.ordered_orbit);
}

static void test_offline_to_ready_never_uses_full_layer(void) {
    pager_blossom_motion_t motion;
    pager_blossom_model_t middle;

    pager_blossom_motion_init(&motion, PAGER_OFFLINE, 3000U);
    pager_blossom_motion_set_target(&motion, PAGER_IDLE, 3000U);
    pager_blossom_motion_sample(&motion, 3600U, &middle);

    assert(middle.petal_layer_opacity == 255U);
    assert(middle.full_layer_opacity == 0U);
}
```

Call all three tests from `main()`.

- [ ] **Step 2: Run host tests and verify RED**

Run:

```powershell
powershell -ExecutionPolicy Bypass -File tools/run_host_tests.ps1
```

Expected: compilation fails because the two opacity fields do not exist, or assertions fail against the old `1450 ms` timeline.

- [ ] **Step 3: Extend the render model**

In `blossom_motion.h`, use:

```c
#define PAGER_READY_TO_RUNNING_MS 800U
#define PAGER_RUNNING_TO_READY_MS 1200U
#define PAGER_OFFLINE_TO_READY_MS 1200U

typedef struct {
    pager_blossom_piece_pose_t pieces[BLOSSOM_PIECE_COUNT];
    uint8_t balance_opacity;
    uint8_t petal_layer_opacity;
    uint8_t full_layer_opacity;
    int16_t angular_velocity_q8;
    bool ordered_orbit;
} pager_blossom_model_t;
```

Remove `assembled`; the renderer must no longer select one layer with a boolean.

- [ ] **Step 4: Implement the exact aggregation timeline**

Set layer defaults in model builders:

```c
static void assembled_model(
    pager_blossom_model_t *model,
    uint16_t color,
    int16_t angle_q8) {
    model->petal_layer_opacity = 0U;
    model->full_layer_opacity = 255U;
}

static void ready_model(pager_blossom_model_t *model, uint32_t elapsed_ms) {
    model->petal_layer_opacity = 255U;
    model->full_layer_opacity = 0U;
}

static void offline_model(pager_blossom_model_t *model, uint32_t elapsed_ms) {
    model->petal_layer_opacity = 255U;
    model->full_layer_opacity = 0U;
}
```

The snippets above are exact assignments added after each builder's current pose loop. Keep each builder's current `memset`, position, angle, scale, color, balance, orbit, and velocity assignments unchanged.

Interpolate both opacity fields in `lerp_model()`:

```c
result->petal_layer_opacity = lerp_u8(
    from->petal_layer_opacity, to->petal_layer_opacity, amount_q15);
result->full_layer_opacity = lerp_u8(
    from->full_layer_opacity, to->full_layer_opacity, amount_q15);
```

Implement READY to RUNNING with a `640 ms` gather and `160 ms` crossfade:

```c
static void sample_ready_to_running(
    const pager_blossom_motion_t *motion,
    uint32_t elapsed,
    pager_blossom_model_t *model) {
    pager_blossom_model_t gathered;
    pager_blossom_model_t full;
    uint8_t piece;

    assembled_model(&gathered, PAGER_BLOSSOM_RUNNING_COLOR, 0);
    gathered.petal_layer_opacity = 255U;
    gathered.full_layer_opacity = 0U;
    for (piece = 0U; piece < BLOSSOM_PIECE_COUNT; ++piece) {
        gathered.pieces[piece].color = PAGER_BLOSSOM_RUNNING_COLOR;
    }
    if (elapsed < 640U) {
        pager_blossom_model_t purple_start = motion->start;
        for (piece = 0U; piece < BLOSSOM_PIECE_COUNT; ++piece) {
            purple_start.pieces[piece].color = PAGER_BLOSSOM_RUNNING_COLOR;
        }
        purple_start.balance_opacity = 0U;
        lerp_model(
            &purple_start, &gathered, smooth_q15(elapsed, 640U), model);
        model->petal_layer_opacity = 255U;
        model->full_layer_opacity = 0U;
        return;
    }
    if (elapsed <= PAGER_READY_TO_RUNNING_MS) {
        full = gathered;
        full.petal_layer_opacity = 0U;
        full.full_layer_opacity = 255U;
        lerp_model(
            &gathered,
            &full,
            smooth_q15(elapsed - 640U, 160U),
            model);
        return;
    }
    running_model(model, elapsed - PAGER_READY_TO_RUNNING_MS);
}
```

Implement RUNNING to READY as the reverse: ease rotation for `240 ms`, crossfade full purple to gathered green petals from `240-400 ms`, then separate those petals into the READY orbit from `400-1200 ms`. Keep scale `FULL_SCALE_Q12` through all phases.

- [ ] **Step 5: Render both layers with generated clip metadata**

In `display_scene.c`, replace hard-coded bounds with generated arrays:

```c
const int32_t source_center_x_q8 =
    ((int32_t)g_blossom_piece_min_x[piece] +
     g_blossom_piece_max_x[piece]) * 128;
const int32_t source_center_y_q8 =
    ((int32_t)g_blossom_piece_min_y[piece] +
     g_blossom_piece_max_y[piece]) * 128;
const uint8_t clip_radius = g_blossom_piece_radius[piece];
```

Multiply per-piece alpha by the petal layer opacity:

```c
const uint16_t opacity =
    ((uint16_t)pose->opacity * model->petal_layer_opacity + 127U) / 255U;
```

Render the full canonical mask whenever `full_layer_opacity != 0U`, using piece `0` as the common full-layer transform:

```c
if (model->full_layer_opacity != 0U) {
    pager_blossom_piece_pose_t full_pose = model->pieces[0];
    full_pose.opacity = (uint8_t)(
        ((uint16_t)full_pose.opacity * model->full_layer_opacity + 127U)
        / 255U);
    render_blossom_layer(
        frame,
        &full_pose,
        sample_full_blossom_alpha,
        0U,
        0U,
        BLOSSOM_ASSET_WIDTH - 1U,
        BLOSSOM_ASSET_HEIGHT - 1U);
}
```

Render the six petal masks first and the canonical full mask second so crossfade overlap converges to the exact RUNNING logo.

- [ ] **Step 6: Run host tests and firmware build**

Run:

```powershell
powershell -ExecutionPolicy Bypass -File tools/run_host_tests.ps1
powershell -ExecutionPolicy Bypass -File tools/build_rp2040.ps1
```

Expected: host tests report success; firmware build exits `0`; SRAM and flash size checks stay within the existing limits.

- [ ] **Step 7: Commit only motion/render changes**

```powershell
git add ports/rp2040-zero/firmware/include/blossom_motion.h ports/rp2040-zero/firmware/src/blossom_motion.c ports/rp2040-zero/firmware/src/display_scene.c ports/rp2040-zero/tests/test_pager_core.c
git commit -m "feat: crossfade Blossom petals into running"
```

---

### Task 3: Detect Prompt Submission From Codex SQLite

**Files:**
- Create: `tools/codex_log_watcher.py`
- Create: `tools/test_codex_log_watcher.py`

**Interfaces:**
- Produces: `CodexLogWatcher(path: Path)`.
- Produces: `poll_events() -> list[tuple[str, str]]`, where events are `(thread_id, "UserPromptSubmit")`.
- The first poll initializes `last_id` to `MAX(logs.id)` and emits no stale events.

- [ ] **Step 1: Write a temporary-database integration test**

Create `tools/test_codex_log_watcher.py`:

```python
from pathlib import Path
import sqlite3

from codex_log_watcher import CodexLogWatcher


CREATE_LOGS = """
CREATE TABLE logs (
    id INTEGER PRIMARY KEY,
    ts TEXT,
    ts_nanos INTEGER,
    level TEXT,
    target TEXT,
    feedback_log_body TEXT,
    module_path TEXT,
    file TEXT,
    line INTEGER,
    thread_id TEXT,
    process_uuid TEXT,
    estimated_bytes INTEGER
)
"""


def insert_log(
    path: Path,
    *,
    target: str,
    body: str,
    thread_id: str | None,
) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            INSERT INTO logs(target, feedback_log_body, thread_id)
            VALUES (?, ?, ?)
            """,
            (target, body, thread_id),
        )


def test_ignores_stale_rows_and_emits_new_user_input(tmp_path: Path) -> None:
    path = tmp_path / "logs_2.sqlite"
    with sqlite3.connect(path) as connection:
        connection.execute(CREATE_LOGS)
    insert_log(
        path,
        target="codex_core::session::handlers",
        body="Submission op: UserInput stale",
        thread_id="old",
    )
    watcher = CodexLogWatcher(path)
    assert watcher.poll_events() == []

    insert_log(path, target="other", body="noise", thread_id="noise")
    insert_log(
        path,
        target="codex_core::session::handlers",
        body="session_loop Submission sub=Submission op: UserInput text",
        thread_id="thread-7",
    )
    assert watcher.poll_events() == [("thread-7", "UserPromptSubmit")]
    assert watcher.poll_events() == []


def test_missing_thread_is_ignored_but_cursor_advances(tmp_path: Path) -> None:
    path = tmp_path / "logs_2.sqlite"
    with sqlite3.connect(path) as connection:
        connection.execute(CREATE_LOGS)
    watcher = CodexLogWatcher(path)
    assert watcher.poll_events() == []
    insert_log(
        path,
        target="codex_core::session::handlers",
        body="Submission op: UserInput",
        thread_id=None,
    )
    assert watcher.poll_events() == []
    assert watcher.poll_events() == []


def test_missing_database_recovers_after_creation(tmp_path: Path) -> None:
    path = tmp_path / "logs_2.sqlite"
    watcher = CodexLogWatcher(path)
    assert watcher.poll_events() == []
    with sqlite3.connect(path) as connection:
        connection.execute(CREATE_LOGS)
    assert watcher.poll_events() == []
    insert_log(
        path,
        target="codex_core::session::handlers",
        body="Submission op: UserInput",
        thread_id="thread-new",
    )
    assert watcher.poll_events() == [("thread-new", "UserPromptSubmit")]
```

- [ ] **Step 2: Run watcher tests and verify RED**

Run:

```powershell
python -m pytest tools/test_codex_log_watcher.py -v --basetemp "$env:TEMP\saltyfish-log-red"
```

Expected: collection fails with `ModuleNotFoundError: No module named 'codex_log_watcher'`.

- [ ] **Step 3: Implement the read-only incremental watcher**

Create `tools/codex_log_watcher.py`:

```python
from __future__ import annotations

from pathlib import Path
import sqlite3


TARGET = "codex_core::session::handlers"


class CodexLogWatcher:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.last_id: int | None = None
        self._identity: tuple[int, int] | None = None

    def _file_identity(self) -> tuple[int, int]:
        stat = self.path.stat()
        return stat.st_dev, stat.st_ino

    def _connect(self) -> sqlite3.Connection:
        uri = self.path.resolve().as_uri() + "?mode=ro"
        connection = sqlite3.connect(uri, uri=True, timeout=0.02)
        connection.execute("PRAGMA query_only = ON")
        connection.execute("PRAGMA busy_timeout = 20")
        return connection

    def poll_events(self) -> list[tuple[str, str]]:
        try:
            identity = self._file_identity()
            if identity != self._identity:
                self._identity = identity
                self.last_id = None
            with self._connect() as connection:
                if self.last_id is None:
                    row = connection.execute(
                        "SELECT COALESCE(MAX(id), 0) FROM logs"
                    ).fetchone()
                    self.last_id = int(row[0])
                    return []
                rows = connection.execute(
                    """
                    SELECT id, target, feedback_log_body, thread_id
                    FROM logs
                    WHERE id > ?
                    ORDER BY id
                    """,
                    (self.last_id,),
                ).fetchall()
        except (OSError, sqlite3.Error):
            self._identity = None
            self.last_id = None
            return []

        events: list[tuple[str, str]] = []
        for row_id, target, body, thread_id in rows:
            self.last_id = max(self.last_id, int(row_id))
            if (
                target == TARGET
                and isinstance(body, str)
                and "Submission" in body
                and "op: UserInput" in body
                and isinstance(thread_id, str)
                and thread_id
            ):
                events.append((thread_id, "UserPromptSubmit"))
        return events
```

- [ ] **Step 4: Verify watcher behavior**

Run:

```powershell
python -m pytest tools/test_codex_log_watcher.py -v --basetemp "$env:TEMP\saltyfish-log-green"
```

Expected: all watcher tests pass.

- [ ] **Step 5: Add explicit database-replacement coverage**

Add:

```python
def test_database_replacement_reinitializes_without_replaying(tmp_path: Path) -> None:
    path = tmp_path / "logs_2.sqlite"
    with sqlite3.connect(path) as connection:
        connection.execute(CREATE_LOGS)
    watcher = CodexLogWatcher(path)
    assert watcher.poll_events() == []
    path.unlink()
    with sqlite3.connect(path) as connection:
        connection.execute(CREATE_LOGS)
    insert_log(
        path,
        target="codex_core::session::handlers",
        body="Submission op: UserInput replacement-stale",
        thread_id="stale-after-replace",
    )
    assert watcher.poll_events() == []
```

Run the test and keep it green.

- [ ] **Step 6: Commit the focused watcher**

```powershell
git add tools/codex_log_watcher.py tools/test_codex_log_watcher.py
git commit -m "feat: watch Codex prompt submissions in sqlite"
```

---

### Task 4: Integrate Immediate Starts Without Duplicate Sends

**Files:**
- Modify: `tools/pager_runtime.py`
- Modify: `tools/test_pager_runtime.py`
- Modify: `tools/pager_daemon.py`
- Modify: `tools/test_session_watcher.py`

**Interfaces:**
- Consumes: `CodexLogWatcher.poll_events()` from Task 3.
- Consumes: existing `SessionLogWatcher.poll_events()` for completion/fallback.
- Produces: one immediate snapshot send per task state change.

- [ ] **Step 1: Add failing daemon integration tests**

Add to `tools/test_session_watcher.py`:

```python
from pager_daemon import process_session_events


class QueueWatcher:
    def __init__(self, events):
        self.events = list(events)

    def poll_events(self):
        events = self.events
        self.events = []
        return events


def test_sqlite_prompt_event_immediately_sends_running(tmp_path: Path) -> None:
    store = RuntimeStore(tmp_path / "runtime.sqlite")
    sent = []
    watcher = QueueWatcher([("thread-fast", "UserPromptSubmit")])
    snapshot = process_session_events(store, watcher, sent.append, now=10.0)
    assert snapshot is not None
    assert snapshot.state == "RUNNING"
    assert snapshot.running == 1
    assert [item.state for item in sent] == ["RUNNING"]


def test_duplicate_prompt_does_not_send_same_snapshot_twice(tmp_path: Path) -> None:
    store = RuntimeStore(tmp_path / "runtime.sqlite")
    sent = []
    first = QueueWatcher([("thread-fast", "UserPromptSubmit")])
    fallback = QueueWatcher([("thread-fast", "UserPromptSubmit")])
    assert process_session_events(store, first, sent.append, now=10.0)
    assert process_session_events(store, fallback, sent.append, now=10.1) is None
    assert len(sent) == 1
```

- [ ] **Step 2: Run integration tests and verify RED**

Run:

```powershell
python -m pytest tools/test_session_watcher.py -k "sqlite_prompt or duplicate_prompt" -v --basetemp "$env:TEMP\saltyfish-daemon-red"
```

Expected: the immediate-send test passes with existing behavior, while duplicate suppression fails because `process_session_events` sends twice.

- [ ] **Step 3: Make RuntimeStore report whether a record changed**

Change `RuntimeStore.record(...)` to return `bool`:

```python
def record(self, session_id: str, event_name: str, now: float) -> bool:
    state = EVENT_STATES.get(event_name)
    if not state or not session_id:
        return False
```

Inside the existing transaction, immediately after assigning `previous`, add:

```python
if previous == state and state == "RUNNING":
    return False
changed = previous != state
```

After the existing UPSERT, add:

```python
return changed
```

Preserve existing WAIT/DONE pending-event semantics. A duplicate `UserPromptSubmit` for an already RUNNING task updates neither state nor `updated_at`, preventing the delayed JSONL fallback from extending the task TTL or sending a second serial frame.

Update `process_session_events()`:

```python
changed = False
for session_id, event_name in events:
    changed = store.record(session_id, event_name, now=current_time) or changed
if not changed:
    return None
return run_cycle(store, sender, now=current_time)
```

Add to `tools/test_pager_runtime.py`:

```python
def test_duplicate_running_event_reports_no_change(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    assert store.record("thread-a", "UserPromptSubmit", now=10.0) is True
    assert store.record("thread-a", "UserPromptSubmit", now=10.1) is False
    assert store.snapshot(now=10.2).running == 1
```

- [ ] **Step 4: Add the SQLite watcher to the daemon loop**

Import and construct:

```python
from codex_log_watcher import CodexLogWatcher

prompt_watcher = CodexLogWatcher(Path.home() / ".codex" / "logs_2.sqlite")
session_watcher = SessionLogWatcher(Path.home() / ".codex" / "sessions")
```

Poll `prompt_watcher` first on every `100 ms` loop:

```python
prompt_snapshot = process_session_events(
    store, prompt_watcher, send_snapshot
)
if prompt_snapshot is not None:
    next_heartbeat = current_monotonic + interval

event_snapshot = process_session_events(
    store, session_watcher, send_snapshot
)
if event_snapshot is not None:
    next_heartbeat = current_monotonic + interval
```

Do not let a missing/locked SQLite database stop JSONL polling or heartbeat.

- [ ] **Step 5: Run all daemon/runtime tests**

Run:

```powershell
python -m pytest tools/test_codex_log_watcher.py tools/test_session_watcher.py tools/test_pager_runtime.py -v --basetemp "$env:TEMP\saltyfish-daemon-green"
```

Expected: all selected tests pass and duplicate prompt fallback sends only once.

- [ ] **Step 6: Commit daemon integration**

```powershell
git add tools/pager_daemon.py tools/pager_runtime.py tools/test_session_watcher.py tools/test_pager_runtime.py
git commit -m "feat: send running state immediately from Codex logs"
```

---

### Task 5: Full Verification, Daemon Restart, And RP2040 Flash

**Files:**
- Verify all changed files.
- Flash: `build-rp2040/codex_usb_pager.uf2` to the detected `RPI-RP2` drive.

**Interfaces:**
- Consumes: generated asset, firmware build, SQLite watcher, daemon integration.
- Produces: running RP2040 firmware and a restarted host daemon using the new watcher.

- [ ] **Step 1: Run the full Python test suite**

Run with a unique elevated base temp because the machine's default pytest temp ACL is known to be broken:

```powershell
$base = Join-Path $env:TEMP ("saltyfish-full-" + [guid]::NewGuid().ToString("N"))
python -m pytest -v --basetemp $base
```

Expected: all tests pass; no collection errors or warnings from project code.

- [ ] **Step 2: Run host C tests and rebuild firmware from clean staging**

Run:

```powershell
powershell -ExecutionPolicy Bypass -File tools/run_host_tests.ps1
powershell -ExecutionPolicy Bypass -File tools/build_rp2040.ps1
```

Expected: host test executable exits `0`; Pico build exits `0`; generated UF2 exists; reported SRAM use remains below the linker limit.

- [ ] **Step 3: Restart the pager daemon**

Find only the daemon process whose command line contains `tools\pager_daemon.py`, stop it, and start the current workspace copy hidden:

```powershell
Get-CimInstance Win32_Process |
    Where-Object { $_.CommandLine -like '*tools\pager_daemon.py*' } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
Start-Process python `
    -ArgumentList 'tools\pager_daemon.py' `
    -WorkingDirectory 'C:\Users\28026\Documents\saltyfish\codex_usb_pager' `
    -WindowStyle Hidden
```

Expected: exactly one daemon process remains and it references the `saltyfish` workspace.

- [ ] **Step 4: Enter BOOTSEL and flash**

Trigger RP2040 USB boot by opening COM7 at 1200 baud, wait for the `RPI-RP2` volume, then copy the UF2:

```powershell
$port = New-Object System.IO.Ports.SerialPort 'COM7',1200,'None',8,'one'
try { $port.Open() } catch { }
finally { if ($port.IsOpen) { $port.Close() } }
Start-Sleep -Milliseconds 800
$drive = Get-Volume -FileSystemLabel 'RPI-RP2' |
    Select-Object -First 1 -ExpandProperty DriveLetter
if (-not $drive) { throw 'RPI-RP2 drive not found' }
Copy-Item -LiteralPath 'build-rp2040\codex_usb_pager.uf2' `
    -Destination "${drive}:\codex_usb_pager.uf2" -Force
```

Expected: `RPI-RP2` disconnects after the copy and COM7 returns as the pager CDC port.

- [ ] **Step 5: Verify firmware identity and host state latency**

Run:

```powershell
Get-PnpDevice -PresentOnly |
    Where-Object {
        $_.FriendlyName -match 'COM7|RP2040|Serial|CDC'
    } |
    Select-Object Status, FriendlyName, InstanceId
Get-FileHash -Algorithm SHA256 build-rp2040\codex_usb_pager.uf2
```

Then send one new Codex prompt. Compare its newest matching `logs.id` timestamp with the `tasks.updated_at` value in the pager runtime database. The measured difference must be below `0.100 s`, and the display must begin purple aggregation on the first visible frame.

- [ ] **Step 6: Perform visual acceptance checks**

Verify on the physical display:

1. READY shows six green equal-width closed petals and centered weekly digits.
2. READY orbit is slow and continuous.
3. Sending a prompt changes to purple immediately.
4. Six petals gather without pause, gap, or size jump.
5. The canonical full Blossom rotates continuously in RUNNING.
6. Completion reverses into six READY petals smoothly.
7. OFFLINE petals drift irregularly; reopening Codex settles them into READY without assembling.
8. No blue/black band, square ghost, row-wave refresh, or clipped petal appears.

- [ ] **Step 7: Record environment issues and recommendation**

Report each local issue observed during the run and whether it should be repaired:

- Broken pytest temp ACL: recommend repair only if it still reproduces outside the unique `--basetemp`; otherwise retain the workaround.
- Stale PDB/compiler service: recommend repair if build scripts still need to terminate it.
- COM7 1200-baud open exception during USB identity change: expected behavior; no repair recommended.
- Any duplicate daemon process or stale non-English workspace command line: repair immediately.

- [ ] **Step 8: Commit final verification documentation only if changed**

If verification updates `ports/rp2040-zero/README.md`, stage only that file:

```powershell
git add ports/rp2040-zero/README.md
git commit -m "docs: record Blossom pager verification"
```

Do not create an empty commit when no documentation changed.
