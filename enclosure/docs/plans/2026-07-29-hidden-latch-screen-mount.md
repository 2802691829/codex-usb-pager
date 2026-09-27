# Hidden Latch And Screen Mount Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the four rectangular closure placeholders with a functional hidden, easy-open resin latch system and add a screen-face pocket, four locating posts, and two light retention lips to the front shell.

**Architecture:** Keep `enclosure/cad/build_blossom_enclosure.py` as the FreeCAD source of truth, but express every approved dimension in `enclosure_params.py`. Build screen retention and closure as named intermediate shapes, fuse/cut them into the final shells, and extend the FreeCAD audit to verify actual Boolean relationships rather than object names alone. Generate internal review views before treating the STL files as print-ready.

**Tech Stack:** Python 3.11, pytest, FreeCAD 1.1 Part/Import/Mesh APIs, OpenCascade Boolean solids, FreeCADGui image export.

## Global Constraints

- Use the original `openai-blossom.svg` with uniform scaling; do not redraw the outer silhouette.
- Preserve the 56.0 mm Blossom width, 20.6 mm total thickness, 1.5 mm front/rear relief depth, and 0.6 mm target relief transition radius.
- Preserve the rear-facing rounded USB opening at 13.4 × 8.8 mm with R2.0 corners and its internal 5 mm force-plate gap.
- Keep the buzzer fully internal with no sound opening.
- Minimum solid feature thickness is 0.8 mm.
- Screen PCB is 27.78 × 39.22 mm; screen face is 25.30 × 29.22 mm; active area is 23.40 × 23.40 mm.
- Screen face-to-PCB-front distance is 2.0 mm.
- Four screen holes are Ø2.0 mm with centres 2.50 mm from their PCB edges.
- The active-area centre is 1.64 mm toward the pin header from the PCB centre; align the front hexagon to the active area, not the PCB centre.
- Shift the 28 × 39.5 mm electronic cavity with the PCB to Y = -1.64 mm and place the USB-window bottom at Y = -24.75 mm so it remains 3.5 mm below the PCB bottom.
- Screen pocket clearance is 0.20 mm per side; screen post diameter is 1.65 mm.
- Hidden closure uses two 5.0 mm upper tongues and two 13.0 mm long lower cantilever arms with 0.40 mm engagement.
- No closure feature may protrude beyond the existing Blossom outline.
- Run all Python, pytest, FreeCAD build, audit, and render commands from `codex_usb_pager`.

---

### Task 1: Encode The Approved Mechanical Contract

**Files:**
- Modify: `codex_usb_pager/enclosure/cad/enclosure_params.py`
- Modify: `codex_usb_pager/enclosure/tests/test_enclosure_params.py`

**Interfaces:**
- Consumes: the approved dimensions in `docs/superpowers/specs/2026-07-29-hidden-resin-latch-design.md`.
- Produces: `DEFAULTS.screen_pocket_mm`, `DEFAULTS.screen_pcb_center_y_mm`, `DEFAULTS.screen_post_centres_mm`, and named latch/screen dimension fields used by every later task.

- [ ] **Step 1: Add failing parameter tests**

Append:

```python
def test_screen_mount_uses_screen_face_and_real_hole_centres():
    assert DEFAULTS.screen_pcb_mm == (27.78, 39.22)
    assert DEFAULTS.screen_face_mm == (25.30, 29.22)
    assert DEFAULTS.screen_active_mm == (23.40, 23.40)
    assert DEFAULTS.screen_face_to_pcb_mm == 2.0
    assert DEFAULTS.screen_hole_diameter_mm == 2.0
    assert DEFAULTS.screen_hole_edge_offset_mm == 2.5
    assert DEFAULTS.screen_pocket_mm == (25.70, 29.62)
    assert DEFAULTS.screen_post_diameter_mm == 1.65
    assert DEFAULTS.screen_post_boss_diameter_mm == 3.2


def test_display_active_area_not_pcb_is_centered_on_front_window():
    assert DEFAULTS.screen_active_offset_to_header_mm == 1.64
    assert DEFAULTS.screen_pcb_center_y_mm == -1.64
    assert DEFAULTS.screen_post_centres_mm == (
        (-11.39, 15.47),
        (11.39, 15.47),
        (-11.39, -18.75),
        (11.39, -18.75),
    )


def test_hidden_closure_dimensions_are_resin_safe():
    assert DEFAULTS.top_tongue_mm == (5.0, 2.5, 1.0)
    assert DEFAULTS.latch_arm_mm == (13.0, 4.0, 1.0)
    assert DEFAULTS.latch_root_radius_mm == 1.0
    assert DEFAULTS.latch_engagement_mm == 0.40
    assert DEFAULTS.latch_entry_angle_deg == 35.0
    assert DEFAULTS.latch_release_angle_deg == 20.0
    assert DEFAULTS.fingernail_notch_mm == (10.0, 1.2, 0.8)
```

