# Buzzer Service Cavity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the buzzer-matched rear relief with a large, non-cylindrical left-petal service cavity while preserving the complete visible enclosure and all closure features.

**Architecture:** Keep the cylindrical 12.0 x 11.5 mm buzzer object only as an assembly-validation envelope. Build a separate rounded rectangular service window, clip it to a 1.50 mm protected Blossom core, subtract only its new volume outside the existing electronics cavity, and audit the resulting exterior wall, keepouts, and assembly. Update the review renderer so the enlarged service volume is directly visible beside the buzzer envelope.

**Tech Stack:** Python 3, FreeCAD 1.1 Part workbench, pytest, PowerShell.

## Global Constraints

- Blossom exterior width remains 56.0 mm with unchanged SVG proportions.
- Front and rear relief depth remains 1.5 mm.
- Buzzer validation envelope remains 12.0 mm diameter x 11.5 mm high at centre (-9.0, 4.36) mm.
- Service window bounds are X = -28.0 to -12.0 mm, Y = -5.5 to 18.0 mm, and Z = 4.30 to 18.30 mm.
- Service window corner radius is 3.0 mm.
- The service cavity keeps at least 1.50 mm of protected exterior wall.
- Top locator tongues/sockets, lower hidden latches, screen mounts, USB structures, and exterior appearance remain unchanged.
- No buzzer sound opening is added.

---

### Task 1: Define the service-cavity datum contract

**Files:**
- Modify: `codex_usb_pager/enclosure/cad/enclosure_params.py`
- Create: `codex_usb_pager/enclosure/tests/test_buzzer_service_cavity_contract.py`

**Interfaces:**
- Consumes: `EnclosureParameters`, the approved screen PCB rear plane, and the existing internal envelope.
- Produces: `buzzer_service_window_mm`, `buzzer_service_window_origin_mm`, `buzzer_service_corner_radius_mm`, `buzzer_service_wall_mm`, `buzzer_front_z_mm`, and `buzzer_service_depth_mm`.

- [ ] **Step 1: Write the failing parameter tests**

```python
from pathlib import Path

from enclosure.cad.enclosure_params import DEFAULTS


BUILD = Path("enclosure/cad/build_blossom_enclosure.py").read_text(
    encoding="utf-8"
)


def test_large_buzzer_service_window_has_approved_datums():
    assert DEFAULTS.buzzer_service_window_mm == (16.0, 23.5)
    assert DEFAULTS.buzzer_service_window_origin_mm == (-28.0, -5.5)
    assert DEFAULTS.buzzer_service_corner_radius_mm == 3.0
    assert DEFAULTS.buzzer_service_wall_mm == 1.50
    assert DEFAULTS.buzzer_front_z_mm == 4.30
    assert DEFAULTS.buzzer_service_depth_mm == 14.0


def test_buzzer_validation_envelope_remains_measured_hardware():
    assert DEFAULTS.buzzer_clearance_mm == (12.0, 11.5)
    assert DEFAULTS.buzzer_centre_mm == (-9.0, 4.36)
```

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```powershell
python -m pytest enclosure/tests/test_buzzer_service_cavity_contract.py -q
```

Expected: FAIL because the `buzzer_service_*` parameters and derived properties do not exist.

- [ ] **Step 3: Add the exact parameters and derived properties**

Add these fields beside the existing buzzer dimensions:

```python
    buzzer_service_window_mm: tuple[float, float] = (16.0, 23.5)
    buzzer_service_window_origin_mm: tuple[float, float] = (-28.0, -5.5)
    buzzer_service_corner_radius_mm: float = 3.0
    buzzer_service_wall_mm: float = 1.50
```

Add these properties to `EnclosureParameters`:

```python
    @property
    def buzzer_front_z_mm(self) -> float:
        return round(
            self.front_seam_z_mm + self.screen_face_to_pcb_mm,
            2,
        )

    @property
    def buzzer_service_depth_mm(self) -> float:
        rear_inner_z = (
            self.front_seam_z_mm + self.internal_envelope_mm[2]
        )
        return round(rear_inner_z - self.buzzer_front_z_mm, 2)
```

- [ ] **Step 4: Run the focused test and the full pure-Python suite**

Run:

```powershell
python -m pytest enclosure/tests/test_buzzer_service_cavity_contract.py -q
python -m pytest enclosure/tests -q
```

Expected: the focused tests PASS and the existing suite remains green.

- [ ] **Step 5: Commit the datum contract**

