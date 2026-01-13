from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtCore import QPoint
from PySide6.QtCore import QSize
from PySide6.QtCore import QTimer
from PySide6.QtCore import Signal
from PySide6.QtCore import QUrl
from PySide6.QtGui import QColor
from PySide6.QtGui import QIcon
from PySide6.QtGui import QPainter
from PySide6.QtGui import QPixmap
from PySide6.QtGui import QPolygon
from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import QMenu
from PySide6.QtWidgets import QGridLayout
from PySide6.QtWidgets import QHBoxLayout
from PySide6.QtWidgets import QLabel
from PySide6.QtWidgets import QPlainTextEdit
from PySide6.QtWidgets import QStyle
from PySide6.QtWidgets import QTabWidget
from PySide6.QtWidgets import QToolButton
from PySide6.QtWidgets import QVBoxLayout
from PySide6.QtWidgets import QWidget

try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
except Exception:  # pragma: no cover
    QWebEngineView = None

from agents_runner.ui.pages.artifacts_tab import ArtifactsTab

from agents_runner.artifacts import get_artifact_info
from agents_runner.environments import GH_MANAGEMENT_GITHUB
from agents_runner.ui.task_model import Task
from agents_runner.ui.task_model import _task_display_status
from agents_runner.ui.utils import _format_duration
from agents_runner.ui.utils import _rgba
from agents_runner.ui.utils import _status_color
from agents_runner.widgets import GlassCard
from agents_runner.widgets import LogHighlighter
from agents_runner.widgets import StatusGlyph

import logging

logger = logging.getLogger(__name__)


def _diamond_icon(size: int = 16, color: QColor | None = None) -> QIcon:
    color = color or QColor(237, 239, 245)
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)

    half = (size - 1) / 2.0
    inset = max(2, int(size * 0.22))
    pts = QPolygon(
        [
            QPoint(int(half), inset),
            QPoint(size - inset - 1, int(half)),
            QPoint(int(half), size - inset - 1),
            QPoint(inset, int(half)),
        ]
    )

    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setPen(Qt.NoPen)
    p.setBrush(color)
    p.drawPolygon(pts)
    p.end()

    return QIcon(pm)