- [ ] **Step 2: Run the tests and verify RED**

Run:

```powershell
python -m pytest enclosure/tests/test_enclosure_params.py -q
```

Expected: three failures because the screen mount and named latch parameters do not exist.

- [ ] **Step 3: Add the complete parameter set**

Replace the old `latch_arm_mm` tuple and add these fields to `EnclosureParameters`:

```python
    screen_pcb_mm: tuple[float, float] = (27.78, 39.22)
    screen_face_mm: tuple[float, float] = (25.30, 29.22)
    screen_active_mm: tuple[float, float] = (23.40, 23.40)
    screen_face_to_pcb_mm: float = 2.0
    screen_hole_diameter_mm: float = 2.0
    screen_hole_edge_offset_mm: float = 2.5
    screen_face_clearance_mm: float = 0.20
    screen_slot_depth_mm: float = 1.0
    screen_post_diameter_mm: float = 1.65
    screen_post_boss_diameter_mm: float = 3.2
    screen_post_height_mm: float = 3.2
    screen_retention_overlap_mm: float = 0.25
    screen_active_offset_to_header_mm: float = 1.64
    top_tongue_mm: tuple[float, float, float] = (5.0, 2.5, 1.0)
    top_tongue_clearance_mm: float = 0.25
    latch_arm_mm: tuple[float, float, float] = (13.0, 4.0, 1.0)
    latch_root_radius_mm: float = 1.0
    latch_engagement_mm: float = 0.40
    latch_entry_angle_deg: float = 35.0
    latch_release_angle_deg: float = 20.0
    latch_slot_clearance_mm: float = 0.30
    fingernail_notch_mm: tuple[float, float, float] = (10.0, 1.2, 0.8)
```

Add:

```python
    @property
    def screen_pocket_mm(self) -> tuple[float, float]:
        extra = 2.0 * self.screen_face_clearance_mm
        return (self.screen_face_mm[0] + extra, self.screen_face_mm[1] + extra)

    @property
    def screen_pcb_center_y_mm(self) -> float:
        return -self.screen_active_offset_to_header_mm

    @property
    def screen_post_centres_mm(self) -> tuple[tuple[float, float], ...]:
        x = self.screen_pcb_mm[0] / 2.0 - self.screen_hole_edge_offset_mm
        y = self.screen_pcb_mm[1] / 2.0 - self.screen_hole_edge_offset_mm
        centre_y = self.screen_pcb_center_y_mm
        return (
            (-x, centre_y + y),
            (x, centre_y + y),
            (-x, centre_y - y),
            (x, centre_y - y),
        )
```

- [ ] **Step 4: Run the tests and verify GREEN**

Run:

```powershell
python -m pytest enclosure/tests/test_enclosure_params.py -q
```

Expected: all parameter tests pass.

- [ ] **Step 5: Commit**

```powershell
git add codex_usb_pager/enclosure/cad/enclosure_params.py codex_usb_pager/enclosure/tests/test_enclosure_params.py
git commit -m "feat: define screen mount and latch dimensions"
```

---

### Task 2: Build A Real Screen-Face Mount

**Files:**
- Create: `codex_usb_pager/enclosure/tests/test_screen_mount_contract.py`
- Modify: `codex_usb_pager/enclosure/cad/build_blossom_enclosure.py`

**Interfaces:**
- Consumes: `DEFAULTS.screen_pocket_mm`, `screen_post_centres_mm`, `screen_post_height_mm`, and `screen_pcb_center_y_mm`.
- Produces: `rectangular_frame(...)`, `build_screen_mount()`, and named FreeCAD objects `ScreenMount`, `ScreenFaceEnvelope`, `ScreenActiveEnvelope`, `ScreenPost1` through `ScreenPost4`, `ScreenRetainerLeft`, and `ScreenRetainerRight`.

- [ ] **Step 1: Add failing source-contract tests**

Create:

