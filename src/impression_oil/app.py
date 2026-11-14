"""Application entry point."""

from __future__ import annotations

import os
import sys

from impression_oil.logging_setup import setup_logging
from impression_oil.version import APP_NAME, WINDOW_TITLE, __version__


def _prepare_qt_runtime() -> None:
    """Keep the window off the GPU. Qt + CUDA on the same machine
    have been aborting Qt6Core.dll when the UI uses hardware drawing.
    """
    # Qt 6.8 widgets default to a GPU (D3D11) paint engine. That has been
    # aborting Qt6Core.dll on this machine once CUDA in the child process
    # finishes and the window tries to show the result.
    os.environ["QT_WIDGETS_RHI"] = "0"
    os.environ["QT_OPENGL"] = "software"
    os.environ["QSG_RHI_BACKEND"] = "software"
    os.environ["QT_QUICK_BACKEND"] = "software"
    os.environ["QT_WIDGETS_RHI_BACKEND"] = "software"


def main(argv: list[str] | None = None) -> int:
    _prepare_qt_runtime()
    setup_logging()
    try:
        import faulthandler
        from impression_oil.logging_setup import log_file_path

        with log_file_path().open("a", encoding="utf-8") as fh:
            faulthandler.enable(file=fh, all_threads=True)
    except OSError:
        pass
    args = list(sys.argv if argv is None else argv)

    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    # High-DPI before the application is constructed when the API allows it.
    if hasattr(Qt, "HighDpiScaleFactorRoundingPolicy"):
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )
    if hasattr(Qt.ApplicationAttribute, "AA_UseSoftwareOpenGL"):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseSoftwareOpenGL, True)

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
