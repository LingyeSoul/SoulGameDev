"""Per-asset checks for generated raster art.

Every asset module runs these checks before returning its atlas metadata, so a
bad sprite fails at its own module instead of poisoning the whole build.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

Color = tuple[int, int, int, int]


class AssetCheckError(RuntimeError):
    """Raised when a generated image violates its declared contract."""


def load_rgba(path: Path) -> Image.Image:
    if not path.exists():
        raise AssetCheckError(f"asset missing: {path}")
    image = Image.open(path)
    if image.mode != "RGBA":
        raise AssetCheckError(f"{path}: mode is {image.mode}, expected RGBA")
    return image


def check_size(image: Image.Image, width: int, height: int, path: Path) -> None:
    if image.size != (width, height):
        raise AssetCheckError(f"{path}: size is {image.width}x{image.height}, expected {width}x{height}")


def visible_colors(image: Image.Image) -> set[Color]:
    return {pixel for pixel in image.getdata() if pixel[3] > 0}


def check_palette(image: Image.Image, allowed: set[Color], path: Path) -> None:
    actual = visible_colors(image)
    illegal = sorted(actual - allowed)
    if illegal:
        sample = ", ".join(f"#{r:02x}{g:02x}{b:02x}{a:02x}" for r, g, b, a in illegal[:6])
        raise AssetCheckError(
            f"{path}: {len(illegal)} colour(s) outside the palette: {sample}"
        )


def check_max_colors(image: Image.Image, maximum: int, path: Path) -> None:
    actual = visible_colors(image)
    if len(actual) > maximum:
        raise AssetCheckError(f"{path}: {len(actual)} colours, maximum is {maximum}")


def check_alpha(image: Image.Image, require_alpha: bool, path: Path) -> None:
    if not require_alpha:
        return
    alphas = {pixel[3] for pixel in image.getdata()}
    if 0 not in alphas:
        raise AssetCheckError(f"{path}: expected transparent pixels, found none")


def check_bottom_row(image: Image.Image, path: Path) -> None:
    pixels = image.load()
    for x in range(image.width):
        if pixels[x, image.height - 1][3] > 0:
            return
    raise AssetCheckError(
        f"{path}: bottom row is transparent; a bottom-center pivot would float"
    )


def check_outline(image: Image.Image, ink: Color, path: Path) -> None:
    """Every transparent neighbour of a coloured pixel must be the ink colour.

    Ink pixels may themselves touch transparency: that is the outer edge of a
    one-pixel border. What must not happen is a visible colour running straight
    into the background with no ink between them.
    """
    pixels = image.load()
    for y in range(image.height):
        for x in range(image.width):
            if pixels[x, y][3] != 0:
                continue
            # A silhouette may touch the canvas edge; there is no room for ink
            # outside the texture, so boundary pixels are exempt.
            if x == 0 or y == 0 or x == image.width - 1 or y == image.height - 1:
                continue
            neighbours = (
                (x - 1, y),
                (x + 1, y),
                (x, y - 1),
                (x, y + 1),
            )
            for nx, ny in neighbours:
                if nx < 0 or ny < 0 or nx >= image.width or ny >= image.height:
                    continue
                neighbour = pixels[nx, ny]
                if neighbour[3] > 0 and neighbour != ink:
                    raise AssetCheckError(
                        f"{path}: transparent pixel ({x},{y}) touches colour {neighbour} "
                        f"without a 1px ink border"
                    )


def verify_sprite(
    path: Path,
    width: int,
    height: int,
    allowed: set[Color],
    ink: Color,
    require_alpha: bool,
    bottom_row: bool,
    max_colors: int,
    outline: bool,
) -> dict:
    image = load_rgba(path)
    check_size(image, width, height, path)
    check_palette(image, allowed, path)
    check_max_colors(image, max_colors, path)
    check_alpha(image, require_alpha, path)
    if bottom_row:
        check_bottom_row(image, path)
    if outline:
        check_outline(image, ink, path)
    return {
        "path": str(path),
        "size": [image.width, image.height],
        "colors": len(visible_colors(image)),
    }