```python
from pathlib import Path


BUILD = Path("enclosure/cad/build_blossom_enclosure.py").read_text(
    encoding="utf-8"
)


def test_front_uses_screen_face_mount_instead_of_flat_pcb_ledge():
    assert "screen_ledge = Part.makeBox" not in BUILD
    assert "def build_screen_mount(" in BUILD
    assert 'add_feature(document, "ScreenMount"' in BUILD
    assert "front_body.fuse(screen_mount)" in BUILD


def test_screen_mount_contains_four_posts_and_two_face_retainers():
    for token in (
        '"ScreenPost1"',
        '"ScreenPost2"',
        '"ScreenPost3"',
        '"ScreenPost4"',
        '"ScreenRetainerLeft"',
        '"ScreenRetainerRight"',
        '"ScreenFaceEnvelope"',
        '"ScreenActiveEnvelope"',
    ):
        assert token in BUILD


def test_hex_cut_is_applied_after_screen_mount_is_fused():
    fuse_index = BUILD.index("front_body.fuse(screen_mount)")
    cut_index = BUILD.index(".cut(front_hex_cut)", fuse_index)
    assert fuse_index < cut_index
```

- [ ] **Step 2: Run the tests and verify RED**

Run:

```powershell
python -m pytest enclosure/tests/test_screen_mount_contract.py -q
```

Expected: failures because the flat `screen_ledge` still exists and the new geometry is absent.

- [ ] **Step 3: Add reusable frame and screen-mount builders**

Add after `rounded_rectangle_prism`:

```python
def rectangular_frame(
    inner_width: float,
    inner_height: float,
    wall: float,
    height: float,
    base: App.Vector,
):
    outer = Part.makeBox(
        inner_width + 2.0 * wall,
        inner_height + 2.0 * wall,
        height,
        base,
    )
    inner = Part.makeBox(
        inner_width,
        inner_height,
        height + 0.2,
        App.Vector(base.x + wall, base.y + wall, base.z - 0.1),
    )
    return outer.cut(inner)


def build_screen_mount():
    pocket_width, pocket_height = DEFAULTS.screen_pocket_mm
    centre_y = DEFAULTS.screen_pcb_center_y_mm
    seam_z = DEFAULTS.front_seam_z_mm
    overlap_z = seam_z - 0.05
    frame_wall = 1.0
    frame = rectangular_frame(
        pocket_width,
        pocket_height,
        frame_wall,
        DEFAULTS.screen_slot_depth_mm + 0.05,
        App.Vector(
            -pocket_width / 2.0 - frame_wall,
            centre_y - pocket_height / 2.0 - frame_wall,
            overlap_z,
        ),
    )

    posts = []
    for x, y in DEFAULTS.screen_post_centres_mm:
        boss = Part.makeCylinder(
            DEFAULTS.screen_post_boss_diameter_mm / 2.0,
            0.8,
            App.Vector(x, y, overlap_z),
        )
        pin = Part.makeCylinder(
            DEFAULTS.screen_post_diameter_mm / 2.0,
            DEFAULTS.screen_post_height_mm,
            App.Vector(x, y, overlap_z),
        )
        posts.append(boss.fuse(pin))

    retainer_y = centre_y + 10.0
    arm_height = DEFAULTS.screen_face_to_pcb_mm + 0.25
    lip_height = 0.35
    lip_extension = (
        DEFAULTS.screen_face_clearance_mm
        + DEFAULTS.screen_retention_overlap_mm
    )
    left_arm = Part.makeBox(
        1.0,
        3.0,
        arm_height,
        App.Vector(-pocket_width / 2.0 - 1.0, retainer_y - 1.5, overlap_z),
    )
    left_lip = Part.makeBox(
        1.0 + lip_extension,
        3.0,
        lip_height,
        App.Vector(
            -pocket_width / 2.0 - 1.0,
            retainer_y - 1.5,
            seam_z + DEFAULTS.screen_face_to_pcb_mm - 0.10,
        ),
    )
    right_arm = Part.makeBox(
        1.0,
        3.0,
        arm_height,
        App.Vector(pocket_width / 2.0, retainer_y - 1.5, overlap_z),
    )
    right_lip = Part.makeBox(
        1.0 + lip_extension,
        3.0,
        lip_height,
        App.Vector(
            pocket_width / 2.0 - lip_extension,
            retainer_y - 1.5,
            seam_z + DEFAULTS.screen_face_to_pcb_mm - 0.10,
        ),
    )
    retainers = (left_arm.fuse(left_lip), right_arm.fuse(right_lip))
    screen_mount = frame.multiFuse([*posts, *retainers])

    face_width, face_height = DEFAULTS.screen_face_mm
    screen_face = Part.makeBox(
        face_width,
        face_height,
        DEFAULTS.screen_face_to_pcb_mm,
        App.Vector(
            -face_width / 2.0,
            centre_y - face_height / 2.0,
            seam_z,
        ),
    )
    active_width, active_height = DEFAULTS.screen_active_mm
    screen_active = Part.makeBox(
        active_width,
        active_height,
        DEFAULTS.screen_face_to_pcb_mm + 0.5,
        App.Vector(
            -active_width / 2.0,
            -active_height / 2.0,
            seam_z - 0.1,
        ),
    )
    return screen_mount, frame, posts, retainers, screen_face, screen_active
```

