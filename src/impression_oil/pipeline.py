"""Application pipeline and state machine.

The GUI calls this module; it must not re-implement prompts in widgets.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from impression_oil.engine import EngineNotReady, GenerationError, ImageEngine, get_engine
from impression_oil.logging_setup import get_logger
from impression_oil.paths import outputs_dir
from impression_oil.review import ReviewResult, review_paths
from impression_oil.scene import FileOpenError, SceneAnalysis, analyze_scene, open_rgb, validate_image_path
from impression_oil.skill_prompts import PromptSet, build_prompts
from impression_oil.version import __version__

LOGGER = get_logger("pipeline")

MAX_AUTO_PATCH_PASSES = 1


class AppState(str, Enum):
    EMPTY = "empty"
    SOURCE_LOADED = "source_loaded"
    GENERATING = "generating"
    RESULT_READY = "result_ready"
    REGENERATING = "regenerating"
    ACCEPTED = "accepted"


class PipelineError(Exception):
    def __init__(self, status_text: str) -> None:
        super().__init__(status_text)
        self.status_text = status_text


@dataclass
class GenerateOutcome:
    path: Path | None
    review: ReviewResult | None
    prompts: PromptSet | None
    auto_patched: bool = False


class Pipeline:
    """empty -> source loaded -> generate (blocked without model);
    unsatisfied triggers rereview + regenerate.
    """

    def __init__(self, engine: ImageEngine | None = None) -> None:
        self.engine = engine if engine is not None else get_engine()
        self.state = AppState.EMPTY
        self.source_path: Path | None = None
        self.result_path: Path | None = None
        self.scene: SceneAnalysis | None = None
        self.last_review: ReviewResult | None = None
        self.last_prompts: PromptSet | None = None
        self.accepted = False
        self.saved_path: Path | None = None
        self.generation_count = 0

    # --- queries used by the UI ---

    def engine_is_ready(self) -> bool:
        return self.engine.is_available()

    def engine_message(self) -> str:
        return self.engine.unavailable_reason()

    def prepare_engine(self) -> None:
        """Load local model weights on the current thread, if the engine supports it."""
        prepare = getattr(self.engine, "prepare", None)
        if callable(prepare):
            LOGGER.info("preparing local engine")
            prepare()
            LOGGER.info("local engine ready")

    def can_generate(self) -> bool:
        return self.source_path is not None and self.state != AppState.GENERATING and self.state != AppState.REGENERATING

    def can_regenerate(self) -> bool:
        return self.can_generate()

    def can_save(self) -> bool:
        return self.result_path is not None and Path(self.result_path).is_file()

    def can_accept_or_reject(self) -> bool:
        return self.result_path is not None and self.state in {AppState.RESULT_READY, AppState.ACCEPTED}

    def default_save_name(self) -> str:
        stem = Path(self.source_path).stem if self.source_path else "照片"
        return f"{stem}-印象油画.jpg"

    # --- mutations ---

    def reset(self) -> None:
        self.state = AppState.EMPTY
        self.source_path = None
        self.result_path = None
        self.scene = None
        self.last_review = None
        self.last_prompts = None
        self.accepted = False
        self.saved_path = None
        self.generation_count = 0

    def load_source(self, path: Path) -> SceneAnalysis:
        path = validate_image_path(Path(path))
        # Fully decode once so a truncated file fails here, with a Chinese status.
        open_rgb(path)
        self.scene = analyze_scene(path)
        self.source_path = path
        self.result_path = None
        self.last_review = None
        self.last_prompts = None
        self.accepted = False
        self.saved_path = None
        self.generation_count = 0
        self.state = AppState.SOURCE_LOADED
        LOGGER.info("source loaded: %s (%s)", path, self.scene.kind.value)
        return self.scene

    def generate(self, *, auto_patch: bool = True) -> Path:
        """Run a generation. Raises EngineNotReady when no local model is present."""
        if self.source_path is None or self.scene is None:
            raise PipelineError("请先打开一张本地照片。")
        if not self.engine.is_available():
            self.last_review = review_paths(self.source_path, None, engine_ready=False)
            LOGGER.info("generate blocked: engine not ready")
            raise EngineNotReady(self.engine.unavailable_reason())

        self.state = AppState.GENERATING
        try:
            outcome = self._run_generation(
                style_issues=[],
                scenery_issues=[],
                auto_patch=auto_patch,
            )
        except Exception:
            self.state = AppState.SOURCE_LOADED if self.result_path is None else AppState.RESULT_READY
            raise
        assert outcome.path is not None
        self.result_path = outcome.path
        self.last_review = outcome.review
        self.last_prompts = outcome.prompts
        self.accepted = False
        self.state = AppState.RESULT_READY
        return outcome.path

    def reject(self) -> tuple[ReviewResult, Path]:
        """不满意: self-check against the current result, then regenerate with patches."""
        if self.source_path is None or self.scene is None:
            raise PipelineError("请先打开一张本地照片。")
        if self.result_path is None:
            raise PipelineError("还没有可审阅的油画结果。")

        review = review_paths(self.source_path, self.result_path, engine_ready=self.engine.is_available())
        self.last_review = review
        LOGGER.info(
            "unsatisfied review: style=%s scenery=%s",
            list(review.style_issues),
            list(review.scenery_issues),
        )

        if not self.engine.is_available():
            self.state = AppState.RESULT_READY
            raise EngineNotReady(self.engine.unavailable_reason())

        self.state = AppState.REGENERATING
        try:
            outcome = self._run_generation(
                style_issues=list(review.style_issues),
                scenery_issues=list(review.scenery_issues),
                auto_patch=False,
            )
        except Exception:
            self.state = AppState.RESULT_READY
            raise
        assert outcome.path is not None
        self.result_path = outcome.path
        # Review the new result as well, so the next panel is current.
        self.last_review = outcome.review or review
        self.last_prompts = outcome.prompts
        self.accepted = False
        self.state = AppState.RESULT_READY
        return self.last_review, outcome.path

    def accept(self) -> None:
        if self.result_path is None:
            raise PipelineError("还没有可保存的油画结果。")
        self.accepted = True
        self.state = AppState.ACCEPTED
        LOGGER.info("result accepted: %s", self.result_path)

    def mark_saved(self, path: Path) -> None:
        self.saved_path = Path(path)
        LOGGER.info("saved: %s", self.saved_path)

    def save_result(self, destination: Path) -> Path:
        if not self.can_save() or self.result_path is None:
            raise PipelineError("还没有可保存的油画结果。")
        destination = Path(destination)
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(self.result_path, destination)
        except PermissionError as exc:
            raise PipelineError("没有权限保存到该位置。") from exc
        except OSError as exc:
            raise PipelineError("保存失败，请换一个位置再试。") from exc
        self.mark_saved(destination)
        return destination

    # --- internals ---

    def _run_generation(
        self,
        *,
        style_issues: list[str],
        scenery_issues: list[str],
        auto_patch: bool,
    ) -> GenerateOutcome:
        assert self.source_path is not None and self.scene is not None
        prompts = build_prompts(
            self.scene,
            style_issues=style_issues,
            scenery_issues=scenery_issues,
            composition_lock=True,
        )
        path = self._call_engine(prompts)
        self.generation_count += 1
        review = review_paths(self.source_path, path, engine_ready=True)
        auto_patched = False
        if auto_patch and not review.all_passed and MAX_AUTO_PATCH_PASSES > 0:
            LOGGER.info("auto patch pass after self-check: %s %s", review.style_issues, review.scenery_issues)
            patched = build_prompts(
                self.scene,
                style_issues=list(review.style_issues),
                scenery_issues=list(review.scenery_issues),
                composition_lock=True,
            )
            path = self._call_engine(patched)
            self.generation_count += 1
            review = review_paths(self.source_path, path, engine_ready=True)
            prompts = patched
            auto_patched = True
        return GenerateOutcome(path=path, review=review, prompts=prompts, auto_patched=auto_patched)

    def _call_engine(self, prompts: PromptSet) -> Path:
        try:
            path = self.engine.generate(
                self.source_path,  # type: ignore[arg-type]
                prompts.prompt,
                prompts.negative_prompt,
                True,
            )
        except EngineNotReady:
            raise
        except GenerationError:
            raise
        except PermissionError as exc:
            raise PipelineError("没有权限写入生成结果。") from exc
        except OSError as exc:
            raise PipelineError("生成失败，请稍后再试。") from exc
        path = Path(path)
        if not path.is_file():
            raise PipelineError("生成失败，没有得到结果文件。")
        return path

    def preview_prompts(self) -> PromptSet | None:
        if self.scene is None:
            return None
        return build_prompts(self.scene, composition_lock=True)


# Re-export for callers that only import pipeline.
__all__ = [
    "AppState",
    "GenerateOutcome",
    "MAX_AUTO_PATCH_PASSES",
    "Pipeline",
    "PipelineError",
    "FileOpenError",
    "outputs_dir",
    "__version__",
]