```powershell
git add codex_usb_pager/enclosure/cad/enclosure_params.py codex_usb_pager/enclosure/tests/test_buzzer_service_cavity_contract.py
git commit -m "feat: define enlarged buzzer service cavity"
```

---

### Task 2: Build and audit the protected left-petal cavity

**Files:**
- Modify: `codex_usb_pager/enclosure/tests/test_buzzer_service_cavity_contract.py`
- Modify: `codex_usb_pager/enclosure/cad/build_blossom_enclosure.py`
- Modify: `codex_usb_pager/enclosure/cad/audit_blossom_enclosure.py`
- Modify: `codex_usb_pager/enclosure/tests/test_audit_contract.py`
- Modify: `codex_usb_pager/enclosure/tests/freecad_latch_geometry_contract.py`

**Interfaces:**
- Consumes: the Task 1 service window parameters and `rounded_rectangle_prism()`.
- Produces: FreeCAD objects `BuzzerServiceWindow`, `BuzzerServiceEnvelope`, `BuzzerServiceCavity`, and `BuzzerServiceExteriorGuard`; serialisable audit fields for size, depth, breach, and keepout intersections.

- [ ] **Step 1: Extend the source contract with the desired non-cylindrical build**

Append:

```python
def test_build_uses_a_protected_non_cylindrical_service_cavity():
    for name in (
        '"BuzzerServiceWindow"',
        '"BuzzerServiceEnvelope"',
        '"BuzzerServiceCavity"',
        '"BuzzerServiceExteriorGuard"',
    ):
        assert name in BUILD
    assert "buzzer_service_window.common(buzzer_service_core)" in BUILD
    assert "buzzer_service_envelope.cut(cavity)" in BUILD
    assert "rear_body = rear_body.cut(buzzer_service_cavity)" in BUILD
    assert "buzzer_clearance = buzzer_envelope.cut(cavity)" not in BUILD
```

- [ ] **Step 2: Run the source contract and verify RED**

Run:

```powershell
python -m pytest enclosure/tests/test_buzzer_service_cavity_contract.py -q
```

Expected: FAIL because no service-cavity objects or clipped cutter exist.

- [ ] **Step 3: Build the window, protected core, and physical cavity**

Replace the cylindrical `buzzer_clearance` production cutter with:

```python
    buzzer_front_z = DEFAULTS.buzzer_front_z_mm
    buzzer_envelope = Part.makeCylinder(
        DEFAULTS.buzzer_clearance_mm[0] / 2.0,
        DEFAULTS.buzzer_clearance_mm[1],
        App.Vector(
            DEFAULTS.buzzer_centre_mm[0],
            DEFAULTS.buzzer_centre_mm[1],
            buzzer_front_z,
        ),
    )
    service_x, service_y = DEFAULTS.buzzer_service_window_origin_mm
    service_width, service_height = DEFAULTS.buzzer_service_window_mm
    buzzer_service_window = rounded_rectangle_prism(
        service_width,
        service_height,
        DEFAULTS.buzzer_service_corner_radius_mm,
        DEFAULTS.buzzer_service_depth_mm,
        App.Vector(service_x, service_y, buzzer_front_z),
    )
    service_guard_ratio = (
        DEFAULTS.blossom_target_width_mm
        - 2.0 * DEFAULTS.buzzer_service_wall_mm
    ) / DEFAULTS.blossom_target_width_mm
    buzzer_service_core = Part.makeLoft(
        [
            wire_profile(
                outer_wire,
                svg_scale * service_guard_ratio,
                DEFAULTS.front_seam_z_mm - 0.1,
            ),
            wire_profile(
                outer_wire,
                svg_scale * service_guard_ratio,
                DEFAULTS.front_seam_z_mm
                + DEFAULTS.internal_envelope_mm[2],
            ),
            wire_profile(
                outer_wire,
                svg_scale * 0.965 * service_guard_ratio,
                DEFAULTS.maximum_thickness_mm
                - DEFAULTS.buzzer_service_wall_mm,
            ),
        ],
        True,
        True,
    )
    buzzer_service_envelope = (
        buzzer_service_window.common(buzzer_service_core)
    )
    buzzer_service_cavity = buzzer_service_envelope.cut(cavity)
    buzzer_service_exterior_guard = rear_body.cut(buzzer_service_core)
    service_guard_overlap = buzzer_service_cavity.common(
        buzzer_service_exterior_guard
    ).Volume
    if service_guard_overlap > 1e-5:
        raise RuntimeError(
            "Buzzer service cavity breaches its 1.50 mm guard by "
            f"{service_guard_overlap:.6f} mm^3"
        )
    rear_body = rear_body.cut(buzzer_service_cavity)
    add_feature(document, "BuzzerEnvelope", buzzer_envelope)
    add_feature(document, "BuzzerServiceWindow", buzzer_service_window)
    add_feature(document, "BuzzerServiceEnvelope", buzzer_service_envelope)
    add_feature(document, "BuzzerServiceCavity", buzzer_service_cavity)
    add_feature(
        document,
        "BuzzerServiceExteriorGuard",
        buzzer_service_exterior_guard,
    )
```