- [ ] **Step 4: Replace the flat ledge with the mounted geometry**

Delete the `screen_ledge = Part.makeBox(...)` block. Immediately after creating `front_hex_cut`, call:

```python
    (
        screen_mount,
        screen_frame,
        screen_posts,
        screen_retainers,
        screen_face,
        screen_active,
    ) = build_screen_mount()
```

Build the final front solid in this exact Boolean order:

```python
    front_body = (
        front_outer
        .fuse(screen_mount)
        .cut(front_recess)
        .cut(front_hex_cut)
    )
```

Create the named objects:

```python
    add_feature(document, "ScreenMount", screen_mount)
    add_feature(document, "ScreenFaceSlot", screen_frame)
    add_feature(document, "ScreenFaceEnvelope", screen_face)
    add_feature(document, "ScreenActiveEnvelope", screen_active)
    for index, post in enumerate(screen_posts, start=1):
        add_feature(document, f"ScreenPost{index}", post)
    add_feature(document, "ScreenRetainerLeft", screen_retainers[0])
    add_feature(document, "ScreenRetainerRight", screen_retainers[1])
```

- [ ] **Step 5: Run the source tests and verify GREEN**

Run:

```powershell
python -m pytest enclosure/tests/test_screen_mount_contract.py -q
```

Expected: 3 passed.

- [ ] **Step 6: Commit**

```powershell
git add codex_usb_pager/enclosure/cad/build_blossom_enclosure.py codex_usb_pager/enclosure/tests/test_screen_mount_contract.py
git commit -m "feat: add front screen face mount"
```

---

### Task 3: Replace Closure Placeholders With Mating Geometry

**Files:**
- Create: `codex_usb_pager/enclosure/tests/test_closure_contract.py`
- Modify: `codex_usb_pager/enclosure/cad/build_blossom_enclosure.py`

**Interfaces:**
- Consumes: the named tongue, latch, and fingernail dimensions from `DEFAULTS`.
- Produces: `make_x_prism(...)`, `build_hidden_closure(...)`, two top tongues and mating pockets, two cantilever arms with wedge hooks and mating pockets, two rear latch tunnels, and an actual subtracted fingernail notch.

- [ ] **Step 1: Add failing closure tests**

Create:

```python
from pathlib import Path


BUILD = Path("enclosure/cad/build_blossom_enclosure.py").read_text(
    encoding="utf-8"
)


def test_rectangular_closure_placeholders_are_removed():
    for old_line in (
        'Part.makeBox(5.0, 2.0, 2.0, App.Vector(-15.0, 19.5, 2.2))',
        'Part.makeBox(4.0, 2.0, 6.0, App.Vector(-16.0, -21.0, 6.0))',
    ):
        assert old_line not in BUILD


def test_closure_has_mating_front_and_rear_features():
    for name in (
        '"TopTongueLeft"',
        '"TopTongueRight"',
        '"TopPocketLeft"',
        '"TopPocketRight"',
        '"LatchArmLeft"',
        '"LatchArmRight"',
        '"LatchHookLeft"',
        '"LatchHookRight"',
        '"LatchPocketLeft"',
        '"LatchPocketRight"',
        '"FingernailNotch"',
    ):
        assert name in BUILD


def test_fingernail_notch_and_front_pockets_are_subtracted():
    assert "front_body.cut(top_pockets).cut(latch_pockets)" in BUILD
    assert "rear_body.cut(latch_tunnels).cut(fingernail_notch)" in BUILD
```

- [ ] **Step 2: Run the tests and verify RED**

Run:

```powershell
python -m pytest enclosure/tests/test_closure_contract.py -q
```

Expected: failures because the old rectangular blocks remain and no mating cuts exist.

- [ ] **Step 3: Add a wedge-prism helper**

Add:

```python
def make_x_prism(width: float, yz_points: tuple[tuple[float, float], ...], x: float):
    points = [App.Vector(x, y, z) for y, z in yz_points]
    wire = Part.makePolygon(points + [points[0]])
    return Part.Face(wire).extrude(App.Vector(width, 0, 0))
```

- [ ] **Step 4: Build the complete hidden closure**

Add:

