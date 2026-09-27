import json
import shutil
import subprocess
from pathlib import Path


HANDOFF = Path(__file__).parents[1]
BUILD_SCRIPT = HANDOFF / "cad" / "build_blossom_enclosure.py"
AUDIT_SCRIPT = HANDOFF / "cad" / "audit_blossom_enclosure.py"
RETROFIT = HANDOFF / "outputs" / "four-latch-retrofit" / "blossom-enclosure.FCStd"
BASELINE = HANDOFF / "outputs" / "blossom-enclosure.FCStd"
RETROFIT_OUTPUT_DIR = RETROFIT.parent
FREECAD_PYTHON = Path(r"C:\Program Files\FreeCAD 1.1\bin\python.exe")
# Complex B-spline comparisons can exceed 30 seconds after a cold FreeCAD start.
FREECAD_TIMEOUT_SECONDS = 30
ORIGINAL_SVG = HANDOFF.parent / "enclosure_handoff_2026-07-28" / "openai-blossom.svg"
PRINT_CLEAN_SVG = HANDOFF / "cad" / "openai-blossom-print-clean.svg"
SVG_BOUNDS_TOLERANCE_MM = 0.001
# The only permitted area change is the removed 0.003-source-unit closure sliver.
SVG_AREA_TOLERANCE_MM2 = 0.0011


def run_freecad(*args: str) -> subprocess.CompletedProcess[str]:
    result = run_freecad_result(*args)
    assert result.returncode == 0, result.stdout + result.stderr
    return result


def run_freecad_result(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(FREECAD_PYTHON), *args],
        cwd=HANDOFF.parents[2],
        capture_output=True,
        text=True,
        timeout=FREECAD_TIMEOUT_SECONDS,
        check=False,
    )


def copy_retrofit(name: str) -> Path:
    copied = RETROFIT_OUTPUT_DIR / f"{name}.FCStd"
    remove_tampered_copy(copied)
    shutil.copy2(RETROFIT, copied)
    return copied


def remove_tampered_copy(document_path: Path) -> None:
    document_path.unlink(missing_ok=True)
    for backup in document_path.parent.glob(f"{document_path.stem}.*.FCBak"):
        backup.unlink(missing_ok=True)


def mutate_document(document_path: Path, statements: str) -> None:
    mutation = f'''
import FreeCAD as App
import Part

document = App.openDocument(r"{document_path}")
{statements}
document.recompute()
document.save()
'''
    run_freecad("-c", mutation)


def audit_copy(document_path: Path) -> dict[str, object]:
    probe = f'''
import json
import sys
from pathlib import Path

handoff = Path(r"{HANDOFF}")
sys.path.insert(0, str(handoff / "cad"))
import audit_blossom_enclosure as audit

print(json.dumps(audit.audit_document(r"{document_path}", r"{BASELINE}"), sort_keys=True))
'''
    return json.loads(run_freecad("-c", probe).stdout)


