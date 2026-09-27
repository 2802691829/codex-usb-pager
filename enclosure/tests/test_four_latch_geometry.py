import json
import subprocess
import sys
from pathlib import Path

import pytest


HANDOFF = Path(__file__).parents[1]
BUILD_SCRIPT = HANDOFF / "cad" / "build_blossom_enclosure.py"
DOCUMENT = HANDOFF / "outputs" / "four-latch-retrofit" / "blossom-enclosure.FCStd"
FREECAD_PYTHON = Path(r"C:\Program Files\FreeCAD 1.1\bin\python.exe")
FREECAD_TIMEOUT_SECONDS = 30
sys.path.insert(0, str(HANDOFF / "cad"))
from enclosure_params import DEFAULTS


def run_freecad(*args: str) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            [str(FREECAD_PYTHON), *args],
            cwd=HANDOFF.parents[2],
            capture_output=True,
            text=True,
            timeout=FREECAD_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        pytest.fail(
            f"FreeCAD child exceeded {FREECAD_TIMEOUT_SECONDS}s and was terminated: {exc.cmd}"
        )
    assert result.returncode == 0, result.stdout + result.stderr
    return result


@pytest.fixture(scope="module")
def geometry_report() -> dict[str, object]:
    run_freecad(str(BUILD_SCRIPT))
    probe = f'''
import json
import FreeCAD as App
import Part

document = App.openDocument(r"{DOCUMENT}")
front = document.getObject("FrontShell").Shape
rear = document.getObject("RearCover").Shape
cavity = document.getObject("ElectronicCavity").Shape
guard = document.getObject("RearClosureExteriorGuard").Shape

pose_names = (
    "AssemblyFrontTilted",
    "AssemblyFrontFlatUnlocked",
    "AssemblyFrontLocked",
)
socket_names = ("RearUpperSocketLeft", "RearUpperSocketRight")
tab_names = ("FrontUpperTabLeft", "FrontUpperTabRight")
lower_tab_names = ("FrontLowerTabLeft", "FrontLowerTabRight")
detent_names = ("RearLowerDetentLeft", "RearLowerDetentRight")
guide_names = ("RearLowerGuideLeft", "RearLowerGuideRight")

approved_upper = {{}}
APPROVED_UPPER_CENTRE_Y = 21.60
APPROVED_UPPER_WIDTH = 5.00
APPROVED_UPPER_THICKNESS = 1.00
APPROVED_UPPER_PROJECTION = 2.50
APPROVED_UPPER_CLEARANCE = 0.25
APPROVED_UPPER_BOTTOM_CLEARANCE = 0.30
APPROVED_UPPER_TAB_Z_MIN = 2.60
APPROVED_UPPER_ENVELOPE_Y_MIN = 17.95
APPROVED_UPPER_ENVELOPE_Z_MIN = 0.40
APPROVED_UPPER_ENVELOPE_Y_LENGTH = 4.50
APPROVED_UPPER_ENVELOPE_Z_LENGTH = 4.80
for side, centre_x in (("Left", -10.0), ("Right", 10.0)):
    tab = document.getObject("FrontUpperTab" + side).Shape
    root_object = document.getObject("FrontUpperRoot" + side)
    entry_object = document.getObject("RearUpperEntryFunnel" + side)
    blind_object = document.getObject("RearUpperBlindSocket" + side)
    socket = document.getObject("RearUpperSocket" + side).Shape
    blind = None if blind_object is None else blind_object.Shape
    approved_blind = Part.makeBox(
        APPROVED_UPPER_WIDTH + 2.0 * APPROVED_UPPER_CLEARANCE,
        APPROVED_UPPER_THICKNESS + 2.0 * APPROVED_UPPER_CLEARANCE,
        APPROVED_UPPER_PROJECTION + APPROVED_UPPER_BOTTOM_CLEARANCE,
        App.Vector(
            centre_x - APPROVED_UPPER_WIDTH / 2.0 - APPROVED_UPPER_CLEARANCE,
            APPROVED_UPPER_CENTRE_Y
            - APPROVED_UPPER_THICKNESS / 2.0
            - APPROVED_UPPER_CLEARANCE,
            APPROVED_UPPER_TAB_Z_MIN - APPROVED_UPPER_BOTTOM_CLEARANCE,
        ),
    )
    approved_envelope = Part.makeBox(
        APPROVED_UPPER_WIDTH + 2.0 * APPROVED_UPPER_CLEARANCE,
        APPROVED_UPPER_ENVELOPE_Y_LENGTH,
        APPROVED_UPPER_ENVELOPE_Z_LENGTH,
        App.Vector(
            centre_x - APPROVED_UPPER_WIDTH / 2.0 - APPROVED_UPPER_CLEARANCE,
            APPROVED_UPPER_ENVELOPE_Y_MIN,
            APPROVED_UPPER_ENVELOPE_Z_MIN,
        ),
    )
    side_sign = -1.0 if side == "Left" else 1.0
    side_wall = Part.makeBox(
        1.30,
        APPROVED_UPPER_THICKNESS + 2.0 * APPROVED_UPPER_CLEARANCE,
        APPROVED_UPPER_PROJECTION + APPROVED_UPPER_BOTTOM_CLEARANCE,
        App.Vector(
            centre_x - APPROVED_UPPER_WIDTH / 2.0
            - APPROVED_UPPER_CLEARANCE
            - 1.30
            if side_sign < 0.0
            else centre_x + APPROVED_UPPER_WIDTH / 2.0 + APPROVED_UPPER_CLEARANCE,
            APPROVED_UPPER_CENTRE_Y
            - APPROVED_UPPER_THICKNESS / 2.0
            - APPROVED_UPPER_CLEARANCE,
            APPROVED_UPPER_TAB_Z_MIN - APPROVED_UPPER_BOTTOM_CLEARANCE,
        ),
    )
    approved_upper[side] = {{
        "body_bounds_mm": [
            tab.BoundBox.XLength,
            tab.BoundBox.YLength,
            tab.BoundBox.ZLength,
        ],
        "body_centre_y_mm": 0.5 * (tab.BoundBox.YMin + tab.BoundBox.YMax),
        "body_volume_mm3": tab.Volume,
        "root_min_mm": 0.0 if root_object is None else min(
            root_object.Shape.BoundBox.YLength,
            root_object.Shape.BoundBox.ZLength,
        ),
        "entry_outside_envelope_mm3": 0.0 if entry_object is None else (
            entry_object.Shape.cut(approved_envelope).Volume
        ),
        "entry_volume_mm3": 0.0 if entry_object is None else entry_object.Shape.Volume,
        "socket_outside_envelope_mm3": socket.cut(approved_envelope).Volume,
        "socket_volume_mm3": socket.Volume,
        "blind_delta_mm3": 999.0 if blind is None else (
            blind.cut(approved_blind).Volume + approved_blind.cut(blind).Volume
        ),
        "side_wall_missing_mm3": side_wall.cut(rear).Volume,
    }}

upper_pose_overlap = {{}}
upper_tab_outside = {{}}
upper_pivot = App.Vector(
    0.0,
    document.getObject("RearClosureBlank").Shape.BoundBox.YMax,
    2.30,
)
upper_axis = App.Vector(1.0, 0.0, 0.0)
upper_keepout_names = (
    "RearScreenFacePocket",
    "RearScreenPcbEnvelope",
    "ScreenFaceEnvelope",
    "ScreenActiveEnvelope",
    "UsbWindow",
    "BuzzerEnvelope",
    "BuzzerServiceEnvelope",
)
for tab_name in tab_names:
    locked_tab = document.getObject(tab_name).Shape
    flat_tab = locked_tab.copy()
    flat_tab.translate(App.Vector(0.0, -2.50, 0.0))
    tilted_tab = flat_tab.copy()
    tilted_tab.rotate(upper_pivot, upper_axis, 12.0)
    upper_pose_overlap[tab_name] = {{
        "tilted_mm3": sum(
            tilted_tab.common(document.getObject(name).Shape).Volume
            for name in upper_keepout_names
        ),
        "flat_mm3": sum(
            flat_tab.common(document.getObject(name).Shape).Volume
            for name in upper_keepout_names
        ),
        "locked_mm3": sum(
            locked_tab.common(document.getObject(name).Shape).Volume
            for name in upper_keepout_names
        ),
    }}
    socket = document.getObject(
        "RearUpperSocketLeft" if tab_name.endswith("Left")
        else "RearUpperSocketRight"
    ).Shape
    upper_tab_outside[tab_name] = {{
        "tilted_mm3": tilted_tab.cut(socket).Volume,
        "flat_mm3": flat_tab.cut(socket).Volume,
        "locked_mm3": locked_tab.cut(socket).Volume,
    }}

expected_tilted_front = front.copy()
expected_tilted_front.translate(App.Vector(0.0, -2.50, 0.0))
expected_tilted_front.rotate(upper_pivot, upper_axis, 12.0)
actual_tilted_front = document.getObject("AssemblyFrontTilted").Shape
tilted_pose_delta = (
    expected_tilted_front.cut(actual_tilted_front).Volume
    + actual_tilted_front.cut(expected_tilted_front).Volume
)

detent_lock = {{}}
for tab_name, detent_name in zip(lower_tab_names, detent_names):
    tab = document.getObject(tab_name).Shape
    detent = document.getObject(detent_name).Shape
    detent_lock[detent_name] = {{
        "distance_mm": tab.distToShape(detent)[0],
        "common_mm3": tab.common(detent).Volume,
        "engagement_mm": tab.BoundBox.ZMax - detent.BoundBox.ZMin,
    }}

guide_wall = {{}}
for index, guide_name in enumerate(guide_names):
    guide = document.getObject(guide_name).Shape
    box = guide.BoundBox
    wall_x = box.XMin - 1.30 if index == 0 else box.XMax
    wall_probe = Part.makeBox(
        1.30,
        box.YLength,
        box.ZLength,
        App.Vector(wall_x, box.YMin, box.ZMin),
    )
    guide_wall[guide_name] = {{
        "probe_mm3": wall_probe.Volume,
        "missing_mm3": wall_probe.cut(rear).Volume,
    }}

lower_sections = {{}}
for side in ("Left", "Right"):
    tab = document.getObject("FrontLowerTab" + side).Shape
    root = document.getObject("FrontLowerRoot" + side)
    integrated_bearing = tab.common(front)
    lower_sections[side] = {{
        "integrated_bounds_mm": [
            integrated_bearing.BoundBox.XLength,
            integrated_bearing.BoundBox.YLength,
            integrated_bearing.BoundBox.ZLength,
        ],
        "integrated_volume_mm3": integrated_bearing.Volume,
        "root_min_mm": 0.0 if root is None else min(
            root.Shape.BoundBox.XLength,
            root.Shape.BoundBox.ZLength,
        ),
    }}

component_names = (
    "RearScreenFacePocket",
    "RearScreenPcbEnvelope",
    "ScreenFaceEnvelope",
    "ScreenActiveEnvelope",
    "UsbWindow",
    "UsbGuideLeft",
    "UsbGuideRight",
    "UsbForcePlate",
    "UsbForcePlateBridgeLeft",
    "UsbForcePlateBridgeRight",
    "BuzzerEnvelope",
    "BuzzerServiceEnvelope",
)
upper_root_names = ("FrontUpperRootLeft", "FrontUpperRootRight")
lower_root_names = ("FrontLowerRootLeft", "FrontLowerRootRight")
closure_part_names = (
    *tab_names,
    *upper_root_names,
    *lower_tab_names,
    *lower_root_names,
    *detent_names,
)
component_overlap = sum(
    document.getObject(part_name).Shape.common(
        document.getObject(component_name).Shape
    ).Volume
    for part_name in closure_part_names
    if document.getObject(part_name) is not None
    for component_name in component_names
)

cutter_names = (*socket_names, *guide_names)
exterior_breach = sum(
    document.getObject(cutter_name).Shape.common(guard_solid).Volume
    for cutter_name in cutter_names
    for guard_solid in guard.Solids
)

report = {{
    "front_valid": front.isValid(),
    "rear_valid": rear.isValid(),
    "front_solids": len(front.Solids),
    "rear_solids": len(rear.Solids),
    "pose_interference_mm3": {{
        pose_name: document.getObject(pose_name).Shape.common(rear).Volume
        for pose_name in pose_names
    }},
    "upper_tab_volume_mm3": {{
        tab_name: document.getObject(tab_name).Shape.Volume
        for tab_name in tab_names
    }},
    "approved_upper": approved_upper,
    "upper_pose_overlap_mm3": upper_pose_overlap,
    "upper_tab_outside_mm3": upper_tab_outside,
    "tilted_pose_delta_mm3": tilted_pose_delta,
    "detent_lock": detent_lock,
    "lower_cavity_overlap_mm3": {{
        part_name: document.getObject(part_name).Shape.common(cavity).Volume
        for part_name in (*lower_tab_names, *lower_root_names)
        if document.getObject(part_name) is not None
    }},
    "guide_wall": guide_wall,
    "lower_sections": lower_sections,
    "component_overlap_mm3": component_overlap,
    "exterior_breach_mm3": exterior_breach,
}}
print(json.dumps(report))
'''
    return json.loads(run_freecad("-c", probe).stdout)


