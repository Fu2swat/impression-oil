"""Shared helpers for building synthetic photos in tmp_path."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image, ImageDraw


def write_bands(
    path: Path,
    *,
    size: tuple[int, int] = (400, 600),
    top: tuple[int, int, int] = (120, 180, 230),
    mid: tuple[int, int, int] = (40, 110, 190),
    bottom: tuple[int, int, int] = (80, 150, 50),
    figure: tuple[int, int, int, int] | None = None,
) -> Path:
    """Vertical landscape: sky / water / field, optional figure box (x0,y0,x1,y1)."""
    image = Image.new("RGB", size)
    w, h = size
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, w, int(h * 0.36)), fill=top)
    draw.rectangle((0, int(h * 0.36), w, int(h * 0.62)), fill=mid)
    draw.rectangle((0, int(h * 0.62), w, h), fill=bottom)
    if figure:
        x0, y0, x1, y1 = figure
        # A back-figure-like cool dress plus a warm skin-tone head.
        head_h = max(8, (y1 - y0) // 5)
        draw.ellipse((x0 + (x1 - x0) // 4, y0, x1 - (x1 - x0) // 4, y0 + head_h), fill=(210, 170, 140))
        draw.rectangle((x0, y0 + head_h - 2, x1, y1), fill=(70, 110, 170))
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)
    return path


def write_portrait(path: Path, size: tuple[int, int] = (320, 420)) -> Path:
    w, h = size
    image = Image.new("RGB", size, (230, 220, 210))
    draw = ImageDraw.Draw(image)
    # Large central skin mass with simple features suggested by color only.
    draw.rectangle((w * 0.15, h * 0.08, w * 0.85, h * 0.95), fill=(228, 186, 150))
    draw.ellipse((w * 0.22, h * 0.10, w * 0.78, h * 0.62), fill=(232, 190, 155))
    image.save(path)
    return path


@pytest.fixture
def lakeside(tmp_path: Path) -> Path:
    return write_bands(
        tmp_path / "lakeside.png",
        figure=(170, 300, 230, 500),
    )
