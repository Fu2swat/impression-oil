"""Local directories for logs, outputs and the future model hook."""

from __future__ import annotations

import os
import sys
from pathlib import Path


APP_DIR_NAME = "ImpressionOil"


def project_root() -> Path:
    """Repo / install root when running from source; otherwise the app data dir."""
    # src/impression_oil/paths.py -> src -> project
    here = Path(__file__).resolve()
    candidate = here.parents[2]
    if (candidate / "pyproject.toml").is_file() or (candidate / "run.bat").is_file():
        return candidate
    return app_data_dir()


def app_data_dir() -> Path:
    override = os.environ.get("IMPRESSION_OIL_DATA")
    if override:
        path = Path(override).expanduser()
    elif sys.platform.startswith("win"):
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
        path = base / APP_DIR_NAME
    elif sys.platform == "darwin":
        path = Path.home() / "Library" / "Application Support" / APP_DIR_NAME
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
        path = base / "impression-oil"
    path.mkdir(parents=True, exist_ok=True)
    return path


def models_dir() -> Path:
    """Hook directory for a later one-time local model install.

    Lookup order: IMPRESSION_OIL_MODELS, <project>/models, <app data>/models.
    The directory is created if missing; 0.0.1 never downloads weights into it.
    """
    override = os.environ.get("IMPRESSION_OIL_MODELS")
    if override:
        path = Path(override).expanduser()
    else:
        project_models = project_root() / "models"
        data_models = app_data_dir() / "models"
        # Prefer the project folder when running from source so dropping
        # weights next to the repo is enough; otherwise use app data.
        if _looks_like_source_tree(project_root()):
            path = project_models
        else:
            path = data_models
    path.mkdir(parents=True, exist_ok=True)
    return path


def _looks_like_source_tree(root: Path) -> bool:
    return (root / "pyproject.toml").is_file() or (root / "run.bat").is_file()


def logs_dir() -> Path:
    path = app_data_dir() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def outputs_dir() -> Path:
    path = app_data_dir() / "outputs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def default_pictures_dir() -> Path:
    home = Path.home()
    candidates = [
        home / "Pictures",
        home / "图片",
        Path(os.environ.get("USERPROFILE", "")) / "Pictures",
    ]
    for folder in candidates:
        if folder and folder.is_dir():
            return folder
    return home