def test_four_latch_geometry_contract(geometry_report):
    report = geometry_report
    failures = []

    if not report["front_valid"] or report["front_solids"] != 1:
        failures.append("FrontShell must be one valid solid")
    if not report["rear_valid"] or report["rear_solids"] != 1:
        failures.append(
            f"RearCover must be one valid solid, got {report['rear_solids']}"
        )

    for side, upper in report["approved_upper"].items():
        if any(abs(actual - expected) > 1e-5 for actual, expected in zip(
            upper["body_bounds_mm"], [5.0, 1.0, 2.5]
        )):
            failures.append(
                f"FrontUpperTab{side} bounds are {upper['body_bounds_mm']}"
            )
        if abs(
            upper["body_centre_y_mm"]
            - DEFAULTS.top_tongue_approved_y_exception_mm
        ) > 1e-5:
            failures.append(
                f"FrontUpperTab{side} centre Y is not the approved "
                "21.60 mm exception"
            )
        if not (10.0 < upper["body_volume_mm3"] < 12.5):
            failures.append(f"FrontUpperTab{side} lacks the 35 degree tip relief")
        if upper["root_min_mm"] < 1.30 - 1e-5:
            failures.append(f"FrontUpperRoot{side} is below 1.30 mm")
        if upper["entry_volume_mm3"] <= 0.0:
            failures.append(f"RearUpperEntryFunnel{side} is missing")
        if upper["entry_outside_envelope_mm3"] > 1e-5:
            failures.append(
                f"RearUpperEntryFunnel{side} leaves the approved envelope"
            )
        if upper["entry_volume_mm3"] > 85.0:
            failures.append(f"RearUpperEntryFunnel{side} exceeds 85 mm3")
        if upper["blind_delta_mm3"] > 1e-5:
            failures.append(f"RearUpperBlindSocket{side} differs from approval")
        if upper["socket_outside_envelope_mm3"] > 1e-5:
            failures.append(f"RearUpperSocket{side} leaves the approved envelope")
        if upper["socket_volume_mm3"] > 100.0:
            failures.append(f"RearUpperSocket{side} exceeds 100 mm3")
        if upper["side_wall_missing_mm3"] > 1e-5:
            failures.append(
                f"RearUpperBlindSocket{side} lacks its independent 1.20 mm side wall"
            )

    if report["tilted_pose_delta_mm3"] > 1e-5:
        failures.append(
            f"tilted pose transform delta is {report['tilted_pose_delta_mm3']:.6f} mm3"
        )

    for tab_name, overlaps in report["upper_pose_overlap_mm3"].items():
        for pose_name, overlap in overlaps.items():
            if overlap > 1e-5:
                failures.append(
                    f"{tab_name} {pose_name} component overlap is "
                    f"{overlap:.6f} mm3"
                )

    for tab_name, outside_by_pose in report["upper_tab_outside_mm3"].items():
        for pose_name, outside_volume in outside_by_pose.items():
            if outside_volume > 1e-5:
                failures.append(
                    f"{tab_name} {pose_name} leaves its receiver by "
                    f"{outside_volume:.6f} mm3"
                )

    for side, section in report["lower_sections"].items():
        if any(
            abs(actual - expected) > 1e-5
            for actual, expected in zip(
                section["integrated_bounds_mm"], [4.0, 2.2, 1.2]
            )
        ):
            failures.append(
                f"FrontLowerTab{side} integrated bounds are "
                f"{section['integrated_bounds_mm']}"
            )
        if abs(section["integrated_volume_mm3"] - 10.56) > 0.01:
            failures.append(f"FrontLowerTab{side} is not fully integrated")
        if section["root_min_mm"] < 1.30 - 1e-5:
            failures.append(f"FrontLowerRoot{side} is below 1.30 mm")

    for detent_name, lock in report["detent_lock"].items():
        if lock["distance_mm"] > 1e-5:
            failures.append(
                f"{detent_name} has {lock['distance_mm']:.6f} mm lock gap"
            )
        if lock["common_mm3"] > 1e-5:
            failures.append(f"{detent_name} positively interferes with its tab")
        if abs(lock["engagement_mm"] - 0.25) > 0.01:
            failures.append(
                f"{detent_name} engagement is {lock['engagement_mm']:.6f} mm"
            )

    for tab_name, overlap in report["lower_cavity_overlap_mm3"].items():
        if overlap > 1e-5:
            failures.append(f"{tab_name} enters ElectronicCavity by {overlap:.6f} mm3")

    for guide_name, wall in report["guide_wall"].items():
        if wall["missing_mm3"] > 1e-5:
            failures.append(
                f"{guide_name} lacks a complete 1.30 mm local wall by "
                f"{wall['missing_mm3']:.6f} mm3"
            )

    if max(report["pose_interference_mm3"].values()) > 1e-5:
        failures.append(f"assembly pose interference: {report['pose_interference_mm3']}")
    if report["component_overlap_mm3"] > 1e-5:
        failures.append(
            f"closure/component overlap: {report['component_overlap_mm3']:.6f} mm3"
        )
    if report["exterior_breach_mm3"] > 1e-5:
        failures.append(
            f"closure/exterior breach: {report['exterior_breach_mm3']:.6f} mm3"
        )

    assert not failures, "\n" + "\n".join(failures)
