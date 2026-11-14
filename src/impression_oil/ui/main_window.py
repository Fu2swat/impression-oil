"""Main workbench window. Matches the approved mockups; talks to the pipeline only."""

from __future__ import annotations

import threading

from pathlib import Path

from PySide6.QtCore import QObject, QSize, QTimer, Qt, Signal, Slot
from PySide6.QtGui import QGuiApplication, QImage, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from impression_oil.engine import EngineNotReady, GenerationError
from impression_oil.logging_setup import get_logger
from impression_oil.paths import default_pictures_dir
from impression_oil.pipeline import AppState, Pipeline, PipelineError
from impression_oil.scene import FileOpenError
from impression_oil.ui.title_bar import TitleBar
from impression_oil.ui.widgets import (
    Banner,
    DropZone,
    FeedbackBar,
    Footer,
    Hairline,
    ImageCard,
    PlaceholderPanel,
    _has_local_image,
    _local_image_paths,
)
from impression_oil.version import WINDOW_TITLE

LOGGER = get_logger("ui")
PREFERRED_SIZE = QSize(1580, 1040)
RESIZE_MARGIN = 6

OPEN_FILTER = "照片 (*.jpg *.jpeg *.png *.webp)"
SAVE_FILTER = "JPEG (*.jpg *.jpeg);;PNG (*.png)"


