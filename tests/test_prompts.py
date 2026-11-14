from impression_oil.scene import SceneAnalysis, SceneKind
from impression_oil.skill_prompts import (
    BANNED_PHRASES,
    contains_banned_phrase,
    build_prompts,
    scenery_lock_instructions,
)


def _scene(**overrides) -> SceneAnalysis:
    data = dict(
        kind=SceneKind.FIGURE_IN_LANDSCAPE,
        has_face=False,
        has_figure=True,
        has_water=True,
        has_sky=True,
        has_flowers=True,
        has_mountains=True,
        width=400,
        height=600,
        notes="test",
    )
    data.update(overrides)
    return SceneAnalysis(**data)


def test_prompts_contain_required_constraints() -> None:
    prompts = build_prompts(_scene())
    blob = prompts.prompt.lower()
    for needle in (
        "optical mixing",
        "wet-on-wet",
        "sweeping",
        "complementary shadows",
        "environmental color",
        "soft edges",
        "canvas",
        "do not draw individual",
        "watermark",
        "logo",
        "lock composition",
        "monet",
        "never black",
    ):
        assert needle in blob, f"missing constraint: {needle}"
    # Van Gogh must be banned, not used as the style target in the positive prompt.
    assert "van gogh" not in blob
    assert "post-impressionism" not in blob
    negative = prompts.negative_prompt.lower()
    for needle in (
        "photorealism",
        "beauty filter",
        "van gogh",
        "kuwahara",
        "oil shader",
        "watermark",
        "fish-scale",
        "harsh noon",
    ):
        assert needle in negative, f"missing negative: {needle}"


def test_prompts_never_contain_banned_face_phrases() -> None:
    portrait = build_prompts(
        _scene(kind=SceneKind.PORTRAIT, has_face=True, has_figure=True, has_water=False)
    )
    landscape = build_prompts(_scene())
    patched = build_prompts(
        _scene(kind=SceneKind.PORTRAIT, has_face=True, has_figure=True),
        style_issues=["figure", "sky"],
        scenery_issues=["人物偏移"],
    )
    for prompts in (portrait, landscape, patched):
        blob = prompts.prompt + "\n" + prompts.negative_prompt
        assert contains_banned_phrase(blob) == []
        lowered = blob.lower()
        for phrase in BANNED_PHRASES:
            assert phrase.lower() not in lowered
    # Portrait instructions stay positive: features are suggested, not erased.
    assert "eyes, brows, nose and lips" in portrait.prompt.lower() or "eyes, brows, nose" in portrait.prompt.lower()


def test_scenery_lock_instructions_included_when_flagged() -> None:
    issues = ["湖面丢失", "岸线错位"]
    text = scenery_lock_instructions(issues)
    assert "湖面丢失" in text
    assert "岸线错位" in text
    assert "lock" in text.lower() or "原照" in text
    assert "source photograph" in text.lower()
    prompts = build_prompts(_scene(), scenery_issues=issues)
    assert prompts.scenery_lock
    assert "湖面丢失" in prompts.prompt
    assert "scenery_lock_patch" in prompts.constraints
    # Style improvements are kept while scenery is locked back.
    assert "improved sky" in prompts.prompt.lower() or "keep the improved" in prompts.prompt.lower()
