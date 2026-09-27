# Front-Mounted Hidden Latch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the visible front-shell latch holes with short rigid male
features on the front side petals and blind sockets plus long flexible female
arms on the rear shell, while reserving the user's relocated buzzer envelope.

**Architecture:** The front closure is additive only: two axial locating tongues and two short wedge hooks fuse to the existing front shell without cutting `FrontClosureBlank`. The rear cover owns all compliant parts and blind recesses. Geometry audit compares the final shells with their pre-closure blanks and renders opaque exterior views so a valid solid cannot hide an exterior breakthrough.

**Tech Stack:** Python 3, pytest, FreeCAD 1.1 Python API (`Part`, `Mesh`, `Import`), FreeCAD GUI macro rendering.

## Global Constraints

- Front closure geometry may add material but must remove exactly `0.0 mm³` from `FrontClosureBlank`.
- Rear locating sockets and latch tunnels must not reach any rear exterior surface.
- Front locating tongues: 5.0 mm wide, 1.0 mm thick, 2.5 mm axial projection, centres X = ±10.0 mm and Y = 19.75 mm.
- Front hooks: 4.0 mm wide, 1.2 mm stem thickness, 2.2 mm axial projection,
  initial centres X = ±15.0 mm and Y = -9.0 mm. A same-petal adjustment up to
  1.0 mm is allowed only when the audit proves it necessary.
- Side hooks and rear arms deflect outward along X; their profiles are built in
  XZ and extruded 4.0 mm along Y.
- Hook engagement is 0.35 mm, entry angle 35°, release angle 20°.
- Rear arms remain 13.0 × 4.0 × 1.0 mm with R1.0 roots and 0.30 mm activity clearance.
- Rear exterior guard thickness is 1.0 mm; the intentional fingernail notch is excluded from the breach calculation.
- The fully internal buzzer uses a reserved cylinder of diameter 12.0 mm and
  height 11.5 mm at initial centre X = -9.0 mm and Y = 4.36 mm. The cylinder
  starts at the screen-PCB rear plane and may require a local rear-shell
  clearance cut, but it must not break the 1.0 mm exterior guard.
- Screen mount, rounded USB rear opening, no buzzer sound hole and 1.5 mm
  Blossom relief remain unchanged.
- Final front/rear assembly interference, screen obstruction, USB obstruction
  and buzzer obstruction must each remain `0.0 mm³`.

---

### Task 1: Encode Reversed-Closure Dimensions

**Files:**
- Modify: `codex_usb_pager/enclosure/cad/enclosure_params.py`
- Modify: `codex_usb_pager/enclosure/tests/test_enclosure_params.py`

**Interfaces:**
- Consumes: `EnclosureParameters` and `DEFAULTS`.
- Produces: named front-male and rear-guard parameters used by the builder and audit.

- [ ] **Step 1: Write the failing parameter test**

Replace `test_hidden_closure_dimensions_are_resin_safe` with:

```python
def test_hidden_closure_places_rigid_males_on_front():
    assert DEFAULTS.closure_style == "front_male_rear_flex"
    assert DEFAULTS.top_tongue_mm == (5.0, 1.0, 2.5)
    assert DEFAULTS.top_tongue_centres_mm == (
        (-10.0, 19.75),
        (10.0, 19.75),
    )
    assert DEFAULTS.front_latch_hook_mm == (4.0, 1.2, 2.2)
    assert DEFAULTS.front_latch_centres_mm == (
        (-15.0, -9.0),
        (15.0, -9.0),
    )
    assert DEFAULTS.buzzer_clearance_mm == (12.0, 11.5)
    assert DEFAULTS.buzzer_centre_mm == (-9.0, 4.36)
    assert DEFAULTS.latch_arm_mm == (13.0, 4.0, 1.0)
    assert DEFAULTS.latch_root_radius_mm == 1.0
    assert DEFAULTS.latch_engagement_mm == 0.35
    assert DEFAULTS.latch_entry_angle_deg == 35.0
    assert DEFAULTS.latch_release_angle_deg == 20.0
    assert DEFAULTS.rear_exterior_guard_mm == 1.0
    assert DEFAULTS.fingernail_notch_mm == (10.0, 1.2, 0.8)
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```powershell
python -m pytest enclosure/tests/test_enclosure_params.py::test_hidden_closure_places_rigid_males_on_front -q
```

Expected: FAIL because `top_tongue_centres_mm`, `front_latch_hook_mm`,
`front_latch_centres_mm`, and `rear_exterior_guard_mm` do not exist and the
old engagement is 0.40 mm.

- [ ] **Step 3: Implement the parameter contract**

Change the closure fields in `EnclosureParameters` to:

```python
    top_tongue_mm: tuple[float, float, float] = (5.0, 1.0, 2.5)
    top_tongue_centres_mm: tuple[tuple[float, float], ...] = (
        (-10.0, 19.75),
        (10.0, 19.75),
    )
    top_tongue_clearance_mm: float = 0.25
    front_latch_hook_mm: tuple[float, float, float] = (4.0, 1.2, 2.2)
    front_latch_centres_mm: tuple[tuple[float, float], ...] = (
        (-15.0, -9.0),
        (15.0, -9.0),
    )
    buzzer_clearance_mm: tuple[float, float] = (12.0, 11.5)
    buzzer_centre_mm: tuple[float, float] = (-9.0, 4.36)
    latch_arm_mm: tuple[float, float, float] = (13.0, 4.0, 1.0)
    latch_root_radius_mm: float = 1.0
    latch_engagement_mm: float = 0.35
    latch_entry_angle_deg: float = 35.0
    latch_release_angle_deg: float = 20.0
    latch_slot_clearance_mm: float = 0.30
    rear_exterior_guard_mm: float = 1.0
    closure_style: str = "front_male_rear_flex"
```

- [ ] **Step 4: Run the parameter suite and verify GREEN**

Run:

```powershell
python -m pytest enclosure/tests/test_enclosure_params.py -q
```

Expected: all parameter tests PASS.

- [ ] **Step 5: Commit**

```powershell
git add -- codex_usb_pager/enclosure/cad/enclosure_params.py codex_usb_pager/enclosure/tests/test_enclosure_params.py
git commit -m "feat: define front-mounted latch dimensions"
```

---

### Task 2: Reverse the Real Closure Geometry

**Files:**
- Modify: `codex_usb_pager/enclosure/cad/enclosure_params.py`
- Modify: `codex_usb_pager/enclosure/cad/build_blossom_enclosure.py`
- Modify: `codex_usb_pager/enclosure/tests/test_enclosure_params.py`
- Modify: `codex_usb_pager/enclosure/tests/test_closure_contract.py`
- Modify: `codex_usb_pager/enclosure/tests/test_audit_contract.py`
- Modify: `codex_usb_pager/enclosure/cad/audit_blossom_enclosure.py`

**Interfaces:**
- Consumes: the parameters from Task 1, screen-PCB placement and the existing
  `make_x_prism` helper.
- Produces: `FrontTopTongue*`, `RearTopSocket*`, `FrontLatchHook*`,
  `RearLatchArm*`, `RearLatchPocket*`, `RearLatchTunnel*`,
  `RearClosureExteriorGuard`, `BuzzerEnvelope`, local buzzer clearance and new
  serialisable audit fields.

- [ ] **Step 1: Write failing source-contract tests**

Replace the old mating-feature and subtraction tests in
`test_closure_contract.py` with:

```python
def test_closure_uses_front_males_and_rear_flexible_receivers():
    for name in (
        '"FrontTopTongueLeft"',
        '"FrontTopTongueRight"',
        '"RearTopSocketLeft"',
        '"RearTopSocketRight"',
        '"FrontLatchHookLeft"',
        '"FrontLatchHookRight"',
        '"RearLatchArmLeft"',
        '"RearLatchArmRight"',
        '"RearLatchPocketLeft"',
        '"RearLatchPocketRight"',
        '"RearLatchTunnelLeft"',
        '"RearLatchTunnelRight"',
        '"RearClosureExteriorGuard"',
        '"BuzzerEnvelope"',
        '"FingernailNotch"',
    ):
        assert name in BUILD


def test_front_closure_is_additive_and_rear_receivers_are_subtractive():
    assert "front_body = front_blank.multiFuse([*tongues, *hooks])" in BUILD
    assert "front_body.cut(top_pockets)" not in BUILD
    assert "front_body.cut(latch_pockets)" not in BUILD
    assert "rear_body.cut(top_sockets).cut(latch_tunnels)" in BUILD
    assert ".cut(fingernail_notch)" in BUILD
