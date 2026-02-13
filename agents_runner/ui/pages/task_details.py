from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtCore import QProcess
from PySide6.QtCore import QProcessEnvironment
from PySide6.QtCore import QUrl
from PySide6.QtCore import QSize
from PySide6.QtCore import QTimer
from PySide6.QtCore import Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import QApplication
from PySide6.QtWidgets import QMenu
from PySide6.QtWidgets import QGridLayout
from PySide6.QtWidgets import QHBoxLayout
from PySide6.QtWidgets import QLabel
from PySide6.QtWidgets import QMessageBox
from PySide6.QtWidgets import QPlainTextEdit
from PySide6.QtWidgets import QTabWidget
from PySide6.QtWidgets import QToolButton
from PySide6.QtWidgets import QVBoxLayout
from PySide6.QtWidgets import QWidget

from agents_runner.ui.pages.artifacts_tab import ArtifactsTab

from agents_runner.artifacts import get_artifact_info
from agents_runner.environments import WORKSPACE_CLONED
from agents_runner.ui.lucide_icons import lucide_icon
from agents_runner.ui.task_model import Task
from agents_runner.ui.task_model import _task_display_status
from agents_runner.ui.utils import _format_duration
from agents_runner.ui.utils import _rgba
from agents_runner.ui.utils import _status_color
from agents_runner.ui.widgets import GlassCard
from agents_runner.ui.widgets import LogHighlighter
from agents_runner.ui.widgets import StatusGlyph

import logging
import sys

logger = logging.getLogger(__name__)