```python
def build_hidden_closure(front_blank, rear_blank):
    seam_z = DEFAULTS.front_seam_z_mm
    tongue_width, tongue_insertion, tongue_thickness = DEFAULTS.top_tongue_mm
    tongue_clearance = DEFAULTS.top_tongue_clearance_mm
    tongue_centres = (-10.0, 10.0)
    tongues = []
    top_pocket_parts = []
    for centre_x in tongue_centres:
        x = centre_x - tongue_width / 2.0
        blade = Part.makeBox(
            tongue_width,
            tongue_insertion,
            tongue_thickness,
            App.Vector(x, 19.25, seam_z - tongue_thickness),
        )
        bridge = Part.makeBox(
            tongue_width,
            1.0,
            1.5,
            App.Vector(x, 19.25, seam_z - 0.05),
        )
        tongues.append(blade.fuse(bridge))
        top_pocket_parts.append(
            Part.makeBox(
                tongue_width + 2.0 * tongue_clearance,
                tongue_insertion + 2.0 * tongue_clearance,
                tongue_thickness + 0.2,
                App.Vector(
                    x - tongue_clearance,
                    19.25 - tongue_clearance,
                    seam_z - tongue_thickness - 0.1,
                ),
            )
        )

    arm_length, arm_width, arm_thickness = DEFAULTS.latch_arm_mm
    latch_centres_x = (-10.0, 10.0)
    arm_outer_y = -22.8
    arm_inner_y = arm_outer_y + arm_thickness
    arm_front_z = seam_z - 0.30
    arms = []
    hooks = []
    tunnels = []
    latch_pocket_parts = []
    for centre_x in latch_centres_x:
        x = centre_x - arm_width / 2.0
        tunnel = Part.makeBox(
            arm_width + 2.0 * DEFAULTS.latch_slot_clearance_mm,
            arm_thickness + 2.0 * DEFAULTS.latch_slot_clearance_mm,
            arm_length + 0.6,
            App.Vector(
                x - DEFAULTS.latch_slot_clearance_mm,
                arm_outer_y - DEFAULTS.latch_slot_clearance_mm,
                arm_front_z - 0.2,
            ),
        )
        arm = Part.makeBox(
            arm_width,
            arm_thickness,
            arm_length,
            App.Vector(x, arm_outer_y, arm_front_z),
        )
        anchor = Part.makeBox(
            arm_width,
            arm_thickness + 0.8,
            2.0,
            App.Vector(
                x,
                arm_outer_y,
                arm_front_z + arm_length - 0.2,
            ),
        )
        hook = make_x_prism(
            arm_width,
            (
                (arm_outer_y, seam_z - 1.0),
                (
                    arm_outer_y - DEFAULTS.latch_engagement_mm,
                    seam_z - 0.35,
                ),
                (
                    arm_outer_y - 0.26,
                    seam_z + 0.05,
                ),
                (arm_inner_y, seam_z + 0.05),
                (arm_inner_y, seam_z - 1.0),
            ),
            x,
        )
        pocket = Part.makeBox(
            arm_width + 2.0 * DEFAULTS.latch_slot_clearance_mm,
            arm_thickness
            + DEFAULTS.latch_engagement_mm
            + 2.0 * DEFAULTS.latch_slot_clearance_mm,
            1.35,
            App.Vector(
                x - DEFAULTS.latch_slot_clearance_mm,
                arm_outer_y
                - DEFAULTS.latch_engagement_mm
                - DEFAULTS.latch_slot_clearance_mm,
                seam_z - 1.1,
            ),
        )
        arms.append(arm.fuse(anchor))
        hooks.append(hook)
        tunnels.append(tunnel)
        latch_pocket_parts.append(pocket)

    top_pockets = Part.makeCompound(top_pocket_parts)
    latch_pockets = Part.makeCompound(latch_pocket_parts)
    latch_tunnels = Part.makeCompound(tunnels)
    rear_with_tunnels = rear_blank.cut(latch_tunnels)
    rear_with_closure = rear_with_tunnels.multiFuse([*tongues, *arms, *hooks])

    notch_width, notch_height, notch_depth = DEFAULTS.fingernail_notch_mm
    fingernail_notch = Part.makeBox(
        notch_width,
        notch_depth,
        notch_height,
        App.Vector(
            -notch_width / 2.0,
            rear_blank.BoundBox.YMin,
            seam_z,
        ),
    )
    return {
        "front": front_blank.cut(top_pockets).cut(latch_pockets),
        "rear": rear_with_closure.cut(fingernail_notch),
        "tongues": tongues,
        "top_pockets": top_pocket_parts,
        "arms": arms,
        "hooks": hooks,
        "latch_pockets": latch_pocket_parts,
        "tunnels": tunnels,
        "fingernail_notch": fingernail_notch,
        "front_blank": front_blank,
        "rear_blank": rear_blank,
    }
```