```

Update `test_audit_contract.py` so `REQUIRED_CLOSURE` contains the new names
and so `audit_document` must expose:

```python
for field in (
    "front_closure_skin_removed_mm3",
    "front_closure_features_fused",
    "rear_socket_cut_mm3",
    "rear_latch_pocket_cut_mm3",
    "rear_latch_arms_fused",
    "rear_exterior_breach_mm3",
    "buzzer_obstruction_mm3",
):
    assert field in getsource(audit_document)
```

- [ ] **Step 2: Run the contract tests and verify RED**

Run:

```powershell
python -m pytest enclosure/tests/test_closure_contract.py enclosure/tests/test_audit_contract.py -q
```

Expected: FAIL because the side-petal parameter values, X-deflecting latch
geometry and buzzer envelope are not yet implemented.

- [ ] **Step 3: Build front axial tongues and rear blind sockets**

In `build_hidden_closure`, create each tongue with a 0.05 mm fusion overlap:

```python
tongue_width, tongue_thickness, tongue_projection = DEFAULTS.top_tongue_mm
tongues = []
top_socket_parts = []
for centre_x, centre_y in DEFAULTS.top_tongue_centres_mm:
    tongue = Part.makeBox(
        tongue_width,
        tongue_thickness,
        tongue_projection + 0.05,
        App.Vector(
            centre_x - tongue_width / 2.0,
            centre_y - tongue_thickness / 2.0,
            seam_z - 0.05,
        ),
    )
    socket = Part.makeBox(
        tongue_width + 2.0 * DEFAULTS.top_tongue_clearance_mm,
        tongue_thickness + 2.0 * DEFAULTS.top_tongue_clearance_mm,
        tongue_projection + 0.30,
        App.Vector(
            centre_x - tongue_width / 2.0
            - DEFAULTS.top_tongue_clearance_mm,
            centre_y - tongue_thickness / 2.0
            - DEFAULTS.top_tongue_clearance_mm,
            seam_z - 0.05,
        ),
    )
    tongues.append(tongue)
    top_socket_parts.append(socket)
