from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from petal_preview_geometry import (
    READY_ASSEMBLED_RADIUS,
    READY_PETAL_WIDTH,
    READY_SEPARATION,
    load_exact_petal,
    render_ready_pieces,
)


ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "assets" / "reference-petal-exact.png"
OUTPUT = ROOT / "outputs" / "exact_petal_review.png"
PANEL = 700
HEIGHT = 700
BACKGROUND = (6, 13, 25, 255)
PURPLE = (130, 108, 255, 255)
GREEN = (48, 214, 158, 255)
WHITE = (238, 244, 255, 255)


def font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", size)


def colored_mask(
    mask: np.ndarray,
    color: tuple[int, int, int, int],
    size: tuple[int, int],
) -> Image.Image:
    alpha = Image.fromarray(mask, mode="L").resize(
        size,
        Image.Resampling.LANCZOS,
    )
    image = Image.new("RGBA", size, color)
    image.putalpha(alpha)
    return image


def hexagon(draw: ImageDraw.ImageDraw, origin_x: int) -> None:
    center_x = origin_x + PANEL // 2
    radius = 300
    half_width = round(radius * 3**0.5 / 2)
    top = 76
    points = (
        (center_x, top),
        (center_x + half_width, top + radius // 2),
        (center_x + half_width, top + radius * 3 // 2),
        (center_x, top + radius * 2),
        (center_x - half_width, top + radius * 3 // 2),
        (center_x - half_width, top + radius // 2),
    )
    draw.line(points + (points[0],), fill=WHITE, width=3, joint="curve")


def main() -> None:
    petal = load_exact_petal(REFERENCE)
    canvas = Image.new("RGBA", (PANEL * 2, HEIGHT), BACKGROUND)
    draw = ImageDraw.Draw(canvas)

    draw.text(
        (PANEL // 2, 22),
        "你提供的唯一标准单瓣",
        font=font(34),
        fill=WHITE,
        anchor="ma",
    )
    single_width = 570
    single_height = round(petal.shape[0] * single_width / petal.shape[1])
    single = colored_mask(
        petal,
        PURPLE,
        (single_width, single_height),
    )
    canvas.alpha_composite(
        single,
        (
            (PANEL - single_width) // 2,
            102 + (510 - single_height) // 2,
        ),
    )

    draw.text(
        (PANEL + PANEL // 2, 22),
        "就绪态：原方案逆时针旋转90度",
        font=font(34),
        fill=WHITE,
        anchor="ma",
    )
    piece_masks, _ = render_ready_pieces(
        petal,
        canvas_size=900,
        petal_width=READY_PETAL_WIDTH,
        assembled_radius=READY_ASSEMBLED_RADIUS,
        separation=READY_SEPARATION,
        ready_orientation=True,
    )
    ready_layer = Image.new("RGBA", (600, 600), (0, 0, 0, 0))
    for piece in piece_masks:
        ready_layer.alpha_composite(colored_mask(piece, GREEN, (600, 600)))
    canvas.alpha_composite(ready_layer, (PANEL + 50, 76))

    hexagon(draw, PANEL)
    draw.text(
        (PANEL + PANEL // 2, 376),
        "82",
        font=font(76),
        fill=WHITE,
        anchor="mm",
    )
    draw.line(
        (PANEL, 0, PANEL, HEIGHT),
        fill=(37, 52, 75, 255),
        width=2,
    )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(OUTPUT, quality=98)
    print(OUTPUT)


if __name__ == "__main__":
    main()