Add `buzzer_service_envelope` to `closure_keepouts`. Retain the circular
`BuzzerEnvelope` solely for obstruction checks and the small screen-retainer
manufacturing notch.

- [ ] **Step 4: Run the source contract and verify GREEN**

Run:

```powershell
python -m pytest enclosure/tests/test_buzzer_service_cavity_contract.py -q
```

Expected: PASS.

- [ ] **Step 5: Add failing audit-contract assertions**

Require these object names in `REQUIRED_CLOSURE` and
`test_audit_contract.py`:

```python
    "BuzzerServiceWindow",
    "BuzzerServiceEnvelope",
    "BuzzerServiceCavity",
    "BuzzerServiceExteriorGuard",
```

Require these report fields:

```python
    "buzzer_service_window_dimensions_mm",
    "buzzer_service_envelope_dimensions_mm",
    "buzzer_service_cavity_volume_mm3",
    "buzzer_service_exterior_breach_mm3",
    "buzzer_service_locator_obstruction_mm3",
    "buzzer_service_latch_obstruction_mm3",
```

Run:

```powershell
python -m pytest enclosure/tests/test_audit_contract.py -q
```

Expected: FAIL because the new object requirements and report fields are absent.

- [ ] **Step 6: Extend `audit_document()` with physical service-cavity facts**

Load the shapes:

```python
    buzzer_service_window = document.getObject(
        "BuzzerServiceWindow"
    ).Shape
    buzzer_service_envelope = document.getObject(
        "BuzzerServiceEnvelope"
    ).Shape
    buzzer_service_cavity = document.getObject(
        "BuzzerServiceCavity"
    ).Shape
    buzzer_service_exterior_guard = document.getObject(
        "BuzzerServiceExteriorGuard"
    ).Shape
```

Add:

```python
        "buzzer_service_window_dimensions_mm": [
            round(buzzer_service_window.BoundBox.XLength, 3),
            round(buzzer_service_window.BoundBox.YLength, 3),
            round(buzzer_service_window.BoundBox.ZLength, 3),
        ],
        "buzzer_service_envelope_dimensions_mm": [
            round(buzzer_service_envelope.BoundBox.XLength, 3),
            round(buzzer_service_envelope.BoundBox.YLength, 3),
            round(buzzer_service_envelope.BoundBox.ZLength, 3),
        ],
        "buzzer_service_cavity_volume_mm3": round(
            buzzer_service_cavity.Volume,
            6,
        ),
        "buzzer_service_exterior_breach_mm3": round(
            buzzer_service_cavity.common(
                buzzer_service_exterior_guard
            ).Volume,
            6,
        ),
        "buzzer_service_locator_obstruction_mm3": round(
            sum(
                buzzer_service_envelope.common(item).Volume
                for item in rear_sockets
            ),
            6,
        ),
        "buzzer_service_latch_obstruction_mm3": round(
            sum(
                buzzer_service_envelope.common(item).Volume
                for item in rear_arm_activity_envelopes
            ),
            6,
        ),
```

Replace the obsolete `BuzzerClearance` requirement and guard calculation with
the new service-cavity objects and field.

- [ ] **Step 7: Rebuild and inspect the audit once before hard-coding geometric thresholds**

Run from `codex_usb_pager`:

```powershell
"code=open(r'enclosure/cad/build_blossom_enclosure.py').read(); exec(compile(code, r'enclosure/cad/build_blossom_enclosure.py', 'exec'), {'__name__':'__main__','__file__':r'enclosure/cad/build_blossom_enclosure.py'})" | & 'C:\Program Files\FreeCAD 1.1\bin\FreeCADCmd.exe' -c

"import sys; sys.argv=[r'enclosure/cad/audit_blossom_enclosure.py', r'enclosure/outputs/blossom-enclosure.FCStd']; code=open(r'enclosure/cad/audit_blossom_enclosure.py').read(); exec(compile(code, r'enclosure/cad/audit_blossom_enclosure.py', 'exec'), {'__name__':'__main__','__file__':r'enclosure/cad/audit_blossom_enclosure.py'})" | & 'C:\Program Files\FreeCAD 1.1\bin\FreeCADCmd.exe' -c
```

