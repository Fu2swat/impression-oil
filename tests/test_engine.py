from pathlib import Path

import pytest

from impression_oil.engine import ENGINE_NOT_READY_MESSAGE, EngineNotReady, StubEngine, get_engine


def test_stub_engine_is_unavailable_and_does_not_paint(tmp_path: Path) -> None:
    engine = StubEngine(models_directory=tmp_path)
    assert engine.is_available() is False
    with pytest.raises(EngineNotReady) as caught:
        engine.generate(tmp_path / "a.jpg", "prompt", "negative", True)
    assert "本次不会开始下载" in caught.value.status_text
    assert "0.0.1" in caught.value.status_text


def test_get_engine_defaults_to_stub(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IMPRESSION_OIL_MODELS", str(tmp_path / "models"))
    monkeypatch.delenv("IMPRESSION_OIL_BACKEND", raising=False)
    engine = get_engine()
    assert isinstance(engine, StubEngine)
    assert engine.is_available() is False
    assert ENGINE_NOT_READY_MESSAGE in engine.unavailable_reason()
