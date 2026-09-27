from pathlib import Path

import cv2
import numpy as np


READY_PETAL_WIDTH = 238
READY_ASSEMBLED_RADIUS = 116
READY_SEPARATION = 140


def load_exact_petal(reference_path: Path) -> np.ndarray:
    source = cv2.imread(str(reference_path), cv2.IMREAD_GRAYSCALE)
    if source is None:
        raise FileNotFoundError(reference_path)
    mask = np.where(source < 128, 255, 0).astype(np.uint8)
    x, y, width, height = cv2.boundingRect(mask)
    if width == 0 or height == 0:
        raise ValueError("reference petal contains no black pixels")
    return mask[y : y + height, x : x + width]


def orient_petal_ready(petal: np.ndarray) -> np.ndarray:
    return cv2.rotate(petal, cv2.ROTATE_90_COUNTERCLOCKWISE)


def _resize_mask(mask: np.ndarray, width: int) -> np.ndarray:
    height = round(mask.shape[0] * width / mask.shape[1])
    resized = cv2.resize(
        mask,
        (width, height),
        interpolation=cv2.INTER_AREA,
    )
    return np.where(resized >= 128, 255, 0).astype(np.uint8)


def _rotate_canvas(
    image: np.ndarray,
    angle: float,
    center: tuple[float, float],
) -> np.ndarray:
    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    return cv2.warpAffine(
        image,
        matrix,
        (image.shape[1], image.shape[0]),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=0,
    )


def radial_piece_masks(
    petal: np.ndarray,
    canvas_size: int,
    petal_width: int,
    radius: float,
    ready_orientation: bool = False,
) -> list[np.ndarray]:
    resized = _resize_mask(petal, petal_width)
    if ready_orientation:
        resized = orient_petal_ready(resized)
    center = canvas_size / 2.0
    layer = np.zeros((canvas_size, canvas_size), dtype=np.uint8)
    x = round(center - resized.shape[1] / 2.0)
    y = round(center - radius - resized.shape[0] / 2.0)
    layer[y : y + resized.shape[0], x : x + resized.shape[1]] = resized
    return [
        _rotate_canvas(layer, angle, (center, center))
        for angle in range(0, 360, 60)
    ]


def _pieces_overlap(pieces: list[np.ndarray]) -> bool:
    clearance_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    expanded = [
        cv2.dilate(
            np.where(piece >= 128, 255, 0).astype(np.uint8),
            clearance_kernel,
        )
        for piece in pieces
    ]
    for left in range(len(pieces)):
        for right in range(left + 1, len(pieces)):
            if np.any(cv2.bitwise_and(expanded[left], expanded[right])):
                return True
    return False


def render_ready_pieces(
    petal: np.ndarray,
    canvas_size: int,
    petal_width: int,
    assembled_radius: float,
    separation: float,
    ready_orientation: bool = False,
) -> tuple[list[np.ndarray], np.ndarray]:
    resized = _resize_mask(petal, petal_width)
    if ready_orientation:
        resized = orient_petal_ready(resized)
    radial_half_extent = resized.shape[0] / 2.0
    radius = assembled_radius + separation
    pieces = radial_piece_masks(
        petal,
        canvas_size=canvas_size,
        petal_width=petal_width,
        radius=radius,
        ready_orientation=ready_orientation,
    )
    while _pieces_overlap(pieces):
        radius += 2.0
        if radius + radial_half_extent >= canvas_size / 2.0:
            raise ValueError("ready petals cannot fit without overlap")
        pieces = radial_piece_masks(
            petal,
            canvas_size=canvas_size,
            petal_width=petal_width,
            radius=radius,
            ready_orientation=ready_orientation,
        )

    combined = np.zeros((canvas_size, canvas_size), dtype=np.uint8)
    for piece in pieces:
        combined = cv2.bitwise_or(combined, piece)
    return pieces, combined
