from pathlib import Path

from impression_oil.backends.local import create_engine, models_are_ready
from impression_oil.engine import StubEngine, get_engine


def test_models_are_ready_false_when_empty(tmp_path: Path) -> None:
    assert models_are_ready(tmp_path) is False
    assert create_engine(tmp_path) is None


def test_models_are_ready_true_with_manifest(tmp_path: Path) -> None:
    (tmp_path / "sd15").mkdir()
    (tmp_path / "sd15" / "model_index.json").write_text("{}", encoding="utf-8")
    (tmp_path / "lora").mkdir()
    (tmp_path / "lora" / "monet_style_lora.safetensors").write_bytes(b"x")
    (tmp_path / "manifest.json").write_text(
        '{"required_paths": ["sd15/model_index.json", "lora/monet_style_lora.safetensors"]}',
        encoding="utf-8",
    )
    assert models_are_ready(tmp_path) is True
    # torch / diffusers are not installed in the lightweight test env, so factory returns None.
    engine = create_engine(tmp_path)
    assert engine is None or engine.is_available()


def test_get_engine_stays_stub_without_models(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("IMPRESSION_OIL_MODELS", str(tmp_path / "models"))
    monkeypatch.delenv("IMPRESSION_OIL_BACKEND", raising=False)
    engine = get_engine(tmp_path / "models")
    assert isinstance(engine, StubEngine)
