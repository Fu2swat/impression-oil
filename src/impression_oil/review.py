"""Post-generate self-check: style gaps vs Monet, then scenery lock.

Checklist pass/fail is computed by this module, never hardcoded as all-pass.
When no engine result exists, items still have a stable structure so the
review panel and tests can run (detail explains that the engine is not ready).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageFilter, ImageOps, ImageStat

from impression_oil.scene import open_rgb

# UI labels, in the order and wording of the approved mockup / brief.
CHECKLIST_SPEC: tuple[tuple[str, str], ...] = (
    ("sky", "天空：横扫与湿接，没有鱼鳞结块"),
    ("color", "色彩：有环境色和光学混合"),
    ("mountains", "远山溶进雾气，没有硬边"),
    ("flowers", "花田是抽象色块，不是印章"),
    ("figure", "人物是溶边色团，不是插画切图"),
    ("scenery", "景色/构图是否走样（湖面丢失、多出树、岸线错位、人物偏移、背景被换）"),
)

REVIEW_TITLE = "已按补丁自查，正在重画"
ENGINE_NOT_READY_DETAIL = "本机模型未安装，0.0.1 无法出图核验。"


@dataclass(frozen=True)
class ChecklistItem:
    key: str
    label: str
    passed: bool
    detail: str = ""


@dataclass(frozen=True)
class ReviewResult:
    items: tuple[ChecklistItem, ...]
    style_issues: tuple[str, ...]
    scenery_issues: tuple[str, ...]
    status_line: str
    title: str = REVIEW_TITLE
    engine_ready: bool = True

    @property
    def all_passed(self) -> bool:
        return self.engine_ready and all(item.passed for item in self.items)

    def item(self, key: str) -> ChecklistItem | None:
        for item in self.items:
            if item.key == key:
                return item
        return None


def _resize(image: Image.Image, width: int, height: int) -> Image.Image:
    return image.convert("RGB").resize((width, height), Image.Resampling.BOX)


def _grid(image: Image.Image, cols: int, rows: int) -> list[list[tuple[int, int, int]]]:
    small = _resize(image, cols, rows)
    data = list(small.getdata())
    return [data[y * cols:(y + 1) * cols] for y in range(rows)]


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


def _hue_mean_var(cells: list[tuple[int, int, int]]) -> tuple[float, float, float]:
    if not cells:
        return 0.0, 0.0, 0.0
    # Circular hue via vectors, plus saturation / value means.
    xs = ys = sats = vals = 0.0
    for r, g, b in cells:
        h, s, v = _rgb_to_hsv(r, g, b)
        rad = math.radians(h)
        xs += math.cos(rad) * s
        ys += math.sin(rad) * s
        sats += s
        vals += v
    n = len(cells)
    mean_s = sats / n
    mean_v = vals / n
    # Resultant length close to mean_s means hues agree; low length with high s means mixed hues.
    resultant = math.hypot(xs / n, ys / n)
    hue_coherence = resultant / mean_s if mean_s > 1e-6 else 1.0
    return mean_s, mean_v, hue_coherence


def _region(grid: list[list[tuple[int, int, int]]], y0: float, y1: float) -> list[tuple[int, int, int]]:
    rows = len(grid)
    a = int(rows * y0)
    b = max(a + 1, int(rows * y1))
    cells: list[tuple[int, int, int]] = []
    for row in grid[a:b]:
        cells.extend(row)
    return cells


def _high_frequency_uniformity(image: Image.Image, box: tuple[int, int, int, int]) -> float:
    """High when a crop is filled with even, small-scale texture (fish-scale risk)."""
    crop = image.convert("L").crop(box)
    if crop.width < 16 or crop.height < 16:
        return 0.0
    crop = crop.resize((64, 40), Image.Resampling.BILINEAR)
    edges = crop.filter(ImageFilter.FIND_EDGES)
    # Tile energy of the edge map; uniformity of high energy is the warning sign.
    energies = []
    tw, th = 8, 5
    for y in range(0, crop.height, th):
        for x in range(0, crop.width, tw):
            tile = edges.crop((x, y, min(x + tw, crop.width), min(y + th, crop.height)))
            energies.append(ImageStat.Stat(tile).mean[0])
    if not energies:
        return 0.0
    mean_e = sum(energies) / len(energies)
    var_e = sum((e - mean_e) ** 2 for e in energies) / len(energies)
    # High mean (busy texture) and low variance (the same everywhere) -> fish-scale.
    if mean_e < 8:
        return 0.0
    return mean_e / (1.0 + math.sqrt(var_e))


def _edge_strength(image: Image.Image, y0: float, y1: float) -> float:
    gray = image.convert("L")
    w, h = gray.size
    band = gray.crop((0, int(h * y0), w, max(int(h * y0) + 1, int(h * y1))))
    edges = band.filter(ImageFilter.FIND_EDGES)
    return float(ImageStat.Stat(edges).mean[0])


def _count_small_blobs(image: Image.Image, y0: float) -> int:
    """Count small saturated spots in the lower area (stamp-flower risk)."""
    w, h = image.size
    crop = image.crop((0, int(h * y0), w, h)).convert("RGB")
    small = crop.resize((48, 24), Image.Resampling.BOX)
    pixels = list(small.getdata())
    ww, hh = small.size
    marked = [False] * (ww * hh)

    def is_blob(i: int) -> bool:
        r, g, b = pixels[i]
        _h, s, v = _rgb_to_hsv(r, g, b)
        return s >= 0.45 and v >= 0.45 and not (55 <= _h <= 150)

    count = 0
    for i in range(ww * hh):
        if marked[i] or not is_blob(i):
            continue
        # flood
        stack = [i]
        marked[i] = True
        size = 0
        while stack:
            j = stack.pop()
            size += 1
            y, x = j // ww, j % ww
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if 0 <= nx < ww and 0 <= ny < hh:
                    k = ny * ww + nx
                    if not marked[k] and is_blob(k):
                        marked[k] = True
                        stack.append(k)
        if 2 <= size <= 18:
            count += 1
    return count


def _skin_mask(grid: list[list[tuple[int, int, int]]]) -> list[tuple[int, int]]:
    cells = []
    for y, row in enumerate(grid):
        for x, (r, g, b) in enumerate(row):
            if r > 90 and g > 40 and b > 20 and r > g + 8 and r > b and max(r, g, b) - min(r, g, b) > 15:
                h, s, v = _rgb_to_hsv(r, g, b)
                if 0 <= h <= 50 and 0.12 <= s <= 0.75:
                    cells.append((x, y))
    return cells


def _figure_cutout_score(image: Image.Image) -> float:
    """High when a figure-like mass has a hard halo, like a pasted cutout."""
    grid = _grid(image, 48, 48)
    skin = _skin_mask(grid)
    if len(skin) < 6:
        return 0.0
    skin_set = set(skin)
    # Contrast between skin-adjacent background vs interior.
    border_deltas = []
    for x, y in skin:
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if (nx, ny) in skin_set:
                continue
            if 0 <= ny < 48 and 0 <= nx < 48:
                a = grid[y][x]
                b = grid[ny][nx]
                delta = abs(a[0] - b[0]) + abs(a[1] - b[1]) + abs(a[2] - b[2])
                border_deltas.append(delta)
    if not border_deltas:
        return 0.0
    return sum(border_deltas) / len(border_deltas)


def _band_layout(image: Image.Image, bands: int = 6, cols: int = 8) -> list[tuple[float, float, float]]:
    small = _resize(image, cols, bands)
    data = list(small.getdata())
    out = []
    for y in range(bands):
        rs = gs = bs = 0
        for x in range(cols):
            r, g, b = data[y * cols + x]
            rs += r
            gs += g
            bs += b
        n = cols
        out.append((rs / n, gs / n, bs / n))
    return out


def _layout_similarity(a: Image.Image, b: Image.Image) -> float:
    la, lb = _band_layout(a), _band_layout(b)
    # Also compare a coarse 8x8 map.
    ga = _resize(a, 8, 8)
    gb = _resize(b, 8, 8)
    pa, pb = list(ga.getdata()), list(gb.getdata())
    dots = na = nb = 0.0
    for ca, cb in zip(pa, pb):
        # luminance + color
        va = (ca[0] * 0.3 + ca[1] * 0.6 + ca[2] * 0.1, ca[0], ca[1], ca[2])
        vb = (cb[0] * 0.3 + cb[1] * 0.6 + cb[2] * 0.1, cb[0], cb[1], cb[2])
        dots += sum(x * y for x, y in zip(va, vb))
        na += sum(x * x for x in va)
        nb += sum(y * y for y in vb)
    if na <= 0 or nb <= 0:
        return 0.0
    return dots / (math.sqrt(na) * math.sqrt(nb))


def _water_present(image: Image.Image) -> bool:
    grid = _grid(image, 24, 24)
    mid = _region(grid, 0.32, 0.68)
    water = 0
    for r, g, b in mid:
        h, s, v = _rgb_to_hsv(r, g, b)
        if 185 <= h <= 255 and s >= 0.15 and 0.18 <= v <= 0.85:
            water += 1
    return (water / max(1, len(mid))) >= 0.22


def _extra_tree_mass(source: Image.Image, result: Image.Image) -> bool:
    """Result has a strong mid-frame vertical green mass that the source lacks."""
    def green_cols(image: Image.Image) -> list[float]:
        grid = _grid(image, 16, 16)
        scores = []
        for x in range(16):
            greenery = 0
            for y in range(3, 12):
                r, g, b = grid[y][x]
                h, s, v = _rgb_to_hsv(r, g, b)
                if 70 <= h <= 150 and s >= 0.25 and v >= 0.15:
                    greenery += 1
            scores.append(greenery / 9)
        return scores

    src, res = green_cols(source), green_cols(result)
    return any(res[i] - src[i] >= 0.45 and res[i] >= 0.55 for i in range(16))


def _skin_centroid(image: Image.Image) -> tuple[float, float] | None:
    grid = _grid(image, 32, 32)
    skin = _skin_mask(grid)
    if len(skin) < 5:
        return None
    cx = sum(x for x, _ in skin) / len(skin)
    cy = sum(y for _, y in skin) / len(skin)
    return cx / 32, cy / 32


def inspect_scenery(source: Image.Image, result: Image.Image) -> list[str]:
    issues: list[str] = []
    if _water_present(source) and not _water_present(result):
        issues.append("湖面丢失")
    if _extra_tree_mass(source, result):
        issues.append("多出树")
    src_c = _skin_centroid(source)
    res_c = _skin_centroid(result)
    if src_c and res_c:
        dist = math.hypot(src_c[0] - res_c[0], src_c[1] - res_c[1])
        if dist >= 0.12:
            issues.append("人物偏移")
    similarity = _layout_similarity(source, result)
    if similarity < 0.92:
        # Shore / horizon shift or background swap often show up as layout drift.
        if "湖面丢失" not in issues:
            # Distinguish a nearly different picture.
            if similarity < 0.80:
                issues.append("背景被换")
            else:
                issues.append("岸线错位")
    return issues


def inspect_style(source: Image.Image, result: Image.Image) -> dict[str, tuple[bool, str]]:
    """Return pass/fail + detail for the five style dimensions."""
    w, h = result.size
    top_box = (0, 0, w, max(8, int(h * 0.32)))
    sky_score = _high_frequency_uniformity(result, top_box)
    sky_ok = sky_score < 14.0
    sky_detail = (
        "天空为宽大横扫与湿接"
        if sky_ok
        else "天空出现均匀短笔／结块肌理，需改横扫与湿接"
    )

    # Dead local color: large adjacent bands with high hue coherence and little shared tint.
    grid = _grid(result, 24, 24)
    top, mid, bot = _region(grid, 0.0, 0.3), _region(grid, 0.3, 0.6), _region(grid, 0.6, 1.0)
    _, _, coh_top = _hue_mean_var(top)
    _, _, coh_mid = _hue_mean_var(mid)
    # Cross-band color sharing: average of mid should not be isolated from top.
    def mean_rgb(cells):
        n = max(1, len(cells))
        return tuple(sum(c[i] for c in cells) / n for i in range(3))

    mt, mm = mean_rgb(top), mean_rgb(mid)
    cross = abs(mt[0] - mm[0]) + abs(mt[1] - mm[1]) + abs(mt[2] - mm[2])
    # Photographic or poster-like separations tend to have high coherence + a hard jump.
    color_ok = not (coh_top > 0.88 and coh_mid > 0.88 and cross > 90)
    color_detail = (
        "色彩有环境色与光学混合"
        if color_ok
        else "色带互不往来，缺少环境色和倒影"
    )

    # Mountains / horizon hardness. Compare result edge strength in the mid-sky band
    # against a blurred expectation; a photo-like hard ridge fails.
    ridge = _edge_strength(result, 0.22, 0.50)
    # Soft atmospheric mountains after a downscale should be modest.
    mountains_ok = ridge < 22.0
    mountains_detail = (
        "远山溶进雾气"
        if mountains_ok
        else "远山过实过利，没有溶进雾气"
    )

    stamps = _count_small_blobs(result, 0.58)
    flowers_ok = stamps < 14
    flowers_detail = (
        "花田是抽象色块"
        if flowers_ok
        else "花田出现可数的印章状小花，需收成色块"
    )

    cut = _figure_cutout_score(result)
    # Only fail when there is a strong cutout halo.
    figure_ok = cut < 140
    figure_detail = (
        "人物是溶边色团"
        if figure_ok
        else "人物边缘过硬，像插画切图"
    )

    return {
        "sky": (sky_ok, sky_detail),
        "color": (color_ok, color_detail),
        "mountains": (mountains_ok, mountains_detail),
        "flowers": (flowers_ok, flowers_detail),
        "figure": (figure_ok, figure_detail),
    }


def build_status_line(style_issues: list[str], scenery_issues: list[str]) -> str:
    fixes: list[str] = []
    labels = {
        "sky": "天空改横扫与湿接",
        "color": "加强环境色和光学混合",
        "mountains": "远山溶进雾气",
        "flowers": "花田收成抽象色块",
        "figure": "人物收成溶边色团",
    }
    for key in style_issues:
        if key in labels:
            fixes.append(labels[key])
    if scenery_issues:
        named = "、".join(scenery_issues)
        if style_issues:
            fixes.append(f"保住已改善的画法，并把{named}按原照锁回去")
        else:
            fixes.append(f"把{named}按原照锁回去")
    if not fixes:
        return "正在按补丁重画：再核一遍画法与景色。"
    return "正在按补丁重画：" + "；".join(fixes) + "。"


def _engine_not_ready_result() -> ReviewResult:
    items = tuple(
        ChecklistItem(key=key, label=label, passed=False, detail=ENGINE_NOT_READY_DETAIL)
        for key, label in CHECKLIST_SPEC
    )
    return ReviewResult(
        items=items,
        style_issues=tuple(key for key, _ in CHECKLIST_SPEC if key != "scenery"),
        scenery_issues=("引擎未就绪",),
        status_line="本机模型未安装，0.0.1 无法按补丁重画。本次不会开始下载。",
        engine_ready=False,
    )


def review_images(source: Image.Image, result: Image.Image) -> ReviewResult:
    source = source.convert("RGB")
    result = result.convert("RGB")
    # Align sizes for fair scenery comparison.
    if result.size != source.size:
        result_for_scene = result.resize(source.size, Image.Resampling.LANCZOS)
    else:
        result_for_scene = result

    style = inspect_style(source, result)
    scenery_issues = inspect_scenery(source, result_for_scene)
    items: list[ChecklistItem] = []
    style_issues: list[str] = []
    for key, label in CHECKLIST_SPEC:
        if key == "scenery":
            passed = not scenery_issues
            if passed:
                detail = "构图与主要景色与原照一致"
            else:
                detail = "景色走样：" + "、".join(scenery_issues) + "，将按原照锁回"
            items.append(ChecklistItem(key=key, label=label, passed=passed, detail=detail))
        else:
            passed, detail = style[key]
            if not passed:
                style_issues.append(key)
            items.append(ChecklistItem(key=key, label=label, passed=passed, detail=detail))
    status = build_status_line(style_issues, scenery_issues)
    return ReviewResult(
        items=tuple(items),
        style_issues=tuple(style_issues),
        scenery_issues=tuple(scenery_issues),
        status_line=status,
        engine_ready=True,
    )


def review_paths(
    source_path: Path | None,
    result_path: Path | None,
    *,
    engine_ready: bool = True,
) -> ReviewResult:
    if not engine_ready or source_path is None or result_path is None:
        return _engine_not_ready_result()
    source = open_rgb(source_path)
    result = open_rgb(result_path)
    return review_images(source, result)
