from pathlib import Path

from impression_oil.scene import SceneKind, analyze_scene
from tests.conftest import write_bands, write_portrait


def test_lakeside_is_landscape_or_figure(tmp_path: Path) -> None:
    path = write_bands(tmp_path / "lake.png", figure=(170, 300, 230, 500))
    scene = analyze_scene(path)
    assert scene.has_sky
    assert scene.has_water
    assert scene.kind in {SceneKind.LANDSCAPE, SceneKind.FIGURE_IN_LANDSCAPE}


def test_open_water_landscape(tmp_path: Path) -> None:
    path = write_bands(tmp_path / "open.png")  # no figure
    scene = analyze_scene(path)
    assert scene.kind is SceneKind.LANDSCAPE
    assert scene.has_water
    assert scene.has_sky


def test_portrait_inference(tmp_path: Path) -> None:
    path = write_portrait(tmp_path / "face.png")
    scene = analyze_scene(path)
    assert scene.kind is SceneKind.PORTRAIT
    assert scene.has_face
