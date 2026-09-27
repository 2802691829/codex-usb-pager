"""Generate the two-piece Blossom enclosure in FreeCAD.

Run from the repository root with FreeCADCmd.exe. The source SVG is imported
directly; its paths are uniformly scaled into every visible Blossom feature.
"""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
from math import cos, pi, radians, sin, sqrt, tan

FREECAD_MOD = r"C:\Program Files\FreeCAD 1.1\Mod"
sys.path.append(os.path.join(FREECAD_MOD, "Draft"))
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HANDOFF_DIR = os.path.dirname(SCRIPT_DIR)
DOCS_DIR = os.path.dirname(HANDOFF_DIR)
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import FreeCAD as App
import Import
import Part
import importSVG

from enclosure_params import DEFAULTS


SVG_PATH = os.path.join(SCRIPT_DIR, "openai-blossom-print-clean.svg")
BASELINE_OUTPUT_DIR = os.path.join(HANDOFF_DIR, "outputs")
OUTPUT_DIR = os.path.join(BASELINE_OUTPUT_DIR, "four-latch-retrofit")
BASELINE_DOCUMENT_PATH = os.path.join(
    BASELINE_OUTPUT_DIR,
    "blossom-enclosure.FCStd",
)
ASSEMBLY_TILT_ANGLE_DEG = 12.0
GMSH_EXE = os.path.join(os.path.dirname(sys.executable), "gmsh.exe")
GMSH_MIN_SIZE_MM = 0.20
GMSH_MAX_SIZE_MM = 0.60
GMSH_CURVATURE_NODES = 8


