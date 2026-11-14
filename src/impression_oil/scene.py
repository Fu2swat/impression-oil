"""Infer portrait / landscape / figure-in-landscape from a source photo.

The user does not pick a mode first. Heuristics are based on color layout
and skin-tone mass; they only steer prompt constraints, never rewrite the scene.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from PIL import Image, ImageOps


SUPPORTED_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


class FileOpenError(Exception):
    """User-facing Chinese error when a photo cannot be opened."""

    def __init__(self, status_text: str) -> None:
        super().__init__(status_text)
        self.status_text = status_text


class SceneKind(str, Enum):
    LANDSCAPE = "landscape"
    PORTRAIT = "portrait"
    FIGURE_IN_LANDSCAPE = "figure_in_landscape"


@dataclass(frozen=True)
class SceneAnalysis:
    kind: SceneKind
    has_face: bool
    has_figure: bool
    has_water: bool
    has_sky: bool
    has_flowers: bool
    has_mountains: bool
    width: int
    height: int
    notes: str = ""
    extras: dict = field(default_factory=dict)


def validate_image_path(path: Path) -> Path:
    path = Path(path)
    try:
        if not path.exists() or not path.is_file():
            raise FileOpenError("找不到该文件。")
    except PermissionError as exc:
        raise FileOpenError("没有权限读取该文件。") from exc
    if path.suffix.lower() not in SUPPORTED_SUFFIXES:
        raise FileOpenError("暂不支持该图片格式，请使用 JPG 或 PNG。")
    return path


def open_rgb(path: Path) -> Image.Image:
    """Open an image, apply EXIF orientation, return an RGB copy."""
    path = validate_image_path(path)
    try:
        with Image.open(path) as raw:
            raw = ImageOps.exif_transpose(raw)
            raw.load()
            image = raw.convert("RGB")
    except FileOpenError:
        raise
    except PermissionError as exc:
        raise FileOpenError("没有权限读取该文件。") from exc
    except FileNotFoundError as exc:
        raise FileOpenError("找不到该文件。") from exc
    except OSError as exc:
        raise FileOpenError("无法打开该图片，文件可能已损坏。") from exc
    if image.width < 8 or image.height < 8:
        raise FileOpenError("图片尺寸过小，请换一张照片。")
    return image


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return lo if value < lo else hi if value > hi else value


def _rgb_to_hsv(r: int, g: int, b: int) -> tuple[float, float, float]:
    rf, gf, bf = r / 255.0, g / 255.0, b / 255.0
    mx, mn = max(rf, gf, bf), min(rf, gf, bf)
    diff = mx - mn
    if diff == 0:
        h = 0.0
    elif mx == rf:
        h = (60 * ((gf - bf) / diff) + 360) % 360
    elif mx == gf:
        h = (60 * ((bf - rf) / diff) + 120) % 360
    else:
        h = (60 * ((rf - gf) / diff) + 240) % 360
    s = 0.0 if mx == 0 else diff / mx
    return h, s, mx


def _is_skin(r: int, g: int, b: int) -> bool:
    if r < 80 or g < 30 or b < 15:
        return False
    if r <= g or r <= b:
        return False
    if max(r, g, b) - min(r, g, b) < 15:
        return False
    # Reject strong greens / very blue pixels often found in landscapes.
    if g > r - 10 and g > b + 20:
        return False
    h, s, v = _rgb_to_hsv(r, g, b)
    return 0 <= h <= 50 and 0.12 <= s <= 0.75 and v >= 0.25


def _is_sky(r: int, g: int, b: int) -> bool:
    h, s, v = _rgb_to_hsv(r, g, b)
    if v > 0.72 and s < 0.22:
        return True  # bright cloud / pale sky
    return 190 <= h <= 250 and s >= 0.12 and v >= 0.35


def _is_water(r: int, g: int, b: int) -> bool:
    h, s, v = _rgb_to_hsv(r, g, b)
    return 185 <= h <= 255 and s >= 0.15 and 0.18 <= v <= 0.85


def _is_vegetation(r: int, g: int, b: int) -> bool:
    h, s, v = _rgb_to_hsv(r, g, b)
    return 55 <= h <= 150 and s >= 0.18 and v >= 0.15


def _is_flower_like(r: int, g: int, b: int) -> bool:
    h, s, v = _rgb_to_hsv(r, g, b)
    if s < 0.35 or v < 0.35:
        return False
    return (h <= 70) or (h >= 280) or (300 <= h or h <= 20) or (40 <= h <= 70)


def _is_mountain_like(r: int, g: int, b: int) -> bool:
    h, s, v = _rgb_to_hsv(r, g, b)
    # Cool grey-blue / violet distant range, mid value.
    return (200 <= h <= 280 or s < 0.18) and 0.25 <= v <= 0.75 and not _is_sky(r, g, b)


def _sample_grid(image: Image.Image, cols: int = 32, rows: int = 32) -> list[list[tuple[int, int, int]]]:
    small = image.resize((cols, rows), Image.Resampling.BOX)
    pixels = list(small.getdata())
    grid = []
    for y in range(rows):
        row = [pixels[y * cols + x] for x in range(cols)]
        grid.append(row)
    return grid


def _fraction(cells: list[tuple[int, int, int]], pred) -> float:
    if not cells:
        return 0.0
    return sum(1 for c in cells if pred(*c)) / len(cells)


def _band(grid: list[list[tuple[int, int, int]]], y0: float, y1: float) -> list[tuple[int, int, int]]:
    rows = len(grid)
    start = int(rows * y0)
    end = max(start + 1, int(rows * y1))
    cells: list[tuple[int, int, int]] = []
    for row in grid[start:end]:
        cells.extend(row)
    return cells


def analyze_image(image: Image.Image) -> SceneAnalysis:
    rgb = image.convert("RGB")
    width, height = rgb.size
    grid = _sample_grid(rgb, 32, 32)
    flat = [cell for row in grid for cell in row]

    top = _band(grid, 0.0, 0.32)
    mid = _band(grid, 0.32, 0.62)
    bottom = _band(grid, 0.62, 1.0)

    sky_frac = _fraction(top, _is_sky)
    water_frac = _fraction(mid, _is_water)
    vegetation_frac = _fraction(bottom, _is_vegetation) + _fraction(mid, _is_vegetation) * 0.3
    flower_frac = _fraction(bottom, _is_flower_like)
    mountain_frac = _fraction(_band(grid, 0.22, 0.55), _is_mountain_like)

    # Skin masses: collect coordinates of skin-like cells.
    skin_cells = [(x, y) for y, row in enumerate(grid) for x, cell in enumerate(row) if _is_skin(*cell)]
    skin_frac = len(skin_cells) / max(1, len(flat))
    has_figure = skin_frac >= 0.015 or len(skin_cells) >= 8

    # A close portrait occupies the center with a larger skin mass.
    if skin_cells:
        cx = sum(x for x, _ in skin_cells) / len(skin_cells)
        cy = sum(y for _, y in skin_cells) / len(skin_cells)
        center_skin = sum(1 for x, y in skin_cells if 8 <= x <= 23 and 6 <= y <= 26)
        center_frac = center_skin / max(1, len(skin_cells))
        # Vertical extent of the skin blob relative to the frame.
        ys = [y for _, y in skin_cells]
        extent = (max(ys) - min(ys) + 1) / 32
    else:
        cx = cy = center_frac = extent = 0.0

    has_sky = sky_frac >= 0.28
    has_water = water_frac >= 0.22
    has_flowers = flower_frac >= 0.12
    has_mountains = mountain_frac >= 0.12 and has_sky
    landscape_cues = has_sky or has_water or vegetation_frac >= 0.22 or has_mountains

    has_face = False
    if skin_frac >= 0.08 and center_frac >= 0.45 and extent >= 0.28:
        has_face = True
        kind = SceneKind.PORTRAIT
        # A visible environment around a person still counts as a portrait
        # with landscape constraints added via has_sky / has_water flags.
        if landscape_cues and skin_frac < 0.18 and (has_sky or has_water):
            kind = SceneKind.FIGURE_IN_LANDSCAPE
            has_face = False  # typically a back figure in these photos
    elif has_figure and landscape_cues:
        kind = SceneKind.FIGURE_IN_LANDSCAPE
    elif has_figure and not landscape_cues and skin_frac >= 0.06:
        kind = SceneKind.PORTRAIT
        has_face = True
    else:
        kind = SceneKind.LANDSCAPE

    notes = (
        f"kind={kind.value} sky={sky_frac:.2f} water={water_frac:.2f} "
        f"veg={vegetation_frac:.2f} flower={flower_frac:.2f} skin={skin_frac:.2f}"
    )
    return SceneAnalysis(
        kind=kind,
        has_face=has_face,
        has_figure=has_figure or has_face,
        has_water=has_water,
        has_sky=has_sky,
        has_flowers=has_flowers,
        has_mountains=has_mountains,
        width=width,
        height=height,
        notes=notes,
        extras={
            "sky_frac": sky_frac,
            "water_frac": water_frac,
            "vegetation_frac": vegetation_frac,
            "flower_frac": flower_frac,
            "mountain_frac": mountain_frac,
            "skin_frac": skin_frac,
            "skin_center": (cx, cy),
        },
    )


def analyze_scene(path: Path) -> SceneAnalysis:
    return analyze_image(open_rgb(path))