```

Fuse a 0.5 mm-high tapered cap or apply an equivalent tip chamfer while
retaining the same maximum 2.5 mm projection.

- [ ] **Step 4: Build side-petal front wedge hooks and rear female arms**

Add a `make_y_prism` helper. For each centre in
`front_latch_centres_mm`, mirror an XZ hook profile and extrude it 4.0 mm along
Y. The short front hook points toward the nearest side wall. The rear arm sits
immediately outside that hook and runs 13.0 mm rearward from the seam, so the
arm deflects outward along X during insertion and removal.

```python
hook = make_y_prism(
    hook_width,
    mirrored_xz_profile,
    centre_y - hook_width / 2.0,
)
```

Create the activity tunnel around `arm_box`, fuse an anchor and R1.0 root at
the deep end, and use `arm.cut(latch_pocket)` as the review/audit arm shape.
The tunnel must leave at least 0.30 mm around the moving surfaces. Check a
small discrete grid around each initial centre, within the allowed 1.0 mm
same-petal adjustment, and accept only a mirrored pair that has zero USB,
buzzer and exterior-guard intersection.

- [ ] **Step 5: Reserve the relocated buzzer**

Create `BuzzerEnvelope` as a 12.0 mm diameter, 11.5 mm high cylinder centred at
X = -9.0 mm and Y = 4.36 mm. Its front face is the screen-PCB rear plane:

```python
buzzer_front_z = (
    DEFAULTS.front_seam_z_mm + DEFAULTS.screen_face_to_pcb_mm
)
buzzer_envelope = Part.makeCylinder(
    DEFAULTS.buzzer_clearance_mm[0] / 2.0,
    DEFAULTS.buzzer_clearance_mm[1],
    App.Vector(
        DEFAULTS.buzzer_centre_mm[0],
        DEFAULTS.buzzer_centre_mm[1],
        buzzer_front_z,
    ),
)
```

Subtract only the portion not already cleared by the main electronics cavity
from the rear blank. Keep the cylinder fully inside the 1.0 mm exterior guard,
register it as `BuzzerEnvelope`, and do not add a buzzer sound opening.

- [ ] **Step 6: Apply closure booleans without cutting the front**

Use:

```python
top_sockets = Part.makeCompound(top_socket_parts)
latch_tunnels = Part.makeCompound(tunnels)
front_body = front_blank.multiFuse([*tongues, *hooks])
rear_body = (
    rear_blank
    .cut(top_sockets)
    .cut(latch_tunnels)
    .cut(fingernail_notch)
)
rear_body = rear_body.multiFuse(arms)
```

Return the new feature lists with explicit keys:

```python
return {
    "front": front_body.removeSplitter(),
    "rear": rear_body.removeSplitter(),
    "front_tongues": tongues,
    "rear_top_sockets": top_socket_parts,
    "front_hooks": hooks,
    "rear_arms": arms,
    "rear_latch_pockets": latch_pocket_parts,
    "rear_latch_tunnels": tunnels,
    "fingernail_notch": fingernail_notch,
    "front_blank": front_blank,
    "rear_blank": rear_blank,
}
```

Register the new object names and remove the old ambiguous `TopPocket*`,
`LatchHook*`, and `LatchArm*` registrations.

- [ ] **Step 7: Add exterior-guard, closure and buzzer audit facts**

Create `RearClosureExteriorGuard` from an inward-scaled Blossom core in
`build()`, so the guard follows the curved petal perimeter instead of using
the rectangular bounding box:

```python
guard_ratio = (
    DEFAULTS.blossom_target_width_mm
    - 2.0 * DEFAULTS.rear_exterior_guard_mm
) / DEFAULTS.blossom_target_width_mm
rear_guard_core = Part.makeLoft(
    [
        wire_profile(
            outer_wire,
            svg_scale * guard_ratio,
            DEFAULTS.front_seam_z_mm - 0.1,
        ),
        wire_profile(
            outer_wire,
            svg_scale * guard_ratio,
            DEFAULTS.front_seam_z_mm
            + DEFAULTS.internal_envelope_mm[2],
        ),
        wire_profile(
            outer_wire,
            svg_scale * 0.965 * guard_ratio,
            DEFAULTS.maximum_thickness_mm
            - DEFAULTS.rear_exterior_guard_mm,
        ),
    ],
    True,
    True,
)
rear_exterior_guard = rear_body.cut(rear_guard_core)
```

Pass `rear_exterior_guard` into `build_hidden_closure`, retain it unchanged
for the audit, and register it as `RearClosureExteriorGuard`.

In `audit_document`, calculate:

```python
front_removed = front_blank.cut(front)
front_features = [
    document.getObject(name).Shape
    for name in (
        "FrontTopTongueLeft",
        "FrontTopTongueRight",
        "FrontLatchHookLeft",
        "FrontLatchHookRight",
    )
]
rear_removed_without_notch = rear_blank.cut(
    rear.fuse(fingernail_notch)
)
report.update(
    {
        "front_closure_skin_removed_mm3": round(
            front_removed.Volume, 6
        ),
        "front_closure_features_fused": all(
            abs(front.common(feature).Volume - feature.Volume) <= 1e-5
            for feature in front_features
        ),
        "rear_socket_cut_mm3": round(
            sum(
                rear_blank.common(socket).Volume
                - rear.common(socket).Volume
                for socket in rear_sockets
            ),
            6,
        ),
        "rear_latch_pocket_cut_mm3": round(
            sum(pocket.Volume for pocket in rear_latch_pockets),
            6,
        ),
        "rear_latch_arms_fused": all(
            abs(rear.common(arm).Volume - arm.Volume) <= 1e-5
            for arm in rear_arms
        ),
        "rear_exterior_breach_mm3": round(
            rear_removed_without_notch.common(rear_exterior_guard).Volume,
            6,
        ),
        "buzzer_obstruction_mm3": round(
            rear.common(buzzer_envelope).Volume,
            6,
        ),
    }
)
```

- [ ] **Step 8: Run source tests and verify GREEN**

Run:

```powershell
python -m pytest enclosure/tests/test_closure_contract.py enclosure/tests/test_audit_contract.py enclosure/tests/test_enclosure_params.py -q
```

Expected: all selected tests PASS.

- [ ] **Step 9: Build and audit the real FreeCAD geometry**

Run:

```powershell
"code=open(r'enclosure/cad/build_blossom_enclosure.py').read(); exec(compile(code, r'enclosure/cad/build_blossom_enclosure.py', 'exec'), {'__name__':'__main__','__file__':r'enclosure/cad/build_blossom_enclosure.py'})" | & 'C:\Program Files\FreeCAD 1.1\bin\FreeCADCmd.exe' -c
```

Then:

```powershell
"import sys; sys.argv=[r'enclosure/cad/audit_blossom_enclosure.py', r'enclosure/outputs/blossom-enclosure.FCStd']; code=open(r'enclosure/cad/audit_blossom_enclosure.py').read(); exec(compile(code, r'enclosure/cad/audit_blossom_enclosure.py', 'exec'), {'__name__':'__main__','__file__':r'enclosure/cad/audit_blossom_enclosure.py'})" | & 'C:\Program Files\FreeCAD 1.1\bin\FreeCADCmd.exe' -c
```

Expected: `BUILD PASS`; the front skin removal, rear exterior breach,
assembly interference, screen obstruction, USB obstruction and buzzer
obstruction are each `0.0 mm³`; both shells are valid single solids.

- [ ] **Step 10: Commit**

```powershell
git add -- codex_usb_pager/enclosure/cad/enclosure_params.py codex_usb_pager/enclosure/cad/build_blossom_enclosure.py codex_usb_pager/enclosure/cad/audit_blossom_enclosure.py codex_usb_pager/enclosure/tests/test_enclosure_params.py codex_usb_pager/enclosure/tests/test_closure_contract.py codex_usb_pager/enclosure/tests/test_audit_contract.py
git commit -m "fix: move hidden latches to side petals"
```

---

### Task 3: Add Opaque Exterior Review Views

**Files:**
- Modify: `codex_usb_pager/enclosure/cad/render_blossom_review.py`
- Modify: `codex_usb_pager/enclosure/tests/test_render_contract.py`
- Modify: `codex_usb_pager/enclosure/README.md`
- Modify: `codex_usb_pager/enclosure/outputs/README.md`

**Interfaces:**
- Consumes: new FreeCAD object names from Task 2.
- Produces: opaque exterior PNGs plus updated internal and cutaway views.

- [ ] **Step 1: Write the failing render contract**

Require both new outputs and all renamed closure objects:

```python
def test_review_renderer_includes_opaque_exterior_views():
    source = RENDER.read_text(encoding="utf-8")
    for name in (
        "review-front-exterior.png",
        "review-rear-exterior.png",
        "FrontTopTongueLeft",
        "RearTopSocketLeft",
        "FrontLatchHookLeft",
        "RearLatchArmLeft",
        "RearLatchPocketLeft",
        "BuzzerEnvelope",
    ):
        assert name in source
    assert '"FrontShell": ((0.72, 0.76, 0.80), 0)' in source
    assert '"RearCover": ((0.42, 0.46, 0.50), 0)' in source
