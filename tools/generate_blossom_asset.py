import argparse
import math
import os
import re
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image, ImageDraw


TOKEN_RE = re.compile(r"[A-Za-z]|[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?")
CANONICAL_PETAL_WIDTH_RATIO = 72 / 128
READY_MASK_SIZE = 228
READY_MASK_SUPERSAMPLE = 2
READY_SCENE_OFFSET = 6
READY_CENTER = 120
READY_RADIUS = 68
READY_SCALE_Q12 = 3604
READY_PETAL_CLOCKWISE_ANGLE = 32


def _cubic(p0, p1, p2, p3, t):
    u = 1.0 - t
    return (
        u * u * u * p0[0]
        + 3 * u * u * t * p1[0]
        + 3 * u * t * t * p2[0]
        + t * t * t * p3[0],
        u * u * u * p0[1]
        + 3 * u * u * t * p1[1]
        + 3 * u * t * t * p2[1]
        + t * t * t * p3[1],
    )


def flatten_path(path_data, curve_steps=18):
    tokens = TOKEN_RE.findall(path_data)
    index = 0
    command = None
    point = (0.0, 0.0)
    start = point
    subpath = []
    subpaths = []

    def number():
        nonlocal index
        value = float(tokens[index])
        index += 1
        return value

    def finish():
        nonlocal subpath
        if len(subpath) >= 3:
            subpaths.append(subpath)
        subpath = []

    while index < len(tokens):
        if tokens[index].isalpha():
            command = tokens[index]
            index += 1

        if command == "M":
            finish()
            point = (number(), number())
            start = point
            subpath = [point]
            command = "L"
        elif command == "L":
            point = (number(), number())
            subpath.append(point)
        elif command == "H":
            point = (number(), point[1])
            subpath.append(point)
        elif command == "V":
            point = (point[0], number())
            subpath.append(point)
        elif command == "C":
            control1 = (number(), number())
            control2 = (number(), number())
            end = (number(), number())
            origin = point
            for step in range(1, curve_steps + 1):
                subpath.append(_cubic(origin, control1, control2, end, step / curve_steps))
            point = end
        elif command in ("Z", "z"):
            if subpath and subpath[-1] != start:
                subpath.append(start)
            finish()
            point = start
            command = None
        else:
            raise ValueError(f"Unsupported SVG path command: {command}")

    finish()
    return subpaths


