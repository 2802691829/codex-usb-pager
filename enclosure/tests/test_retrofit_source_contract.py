import hashlib
from pathlib import Path
import xml.etree.ElementTree as ElementTree


def test_handoff_scripts_use_only_local_cad_and_output_paths():
    cad = Path(__file__).parents[1] / "cad"
    build = (cad / "build_blossom_enclosure.py").read_text("utf-8")
    audit = (cad / "audit_blossom_enclosure.py").read_text("utf-8")
    assert "from enclosure_params import DEFAULTS" in build
    assert "from enclosure_params import DEFAULTS" in audit
    assert "from enclosure.cad" not in build
    assert "from enclosure.cad" not in audit
    assert 'BASELINE_OUTPUT_DIR = os.path.join(HANDOFF_DIR, "outputs")' in build
    assert '"openai-blossom-print-clean.svg"' in build


def test_print_clean_svg_preserves_the_frozen_source_and_path_structure():
    handoff = Path(__file__).parents[1]
    original = handoff.parent / "enclosure_handoff_2026-07-28" / "openai-blossom.svg"
    clean = handoff / "cad" / "openai-blossom-print-clean.svg"

    assert hashlib.sha256(original.read_bytes()).hexdigest() == (
        "c799a3b46d8320cbd50e2d9718caab193f44fd4cd87d23f25f0c454bfcc2507a"
    )
    assert clean.is_file()

    original_root = ElementTree.parse(original).getroot()
    clean_root = ElementTree.parse(clean).getroot()
    original_paths = original_root.findall("{http://www.w3.org/2000/svg}path")
    clean_paths = clean_root.findall("{http://www.w3.org/2000/svg}path")
    assert clean_root.attrib["viewBox"] == original_root.attrib["viewBox"]
    assert len(clean_paths) == len(original_paths)
    assert "V421.415" not in clean_paths[0].attrib["d"]
    assert "M367.283 421.412" in clean_paths[0].attrib["d"]
    assert "M233.553 368.452" not in clean_paths[0].attrib["d"]
    assert "V475.968" not in clean_paths[0].attrib["d"]
    assert "H234.614Z" not in clean_paths[0].attrib["d"]


def test_builder_never_overwrites_the_approved_baseline():
    build = (Path(__file__).parents[1] / "cad" / "build_blossom_enclosure.py").read_text("utf-8")
    assert 'OUTPUT_DIR = os.path.join(BASELINE_OUTPUT_DIR, "four-latch-retrofit")' in build
    assert 'document.saveAs(os.path.join(OUTPUT_DIR, "blossom-enclosure.FCStd"))' in build


def test_builder_derives_electronic_cavity_from_internal_envelope():
    build = (Path(__file__).parents[1] / "cad" / "build_blossom_enclosure.py").read_text("utf-8")
    assert (
        "cavity_width, cavity_height, cavity_depth = "
        "DEFAULTS.internal_envelope_mm"
    ) in build
    assert "        cavity_width,\n        cavity_height,\n        cavity_depth," in build


def test_screen_mount_is_owned_only_by_the_rear_shell():
    build = (Path(__file__).parents[1] / "cad" / "build_blossom_enclosure.py").read_text("utf-8")
    assert "def build_rear_screen_mount(" in build
    assert "front_body = front_body.cut(front_hex_cut)" in build
    assert "front_body.fuse(screen_mount)" not in build
    assert '"RearScreenSupport"' in build
    assert '"RearScreenEdgeStop1"' in build
    assert '"RearScreenEdgeStop4"' in build
    assert "rear_body = rear_body.fuse(rear_screen_support)" in build
    assert "screen_backing_plate" not in build
    assert "rear_screen_support = support_ring.removeSplitter()" in build


def test_usb_window_and_supports_share_one_shifted_origin():
    build = (Path(__file__).parents[1] / "cad" / "build_blossom_enclosure.py").read_text("utf-8")
    assert "usb_y = DEFAULTS.usb_window_bottom_y_mm" in build
    assert "def build_usb_structure(usb_x, usb_y):" in build
    assert "usb_parts = build_usb_structure(usb_x, usb_y)" in build
    assert "usb_window_baseline_bottom_y_mm" not in build
    for token in ("usb_window", "guide_left", "guide_right", "force_plate", "bridge_left", "bridge_right"):
        assert token in build