def test_print_clean_svg_keeps_approved_recess_geometry_printable():
    probe = f'''
import importlib.util
import json
import sys
from pathlib import Path

import FreeCAD as App
import Part
import importSVG

handoff = Path(r"{HANDOFF}")
cad = handoff / "cad"
sys.path.insert(0, str(cad))
spec = importlib.util.spec_from_file_location("blossom_build", cad / "build_blossom_enclosure.py")
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)

def bounds(shape):
    box = shape.BoundBox
    return [box.XMin, box.XMax, box.YMin, box.YMax, box.ZMin, box.ZMax]

def source_facts(path):
    imported = importSVG.open(str(path))
    try:
        shapes = [item.Shape.copy() for item in imported.Objects if hasattr(item, "Shape") and not item.Shape.isNull()]
        outer, details = build.split_blossom_faces(shapes)
        outer_wire = max(outer.Wires, key=lambda item: item.BoundBox.XLength * item.BoundBox.YLength)
        scale = build.DEFAULTS.blossom_target_width_mm / outer_wire.BoundBox.XLength
        facts = []
        for detail in details:
            scaled = build.transform_shape_relative(detail, outer_wire, scale, 0.0)
            wire = max(scaled.Wires, key=lambda item: Part.Face(item).Area)
            facts.append({{
                "bounds": bounds(scaled),
                "area": Part.Face(wire).Area,
                "minimum_edge": min(edge.Length for edge in wire.Edges),
            }})
        return facts
    finally:
        App.closeDocument(imported.Name)

original = source_facts(Path(r"{ORIGINAL_SVG}"))
clean = source_facts(Path(r"{PRINT_CLEAN_SVG}"))
cutters = []
outer_wire, details, scale = build.source_geometry()
for surface_z, inward_sign in ((0.0, 1.0), (build.DEFAULTS.maximum_thickness_mm, -1.0)):
    for detail in details:
        scaled = build.transform_shape_relative(detail, outer_wire, scale, surface_z)
        cutter, radius = build.rounded_recess_cutter(
            scaled,
            surface_z,
            inward_sign,
            build.DEFAULTS.relief_depth_mm,
            build.DEFAULTS.relief_radius_fallbacks_mm,
        )
        cutters.append({{
            "valid": cutter.isValid(),
            "solids": len(cutter.Solids),
            "radius": radius,
            "z_length": cutter.BoundBox.ZLength,
            "minimum_face": min(face.Area for face in cutter.Faces),
            "minimum_edge": min(edge.Length for edge in cutter.Edges),
        }})
print(json.dumps({{"original": original, "clean": clean, "cutters": cutters}}, sort_keys=True))
'''
    result = json.loads(run_freecad("-c", probe).stdout)

    assert len(result["original"]) == len(result["clean"]) == 7
    for before, after in zip(result["original"], result["clean"]):
        assert max(abs(a - b) for a, b in zip(before["bounds"], after["bounds"])) <= SVG_BOUNDS_TOLERANCE_MM
        assert abs(before["area"] - after["area"]) <= SVG_AREA_TOLERANCE_MM2
        assert after["minimum_edge"] >= 0.01

    assert len(result["cutters"]) == 14
    for cutter in result["cutters"]:
        assert cutter["valid"] is True
        assert cutter["solids"] == 1
        assert cutter["radius"] == 0.6
        # OCCT can expand this historical loft cutter slightly during the
        # coplanar clip; the final shell depth is audited after subtraction.
        assert 1.5 <= cutter["z_length"] <= 1.61
        assert cutter["minimum_face"] >= 0.01
        assert cutter["minimum_edge"] >= 0.01