```

- [ ] **Step 2: Run the render contract and verify RED**

Run:

```powershell
python -m pytest enclosure/tests/test_render_contract.py -q
```

Expected: FAIL because exterior filenames and renamed objects are absent.

- [ ] **Step 3: Add exterior and renamed internal views**

Add:

```python
"review-front-exterior.png": (("FrontShell",), "bottom"),
"review-rear-exterior.png": (("RearCover",), "top"),
```

Replace old closure names in internal and cutaway views with:

```python
"FrontTopTongueLeft",
"RearTopSocketLeft",
"FrontLatchHookLeft",
"RearLatchArmLeft",
"RearLatchPocketLeft",
```

Set shell styles to zero transparency. Use separate translucent helper styles
for `FrontClosureBlank` and `RearClosureBlank`.

- [ ] **Step 4: Update output documentation**

Add `review-buzzer-clearance.png`. Document all seven review images and state
that the two exterior views must show continuous opaque surfaces without
rectangular closure openings.

- [ ] **Step 5: Run the render contract and verify GREEN**

Run:

```powershell
python -m pytest enclosure/tests/test_render_contract.py -q
```

Expected: all render contract tests PASS.

- [ ] **Step 6: Commit**

```powershell
git add -- codex_usb_pager/enclosure/cad/render_blossom_review.py codex_usb_pager/enclosure/tests/test_render_contract.py codex_usb_pager/enclosure/README.md codex_usb_pager/enclosure/outputs/README.md
git commit -m "test: add opaque shell visibility review"
```

---

### Task 4: Build, Audit and Visually Verify the Corrected Enclosure

**Files:**
- Generated: `codex_usb_pager/enclosure/outputs/blossom-enclosure.FCStd`
- Generated: `codex_usb_pager/enclosure/outputs/blossom-enclosure.step`
- Generated: `codex_usb_pager/enclosure/outputs/blossom-front.stl`
- Generated: `codex_usb_pager/enclosure/outputs/blossom-rear.stl`
- Generated: `codex_usb_pager/enclosure/outputs/review-*.png`

**Interfaces:**
- Consumes: all source and tests from Tasks 1–3.
- Produces: verified CAD deliverables and visual evidence for user approval.

- [ ] **Step 1: Run the complete Python test suite**

Run:

```powershell
python -m pytest enclosure/tests -q
```

Expected: all tests PASS before FreeCAD export-dependent checks; if the STL
test is the only failure in a clean worktree, continue to Step 2 and rerun.

- [ ] **Step 2: Rebuild through FreeCAD**

Run from `codex_usb_pager`:

```powershell
"code=open(r'enclosure/cad/build_blossom_enclosure.py').read(); exec(compile(code, r'enclosure/cad/build_blossom_enclosure.py', 'exec'), {'__name__':'__main__','__file__':r'enclosure/cad/build_blossom_enclosure.py'})" | & 'C:\Program Files\FreeCAD 1.1\bin\FreeCADCmd.exe' -c
```

Expected: `BUILD PASS` and four non-empty CAD/mesh outputs.

- [ ] **Step 3: Run the serialisable geometry audit**

Run:

```powershell
"import sys; sys.argv=[r'enclosure/cad/audit_blossom_enclosure.py', r'enclosure/outputs/blossom-enclosure.FCStd']; code=open(r'enclosure/cad/audit_blossom_enclosure.py').read(); exec(compile(code, r'enclosure/cad/audit_blossom_enclosure.py', 'exec'), {'__name__':'__main__','__file__':r'enclosure/cad/audit_blossom_enclosure.py'})" | & 'C:\Program Files\FreeCAD 1.1\bin\FreeCADCmd.exe' -c
```

Required values:

```text
front_closure_skin_removed_mm3 = 0.0
front_closure_features_fused = true
rear_latch_arms_fused = true
rear_exterior_breach_mm3 = 0.0
assembly_interference_mm3 = 0.0
screen_obstruction_mm3 = 0.0
usb_obstruction_mm3 = 0.0
buzzer_obstruction_mm3 = 0.0
front_solids = 1
rear_solids = 1
front_valid = true
rear_valid = true
```

- [ ] **Step 4: Render all review views**

Run:

```powershell
$macro = (Resolve-Path 'enclosure/cad/render_blossom_review.FCMacro').Path
$process = Start-Process -FilePath 'C:\Program Files\FreeCAD 1.1\bin\FreeCAD.exe' -ArgumentList $macro -WindowStyle Hidden -Wait -PassThru
$process.ExitCode
```

Expected: exit code `0` and seven non-empty PNGs.

- [ ] **Step 5: Inspect visual acceptance**

Open the seven PNGs and verify:

- front exterior has no rectangular holes or transparent closure regions;
- rear exterior has no socket or arm-tunnel breakthroughs;
- front males remain outside the display PCB and post envelopes;
- rear arms have visible activity gaps and rooted anchors;
- hook cutaway shows the 35° entry face and 20° release face;
- the USB rear opening remains rounded and unobstructed.
- the 12.0 mm × 11.5 mm buzzer envelope is unobstructed and remains fully
  internal without a sound hole.

- [ ] **Step 6: Rerun all tests and whitespace checks**

Run:

```powershell
python -m pytest enclosure/tests -q
git diff --check
```

Expected: all tests PASS and `git diff --check` reports no errors.

- [ ] **Step 7: Confirm repository state**

Run:

```powershell
git status --short --branch
git log -4 --oneline
```

Expected: source and tests are committed; only ignored generated FCStd, STEP,
STL and PNG files exist in `enclosure/outputs`.