def test_closure_has_four_rigid_points_and_no_flexible_arms():
    build = (Path(__file__).parents[1] / "cad" / "build_blossom_enclosure.py").read_text("utf-8")
    for name in (
        '"FrontUpperTabLeft"', '"FrontUpperTabRight"',
        '"RearUpperSocketLeft"', '"RearUpperSocketRight"',
        '"FrontLowerTabLeft"', '"FrontLowerTabRight"',
        '"RearLowerGuideLeft"', '"RearLowerGuideRight"',
        '"RearLowerDetentLeft"', '"RearLowerDetentRight"',
        '"AssemblyFrontTilted"', '"AssemblyFrontFlatUnlocked"',
        '"AssemblyFrontLocked"',
        '"AssemblyPoseTilted"', '"AssemblyPoseFlatUnlocked"',
        '"AssemblyPoseLocked"',
    ):
        assert name in build
    assert "RearLatchArmLeft" not in build
    assert "RearLatchArmRight" not in build
    assert "latch_arm_mm" not in build


def test_closure_uses_the_approved_motion():
    build = (Path(__file__).parents[1] / "cad" / "build_blossom_enclosure.py").read_text("utf-8")
    assert "def build_four_point_slide_closure(" in build
    assert "DEFAULTS.closure_slide_travel_mm" in build
    assert "DEFAULTS.closure_detent_mm" in build
    assert "DEFAULTS.latch_entry_angle_deg" in build
    assert "rear_closure_blank = rear_blank.cut(front_blank)" not in build


def test_audit_covers_retrofit_geometry_and_immutable_baseline():
    audit = (
        Path(__file__).parents[1] / "cad" / "audit_blossom_enclosure.py"
    ).read_text("utf-8")

    assert "def audit_document(document_path: str, baseline_path: str)" in audit
    for field in (
        '"usb_vertical_shift_mm"',
        '"front_screen_mount_volume_mm3"',
        '"rear_screen_support_count"',
        '"screen_face_setback_mm"',
        '"closure_point_count"',
        '"slide_travel_mm"',
        '"tilted_pose_interference_mm3"',
        '"flat_unlocked_pose_interference_mm3"',
        '"locked_pose_interference_mm3"',
        '"front_frozen_exterior_delta_mm3"',
        '"rear_frozen_exterior_delta_mm3"',
        '"front_is_single_valid_solid"',
        '"rear_is_single_valid_solid"',
        '"screen_keepout_interference_mm3"',
        '"usb_keepout_interference_mm3"',
        '"buzzer_keepout_interference_mm3"',
        '"buzzer_hole_absent"',
        '"minimum_latch_root_mm"',
        '"minimum_guide_wall_mm"',
        '"baseline_overall_thickness_mm"',
        '"overall_thickness_delta_mm"',
        '"front_visible_surface_delta_mm2"',
        '"rear_visible_surface_delta_mm2"',
        '"rear_screen_support_status"',
        '"front_printable_closed_solid"',
        '"rear_printable_closed_solid"',
        '"known_thin_feature_minimums_mm"',
    ):
        assert field in audit

    assert "symmetric_difference_volume" not in audit
    assert "POSE_NAMES" in audit
    assert "pose_keepout_report" in audit
    assert "output.write_text(payload + \"\\n\", encoding=\"utf-8\")" in audit
    assert "raise SystemExit(1)" in audit


def test_audit_thickness_uses_the_approved_immutable_baseline():
    audit = (
        Path(__file__).parents[1] / "cad" / "audit_blossom_enclosure.py"
    ).read_text("utf-8")

    assert (
        'report["overall_thickness_delta_mm"] <= TOLERANCE_MM'
    ) in audit
    assert "abs(retrofit_thickness - baseline_thickness)" not in audit


def test_audit_does_not_misclassify_the_electronic_cavity_as_screen_keepout():
    audit = (
        Path(__file__).parents[1] / "cad" / "audit_blossom_enclosure.py"
    ).read_text("utf-8")

    screen_keepouts = audit[
        audit.index("screen_keepouts = [") : audit.index("usb_keepouts = [")
    ]
    assert '"ElectronicCavity",' not in screen_keepouts