Expected: build exit 0; service window `[16.0, 23.5, 14.0]`; service envelope
X and Y spans exceed 12.0 mm; service exterior breach, locator obstruction,
latch obstruction, USB obstruction, buzzer obstruction, screen obstruction,
and assembly interference are all `0.0`.

- [ ] **Step 8: Lock the actual geometry into the FreeCAD contract**

Add:

```python
    assert report["buzzer_service_window_dimensions_mm"] == [
        16.0,
        23.5,
        14.0,
    ]
    assert report["buzzer_service_envelope_dimensions_mm"][0] > 12.0
    assert report["buzzer_service_envelope_dimensions_mm"][1] > 12.0
    assert report["buzzer_service_envelope_dimensions_mm"][2] > 11.5
    assert report["buzzer_service_cavity_volume_mm3"] > 0.0
    for field in (
        "buzzer_service_exterior_breach_mm3",
        "buzzer_service_locator_obstruction_mm3",
        "buzzer_service_latch_obstruction_mm3",
    ):
        assert_close(report[field], 0.0)
```

Run:

```powershell
"import sys; sys.argv=[r'enclosure/tests/freecad_latch_geometry_contract.py', r'enclosure/outputs/blossom-enclosure.FCStd']; code=open(r'enclosure/tests/freecad_latch_geometry_contract.py').read(); exec(compile(code, r'enclosure/tests/freecad_latch_geometry_contract.py', 'exec'), {'__name__':'__main__','__file__':r'enclosure/tests/freecad_latch_geometry_contract.py'})" | & 'C:\Program Files\FreeCAD 1.1\bin\FreeCADCmd.exe' -c
```

Expected: `FREECAD LATCH CONTRACT PASS`.

- [ ] **Step 9: Run all tests and commit the geometry**

```powershell
python -m pytest enclosure/tests -q
git diff --check
git add enclosure/cad/build_blossom_enclosure.py enclosure/cad/audit_blossom_enclosure.py enclosure/tests/test_buzzer_service_cavity_contract.py enclosure/tests/test_audit_contract.py enclosure/tests/freecad_latch_geometry_contract.py
git commit -m "feat: enlarge buzzer service cavity"
```

Expected: all tests pass and the commit succeeds.

---

### Task 3: Render, verify, and package the enlarged cavity

**Files:**
- Modify: `codex_usb_pager/enclosure/tests/test_render_contract.py`
- Modify: `codex_usb_pager/enclosure/cad/render_blossom_review.py`
- Modify: `codex_usb_pager/enclosure/README.md`
- Regenerate: `codex_usb_pager/enclosure/outputs/blossom-enclosure.FCStd`
- Regenerate: `codex_usb_pager/enclosure/outputs/blossom-enclosure.step`
- Regenerate: `codex_usb_pager/enclosure/outputs/blossom-front.stl`
- Regenerate: `codex_usb_pager/enclosure/outputs/blossom-rear.stl`
- Regenerate: `codex_usb_pager/enclosure/outputs/review-*.png`
- Refresh: `codex_usb_pager/docs/enclosure_handoff_2026-07-29/`
- Refresh: `codex_usb_pager/docs/enclosure_handoff_2026-07-29.zip`

**Interfaces:**
- Consumes: `BuzzerEnvelope`, `BuzzerServiceEnvelope`, and `BuzzerServiceCavity`.
- Produces: seven verified 1600 x 1200 review images and a self-contained handoff archive.

- [ ] **Step 1: Write the failing renderer contract**

Update the renderer object expectations:

```python
def test_review_renderer_uses_service_cavity_objects():
    source = RENDER.read_text(encoding="utf-8")
    for name in (
        "BuzzerEnvelope",
        "BuzzerServiceEnvelope",
        "BuzzerServiceCavity",
    ):
        assert name in source
    assert '"BuzzerClearance"' not in source


def test_buzzer_review_compares_large_service_space_to_hardware():
    names, direction = _literal_views()["review-buzzer-clearance.png"]
    assert direction == "bottom"
    assert set(names) == {
        "ElectronicCavity",
        "BuzzerEnvelope",
        "BuzzerServiceEnvelope",
    }
```