class TaskDetailsPage(QWidget):
    back_requested = Signal()
    pr_requested = Signal(str)
    container_action_requested = Signal(str, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._current_task_id: str | None = None
        self._artifacts_tab_visible: bool = False
        self._environments: dict[str, object] | None = None
        self._desktop_viewer_process: QProcess | None = None
        self._desktop_viewer_url: str = ""
        self._desktop_viewer_output_lines: list[str] = []

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

        self._review_menu = QMenu(self)
        self._review_pr = self._review_menu.addAction("Create PR")
        self._review_pr.triggered.connect(self._on_pr_triggered)
        self._review = QToolButton()
        self._review.setText("Review")
        self._review.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self._review.setMenu(self._review_menu)
        self._review.setPopupMode(QToolButton.InstantPopup)
        self._review.setVisible(False)

        self._desktop_btn = QToolButton()
        self._desktop_btn.setText("Desktop")
        self._desktop_btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self._desktop_btn.clicked.connect(self._launch_desktop_viewer)
        self._desktop_btn.setVisible(False)

        header_layout.addWidget(self._title)
        header_layout.addWidget(self._subtitle, 1)
        header_layout.addWidget(self._review, 0, Qt.AlignRight)
        header_layout.addWidget(self._desktop_btn, 0, Qt.AlignRight)
        layout.addWidget(header)

        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)
        self._tabs.tabBar().setDrawBase(False)
        self._tabs.currentChanged.connect(self._on_tab_changed)

        task_tab = QWidget()
        task_layout = QVBoxLayout(task_tab)
        task_layout.setContentsMargins(0, 0, 0, 0)
        task_layout.setSpacing(14)

        mid = QHBoxLayout()
        mid.setSpacing(14)
        task_layout.addLayout(mid, 1)

        # Left side: Logs card (full height)
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
        mid.addWidget(logs, 3)

        # Right side: Container state + Prompt cards stacked vertically
        right_column = QVBoxLayout()
        right_column.setSpacing(14)

        # Container state card (top-right)
        state_card = GlassCard()
        state_layout = QVBoxLayout(state_card)
        state_layout.setContentsMargins(18, 16, 18, 16)
        state_layout.setSpacing(12)

        stitle = QLabel("Container state")
        stitle.setStyleSheet("font-size: 14px; font-weight: 650;")

        self._btn_freeze = QToolButton()
        self._btn_freeze.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self._btn_freeze.setAutoRaise(True)
        self._btn_freeze.setIcon(lucide_icon("pause"))
        self._btn_freeze.setIconSize(QSize(16, 16))
        self._btn_freeze.setToolTip("Freeze: Pause the container")
        self._btn_freeze.clicked.connect(lambda: self._emit_container_action("freeze"))

        self._btn_unfreeze = QToolButton()
        self._btn_unfreeze.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self._btn_unfreeze.setAutoRaise(True)
        self._btn_unfreeze.setIcon(lucide_icon("play"))
        self._btn_unfreeze.setIconSize(QSize(16, 16))
        self._btn_unfreeze.setToolTip("Unfreeze: Resume the container")
        self._btn_unfreeze.clicked.connect(
            lambda: self._emit_container_action("unfreeze")
        )

        self._btn_stop = QToolButton()
        self._btn_stop.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self._btn_stop.setAutoRaise(True)
        self._btn_stop.setIcon(lucide_icon("square"))
        self._btn_stop.setIconSize(QSize(16, 16))
        self._btn_stop.setToolTip("Stop container")
        self._btn_stop.clicked.connect(lambda: self._emit_container_action("stop"))

        self._btn_kill = QToolButton()
        self._btn_kill.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self._btn_kill.setAutoRaise(True)
        self._btn_kill.setIcon(lucide_icon("circle-x"))
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

        state_layout.addLayout(title_row)
        state_layout.addLayout(state_row)
        state_layout.addLayout(details)
        right_column.addWidget(state_card)

        # Prompt card (bottom-right)
        prompt_card = GlassCard()
        prompt_layout = QVBoxLayout(prompt_card)
        prompt_layout.setContentsMargins(18, 16, 18, 16)
        prompt_layout.setSpacing(10)

        prompt_title_row = QHBoxLayout()
        prompt_title_row.setSpacing(8)
        prompt_title = QLabel("Prompt")
        prompt_title.setStyleSheet("font-size: 14px; font-weight: 650;")
        prompt_title_row.addWidget(prompt_title)
        prompt_title_row.addStretch(1)

        self._btn_copy_prompt = QToolButton()
        self._btn_copy_prompt.setText("Copy")
        self._btn_copy_prompt.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self._btn_copy_prompt.setToolTip("Copy prompt to clipboard")
        self._btn_copy_prompt.clicked.connect(self._copy_prompt_to_clipboard)
        prompt_title_row.addWidget(self._btn_copy_prompt)

        self._prompt = QPlainTextEdit()
        self._prompt.setReadOnly(True)
        self._prompt.setMaximumBlockCount(2000)

        cfg = QGridLayout()
        cfg.setHorizontalSpacing(10)
        cfg.setVerticalSpacing(8)

        self._workdir = QLabel("—")
        self._workdir_label = QLabel("Host Workdir")
        self._container = QLabel("—")
        self._container.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._workdir.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self._novnc_url = QLabel("—")
        self._novnc_url.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._desktop_display = QLabel("—")
        self._desktop_display.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self._workdir_row = 0
        cfg.addWidget(self._workdir_label, self._workdir_row, 0)
        cfg.addWidget(self._workdir, self._workdir_row, 1)
        self._container_row = 1
        cfg.addWidget(QLabel("Container ID"), self._container_row, 0)
        cfg.addWidget(self._container, self._container_row, 1)
        self._novnc_row = 2
        cfg.addWidget(QLabel("noVNC URL"), self._novnc_row, 0)
        cfg.addWidget(self._novnc_url, self._novnc_row, 1)
        self._display_row = 3
        cfg.addWidget(QLabel("DISPLAY"), self._display_row, 0)
        cfg.addWidget(self._desktop_display, self._display_row, 1)

        prompt_layout.addLayout(prompt_title_row)
        prompt_layout.addWidget(self._prompt, 1)
        prompt_layout.addLayout(cfg)
        right_column.addWidget(prompt_card, 1)

        mid.addLayout(right_column, 2)

        # Artifacts tab
        artifacts_tab = ArtifactsTab()
        self._artifacts_tab = artifacts_tab

        # Store tab widgets for dynamic show/hide
        self._task_tab_widget = task_tab
        self._artifacts_tab_widget = artifacts_tab

        # Add only the Task tab initially (always visible)
        self._task_tab_index = self._tabs.addTab(task_tab, "Task")
        # Artifacts tab will be added dynamically when needed
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

        if index == getattr(self, "_artifacts_tab_index", -1) and index >= 0:
            QTimer.singleShot(0, self._load_artifacts)

    def _show_artifacts_tab(self) -> None:
        """Show the Artifacts tab if not already visible."""
        if self._artifacts_tab_visible:
            return
        self._artifacts_tab_index = self._tabs.addTab(
            self._artifacts_tab_widget, "Artifacts"
        )
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

    def _copy_prompt_to_clipboard(self) -> None:
        """Copy the full prompt text to clipboard."""
        prompt_text = self._prompt.toPlainText()
        if prompt_text:
            clipboard = QApplication.clipboard()
            if clipboard:
                clipboard.setText(prompt_text)

    def _launch_desktop_viewer(self) -> None:
        """Launch the external desktop viewer process."""
        if not self._last_task:
            return

        url = str(self._last_task.novnc_url or "").strip()
        if not url:
            logger.warning("Cannot launch desktop viewer: no noVNC URL available")
            return

        try:
            from PySide6 import QtWebEngineWidgets as _  # noqa: F401
        except Exception:
            logger.warning(
                "QtWebEngine not available; opening noVNC URL in system browser instead"
            )
            QDesktopServices.openUrl(QUrl(url))
            return

        # If viewer is already running for this URL, don't launch another
        if (
            self._desktop_viewer_process is not None
            and self._desktop_viewer_process.state() == QProcess.ProcessState.Running
            and self._desktop_viewer_url == url
        ):
            logger.info("Desktop viewer already running")
            return

        # Clean up old process if it exists
        if self._desktop_viewer_process is not None:
            self._desktop_viewer_process.kill()
            self._desktop_viewer_process.waitForFinished(1000)
            self._desktop_viewer_process = None

        # Launch new viewer process
        task_id = str(self._current_task_id or "")
        title = f"Task {task_id}" if task_id else "Desktop"

        self._desktop_viewer_process = QProcess(self)
        self._desktop_viewer_process.setProcessChannelMode(
            QProcess.ProcessChannelMode.MergedChannels
        )
        self._desktop_viewer_process.readyReadStandardOutput.connect(
            self._on_viewer_output
        )
        self._desktop_viewer_process.finished.connect(self._on_viewer_finished)

        # Use sys.executable to get the current Python interpreter
        args = [
            "-X",
            "faulthandler",
            "-m",
            "agents_runner.ui.desktop_viewer",
            "--url",
            url,
            "--title",
            title,
        ]

        self._desktop_viewer_url = url
        self._desktop_viewer_output_lines = []
        env = QProcessEnvironment.systemEnvironment()
        env.insert("AGENTS_RUNNER_DESKTOP_VIEWER_FAULTHANDLER", "1")
        # QtWebEngine/Wayland can crash on some GPU stacks (often around GBM support).
        # Prefer XWayland for the out-of-process viewer unless the user overrides.
        try:
            session_type = str(env.value("XDG_SESSION_TYPE") or "").strip().lower()
        except Exception:
            session_type = ""
        allow_wayland = str(
            env.value("AGENTS_RUNNER_DESKTOP_VIEWER_ALLOW_WAYLAND") or ""
        ).strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        if (
            session_type == "wayland"
            and not allow_wayland
            and not env.contains("QT_QPA_PLATFORM")
        ):
            env.insert("QT_QPA_PLATFORM", "xcb")
        self._desktop_viewer_process.setProcessEnvironment(env)
        self._desktop_viewer_process.start(sys.executable, args)

        if not self._desktop_viewer_process.waitForStarted(3000):
            logger.error("Failed to start desktop viewer process")
            self._desktop_viewer_process = None
            self._desktop_viewer_url = ""
        else:
            logger.info(f"Desktop viewer launched: {title}")

    def _on_viewer_output(self) -> None:
        """Capture desktop viewer output for crash diagnostics."""
        proc = self._desktop_viewer_process
        if proc is None:
            return
        try:
            chunk = bytes(proc.readAllStandardOutput()).decode(
                "utf-8", errors="replace"
            )
        except Exception:
            return

        if not chunk:
            return

        lines = chunk.splitlines()
        if not lines:
            return

        self._desktop_viewer_output_lines.extend(lines)
        if len(self._desktop_viewer_output_lines) > 250:
            self._desktop_viewer_output_lines = self._desktop_viewer_output_lines[-250:]

    def _on_viewer_finished(
        self, exit_code: int, exit_status: QProcess.ExitStatus
    ) -> None:
        """Handle desktop viewer process exit."""
        try:
            if exit_status == QProcess.ExitStatus.CrashExit:
                logger.warning(f"Desktop viewer crashed (exit code {exit_code})")
                tail = "\n".join(self._desktop_viewer_output_lines[-40:])
                if tail.strip():
                    logger.warning(f"Desktop viewer output (tail):\n{tail}")
                QMessageBox.warning(
                    self,
                    "Desktop viewer crashed",
                    "The desktop viewer process crashed.\n\n"
                    f"Exit code: {exit_code}\n\n"
                    "A faulthandler log may be available at:\n"
                    "~/.midoriai/agents-runner/desktop-viewer-faulthandler.log\n\n"
                    "Tip: If this is a QtWebEngine/GPU crash, try setting:\n"
                    "AGENTS_RUNNER_DESKTOP_VIEWER_DISABLE_GPU=1\n"
                    "AGENTS_RUNNER_DESKTOP_VIEWER_DISABLE_VULKAN=1\n\n"
                    "If you're on Wayland, try forcing XWayland for the viewer:\n"
                    "AGENTS_RUNNER_DESKTOP_VIEWER_ALLOW_WAYLAND=0 (default)\n\n"
                    + (f"Viewer output (tail):\n{tail}" if tail.strip() else ""),
                )
                if self._desktop_viewer_url.startswith("http") and exit_code != 9:
                    QDesktopServices.openUrl(QUrl(self._desktop_viewer_url))
            elif exit_code != 0:
                logger.warning(f"Desktop viewer failed (exit code {exit_code})")
                if self._desktop_viewer_url.startswith("http"):
                    QDesktopServices.openUrl(QUrl(self._desktop_viewer_url))
            else:
                logger.info(f"Desktop viewer exited (exit code {exit_code})")
        except Exception as exc:
            logger.exception(f"Viewer exit handler failed: {exc}")

        self._desktop_viewer_url = ""

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

        # Show/hide Host Workdir based on workspace type
        is_cloned = task.workspace_type == WORKSPACE_CLONED
        self._workdir_label.setVisible(not is_cloned)
        self._workdir.setVisible(not is_cloned)
        if not is_cloned:
            self._workdir.setText(task.host_workdir)

        self._container.setText(task.container_id or "—")
        self._tabs.setCurrentIndex(self._task_tab_index)
        self._sync_desktop_button(task)
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
        self._sync_desktop_button(task)
        self._sync_artifacts(task)
        self._sync_container_actions(task)
        self._exit.setText("—" if task.exit_code is None else str(task.exit_code))
        self._apply_status(task)
        self._tick_uptime()
        self._sync_review_menu(task)

        # Notify artifacts tab of status changes
        if self._artifacts_tab_visible:
            self._artifacts_tab.on_task_status_changed(task)

    def _sync_desktop_button(self, task: Task) -> None:
        """Update Desktop button visibility and noVNC URL display."""
        url = str(task.novnc_url or "").strip()

        # Show button when desktop is ready
        should_show = bool(task.is_active() and task.headless_desktop_enabled and url)

        self._desktop_btn.setVisible(should_show)
        self._novnc_url.setText(url if url else "—")
        self._desktop_display.setText(str(task.desktop_display or ":1") if url else "—")

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
        should_show = artifact_info.file_count > 0 or has_encrypted

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
            f"font-size: 16px; font-weight: 750; color: {_rgba(color, 235)};"
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

    def cleanup(self) -> None:
        """Clean up resources, including external viewer process."""
        if self._desktop_viewer_process is not None:
            if self._desktop_viewer_process.state() == QProcess.ProcessState.Running:
                self._desktop_viewer_process.terminate()
                # Give it a moment to terminate gracefully
                if not self._desktop_viewer_process.waitForFinished(2000):
                    self._desktop_viewer_process.kill()
            self._desktop_viewer_process = None