class TaskDetailsPage(QWidget):
    back_requested = Signal()
    pr_requested = Signal(str)
    container_action_requested = Signal(str, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._current_task_id: str | None = None
        self._desktop_tab_visible: bool = False
        self._artifacts_tab_visible: bool = False
        self._environments: dict[str, object] | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        header = GlassCard()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(18, 16, 18, 16)
        header_layout.setSpacing(10)

        self._title = QLabel("Task")
        self._title.setStyleSheet("font-size: 18px; font-weight: 750;")
        self._subtitle = QLabel("—")
        self._subtitle.setStyleSheet("color: rgba(237, 239, 245, 160);")

        back = QToolButton()
        back.setText("Back")
        back.setToolButtonStyle(Qt.ToolButtonTextOnly)
        back.clicked.connect(self.back_requested.emit)

        self._review_menu = QMenu(self)
        self._review_pr = self._review_menu.addAction("Create PR")
        self._review_pr.triggered.connect(self._on_pr_triggered)
        self._review = QToolButton()
        self._review.setText("Review")
        self._review.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self._review.setMenu(self._review_menu)
        self._review.setPopupMode(QToolButton.InstantPopup)
        self._review.setVisible(False)

        header_layout.addWidget(self._title)
        header_layout.addWidget(self._subtitle, 1)
        header_layout.addWidget(self._review, 0, Qt.AlignRight)
        header_layout.addWidget(back, 0, Qt.AlignRight)
        layout.addWidget(header)

        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)
        self._tabs.currentChanged.connect(self._on_tab_changed)

        task_tab = QWidget()
        task_layout = QVBoxLayout(task_tab)
        task_layout.setContentsMargins(0, 0, 0, 0)
        task_layout.setSpacing(14)

        mid = QHBoxLayout()
        mid.setSpacing(14)
        task_layout.addLayout(mid, 2)

        left = GlassCard()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(18, 16, 18, 16)
        left_layout.setSpacing(10)

        left_title = QLabel("Prompt")
        left_title.setStyleSheet("font-size: 14px; font-weight: 650;")

        self._prompt = QPlainTextEdit()
        self._prompt.setReadOnly(True)
        self._prompt.setMaximumBlockCount(2000)

        cfg = QGridLayout()
        cfg.setHorizontalSpacing(10)
        cfg.setVerticalSpacing(8)

        self._workdir = QLabel("—")
        self._codexdir = QLabel("—")
        self._container = QLabel("—")
        self._container.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._workdir.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._codexdir.setTextInteractionFlags(Qt.TextSelectableByMouse)

        cfg.addWidget(QLabel("Host Workdir"), 0, 0)
        cfg.addWidget(self._workdir, 0, 1)
        cfg.addWidget(QLabel("Host Config folder"), 1, 0)
        cfg.addWidget(self._codexdir, 1, 1)
        cfg.addWidget(QLabel("Container ID"), 2, 0)
        cfg.addWidget(self._container, 2, 1)

        prompt_page = QWidget()
        prompt_layout = QVBoxLayout(prompt_page)
        prompt_layout.setContentsMargins(0, 0, 0, 0)
        prompt_layout.setSpacing(10)
        prompt_layout.addWidget(self._prompt, 1)
        prompt_layout.addLayout(cfg)

        left_layout.addWidget(left_title)
        left_layout.addWidget(prompt_page, 1)
        mid.addWidget(left, 3)

        right = GlassCard()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(18, 16, 18, 16)
        right_layout.setSpacing(12)

        stitle = QLabel("Container state")
        stitle.setStyleSheet("font-size: 14px; font-weight: 650;")

        self._btn_freeze = QToolButton()
        self._btn_freeze.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self._btn_freeze.setAutoRaise(True)
        self._btn_freeze.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))
        self._btn_freeze.setIconSize(QSize(16, 16))
        self._btn_freeze.setToolTip("Freeze: Pause the container")
        self._btn_freeze.clicked.connect(lambda: self._emit_container_action("freeze"))

        self._btn_unfreeze = QToolButton()
        self._btn_unfreeze.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self._btn_unfreeze.setAutoRaise(True)
        self._btn_unfreeze.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self._btn_unfreeze.setIconSize(QSize(16, 16))
        self._btn_unfreeze.setToolTip("Unfreeze: Resume the container")
        self._btn_unfreeze.clicked.connect(
            lambda: self._emit_container_action("unfreeze")
        )

        self._btn_stop = QToolButton()
        self._btn_stop.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self._btn_stop.setAutoRaise(True)
        self._btn_stop.setIcon(self.style().standardIcon(QStyle.SP_MediaStop))
        self._btn_stop.setIconSize(QSize(16, 16))
        self._btn_stop.setToolTip("Stop container")
        self._btn_stop.clicked.connect(lambda: self._emit_container_action("stop"))

        self._btn_kill = QToolButton()
        self._btn_kill.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self._btn_kill.setAutoRaise(True)
        self._btn_kill.setIcon(_diamond_icon(16))
        self._btn_kill.setIconSize(QSize(16, 16))
        self._btn_kill.setToolTip("Kill: Force stop the container immediately")
        self._btn_kill.clicked.connect(lambda: self._emit_container_action("kill"))

        title_row = QHBoxLayout()
        title_row.setSpacing(8)
        title_row.addWidget(stitle)
        title_row.addStretch(1)
        title_row.addWidget(self._btn_freeze)
        title_row.addWidget(self._btn_unfreeze)
        title_row.addWidget(self._btn_stop)
        title_row.addWidget(self._btn_kill)

        state_row = QHBoxLayout()
        state_row.setSpacing(12)
        self._glyph = StatusGlyph(size=44)
        self._status = QLabel("idle")
        self._status.setStyleSheet("font-size: 16px; font-weight: 750;")
        state_row.addWidget(self._glyph, 0, Qt.AlignLeft)
        state_row.addWidget(self._status, 1)

        details = QGridLayout()
        details.setHorizontalSpacing(10)
        details.setVerticalSpacing(8)

        self._started = QLabel("—")
        self._uptime = QLabel("—")
        self._exit = QLabel("—")
        details.addWidget(QLabel("Started"), 0, 0)
        details.addWidget(self._started, 0, 1)
        details.addWidget(QLabel("Elapsed"), 1, 0)
        details.addWidget(self._uptime, 1, 1)
        details.addWidget(QLabel("Exit code"), 2, 0)
        details.addWidget(self._exit, 2, 1)

        right_layout.addLayout(title_row)
        right_layout.addLayout(state_row)
        right_layout.addLayout(details)
        right_layout.addStretch(1)
        mid.addWidget(right, 2)

        logs = GlassCard()
        logs_layout = QVBoxLayout(logs)
        logs_layout.setContentsMargins(18, 16, 18, 16)
        logs_layout.setSpacing(10)

        ltitle = QLabel("Logs")
        ltitle.setStyleSheet("font-size: 14px; font-weight: 650;")
        self._logs = QPlainTextEdit()
        self._logs.setObjectName("LogsView")
        self._logs.setReadOnly(True)
        self._logs.setLineWrapMode(QPlainTextEdit.NoWrap)
        self._logs.setMaximumBlockCount(5000)
        self._log_highlighter = LogHighlighter(self._logs.document())
        logs_layout.addWidget(ltitle)
        logs_layout.addWidget(self._logs, 1)
        task_layout.addWidget(logs, 2)

        desktop_tab = QWidget()
        desktop_layout = QVBoxLayout(desktop_tab)
        desktop_layout.setContentsMargins(0, 0, 0, 0)
        desktop_layout.setSpacing(10)

        self._desktop_loaded_url = ""
        self._desktop_url = QLabel("—")
        self._desktop_display = QLabel("—")
        for label in (self._desktop_url, self._desktop_display):
            label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self._desktop_layout = desktop_layout
        self._desktop_web: QWebEngineView | None = None

        # Create QWebEngineView immediately if available (not lazily)
        if QWebEngineView is not None:
            self._desktop_web = QWebEngineView()
            self._desktop_view: QWidget = self._desktop_web
        else:
            # Fallback label if QtWebEngine is not available
            desktop_label = QLabel(
                "QtWebEngine not available; open the noVNC URL externally."
            )
            desktop_label.setWordWrap(True)
            self._desktop_view: QWidget = desktop_label

        desktop_cfg = QGridLayout()
        desktop_cfg.setHorizontalSpacing(10)
        desktop_cfg.setVerticalSpacing(8)
        desktop_cfg.addWidget(QLabel("noVNC URL"), 0, 0)
        desktop_cfg.addWidget(self._desktop_url, 0, 1)
        desktop_cfg.addWidget(QLabel("DISPLAY"), 1, 0)
        desktop_cfg.addWidget(self._desktop_display, 1, 1)

        desktop_layout.addWidget(self._desktop_view, 1)
        desktop_layout.addLayout(desktop_cfg)

        # Artifacts tab
        artifacts_tab = ArtifactsTab()
        self._artifacts_tab = artifacts_tab

        # Store tab widgets for dynamic show/hide
        self._task_tab_widget = task_tab
        self._desktop_tab_widget = desktop_tab
        self._artifacts_tab_widget = artifacts_tab

        # Add only the Task tab initially (always visible)
        self._task_tab_index = self._tabs.addTab(task_tab, "Task")
        # Desktop and Artifacts tabs will be added dynamically when needed
        self._desktop_tab_index = -1
        self._artifacts_tab_index = -1
        layout.addWidget(self._tabs, 1)

        self._ticker = QTimer(self)
        self._ticker.setInterval(1000)
        self._ticker.timeout.connect(self._tick_uptime)
        self._ticker.start()

        self._last_task: Task | None = None

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        if self._tabs.currentIndex() == getattr(self, "_task_tab_index", -1):
            QTimer.singleShot(0, self._scroll_logs_to_bottom)

    def _on_tab_changed(self, index: int) -> None:
        if index == getattr(self, "_task_tab_index", -1):
            QTimer.singleShot(0, self._scroll_logs_to_bottom)
            return

        if index == getattr(self, "_desktop_tab_index", -1) and index >= 0:
            QTimer.singleShot(0, self._maybe_load_desktop)
            return

        if index == getattr(self, "_artifacts_tab_index", -1) and index >= 0:
            QTimer.singleShot(0, self._load_artifacts)

    def _show_desktop_tab(self) -> None:
        """Show the Desktop tab if not already visible."""
        if self._desktop_tab_visible:
            return
        self._desktop_tab_index = self._tabs.addTab(self._desktop_tab_widget, "Desktop")
        self._desktop_tab_visible = True

    def _hide_desktop_tab(self) -> None:
        """Hide the Desktop tab if currently visible."""
        if not self._desktop_tab_visible:
            return
        # If Desktop tab is currently active, switch to Task tab
        if self._tabs.currentIndex() == self._desktop_tab_index:
            self._tabs.setCurrentIndex(self._task_tab_index)
        self._tabs.removeTab(self._desktop_tab_index)
        self._desktop_tab_index = -1
        self._desktop_tab_visible = False

    def _show_artifacts_tab(self) -> None:
        """Show the Artifacts tab if not already visible."""
        if self._artifacts_tab_visible:
            return
        self._artifacts_tab_index = self._tabs.addTab(self._artifacts_tab_widget, "Artifacts")
        self._artifacts_tab_visible = True

    def _hide_artifacts_tab(self) -> None:
        """Hide the Artifacts tab if currently visible."""
        if not self._artifacts_tab_visible:
            return
        # If Artifacts tab is currently active, switch to Task tab
        if self._tabs.currentIndex() == self._artifacts_tab_index:
            self._tabs.setCurrentIndex(self._task_tab_index)
        self._tabs.removeTab(self._artifacts_tab_index)
        self._artifacts_tab_index = -1
        self._artifacts_tab_visible = False

    def _on_pr_triggered(self) -> None:
        task_id = str(self._current_task_id or "").strip()
        if task_id:
            self.pr_requested.emit(task_id)

    def _sync_review_menu(self, task: Task) -> None:
        # Task.requires_git_metadata() already checks workspace_type
        can_pr = task.requires_git_metadata()
        
        pr_url = str(task.gh_pr_url or "").strip()
        self._review_pr.setVisible(can_pr)
        self._review_pr.setEnabled(can_pr and not task.is_active())
        self._review_pr.setText("Open PR" if pr_url.startswith("http") else "Create PR")

        self._review.setVisible(can_pr)
        self._review.setEnabled(can_pr and not task.is_active())

    def _logs_is_at_bottom(self, slack: int = 6) -> bool:
        bar = self._logs.verticalScrollBar()
        return bar.value() >= (bar.maximum() - slack)

    def _scroll_logs_to_bottom(self) -> None:
        bar = self._logs.verticalScrollBar()
        bar.setValue(bar.maximum())

    def current_task_id(self) -> str | None:
        return self._current_task_id

    def _emit_container_action(self, action: str) -> None:
        task_id = str(self._current_task_id or "").strip()
        if task_id:
            if str(action or "").strip().lower() in {"stop", "kill"}:
                self._btn_stop.setEnabled(False)
                self._btn_kill.setEnabled(False)
            self.container_action_requested.emit(task_id, str(action or "").strip())

    def _sync_container_actions(self, task: Task) -> None:
        has_container = bool(str(task.container_id or "").strip())
        is_paused = (task.status or "").lower() == "paused"
        is_terminal = (task.status or "").lower() in {"cancelled", "killed"}
        self._btn_freeze.setEnabled(has_container and not is_paused and not is_terminal)
        self._btn_unfreeze.setEnabled(has_container and is_paused and not is_terminal)
        self._btn_stop.setEnabled(has_container and not is_terminal)
        self._btn_kill.setEnabled(has_container and not is_terminal)

    def set_environments(self, environments: dict[str, object]) -> None:
        """Set the environments dict for looking up cloned repo status."""
        self._environments = environments

    def show_task(self, task: Task) -> None:
        self._current_task_id = task.task_id
        self._last_task = task
        self._title.setText(f"Task {task.task_id}")
        self._subtitle.setText(task.prompt_one_line())
        self._prompt.setPlainText(task.prompt)
        self._workdir.setText(task.host_workdir)
        self._codexdir.setText(task.host_codex_dir)
        self._container.setText(task.container_id or "—")
        self._tabs.setCurrentIndex(self._task_tab_index)
        self._sync_desktop(task)
        self._sync_artifacts(task)
        self._sync_container_actions(task)
        self._logs.setPlainText("\n".join(task.logs[-5000:]))
        QTimer.singleShot(0, self._scroll_logs_to_bottom)
        self._apply_status(task)
        self._tick_uptime()
        self._sync_review_menu(task)

    def append_log(self, task_id: str, line: str) -> None:
        if self._current_task_id != task_id:
            return
        should_follow = self._logs_is_at_bottom()
        self._logs.appendPlainText(line)
        if should_follow:
            QTimer.singleShot(0, self._scroll_logs_to_bottom)

    def update_task(self, task: Task) -> None:
        if self._current_task_id != task.task_id:
            return
        self._last_task = task
        self._container.setText(task.container_id or "—")
        self._sync_desktop(task)
        self._sync_artifacts(task)
        self._sync_container_actions(task)
        self._exit.setText("—" if task.exit_code is None else str(task.exit_code))
        self._apply_status(task)
        self._tick_uptime()
        self._sync_review_menu(task)
        
        # Notify artifacts tab of status changes
        if self._artifacts_tab_visible:
            self._artifacts_tab.on_task_status_changed(task)

    def _maybe_load_desktop(self) -> None:
        if not self._last_task or not self._desktop_tab_visible:
            return
        if self._tabs.currentIndex() != self._desktop_tab_index:
            return
        url = str(self._last_task.novnc_url or "").strip()
        if not url or url == self._desktop_loaded_url:
            return
        # Use the pre-created webview directly (no lazy initialization)
        if self._desktop_web is None:
            return
        self._desktop_loaded_url = url
        try:
            self._desktop_web.setUrl(QUrl(url))
        except Exception:
            pass

    def _sync_desktop(self, task: Task) -> None:
        # Get the URL first to check if desktop is ready
        url = str(task.novnc_url or "").strip()
        
        # Show tab ONLY when desktop is ready (URL is available)
        should_show = bool(
            task.is_active() and 
            task.headless_desktop_enabled and
            url  # Desktop is ready (not empty)
        )
        
        if not hasattr(self, "_tabs"):
            return

        if not should_show:
            self._hide_desktop_tab()
            self._desktop_loaded_url = ""
            self._desktop_url.setText("—")
            self._desktop_display.setText("—")
            if self._desktop_web is not None:
                try:
                    self._desktop_web.setUrl(QUrl("about:blank"))
                except Exception:
                    pass
            return

        self._show_desktop_tab()
        self._desktop_url.setText(url)
        self._desktop_display.setText(str(task.desktop_display or ":1"))
        if self._desktop_tab_visible and self._tabs.currentIndex() == self._desktop_tab_index:
            self._maybe_load_desktop()

    def _sync_artifacts(self, task: Task) -> None:
        """
        Update Artifacts tab visibility based on artifact status.
        
        Shows tab ONLY when artifacts actually exist:
        - file_count > 0 (has files in staging directory), OR
        - task.artifacts is not empty (has encrypted artifacts from completed task)
        
        Does NOT show for:
        - Empty staging directory
        - Active task with no artifacts yet
        - When artifact_info.exists is True but file_count is 0
        """
        # Get single source of truth
        artifact_info = get_artifact_info(task.task_id)
        
        # Check encrypted artifacts (for completed tasks)
        has_encrypted = bool(task.artifacts)
        
        # Show tab ONLY when artifacts actually exist
        should_show = (
            artifact_info.file_count > 0 or
            has_encrypted
        )
        
        # Debug logging (REQUIRED)
        logger.info(
            f"Artifacts tab: task={task.task_id} dir={artifact_info.host_artifacts_dir} "
            f"exists={artifact_info.exists} count={artifact_info.file_count} shown={should_show}"
        )
        
        if should_show:
            was_visible = self._artifacts_tab_visible
            self._show_artifacts_tab()
            # Load artifacts when tab first appears
            if not was_visible:
                QTimer.singleShot(0, self._load_artifacts)
        else:
            self._hide_artifacts_tab()

    def _load_artifacts(self) -> None:
        if self._last_task:
            self._artifacts_tab.set_task(self._last_task)

    def _apply_status(self, task: Task) -> None:
        status = _task_display_status(task)
        color = _status_color(task.status)
        self._status.setText(status)
        self._status.setStyleSheet(
            "font-size: 16px; font-weight: 750; " f"color: {_rgba(color, 235)};"
        )
        if task.is_active():
            self._glyph.set_mode("spinner", color)
        elif task.is_done():
            self._glyph.set_mode("check", color)
        elif task.is_failed() or status.startswith("Exit "):
            self._glyph.set_mode("x", color)
        else:
            self._glyph.set_mode("idle", color)

        started_local = "—"
        if task.started_at:
            started_local = task.started_at.astimezone().strftime("%Y-%m-%d %H:%M:%S")
        self._started.setText(started_local)
        self._exit.setText("—" if task.exit_code is None else str(task.exit_code))

    def _tick_uptime(self) -> None:
        task = self._last_task
        if not task:
            self._uptime.setText("—")
            return
        self._uptime.setText(_format_duration(task.elapsed_seconds()))