- [ ] **Step 2: Run the renderer test and verify RED**

Run:

```powershell
python -m pytest enclosure/tests/test_render_contract.py -q
```

Expected: FAIL because the renderer still references `BuzzerClearance` and the
old clipped retainer-gap view.

- [ ] **Step 3: Update the review views and styles**

Use:

```python
    "review-buzzer-clearance.png": (
        (
            "ElectronicCavity",
            "BuzzerEnvelope",
            "BuzzerServiceEnvelope",
        ),
        "bottom",
    ),
```

Replace `BuzzerClearance` in the rear-inside and assembly-cutaway views with
`BuzzerServiceEnvelope` and `BuzzerServiceCavity`. Add:

```python
    "ElectronicCavity": ((0.58, 0.64, 0.70), 82),
    "BuzzerServiceEnvelope": ((0.15, 0.82, 0.48), 68),
    "BuzzerServiceCavity": ((0.96, 0.18, 0.16), 18),
```

Keep `BuzzerEnvelope` blue and translucent so its 12.0 mm hardware boundary is
visibly smaller than the new green service volume.

- [ ] **Step 4: Run the renderer contract and full pure suite**

Run:

```powershell
python -m pytest enclosure/tests/test_render_contract.py -q
python -m pytest enclosure/tests -q
```

Expected: all tests pass.

- [ ] **Step 5: Update the enclosure README**

State that the buzzer is checked with a 12.0 x 11.5 mm hardware envelope but
the physical left-petal service cavity uses the larger protected,
non-cylindrical Blossom-contour volume and has no exterior opening.

- [ ] **Step 6: Cold-build and render**

Run:

```powershell
"code=open(r'enclosure/cad/build_blossom_enclosure.py').read(); exec(compile(code, r'enclosure/cad/build_blossom_enclosure.py', 'exec'), {'__name__':'__main__','__file__':r'enclosure/cad/build_blossom_enclosure.py'})" | & 'C:\Program Files\FreeCAD 1.1\bin\FreeCADCmd.exe' -c

$macro = (Resolve-Path 'enclosure/cad/render_blossom_review.FCMacro').Path
$process = Start-Process -FilePath 'C:\Program Files\FreeCAD 1.1\bin\FreeCAD.exe' -ArgumentList $macro -WindowStyle Hidden -Wait -PassThru
$process.ExitCode
```

Expected: `BUILD PASS`, renderer exit `0`, and seven nonblank PNG files.

- [ ] **Step 7: Inspect the acceptance views**

Open:

- `enclosure/outputs/review-rear-inside.png`
- `enclosure/outputs/review-buzzer-clearance.png`
- `enclosure/outputs/review-assembly-cutaway.png`
- `enclosure/outputs/review-front-exterior.png`
- `enclosure/outputs/review-rear-exterior.png`

Confirm the large cavity visibly follows the safe left-petal volume, the blue
buzzer envelope is substantially smaller, the locator/latch regions remain
intact, and both exterior views are unchanged.

- [ ] **Step 8: Perform final verification**

Run:

```powershell
python -m pytest enclosure/tests -q
git diff --check
"import sys; sys.argv=[r'enclosure/tests/freecad_latch_geometry_contract.py', r'enclosure/outputs/blossom-enclosure.FCStd']; code=open(r'enclosure/tests/freecad_latch_geometry_contract.py').read(); exec(compile(code, r'enclosure/tests/freecad_latch_geometry_contract.py', 'exec'), {'__name__':'__main__','__file__':r'enclosure/tests/freecad_latch_geometry_contract.py'})" | & 'C:\Program Files\FreeCAD 1.1\bin\FreeCADCmd.exe' -c
```

Expected: all pytest tests pass, `git diff --check` is silent, and the FreeCAD
contract prints `PASS` with every interference and exterior-breach field at
`0.0`.

- [ ] **Step 9: Commit renderer and documentation**

```powershell
git add enclosure/cad/render_blossom_review.py enclosure/tests/test_render_contract.py enclosure/README.md
git commit -m "docs: review enlarged buzzer service cavity"
```

- [ ] **Step 10: Refresh and validate the stable handoff**

Copy the regenerated CAD exports, seven review images, updated CAD sources,
tests, specification, and plan into
`codex_usb_pager/docs/enclosure_handoff_2026-07-29/`. Recreate
`codex_usb_pager/docs/enclosure_handoff_2026-07-29.zip`, then confirm the zip
contains the FCStd, STEP, both STL files, and both buzzer review images with
nonzero sizes.
