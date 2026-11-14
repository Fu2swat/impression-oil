from pathlib import Path

from PIL import Image, ImageDraw

from impression_oil.review import (
    CHECKLIST_SPEC,
    ENGINE_NOT_READY_DETAIL,
    REVIEW_TITLE,
    ReviewResult,
    build_status_line,
    review_images,
    review_paths,
)
from impression_oil.skill_prompts import build_prompts, scenery_lock_instructions
from tests.conftest import write_bands


def test_checklist_structure_without_engine() -> None:
    result = review_paths(None, None, engine_ready=False)
    assert isinstance(result, ReviewResult)
    assert result.engine_ready is False
    assert result.all_passed is False
    assert result.title == REVIEW_TITLE
    assert len(result.items) == 6
    keys = [item.key for item in result.items]
    labels = [item.label for item in result.items]
    assert keys == [spec[0] for spec in CHECKLIST_SPEC]
    assert labels == [spec[1] for spec in CHECKLIST_SPEC]
    assert all(item.detail == ENGINE_NOT_READY_DETAIL for item in result.items)
    assert "引擎未就绪" in result.scenery_issues or "未安装" in result.status_line


def test_checklist_structure_from_images(tmp_path: Path) -> None:
    source = write_bands(tmp_path / "src.png")
    # A result that keeps the same layout should produce a 6-item checklist.
    result_path = write_bands(tmp_path / "ok.png", top=(130, 170, 210), mid=(60, 120, 180), bottom=(90, 140, 60))
    review = review_paths(source, result_path, engine_ready=True)
    assert len(review.items) == 6
    assert [item.key for item in review.items] == [spec[0] for spec in CHECKLIST_SPEC]
    assert review.engine_ready is True
    # Scenery should remain acceptable for a near-faithful layout.
    scenery = review.item("scenery")
    assert scenery is not None
    assert scenery.passed is True
    assert review.scenery_issues == ()


def test_lost_lake_flags_scenery_and_builds_lock_prompt(tmp_path: Path) -> None:
    source = write_bands(tmp_path / "src.png", figure=(170, 300, 230, 500))
    # Mid band becomes field instead of water: the lake is gone.
    lost = write_bands(
        tmp_path / "lost.png",
        top=(130, 170, 210),
        mid=(200, 190, 80),
        bottom=(210, 200, 70),
        figure=(170, 300, 230, 500),
    )
    review = review_paths(source, lost, engine_ready=True)
    scenery = review.item("scenery")
    assert scenery is not None
    assert scenery.passed is False
    assert "湖面丢失" in review.scenery_issues
    assert "湖面" in scenery.detail or "走样" in scenery.detail
    status = build_status_line(list(review.style_issues), list(review.scenery_issues))
    assert "湖面丢失" in status
    assert status.startswith("正在按补丁重画：")

    from impression_oil.scene import analyze_scene

    prompts = build_prompts(
        analyze_scene(source),
        style_issues=list(review.style_issues),
        scenery_issues=list(review.scenery_issues),
    )
    assert prompts.scenery_lock
    assert "湖面丢失" in prompts.prompt
    assert "source photograph" in scenery_lock_instructions(list(review.scenery_issues)).lower()


def test_status_line_names_concrete_fixes() -> None:
    line = build_status_line(["sky", "color"], ["湖面丢失"])
    assert line.startswith("正在按补丁重画：")
    assert "天空" in line
    assert "环境色" in line
    assert "湖面丢失" in line
    assert "原照" in line