def test_task6_render_contract_targets_the_retrofit_and_four_latch_review():
    render = (
        Path(__file__).parents[1] / "cad" / "render_blossom_review.py"
    ).read_text("utf-8")

    assert '"four-latch-retrofit"' in render
    assert '"review-screen-setback-section.png"' in render
    assert '"review-four-latch-cutaway.png"' in render
    assert '"review-assembly-1-tilted.png"' in render
    assert '"review-assembly-2-flat.png"' in render
    assert '"review-assembly-3-locked.png"' in render
    assert '"review-usb-shift.png"' in render
    for name in (
        "RearScreenSupport",
        "RearScreenEdgeStop1",
        "RearUpperSocketLeft",
        "RearLowerGuideLeft",
        "RearLowerDetentLeft",
        "FrontUpperTabLeft",
        "FrontLowerTabLeft",
        "AssemblyPoseTilted",
        "AssemblyPoseFlatUnlocked",
        "AssemblyPoseLocked",
        "UsbWindow",
    ):
        assert f'"{name}"' in render
    for obsolete_name in (
        "ScreenPost1",
        "ScreenRetainerLeft",
        "RearLatchArmLeft",
        "RearLatchPocketLeft",
        "BuzzerEnvelope",
    ):
        assert obsolete_name not in render


def test_task6_audit_contract_includes_exported_stl_mesh_gates():
    audit = (
        Path(__file__).parents[1] / "cad" / "audit_blossom_enclosure.py"
    ).read_text("utf-8")

    for field in (
        '"stl_meshes"',
        "stl_matches_fcstd_bounds",
        "stl_matches_step_bounds",
        "stl_watertight",
        "stl_two_manifold",
        "stl_no_self_intersections",
        "stl_no_degenerate_triangles",
        "stl_single_shell",
        "stl_consistent_normals",
        "stl_positive_oriented_volume",
        "gmsh_check_passed",
        "gmsh_check_has_warning",
    ):
        assert field in audit


def test_task6_exports_each_print_mesh_from_its_own_temporary_step():
    build = (
        Path(__file__).parents[1] / "cad" / "build_blossom_enclosure.py"
    ).read_text("utf-8")

    assert "def export_print_mesh(shell, filename: str)" in build
    assert 'Import.export([shell], str(temp_step_path))' in build
    assert '"-2"' in build
    assert '"-clmin", str(GMSH_MIN_SIZE_MM)' in build
    assert '"-clmax", str(GMSH_MAX_SIZE_MM)' in build
    assert '"-clcurv", str(GMSH_CURVATURE_NODES)' in build
    assert "blossom-enclosure-gmsh.stl" not in build


def test_blossom_recess_cutters_preserve_the_approved_compound_geometry():
    build = (
        Path(__file__).parents[1] / "cad" / "build_blossom_enclosure.py"
    ).read_text("utf-8")

    assert "def union_recess_cutters(cutters):" not in build
    assert "front_recess = Part.makeCompound(front_recesses)" in build
    assert "rear_recess = Part.makeCompound(rear_recesses)" in build


def test_builder_uses_print_clean_svg_and_the_approved_recess_transition():
    build = (
        Path(__file__).parents[1] / "cad" / "build_blossom_enclosure.py"
    ).read_text("utf-8")

    assert '"openai-blossom-print-clean.svg"' in build
    assert "def rounded_recess_cutter(" in build
    assert "Part.makeLoft(profiles, True, False)" in build
    assert "filleted_recess_cutter" not in build


def test_review_dimensions_record_the_four_latch_assembly_motion():
    build = (
        Path(__file__).parents[1] / "cad" / "build_blossom_enclosure.py"
    ).read_text("utf-8")

    assert "Upper latch entry angle: 35 deg; nominal centre Y: 21.60 mm" in build
    assert "Lower lock travel: 2.50 mm upward; detent: 0.25 mm" in build
    assert "Latch side clearances: upper 0.25 mm; lower guide 0.30 mm" in build


def test_step_hierarchy_counts_only_imported_leaf_features():
    audit = (
        Path(__file__).parents[1] / "cad" / "audit_blossom_enclosure.py"
    ).read_text("utf-8")

    assert 'item.TypeId == "Part::Feature"' in audit
    assert "solid.isSame(existing)" not in audit
    assert "signature = (round(solid.Volume, 6)" not in audit
