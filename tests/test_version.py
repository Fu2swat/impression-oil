from pathlib import Path

from impression_oil import APP_NAME, WINDOW_TITLE, __version__
from impression_oil.version import __version__ as version_module_value


ROOT = Path(__file__).resolve().parents[1]


def test_version_is_0_0_1() -> None:
    assert __version__ == "0.0.1"
    assert version_module_value == "0.0.1"
    assert ROOT.joinpath("VERSION").read_text(encoding="utf-8").strip() == "0.0.1"
    text = ROOT.joinpath("pyproject.toml").read_text(encoding="utf-8")
    assert 'version = "0.0.1"' in text
    assert WINDOW_TITLE == "印象派油画生成 0.0.1"
    assert APP_NAME == "印象派油画生成"