class MainWindow(QWidget):
    _job_finished = Signal(object)
    _job_failed = Signal(str)

    def __init__(self, pipeline: Pipeline | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("RootWindow")
        self.setWindowTitle(WINDOW_TITLE)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        # A translucent frameless window plus a large result image has been
        # aborting Qt6Core.dll on this machine. Keep the frame custom, but
        # draw on an opaque background.
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setMinimumSize(1100, 760)
        self.setAcceptDrops(True)

        self.pipeline = pipeline or Pipeline()
        self._work_thread: threading.Thread | None = None
        self._job_on_ok = None
        self._maximized = False
        self._normal_geo = None
        self._resize_edge: str | None = None
        self._busy = False
        self._job_finished.connect(self._on_job_finished, Qt.ConnectionType.QueuedConnection)
        self._job_failed.connect(self._on_job_failed, Qt.ConnectionType.QueuedConnection)

        self._build()
        self._sync_chrome()
        self._fit_to_screen()

    # ----- layout -----

    def _build(self) -> None:
        self._chrome = QWidget(self)
        self._chrome.setObjectName("Canvas")

        self.title_bar = TitleBar(self._chrome)
        self.title_bar.close_requested.connect(self.close)
        self.title_bar.minimize_requested.connect(self.showMinimized)
        self.title_bar.maximize_requested.connect(self.toggle_max_restore)
        self.title_bar.move_requested.connect(self._nudge)

        self.open_btn = self._toolbar_button("打开照片")
        self.regen_btn = self._toolbar_button("再生成")
        self.save_btn = self._toolbar_button("保存")
        self.open_btn.clicked.connect(self.open_photo)
        self.regen_btn.clicked.connect(self._on_generate)
        self.save_btn.clicked.connect(self.save_result)

        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(28, 16, 28, 8)
        toolbar.setSpacing(10)
        toolbar.addWidget(self.open_btn)
        toolbar.addWidget(self.regen_btn)
        toolbar.addStretch(1)
        toolbar.addWidget(self.save_btn)

        self.banner = Banner(self._chrome)

        self.drop_zone = DropZone(self._chrome)
        self.drop_zone.open_clicked.connect(self.open_photo)
        self.drop_zone.files_dropped.connect(self._on_dropped)
        self.source_card = ImageCard(self._chrome)
        self.left_stack = QStackedWidget(self._chrome)
        self.left_stack.addWidget(self.drop_zone)
        self.left_stack.addWidget(self.source_card)

        self.placeholder = PlaceholderPanel("生成后显示在这里", self._chrome)
        self.result_card = ImageCard(self._chrome)
        self.right_stack = QStackedWidget(self._chrome)
        self.right_stack.addWidget(self.placeholder)
        self.right_stack.addWidget(self.result_card)

        self.left_caption = QLabel("原照", self._chrome)
        self.left_caption.setObjectName("PanelCaption")
        self.left_caption.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.right_caption = QLabel("油画结果", self._chrome)
        self.right_caption.setObjectName("PanelCaption")
        self.right_caption.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        left_col = QVBoxLayout()
        left_col.setSpacing(8)
        left_col.addWidget(self.left_caption)
        left_col.addWidget(self.left_stack, 1)

        right_col = QVBoxLayout()
        right_col.setSpacing(8)
        right_col.addWidget(self.right_caption)
        right_col.addWidget(self.right_stack, 1)
        self.feedback = FeedbackBar(self._chrome)
        self.feedback.accepted.connect(self._on_accept)
        self.feedback.rejected.connect(self._on_reject)
        right_col.addWidget(self.feedback, 0, Qt.AlignmentFlag.AlignHCenter)

        self.generate_btn = QPushButton("生成油画", self._chrome)
        self.generate_btn.setObjectName("PrimaryButton")
        self.generate_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.generate_btn.clicked.connect(self._on_generate)
        self.busy_pill = QPushButton("正在重画…", self._chrome)
        self.busy_pill.setObjectName("BusyPill")
        self.busy_pill.setEnabled(False)
        self.busy_pill.setVisible(False)

        center = QVBoxLayout()
        center.addStretch(1)
        center.addWidget(self.generate_btn, 0, Qt.AlignmentFlag.AlignHCenter)
        center.addWidget(self.busy_pill, 0, Qt.AlignmentFlag.AlignHCenter)
        center.addStretch(1)

        workbench = QHBoxLayout()
        workbench.setContentsMargins(48, 4, 48, 8)
        workbench.setSpacing(12)
        workbench.addLayout(left_col, 1)
        workbench.addLayout(center, 0)
        workbench.addLayout(right_col, 1)

        self.footer = Footer(self._chrome)
        self.footer.toggle_requested.connect(self._on_footer_toggle)

        outer = QVBoxLayout(self._chrome)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self.title_bar)
        outer.addWidget(Hairline(self._chrome))
        outer.addLayout(toolbar)
        outer.addWidget(self.banner)
        outer.addLayout(workbench, 1)
        outer.addWidget(self.footer)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self._chrome)

    def _toolbar_button(self, text: str) -> QPushButton:
        btn = QPushButton(text, self)
        btn.setObjectName("ToolbarButton")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        return btn

    def _fit_to_screen(self) -> None:
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            self.resize(PREFERRED_SIZE)
            return
        avail = screen.availableGeometry()
        width = min(PREFERRED_SIZE.width(), max(1100, avail.width() - 40))
        height = min(PREFERRED_SIZE.height(), max(760, avail.height() - 40))
        self.resize(width, height)
        geo = self.frameGeometry()
        geo.moveCenter(avail.center())
        self.move(geo.topLeft())

    # ----- window chrome -----

    def toggle_max_restore(self) -> None:
        if self._maximized:
            self._maximized = False
            if self._normal_geo is not None:
                self.setGeometry(self._normal_geo)
            self.title_bar.set_maximized(False)
            self._chrome.setStyleSheet("")
        else:
            self._normal_geo = self.geometry()
            screen = QGuiApplication.primaryScreen()
            if screen is not None:
                self.setGeometry(screen.availableGeometry())
            self._maximized = True
            self.title_bar.set_maximized(True)
        self.update()

    def _nudge(self, delta) -> None:  # noqa: ANN001
        if self._maximized:
            return
        self.move(self.pos() + delta)

    def mousePressEvent(self, event) -> None:  # noqa: ANN001
        if event.button() == Qt.MouseButton.LeftButton and not self._maximized:
            self._resize_edge = self._hit_edge(event.position().toPoint())
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: ANN001
        pos = event.position().toPoint()
        edge = self._hit_edge(pos) if not self._maximized else ""
        cursors = {
            "left": Qt.CursorShape.SizeHorCursor,
            "right": Qt.CursorShape.SizeHorCursor,
            "top": Qt.CursorShape.SizeVerCursor,
            "bottom": Qt.CursorShape.SizeVerCursor,
            "top-left": Qt.CursorShape.SizeFDiagCursor,
            "bottom-right": Qt.CursorShape.SizeFDiagCursor,
            "top-right": Qt.CursorShape.SizeBDiagCursor,
            "bottom-left": Qt.CursorShape.SizeBDiagCursor,
        }
        self.setCursor(cursors.get(edge, Qt.CursorShape.ArrowCursor))
        if self._resize_edge and event.buttons() & Qt.MouseButton.LeftButton:
            self._resize_to(event.globalPosition().toPoint())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: ANN001
        self._resize_edge = None
        super().mouseReleaseEvent(event)

    def _hit_edge(self, pos) -> str:  # noqa: ANN001
        m = RESIZE_MARGIN
        x, y, w, h = pos.x(), pos.y(), self.width(), self.height()
        left, right, top, bottom = x <= m, x >= w - m, y <= m, y >= h - m
        if top and left:
            return "top-left"
        if top and right:
            return "top-right"
        if bottom and left:
            return "bottom-left"
        if bottom and right:
            return "bottom-right"
        if left:
            return "left"
        if right:
            return "right"
        if top:
            return "top"
        if bottom:
            return "bottom"
        return ""

    def _resize_to(self, global_pos) -> None:  # noqa: ANN001
        geo = self.geometry()
        edge = self._resize_edge
        min_w, min_h = self.minimumWidth(), self.minimumHeight()
        if "left" in edge:
            x2 = geo.right()
            geo.setLeft(min(global_pos.x(), x2 - min_w))
        if "right" in edge:
            geo.setRight(max(global_pos.x(), geo.left() + min_w))
        if "top" in edge:
            y2 = geo.bottom()
            geo.setTop(min(global_pos.y(), y2 - min_h))
        if "bottom" in edge:
            geo.setBottom(max(global_pos.y(), geo.top() + min_h))
        self.setGeometry(geo)

    # ----- file open / drop / save -----

    def open_photo(self) -> None:
        start = str(default_pictures_dir())
        path, _ = QFileDialog.getOpenFileName(self, "打开本地照片", start, OPEN_FILTER)
        if path:
            self._load_source(Path(path))

    def save_result(self) -> None:
        if not self.pipeline.can_save():
            self.banner.show_message("还没有可保存的油画结果。")
            return
        suggested = str(default_pictures_dir() / self.pipeline.default_save_name())
        path, selected = QFileDialog.getSaveFileName(self, "保存油画", suggested, SAVE_FILTER)
        if not path:
            return
        dest = Path(path)
        if dest.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
            dest = dest.with_suffix(".jpg" if "JPEG" in selected else ".png")
        try:
            self.pipeline.save_result(dest)
        except PipelineError as exc:
            self.banner.show_message(exc.status_text)
            return
        self.banner.show_message(f"已保存到 {dest.name}。文件只留在本机。")
        self._sync_chrome()

    def _on_dropped(self, paths: list) -> None:
        if paths:
            self._load_source(Path(paths[0]))

    def dragEnterEvent(self, event) -> None:  # noqa: ANN001
        if _has_local_image(event):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event) -> None:  # noqa: ANN001
        paths = _local_image_paths(event)
        if paths:
            event.acceptProposedAction()
            self._load_source(Path(paths[0]))
        else:
            event.ignore()

    def _load_source(self, path: Path) -> None:
        try:
            self.pipeline.load_source(path)
        except FileOpenError as exc:
            self.banner.show_message(exc.status_text)
            return
        except PermissionError:
            self.banner.show_message("没有权限读取该文件。")
            return
        pixmap = _preview_pixmap(path)
        if pixmap.isNull():
            self.banner.show_message("无法打开该图片，文件可能已损坏。")
            return
        self.source_card.set_pixmap(pixmap)
        self.left_stack.setCurrentWidget(self.source_card)
        self.result_card.clear()
        self.right_stack.setCurrentWidget(self.placeholder)
        self.feedback.reset()
        self.footer.collapse()
        self.banner.setVisible(False)
        self._sync_chrome()

    # ----- generate / review -----

    def _on_generate(self) -> None:
        if self._busy:
            return
        if self.pipeline.source_path is None:
            self.banner.show_message("请先打开一张本地照片。")
            return
        if not self.pipeline.engine_is_ready():
            self.banner.show_message(self.pipeline.engine_message())
            try:
                self.pipeline.generate()
            except EngineNotReady:
                pass
            self._sync_chrome()
            return
        self._set_busy(True, "正在加载模型…")
        QApplication.processEvents()
        try:
            self.pipeline.prepare_engine()
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("failed to load local model: %s", exc)
            self._set_busy(False)
            self.banner.show_message("模型加载失败，请再试一次。")
            self._sync_chrome()
            return
        self._run_in_thread(lambda: self.pipeline.generate(auto_patch=False), on_ok=self._on_generated, busy_text="正在生成…")

    def _on_generated(self, path: Path) -> None:
        # Give the GPU and the window a moment after the CUDA process exits.
        QTimer.singleShot(400, lambda p=Path(path): self._present_result(p))

    def _present_result(self, path: Path) -> None:
        self._show_result(path)
        self.feedback.set_selection(None)
        self.feedback.setVisible(True)
        if self.pipeline.last_review and not self.pipeline.last_review.all_passed:
            # Auto-patch already ran inside the pipeline; still present the result.
            self.footer.show_review(self.pipeline.last_review)
        self._sync_chrome()

    def _on_accept(self) -> None:
        try:
            self.pipeline.accept()
        except PipelineError as exc:
            self.banner.show_message(exc.status_text)
            return
        self.feedback.set_selection("yes")
        self.footer.collapse()
        if self.pipeline.saved_path is None:
            self.banner.show_message("已标记为满意，可以点右上角「保存」。不会上传到任何地方。")
        self._highlight_save(True)
        self._sync_chrome()

    def _on_reject(self) -> None:
        if self._busy:
            return
        if self.pipeline.result_path is None:
            self.banner.show_message("还没有可审阅的油画结果。")
            return
        self.feedback.set_selection("no")
        # Run review immediately (sync, cheap) so the panel can open at once.
        if self.pipeline.source_path and self.pipeline.result_path:
            from impression_oil.review import review_paths

            preview = review_paths(
                self.pipeline.source_path,
                self.pipeline.result_path,
                engine_ready=self.pipeline.engine_is_ready(),
            )
            self.footer.show_review(preview, busy=True)
        if not self.pipeline.engine_is_ready():
            self.banner.show_message(self.pipeline.engine_message())
            try:
                self.pipeline.reject()
            except EngineNotReady:
                pass
            self._sync_chrome()
            return
        self._run_in_thread(self.pipeline.reject, on_ok=self._on_rejected, busy_text="正在重画…")

    def _on_rejected(self, payload) -> None:  # noqa: ANN001
        review, path = payload
        self._show_result(path)
        self.feedback.set_selection(None)
        self.feedback.setVisible(True)
        self.footer.show_review(review)
        self._sync_chrome()

    def _show_result(self, path: Path) -> None:
        pixmap = _preview_pixmap(path)
        if pixmap.isNull():
            self.banner.show_message("无法打开生成结果。")
            return
        self.result_card.set_pixmap(pixmap)
        self.right_stack.setCurrentWidget(self.result_card)

    def _on_footer_toggle(self, expanded: bool) -> None:
        if expanded:
            self.footer.reveal_or_hide_review(self.pipeline.last_review)
        else:
            self.footer.collapse()

    def _highlight_save(self, on: bool) -> None:
        self.save_btn.setProperty("highlight", "true" if on else "false")
        self.save_btn.style().unpolish(self.save_btn)
        self.save_btn.style().polish(self.save_btn)
        self.save_btn.update()

    # ----- worker -----

    def _run_in_thread(self, fn, *, on_ok, busy_text: str) -> None:  # noqa: ANN001
        if self._work_thread is not None and self._work_thread.is_alive():
            return
        self._set_busy(True, busy_text)
        self._job_on_ok = on_ok

        def work() -> None:
            try:
                self._job_finished.emit(fn())
            except (EngineNotReady, GenerationError, PipelineError, FileOpenError) as exc:
                self._job_failed.emit(getattr(exc, "status_text", str(exc)))
            except Exception as exc:  # noqa: BLE001
                LOGGER.exception("worker failed: %s", exc)
                self._job_failed.emit("处理失败，请再试一次。")

        thread = threading.Thread(target=work, daemon=True)
        self._work_thread = thread
        thread.start()

    def _on_job_finished(self, result) -> None:  # noqa: ANN001
        self._work_thread = None
        # Release the CUDA process before touching the window. Showing a
        # result while the child still holds the GPU has been aborting
        # Qt6Core.dll on this machine.
        self.pipeline.release_engine()
        self._set_busy(False)
        on_ok = self._job_on_ok
        self._job_on_ok = None
        if on_ok is not None:
            on_ok(result)

    def _on_job_failed(self, message: str) -> None:
        self._work_thread = None
        self._job_on_ok = None
        self.pipeline.release_engine()
        self._set_busy(False)
        self.banner.show_message(message)
        self._sync_chrome()

    def _set_busy(self, busy: bool, text: str = "正在重画…") -> None:
        self._busy = busy
        self.generate_btn.setVisible(not busy)
        self.busy_pill.setText(text)
        self.busy_pill.setVisible(busy)
        self.open_btn.setEnabled(not busy)
        self._sync_chrome()

    def _sync_chrome(self) -> None:
        has_source = self.pipeline.source_path is not None
        has_result = self.pipeline.can_save()
        busy = self._busy
        self.generate_btn.setEnabled(has_source and not busy)
        self.regen_btn.setEnabled(has_source and not busy)
        self.save_btn.setEnabled(has_result and not busy)
        if not (self.pipeline.accepted and self.pipeline.saved_path is None):
            if not self.pipeline.accepted:
                self._highlight_save(False)
        if not has_result:
            self._highlight_save(False)

    def resizeEvent(self, event) -> None:  # noqa: ANN001
        # Do not call setMask() here: it can abort Qt on Windows during layout
        # changes (for example when the generate button is replaced by the busy pill).
        super().resizeEvent(event)

    def closeEvent(self, event) -> None:  # noqa: ANN001
        thread = self._work_thread
        if thread is not None and thread.is_alive():
            thread.join(1.0)
        super().closeEvent(event)


def _preview_pixmap(path: Path, max_edge: int = 2048) -> QPixmap:
    """Load a display copy so a huge photo cannot blow up the window."""
    try:
        data = Path(path).read_bytes()
    except OSError:
        return QPixmap()
    image = QImage()
    if not image.loadFromData(data):
        return QPixmap()
    if max(image.width(), image.height()) > max_edge:
        image = image.scaled(
            max_edge,
            max_edge,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.FastTransformation,
        )
    return QPixmap.fromImage(image)


def make_window(pipeline: Pipeline | None = None) -> MainWindow:
    return MainWindow(pipeline=pipeline)