If an OpenCascade Boolean requires a healing pass, apply `removeSplitter()` to the returned front and rear shapes without changing any dimensions.

- [ ] **Step 5: Integrate the closure and named geometry**

After the screen mount and USB geometry are complete, call:

```python
    closure = build_hidden_closure(front_body, rear_body)
    front_body = closure["front"]
    rear_body = closure["rear"]
```

Remove the old `TopHook*` and `ReleaseLatch*` block. Add:

```python
    add_feature(document, "FrontClosureBlank", closure["front_blank"])
    add_feature(document, "RearClosureBlank", closure["rear_blank"])
    for side, tongue, pocket in zip(
        ("Left", "Right"),
        closure["tongues"],
        closure["top_pockets"],
    ):
        add_feature(document, f"TopTongue{side}", tongue)
        add_feature(document, f"TopPocket{side}", pocket)
    for side, arm, hook, pocket, tunnel in zip(
        ("Left", "Right"),
        closure["arms"],
        closure["hooks"],
        closure["latch_pockets"],
        closure["tunnels"],
    ):
        add_feature(document, f"LatchArm{side}", arm)
        add_feature(document, f"LatchHook{side}", hook)
        add_feature(document, f"LatchPocket{side}", pocket)
        add_feature(document, f"LatchTunnel{side}", tunnel)
    add_feature(document, "FingernailNotch", closure["fingernail_notch"])
```

- [ ] **Step 6: Run the closure tests and verify GREEN**

Run:

```powershell
python -m pytest enclosure/tests/test_closure_contract.py -q
```

Expected: 3 passed.

- [ ] **Step 7: Commit**

```powershell
git add codex_usb_pager/enclosure/cad/build_blossom_enclosure.py codex_usb_pager/enclosure/tests/test_closure_contract.py
git commit -m "feat: add mating hidden enclosure latches"
```

---

### Task 4: Audit Actual Screen And Closure Geometry

**Files:**
- Modify: `codex_usb_pager/enclosure/cad/audit_blossom_enclosure.py`
- Modify: `codex_usb_pager/enclosure/tests/test_audit_contract.py`

**Interfaces:**
- Consumes: the named FreeCAD objects generated by Tasks 2 and 3.
- Produces: serialisable proof that posts are fused, screen mount does not enter the display window, front pockets are actually cut, hooks sit inside their pocket envelopes, arms are fused to the rear, and the fingernail notch is actually removed.

- [ ] **Step 1: Add failing audit-contract tests**

Extend `test_geometry_audit_reports_relief_and_opening_facts` with:

```python
        "screen_post_count",
        "screen_mount_hex_intrusion_mm3",
        "screen_posts_fused",
        "closure_pocket_cut_mm3",
        "closure_hook_seated_mm3",
        "closure_arms_fused",
        "fingernail_notch_cut_mm3",
```

Add:

```python
def test_closure_contract_requires_mating_features_not_placeholders():
    for name in (
        "TopTongueLeft",
        "TopTongueRight",
        "TopPocketLeft",
        "TopPocketRight",
        "LatchArmLeft",
        "LatchArmRight",
        "LatchHookLeft",
        "LatchHookRight",
        "LatchPocketLeft",
        "LatchPocketRight",
        "FingernailNotch",
    ):
        assert name in REQUIRED_CLOSURE
    assert "ReleaseLatchLeft" not in REQUIRED_CLOSURE
```

- [ ] **Step 2: Run the tests and verify RED**

Run:

```powershell
python -m pytest enclosure/tests/test_audit_contract.py -q
```

Expected: failures because the new fields and required names are absent.

- [ ] **Step 3: Replace the closure name-only contract**

Set:

```python
REQUIRED_SCREEN_MOUNT = (
    "ScreenMount",
    "ScreenFaceSlot",
    "ScreenFaceEnvelope",
    "ScreenActiveEnvelope",
    "ScreenPost1",
    "ScreenPost2",
    "ScreenPost3",
    "ScreenPost4",
    "ScreenRetainerLeft",
    "ScreenRetainerRight",
)

REQUIRED_CLOSURE = (
    "FrontClosureBlank",
    "RearClosureBlank",
    "TopTongueLeft",
    "TopTongueRight",
    "TopPocketLeft",
    "TopPocketRight",
    "LatchArmLeft",
    "LatchArmRight",
    "LatchHookLeft",
    "LatchHookRight",
    "LatchPocketLeft",
    "LatchPocketRight",
    "LatchTunnelLeft",
    "LatchTunnelRight",
    "FingernailNotch",
)
```

