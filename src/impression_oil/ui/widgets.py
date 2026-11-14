"""Workbench widgets: drop zone, image cards, review panel, footer."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPaintEvent, QPen, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from impression_oil.review import ChecklistItem, ReviewResult
from impression_oil.styles import DROP_RADIUS, IMAGE_RADIUS, TOKENS

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def _font(size: int, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    font = QFont()
    font.setPixelSize(size)
    font.setWeight(weight)
    return font


def _has_local_image(event) -> bool:  # noqa: ANN001
    mime = event.mimeData()
    return bool(mime and _local_image_paths(event))


def _local_image_paths(event) -> list[str]:  # noqa: ANN001
    mime = event.mimeData()
    if mime is None or not mime.hasUrls():
        return []
    paths: list[str] = []
    for url in mime.urls():
        if url.isLocalFile():
            path = Path(url.toLocalFile())
            if path.suffix.lower() in IMAGE_SUFFIXES:
                paths.append(str(path))
    return paths


class Hairline(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Hairline")
        self.setFixedHeight(1)
        self.setFrameShape(QFrame.Shape.NoFrame)


class Banner(QWidget):
    """Non-blocking in-app message. Never used to start a download."""

    dismissed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setVisible(False)
        self._label = QLabel(self)
        self._label.setObjectName("Banner")
        self._label.setWordWrap(True)
        self._close = QPushButton("关闭", self)
        self._close.setObjectName("GhostButton")
        self._close.setFixedHeight(30)
        self._close.setCursor(Qt.CursorShape.PointingHandCursor)
        self._close.clicked.connect(self._dismiss)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(28, 8, 28, 0)
        layout.setSpacing(12)
        layout.addWidget(self._label, 1)
        layout.addWidget(self._close, 0, Qt.AlignmentFlag.AlignTop)

    def show_message(self, text: str) -> None:
        self._label.setText(text)
        self.setVisible(True)

    def _dismiss(self) -> None:
        self.setVisible(False)
        self.dismissed.emit()


class DropZone(QWidget):
    open_clicked = Signal()
    files_dropped = Signal(list)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setMinimumSize(280, 420)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._hover = False

        self._title = QLabel("将照片拖到这里", self)
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title.setFont(_font(18, QFont.Weight.DemiBold))
        self._subtitle = QLabel("或从电脑选择本地文件", self)
        self._subtitle.setObjectName("MutedLabel")
        self._subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._button = QPushButton("打开本地照片", self)
        self._button.setObjectName("DropCta")
        self._button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._button.clicked.connect(self.open_clicked.emit)
        self._hint = QLabel("支持 JPG、PNG，只在本机处理", self)
        self._hint.setObjectName("FaintLabel")
        self._hint.setAlignment(Qt.AlignmentFlag.AlignCenter)

        inner = QVBoxLayout()
        inner.setSpacing(10)
        inner.addStretch(1)
        inner.addSpacing(72)
        inner.addWidget(self._title)
        inner.addWidget(self._subtitle)
        inner.addSpacing(8)
        inner.addWidget(self._button, 0, Qt.AlignmentFlag.AlignHCenter)
        inner.addSpacing(6)
        inner.addWidget(self._hint)
        inner.addStretch(1)
        self.setLayout(inner)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: ARG002
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(8, 8, -8, -8)
        path = QPainterPath()
        path.addRoundedRect(rect, DROP_RADIUS, DROP_RADIUS)
        painter.fillPath(path, QColor(TOKENS["card"]))
        pen = QPen(QColor(TOKENS["accent"] if self._hover else TOKENS["dash"]))
        pen.setWidthF(1.2)
        pen.setStyle(Qt.PenStyle.DashLine)
        pen.setDashPattern([5, 4])
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)
        self._draw_icon(painter, rect)

    def _draw_icon(self, painter: QPainter, rect: QRectF) -> None:
        cx = rect.center().x()
        top = rect.top() + rect.height() * 0.28
        size = 52
        box = QRectF(cx - size / 2, top, size, size * 0.78)
        painter.setPen(QPen(QColor(TOKENS["muted"]), 1.7))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(box, 8, 8)
        painter.drawEllipse(QRectF(box.left() + 12, box.top() + 8, 10, 10))
        mountain = QPainterPath()
        mountain.moveTo(box.left() + 6, box.bottom() - 8)
        mountain.lineTo(box.left() + 20, box.top() + 18)
        mountain.lineTo(box.left() + 30, box.top() + 28)
        mountain.lineTo(box.left() + 42, box.top() + 16)
        mountain.lineTo(box.right() - 6, box.bottom() - 8)
        painter.drawPath(mountain)

    def enterEvent(self, event) -> None:  # noqa: ANN001
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: ANN001
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def dragEnterEvent(self, event) -> None:  # noqa: ANN001
        if _has_local_image(event):
            event.acceptProposedAction()
            self._hover = True
            self.update()
        else:
            event.ignore()

    def dragLeaveEvent(self, event) -> None:  # noqa: ANN001
        self._hover = False
        self.update()
        super().dragLeaveEvent(event)

    def dropEvent(self, event) -> None:  # noqa: ANN001
        self._hover = False
        self.update()
        paths = _local_image_paths(event)
        if paths:
            event.acceptProposedAction()
            self.files_dropped.emit(paths)
        else:
            event.ignore()


class ImageCard(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._pixmap = QPixmap()
        self.setMinimumSize(240, 360)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_pixmap(self, pixmap: QPixmap) -> None:
        self._pixmap = pixmap
        self.update()

    def clear(self) -> None:
        self._pixmap = QPixmap()
        self.update()

    def has_image(self) -> bool:
        return not self._pixmap.isNull()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: ARG002
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        rect = QRectF(self.rect()).adjusted(10, 6, -10, -14)
        if rect.width() <= 4 or rect.height() <= 4:
            return
        shadow = QPainterPath()
        shadow.addRoundedRect(rect.adjusted(0, 4, 0, 6), IMAGE_RADIUS, IMAGE_RADIUS)
        painter.fillPath(shadow, QColor(0, 0, 0, 28))
        path = QPainterPath()
        path.addRoundedRect(rect, IMAGE_RADIUS, IMAGE_RADIUS)
        painter.fillPath(path, QColor(TOKENS["card"]))
        if self._pixmap.isNull():
            return
        painter.setClipPath(path)
        pix = self._pixmap
        scale = min(rect.width() / max(1, pix.width()), rect.height() / max(1, pix.height()))
        dw, dh = pix.width() * scale, pix.height() * scale
        target = QRectF(rect.center().x() - dw / 2, rect.center().y() - dh / 2, dw, dh)
        painter.drawPixmap(target, pix, QRectF(pix.rect()))


class PlaceholderPanel(QWidget):
    def __init__(self, text: str = "生成后显示在这里", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._text = text
        self.setMinimumSize(240, 360)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: ARG002
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(10, 6, -10, -14)
        path = QPainterPath()
        path.addRoundedRect(rect, IMAGE_RADIUS, IMAGE_RADIUS)
        painter.fillPath(path, QColor(TOKENS["placeholder"]))
        painter.setPen(QColor(TOKENS["faint"]))
        painter.setFont(_font(13))
        painter.drawText(rect, int(Qt.AlignmentFlag.AlignCenter), self._text)


class FeedbackBar(QWidget):
    accepted = Signal()
    rejected = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setVisible(False)
        self._yes = QPushButton("满意", self)
        self._no = QPushButton("不满意", self)
        self._yes.setCursor(Qt.CursorShape.PointingHandCursor)
        self._no.setCursor(Qt.CursorShape.PointingHandCursor)
        self._yes.clicked.connect(self._on_yes)
        self._no.clicked.connect(self._on_no)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 10, 8)
        layout.setSpacing(12)
        layout.addStretch(1)
        layout.addWidget(self._yes)
        layout.addWidget(self._no)
        layout.addStretch(1)
        self.set_selection(None)

    def _on_yes(self) -> None:
        self.set_selection("yes")
        self.accepted.emit()

    def _on_no(self) -> None:
        self.set_selection("no")
        self.rejected.emit()

    def set_selection(self, which: str | None) -> None:
        self._yes.setObjectName("AccentButton" if which != "no" else "GhostButton")
        self._no.setObjectName("GhostButton")
        if which == "no":
            self._no.setStyleSheet(
                f"QPushButton {{ border: 1.6px solid {TOKENS['accent']}; "
                f"color: {TOKENS['accent']}; background: {TOKENS['card']}; }}"
            )
            self._yes.setStyleSheet("")
        elif which == "yes":
            self._yes.setStyleSheet("")
            self._no.setStyleSheet("")
        else:
            self._yes.setObjectName("AccentButton")
            self._no.setObjectName("GhostButton")
            self._yes.setStyleSheet("")
            self._no.setStyleSheet("")
        self._refresh(self._yes)
        self._refresh(self._no)

    def _refresh(self, widget: QWidget) -> None:
        style = widget.style()
        style.unpolish(widget)
        style.polish(widget)
        widget.update()

    def reset(self) -> None:
        self.set_selection(None)
        self.setVisible(False)


class CheckRow(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._item: ChecklistItem | None = None
        self.setMinimumHeight(36)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_item(self, item: ChecklistItem) -> None:
        self._item = item
        self.setToolTip(item.detail or "")
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: ARG002
        if self._item is None:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(0, 2, 0, -2)
        path = QPainterPath()
        path.addRoundedRect(rect, 8, 8)
        bg = QColor(TOKENS["pass_bg"] if self._item.passed else TOKENS["fail_bg"])
        painter.fillPath(path, bg)

        cx = rect.left() + 18
        cy = rect.center().y()
        if self._item.passed:
            painter.setPen(QPen(QColor(TOKENS["pass_icon"]), 2.0))
            check = QPainterPath()
            check.moveTo(cx - 5, cy)
            check.lineTo(cx - 1, cy + 5)
            check.lineTo(cx + 7, cy - 5)
            painter.drawPath(check)
        else:
            painter.setPen(QPen(QColor(TOKENS["accent"]), 2.0))
            painter.drawLine(int(cx - 5), int(cy - 5), int(cx + 5), int(cy + 5))
            painter.drawLine(int(cx + 5), int(cy - 5), int(cx - 5), int(cy + 5))

        text_rect = rect.adjusted(34, 0, -8, 0)
        painter.setPen(QColor(TOKENS["text"]))
        painter.setFont(_font(12))
        if not self._item.passed and self._item.key == "scenery" and self._item.detail:
            label = self._item.detail
        else:
            label = self._item.label
        painter.drawText(text_rect, int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), label)


class ReviewPanel(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ReviewPane")
        self._title = QLabel("已按补丁自查，正在重画", self)
        self._title.setFont(_font(14, QFont.Weight.DemiBold))
        self._rows = [CheckRow(self) for _ in range(6)]
        grid = QGridLayout()
        grid.setContentsMargins(0, 4, 0, 4)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(8)
        # Two columns: left sky / mountains / figure; right color / flowers / scenery.
        # CHECKLIST_SPEC is sky, color, mountains, flowers, figure, scenery
        # Mockup left: sky, mountains, figure (0, 2, 4); right: color, flowers, scenery (1, 3, 5)
        left = [0, 2, 4]
        right = [1, 3, 5]
        for row, idx in enumerate(left):
            grid.addWidget(self._rows[idx], row, 0)
        for row, idx in enumerate(right):
            grid.addWidget(self._rows[idx], row, 1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 10, 28, 8)
        layout.setSpacing(8)
        layout.addWidget(self._title)
        layout.addLayout(grid)
        self.setVisible(False)

    def show_review(self, review: ReviewResult) -> None:
        self._title.setText(review.title)
        for row, item in zip(self._rows, review.items):
            row.set_item(item)
        self.setVisible(True)

    def clear(self) -> None:
        self.setVisible(False)


class Footer(QWidget):
    toggle_requested = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("FooterBar")
        self._expanded = False

        self._toggle = QPushButton("▸  这次改了什么", self)
        self._toggle.setFlat(True)
        self._toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle.setStyleSheet(
            f"QPushButton {{ border: none; color: {TOKENS['muted']}; font-size: 13px; text-align: left; }}"
        )
        self._toggle.clicked.connect(self._on_toggle)

        self.review_panel = ReviewPanel(self)

        self._status = QLabel("", self)
        self._status.setObjectName("FooterHint")
        self._status.setWordWrap(False)
        self._status.setVisible(False)

        self._offline = QLabel("本机运行  ·  无需联网", self)
        self._offline.setObjectName("OfflineHint")
        self._offline.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self._status_strip = QWidget(self)
        self._status_strip.setObjectName("StatusStrip")
        strip = QHBoxLayout(self._status_strip)
        strip.setContentsMargins(28, 8, 28, 8)
        strip.addWidget(self._status, 1)
        strip.addWidget(self._offline, 0)
        # When collapsed, the status strip shares the same row as the toggle.
        self._collapsed_row = QWidget(self)
        collapsed = QHBoxLayout(self._collapsed_row)
        collapsed.setContentsMargins(20, 10, 28, 10)
        collapsed.addWidget(self._toggle, 0)
        collapsed.addStretch(1)
        self._offline_collapsed = QLabel("本机运行  ·  无需联网", self)
        self._offline_collapsed.setObjectName("OfflineHint")
        collapsed.addWidget(self._offline_collapsed, 0)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(Hairline(self))
        layout.addWidget(self._collapsed_row)
        layout.addWidget(self.review_panel)
        layout.addWidget(self._status_strip)
        self._status_strip.setVisible(False)

    def _on_toggle(self) -> None:
        self.set_expanded(not self._expanded)
        self.toggle_requested.emit(self._expanded)

    def set_expanded(self, expanded: bool) -> None:
        self._expanded = expanded
        prefix = "▾" if expanded else "▸"
        self._toggle.setText(f"{prefix}  这次改了什么")
        # Review panel visibility is controlled separately; the chevron only
        # reveals or hides it when a review already exists.

    @property
    def expanded(self) -> bool:
        return self._expanded

    def show_review(self, review: ReviewResult, *, busy: bool = False) -> None:
        self.set_expanded(True)
        self._collapsed_row.setVisible(False)
        self.review_panel.show_review(review)
        self._status.setText(review.status_line)
        self._status.setVisible(True)
        self._status_strip.setVisible(True)
        if busy:
            # Keep the status line even while redrawing.
            pass

    def show_idle_status(self, text: str) -> None:
        # Used after 满意: keep footer collapsed, no review chrome.
        self._status.setText(text)

    def collapse(self) -> None:
        self.set_expanded(False)
        self._collapsed_row.setVisible(True)
        self.review_panel.clear()
        self._status_strip.setVisible(False)

    def reveal_or_hide_review(self, review: ReviewResult | None) -> None:
        if not self._expanded:
            self.review_panel.clear()
            self._status_strip.setVisible(False)
            self._collapsed_row.setVisible(True)
            return
        if review is None:
            # Empty explanation when the user opens the pane too early.
            placeholder = ReviewResult(
                items=tuple(),
                style_issues=tuple(),
                scenery_issues=tuple(),
                status_line="生成之后，这里会列出画法自查和景色核对的结果。",
            )
            self._collapsed_row.setVisible(True)
            self.review_panel.setVisible(False)
            self._status.setText(placeholder.status_line)
            self._status.setVisible(True)
            self._status_strip.setVisible(True)
            return
        self.show_review(review)
