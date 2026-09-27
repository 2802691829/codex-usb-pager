from pathlib import Path

import cv2
import numpy as np

from petal_preview_geometry import (
    READY_ASSEMBLED_RADIUS,
    READY_PETAL_WIDTH,
    READY_SEPARATION,
    load_exact_petal,
    orient_petal_ready,
    render_ready_pieces,
)


ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "assets" / "reference-petal-exact.png"


def source_black_mask() -> np.ndarray:
    source = cv2.imread(str(REFERENCE), cv2.IMREAD_GRAYSCALE)
    assert source is not None
    mask = np.where(source < 128, 255, 0).astype(np.uint8)
    x, y, width, height = cv2.boundingRect(mask)
    return mask[y : y + height, x : x + width]


def test_loaded_petal_is_pixel_exact_black_shape():
    expected = source_black_mask()
    actual = load_exact_petal(REFERENCE)

    assert actual.shape == expected.shape
    assert np.array_equal(actual, expected)


def test_ready_orientation_is_counterclockwise_quarter_turn_only():
    petal = load_exact_petal(REFERENCE)

    assert np.array_equal(
        orient_petal_ready(petal),
        cv2.rotate(petal, cv2.ROTATE_90_COUNTERCLOCKWISE),
    )


def test_ready_layout_has_six_separate_pieces_and_clear_center():
    petal = load_exact_petal(REFERENCE)
    piece_masks, combined = render_ready_pieces(
        petal,
        canvas_size=900,
        petal_width=READY_PETAL_WIDTH,
        assembled_radius=READY_ASSEMBLED_RADIUS,
        separation=READY_SEPARATION,
        ready_orientation=True,
    )

    assert len(piece_masks) == 6
    top_bounds = cv2.boundingRect(piece_masks[0])
    assert max(top_bounds[2], top_bounds[3]) >= 236
    for left in range(6):
        for right in range(left + 1, 6):
            assert not np.any(
                cv2.bitwise_and(piece_masks[left], piece_masks[right])
            )

    component_count, _ = cv2.connectedComponents(
        np.where(combined > 0, 255, 0).astype(np.uint8)
    )
    assert component_count - 1 == 6
    center = combined[380:520, 380:520]
    assert np.count_nonzero(center) == 0


def test_full_ready_orbit_keeps_three_screen_pixels_inside_hexagon():
    petal = load_exact_petal(REFERENCE)
    _, combined = render_ready_pieces(
        petal,
        canvas_size=900,
        petal_width=READY_PETAL_WIDTH,
        assembled_radius=READY_ASSEMBLED_RADIUS,
        separation=READY_SEPARATION,
        ready_orientation=True,
    )
    center = 450
    radius = 450
    half_width = round(radius * 3**0.5 / 2)
    hexagon = np.zeros((900, 900), dtype=np.uint8)
    cv2.fillPoly(
        hexagon,
        [np.array((
            (center, 0),
            (center + half_width, 225),
            (center + half_width, 675),
            (center, 900),
            (center - half_width, 675),
            (center - half_width, 225),
        ), dtype=np.int32)],
        255,
    )
    clearance = cv2.distanceTransform(hexagon, cv2.DIST_L2, 5)
    minimum = float("inf")
    for angle in range(0, 360, 3):
        matrix = cv2.getRotationMatrix2D((center, center), angle, 1.0)
        frame = cv2.warpAffine(
            combined,
            matrix,
            (900, 900),
            flags=cv2.INTER_NEAREST,
        )
        minimum = min(minimum, float(clearance[frame > 0].min()))
    assert minimum * 240 / 900 >= 3.0
