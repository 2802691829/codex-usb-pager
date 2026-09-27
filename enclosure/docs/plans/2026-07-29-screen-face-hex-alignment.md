# Screen Face Pocket and Hex Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the front shell so its locating pocket grips the measured
`26 × 29 mm` raised screen face and its regular hexagonal window is `23.5 mm`
point-to-point, top-referenced to hide the black border and lower non-display
area.

**Architecture:** Keep PCB-hole posts referenced to the PCB, but introduce
separate screen-face and window datums in `EnclosureParameters`. Build the
screen pocket from the face datum, translate the independent regular-hex cut
to its calculated Y centre, and expose actual FreeCAD bounds through the audit
so tests verify the exported solid rather than source constants alone.

**Tech Stack:** Python 3, pytest, FreeCAD 1.1 Python API, OpenCascade/Part,
FreeCAD GUI renderer.

## Global Constraints

- Blossom target width remains `56.0 mm`; its SVG is uniformly scaled and
  never stretched along one axis.
- The regular hex remains undistorted, with `23.50 mm` between top and bottom
  vertices and `20.35 mm` between left and right flats.
- Raised screen face is `26.0 × 29.0 mm`; pocket clearance is `0.15 mm` per
  side, producing `26.30 × 29.30 mm`.
- Raised-face top is `5.00 mm` below the PCB top; face centre Y is `-1.53 mm`.
- Hex top vertex is `0.50 mm` below the face top; hex centre Y is `0.72 mm`;
  its bottom vertex leaves `5.00 mm` of covered face.
- Raised-face front and the front-shell bearing plane are both `Z = 2.30 mm`.
- USB, buzzer, hidden latches, PCB locating posts and `1.5 mm` Blossom relief
  remain unchanged and unobstructed.

---

### Task 1: Screen-face and regular-hex parameter contract

**Files:**
- Modify: `codex_usb_pager/enclosure/tests/test_enclosure_params.py`
- Modify: `codex_usb_pager/enclosure/cad/enclosure_params.py`

**Interfaces:**
- Consumes: existing PCB centre and dimensions.
- Produces: `front_hex_point_to_point_mm`,
  `front_hex_across_flats_mm`, `front_hex_center_y_mm`,
  `screen_face_center_y_mm`, `screen_face_top_y_mm`,
  `screen_pocket_mm`.

- [ ] **Step 1: Write failing parameter tests**

```python
def test_hex_is_regular_and_top_referenced_to_screen_face():
    assert DEFAULTS.front_hex_point_to_point_mm == 23.5
    assert round(DEFAULTS.front_hex_across_flats_mm, 2) == 20.35
    assert DEFAULTS.screen_face_top_y_mm == 12.97
    assert DEFAULTS.front_hex_center_y_mm == 0.72
    assert DEFAULTS.front_hex_top_margin_mm == 0.50
    assert DEFAULTS.front_hex_bottom_margin_mm == 5.00


def test_screen_pocket_grips_measured_raised_face():
    assert DEFAULTS.screen_face_mm == (26.0, 29.0)
    assert DEFAULTS.screen_face_clearance_mm == 0.15
    assert DEFAULTS.screen_pocket_mm == (26.30, 29.30)
    assert DEFAULTS.screen_face_center_y_mm == -1.53
    assert DEFAULTS.screen_face_top_offset_from_pcb_mm == 5.0
```

- [ ] **Step 2: Verify the new tests fail for the old values**

Run:

```powershell
python -m pytest enclosure/tests/test_enclosure_params.py -q
```

Expected: failures showing the old `31.3 mm` point-to-point hex,
`25.30 × 29.22 mm` face and `0.20 mm` side clearance.

- [ ] **Step 3: Implement the datum properties**

Use these definitions in `EnclosureParameters`:

```python
front_hex_point_to_point_mm: float = 23.5
screen_face_mm: tuple[float, float] = (26.0, 29.0)
screen_face_clearance_mm: float = 0.15
screen_face_top_offset_from_pcb_mm: float = 5.0
screen_black_border_mm: float = 0.5

@property
def front_hex_across_flats_mm(self) -> float:
    return self.front_hex_point_to_point_mm * sqrt(3.0) / 2.0

@property
def screen_face_top_y_mm(self) -> float:
    return round(
        self.screen_pcb_center_y_mm
        + self.screen_pcb_mm[1] / 2.0
        - self.screen_face_top_offset_from_pcb_mm,
        2,
    )

@property
def screen_face_center_y_mm(self) -> float:
    return round(
        self.screen_face_top_y_mm - self.screen_face_mm[1] / 2.0,
        2,
    )

@property
def front_hex_center_y_mm(self) -> float:
    return round(
        self.screen_face_top_y_mm
        - self.screen_black_border_mm
        - self.front_hex_point_to_point_mm / 2.0,
        2,
    )
```

Keep `front_hex_across_corners_mm` as a compatibility property returning
`front_hex_point_to_point_mm`.

- [ ] **Step 4: Verify parameter tests and the complete pure-Python suite**

Run:

```powershell
python -m pytest enclosure/tests/test_enclosure_params.py -q
python -m pytest enclosure/tests -q
```

Expected: all tests pass except later geometry-contract tests that have not
yet been introduced.

- [ ] **Step 5: Commit Task 1**

```powershell
git add codex_usb_pager/enclosure/cad/enclosure_params.py codex_usb_pager/enclosure/tests/test_enclosure_params.py
git commit -m "feat: define measured screen face and hex datums"
```

### Task 2: Build the raised-face pocket and translated hex cut

**Files:**
- Modify: `codex_usb_pager/enclosure/tests/test_screen_mount_contract.py`
- Modify: `codex_usb_pager/enclosure/cad/build_blossom_enclosure.py`

**Interfaces:**
- Consumes: Task 1 datum properties.
- Produces: translated `FrontHexCut`, `ScreenPocketEnvelope`,
  face-centred locating frame and retainers; PCB posts remain PCB-centred.

- [ ] **Step 1: Write failing build-contract tests**

```python
def test_regular_hexagon_accepts_an_xy_centre():
    assert "def regular_hexagon(" in BUILD
    assert "center_x: float = 0.0" in BUILD
    assert "center_y: float = 0.0" in BUILD
    assert "DEFAULTS.front_hex_center_y_mm" in BUILD


def test_screen_frame_uses_face_centre_but_posts_keep_pcb_centres():
    mount = BUILD[BUILD.index("def build_screen_mount("):]
    assert "DEFAULTS.screen_face_center_y_mm" in mount
    assert "DEFAULTS.screen_post_centres_mm" in mount
    assert '"ScreenPocketEnvelope"' in BUILD
```

- [ ] **Step 2: Verify contract tests fail**

Run:

```powershell
python -m pytest enclosure/tests/test_screen_mount_contract.py -q
```

Expected: failure because the hex is origin-centred and the frame reuses the
PCB centre.

- [ ] **Step 3: Translate the regular hex without distorting it**

Change the helper signature and point creation:

```python
def regular_hexagon(
    across_flats: float,
    z: float,
    height: float,
    center_x: float = 0.0,
    center_y: float = 0.0,
):
    apothem = across_flats / 2.0
    radius = apothem / (sqrt(3.0) / 2.0)
    points = [
        App.Vector(
            center_x + radius * cos(pi / 6.0 + index * pi / 3.0),
            center_y + radius * sin(pi / 6.0 + index * pi / 3.0),
            z,
        )
        for index in range(6)
    ]
```

Create `front_hex_cut` with
`center_y=DEFAULTS.front_hex_center_y_mm`.

- [ ] **Step 4: Separate screen-face and PCB datums**

Inside `build_screen_mount()`:

```python
pocket_width, pocket_height = DEFAULTS.screen_pocket_mm
face_centre_y = DEFAULTS.screen_face_center_y_mm
```

