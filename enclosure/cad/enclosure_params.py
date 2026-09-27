"""Approved dimensions for the Blossom resin enclosure, in millimetres."""

from dataclasses import dataclass
from math import sqrt


@dataclass(frozen=True)
class EnclosureParameters:
    blossom_target_width_mm: float = 56.0
    internal_envelope_mm: tuple[float, float, float] = (28.0, 39.5, 16.0)
    nominal_wall_mm: float = 1.5
    minimum_feature_mm: float = 0.8
    relief_depth_mm: float = 1.5
    relief_transition_radius_mm: float = 0.6
    relief_radius_fallbacks_mm: tuple[float, ...] = (0.6, 0.5, 0.4, 0.3)
    minimum_relief_backing_mm: float = 0.8
    front_seam_z_mm: float = 2.3
    maximum_thickness_mm: float = 20.6
    front_hex_point_to_point_mm: float = 23.5
    usb_window_mm: tuple[float, float] = (13.4, 8.8)
    usb_corner_radius_mm: float = 2.0
    usb_adapter_exposure_mm: float = 7.0
    usb_opening_face: str = "rear"
    usb_window_center_x_mm: float = 0.0
    usb_bottom_offset_from_screen_pcb_mm: float = 3.5
    usb_vertical_shift_mm: float = 5.0
    # Internal clearance between the display PCB and the USB adapter.  A brace
    # may use this space, but the rear port itself must remain fully open.
    usb_force_plate_gap_mm: float = 5.0
    usb_port_bottom_clear: bool = True
    assembly_clearance_mm: float = 0.30
    screen_pcb_mm: tuple[float, float] = (27.78, 39.22)
    screen_face_mm: tuple[float, float] = (26.0, 29.0)
    screen_active_mm: tuple[float, float] = (23.40, 23.40)
    screen_face_to_pcb_mm: float = 2.0
    screen_hole_diameter_mm: float = 2.0
    screen_hole_edge_offset_mm: float = 2.5
    screen_face_clearance_mm: float = 0.15
    screen_pcb_clearance_mm: float = 0.10
    screen_face_setback_mm: float = 0.20
    screen_face_setback_range_mm: tuple[float, float] = (0.10, 0.30)
    screen_edge_stop_mm: tuple[float, float, float] = (3.0, 1.2, 1.2)
    screen_face_top_offset_from_pcb_mm: float = 5.0
    screen_black_border_mm: float = 0.5
    screen_non_display_bottom_mm: float = 3.0
    screen_slot_depth_mm: float = 1.0
    screen_post_diameter_mm: float = 1.65
    screen_post_boss_diameter_mm: float = 3.2
    screen_post_height_mm: float = 3.2
    screen_retention_overlap_mm: float = 0.25
    screen_active_offset_to_header_mm: float = 1.64
    top_tongue_mm: tuple[float, float, float] = (5.0, 1.0, 2.5)
    top_tongue_nominal_centres_mm: tuple[tuple[float, float], ...] = (
        (-10.0, 19.75),
        (10.0, 19.75),
    )
    # Approved 2026-08-08 exception: the fixed 19.75 mm centres sweep through
    # the fixed screen PCB during the required flat and tilted assembly poses.
    # Moving the internal tabs to 21.60 mm preserves the screen and exterior.
    top_tongue_approved_y_exception_mm: float = 21.60
    top_tongue_clearance_mm: float = 0.25
    top_tongue_bottom_clearance_mm: float = 0.30
    lower_guide_clearance_mm: float = 0.30
    closure_slide_travel_mm: float = 2.50
    closure_detent_mm: float = 0.25
    front_latch_hook_mm: tuple[float, float, float] = (4.0, 1.2, 2.2)
    front_latch_centres_mm: tuple[tuple[float, float], ...] = (
        (-15.0, -9.0),
        (15.0, -9.0),
    )
    buzzer_clearance_mm: tuple[float, float] = (12.0, 11.5)
    buzzer_centre_mm: tuple[float, float] = (-9.0, 4.36)
    buzzer_service_window_mm: tuple[float, float] = (16.0, 23.5)
    buzzer_service_window_origin_mm: tuple[float, float] = (-28.0, -5.5)
    buzzer_service_corner_radius_mm: float = 3.0
    buzzer_service_wall_mm: float = 1.50
    buzzer_retainer_clearance_mm: float = 0.20
    latch_arm_mm: tuple[float, float, float] = (13.0, 4.0, 1.0)
    latch_root_radius_mm: float = 1.0
    latch_engagement_mm: float = 0.35
    latch_hook_running_clearance_mm: float = 0.05
    latch_entry_angle_deg: float = 35.0
    latch_release_angle_deg: float = 20.0
    latch_slot_clearance_mm: float = 0.30
    rear_exterior_guard_mm: float = 1.0
    fingernail_notch_mm: tuple[float, float, float] = (10.0, 1.2, 0.8)
    closure_style: str = "front_four_rigid_slide"
    bottom_edge_opening: bool = True

    @property
    def front_hex_across_flats_mm(self) -> float:
        return self.front_hex_point_to_point_mm * sqrt(3.0) / 2.0

    @property
    def front_hex_across_corners_mm(self) -> float:
        return self.front_hex_point_to_point_mm

    @property
    def screen_face_top_y_mm(self) -> float:
        return round(
            self.screen_pcb_center_y_mm
            + self.screen_pcb_mm[1] / 2.0
            - self.screen_face_top_offset_from_pcb_mm,
            2,
        )

    @property
    def top_tongue_centres_mm(self) -> tuple[tuple[float, float], ...]:
        return tuple(
            (centre_x, self.top_tongue_approved_y_exception_mm)
            for centre_x, _ in self.top_tongue_nominal_centres_mm
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

    @property
    def front_hex_top_margin_mm(self) -> float:
        return self.screen_black_border_mm

    @property
    def front_hex_bottom_margin_mm(self) -> float:
        return round(
            self.screen_face_mm[1]
            - self.front_hex_top_margin_mm
            - self.front_hex_point_to_point_mm,
            2,
        )

    @property
    def screen_pcb_pocket_mm(self) -> tuple[float, float]:
        extra = 2.0 * self.screen_pcb_clearance_mm
        return (
            round(self.screen_pcb_mm[0] + extra, 2),
            round(self.screen_pcb_mm[1] + extra, 2),
        )

    @property
    def screen_face_front_z_mm(self) -> float:
        return round(self.front_seam_z_mm + self.screen_face_setback_mm, 2)

    @property
    def usb_window_baseline_bottom_y_mm(self) -> float:
        return round(
            self.screen_pcb_bottom_y_mm
            - self.usb_bottom_offset_from_screen_pcb_mm,
            2,
        )

    @property
    def usb_window_bottom_y_mm(self) -> float:
        return round(
            self.usb_window_baseline_bottom_y_mm
            + self.usb_vertical_shift_mm,
            2,
        )

    @property
    def screen_pocket_mm(self) -> tuple[float, float]:
        extra = 2.0 * self.screen_face_clearance_mm
        return (
            round(self.screen_face_mm[0] + extra, 2),
            round(self.screen_face_mm[1] + extra, 2),
        )

    @property
    def screen_pcb_center_y_mm(self) -> float:
        return -self.screen_active_offset_to_header_mm

    @property
    def screen_pcb_bottom_y_mm(self) -> float:
        return round(
            self.screen_pcb_center_y_mm - self.screen_pcb_mm[1] / 2.0,
            2,
        )

    @property
    def internal_envelope_center_y_mm(self) -> float:
        return self.screen_pcb_center_y_mm

    @property
    def internal_envelope_bottom_y_mm(self) -> float:
        return round(
            self.internal_envelope_center_y_mm
            - self.internal_envelope_mm[1] / 2.0,
            2,
        )

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

    @property
    def screen_post_centres_mm(self) -> tuple[tuple[float, float], ...]:
        x = self.screen_pcb_mm[0] / 2.0 - self.screen_hole_edge_offset_mm
        y = self.screen_pcb_mm[1] / 2.0 - self.screen_hole_edge_offset_mm
        centre_y = self.screen_pcb_center_y_mm
        return (
            (round(-x, 2), round(centre_y + y, 2)),
            (round(x, 2), round(centre_y + y, 2)),
            (round(-x, 2), round(centre_y - y, 2)),
            (round(x, 2), round(centre_y - y, 2)),
        )


DEFAULTS = EnclosureParameters()
