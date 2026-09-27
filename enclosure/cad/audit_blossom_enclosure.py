"""FreeCAD audit for the immutable Blossom enclosure baseline and retrofit."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from enclosure_params import DEFAULTS


HANDOFF_DIR = SCRIPT_DIR.parent
RETROFIT_OUTPUT_DIR = HANDOFF_DIR / "outputs" / "four-latch-retrofit"
TOLERANCE_MM = 0.01
TOLERANCE_MM3 = 1e-5
STL_BOUNDS_TOLERANCE_MM = 0.05
GMSH_EXE = Path(sys.executable).with_name("gmsh.exe")
GMSH_CHECK_TIMEOUT_SECONDS = 30
FROZEN_SURFACE_REFERENCE_DEPTH_MM = 1.00
FROZEN_SURFACE_AREA_TOLERANCE_MM2 = 0.50
FROZEN_SURFACE_BOUNDARY_TOLERANCE_MM = 0.001

REQUIRED = {
    "front": ("FrontShell", "FrontHexCut", "BlossomRecessFront", "FrontView"),
    "rear": (
        "RearCover",
        "ElectronicCavity",
        "BlossomRecessRear",
        "UsbWindow",
        "UsbGuideLeft",
        "UsbGuideRight",
        "UsbForcePlate",
        "UsbForcePlateBridgeLeft",
        "UsbForcePlateBridgeRight",
        "BuzzerEnvelope",
    ),
}
REQUIRED_SCREEN_MOUNT = (
    "RearScreenSupport",
    "RearScreenFacePocket",
    "RearScreenPcbEnvelope",
    "RearScreenEdgeStop1",
    "RearScreenEdgeStop2",
    "RearScreenEdgeStop3",
    "RearScreenEdgeStop4",
    "ScreenFaceEnvelope",
    "ScreenActiveEnvelope",
)
REQUIRED_CLOSURE = (
    "FrontUpperTabLeft",
    "FrontUpperTabRight",
    "RearUpperSocketLeft",
    "RearUpperSocketRight",
    "FrontLowerTabLeft",
    "FrontLowerTabRight",
    "RearLowerGuideLeft",
    "RearLowerGuideRight",
    "RearLowerDetentLeft",
    "RearLowerDetentRight",
    "AssemblyFrontTilted",
    "AssemblyFrontFlatUnlocked",
    "AssemblyFrontLocked",
    "AssemblyPoseTilted",
    "AssemblyPoseFlatUnlocked",
    "AssemblyPoseLocked",
)
REAR_SCREEN_STOP_NAMES = tuple(f"RearScreenEdgeStop{index}" for index in range(1, 5))
KNOWN_THIN_FEATURE_NAMES = (
    *REAR_SCREEN_STOP_NAMES,
    "RearScreenStopBridge",
    "UsbForcePlateBridgeLeft",
    "UsbForcePlateBridgeRight",
    "UsbSupportAnchorLeft",
    "UsbSupportAnchorRight",
)
POSE_NAMES = {
    "tilted": "AssemblyFrontTilted",
    "flat_unlocked": "AssemblyFrontFlatUnlocked",
    "locked": "AssemblyFrontLocked",
}


def _missing_names(names: set[str], required: tuple[str, ...]) -> list[str]:
    return [name for name in required if name not in names]


def _shape(document, name: str):
    item = document.getObject(name)
    if item is None or item.Shape.isNull():
        raise ValueError(f"Required FreeCAD object is missing or empty: {name}")
    return item.Shape


def _shape_or_none(document, name: str):
    item = document.getObject(name)
    if item is None or item.Shape.isNull():
        return None
    return item.Shape


def _bounds(shape) -> list[float]:
    box = shape.BoundBox
    return [
        round(box.XMin, 6),
        round(box.XMax, 6),
        round(box.YMin, 6),
        round(box.YMax, 6),
        round(box.ZMin, 6),
        round(box.ZMax, 6),
    ]


def _max_bounds_delta(left, right) -> float:
    return max(abs(a - b) for a, b in zip(_bounds(left), _bounds(right)))


def _tessellated_bounds(shape, deflection: float = 0.05) -> list[float]:
    """Return physical surface bounds without B-spline control-pole overshoot."""
    points, _ = shape.tessellate(deflection)
    if not points:
        raise ValueError("Shape tessellation produced no surface points")
    return [
        min(point.x for point in points),
        max(point.x for point in points),
        min(point.y for point in points),
        max(point.y for point in points),
        min(point.z for point in points),
        max(point.z for point in points),
    ]


def _mesh_to_surface_bounds_delta(mesh, shape) -> float:
    return max(
        abs(mesh_bound - surface_bound)
        for mesh_bound, surface_bound in zip(_bounds(mesh), _tessellated_bounds(shape))
    )


def _visible_faces(shape, z_min: float, z_max: float, direction: float, mask=None):
    """Return exposed forward-facing faces wholly contained in a visible Z band.

    FreeCAD boolean intersections can expand a coplanar clipping face beyond its
    requested Z boundary. Inspecting actual shell faces avoids that result.
    """
    visible = []
    for face in shape.Faces:
        # Do not discard a whole visible face merely because it touches the
        # intentional USB movement zone. Cutting the face itself preserves every
        # fragment outside the mask for comparison.
        fragments = face.cut(mask).Faces if mask is not None and not mask.isNull() else (face,)
        for fragment in fragments:
            box = fragment.BoundBox
            if box.ZMin < z_min - TOLERANCE_MM or box.ZMax > z_max + TOLERANCE_MM:
                continue
            u_min, u_max, v_min, v_max = fragment.ParameterRange
            normal = fragment.normalAt((u_min + u_max) / 2.0, (v_min + v_max) / 2.0)
            if normal.Length <= TOLERANCE_MM3:
                continue
            normal.normalize()
            if normal.z * direction <= TOLERANCE_MM3:
                continue
            centre = fragment.CenterOfMass
            # A face with a forward normal can still be internal after a fuse.
            if shape.isInside(centre + normal * 0.02, TOLERANCE_MM3, True):
                continue
            visible.append(fragment)
    return visible


def _visible_face_records(shape, z_min: float, z_max: float, direction: float, mask=None):
    """Return deterministic descriptive records for visible shell faces."""
    records = []
    for fragment in _visible_faces(shape, z_min, z_max, direction, mask):
        box = fragment.BoundBox
        u_min, u_max, v_min, v_max = fragment.ParameterRange
        normal = fragment.normalAt((u_min + u_max) / 2.0, (v_min + v_max) / 2.0)
        normal.normalize()
        centre = fragment.CenterOfMass
        fingerprint = (
            round(fragment.Area, 6),
            *(_bounds(fragment)),
            round(centre.x, 6),
            round(centre.y, 6),
            round(centre.z, 6),
            round(normal.x, 6),
            round(normal.y, 6),
            round(normal.z, 6),
        )
        records.append(
            {
                "area_mm2": fragment.Area,
                "fingerprint": json.dumps(fingerprint, separators=(",", ":")),
                "z_min": box.ZMin,
                "z_max": box.ZMax,
            }
        )
    return records


def visible_exterior(shape, z_min: float, z_max: float, direction: float, mask=None):
    """Summarise forward visible shell faces without clipping the BRep."""
    records = _visible_face_records(shape, z_min, z_max, direction, mask)
    signatures = Counter(record["fingerprint"] for record in records)
    digest = hashlib.sha256(
        json.dumps(sorted(signatures.items()), separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "area_mm2": round(sum(record["area_mm2"] for record in records), 6),
        "face_count": len(records),
        "signature": digest,
        "z_min": round(min(record["z_min"] for record in records), 6)
        if records
        else None,
        "z_max": round(max(record["z_max"] for record in records), 6)
        if records
        else None,
    }


def visible_surface_delta(
    left,
    right,
    z_min: float,
    z_max: float,
    direction: float,
    mask=None,
) -> float:
    """Return topology-independent visible-area change in square millimetres."""
    left_faces = _visible_faces(left, z_min, z_max, direction, mask)
    right_faces = _visible_faces(right, z_min, z_max, direction, mask)
    return abs(
        sum(face.Area for face in left_faces)
        - sum(face.Area for face in right_faces)
    )


def visible_surface_difference(
    left,
    right,
    z_min: float,
    z_max: float,
    direction: float,
    mask=None,
) -> dict[str, float]:
    """Compare visible geometry without depending on OCC face segmentation."""
    import Part

    left_faces = _visible_faces(left, z_min, z_max, direction, mask)
    right_faces = _visible_faces(right, z_min, z_max, direction, mask)
    left_surface = Part.makeCompound(left_faces)
    right_surface = Part.makeCompound(right_faces)
    boundary_distances = [
        Part.Vertex(vertex.Point).distToShape(right_surface)[0]
        for face in left_faces
        for vertex in face.Vertexes
    ] + [
        Part.Vertex(vertex.Point).distToShape(left_surface)[0]
        for face in right_faces
        for vertex in face.Vertexes
    ]
    return {
        "area_delta_mm2": abs(
            sum(face.Area for face in left_faces)
            - sum(face.Area for face in right_faces)
        ),
        "max_boundary_delta_mm": max(boundary_distances, default=0.0),
    }


def _minimum_root_thickness(document, front) -> tuple[float, bool]:
    root_names = (
        "FrontUpperRootLeft",
        "FrontUpperRootRight",
        "FrontLowerRootLeft",
        "FrontLowerRootRight",
    )
    roots = [_shape(document, name) for name in root_names]
    thicknesses = [
        min(root.BoundBox.XLength, root.BoundBox.YLength, root.BoundBox.ZLength)
        for root in roots
    ]
    roots_fused = all(
        abs(front.common(root).Volume - root.Volume) <= TOLERANCE_MM3
        for root in roots
    )
    return min(thicknesses), roots_fused


def _minimum_guide_wall_thickness(document, rear, Part, App) -> tuple[float, dict[str, float]]:
    """Probe the actual rear solid beside each lower-guide cutter."""
    measurements: dict[str, float] = {}
    required_wall = 1.30
    for index, name in enumerate(("RearLowerGuideLeft", "RearLowerGuideRight")):
        guide = _shape(document, name)
        box = guide.BoundBox
        wall_x = box.XMin - required_wall if index == 0 else box.XMax
        probe = Part.makeBox(
            required_wall,
            box.YLength,
            box.ZLength,
            App.Vector(wall_x, box.YMin, box.ZMin),
        )
        missing_volume = probe.cut(rear).Volume
        # A full probe is direct evidence that the measured local wall is at
        # least 1.30 mm; a partial probe records the missing material as a fail.
        measurements[name] = round(
            required_wall
            if missing_volume <= TOLERANCE_MM3
            else max(0.0, required_wall * (1.0 - missing_volume / probe.Volume)),
            6,
        )
    return min(measurements.values()), measurements


def _screen_stop_status(document, rear) -> tuple[dict[str, dict[str, object]], bool]:
    """Verify every rear screen stop is printable and belongs to the rear solid."""
    status: dict[str, dict[str, object]] = {}
    for name in REAR_SCREEN_STOP_NAMES:
        item = document.getObject(name)
        shape = item.Shape if item is not None else None
        valid = (
            shape is not None
            and not shape.isNull()
            and shape.isValid()
            and shape.Volume > TOLERANCE_MM3
        )
        shared_volume = rear.common(shape).Volume if valid else 0.0
        distance = rear.distToShape(shape)[0] if valid else None
        fused_or_touching = valid and (
            shared_volume > TOLERANCE_MM3
            or distance is not None and distance <= TOLERANCE_MM3
        )
        status[name] = {
            "fused_or_touching": fused_or_touching,
            "present": item is not None,
            "shared_volume_mm3": round(shared_volume, 6),
            "valid": valid,
        }
    return status, all(
        facts["present"] and facts["valid"] and facts["fused_or_touching"]
        for facts in status.values()
    )


def _single_closed_solid(shape) -> bool:
    return (
        shape.isValid()
        and len(shape.Solids) == 1
        and shape.Solids[0].isClosed()
    )


def _minimum_screen_support_wall(document, Part, App) -> float:
    """Probe all four walls of the actual rear screen-support ring at 0.80 mm."""
    support = _shape(document, "RearScreenSupport")
    box = support.BoundBox
    required_wall = DEFAULTS.minimum_feature_mm
    span = 1.00
    probes = (
        Part.makeBox(
            required_wall,
            span,
            box.ZLength,
            App.Vector(box.XMin, box.Center.y - span / 2.0, box.ZMin),
        ),
        Part.makeBox(
            required_wall,
            span,
            box.ZLength,
            App.Vector(box.XMax - required_wall, box.Center.y - span / 2.0, box.ZMin),
        ),
        Part.makeBox(
            span,
            required_wall,
            box.ZLength,
            App.Vector(box.Center.x - span / 2.0, box.YMin, box.ZMin),
        ),
        Part.makeBox(
            span,
            required_wall,
            box.ZLength,
            App.Vector(box.Center.x - span / 2.0, box.YMax - required_wall, box.ZMin),
        ),
    )
    measurements = []
    for probe in probes:
        missing_volume = probe.cut(support).Volume
        measurements.append(
            required_wall
            if missing_volume <= TOLERANCE_MM3
            else max(0.0, required_wall * (1.0 - missing_volume / probe.Volume))
        )
    return min(measurements)


def _known_thin_feature_minimums(document, Part, App) -> dict[str, float]:
    measurements = {}
    for name in KNOWN_THIN_FEATURE_NAMES:
        shape = _shape_or_none(document, name)
        measurements[name] = (
            min(shape.BoundBox.XLength, shape.BoundBox.YLength, shape.BoundBox.ZLength)
            if shape is not None and shape.isValid()
            else 0.0
        )
    measurements["RearScreenSupportWall"] = _minimum_screen_support_wall(
        document,
        Part,
        App,
    )
    return {name: round(value, 6) for name, value in measurements.items()}


def _interference_volume(parts, keepouts) -> float:
    return sum(part.common(keepout).Volume for part in parts for keepout in keepouts)


def _relief_values(document, prefix: str) -> tuple[float, float, int]:
    item = document.getObject(prefix)
    return (
        item.ReliefDepth.Value,
        item.TransitionRadius.Value,
        int(item.WhiteBlockCount),
    )


def _overall_thickness(front, rear) -> float:
    return max(front.BoundBox.ZMax, rear.BoundBox.ZMax) - min(
        front.BoundBox.ZMin,
        rear.BoundBox.ZMin,
    )


def _step_shells(step_path: Path, expected_shells, App):
    """Load the exported STEP and pair its two solids to the FCStd shells."""
    import Import

    document = App.newDocument("BlossomStepAudit")
    try:
        Import.insert(str(step_path), document.Name)
        document.recompute()
        # FreeCAD exposes the STEP assembly container and its Part::Feature
        # children. Count only leaf features so parent solids are not repeated.
        solids = [
            solid
            for item in document.Objects
            if item.TypeId == "Part::Feature"
            if hasattr(item, "Shape") and not item.Shape.isNull()
            for solid in item.Shape.Solids
        ]
        if len(solids) != len(expected_shells):
            raise ValueError(
                "STEP must contain exactly the exported front and rear solids; "
                f"got {len(solids)}"
            )
        remaining = list(solids)
        paired = {}
        for name, expected in expected_shells.items():
            solid = min(remaining, key=lambda candidate: _max_bounds_delta(candidate, expected))
            remaining.remove(solid)
            paired[name] = solid.copy()
        return paired
    finally:
        App.closeDocument(document.Name)


def _signed_mesh_volume(mesh) -> float:
    volume = 0.0
    for facet in mesh.Facets:
        first, second, third = facet.Points
        volume += (
            first[0] * (second[1] * third[2] - second[2] * third[1])
            + first[1] * (second[2] * third[0] - second[0] * third[2])
            + first[2] * (second[0] * third[1] - second[1] * third[0])
        ) / 6.0
    return volume


def _gmsh_check(stl_path: Path) -> dict[str, object]:
    facts = {
        "gmsh_check_passed": False,
        "gmsh_check_has_warning": None,
        "gmsh_check_log": "",
    }
    if not GMSH_EXE.is_file():
        facts["gmsh_check_log"] = f"missing Gmsh: {GMSH_EXE}"
        return facts
    try:
        result = subprocess.run(
            [str(GMSH_EXE), str(stl_path), "-check", "-nopopup", "-v", "2"],
            cwd=str(stl_path.parent),
            capture_output=True,
            text=True,
            timeout=GMSH_CHECK_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        facts["gmsh_check_log"] = "Gmsh check exceeded 30 seconds"
        return facts
    log = f"{result.stdout}\n{result.stderr}".strip()
    facts["gmsh_check_log"] = log
    facts["gmsh_check_has_warning"] = any(
        line.lstrip().startswith("Warning") for line in log.splitlines()
    )
    facts["gmsh_check_passed"] = (
        result.returncode == 0
        and not facts["gmsh_check_has_warning"]
        and not any(line.lstrip().startswith("Error") for line in log.splitlines())
    )
    return facts


def _stl_mesh_facts(stl_path: Path, expected_shape, step_shape, Mesh):
    """Return topology and millimetre-bound evidence for one exported STL."""
    facts = {
        "path": str(stl_path),
        "unit": "unknown",
        "facet_count": 0,
        "component_count": 0,
        "watertight": False,
        "two_manifold": False,
        "self_intersection_count": None,
        "degenerate_triangle_count": None,
        "consistent_normals": False,
        "positive_oriented_volume_mm3": None,
        "fcstd_bounds_delta_mm": None,
        "step_bounds_delta_mm": None,
        "error": None,
    }
    if not stl_path.is_file():
        facts["error"] = "missing STL"
        return facts
    try:
        mesh = Mesh.Mesh(str(stl_path))
        has_self_intersections = mesh.hasSelfIntersections()
        facts.update(
            {
                "facet_count": mesh.CountFacets,
                "component_count": mesh.countComponents(),
                "watertight": mesh.isSolid(),
                "two_manifold": not mesh.hasNonManifolds()
                and not mesh.hasInvalidNeighbourhood(),
                "self_intersection_count": len(mesh.getSelfIntersections())
                if has_self_intersections
                else 0,
                "degenerate_triangle_count": sum(
                    facet.isDegenerated() or facet.Area <= TOLERANCE_MM3
                    for facet in mesh.Facets
                ),
                "consistent_normals": not mesh.hasNonUniformOrientedFacets(),
                "positive_oriented_volume_mm3": round(
                    _signed_mesh_volume(mesh),
                    6,
                ),
                "fcstd_bounds_delta_mm": round(
                    _mesh_to_surface_bounds_delta(mesh, expected_shape),
                    6,
                ),
                "step_bounds_delta_mm": round(
                    _mesh_to_surface_bounds_delta(mesh, step_shape),
                    6,
                ),
            }
        )
        facts["unit"] = (
            "mm"
            if facts["fcstd_bounds_delta_mm"] <= STL_BOUNDS_TOLERANCE_MM
            else "unknown"
        )
        facts.update(_gmsh_check(stl_path))
    except Exception as error:
        facts["error"] = str(error)
    return facts


def audit_document(document_path: str, baseline_path: str) -> dict[str, object]:
    """Compare a retrofit FCStd document to its immutable baseline FCStd."""
    import FreeCAD as App
    import Mesh
    import Part

    document = App.openDocument(str(Path(document_path)))
    baseline = App.openDocument(str(Path(baseline_path)))
    try:
        names = {item.Name for item in document.Objects}
        front = _shape(document, "FrontShell")
        rear = _shape(document, "RearCover")
        baseline_front = _shape(baseline, "FrontShell")
        baseline_rear = _shape(baseline, "RearCover")
        front_hex = _shape(document, "FrontHexCut")
        baseline_front_hex = _shape(baseline, "FrontHexCut")
        usb_window = _shape(document, "UsbWindow")
        baseline_usb_window = _shape(baseline, "UsbWindow")
        screen_face = _shape(document, "ScreenFaceEnvelope")
        artifact_dir = Path(document_path).resolve().parent
        step_shells = _step_shells(
            artifact_dir / "blossom-enclosure.step",
            {"front": front, "rear": rear},
            App,
        )
        stl_meshes = {
            "front": _stl_mesh_facts(
                artifact_dir / "blossom-front.stl",
                front,
                step_shells["front"],
                Mesh,
            ),
            "rear": _stl_mesh_facts(
                artifact_dir / "blossom-rear.stl",
                rear,
                step_shells["rear"],
                Mesh,
            ),
        }

        closure_parts = [
            _shape(document, name)
            for name in (
                "FrontUpperTabLeft",
                "FrontUpperTabRight",
                "FrontUpperRootLeft",
                "FrontUpperRootRight",
                "FrontLowerTabLeft",
                "FrontLowerTabRight",
                "FrontLowerRootLeft",
                "FrontLowerRootRight",
                "RearLowerDetentLeft",
                "RearLowerDetentRight",
            )
        ]
        screen_keepouts = [
            _shape(document, name)
            for name in (
                "RearScreenFacePocket",
                "RearScreenPcbEnvelope",
                "ScreenFaceEnvelope",
                "ScreenActiveEnvelope",
            )
        ]
        usb_keepouts = [
            _shape(document, name)
            for name in (
                "UsbWindow",
                "UsbGuideLeft",
                "UsbGuideRight",
                "UsbForcePlate",
                "UsbForcePlateBridgeLeft",
                "UsbForcePlateBridgeRight",
                "UsbSupportAnchorLeft",
                "UsbSupportAnchorRight",
            )
        ]
        buzzer_keepouts = [
            _shape(document, name)
            for name in ("BuzzerEnvelope", "BuzzerServiceEnvelope")
        ]

        pose_shapes = {
            pose_name: _shape(document, object_name)
            for pose_name, object_name in POSE_NAMES.items()
        }
        pose_interference = {
            pose_name: pose_shape.common(rear).Volume
            for pose_name, pose_shape in pose_shapes.items()
        }
        pose_keepout_groups = {
            "screen": [
                _shape(document, name)
                for name in (
                    "ScreenFaceEnvelope",
                    "RearScreenPcbEnvelope",
                    "ScreenActiveEnvelope",
                )
            ],
            "usb": usb_keepouts,
            "buzzer": [_shape(document, "BuzzerEnvelope")],
        }
        pose_keepout_interference = {
            pose_name: {
                group_name: _interference_volume([pose_shape], keepouts)
                for group_name, keepouts in pose_keepout_groups.items()
            }
            for pose_name, pose_shape in pose_shapes.items()
        }
        locked = _shape(document, "AssemblyFrontLocked")
        flat_unlocked = _shape(document, "AssemblyFrontFlatUnlocked")
        upper_tabs = [
            _shape(document, name)
            for name in ("FrontUpperTabLeft", "FrontUpperTabRight")
        ]
        lower_tabs = [
            _shape(document, name)
            for name in ("FrontLowerTabLeft", "FrontLowerTabRight")
        ]

        front_screen_mount_volume = sum(
            shape.Volume
            for name in (
                "ScreenMount",
                "ScreenPost1",
                "ScreenPost2",
                "ScreenPost3",
                "ScreenPost4",
                "ScreenRetainerLeft",
                "ScreenRetainerRight",
            )
            if (shape := _shape_or_none(document, name)) is not None
        )
        rear_screen_support_status, rear_screen_supports_ready = _screen_stop_status(
            document,
            rear,
        )
        rear_screen_support_count = sum(
            facts["present"] for facts in rear_screen_support_status.values()
        )
        minimum_root, roots_fused = _minimum_root_thickness(document, front)
        minimum_guide_wall, guide_wall_measurements = _minimum_guide_wall_thickness(
            document,
            rear,
            Part,
            App,
        )
        known_thin_feature_minimums = _known_thin_feature_minimums(
            document,
            Part,
            App,
        )

        usb_comparison_mask = usb_window.fuse(baseline_usb_window).removeSplitter()
        front_visible = visible_exterior(front, -0.10, 1.60, -1.0)
        baseline_front_visible = visible_exterior(
            baseline_front,
            -0.10,
            1.60,
            -1.0,
        )
        rear_visible = visible_exterior(
            rear,
            19.00,
            20.70,
            1.0,
            usb_comparison_mask,
        )
        baseline_rear_visible = visible_exterior(
            baseline_rear,
            19.00,
            20.70,
            1.0,
            usb_comparison_mask,
        )
        front_surface_difference = visible_surface_difference(
            front,
            baseline_front,
            -0.10,
            1.60,
            -1.0,
        )
        rear_surface_difference = visible_surface_difference(
            rear,
            baseline_rear,
            19.00,
            20.70,
            1.0,
            usb_comparison_mask,
        )
        front_surface_delta = front_surface_difference["area_delta_mm2"]
        rear_surface_delta = rear_surface_difference["area_delta_mm2"]
        retrofit_thickness = _overall_thickness(front, rear)
        baseline_thickness = _overall_thickness(baseline_front, baseline_rear)
        overall_thickness_delta = retrofit_thickness - baseline_thickness

        front_relief = _relief_values(document, "FrontShell")
        rear_relief = _relief_values(document, "RearCover")
        baseline_front_relief = _relief_values(baseline, "FrontShell")
        baseline_rear_relief = _relief_values(baseline, "RearCover")
        upper_centres_y = [round(tab.BoundBox.Center.y, 3) for tab in upper_tabs]
        pose_keepout_report = {
            f"{pose_name}_{group_name}_keepout_interference_mm3": round(
                interference,
                6,
            )
            for pose_name, groups in pose_keepout_interference.items()
            for group_name, interference in groups.items()
        }
        report: dict[str, object] = {
            "required_front": not _missing_names(names, REQUIRED["front"]),
            "required_rear": not _missing_names(names, REQUIRED["rear"]),
            "required_screen_mount": not _missing_names(names, REQUIRED_SCREEN_MOUNT),
            "required_closure": not _missing_names(names, REQUIRED_CLOSURE),
            "front_valid": front.isValid(),
            "rear_valid": rear.isValid(),
            "front_solids": len(front.Solids),
            "rear_solids": len(rear.Solids),
            "front_is_single_valid_solid": front.isValid() and len(front.Solids) == 1,
            "rear_is_single_valid_solid": rear.isValid() and len(rear.Solids) == 1,
            "front_printable_closed_solid": _single_closed_solid(front),
            "rear_printable_closed_solid": _single_closed_solid(rear),
            "front_free_solid_count": max(0, len(front.Solids) - 1),
            "rear_free_solid_count": max(0, len(rear.Solids) - 1),
            "outer_width_mm": round(max(front.BoundBox.XLength, rear.BoundBox.XLength), 3),
            "baseline_outer_width_mm": round(
                max(
                    baseline_front.BoundBox.XLength,
                    baseline_rear.BoundBox.XLength,
                ),
                3,
            ),
            "outer_width_delta_mm": round(
                abs(
                    max(front.BoundBox.XLength, rear.BoundBox.XLength)
                    - max(
                        baseline_front.BoundBox.XLength,
                        baseline_rear.BoundBox.XLength,
                    )
                ),
                6,
            ),
            "overall_thickness_mm": round(retrofit_thickness, 10),
            "baseline_overall_thickness_mm": round(baseline_thickness, 10),
            "overall_thickness_delta_mm": round(
                overall_thickness_delta,
                6,
            ),
            "front_hex_point_to_point_mm": round(front_hex.BoundBox.YLength, 3),
            "front_hex_bounds_delta_mm": round(
                _max_bounds_delta(front_hex, baseline_front_hex),
                6,
            ),
            "front_relief_depth_mm": round(front_relief[0], 3),
            "rear_relief_depth_mm": round(rear_relief[0], 3),
            "front_transition_radius_mm": round(front_relief[1], 3),
            "rear_transition_radius_mm": round(rear_relief[1], 3),
            "front_white_blocks": front_relief[2],
            "rear_white_blocks": rear_relief[2],
            "relief_properties_match_baseline": front_relief == baseline_front_relief
            and rear_relief == baseline_rear_relief,
            "usb_vertical_shift_mm": round(
                usb_window.BoundBox.YMin - baseline_usb_window.BoundBox.YMin,
                3,
            ),
            "usb_window_bounds_delta_mm": round(
                max(
                    abs(usb_window.BoundBox.XLength - baseline_usb_window.BoundBox.XLength),
                    abs(usb_window.BoundBox.YLength - baseline_usb_window.BoundBox.YLength),
                    abs(usb_window.BoundBox.ZLength - baseline_usb_window.BoundBox.ZLength),
                ),
                6,
            ),
            "front_screen_mount_volume_mm3": round(front_screen_mount_volume, 6),
            "rear_screen_support_count": rear_screen_support_count,
            "rear_screen_support_status": rear_screen_support_status,
            "rear_screen_supports_ready": rear_screen_supports_ready,
            "screen_face_setback_mm": round(
                screen_face.BoundBox.ZMin - DEFAULTS.front_seam_z_mm,
                3,
            ),
            "screen_keepout_interference_mm3": round(
                _interference_volume(closure_parts, screen_keepouts),
                6,
            ),
            "usb_keepout_interference_mm3": round(
                _interference_volume(closure_parts, usb_keepouts),
                6,
            ),
            "buzzer_keepout_interference_mm3": round(
                _interference_volume(closure_parts, buzzer_keepouts),
                6,
            ),
            "closure_point_count": sum(
                shape.Volume > TOLERANCE_MM3 for shape in (*upper_tabs, *lower_tabs)
            ),
            "upper_tab_centres_y_mm": upper_centres_y,
            "slide_travel_mm": round(
                locked.BoundBox.Center.y - flat_unlocked.BoundBox.Center.y,
                3,
            ),
            "tilted_pose_interference_mm3": round(pose_interference["tilted"], 6),
            "flat_unlocked_pose_interference_mm3": round(
                pose_interference["flat_unlocked"],
                6,
            ),
            "locked_pose_interference_mm3": round(pose_interference["locked"], 6),
            "minimum_latch_root_mm": round(minimum_root, 6),
            "latch_roots_fused": roots_fused,
            "minimum_guide_wall_mm": round(minimum_guide_wall, 6),
            "guide_wall_measurements_mm": guide_wall_measurements,
            "known_thin_feature_minimums_mm": known_thin_feature_minimums,
            "buzzer_hole_absent": document.getObject("BuzzerHoleCut") is None,
            "front_visible_exterior": front_visible,
            "baseline_front_visible_exterior": baseline_front_visible,
            "rear_visible_exterior": rear_visible,
            "baseline_rear_visible_exterior": baseline_rear_visible,
            "front_visible_surface_delta_mm2": round(front_surface_delta, 6),
            "rear_visible_surface_delta_mm2": round(rear_surface_delta, 6),
            "front_visible_boundary_delta_mm": round(
                front_surface_difference["max_boundary_delta_mm"],
                6,
            ),
            "rear_visible_boundary_delta_mm": round(
                rear_surface_difference["max_boundary_delta_mm"],
                6,
            ),
            # Kept for downstream consumers which historically expected a
            # volume field. The source evidence above is actual surface area;
            # this field is its stated 1.00 mm reference-depth projection.
            "frozen_exterior_reference_depth_mm": FROZEN_SURFACE_REFERENCE_DEPTH_MM,
            "front_frozen_exterior_delta_mm3": round(
                front_surface_delta * FROZEN_SURFACE_REFERENCE_DEPTH_MM,
                6,
            ),
            "rear_frozen_exterior_delta_mm3": round(
                rear_surface_delta * FROZEN_SURFACE_REFERENCE_DEPTH_MM,
                6,
            ),
            "stl_meshes": stl_meshes,
            **pose_keepout_report,
        }
        pose_keepout_checks = {
            f"{pose_name}_{group_name}_keepout_clear": interference <= TOLERANCE_MM3
            for pose_name, groups in pose_keepout_interference.items()
            for group_name, interference in groups.items()
        }
        checks = {
            "required_objects": all(
                report[name]
                for name in (
                    "required_front",
                    "required_rear",
                    "required_screen_mount",
                    "required_closure",
                )
            ),
            "front_single_valid_solid": report["front_is_single_valid_solid"],
            "rear_single_valid_solid": report["rear_is_single_valid_solid"],
            "front_printable_closed_solid": report["front_printable_closed_solid"],
            "rear_printable_closed_solid": report["rear_printable_closed_solid"],
            "no_free_solids": report["front_free_solid_count"] == 0
            and report["rear_free_solid_count"] == 0,
            "outer_width": abs(report["outer_width_mm"] - 56.0) <= TOLERANCE_MM,
            "outer_width_matches_baseline": report["outer_width_delta_mm"] <= TOLERANCE_MM,
            "overall_thickness": report["overall_thickness_delta_mm"] <= TOLERANCE_MM,
            "overall_thickness_matches_baseline": report["overall_thickness_delta_mm"]
            <= TOLERANCE_MM,
            "front_hex": abs(
                report["front_hex_point_to_point_mm"] - 23.50
            ) <= TOLERANCE_MM,
            "front_hex_matches_baseline": report["front_hex_bounds_delta_mm"] <= TOLERANCE_MM,
            "relief_properties_match_baseline": report[
                "relief_properties_match_baseline"
            ],
            "usb_shift": abs(report["usb_vertical_shift_mm"] - 5.00) <= TOLERANCE_MM,
            "usb_size_matches_baseline": report["usb_window_bounds_delta_mm"] <= TOLERANCE_MM,
            "front_screen_clear": report["front_screen_mount_volume_mm3"] <= TOLERANCE_MM3,
            "rear_screen_supports": report["rear_screen_support_count"] == 4
            and report["rear_screen_supports_ready"],
            "screen_setback": 0.10 <= report["screen_face_setback_mm"] <= 0.30,
            "screen_keepout_clear": report["screen_keepout_interference_mm3"] <= TOLERANCE_MM3,
            "usb_keepout_clear": report["usb_keepout_interference_mm3"] <= TOLERANCE_MM3,
            "buzzer_keepout_clear": report["buzzer_keepout_interference_mm3"] <= TOLERANCE_MM3,
            "four_closure_points": report["closure_point_count"] == 4,
            "approved_upper_tab_y_exception": all(
                abs(value - DEFAULTS.top_tongue_approved_y_exception_mm) <= TOLERANCE_MM
                for value in report["upper_tab_centres_y_mm"]
            ),
            "slide_travel": abs(report["slide_travel_mm"] - 2.50) <= TOLERANCE_MM,
            "tilted_pose_clear": report["tilted_pose_interference_mm3"] <= TOLERANCE_MM3,
            "flat_pose_clear": report["flat_unlocked_pose_interference_mm3"] <= TOLERANCE_MM3,
            "locked_pose_clear": report["locked_pose_interference_mm3"] <= TOLERANCE_MM3,
            "latch_roots": report["latch_roots_fused"]
            and report["minimum_latch_root_mm"] >= 1.30 - TOLERANCE_MM,
            "guide_walls": report["minimum_guide_wall_mm"] >= 1.30 - TOLERANCE_MM,
            "known_thin_features": min(
                report["known_thin_feature_minimums_mm"].values()
            ) >= DEFAULTS.minimum_feature_mm - TOLERANCE_MM,
            "no_buzzer_hole": report["buzzer_hole_absent"],
            "front_exterior_frozen": report[
                "front_visible_surface_delta_mm2"
            ] <= FROZEN_SURFACE_AREA_TOLERANCE_MM2
            and report["front_visible_boundary_delta_mm"]
            <= FROZEN_SURFACE_BOUNDARY_TOLERANCE_MM,
            "rear_exterior_frozen": report[
                "rear_visible_surface_delta_mm2"
            ] <= FROZEN_SURFACE_AREA_TOLERANCE_MM2
            and report["rear_visible_boundary_delta_mm"]
            <= FROZEN_SURFACE_BOUNDARY_TOLERANCE_MM,
            **{
                f"{shell}_stl_matches_fcstd_bounds": facts[
                    "fcstd_bounds_delta_mm"
                ] is not None
                and facts["fcstd_bounds_delta_mm"] <= STL_BOUNDS_TOLERANCE_MM
                for shell, facts in stl_meshes.items()
            },
            **{
                f"{shell}_stl_matches_step_bounds": facts[
                    "step_bounds_delta_mm"
                ] is not None
                and facts["step_bounds_delta_mm"] <= STL_BOUNDS_TOLERANCE_MM
                for shell, facts in stl_meshes.items()
            },
            **{
                f"{shell}_stl_watertight": facts["watertight"]
                for shell, facts in stl_meshes.items()
            },
            **{
                f"{shell}_stl_two_manifold": facts["two_manifold"]
                for shell, facts in stl_meshes.items()
            },
            **{
                f"{shell}_stl_no_self_intersections": facts[
                    "self_intersection_count"
                ] == 0
                for shell, facts in stl_meshes.items()
            },
            **{
                f"{shell}_stl_no_degenerate_triangles": facts[
                    "degenerate_triangle_count"
                ] == 0
                for shell, facts in stl_meshes.items()
            },
            **{
                f"{shell}_stl_single_shell": facts["component_count"] == 1
                for shell, facts in stl_meshes.items()
            },
            **{
                f"{shell}_stl_consistent_normals": facts["consistent_normals"]
                for shell, facts in stl_meshes.items()
            },
            **{
                f"{shell}_stl_positive_oriented_volume": facts[
                    "positive_oriented_volume_mm3"
                ] is not None
                and facts["positive_oriented_volume_mm3"] > 0.0
                for shell, facts in stl_meshes.items()
            },
            **{
                f"{shell}_gmsh_check_passed": facts["gmsh_check_passed"]
                and facts["gmsh_check_has_warning"] is False
                for shell, facts in stl_meshes.items()
            },
            **pose_keepout_checks,
        }
        report["checks"] = checks
        report["passed"] = all(checks.values())
        return report
    finally:
        App.closeDocument(document.Name)
        App.closeDocument(baseline.Name)


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit(
            "usage: audit_blossom_enclosure.py RETROFIT.FCStd BASELINE.FCStd audit.json"
        )
    output = Path(sys.argv[3]).resolve()
    if output.parent != RETROFIT_OUTPUT_DIR.resolve():
        raise SystemExit(f"audit output must be inside {RETROFIT_OUTPUT_DIR}")
    report = audit_document(sys.argv[1], sys.argv[2])
    payload = json.dumps(report, indent=2, sort_keys=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    if not report["passed"]:
        raise SystemExit(1)