def test_visible_exterior_surfaces_are_stable_and_detect_unhidden_root():
    run_freecad(str(BUILD_SCRIPT))
    reports = {}
    cases = (
        ("front", -0.10, 1.60, -1.0, "FrontShell"),
        ("rear", 19.00, 20.70, 1.0, "RearCover"),
    )
    for label, z_min, z_max, direction, body_name in cases:
        extra = ""
        if label == "front":
            extra = '''
unhidden_root = retrofit.getObject("FrontUpperRootLeft").Shape.copy()
unhidden_root.translate(App.Vector(0.0, 0.0, -0.90))
unhidden_front = retrofit_body.fuse(unhidden_root)
result["unhidden_root_delta"] = visible_surface_delta(
    retrofit_body, unhidden_front, z_min, z_max, direction
)
result["upper_root_z_min"] = {
    name: retrofit.getObject(name).Shape.BoundBox.ZMin
    for name in ("FrontUpperRootLeft", "FrontUpperRootRight")
}
'''
        else:
            extra = '''
usb_straddling_panel = Part.makeBox(
    8.0, 2.0, 0.05, App.Vector(2.0, -23.0, 20.60)
)
tampered_rear = retrofit_body.fuse(usb_straddling_panel).removeSplitter()
result["usb_mask_straddling_delta"] = visible_surface_delta(
    retrofit_body, tampered_rear, z_min, z_max, direction, comparison_mask
)
result["panel_outside_usb_mask_mm3"] = usb_straddling_panel.cut(
    comparison_mask
).Volume
'''
        probe = f'''
import json
import sys
from pathlib import Path

import FreeCAD as App
import Part

handoff = Path(r"{HANDOFF}")
sys.path.insert(0, str(handoff / "cad"))
import audit_blossom_enclosure as audit

visible_exterior = audit.visible_exterior
visible_surface_delta = audit.visible_surface_delta
visible_surface_difference = audit.visible_surface_difference

retrofit = App.openDocument(r"{RETROFIT}")
baseline_one = App.openDocument(r"{BASELINE}")
baseline_two = App.openDocument(r"{BASELINE}")
label = "{label}"
z_min = {z_min!r}
z_max = {z_max!r}
direction = {direction!r}
body_name = "{body_name}"
retrofit_body = retrofit.getObject(body_name).Shape
baseline_one_body = baseline_one.getObject(body_name).Shape
baseline_two_body = baseline_two.getObject(body_name).Shape
comparison_mask = None
if label == "rear":
    comparison_mask = retrofit.getObject("UsbWindow").Shape.fuse(
        baseline_one.getObject("UsbWindow").Shape
    ).removeSplitter()

result = {{
    "retrofit": visible_exterior(
        retrofit_body, z_min, z_max, direction, comparison_mask
    ),
    "baseline": visible_exterior(
        baseline_one_body, z_min, z_max, direction, comparison_mask
    ),
    "baseline_self_delta": visible_surface_delta(
        baseline_one_body,
        baseline_two_body,
        z_min,
        z_max,
        direction,
        comparison_mask,
    ),
    "retrofit_delta": visible_surface_delta(
        retrofit_body,
        baseline_one_body,
        z_min,
        z_max,
        direction,
        comparison_mask,
    ),
    "retrofit_difference": visible_surface_difference(
        retrofit_body,
        baseline_one_body,
        z_min,
        z_max,
        direction,
        comparison_mask,
    ),
}}
{extra}

print(json.dumps(result, sort_keys=True))
'''
        reports[label] = json.loads(run_freecad("-c", probe).stdout)

    for label, _, z_max, _, _ in cases:
        for body in ("baseline", "retrofit"):
            facts = reports[label][body]
            assert facts["z_max"] <= z_max + 0.01
            assert facts["face_count"] > 0
        assert reports[label]["baseline_self_delta"] <= 1e-5
        assert reports[label]["retrofit_delta"] <= 0.50
        assert reports[label]["retrofit_difference"]["max_boundary_delta_mm"] <= 0.001
    assert reports["front"]["unhidden_root_delta"] > 1e-5
    assert all(
        z_min >= 1.60 - 1e-6
        for z_min in reports["front"]["upper_root_z_min"].values()
    )
    assert reports["rear"]["panel_outside_usb_mask_mm3"] > 1e-5
    assert reports["rear"]["usb_mask_straddling_delta"] > 1e-5


def test_pose_keepouts_and_rear_screen_stop_validity_are_audited():
    run_freecad(str(BUILD_SCRIPT))
    tampered = copy_retrofit("audit-pose-tampered")
    try:
        mutate_document(
            tampered,
            '''\
pose = document.getObject("AssemblyFrontLocked")
pose.Shape = pose.Shape.fuse(document.getObject("ScreenFaceEnvelope").Shape)
document.getObject("RearScreenEdgeStop3").Shape = Part.Shape()''',
        )

        report = audit_copy(tampered)
        for pose in ("tilted", "flat_unlocked", "locked"):
            for keepout in ("screen", "usb", "buzzer"):
                assert f"{pose}_{keepout}_keepout_clear" in report["checks"]
        assert report["checks"].get("locked_screen_keepout_clear") is False
        assert report["checks"].get("rear_screen_supports") is False
    finally:
        remove_tampered_copy(tampered)


def test_thickness_delta_is_signed_and_permits_a_thinner_retrofit():
    run_freecad(str(BUILD_SCRIPT))
    tampered = copy_retrofit("audit-thickness-tampered")
    try:
        mutate_document(
            tampered,
            '''\
rear = document.getObject("RearCover")
shifted = rear.Shape.copy()
shifted.translate(App.Vector(0.0, 0.0, -1.0))
rear.Shape = shifted''',
        )

        report = audit_copy(tampered)
        assert report["overall_thickness_delta_mm"] < -0.50
        assert report["checks"]["overall_thickness"] is True
    finally:
        remove_tampered_copy(tampered)