def rasterize_svg(svg_path, size=128, supersample=4):
    root = ET.parse(svg_path).getroot()
    view_box = [float(value) for value in root.attrib["viewBox"].split()]
    path = next(element for element in root.iter() if element.tag.endswith("path"))
    subpaths = flatten_path(path.attrib["d"])

    high_size = size * supersample
    scale_x = high_size / view_box[2]
    scale_y = high_size / view_box[3]
    image = Image.new("L", (high_size, high_size), 0)
    draw = ImageDraw.Draw(image)

    def signed_area(points):
        return sum(
            first[0] * second[1] - second[0] * first[1]
            for first, second in zip(points, points[1:])
        ) / 2.0

    outer = max(subpaths, key=lambda points: abs(signed_area(points)))
    outer_sign = 1 if signed_area(outer) >= 0 else -1
    ordered = [outer] + [subpath for subpath in subpaths if subpath is not outer]

    for subpath in ordered:
        polygon = [
            (
                round((x - view_box[0]) * scale_x),
                round((y - view_box[1]) * scale_y),
            )
            for x, y in subpath
        ]
        direction = 1 if signed_area(subpath) >= 0 else -1
        draw.polygon(polygon, fill=255 if direction == outer_sign else 0)

    image = image.resize((size, size), Image.Resampling.LANCZOS)
    return image.point(lambda value: min(15, max(0, (value * 15 + 127) // 255)))


def pack_4bpp(mask):
    values = list(mask.getdata())
    if len(values) % 2:
        values.append(0)
    return bytes((values[index] << 4) | values[index + 1] for index in range(0, len(values), 2))


def _signed_area(points):
    return sum(
        first[0] * second[1] - second[0] * first[1]
        for first, second in zip(points, points[1:])
    ) / 2.0


def _chamfer_distance(binary, width, height):
    diagonal = 1414
    straight = 1000
    infinity = 1 << 30
    distance = [0 if value else infinity for value in binary]

    for y in range(height):
        for x in range(width):
            index = y * width + x
            value = distance[index]
            if x:
                value = min(value, distance[index - 1] + straight)
            if y:
                value = min(value, distance[index - width] + straight)
            if x and y:
                value = min(value, distance[index - width - 1] + diagonal)
            if x + 1 < width and y:
                value = min(value, distance[index - width + 1] + diagonal)
            distance[index] = value

    for y in range(height - 1, -1, -1):
        for x in range(width - 1, -1, -1):
            index = y * width + x
            value = distance[index]
            if x + 1 < width:
                value = min(value, distance[index + 1] + straight)
            if y + 1 < height:
                value = min(value, distance[index + width] + straight)
            if x + 1 < width and y + 1 < height:
                value = min(value, distance[index + width + 1] + diagonal)
            if x and y + 1 < height:
                value = min(value, distance[index + width - 1] + diagonal)
            distance[index] = value
    return distance


def _outer_lobes(svg_path):
    root = ET.parse(svg_path).getroot()
    view_box = [float(value) for value in root.attrib["viewBox"].split()]
    path = next(element for element in root.iter() if element.tag.endswith("path"))
    subpaths = flatten_path(path.attrib["d"])
    outer = max(subpaths, key=lambda points: abs(_signed_area(points)))
    holes = [subpath for subpath in subpaths if subpath is not outer]
    center_x = view_box[0] + view_box[2] / 2.0
    center_y = view_box[1] + view_box[3] / 2.0

    def centroid(points):
        return (
            sum(point[0] for point in points) / len(points),
            sum(point[1] for point in points) / len(points),
        )

    hole_centers = [(hole, centroid(hole)) for hole in holes]
    outer_holes = sorted(
        hole_centers,
        key=lambda item: (
            (item[1][0] - center_x) ** 2 + (item[1][1] - center_y) ** 2
        ),
        reverse=True,
    )[:6]
    outer_holes.sort(
        key=lambda item: math.atan2(
            item[1][1] - center_y, item[1][0] - center_x
        )
    )
    return view_box, [hole for hole, _ in outer_holes]


def load_reference_petal(reference_path: Path) -> Image.Image:
    source = Image.open(reference_path).convert("L")
    foreground = source.point(lambda value: 255 if value < 128 else 0)
    bounds = foreground.getbbox()
    if bounds is None:
        raise ValueError("reference petal contains no black pixels")
    return foreground.crop(bounds)


def rasterize_reference_petal(
    reference_path: Path,
    size: int = 128,
) -> Image.Image:
    source = load_reference_petal(reference_path)
    target_width = max(1, round(size * CANONICAL_PETAL_WIDTH_RATIO))
    target_height = max(
        1,
        round(source.height * target_width / source.width),
    )
    resized = source.resize(
        (target_width, target_height),
        Image.Resampling.LANCZOS,
    )
    quantized = resized.point(
        lambda value: min(15, max(0, (value * 15 + 127) // 255))
    )
    canvas = Image.new("L", (size, size), 0)
    canvas.paste(
        quantized,
        ((size - target_width) // 2, (size - target_height) // 2),
    )
    return canvas


def rasterize_petals(
    reference_path: Path,
    size: int = 128,
) -> list[Image.Image]:
    canonical = rasterize_reference_petal(reference_path, size=size)
    return [canonical.copy() for _ in range(6)]


def _sin_q15(index: int) -> int:
    return round(math.sin(2 * math.pi * (index & 0xFF) / 256) * 32767)


def compose_ready_mask(
    petal: Image.Image,
    canvas_size: int = READY_MASK_SIZE * READY_MASK_SUPERSAMPLE,
) -> Image.Image:
    if petal.size[0] != petal.size[1]:
        raise ValueError("ready petal mask must be square")

    supersample = canvas_size // READY_MASK_SIZE
    if supersample < 1 or canvas_size != READY_MASK_SIZE * supersample:
        raise ValueError("ready mask size must be a multiple of 228")
    if supersample > 1:
        petal = petal.point(lambda value: value * 17).resize(
            (petal.size[0] * supersample, petal.size[1] * supersample),
            Image.Resampling.LANCZOS,
        ).point(lambda value: min(15, max(0, (value * 15 + 127) // 255)))
    source_size = petal.size[0]
    source_values = list(petal.getdata())
    output = [0] * (canvas_size * canvas_size)
    factor_q16 = (source_size << 28) // (132 * READY_SCALE_Q12)
    source_center_q8 = (source_size - 1) * 128

    for piece in range(6):
        piece_step = piece * 256 // 6
        position_angle = (192 - piece_step) & 0xFF
        petal_angle = (
            position_angle + READY_PETAL_CLOCKWISE_ANGLE
        ) & 0xFF
        sine = _sin_q15(petal_angle)
        cosine = _sin_q15(petal_angle + 64)
        center_x_q8 = (
            READY_CENTER * 256
            + (_sin_q15(position_angle + 64) * READY_RADIUS * 256 >> 15)
        )
        center_y_q8 = (
            READY_CENTER * 256
            + (_sin_q15(position_angle) * READY_RADIUS * 256 >> 15)
        )

        for local_y in range(canvas_size):
            screen_y_q8 = (
                (local_y * 256 + 128) // supersample +
                READY_SCENE_OFFSET * 256
            )
            dy_q8 = screen_y_q8 - center_y_q8
            for local_x in range(canvas_size):
                screen_x_q8 = (
                    (local_x * 256 + 128) // supersample +
                    READY_SCENE_OFFSET * 256
                )
                dx_q8 = screen_x_q8 - center_x_q8
                rotated_x = dx_q8 * cosine + dy_q8 * sine
                rotated_y = -dx_q8 * sine + dy_q8 * cosine
                source_x = (
                    ((rotated_x * factor_q16) >> 31)
                    + source_center_q8
                    + 128
                ) >> 8
                source_y = (
                    ((rotated_y * factor_q16) >> 31)
                    + source_center_q8
                    + 128
                ) >> 8
                if not (
                    0 <= source_x < source_size
                    and 0 <= source_y < source_size
                ):
                    continue
                alpha = source_values[source_y * source_size + source_x]
                if alpha == 0:
                    continue
                index = local_y * canvas_size + local_x
                previous = output[index]
                output[index] = 15 - (
                    ((15 - previous) * (15 - alpha) + 7) // 15
                )

    image = Image.new("L", (canvas_size, canvas_size), 0)
    image.putdata(output)
    return image


def rasterize_ready_composite(
    reference_path: Path,
    canvas_size: int = READY_MASK_SIZE * READY_MASK_SUPERSAMPLE,
) -> Image.Image:
    petal = rasterize_reference_petal(reference_path, size=128)
    return compose_ready_mask(petal, canvas_size=canvas_size)


def petal_bounds(
    masks: list[Image.Image],
) -> tuple[list[int], list[int], list[int], list[int], list[int]]:
    minimum_x: list[int] = []
    minimum_y: list[int] = []
    maximum_x: list[int] = []
    maximum_y: list[int] = []
    radius: list[int] = []
    for mask in masks:
        box = mask.getbbox()
        if box is None:
            raise ValueError("generated Blossom petal is empty")
        left, top, right, bottom = box
        right -= 1
        bottom -= 1
        minimum_x.append(left)
        minimum_y.append(top)
        maximum_x.append(right)
        maximum_y.append(bottom)
        width = right - left + 1
        height = bottom - top + 1
        radius.append(math.ceil(math.hypot(width, height) / 2.0) + 2)
    return minimum_x, minimum_y, maximum_x, maximum_y, radius


def rasterize_piece_strokes(
    svg_path, size=128, supersample=4, stroke_width=10.0
):
    view_box, lobes = _outer_lobes(svg_path)
    high_size = size * supersample
    scale_x = high_size / view_box[2]
    scale_y = high_size / view_box[3]
    width = max(1, round(stroke_width * supersample))
    pieces = []

    for lobe in lobes:
        image = Image.new("L", (high_size, high_size), 0)
        draw = ImageDraw.Draw(image)
        points = [
            (
                round((x - view_box[0]) * scale_x),
                round((y - view_box[1]) * scale_y),
            )
            for x, y in lobe
        ]
        draw.line(
            points + [points[0]],
            fill=255,
            width=width,
            joint="curve",
        )
        image = image.resize((size, size), Image.Resampling.LANCZOS)
        pieces.append(
            image.point(
                lambda value: min(15, max(0, (value * 15 + 127) // 255))
            )
        )
    return pieces


def partition_blossom(svg_path, mask):
    view_box, outer_holes = _outer_lobes(svg_path)

    width, height = mask.size
    scale_x = width / view_box[2]
    scale_y = height / view_box[3]
    distance_maps = []
    for hole in outer_holes:
        hole_image = Image.new("1", (width, height), 0)
        draw = ImageDraw.Draw(hole_image)
        draw.polygon(
            [
                (
                    round((x - view_box[0]) * scale_x),
                    round((y - view_box[1]) * scale_y),
                )
                for x, y in hole
            ],
            fill=1,
        )
        distance_maps.append(
            _chamfer_distance(list(hole_image.getdata()), width, height)
        )

    mask_values = list(mask.getdata())
    piece_values = [0] * len(mask_values)
    for index, alpha in enumerate(mask_values):
        if alpha:
            piece_values[index] = 1 + min(
                range(6), key=lambda piece: distance_maps[piece][index]
            )

    pieces = Image.new("L", (width, height), 0)
    pieces.putdata(piece_values)
    return pieces


def pack_piece_ids(piece_ids):
    values = list(piece_ids.getdata())
    if len(values) % 2:
        values.append(0)
    return bytes(
        ((values[index] & 0x0F) << 4) | (values[index + 1] & 0x0F)
        for index in range(0, len(values), 2)
    )


def _write_asset_pair_atomically(
    header_path: Path,
    header_text: str,
    source_path: Path,
    source_text: str,
) -> None:
    destinations = ((header_path, header_text), (source_path, source_text))
    temporary_paths: list[Path] = []
    backups: list[tuple[Path, Path | None]] = []
    replaced: list[tuple[Path, Path | None]] = []

    def temporary_sibling(destination: Path) -> Path:
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{destination.name}.",
            suffix=".tmp",
            dir=destination.parent,
        )
        os.close(descriptor)
        return Path(temporary_name)

    try:
        for destination, text in destinations:
            temporary_path = temporary_sibling(destination)
            temporary_paths.append(temporary_path)
            temporary_path.write_text(text, encoding="ascii")

        for destination, _ in destinations:
            backup = None
            if destination.exists():
                backup = temporary_sibling(destination)
                backup.write_bytes(destination.read_bytes())
            backups.append((destination, backup))

        for (destination, _), temporary_path, (_, backup) in zip(
            destinations,
            temporary_paths.copy(),
            backups,
            strict=True,
        ):
            os.replace(temporary_path, destination)
            temporary_paths.remove(temporary_path)
            replaced.append((destination, backup))
    except Exception:
        for destination, backup in reversed(replaced):
            if backup is None:
                destination.unlink(missing_ok=True)
            else:
                os.replace(backup, destination)
        raise
    finally:
        for temporary_path in temporary_paths:
            temporary_path.unlink(missing_ok=True)
        for _, backup in backups:
            if backup is not None:
                backup.unlink(missing_ok=True)


def emit_c(mask, header_path, source_path, piece_ids, piece_masks):
    header_path = Path(header_path)
    source_path = Path(source_path)
    width, height = mask.size
    if width != height:
        raise ValueError("Blossom mask must be square")
    packed = pack_4bpp(mask)
    packed_piece_ids = pack_piece_ids(piece_ids)
    packed_piece_masks = [pack_4bpp(piece) for piece in piece_masks]
    ready_mask = compose_ready_mask(piece_masks[0])
    packed_ready_mask = pack_4bpp(ready_mask)
    (
        minimum_x,
        minimum_y,
        maximum_x,
        maximum_y,
        radius,
    ) = petal_bounds(piece_masks)
    header_text = (
        "#ifndef CODEX_USB_PAGER_BLOSSOM_ASSET_H\n"
        "#define CODEX_USB_PAGER_BLOSSOM_ASSET_H\n\n"
        "#include <stdint.h>\n\n"
        f"#define BLOSSOM_MASK_SIZE {width}U\n"
        f"#define BLOSSOM_MASK_BYTES {len(packed)}U\n\n"
        "#define BLOSSOM_PIECE_COUNT 6U\n"
        f"#define BLOSSOM_PIECE_ID_BYTES {len(packed_piece_ids)}U\n\n"
        f"#define BLOSSOM_READY_MASK_SIZE {ready_mask.size[0]}U\n"
        f"#define BLOSSOM_READY_MASK_BYTES {len(packed_ready_mask)}U\n\n"
        "extern const uint8_t g_blossom_alpha_4bpp[BLOSSOM_MASK_BYTES];\n\n"
        "extern const uint8_t "
        "g_blossom_piece_id_4bpp[BLOSSOM_PIECE_ID_BYTES];\n\n"
        "extern const uint8_t "
        "g_blossom_piece_alpha_4bpp"
        "[BLOSSOM_PIECE_COUNT][BLOSSOM_MASK_BYTES];\n\n"
        "extern const uint8_t "
        "g_blossom_ready_alpha_4bpp[BLOSSOM_READY_MASK_BYTES];\n\n"
        "extern const uint8_t g_blossom_piece_min_x[BLOSSOM_PIECE_COUNT];\n"
        "extern const uint8_t g_blossom_piece_min_y[BLOSSOM_PIECE_COUNT];\n"
        "extern const uint8_t g_blossom_piece_max_x[BLOSSOM_PIECE_COUNT];\n"
        "extern const uint8_t g_blossom_piece_max_y[BLOSSOM_PIECE_COUNT];\n"
        "extern const uint8_t g_blossom_piece_radius[BLOSSOM_PIECE_COUNT];\n\n"
        "extern const int16_t g_sin_q15[256];\n\n"
        "#endif\n"
    )

    rows = []
    for offset in range(0, len(packed), 16):
        rows.append("  " + ", ".join(f"0x{value:02X}" for value in packed[offset : offset + 16]))
    piece_rows = []
    for offset in range(0, len(packed_piece_ids), 16):
        piece_rows.append(
            "  "
            + ", ".join(
                f"0x{value:02X}"
                for value in packed_piece_ids[offset : offset + 16]
            )
        )
    piece_mask_blocks = []
    for piece in packed_piece_masks:
        piece_mask_rows = []
        for offset in range(0, len(piece), 16):
            piece_mask_rows.append(
                "    "
                + ", ".join(
                    f"0x{value:02X}"
                    for value in piece[offset : offset + 16]
                )
            )
        piece_mask_blocks.append(
            "  {\n" + ",\n".join(piece_mask_rows) + "\n  }"
        )
    ready_rows = []
    for offset in range(0, len(packed_ready_mask), 16):
        ready_rows.append(
            "  "
            + ", ".join(
                f"0x{value:02X}"
                for value in packed_ready_mask[offset : offset + 16]
            )
        )
    bounds_arrays = (
        ("g_blossom_piece_min_x", minimum_x),
        ("g_blossom_piece_min_y", minimum_y),
        ("g_blossom_piece_max_x", maximum_x),
        ("g_blossom_piece_max_y", maximum_y),
        ("g_blossom_piece_radius", radius),
    )
    bounds_blocks = [
        "const uint8_t "
        + name
        + "[BLOSSOM_PIECE_COUNT] = {"
        + ", ".join(str(value) for value in values)
        + "};"
        for name, values in bounds_arrays
    ]
    sine = [round(math.sin(2 * math.pi * index / 256) * 32767) for index in range(256)]
    sine_rows = []
    for offset in range(0, len(sine), 16):
        sine_rows.append("  " + ", ".join(str(value) for value in sine[offset : offset + 16]))

    source_text = (
        '#include "blossom_asset.h"\n\n'
        "const uint8_t g_blossom_alpha_4bpp[BLOSSOM_MASK_BYTES] = {\n"
        + ",\n".join(rows)
        + "\n};\n\n"
        + "const uint8_t "
        "g_blossom_piece_id_4bpp[BLOSSOM_PIECE_ID_BYTES] = {\n"
        + ",\n".join(piece_rows)
        + "\n};\n\n"
        + "const uint8_t g_blossom_piece_alpha_4bpp"
        "[BLOSSOM_PIECE_COUNT][BLOSSOM_MASK_BYTES] = {\n"
        + ",\n".join(piece_mask_blocks)
        + "\n};\n\n"
        + "const uint8_t "
        "g_blossom_ready_alpha_4bpp[BLOSSOM_READY_MASK_BYTES] = {\n"
        + ",\n".join(ready_rows)
        + "\n};\n\n"
        + "\n\n".join(bounds_blocks)
        + "\n\n"
        + "const int16_t g_sin_q15[256] = {\n"
        + ",\n".join(sine_rows)
        + "\n};\n"
    )
    _write_asset_pair_atomically(
        header_path,
        header_text,
        source_path,
        source_text,
    )


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--svg", type=Path, default=root / "assets" / "openai-blossom.svg")
    parser.add_argument(
        "--petal",
        type=Path,
        default=root / "assets" / "reference-petal-exact.png",
    )
    parser.add_argument("--header", type=Path, default=root / "Core" / "Inc" / "blossom_asset.h")
    parser.add_argument("--source", type=Path, default=root / "Core" / "Src" / "blossom_asset.c")
    parser.add_argument("--size", type=int, default=128)
    args = parser.parse_args()

    mask = rasterize_svg(args.svg, size=args.size)
    piece_ids = partition_blossom(args.svg, mask)
    piece_masks = rasterize_petals(args.petal, size=args.size)
    emit_c(mask, args.header, args.source, piece_ids, piece_masks)


if __name__ == "__main__":
    main()
