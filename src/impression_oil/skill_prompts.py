"""Monet Impressionism prompt construction.

Prompts write constraints, not vague style names. Composition stays locked
to the source photo. This module must never emit banned face phrases.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from impression_oil.scene import SceneAnalysis, SceneKind

# Phrases that must never appear in any prompt (positive or negative).
BANNED_PHRASES = (
    "no eyes",
    "without eyes",
    "completely out of focus",
    "face as a color mass",
    "face as a colour mass",
    "face only a color mass",
    "没有眼睛",
    "完全失焦",
    "脸只是色团",
)

FOUR_HARD_RULES = (
    "broad simplified color masses, minimalist brushwork, forms reduced to essential shapes",
    "expressive varied strokes with visible impasto and palette-knife texture; not a uniform mosaic or dense weaving",
    "do not draw individual leaves, individual flowers, or blades of grass; only color masses",
    "sparse strokes so the canvas tooth shows through",
)

CORE_TECHNIQUE = (
    "Claude Monet Impressionist oil painting, en plein air, envelope light, "
    "environmental color and reflections, optical mixing of neighboring hues, "
    "soft edges dissolving into air, wet-on-wet transitions, "
    "large loose sweeping brushstrokes, complementary shadows in violet and blue, never black shadows. "
    "Strokes have direction and clear layers; do not shatter form for the sake of chaos; "
    "do not turn impasto into an even texture map."
)

COMPOSITION_LOCK = (
    "Lock composition, viewpoint, and background exactly to the source photograph. "
    "Change only technique and color, never the scene. "
    "Do not copy, redraw, or transfer any watermark, logo, signature, or text from the source. "
    "Keep water, shoreline, mountains, sky bands, flower or grass belts, and figure position, facing, and pose in place. "
    "Do not invent extra trees or replace the background."
)

NEGATIVE_CORE = (
    "photorealism, photograph, digital illustration, concept art, anime, "
    "beauty filter, airbrushed skin, harsh noon sunlight, high-contrast midday light, "
    "even short strokes filling the surface, fish-scale impasto, washboard texture, "
    "uniform texture-map impasto, 3D material render, oil shader, Kuwahara filter, "
    "edge-preserving oil filter, Van Gogh, post-impressionism, swirling starry night, "
    "heavy black outlines, black shadows, dead unmixed local color, "
    "pure unmixed blue sky, pure unmixed blue water, game-matte hard-edged mountains, "
    "stamp-like countable flowers, flower brush stamps, fashion-illustration cutout figure, "
    "watermark, logo, signature, typography, text, caption"
)


@dataclass(frozen=True)
class PromptSet:
    prompt: str
    negative_prompt: str
    scene_kind: SceneKind
    constraints: tuple[str, ...] = field(default_factory=tuple)
    scenery_lock: str = ""


def _face_constraints() -> str:
    # Positive, specific instructions. Never forbid eyes by name.
    return (
        "If a face is visible, keep a soft, readable Impressionist portrait likeness. "
        "Suggest eyes, brows, nose and lips with broken color; do not paint pores, lip cracks, or sharpened contour makeup. "
        "No beauty-filter finish and no privacy-style blur."
    )


def _distant_figure_constraints() -> str:
    return (
        "Distant or back-facing figures are dissolving color masses in blue, white or yellow, "
        "edges melting into the air, clothing as large color patches, "
        "not a modern illustration character cut out and pasted into the landscape."
    )


def _landscape_atmosphere() -> str:
    return (
        "Landscape atmosphere of pink-violet and gold mist, optical mixing, soft edges, low contrast. "
        "Canopies and reflections read as color masses, not botanical plates. "
        "Distant mountains fade into atmospheric mist, hazy background, soft boundaries merging with the sky."
    )


def _sky_constraints() -> str:
    return (
        "Sky: large loose sweeping brushstrokes and wet-on-wet, a flowing breathing sky; "
        "warm light may tint the undersides of clouds. "
        "Do not cover the whole sky with thick short impasto."
    )


def _flower_fabric_constraints() -> str:
    return (
        "At a distance the surface must read as oil paint: impasto, palette knife, canvas tooth, varied stroke width. "
        "Flower fields are simplified abstract color patches with only a few bright dabs; "
        "clothing folds are large color patches, not refined-smooth strokes."
    )


def _patch_style_fixes(style_issues: list[str]) -> str:
    lines = ["Rebuild with the approved patch approach, not by merely thickening texture:"]
    mapping = {
        "sky": (
            "Sky must use sweeping brushstrokes, large loose brush marks, and wet-on-wet; "
            "no fish-scale, washboard, or uniform short impasto texture-map."
        ),
        "color": (
            "Add environmental color and optical mixing: warm light on cloud undersides, "
            "water reflecting clouds, flowers and mountain violet; no isolated dead local color."
        ),
        "mountains": (
            "Distant mountains fading into atmospheric mist, soft boundaries, merge with the sky; "
            "no hard game-matte silhouettes."
        ),
        "flowers": (
            "Simplified fields of wildflowers as abstract color patches; "
            "do not draw individual flowers or stamp them."
        ),
        "figure": (
            "Figures in the landscape remain dissolving masses with soft melting edges, "
            "not fashion-illustration cutouts."
        ),
    }
    used = False
    for key, text in mapping.items():
        if key in style_issues:
            lines.append(text)
            used = True
    if not used:
        lines.append(
            "Re-apply sweeping wet-on-wet skies, environmental color, atmospheric mountains, "
            "abstract flower masses, and dissolving figures."
        )
    return " ".join(lines)


def scenery_lock_instructions(scenery_issues: list[str]) -> str:
    """Extra constraints used when scenery has drifted. Always a whole-image regen."""
    named = ", ".join(scenery_issues) if scenery_issues else "景色走样"
    return (
        "Style may already be improved; now lock lost or shifted scenery back to the source photograph. "
        f"Concrete issues to correct: {named}. "
        "Keep the improved sky, ambient environmental color, optical mixing, and soft misted mountains. "
        "Restore water, shoreline, mountains, sky bands, flower or grass belts to their original places. "
        "Keep the figure's position, facing, and pose consistent with the source. "
        "Do not invent extra trees or swap the background. "
        "Do not rewrite the scene to look more like a famous Monet location. "
        "Because there is no inpaint step, regenerate the whole image with both style and composition constraints applied together."
    )


def build_prompts(
    scene: SceneAnalysis,
    *,
    style_issues: list[str] | None = None,
    scenery_issues: list[str] | None = None,
    composition_lock: bool = True,
) -> PromptSet:
    style_issues = list(style_issues or [])
    scenery_issues = list(scenery_issues or [])

    parts: list[str] = [CORE_TECHNIQUE, " ".join(FOUR_HARD_RULES)]
    constraints: list[str] = ["monet_impressionism", "optical_mixing", "composition_lock" if composition_lock else ""]
    constraints = [c for c in constraints if c]

    if composition_lock:
        parts.append(COMPOSITION_LOCK)

    parts.append(_sky_constraints())
    parts.append(_landscape_atmosphere() if scene.kind != SceneKind.PORTRAIT or scene.has_sky else "")
    parts.append(_flower_fabric_constraints())

    if scene.kind == SceneKind.PORTRAIT or scene.has_face:
        parts.append(_face_constraints())
        constraints.append("impressionist_portrait")
    if scene.kind == SceneKind.FIGURE_IN_LANDSCAPE or (scene.has_figure and not scene.has_face):
        parts.append(_distant_figure_constraints())
        constraints.append("dissolving_figure")
    if scene.has_water:
        parts.append(
            "A body of water present in the source must remain in the same band of the picture, "
            "reflecting sky, nearby flowers, and distant violet mountains."
        )
        constraints.append("water_present")
    if scene.has_flowers:
        constraints.append("abstract_flower_masses")
    if scene.has_mountains:
        constraints.append("atmospheric_mountains")

    lock_text = ""
    if style_issues:
        parts.append(_patch_style_fixes(style_issues))
        constraints.append("style_patch")
    if scenery_issues:
        lock_text = scenery_lock_instructions(scenery_issues)
        parts.append(lock_text)
        constraints.append("scenery_lock_patch")

    parts.append(
        "The result must read as an oil painting from a distance, "
        "not a photograph with a filter and not a digital texture collage."
    )

    prompt = " ".join(p for p in parts if p).strip()
    negative = NEGATIVE_CORE
    _assert_no_banned(prompt, negative)
    return PromptSet(
        prompt=prompt,
        negative_prompt=negative,
        scene_kind=scene.kind,
        constraints=tuple(constraints),
        scenery_lock=lock_text,
    )


def _assert_no_banned(prompt: str, negative: str) -> None:
    blob = (prompt + "\n" + negative).lower()
    for phrase in BANNED_PHRASES:
        if phrase.lower() in blob:
            raise ValueError(f"banned phrase leaked into prompts: {phrase}")


def contains_banned_phrase(text: str) -> list[str]:
    lowered = text.lower()
    return [p for p in BANNED_PHRASES if p.lower() in lowered]
