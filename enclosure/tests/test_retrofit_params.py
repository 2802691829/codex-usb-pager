import sys
from pathlib import Path


CAD = Path(__file__).parents[1] / "cad"
sys.path.insert(0, str(CAD))
from enclosure_params import DEFAULTS


def test_retrofit_contract_is_exact():
    assert DEFAULTS.closure_style == "front_four_rigid_slide"
    assert DEFAULTS.usb_vertical_shift_mm == 5.0
    assert DEFAULTS.screen_face_clearance_mm == 0.15
    assert DEFAULTS.screen_pcb_clearance_mm == 0.10
    assert DEFAULTS.screen_pocket_mm == (26.30, 29.30)
    assert DEFAULTS.screen_pcb_pocket_mm == (27.98, 39.42)
    assert DEFAULTS.screen_face_setback_mm == 0.20
    assert DEFAULTS.screen_face_setback_range_mm == (0.10, 0.30)
    assert DEFAULTS.top_tongue_mm == (5.0, 1.0, 2.5)
    assert DEFAULTS.top_tongue_nominal_centres_mm == (
        (-10.0, 19.75),
        (10.0, 19.75),
    )
    assert DEFAULTS.top_tongue_approved_y_exception_mm == 21.60
    assert DEFAULTS.top_tongue_centres_mm == ((-10.0, 21.60), (10.0, 21.60))
    assert DEFAULTS.latch_entry_angle_deg == 35.0
    assert DEFAULTS.front_latch_hook_mm == (4.0, 1.2, 2.2)
    assert DEFAULTS.front_latch_centres_mm == ((-15.0, -9.0), (15.0, -9.0))
    assert DEFAULTS.lower_guide_clearance_mm == 0.30
    assert DEFAULTS.closure_slide_travel_mm == 2.50
    assert DEFAULTS.closure_detent_mm == 0.25
    assert DEFAULTS.bottom_edge_opening is True


def test_usb_shift_is_derived_from_the_unchanged_baseline():
    assert DEFAULTS.usb_window_bottom_y_mm == (
        DEFAULTS.usb_window_baseline_bottom_y_mm + 5.0
    )


def test_frozen_exterior_dimensions_remain_unchanged():
    assert DEFAULTS.blossom_target_width_mm == 56.0
    assert DEFAULTS.maximum_thickness_mm == 20.6
    assert DEFAULTS.front_hex_point_to_point_mm == 23.5
    assert round(DEFAULTS.front_hex_across_flats_mm, 2) == 20.35
    assert DEFAULTS.relief_depth_mm == 1.5


def test_relief_transition_prefers_the_approved_radius():
    assert DEFAULTS.relief_transition_radius_mm == 0.60
    assert DEFAULTS.relief_radius_fallbacks_mm[0] == 0.60


def test_internal_envelope_dimensions_remain_unchanged():
    assert DEFAULTS.internal_envelope_mm == (28.0, 39.5, 16.0)
