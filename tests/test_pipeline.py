from pathlib import Path
from shutil import copyfile

import pytest

from impression_oil.engine import ENGINE_NOT_READY_MESSAGE, EngineNotReady, StubEngine
from impression_oil.pipeline import AppState, Pipeline, PipelineError
from tests.conftest import write_bands


class FakeEngine:
    def __init__(self, out_dir: Path, factory) -> None:  # noqa: ANN001
        self.out_dir = out_dir
        self.factory = factory
        self.calls: list[dict] = []
        self.available = True

    def is_available(self) -> bool:
        return self.available

    def unavailable_reason(self) -> str:
        return ENGINE_NOT_READY_MESSAGE

    def generate(self, source_path, prompt, negative_prompt, composition_lock=True):  # noqa: ANN001
        self.calls.append(
            {
                "source": Path(source_path),
                "prompt": prompt,
                "negative": negative_prompt,
                "lock": composition_lock,
            }
        )
        path = self.out_dir / f"result-{len(self.calls)}.jpg"
        self.factory(len(self.calls), Path(source_path), prompt, path)
        return path


def test_empty_to_source_to_generate_blocked_without_model(tmp_path: Path) -> None:
    source = write_bands(tmp_path / "photo.png")
    pipeline = Pipeline(engine=StubEngine(models_directory=tmp_path / "models"))
    assert pipeline.state is AppState.EMPTY
    assert pipeline.can_generate() is False
    assert pipeline.can_save() is False

    scene = pipeline.load_source(source)
    assert pipeline.state is AppState.SOURCE_LOADED
    assert pipeline.can_generate() is True
    assert pipeline.can_save() is False
    assert scene is not None

    with pytest.raises(EngineNotReady) as caught:
        pipeline.generate()
    assert "本机模型" in caught.value.status_text or "0.0.1" in caught.value.status_text
    assert pipeline.state is AppState.SOURCE_LOADED
    assert pipeline.result_path is None
    assert pipeline.last_review is not None
    assert pipeline.last_review.engine_ready is False
    assert len(pipeline.last_review.items) == 6


def test_unsatisfied_triggers_rereview_and_regenerate(tmp_path: Path) -> None:
    source = write_bands(tmp_path / "photo.png", figure=(170, 300, 230, 500))
    lost_dir = tmp_path / "outs"
    lost_dir.mkdir()

    def factory(index: int, src: Path, prompt: str, dest: Path) -> None:
        if index == 1:
            # First result drops the lake so the reviewer has something to flag.
            write_bands(
                dest,
                top=(130, 170, 210),
                mid=(200, 190, 80),
                bottom=(210, 200, 70),
                figure=(170, 300, 230, 500),
            )
        else:
            # Later results lock the lake back (still a synthetic stand-in, not a painting).
            write_bands(
                dest,
                top=(125, 175, 220),
                mid=(50, 115, 185),
                bottom=(85, 145, 55),
                figure=(170, 300, 230, 500),
            )

    engine = FakeEngine(lost_dir, factory)
    pipeline = Pipeline(engine=engine)
    pipeline.load_source(source)
    assert pipeline.state is AppState.SOURCE_LOADED

    result = pipeline.generate(auto_patch=False)
    assert result.is_file()
    assert pipeline.state is AppState.RESULT_READY
    assert len(engine.calls) == 1
    assert pipeline.last_review is not None
    assert "湖面丢失" in pipeline.last_review.scenery_issues

    review, new_path = pipeline.reject()
    assert new_path.is_file()
    assert new_path != result
    assert pipeline.state is AppState.RESULT_READY
    assert len(engine.calls) == 2
    second = engine.calls[1]["prompt"]
    assert "湖面丢失" in second
    assert "source photograph" in second.lower() or "lock" in second.lower()
    assert review is pipeline.last_review
    # The regenerate call must also keep composition lock on.
    assert engine.calls[1]["lock"] is True

    pipeline.accept()
    assert pipeline.state is AppState.ACCEPTED
    assert pipeline.accepted is True
    saved = pipeline.save_result(tmp_path / "saved" / "lake-印象油画.jpg")
    assert saved.is_file()
    assert pipeline.saved_path == saved


def test_generate_without_source_raises() -> None:
    pipeline = Pipeline(engine=StubEngine())
    with pytest.raises(PipelineError):
        pipeline.generate()


def test_load_missing_file(tmp_path: Path) -> None:
    from impression_oil.scene import FileOpenError

    pipeline = Pipeline(engine=StubEngine())
    with pytest.raises(FileOpenError) as caught:
        pipeline.load_source(tmp_path / "missing.png")
    assert "找不到" in caught.value.status_text


def test_load_unsupported_format(tmp_path: Path) -> None:
    from impression_oil.scene import FileOpenError

    bogus = tmp_path / "notes.txt"
    bogus.write_text("hello", encoding="utf-8")
    pipeline = Pipeline(engine=StubEngine())
    with pytest.raises(FileOpenError) as caught:
        pipeline.load_source(bogus)
    assert "格式" in caught.value.status_text