def test_printability_gates_require_closed_shells_and_safe_internal_features():
    run_freecad(str(BUILD_SCRIPT))
    report = audit_copy(RETROFIT)

    assert report["checks"].get("front_printable_closed_solid") is True
    assert report["checks"].get("rear_printable_closed_solid") is True
    assert report["checks"].get("no_free_solids") is True
    assert report["minimum_latch_root_mm"] >= 1.30
    assert report["minimum_guide_wall_mm"] >= 1.30
    assert report["checks"].get("latch_roots") is True
    assert report["checks"].get("guide_walls") is True
    assert min(report["known_thin_feature_minimums_mm"].values()) >= 0.80
    assert report["checks"].get("known_thin_features") is True


def test_step_import_pairs_each_exported_shell_once():
    run_freecad(str(BUILD_SCRIPT))
    probe = f'''
import json
import sys
from pathlib import Path

import FreeCAD as App

handoff = Path(r"{HANDOFF}")
sys.path.insert(0, str(handoff / "cad"))
import audit_blossom_enclosure as audit

retrofit = App.openDocument(r"{RETROFIT}")
try:
    expected = {{
        "front": retrofit.getObject("FrontShell").Shape,
        "rear": retrofit.getObject("RearCover").Shape,
    }}
    shells = audit._step_shells(
        handoff / "outputs" / "four-latch-retrofit" / "blossom-enclosure.step",
        expected,
        App,
    )
    print(json.dumps(sorted(shells)))
finally:
    App.closeDocument(retrofit.Name)
'''
    result = run_freecad("-c", probe)
    assert json.loads(result.stdout) == ["front", "rear"]


def test_exported_stls_are_mm_print_meshes_matching_fcstd_and_step():
    run_freecad(str(BUILD_SCRIPT))
    report = audit_copy(RETROFIT)

    for shell in ("front", "rear"):
        for check in (
            f"{shell}_stl_matches_fcstd_bounds",
            f"{shell}_stl_matches_step_bounds",
            f"{shell}_stl_watertight",
            f"{shell}_stl_two_manifold",
            f"{shell}_stl_no_self_intersections",
            f"{shell}_stl_no_degenerate_triangles",
            f"{shell}_stl_single_shell",
            f"{shell}_stl_consistent_normals",
            f"{shell}_stl_positive_oriented_volume",
            f"{shell}_gmsh_check_passed",
        ):
            assert report["checks"].get(check) is True

        mesh = report["stl_meshes"][shell]
        assert mesh["unit"] == "mm"
        assert mesh["component_count"] == 1
        assert mesh["self_intersection_count"] == 0
        assert mesh["degenerate_triangle_count"] == 0
        assert mesh["positive_oriented_volume_mm3"] > 0.0
        assert mesh["gmsh_check_passed"] is True
        assert mesh["gmsh_check_has_warning"] is False
        assert mesh["fcstd_bounds_delta_mm"] <= 0.05
        assert mesh["step_bounds_delta_mm"] <= 0.05


def test_cli_writes_json_and_exits_nonzero_for_a_tampered_copy():
    run_freecad(str(BUILD_SCRIPT))
    passing_output = RETROFIT_OUTPUT_DIR / "audit-cli-pass.json"
    failing_output = RETROFIT_OUTPUT_DIR / "audit-cli-failure.json"
    tampered = copy_retrofit("audit-cli-tampered")
    mutate_document(
        tampered,
        'document.getObject("RearScreenEdgeStop3").Shape = Part.Shape()',
    )

    try:
        passing = run_freecad_result(
            str(AUDIT_SCRIPT),
            str(RETROFIT),
            str(BASELINE),
            str(passing_output),
        )
        assert passing.returncode == 0, passing.stdout + passing.stderr
        assert json.loads(passing_output.read_text("utf-8"))["passed"] is True

        failing = run_freecad_result(
            str(AUDIT_SCRIPT),
            str(tampered),
            str(BASELINE),
            str(failing_output),
        )
        assert failing.returncode != 0
        failure_report = json.loads(failing_output.read_text("utf-8"))
        assert failure_report["passed"] is False
        assert failure_report["checks"].get("rear_screen_supports") is False
    finally:
        passing_output.unlink(missing_ok=True)
        failing_output.unlink(missing_ok=True)
        remove_tampered_copy(tampered)
