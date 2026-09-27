from collections import deque
import os
from pathlib import Path

from PIL import Image

import generate_blossom_asset as generator
from generate_blossom_asset import emit_c, pack_4bpp, rasterize_svg


ROOT = Path(__file__).resolve().parents[1]
SVG = ROOT / "assets" / "openai-blossom.svg"
REFERENCE_PETAL = ROOT / "assets" / "reference-petal-exact.png"


def mask_bbox(mask: Image.Image) -> tuple[int, int, int, int]:
    box = mask.getbbox()
    assert box is not None
    return box


def test_reference_petal_is_exact_thresholded_black_foreground() -> None:
    source = Image.open(REFERENCE_PETAL).convert("L")
    expected = source.point(lambda value: 255 if value < 128 else 0)
    expected = expected.crop(expected.getbbox())

    actual = generator.load_reference_petal(REFERENCE_PETAL)

    assert actual.mode == "L"
    assert actual.size == expected.size
    assert actual.tobytes() == expected.tobytes()


def test_six_firmware_petals_share_one_exact_mask() -> None:
    petals = generator.rasterize_petals(REFERENCE_PETAL, size=128)

    assert len(petals) == 6
    assert all(petal.size == (128, 128) for petal in petals)
    assert all(petal.tobytes() == petals[0].tobytes() for petal in petals[1:])
    assert mask_bbox(petals[0]) == (28, 40, 100, 88)


def test_ready_composite_contains_six_exact_petals_on_one_228_mask() -> None:
    ready = generator.rasterize_ready_composite(
        REFERENCE_PETAL,
        canvas_size=228,
    )

    assert ready.size == (228, 228)
    assert min(ready.getdata()) == 0
    assert max(ready.getdata()) == 15
    bounds = mask_bbox(ready)
    assert bounds[2] - bounds[0] >= 180
    assert bounds[3] - bounds[1] >= 190
    assert abs((bounds[0] + bounds[2] - 1) / 2 - 113.5) <= 0.5
    assert abs((bounds[1] + bounds[3] - 1) / 2 - 113.5) <= 0.5


def test_petals_keep_one_global_scale() -> None:
    small = generator.rasterize_petals(REFERENCE_PETAL, size=128)
    large = generator.rasterize_petals(REFERENCE_PETAL, size=192)
    for small_mask, large_mask in zip(small, large, strict=True):
        sw = mask_bbox(small_mask)[2] - mask_bbox(small_mask)[0]
        lw = mask_bbox(large_mask)[2] - mask_bbox(large_mask)[0]
        assert abs(lw / sw - 1.5) < 0.08


def test_full_blossom_mask_is_unchanged_by_petal_generation() -> None:
    before = generator.rasterize_svg(SVG, size=128).tobytes()
    generator.rasterize_petals(REFERENCE_PETAL, size=128)
    after = generator.rasterize_svg(SVG, size=128).tobytes()
    assert after == before


def test_petal_bounds_are_inclusive_with_rotation_safe_radius() -> None:
    first = Image.new("L", (16, 16), 0)
    for y in range(4, 11):
        for x in range(3, 9):
            first.putpixel((x, y), 15)
    second = Image.new("L", (16, 16), 0)
    second.putpixel((6, 1), 15)

    bounds = generator.petal_bounds([first, second])

    assert bounds == ([3, 6], [4, 1], [8, 6], [10, 1], [7, 3])


def test_emit_c_keeps_both_outputs_on_second_replace_failure(
    monkeypatch,
) -> None:
    mask = rasterize_svg(SVG, size=128, supersample=4)
    temp_dir = ROOT / ".asset_test_atomic"
    header = temp_dir / "blossom_asset.h"
    source = temp_dir / "blossom_asset.c"
    temp_dir.mkdir(exist_ok=True)
    try:
        header.write_text("header before\n", encoding="ascii")
        source.write_text("source before\n", encoding="ascii")
        monkeypatch.setattr(generator, "os", os, raising=False)
        original_replace = os.replace

        def fail_source_replace(source_path, destination_path) -> None:
            if Path(destination_path) == source:
                raise OSError("forced source replacement failure")
            original_replace(source_path, destination_path)

        monkeypatch.setattr(os, "replace", fail_source_replace)

        try:
            emit_c(
                mask,
                header,
                source,
                generator.partition_blossom(SVG, mask),
                generator.rasterize_petals(REFERENCE_PETAL, size=128),
            )
        except OSError as error:
            assert str(error) == "forced source replacement failure"
        else:
            raise AssertionError("expected source replacement to fail")

        assert header.read_text(encoding="ascii") == "header before\n"
        assert source.read_text(encoding="ascii") == "source before\n"
        assert not list(temp_dir.glob("*.tmp"))
    finally:
        for path in temp_dir.glob("*"):
            path.unlink()
        temp_dir.rmdir()


def test_piece_partition_is_lossless():
    mask = rasterize_svg(SVG, size=128, supersample=4)
    pieces = generator.partition_blossom(SVG, mask)
    mask_values = list(mask.getdata())
    piece_values = list(pieces.getdata())

    assert set(piece_values) <= set(range(7))
    assert all(
        (alpha == 0 and piece == 0) or (alpha > 0 and 1 <= piece <= 6)
        for alpha, piece in zip(mask_values, piece_values)
    )
    assert {piece for piece in piece_values if piece} == set(range(1, 7))


