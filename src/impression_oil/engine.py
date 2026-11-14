"""Generation engine interface.

0.0.1 ships a stub that refuses to invent a fake oil painting when no
local model is installed. A later img2img backend (for example diffusers
on an NVIDIA GPU) can be dropped in without rewriting the UI: put weights
in models/ and provide a module with create_engine(models_dir).
"""

from __future__ import annotations

import importlib
import os
from abc import ABC, abstractmethod
from pathlib import Path

from impression_oil.paths import models_dir as default_models_dir


ENGINE_NOT_READY_MESSAGE = (
    "0.0.1 尚未安装本机模型。现在可以打开照片、预览界面，但还不能出图。"
    "本机模型需另行一次安装，安装后即可完全离线使用。本次不会开始下载。"
)


class GenerationError(Exception):
    """Raised when a generate() call cannot produce an image."""

    def __init__(self, message: str, *, status_text: str | None = None) -> None:
        super().__init__(message)
        self.status_text = status_text or message


class EngineNotReady(GenerationError):
    """No local model is installed. The UI must not start a download."""

    def __init__(self, message: str = ENGINE_NOT_READY_MESSAGE) -> None:
        super().__init__(message, status_text=message)


class ImageEngine(ABC):
    """Contract used by the pipeline. UI code should not call backends directly."""

    @abstractmethod
    def is_available(self) -> bool:
        """True when a local model is present and this engine can run offline."""

    def unavailable_reason(self) -> str:
        return ENGINE_NOT_READY_MESSAGE

    def prepare(self) -> None:
        """Load weights on the calling thread. Default is a no-op."""

    @abstractmethod
    def generate(
        self,
        source_path: Path,
        prompt: str,
        negative_prompt: str,
        composition_lock: bool = True,
    ) -> Path:
        """Return the path of a newly written image. Never call an external API."""


class StubEngine(ImageEngine):
    """Placeholder used in 0.0.1. Does not pretend to paint a Monet."""

    def __init__(self, models_directory: Path | None = None) -> None:
        self.models_directory = Path(models_directory) if models_directory else default_models_dir()

    def is_available(self) -> bool:
        return False

    def generate(
        self,
        source_path: Path,
        prompt: str,
        negative_prompt: str,
        composition_lock: bool = True,
    ) -> Path:
        raise EngineNotReady(self.unavailable_reason())


def _try_load_local_backend(directory: Path) -> ImageEngine | None:
    """Import an optional local backend without requiring it in 0.0.1.

    A backend module must expose create_engine(models_dir) -> ImageEngine | None.
    Set IMPRESSION_OIL_BACKEND to override the module name.
    """
    module_name = os.environ.get("IMPRESSION_OIL_BACKEND", "impression_oil.backends.local")
    try:
        module = importlib.import_module(module_name)
    except ImportError:
        return None
    factory = getattr(module, "create_engine", None)
    if factory is None:
        return None
    engine = factory(directory)
    if engine is not None and engine.is_available():
        return engine
    return None


def get_engine(models_directory: Path | None = None) -> ImageEngine:
    directory = Path(models_directory) if models_directory is not None else default_models_dir()
    directory.mkdir(parents=True, exist_ok=True)
    backend = _try_load_local_backend(directory)
    if backend is not None:
        return backend
    return StubEngine(models_directory=directory)
