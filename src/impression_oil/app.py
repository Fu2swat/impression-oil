"""Application entry point."""

from __future__ import annotations

import sys

from impression_oil.logging_setup import setup_logging
from impression_oil.version import APP_NAME, WINDOW_TITLE, __version__


def main(argv: list[str] | None = None) -> int:
    setup_logging()
    args = list(sys.argv if argv is None else argv)

    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    # High-DPI before the application is constructed when the API allows it.
    if hasattr(Qt, "HighDpiScaleFactorRoundingPolicy"):
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )

    app = QApplication(args)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setOrganizationName(APP_NAME)
    app.setStyle("Fusion")

    from impression_oil.styles import stylesheet
    from impression_oil.ui.main_window import MainWindow

    app.setStyleSheet(stylesheet())
    window = MainWindow()
    window.setWindowTitle(WINDOW_TITLE)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