def test_piece_ids_pack_two_pixels_per_byte():
    mask = rasterize_svg(SVG, size=128, supersample=4)
    pieces = generator.partition_blossom(SVG, mask)
    packed = generator.pack_piece_ids(pieces)

    assert len(packed) == 128 * 128 // 2
    assert any(packed)


def _interior_zero_count(mask):
    width, height = mask.size
    values = list(mask.getdata())
    exterior = set()
    queue = deque()

    for x in range(width):
        queue.append((x, 0))
        queue.append((x, height - 1))
    for y in range(height):
        queue.append((0, y))
        queue.append((width - 1, y))
    while queue:
        x, y = queue.popleft()
        index = y * width + x
        if (x, y) in exterior or values[index] != 0:
            continue
        exterior.add((x, y))
        if x > 0:
            queue.append((x - 1, y))
        if x + 1 < width:
            queue.append((x + 1, y))
        if y > 0:
            queue.append((x, y - 1))
        if y + 1 < height:
            queue.append((x, y + 1))
    return sum(value == 0 for value in values) - len(exterior)


def test_six_display_pieces_are_closed_uniform_loops():
    pieces = generator.rasterize_petals(REFERENCE_PETAL, size=128)
    areas = [
        sum(value >= 8 for value in piece.getdata())
        for piece in pieces
    ]

    assert len(pieces) == 6
    assert all(_interior_zero_count(piece) > 40 for piece in pieces)
    assert max(areas) - min(areas) < sum(areas) / len(areas) * 0.18


def test_blossom_mask_is_centered_and_packed():
    mask = rasterize_svg(SVG, size=128, supersample=4)

    assert mask.size == (128, 128)
    assert min(mask.getdata()) == 0
    assert max(mask.getdata()) == 15

    bbox = mask.point(lambda value: 255 if value else 0).getbbox()
    assert bbox is not None
    center_x = (bbox[0] + bbox[2] - 1) / 2
    center_y = (bbox[1] + bbox[3] - 1) / 2
    assert abs(center_x - 63.5) <= 1.0
    assert abs(center_y - 63.5) <= 1.0

    packed = pack_4bpp(mask)
    assert len(packed) == 128 * 128 // 2
    assert any(packed)


def test_generated_c_files_have_valid_declarations():
    mask = rasterize_svg(SVG, size=128, supersample=4)
    temp_dir = ROOT / ".asset_test_tmp"
    header = temp_dir / "blossom_asset.h"
    source = temp_dir / "blossom_asset.c"
    temp_dir.mkdir(exist_ok=True)

    try:
        emit_c(
            mask,
            header,
            source,
            generator.partition_blossom(SVG, mask),
            generator.rasterize_petals(REFERENCE_PETAL, size=128),
        )
        header_text = header.read_text(encoding="ascii")
        source_text = source.read_text(encoding="ascii")
        assert '"#define' not in header_text
        assert "#define BLOSSOM_MASK_BYTES 8192U" in header_text
        assert "#define BLOSSOM_PIECE_COUNT 6U" in header_text
        assert "#define BLOSSOM_PIECE_ID_BYTES 8192U" in header_text
        assert "g_blossom_alpha_4bpp[BLOSSOM_MASK_BYTES]" in header_text
        assert (
            "g_blossom_piece_id_4bpp[BLOSSOM_PIECE_ID_BYTES]"
            in header_text
        )
        assert (
            "g_blossom_piece_alpha_4bpp"
            "[BLOSSOM_PIECE_COUNT][BLOSSOM_MASK_BYTES]"
            in header_text
        )
        assert "#define BLOSSOM_READY_MASK_SIZE 456U" in header_text
        assert "#define BLOSSOM_READY_MASK_BYTES 103968U" in header_text
        assert (
            "g_blossom_ready_alpha_4bpp[BLOSSOM_READY_MASK_BYTES]"
            in header_text
        )
        assert "g_sin_q15[256]" in header_text
        assert source_text.count("0x") == 169504
        assert source_text.count("g_sin_q15[256]") == 1
    finally:
        header.unlink(missing_ok=True)
        source.unlink(missing_ok=True)
        temp_dir.rmdir()


def test_generated_asset_supports_high_resolution_nearest_sampling():
    mask = rasterize_svg(SVG, size=192, supersample=4)
    temp_dir = ROOT / ".asset_test_tmp_192"
    header = temp_dir / "blossom_asset.h"
    source = temp_dir / "blossom_asset.c"
    temp_dir.mkdir(exist_ok=True)

    try:
        emit_c(
            mask,
            header,
            source,
            generator.partition_blossom(SVG, mask),
            generator.rasterize_petals(REFERENCE_PETAL, size=192),
        )
        header_text = header.read_text(encoding="ascii")
        source_text = source.read_text(encoding="ascii")
        assert "#define BLOSSOM_MASK_SIZE 192U" in header_text
        assert "#define BLOSSOM_MASK_BYTES 18432U" in header_text
        assert source_text.count("0x") == 251424
    finally:
        header.unlink(missing_ok=True)
        source.unlink(missing_ok=True)
        temp_dir.rmdir()