Use `face_centre_y` for the rectangular frame, face envelope and retainers.
Continue using `DEFAULTS.screen_post_centres_mm` for all four posts. Create a
clearance solid named `ScreenPocketEnvelope` with dimensions
`26.30 × 29.30 mm`, based at `Z = 2.30 mm`, for audit and review only.

- [ ] **Step 5: Verify build-contract and full tests**

Run:

```powershell
python -m pytest enclosure/tests/test_screen_mount_contract.py -q
python -m pytest enclosure/tests -q
```

Expected: all pure-Python tests pass.

- [ ] **Step 6: Commit Task 2**

```powershell
git add codex_usb_pager/enclosure/cad/build_blossom_enclosure.py codex_usb_pager/enclosure/tests/test_screen_mount_contract.py
git commit -m "feat: align screen pocket and front hex"
```

### Task 3: Audit actual exported face, pocket and window geometry

**Files:**
- Modify: `codex_usb_pager/enclosure/tests/test_audit_contract.py`
- Modify: `codex_usb_pager/enclosure/tests/freecad_latch_geometry_contract.py`
- Modify: `codex_usb_pager/enclosure/cad/audit_blossom_enclosure.py`

**Interfaces:**
- Consumes: `FrontHexCut`, `ScreenFaceEnvelope`, `ScreenPocketEnvelope`.
- Produces: serialisable actual-bound metrics and FreeCAD assertions.

- [ ] **Step 1: Add failing audit-contract fields**

Require these report fields:

```python
required = {
    "front_hex_point_to_point_mm",
    "front_hex_across_flats_mm",
    "front_hex_center_y_mm",
    "screen_face_dimensions_mm",
    "screen_face_center_y_mm",
    "screen_pocket_dimensions_mm",
    "screen_pocket_center_y_mm",
    "screen_hex_top_margin_mm",
    "screen_hex_bottom_margin_mm",
    "screen_face_front_z_mm",
}
assert required <= set(AUDIT_SOURCE)
```

- [ ] **Step 2: Verify the audit tests fail**

Run:

```powershell
python -m pytest enclosure/tests/test_audit_contract.py -q
```

Expected: missing actual-bound fields.

- [ ] **Step 3: Report actual FreeCAD bounds**

Read `ScreenPocketEnvelope` and derive:

```python
hex_box = front_hex.BoundBox
face_box = screen_face.BoundBox
pocket_box = screen_pocket.BoundBox
```

Return rounded values for X/Y lengths and centres, plus:

```python
"screen_hex_top_margin_mm": round(face_box.YMax - hex_box.YMax, 3),
"screen_hex_bottom_margin_mm": round(hex_box.YMin - face_box.YMin, 3),
"screen_face_front_z_mm": round(face_box.ZMin, 3),
```

- [ ] **Step 4: Assert actual exported geometry**

Extend `freecad_latch_geometry_contract.py`:

```python
assert_close(report["front_hex_point_to_point_mm"], 23.50)
assert_close(report["front_hex_across_flats_mm"], 20.35)
assert_close(report["front_hex_center_y_mm"], 0.72)
assert report["screen_face_dimensions_mm"] == [26.0, 29.0]
assert report["screen_pocket_dimensions_mm"] == [26.3, 29.3]
assert_close(report["screen_face_center_y_mm"], -1.53)
assert_close(report["screen_pocket_center_y_mm"], -1.53)
assert_close(report["screen_hex_top_margin_mm"], 0.50)
assert_close(report["screen_hex_bottom_margin_mm"], 5.00)
assert_close(report["screen_face_front_z_mm"], 2.30)
```

Retain every existing USB, buzzer, latch, interference and single-solid
assertion.

- [ ] **Step 5: Verify pure-Python tests**

Run:

```powershell
python -m pytest enclosure/tests -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit Task 3**

```powershell
git add codex_usb_pager/enclosure/cad/audit_blossom_enclosure.py codex_usb_pager/enclosure/tests/test_audit_contract.py codex_usb_pager/enclosure/tests/freecad_latch_geometry_contract.py
git commit -m "test: audit screen pocket and hex alignment"
```

### Task 4: Cold-build, render and final visual acceptance

**Files:**
- Modify if required by the new review object:
  `codex_usb_pager/enclosure/cad/render_blossom_review.py`
- Modify if required:
  `codex_usb_pager/enclosure/tests/test_render_contract.py`
- Generate ignored artifacts:
  `codex_usb_pager/enclosure/outputs/*`

**Interfaces:**
- Consumes: all Task 1–3 geometry and audit objects.
- Produces: FCStd, STEP, front/rear STL and seven stable review PNGs.

- [ ] **Step 1: Cold-build FreeCAD outputs**

Run from `codex_usb_pager`:

```powershell
"code=open(r'enclosure/cad/build_blossom_enclosure.py').read(); exec(compile(code, r'enclosure/cad/build_blossom_enclosure.py', 'exec'), {'__name__':'__main__','__file__':r'enclosure/cad/build_blossom_enclosure.py'})" | & 'C:\Program Files\FreeCAD 1.1\bin\FreeCADCmd.exe' -c
```

Expected: `BUILD PASS`.

- [ ] **Step 2: Run actual FreeCAD audit and geometry contract**

Run:

```powershell
"import sys; sys.argv=[r'enclosure/cad/audit_blossom_enclosure.py', r'enclosure/outputs/blossom-enclosure.FCStd']; code=open(r'enclosure/cad/audit_blossom_enclosure.py').read(); exec(compile(code, r'enclosure/cad/audit_blossom_enclosure.py', 'exec'), {'__name__':'__main__','__file__':r'enclosure/cad/audit_blossom_enclosure.py'})" | & 'C:\Program Files\FreeCAD 1.1\bin\FreeCADCmd.exe' -c

"import sys; sys.argv=[r'enclosure/tests/freecad_latch_geometry_contract.py', r'enclosure/outputs/blossom-enclosure.FCStd']; code=open(r'enclosure/tests/freecad_latch_geometry_contract.py').read(); exec(compile(code, r'enclosure/tests/freecad_latch_geometry_contract.py', 'exec'), {'__name__':'__main__','__file__':r'enclosure/tests/freecad_latch_geometry_contract.py'})" | & 'C:\Program Files\FreeCAD 1.1\bin\FreeCADCmd.exe' -c
```

Expected: audit fields match the spec and
`FREECAD LATCH CONTRACT PASS`.

- [ ] **Step 3: Render review images**

Run:

```powershell
$macro=(Resolve-Path 'enclosure\cad\render_blossom_review.FCMacro').Path
$process=Start-Process -FilePath 'C:\Program Files\FreeCAD 1.1\bin\FreeCAD.exe' -ArgumentList @($macro) -WindowStyle Hidden -Wait -PassThru
$process.ExitCode
```

Expected: exit code `0`, seven `1600 × 1200` PNGs and no lingering FreeCAD
process.

- [ ] **Step 4: Inspect front exterior, front inside and assembly views**

Confirm:

- outer Blossom remains `56.0 mm` and visually undistorted;
- hex is regular, centred X=0 and Y=0.72, with no black-border exposure;
- pocket follows the `26 × 29 mm` raised face, not the PCB outline;
- four PCB posts, both retainers, USB, buzzer and hidden latches remain clear.

- [ ] **Step 5: Run final suite and clean-state checks**

```powershell
python -m pytest enclosure/tests -q
git diff --check
git status --short --branch
```

Expected: all tests pass, no whitespace errors, only intentional tracked
changes before the final commit.

- [ ] **Step 6: Commit any renderer updates**

```powershell
git add codex_usb_pager/enclosure/cad/render_blossom_review.py codex_usb_pager/enclosure/tests/test_render_contract.py
git commit -m "test: review corrected screen and hex alignment"
```

