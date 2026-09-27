from pathlib import Path

from PIL import Image, ImageDraw

from generate_blossom_asset import (
    partition_blossom,
    rasterize_petals,
    rasterize_svg,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs" / "blossom_partition_preview.png"
SIZE = 512
COLORS = (
    (118, 103, 255),
    (84, 151, 255),
    (57, 201, 210),
    (54, 211, 153),
    (181, 117, 255),
    (231, 104, 191),
)


def tint(alpha: Image.Image, color: tuple[int, int, int]) -> Image.Image:
    layer = Image.new("RGBA", alpha.size, (*color, 0))
    layer.putalpha(alpha.point(lambda value: value * 17))
    return layer


def partition_masks(mask: Image.Image, ids: Image.Image) -> list[Image.Image]:
    alpha = mask.point(lambda value: value * 17)
    values = list(ids.getdata())
    alpha_values = list(alpha.getdata())
    pieces = []
    for piece in range(1, 7):
        image = Image.new("L", mask.size, 0)
        image.putdata([
            alpha_value if piece_id == piece else 0
            for piece_id, alpha_value in zip(values, alpha_values)
        ])
        pieces.append(image)
    return pieces


def panel_title(
    draw: ImageDraw.ImageDraw, x: int, text: str
) -> None:
    draw.text((x + 18, 18), text, fill=(225, 231, 245, 255))


def main() -> None:
    mask = rasterize_svg(ROOT / "assets" / "openai-blossom.svg", size=SIZE)
    ids = partition_blossom(ROOT / "assets" / "openai-blossom.svg", mask)
    exact_pieces = partition_masks(mask, ids)
    piece_masks = rasterize_petals(
        ROOT / "assets" / "openai-blossom.svg",
        size=128,
    )

    panel = 600
    pieces_panel = 1600
    canvas = Image.new(
        "RGBA", (panel * 2 + pieces_panel, 1100), (7, 13, 25, 255)
    )
    draw = ImageDraw.Draw(canvas)
    panel_title(draw, 0, "ORIGINAL BLOSSOM")
    panel_title(draw, panel, "SIX EXACT PARTITIONS")
    panel_title(draw, panel * 2, "SEPARATED PIECES")

    original = tint(mask, (144, 124, 255))
    canvas.alpha_composite(original, (44, 82))

    for index, piece in enumerate(exact_pieces):
        canvas.alpha_composite(tint(piece, COLORS[index]), (panel + 44, 82))

    for index, piece in enumerate(piece_masks):
        colored = tint(piece, COLORS[index])
        column = index % 3
        row = index // 3
        x = panel * 2 + 10 + column * 530
        y = 54 + row * 520
        canvas.alpha_composite(colored, (x, y))
        draw.text(
            (panel * 2 + 22 + column * 530, 50 + row * 520),
            str(index + 1),
            fill=(125, 138, 160, 255),
        )

    for x in (panel, panel * 2):
        draw.line((x, 0, x, 1100), fill=(38, 52, 75, 255), width=2)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(OUTPUT, quality=96)
    print(OUTPUT)


if __name__ == "__main__":
    main()
