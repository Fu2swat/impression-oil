"""Custom title bar matching the approved mockups: logo dots + title + caption buttons."""

from __future__ import annotations

from PySide6.QtCore import QPoint, QSize, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPaintEvent
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSizePolicy, QSpacerItem, QWidget

from impression_oil.styles import TOKENS
from impression_oil.version import APP_NAME


class LogoMark(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(36, 16)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: ARG002
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        colors = [TOKENS["accent"], TOKENS["logo_teal"], TOKENS["logo_gold"]]
        x = 2
        for color in colors:
            painter.setBrush(QColor(color))
            painter.drawEllipse(x, 3, 10, 10)
            x += 11


class TitleBar(QWidget):
    close_requested = Signal()
    minimize_requested = Signal()
    maximize_requested = Signal()
    move_requested = Signal(QPoint)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("TitleBar")
        self.setFixedHeight(50)
        self._press_pos: QPoint | None = None

        logo = LogoMark(self)
        title = QLabel(APP_NAME, self)
        title.setObjectName("TitleText")

        self.min_btn = self._caption("—", "CaptionButton")
        self.max_btn = self._caption("□", "CaptionButton")
        self.close_btn = self._caption("×", "CaptionClose")
        self.close_btn.setObjectName("CaptionClose")
        self.min_btn.clicked.connect(self.minimize_requested.emit)
        self.max_btn.clicked.connect(self.maximize_requested.emit)
        self.close_btn.clicked.connect(self.close_requested.emit)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 0, 4, 0)
        layout.setSpacing(8)
        layout.addWidget(logo, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(title, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addItem(QSpacerItem(10, 10, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))
        layout.addWidget(self.min_btn, 0, Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self.max_btn, 0, Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self.close_btn, 0, Qt.AlignmentFlag.AlignTop)

    def _caption(self, text: str, name: str) -> QPushButton:
        btn = QPushButton(text, self)
        btn.setObjectName(name)
        btn.setCursor(Qt.CursorShape.ArrowCursor)
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn.setFixedSize(QSize(46, 36))
        btn.setFlat(True)
        return btn

    def set_maximized(self, maximized: bool) -> None:
        self.max_btn.setText("❐" if maximized else "□")

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            child = self.childAt(event.position().toPoint())
            if isinstance(child, QPushButton):
                super().mousePressEvent(event)
                return
            self._press_pos = event.globalPosition().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._press_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            now = event.globalPosition().toPoint()
            self.move_requested.emit(now - self._press_pos)
            self._press_pos = now
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._press_pos = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.maximize_requested.emit()
        super().mouseDoubleClickEvent(event)