Add:

```python
def screen_mount_contract_errors(names: set[str]) -> list[str]:
    return [name for name in REQUIRED_SCREEN_MOUNT if name not in names]
```

- [ ] **Step 4: Compute Boolean evidence in `audit_document`**

Before building `report`, add:

```python
    screen_mount = document.getObject("ScreenMount").Shape
    screen_posts = [
        document.getObject(f"ScreenPost{index}").Shape
        for index in range(1, 5)
    ]
    front_blank = document.getObject("FrontClosureBlank").Shape
    rear_blank = document.getObject("RearClosureBlank").Shape
    top_pockets = [
        document.getObject(f"TopPocket{side}").Shape
        for side in ("Left", "Right")
    ]
    latch_pockets = [
        document.getObject(f"LatchPocket{side}").Shape
        for side in ("Left", "Right")
    ]
    latch_hooks = [
        document.getObject(f"LatchHook{side}").Shape
        for side in ("Left", "Right")
    ]
    latch_arms = [
        document.getObject(f"LatchArm{side}").Shape
        for side in ("Left", "Right")
    ]
    fingernail_notch = document.getObject("FingernailNotch").Shape
    all_front_pockets = [*top_pockets, *latch_pockets]
```

Add these report fields:

```python
        "required_screen_mount": not screen_mount_contract_errors(names),
        "screen_post_count": len(screen_posts),
        "screen_mount_hex_intrusion_mm3": round(
            screen_mount.common(front_hex).Volume,
            6,
        ),
        "screen_posts_fused": all(
            abs(front.common(post).Volume - post.Volume) <= 1e-5
            for post in screen_posts
        ),
        "closure_pocket_cut_mm3": round(
            sum(front_blank.common(pocket).Volume for pocket in all_front_pockets),
            6,
        ),
        "closure_hook_seated_mm3": round(
            sum(
                hook.common(pocket).Volume
                for hook, pocket in zip(latch_hooks, latch_pockets)
            ),
            6,
        ),
        "closure_arms_fused": all(
            abs(rear.common(arm).Volume - arm.Volume) <= 1e-5
            for arm in latch_arms
        ),
        "fingernail_notch_cut_mm3": round(
            rear_blank.common(fingernail_notch).Volume
            - rear.common(fingernail_notch).Volume,
            6,
        ),
```

The build is acceptable only when:

- `screen_post_count == 4`
- `screen_mount_hex_intrusion_mm3 == 0`
- `screen_posts_fused is True`
- `closure_pocket_cut_mm3 > 0`
- `closure_hook_seated_mm3 > 0`
- `closure_arms_fused is True`
- `fingernail_notch_cut_mm3 > 0`
- `assembly_interference_mm3 == 0`

- [ ] **Step 5: Run the audit tests and verify GREEN**

Run:

```powershell
python -m pytest enclosure/tests/test_audit_contract.py -q
```

Expected: all audit contract tests pass.

- [ ] **Step 6: Commit**

```powershell
git add codex_usb_pager/enclosure/cad/audit_blossom_enclosure.py codex_usb_pager/enclosure/tests/test_audit_contract.py
git commit -m "test: audit real enclosure retention geometry"
```

---

### Task 5: Rebuild, Render, And Verify The Enclosure

**Files:**
- Create: `codex_usb_pager/enclosure/cad/render_blossom_review.py`
- Modify: `codex_usb_pager/enclosure/README.md`
- Modify: `codex_usb_pager/enclosure/outputs/README.md`
- Regenerate: `codex_usb_pager/enclosure/outputs/blossom-enclosure.FCStd`
- Regenerate: `codex_usb_pager/enclosure/outputs/blossom-enclosure.step`
- Regenerate: `codex_usb_pager/enclosure/outputs/blossom-front.stl`
- Regenerate: `codex_usb_pager/enclosure/outputs/blossom-rear.stl`
- Create: `codex_usb_pager/enclosure/outputs/review-front-inside.png`
- Create: `codex_usb_pager/enclosure/outputs/review-rear-inside.png`
- Create: `codex_usb_pager/enclosure/outputs/review-closure-cutaway.png`
- Create: `codex_usb_pager/enclosure/outputs/review-screen-mount.png`

**Interfaces:**
- Consumes: the generated FCStd and all named screen/closure features.
- Produces: final exchange meshes plus internal views that let the user inspect features hidden in the assembled model.