def export_print_mesh(shell, filename: str) -> None:
    """Generate one resin STL from its own millimetre STEP source."""
    if not os.path.exists(GMSH_EXE):
        raise FileNotFoundError(f"FreeCAD Gmsh executable is missing: {GMSH_EXE}")

    output_path = Path(OUTPUT_DIR) / filename
    temp_step_path = Path(OUTPUT_DIR) / f".{output_path.stem}.step"
    try:
        Import.export([shell], str(temp_step_path))
        result = subprocess.run(
            [
                GMSH_EXE,
                str(temp_step_path),
                "-2",
                "-algo", "del2d",
                "-format",
                "stl",
                "-clmin", str(GMSH_MIN_SIZE_MM),
                "-clmax", str(GMSH_MAX_SIZE_MM),
                "-clcurv", str(GMSH_CURVATURE_NODES),
                "-o",
                str(output_path),
            ],
            cwd=OUTPUT_DIR,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(
                "Gmsh STL export failed: "
                f"{result.stdout}\n{result.stderr}"
            )
        log = f"{result.stdout}\n{result.stderr}"
        if any(line.lstrip().startswith("Warning") for line in log.splitlines()):
            raise RuntimeError(
                f"Gmsh STL export emitted a warning for {filename}: {log}"
            )
    finally:
        temp_step_path.unlink(missing_ok=True)


def transform_shape(shape, scale: float, z: float = 0.0):
    matrix = App.Matrix()
    matrix.A11 = scale
    matrix.A22 = scale
    result = shape.transformGeometry(matrix)
    box = result.BoundBox
    result.translate(App.Vector(-(box.XMin + box.XLength / 2.0), -(box.YMin + box.YLength / 2.0), z))
    return result


def transform_shape_relative(shape, reference_wire, scale: float, z: float):
    """Uniformly scale a source part without losing its SVG-relative position."""
    matrix = App.Matrix()
    matrix.A11 = scale
    matrix.A22 = scale
    result = shape.transformGeometry(matrix)
    reference_box = reference_wire.BoundBox
    result.translate(
        App.Vector(
            -(reference_box.XMin + reference_box.XLength / 2.0) * scale,
            -(reference_box.YMin + reference_box.YLength / 2.0) * scale,
            z - result.BoundBox.ZMin,
        )
    )
    return result


def wire_profile(wire, scale: float, z: float):
    profile = transform_shape(wire, scale, z)
    return profile


def regular_hexagon(
    across_flats: float,
    z: float,
    height: float,
    center_x: float = 0.0,
    center_y: float = 0.0,
):
    apothem = across_flats / 2.0
    radius = apothem / (3.0 ** 0.5 / 2.0)
    points = [
        App.Vector(
            center_x + radius * cos(pi / 6.0 + index * pi / 3.0),
            center_y + radius * sin(pi / 6.0 + index * pi / 3.0),
            z,
        )
        for index in range(6)
    ]
    return Part.Face(Part.makePolygon(points + [points[0]])).extrude(App.Vector(0, 0, height))


def rounded_rectangle_prism(width: float, height: float, radius: float, depth: float, base: App.Vector):
    """Create a rounded rectangle solid whose corners remain visibly rounded."""
    radius = min(radius, width / 2.0, height / 2.0)
    horizontal = Part.makeBox(width - 2.0 * radius, height, depth, App.Vector(base.x + radius, base.y, base.z))
    vertical = Part.makeBox(width, height - 2.0 * radius, depth, App.Vector(base.x, base.y + radius, base.z))
    corners = [
        Part.makeCylinder(radius, depth, App.Vector(base.x + offset_x, base.y + offset_y, base.z))
        for offset_x in (radius, width - radius)
        for offset_y in (radius, height - radius)
    ]
    return horizontal.fuse(vertical).multiFuse(corners)


def rectangular_frame(
    inner_width: float,
    inner_height: float,
    wall: float,
    height: float,
    base: App.Vector,
):
    """Create a rectangular locating frame around a clearance envelope."""
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


def build_rear_screen_mount(cavity):
    """Build the rear-owned display support and clearance envelopes."""
    face_w, face_h = DEFAULTS.screen_pocket_mm
    pcb_w, pcb_h = DEFAULTS.screen_pcb_pocket_mm
    face_y = DEFAULTS.screen_face_center_y_mm
    pcb_y = DEFAULTS.screen_pcb_center_y_mm
    face_z = DEFAULTS.screen_face_front_z_mm
    support_depth = DEFAULTS.screen_face_to_pcb_mm + DEFAULTS.screen_face_setback_mm

    face_pocket = Part.makeBox(
        face_w,
        face_h,
        support_depth,
        App.Vector(-face_w / 2.0, face_y - face_h / 2.0, DEFAULTS.front_seam_z_mm),
    )
    pcb_envelope = Part.makeBox(
        pcb_w,
        pcb_h,
        DEFAULTS.screen_face_to_pcb_mm,
        App.Vector(-pcb_w / 2.0, pcb_y - pcb_h / 2.0, face_z),
    )
    frame_wall = 0.90
    support_ring = rectangular_frame(
        face_w,
        face_h,
        frame_wall,
        DEFAULTS.screen_slot_depth_mm,
        App.Vector(
            -face_w / 2.0 - frame_wall,
            face_y - face_h / 2.0 - frame_wall,
            DEFAULTS.front_seam_z_mm,
        ),
    )

    stop_length, stop_width, stop_height = DEFAULTS.screen_edge_stop_mm
    stop_z = face_z + DEFAULTS.screen_face_to_pcb_mm - 0.05
    stop_ys = (pcb_y - 8.0 - stop_length / 2.0, pcb_y + 8.0 - stop_length / 2.0)
    edge_stops = tuple(
        Part.makeBox(
            stop_width,
            stop_length,
            stop_height,
            App.Vector(x, y, stop_z),
        )
        for x in (-pcb_w / 2.0 - stop_width, pcb_w / 2.0)
        for y in stop_ys
    )

    screen_face = Part.makeBox(
        DEFAULTS.screen_face_mm[0],
        DEFAULTS.screen_face_mm[1],
        DEFAULTS.screen_face_to_pcb_mm,
        App.Vector(
            -DEFAULTS.screen_face_mm[0] / 2.0,
            face_y - DEFAULTS.screen_face_mm[1] / 2.0,
            face_z,
        ),
    )
    screen_active = Part.makeBox(
        DEFAULTS.screen_active_mm[0],
        DEFAULTS.screen_active_mm[1],
        DEFAULTS.screen_face_to_pcb_mm + 0.50,
        App.Vector(
            -DEFAULTS.screen_active_mm[0] / 2.0,
            DEFAULTS.front_hex_center_y_mm
            - DEFAULTS.screen_active_mm[1] / 2.0,
            face_z - 0.10,
        ),
    )
    rear_screen_support = support_ring.removeSplitter()
    return (
        rear_screen_support,
        face_pocket,
        pcb_envelope,
        edge_stops,
        screen_face,
        screen_active,
    )


def make_x_prism(width: float, yz_points: tuple[tuple[float, float], ...], x: float):
    """Extrude one closed YZ profile along X."""
    points = [App.Vector(x, y, z) for y, z in yz_points]
    wire = Part.makePolygon(points + [points[0]])
    return Part.Face(wire).extrude(App.Vector(width, 0, 0))


def upper_capture_pivot(seam_z, pivot_y):
    return App.Vector(0.0, pivot_y, seam_z)


def make_flat_unlocked(shape):
    result = shape.copy()
    result.translate(App.Vector(0.0, -DEFAULTS.closure_slide_travel_mm, 0.0))
    return result


def make_tilted(shape, seam_z, pivot_y):
    result = make_flat_unlocked(shape)
    result.rotate(
        upper_capture_pivot(seam_z, pivot_y),
        App.Vector(1.0, 0.0, 0.0),
        ASSEMBLY_TILT_ANGLE_DEG,
    )
    return result


def make_upper_tab(centre_x, centre_y, seam_z):
    width, thickness, projection = DEFAULTS.top_tongue_mm
    body_y_min = centre_y - thickness / 2.0
    body_z_min = seam_z + DEFAULTS.top_tongue_bottom_clearance_mm
    body = Part.makeBox(
        width,
        thickness,
        projection,
        App.Vector(
            centre_x - width / 2.0,
            body_y_min,
            body_z_min,
        ),
    )
    ramp_height = 0.50
    ramp_run = ramp_height / tan(radians(DEFAULTS.latch_entry_angle_deg))
    cutter = make_x_prism(
        width + 0.20,
        (
            (body_y_min - 0.10, body_z_min + projection - ramp_height),
            (body_y_min + ramp_run, body_z_min + projection + 0.10),
            (body_y_min - 0.10, body_z_min + projection + 0.10),
        ),
        centre_x - width / 2.0 - 0.10,
    )
    # Keep the 1.30 mm root fully above the frozen front visible relief band
    # (Z <= 1.60 mm). It still overlaps the tab body by 0.95 mm and the front
    # shell by 0.05 mm, so both upper latches retain a real fused load path.
    root = Part.makeBox(
        width,
        1.30,
        1.30,
        App.Vector(
            centre_x - width / 2.0,
            body_y_min - 0.30,
            seam_z - 0.05,
        ),
    )
    return body.cut(cutter).removeSplitter(), root


def make_upper_socket(tab, seam_z, pivot_y):
    clearance = DEFAULTS.top_tongue_clearance_mm
    width, thickness, projection = DEFAULTS.top_tongue_mm
    box = tab.BoundBox
    blind = Part.makeBox(
        width + 2.0 * clearance,
        thickness + 2.0 * clearance,
        projection + DEFAULTS.top_tongue_bottom_clearance_mm,
        App.Vector(
            box.XMin - clearance,
            box.YMin - clearance,
            box.ZMin - DEFAULTS.top_tongue_bottom_clearance_mm,
        ),
    )

    # This is an analytical local insertion funnel, not a sampled sweep of
    # transformed BoundBoxes. Its low floor only exists where the 12-degree
    # entry pose needs it, before rising into the final blind socket.
    tilt_angle = radians(ASSEMBLY_TILT_ANGLE_DEG)
    flat_y_min = box.YMin - DEFAULTS.closure_slide_travel_mm
    entry_y_min = (
        pivot_y
        + (flat_y_min - pivot_y) * cos(tilt_angle)
        - (box.ZMax - seam_z) * sin(tilt_angle)
        - clearance
    )
    entry_y_max = box.YMin
    entry_z_min = (
        seam_z
        + (flat_y_min - pivot_y) * sin(tilt_angle)
        + (box.ZMin - seam_z) * cos(tilt_angle)
        - clearance
    )
    entry_z_max = box.ZMax
    entry_floor_rise_y = entry_y_max - 1.20
    entry = make_x_prism(
        width + 2.0 * clearance,
        (
            (entry_y_min, entry_z_min),
            (entry_y_min, entry_z_max),
            (entry_y_max, entry_z_max),
            (entry_y_max, blind.BoundBox.ZMin),
            (entry_floor_rise_y, entry_z_min),
        ),
        box.XMin - clearance,
    )
    return entry.removeSplitter(), blind, entry.fuse(blind).removeSplitter()


def build_four_point_slide_closure(
    front_blank,
    rear_blank,
    rear_exterior_guard,
    buzzer_envelope,
    closure_keepouts,
):
    """Build four rigid tabs for angled entry and a short +Y slide lock."""
    seam_z = DEFAULTS.front_seam_z_mm
    upper_pivot_y = rear_blank.BoundBox.YMax
    upper_tabs = []
    upper_roots = []
    upper_entries = []
    upper_blind_sockets = []
    upper_sockets = []
    for centre_x, centre_y in DEFAULTS.top_tongue_centres_mm:
        tab, root = make_upper_tab(centre_x, centre_y, seam_z)
        entry, blind, socket = make_upper_socket(tab, seam_z, upper_pivot_y)
        upper_tabs.append(tab)
        upper_roots.append(root)
        upper_entries.append(entry)
        upper_blind_sockets.append(blind)
        upper_sockets.append(socket)

    tab_width, tab_thickness, tab_length = DEFAULTS.front_latch_hook_mm
    clearance = DEFAULTS.lower_guide_clearance_mm
    minimum_load_wall = 1.30
    existing_guide_wall = DEFAULTS.nominal_wall_mm - clearance
    guide_wall_reinforcement = minimum_load_wall - existing_guide_wall
    if guide_wall_reinforcement <= 0.0:
        raise RuntimeError("Four-point closure guide-wall reinforcement is invalid")

    component_keepout_solids = [*closure_keepouts.Solids, buzzer_envelope]
    lower_tabs = []
    lower_bearings = []
    lower_roots = []
    lower_guides = []
    lower_guide_wall_reinforcements = []
    lower_root_channels = []
    lower_detents = []
    lower_detent_supports = []
    lower_bearing_z = (
        DEFAULTS.screen_face_front_z_mm
        + DEFAULTS.screen_face_to_pcb_mm
        + DEFAULTS.screen_edge_stop_mm[2]
    )
    for centre_x, centre_y in DEFAULTS.front_latch_centres_mm:
        bearing = Part.makeBox(
            tab_width,
            tab_length,
            tab_thickness,
            App.Vector(
                centre_x - tab_width / 2.0,
                centre_y - tab_length / 2.0,
                lower_bearing_z,
            ),
        )
        root_x_min = (
            bearing.BoundBox.XMin
            if centre_x < 0.0
            else bearing.BoundBox.XMax - minimum_load_wall
        )
        root = Part.makeBox(
            minimum_load_wall,
            tab_length,
            bearing.BoundBox.ZMax - (seam_z - 0.05),
            App.Vector(root_x_min, bearing.BoundBox.YMin, seam_z - 0.05),
        )
        guide = Part.makeBox(
            tab_width + 2.0 * clearance,
            tab_length + DEFAULTS.closure_slide_travel_mm + 2.0 * clearance,
            tab_thickness + 2.0 * clearance,
            App.Vector(
                centre_x - tab_width / 2.0 - clearance,
                centre_y - tab_length / 2.0
                - DEFAULTS.closure_slide_travel_mm - clearance,
                lower_bearing_z - clearance,
            ),
        )
        reinforcement_x = (
            guide.BoundBox.XMin - minimum_load_wall
            if centre_x < 0.0
            else guide.BoundBox.XMax + existing_guide_wall
        )
        guide_wall = Part.makeBox(
            guide_wall_reinforcement,
            guide.BoundBox.YLength,
            guide.BoundBox.ZLength,
            App.Vector(reinforcement_x, guide.BoundBox.YMin, guide.BoundBox.ZMin),
        )
        root_channel = Part.makeBox(
            minimum_load_wall + 2.0 * clearance,
            guide.BoundBox.YLength,
            root.BoundBox.ZLength + 0.10,
            App.Vector(
                root.BoundBox.XMin - clearance,
                guide.BoundBox.YMin,
                root.BoundBox.ZMin,
            ),
        )
        detent = Part.makeBox(
            tab_width,
            DEFAULTS.closure_detent_mm,
            DEFAULTS.closure_detent_mm,
            App.Vector(
                centre_x - tab_width / 2.0,
                centre_y + tab_length / 2.0,
                bearing.BoundBox.ZMax - DEFAULTS.closure_detent_mm,
            ),
        )
        detent_support_z = detent.BoundBox.ZMax - 0.05
        detent_support = Part.makeBox(
            tab_width,
            DEFAULTS.closure_detent_mm,
            guide.BoundBox.ZMax + 0.05 - detent_support_z,
            App.Vector(
                centre_x - tab_width / 2.0,
                centre_y + tab_length / 2.0,
                detent_support_z,
            ),
        )
        lower_tab = bearing.copy()
        lower_tabs.append(lower_tab)
        lower_bearings.append(bearing)
        lower_roots.append(root)
        lower_guides.append(guide)
        lower_guide_wall_reinforcements.append(guide_wall)
        lower_root_channels.append(root_channel)
        lower_detents.append(detent)
        lower_detent_supports.append(detent_support)

    closure_cutters = Part.makeCompound(
        [*upper_sockets, *lower_guides, *lower_root_channels]
    )
    exterior_breach = sum(
        cutter.common(guard_solid).Volume
        for cutter in (*upper_sockets, *lower_guides, *lower_root_channels)
        for guard_solid in rear_exterior_guard.Solids
    )
    if exterior_breach > 1e-5:
        raise RuntimeError("Four-point closure breaches the frozen rear exterior")
    keepout_overlap = sum(
        tab.common(keepout).Volume
        for tab in (*upper_tabs, *upper_roots, *lower_bearings, *lower_roots)
        for keepout in component_keepout_solids
    )
    if keepout_overlap > 1e-5:
        raise RuntimeError("Four-point closure intersects a component keepout")
    detent_keepout_overlap = sum(
        part.common(keepout).Volume
        for part in (*lower_detents, *lower_detent_supports)
        for keepout in component_keepout_solids
    )
    if detent_keepout_overlap > 1e-5:
        raise RuntimeError("Four-point closure detent intersects a component keepout")

    front_body = front_blank.multiFuse(
        [*upper_tabs, *upper_roots, *lower_tabs, *lower_roots]
    ).removeSplitter()
    rear_closure_blank = rear_blank.copy()
    rear_detent_assemblies = [
        detent.fuse(support)
        for detent, support in zip(lower_detents, lower_detent_supports)
    ]
    rear_body = rear_closure_blank.cut(closure_cutters).multiFuse(
        [*rear_detent_assemblies, *lower_guide_wall_reinforcements]
    ).removeSplitter()

    flat_unlocked = make_flat_unlocked(front_body)
    locked = front_body.copy()
    tilted = make_tilted(front_body, seam_z, upper_pivot_y)
    return {
        "front": front_body,
        "rear": rear_body,
        "front_upper_tabs": upper_tabs,
        "front_upper_roots": upper_roots,
        "rear_upper_entries": upper_entries,
        "rear_upper_blind_sockets": upper_blind_sockets,
        "rear_upper_sockets": upper_sockets,
        "front_lower_tabs": lower_tabs,
        "front_lower_bearings": lower_bearings,
        "front_lower_roots": lower_roots,
        "rear_lower_guides": lower_guides,
        "rear_lower_detents": lower_detents,
        "assembly_front_tilted": tilted,
        "assembly_front_flat_unlocked": flat_unlocked,
        "assembly_front_locked": locked,
        "assembly_pose_tilted": Part.makeCompound([tilted, rear_body]),
        "assembly_pose_flat_unlocked": Part.makeCompound([flat_unlocked, rear_body]),
        "assembly_pose_locked": Part.makeCompound([locked, rear_body]),
        "front_blank": front_blank,
        "rear_blank": rear_closure_blank,
        "electronic_cavity_reliefs": Part.makeCompound(
            [*lower_bearings, *lower_roots, *lower_detent_supports]
        ),
    }


def split_blossom_faces(shapes):
    """Return the outer silhouette face and seven faces from SVG sub-objects."""
    outer_shape = max(shapes, key=lambda item: sum(face.Area for face in item.Faces))
    outer_face = max(outer_shape.Faces, key=lambda face: face.Area).copy()
    detail_faces = [
        face.copy()
        for shape in shapes
        if shape is not outer_shape
        for face in shape.Faces
        if face.Area > 1e-4
    ]
    outer_wire_area = max(Part.Face(wire).Area for wire in outer_face.Wires)
    detail_faces.extend(
        Part.Face(wire)
        for wire in outer_face.Wires
        if Part.Face(wire).Area < outer_wire_area - 1e-4
    )
    if len(detail_faces) != 7:
        raise ValueError(f"Expected 7 Blossom white faces, found {len(detail_faces)}")
    return outer_face, detail_faces


def scale_wire_about_center(wire, factor: float, z: float):
    """Scale a wire about its own centre while retaining identical topology."""
    box = wire.BoundBox
    matrix = App.Matrix()
    matrix.A11 = factor
    matrix.A22 = factor
    matrix.A14 = box.Center.x * (1.0 - factor)
    matrix.A24 = box.Center.y * (1.0 - factor)
    section = wire.transformGeometry(matrix)
    section.translate(App.Vector(0, 0, z - section.BoundBox.ZMin))
    return section


def rounded_recess_cutter(face, surface_z: float, inward_sign: float, depth: float, radii):
    """Build the approved smooth transition from one clean SVG outline."""
    if abs(face.BoundBox.ZMin - surface_z) > 1e-6:
        raise ValueError("Relief face is not positioned on the requested surface")
    wire = max(face.Wires, key=lambda item: Part.Face(item).Area)
    minimum_span = min(wire.BoundBox.XLength, wire.BoundBox.YLength)
    for radius in radii:
        if 2.0 * radius >= minimum_span:
            continue
        profiles = []
        for fraction in (0.0, 0.25, 0.5, 0.75, 1.0):
            axial = radius * fraction
            offset = radius - sqrt(max(0.0, radius**2 - axial**2))
            factor = 1.0 - 2.0 * offset / minimum_span
            profiles.append(
                scale_wire_about_center(
                    wire,
                    factor,
                    surface_z + inward_sign * axial,
                )
            )
        profiles.append(
            scale_wire_about_center(
                wire,
                1.0 - 2.0 * radius / minimum_span,
                surface_z + inward_sign * depth,
            )
        )
        try:
            rounded = Part.makeLoft(profiles, True, False)
        except Part.OCCError:
            continue
        lower_z = min(surface_z, surface_z + inward_sign * depth)
        clip = Part.makeBox(
            face.BoundBox.XLength + 4.0,
            face.BoundBox.YLength + 4.0,
            depth,
            App.Vector(
                face.BoundBox.XMin - 2.0,
                face.BoundBox.YMin - 2.0,
                lower_z,
            ),
        )
        rounded = rounded.common(clip)
        if not rounded.isNull() and rounded.isValid():
            return rounded, radius
    raise RuntimeError("Unable to round Blossom recess with approved radii")


def add_feature(document, name: str, shape, visible: bool = False):
    feature = document.addObject("PartDesign::Feature", name)
    feature.Label = name
    feature.Shape = shape
    if feature.ViewObject is not None:
        feature.ViewObject.Visibility = visible
    return feature


def source_geometry():
    imported = importSVG.open(SVG_PATH)
    source_shapes = [obj.Shape.copy() for obj in imported.Objects if hasattr(obj, "Shape") and not obj.Shape.isNull()]
    outer_face, detail_faces = split_blossom_faces(source_shapes)
    outer_wire = max(outer_face.Wires, key=lambda item: item.BoundBox.XLength * item.BoundBox.YLength)
    source_width = outer_wire.BoundBox.XLength
    App.closeDocument(imported.Name)
    return outer_wire, detail_faces, DEFAULTS.blossom_target_width_mm / source_width


def build_usb_structure(usb_x, usb_y):
    usb_window = rounded_rectangle_prism(
        DEFAULTS.usb_window_mm[0],
        DEFAULTS.usb_window_mm[1],
        DEFAULTS.usb_corner_radius_mm,
        5.0,
        App.Vector(usb_x, usb_y, 17.0),
    )
    guide_left = Part.makeBox(1.5, 8.8, 2.0, App.Vector(usb_x - 2.3, usb_y, 15.0))
    guide_right = Part.makeBox(1.5, 8.8, 2.0, App.Vector(usb_x + 15.7, usb_y, 15.0))
    # Keep the USB window clear from edge to edge. The load-spreading plate
    # sits entirely inside the 5 mm PCB-to-adapter gap, behind the rear face.
    force_plate = Part.makeBox(
        DEFAULTS.usb_window_mm[0],
        DEFAULTS.usb_force_plate_gap_mm,
        1.2,
        App.Vector(usb_x, usb_y + DEFAULTS.usb_window_mm[1] + 0.5, 14.5),
    )
    bridge_y = usb_y + DEFAULTS.usb_window_mm[1] - 0.25
    bridge_left = Part.makeBox(
        1.0,
        1.0,
        DEFAULTS.minimum_feature_mm,
        App.Vector(usb_x - 0.9, bridge_y, 15.0),
    )
    bridge_right = Part.makeBox(
        2.5,
        1.0,
        DEFAULTS.minimum_feature_mm,
        App.Vector(usb_x + 13.3, bridge_y, 15.0),
    )
    anchor_size = 1.20
    anchor_z = guide_left.BoundBox.ZMax - 0.05
    rear_inner_roof_z = (
        DEFAULTS.front_seam_z_mm + DEFAULTS.internal_envelope_mm[2]
    )
    anchor_height = rear_inner_roof_z + 0.05 - anchor_z
    anchor_y = usb_y + 1.0
    anchor_left = Part.makeBox(
        anchor_size,
        anchor_size,
        anchor_height,
        App.Vector(
            guide_left.BoundBox.Center.x - anchor_size / 2.0,
            anchor_y,
            anchor_z,
        ),
    )
    anchor_right = Part.makeBox(
        anchor_size,
        anchor_size,
        anchor_height,
        App.Vector(
            guide_right.BoundBox.Center.x - anchor_size / 2.0,
            anchor_y,
            anchor_z,
        ),
    )
    return {
        "window": usb_window,
        "supports": (
            guide_left,
            guide_right,
            force_plate,
            bridge_left,
            bridge_right,
            anchor_left,
            anchor_right,
        ),
    }


def build():
    if not os.path.exists(SVG_PATH):
        raise FileNotFoundError(SVG_PATH)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    outer_wire, detail_faces, svg_scale = source_geometry()
    document = App.newDocument("BlossomEnclosure")

    # Front: the seven SVG white blocks recess into the visible Z=0 face.
    front_outer = Part.makeLoft(
        [
            wire_profile(outer_wire, svg_scale * 0.965, 0.0),
            wire_profile(outer_wire, svg_scale, DEFAULTS.front_seam_z_mm / 2.0),
            wire_profile(outer_wire, svg_scale, DEFAULTS.front_seam_z_mm),
        ],
        True,
        True,
    )
    front_hex_cut = regular_hexagon(
        DEFAULTS.front_hex_across_flats_mm,
        -0.1,
        3.0,
        center_y=DEFAULTS.front_hex_center_y_mm,
    )
    front_recesses = []
    front_radii = []
    for detail_face in detail_faces:
        scaled = transform_shape_relative(detail_face, outer_wire, svg_scale, 0.0)
        cutter, used_radius = rounded_recess_cutter(
            scaled,
            0.0,
            1.0,
            DEFAULTS.relief_depth_mm,
            DEFAULTS.relief_radius_fallbacks_mm,
        )
        front_recesses.append(cutter)
        front_radii.append(used_radius)
    front_recess = Part.makeCompound(front_recesses)
    front_body = front_outer.cut(front_recess)
    front_body = front_body.cut(front_hex_cut)
    add_feature(document, "FrontHexCut", front_hex_cut)
    add_feature(document, "BlossomRecessFront", front_recess)

    # Rear: the same seven white blocks recess into the visible outer crown.
    rear_outer = Part.makeLoft(
        [
            wire_profile(outer_wire, svg_scale, DEFAULTS.front_seam_z_mm),
            wire_profile(
                outer_wire,
                svg_scale,
                DEFAULTS.front_seam_z_mm + DEFAULTS.internal_envelope_mm[2],
            ),
            wire_profile(outer_wire, svg_scale * 0.965, DEFAULTS.maximum_thickness_mm),
        ],
        True,
        True,
    )
    cavity_width, cavity_height, cavity_depth = DEFAULTS.internal_envelope_mm
    cavity = Part.makeBox(
        cavity_width,
        cavity_height,
        cavity_depth,
        App.Vector(
            -cavity_width / 2.0,
            DEFAULTS.internal_envelope_bottom_y_mm,
            DEFAULTS.front_seam_z_mm,
        ),
    )
    rear_recesses = []
    rear_radii = []
    for detail_face in detail_faces:
        scaled = transform_shape_relative(
            detail_face,
            outer_wire,
            svg_scale,
            DEFAULTS.maximum_thickness_mm,
        )
        cutter, used_radius = rounded_recess_cutter(
            scaled,
            DEFAULTS.maximum_thickness_mm,
            -1.0,
            DEFAULTS.relief_depth_mm,
            DEFAULTS.relief_radius_fallbacks_mm,
        )
        rear_recesses.append(cutter)
        rear_radii.append(used_radius)
    rear_recess = Part.makeCompound(rear_recesses)
    rear_body = rear_outer.cut(rear_recess).cut(cavity)
    (
        rear_screen_support,
        screen_face_pocket,
        screen_pcb_envelope,
        screen_edge_stops,
        screen_face,
        screen_active,
    ) = build_rear_screen_mount(cavity)

    upper_left_stop_box = screen_edge_stops[1].BoundBox
    screen_stop_bridge = Part.makeBox(
        upper_left_stop_box.XLength,
        upper_left_stop_box.YLength,
        DEFAULTS.minimum_feature_mm,
        App.Vector(
            upper_left_stop_box.XMin,
            upper_left_stop_box.YMin,
            upper_left_stop_box.ZMin - 0.20,
        ),
    )

    if rear_screen_support.common(rear_body).Volume <= 1e-5:
        raise RuntimeError("Rear screen support does not fuse to the rear shell")
    rear_body = rear_body.fuse(rear_screen_support).multiFuse(
        [*screen_edge_stops, screen_stop_bridge]
    )
    add_feature(document, "BlossomRecessRear", rear_recess)
    add_feature(document, "RearScreenSupport", rear_screen_support)
    add_feature(document, "RearScreenFacePocket", screen_face_pocket)
    add_feature(document, "RearScreenPcbEnvelope", screen_pcb_envelope)
    add_feature(document, "RearScreenEdgeStop1", screen_edge_stops[0])
    add_feature(document, "RearScreenEdgeStop2", screen_edge_stops[1])
    add_feature(document, "RearScreenEdgeStop3", screen_edge_stops[2])
    add_feature(document, "RearScreenEdgeStop4", screen_edge_stops[3])
    add_feature(document, "RearScreenStopBridge", screen_stop_bridge)
    add_feature(document, "ScreenFaceEnvelope", screen_face)
    add_feature(document, "ScreenActiveEnvelope", screen_active)

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
    buzzer_service_core = Part.Face(
        wire_profile(
            outer_wire,
            svg_scale * service_guard_ratio,
            buzzer_front_z,
        )
    ).extrude(
        App.Vector(0.0, 0.0, DEFAULTS.buzzer_service_depth_mm)
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

    # Rear-face USB-C window: x width × y height × z travel.
    usb_y = DEFAULTS.usb_window_bottom_y_mm
    usb_x = DEFAULTS.usb_window_center_x_mm - DEFAULTS.usb_window_mm[0] / 2.0
    usb_parts = build_usb_structure(usb_x, usb_y)
    usb_window = usb_parts["window"]
    (
        guide_left,
        guide_right,
        force_plate,
        bridge_left,
        bridge_right,
        usb_anchor_left,
        usb_anchor_right,
    ) = usb_parts["supports"]
    rear_body = rear_body.cut(usb_window)
    add_feature(document, "UsbWindow", usb_window)
    rear_body = rear_body.multiFuse(
        [
            guide_left,
            guide_right,
            force_plate,
            bridge_left,
            bridge_right,
            usb_anchor_left,
            usb_anchor_right,
        ]
    )
    add_feature(document, "UsbGuideLeft", guide_left)
    add_feature(document, "UsbGuideRight", guide_right)
    add_feature(document, "UsbForcePlate", force_plate)
    add_feature(document, "UsbForcePlateBridgeLeft", bridge_left)
    add_feature(document, "UsbForcePlateBridgeRight", bridge_right)
    add_feature(document, "UsbSupportAnchorLeft", usb_anchor_left)
    add_feature(document, "UsbSupportAnchorRight", usb_anchor_right)
    closure_keepouts = Part.makeCompound(
        [
            screen_face_pocket,
            screen_pcb_envelope,
            *screen_edge_stops,
            screen_stop_bridge,
            screen_face,
            screen_active,
            usb_window,
            guide_left,
            guide_right,
            force_plate,
            bridge_left,
            bridge_right,
            usb_anchor_left,
            usb_anchor_right,
            buzzer_service_envelope,
        ]
    )

    closure = build_four_point_slide_closure(
        front_body,
        rear_body,
        rear_exterior_guard,
        buzzer_envelope,
        closure_keepouts,
    )
    front_body = closure["front"]
    rear_body = closure["rear"]
    electronic_cavity = cavity.cut(
        closure["electronic_cavity_reliefs"]
    ).removeSplitter()
    for lower_part in (
        *closure["front_lower_tabs"],
        *closure["front_lower_bearings"],
        *closure["front_lower_roots"],
    ):
        if lower_part.common(electronic_cavity).Volume > 1e-5:
            raise RuntimeError("Four-point closure enters ElectronicCavity")
    add_feature(document, "ElectronicCavity", electronic_cavity)
    add_feature(document, "FrontClosureBlank", closure["front_blank"])
    add_feature(document, "RearClosureBlank", closure["rear_blank"])
    add_feature(document, "FrontUpperTabLeft", closure["front_upper_tabs"][0])
    add_feature(document, "FrontUpperTabRight", closure["front_upper_tabs"][1])
    add_feature(document, "FrontUpperRootLeft", closure["front_upper_roots"][0])
    add_feature(document, "FrontUpperRootRight", closure["front_upper_roots"][1])
    add_feature(document, "RearUpperEntryFunnelLeft", closure["rear_upper_entries"][0])
    add_feature(document, "RearUpperEntryFunnelRight", closure["rear_upper_entries"][1])
    add_feature(
        document,
        "RearUpperBlindSocketLeft",
        closure["rear_upper_blind_sockets"][0],
    )
    add_feature(
        document,
        "RearUpperBlindSocketRight",
        closure["rear_upper_blind_sockets"][1],
    )
    add_feature(document, "RearUpperSocketLeft", closure["rear_upper_sockets"][0])
    add_feature(document, "RearUpperSocketRight", closure["rear_upper_sockets"][1])
    add_feature(document, "FrontLowerTabLeft", closure["front_lower_tabs"][0])
    add_feature(document, "FrontLowerTabRight", closure["front_lower_tabs"][1])
    add_feature(document, "FrontLowerBearingLeft", closure["front_lower_bearings"][0])
    add_feature(document, "FrontLowerBearingRight", closure["front_lower_bearings"][1])
    add_feature(document, "FrontLowerRootLeft", closure["front_lower_roots"][0])
    add_feature(document, "FrontLowerRootRight", closure["front_lower_roots"][1])
    add_feature(document, "RearLowerGuideLeft", closure["rear_lower_guides"][0])
    add_feature(document, "RearLowerGuideRight", closure["rear_lower_guides"][1])
    add_feature(document, "RearLowerDetentLeft", closure["rear_lower_detents"][0])
    add_feature(document, "RearLowerDetentRight", closure["rear_lower_detents"][1])
    add_feature(document, "AssemblyFrontTilted", closure["assembly_front_tilted"])
    add_feature(
        document,
        "AssemblyFrontFlatUnlocked",
        closure["assembly_front_flat_unlocked"],
    )
    add_feature(document, "AssemblyFrontLocked", closure["assembly_front_locked"])
    add_feature(document, "AssemblyPoseTilted", closure["assembly_pose_tilted"])
    add_feature(
        document,
        "AssemblyPoseFlatUnlocked",
        closure["assembly_pose_flat_unlocked"],
    )
    add_feature(document, "AssemblyPoseLocked", closure["assembly_pose_locked"])
    add_feature(document, "RearClosureExteriorGuard", rear_exterior_guard)
    front = add_feature(document, "FrontShell", front_body, True)
    front.addProperty("App::PropertyString", "Purpose").Purpose = "Front shell retaining the ST7789 screen face"
    front.addProperty("App::PropertyLength", "ReliefDepth").ReliefDepth = DEFAULTS.relief_depth_mm
    front.addProperty("App::PropertyLength", "TransitionRadius").TransitionRadius = min(front_radii)
    front.addProperty("App::PropertyInteger", "WhiteBlockCount").WhiteBlockCount = len(front_recesses)
    add_feature(document, "FrontView", Part.makeCompound([front_body]))
    rear = add_feature(document, "RearCover", rear_body, True)
    rear.addProperty("App::PropertyString", "Purpose").Purpose = "Easy-open rear cover with USB retention"
    rear.addProperty("App::PropertyLength", "ReliefDepth").ReliefDepth = DEFAULTS.relief_depth_mm
    rear.addProperty("App::PropertyLength", "TransitionRadius").TransitionRadius = min(rear_radii)
    rear.addProperty("App::PropertyInteger", "WhiteBlockCount").WhiteBlockCount = len(rear_recesses)

    document.recompute()
    document.saveAs(os.path.join(OUTPUT_DIR, "blossom-enclosure.FCStd"))
    step_path = os.path.join(OUTPUT_DIR, "blossom-enclosure.step")
    Import.export([front, rear], step_path)
    export_print_mesh(front, "blossom-front.stl")
    export_print_mesh(rear, "blossom-rear.stl")
    with open(os.path.join(OUTPUT_DIR, "review-dimensions.txt"), "w", encoding="utf-8") as review:
        review.write("Outer width: 56.0 mm\n")
        review.write("Overall thickness: 20.6 mm\n")
        review.write("Internal envelope: 28.0 x 39.5 x 16.0 mm\n")
        review.write("Front and rear relief: 1.5 mm; target transition radius: R0.6 mm\n")
        review.write(
            "Front hex point-to-point: "
            f"{DEFAULTS.front_hex_point_to_point_mm:.2f} mm; "
            "across flats: "
            f"{DEFAULTS.front_hex_across_flats_mm:.2f} mm\n"
        )
        review.write(
            "Raised screen face: 26.00 x 29.00 mm; pocket: "
            f"{DEFAULTS.screen_pocket_mm[0]:.2f} x "
            f"{DEFAULTS.screen_pocket_mm[1]:.2f} mm\n"
        )
        review.write("USB opening: 13.4 x 8.8 mm; adapter exposure: 7.0 mm\n")
        review.write("Buzzer opening: none\n")
        review.write("Upper latch entry angle: 35 deg; nominal centre Y: 21.60 mm\n")
        review.write("Lower lock travel: 2.50 mm upward; detent: 0.25 mm\n")
        review.write("Latch side clearances: upper 0.25 mm; lower guide 0.30 mm\n")
    print("BUILD PASS", OUTPUT_DIR)


if __name__ == "__main__":
    build()
