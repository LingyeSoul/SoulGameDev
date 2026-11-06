"""Per-asset checks for generated raster art.

Every asset module runs these checks before returning its atlas metadata, so a
bad sprite fails at its own module instead of poisoning the whole build.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ElementTree
from pathlib import Path

from PIL import Image

Color = tuple[int, int, int, int]
SVG_NS_PREFIX = "{http://www.w3.org/2000/svg}"
XLINK_HREF = "{http://www.w3.org/1999/xlink}href"
FORBIDDEN_ELEMENTS = {
    "image",
    "foreignObject",
    "script",
    "style",
    "filter",
    "pattern",
    "linearGradient",
    "radialGradient",
    "text",
    "tspan",
    "use",
}
LOCAL_NAME = re.compile(r"^\{[^}]+\}")


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


def _local_name(tag: str) -> str:
    return LOCAL_NAME.sub("", tag)


def _parse_length(value: str, path: Path, field: str) -> float:
    match = re.fullmatch(r"(\d+(?:\.\d+)?)(?:px)?", value.strip())
    if match is None:
        raise AssetCheckError(f"{path}: {field} must be a pixel length, got {value!r}")
    return float(match.group(1))


def _parse_svg_color(value: str, path: Path, field: str) -> str:
    raw = value.strip().lower()
    if re.fullmatch(r"#[0-9a-f]{6}", raw) is None:
        raise AssetCheckError(f"{path}: {field} must be #rrggbb, got {value!r}")
    return raw


def _normalise_paint(value: str, path: Path, field: str) -> str:
    raw = value.strip().lower()
    if raw in {"none", "transparent"}:
        return "none"
    if raw.startswith("url(") or raw in {"currentcolor", "inherit"}:
        raise AssetCheckError(f"{path}: {field}={value!r} is not a literal palette colour")
    return _parse_svg_color(raw, path, field)


DRAWABLE_ELEMENTS = {"path", "rect", "circle", "ellipse", "line", "polyline", "polygon"}


def verify_vector(path: Path, width: int, height: int, allowed: set[str]) -> dict:
    """Check an SVG source before a derived raster enters the manifest.

    The contract is intentionally narrow: fixed pixel size, the SVG namespace,
    no external references/scripts/filters/text, and every effective fill or
    stroke colour must come from the declared vector palette. An element with
    no paint inherits black, so it is rejected unless the palette contains it.
    """
    if not path.exists():
        raise AssetCheckError(f"asset missing: {path}")
    try:
        root = ElementTree.parse(path).getroot()
    except ElementTree.ParseError as exc:
        raise AssetCheckError(f"{path}: invalid SVG XML: {exc}") from exc
    if root.tag != SVG_NS_PREFIX + "svg":
        raise AssetCheckError(
            f"{path}: root element must be <svg xmlns={SVG_NS_PREFIX[1:-1]!r}>, got {root.tag!r}"
        )

    # Reject forbidden elements before paint validation so a <use>/<text>/<style>
    # inside <defs> reports the real contract violation, not a default fill.
    for element in root.iter():
        name = _local_name(element.tag)
        if name in FORBIDDEN_ELEMENTS:
            raise AssetCheckError(f"{path}: <{name}> is not allowed in a vector asset")

    declared_width = root.get("width")
    declared_height = root.get("height")
    if declared_width is None or declared_height is None:
        raise AssetCheckError(f"{path}: <svg> needs explicit width and height")
    actual_width = _parse_length(declared_width, path, "width")
    actual_height = _parse_length(declared_height, path, "height")
    if (actual_width, actual_height) != (float(width), float(height)):
        raise AssetCheckError(
            f"{path}: size is {actual_width:g}x{actual_height:g}, expected {width}x{height}"
        )

    viewbox = root.get("viewBox")
    if viewbox is not None:
        parts = viewbox.replace(",", " ").split()
        if len(parts) != 4:
            raise AssetCheckError(f"{path}: viewBox needs four numbers, got {viewbox!r}")
        try:
            viewbox_values = [float(part) for part in parts]
        except ValueError as exc:
            raise AssetCheckError(f"{path}: viewBox needs four numbers, got {viewbox!r}") from exc
        if (viewbox_values[2], viewbox_values[3]) != (float(width), float(height)):
            raise AssetCheckError(
                f"{path}: viewBox size is {parts[2]}x{parts[3]}, expected {width}x{height}"
            )

    normalised_allowed = {colour.lower() for colour in allowed}
    used: set[str] = set()

    def visit(element: ElementTree.Element, inherited_fill: str | None, inherited_stroke: str | None) -> None:
        name = _local_name(element.tag)
        if element.tag.startswith("{") and not element.tag.startswith(SVG_NS_PREFIX):
            raise AssetCheckError(f"{path}: element <{name}> is outside the SVG namespace")
        if name in FORBIDDEN_ELEMENTS:
            raise AssetCheckError(f"{path}: <{name}> is not allowed in a vector asset")
        if element.get("style") is not None:
            raise AssetCheckError(f"{path}: inline style attributes are not allowed; use fill/stroke")
        for attribute in element.attrib:
            if _local_name(attribute).lower().startswith("on"):
                raise AssetCheckError(f"{path}: event attribute {attribute!r} is not allowed")
        for attribute in ("href", XLINK_HREF):
            reference = element.get(attribute)
            if reference is not None and not reference.startswith("#"):
                raise AssetCheckError(
                    f"{path}: external reference {reference!r} in <{name}>; embed nothing external"
                )

        fill_value = element.get("fill")
        stroke_value = element.get("stroke")
        fill = (
            _normalise_paint(fill_value, path, "fill")
            if fill_value is not None
            else inherited_fill
        )
        stroke = (
            _normalise_paint(stroke_value, path, "stroke")
            if stroke_value is not None
            else inherited_stroke
        )

        if name in DRAWABLE_ELEMENTS:
            if name == "line":
                if stroke is None or stroke == "none":
                    raise AssetCheckError(f"{path}: <line> needs a stroke colour")
                if stroke not in normalised_allowed:
                    raise AssetCheckError(f"{path}: stroke colour {stroke} is outside the vector palette")
                used.add(stroke)
            else:
                # SVG's initial fill is black; a shape that relies on it is
                # outside the palette unless the palette explicitly contains it.
                effective_fill = fill if fill is not None else "#000000"
                effective_stroke = stroke if stroke is not None else "none"
                if effective_fill == "none" and effective_stroke == "none":
                    raise AssetCheckError(f"{path}: <{name}> has no visible paint")
                if effective_fill != "none":
                    if effective_fill not in normalised_allowed:
                        raise AssetCheckError(
                            f"{path}: fill colour {effective_fill} is outside the vector palette"
                        )
                    used.add(effective_fill)
                if effective_stroke != "none":
                    if effective_stroke not in normalised_allowed:
                        raise AssetCheckError(
                            f"{path}: stroke colour {effective_stroke} is outside the vector palette"
                        )
                    used.add(effective_stroke)

        for child in element:
            visit(child, fill, stroke)

    visit(root, None, None)
    if not used:
        raise AssetCheckError(f"{path}: SVG uses no palette colours (blank asset)")

    return {
        "path": str(path),
        "size": [width, height],
        "colors": len(used),
    }


def verify_raster(path: Path, width: int, height: int, require_alpha: bool) -> dict:
    """Check the PNG derived from an SVG source (size and visible content)."""
    if not path.exists():
        raise AssetCheckError(f"asset missing: {path}")
    image = Image.open(path)
    if image.mode == "RGB" and not require_alpha:
        image = image.convert("RGBA")
    elif image.mode != "RGBA":
        expected = "RGBA" if require_alpha else "RGBA or RGB"
        raise AssetCheckError(f"{path}: mode is {image.mode}, expected {expected}")
    check_size(image, width, height, path)
    check_alpha(image, require_alpha, path)
    visible = visible_colors(image)
    if not visible:
        raise AssetCheckError(f"{path}: raster has no visible pixels")
    return {
        "path": str(path),
        "size": [image.width, image.height],
        "colors": len(visible),
    }