- [ ] **Step 1: Add the review renderer**

Create a FreeCAD GUI script that opens `blossom-enclosure.FCStd`, hides every object, and saves four 1600 × 1200 images. Use these visibility groups:

```python
VIEWS = {
    "review-front-inside.png": (
        "FrontShell",
        "ScreenMount",
        "ScreenPost1",
        "ScreenPost2",
        "ScreenPost3",
        "ScreenPost4",
        "ScreenRetainerLeft",
        "ScreenRetainerRight",
    ),
    "review-rear-inside.png": (
        "RearCover",
        "TopTongueLeft",
        "TopTongueRight",
        "LatchArmLeft",
        "LatchArmRight",
        "LatchHookLeft",
        "LatchHookRight",
    ),
    "review-closure-cutaway.png": (
        "TopTongueLeft",
        "TopPocketLeft",
        "LatchArmLeft",
        "LatchHookLeft",
        "LatchPocketLeft",
        "FingernailNotch",
    ),
    "review-screen-mount.png": (
        "ScreenFaceSlot",
        "ScreenFaceEnvelope",
        "ScreenPost1",
        "ScreenPost2",
        "ScreenPost3",
        "ScreenPost4",
        "ScreenRetainerLeft",
        "ScreenRetainerRight",
    ),
}
```

For each group, set `ViewObject.Visibility = True`, call `viewAxonometric()`, `fitAll()`, then:

```python
Gui.activeDocument().activeView().saveImage(
    os.path.join(OUTPUT_DIR, filename),
    1600,
    1200,
    "Current",
)
```

Assign contrasting colors to the shell, screen envelope, posts, tongues, hooks, and pockets before saving.

- [ ] **Step 2: Run the entire pure-Python suite**

Run:

```powershell
python -m pytest enclosure/tests -q
```

Expected: all tests pass.

- [ ] **Step 3: Rebuild all CAD outputs**

From `codex_usb_pager`, run:

```powershell
"code=open(r'enclosure/cad/build_blossom_enclosure.py').read(); exec(compile(code, r'enclosure/cad/build_blossom_enclosure.py', 'exec'), {'__name__':'__main__','__file__':r'enclosure/cad/build_blossom_enclosure.py'})" | & 'C:\Program Files\FreeCAD 1.1\bin\FreeCADCmd.exe' -c
```

Expected: `BUILD PASS` and refreshed FCStd, STEP, front STL, and rear STL files.

- [ ] **Step 4: Run the real FreeCAD geometry audit**

From `codex_usb_pager`, run:

```powershell
& 'C:\Program Files\FreeCAD 1.1\bin\FreeCADCmd.exe' 'enclosure/cad/audit_blossom_enclosure.py' 'enclosure/outputs/blossom-enclosure.FCStd'
```

Expected: valid front and rear solids, zero USB and screen-window obstruction, four fused posts, positive pocket-cut and hook-seating volumes, fused latch arms, and a positive fingernail-notch cut volume.

- [ ] **Step 5: Render and inspect all four internal views**

Run:

```powershell
& 'C:\Program Files\FreeCAD 1.1\bin\FreeCAD.exe' -c 'enclosure/cad/render_blossom_review.py'
```

Inspect each PNG for:

- all four posts aligned with the dimensioned hole positions;
- no mount material visible inside the hexagonal display opening;
- two screen-face retention lips, not PCB-edge clamps;
- top tongues seated in real front pockets;
- lower wedge hooks seated in real front pockets;
- no closure protrusion outside the Blossom outline;
- the fingernail notch visible only at the lower seam.

- [ ] **Step 6: Document build and audit commands**

Update `codex_usb_pager/enclosure/README.md` with the audit command, render command, output image names, and the note that the first resin print must be treated as a fit coupon for 0.20–0.30 mm clearances. Update `codex_usb_pager/enclosure/outputs/README.md` with the four review PNG names. Generated FCStd, STEP, STL, and PNG files remain ignored local deliverables.

- [ ] **Step 7: Run final verification**

Run:

```powershell
python -m pytest enclosure/tests -q
git diff --check
git status --short
```

Expected: the full enclosure test suite passes, `git diff --check` prints nothing, and status lists only the intentional source, test, documentation, and regenerated artifact changes.

- [ ] **Step 8: Commit**

```powershell
git add codex_usb_pager/enclosure/cad/render_blossom_review.py codex_usb_pager/enclosure/README.md codex_usb_pager/enclosure/outputs/README.md
git commit -m "feat: deliver hidden latch enclosure review model"
```
