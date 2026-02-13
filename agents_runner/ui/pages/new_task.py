from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QEasingCurve
from PySide6.QtCore import QPropertyAnimation
from PySide6.QtCore import Qt
from PySide6.QtCore import QSize
from PySide6.QtCore import Signal
from PySide6.QtCore import QThread
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QComboBox
from PySide6.QtWidgets import QGridLayout
from PySide6.QtWidgets import QHBoxLayout
from PySide6.QtWidgets import QLabel
from PySide6.QtWidgets import QLineEdit
from PySide6.QtWidgets import QMenu
from PySide6.QtWidgets import QMessageBox
from PySide6.QtWidgets import QGraphicsOpacityEffect
from PySide6.QtWidgets import QSizePolicy
from PySide6.QtWidgets import QToolButton
from PySide6.QtWidgets import QVBoxLayout
from PySide6.QtWidgets import QWidget

from agents_runner.agent_display import get_agent_display_name
from agents_runner.environments import WORKSPACE_CLONED
from agents_runner.environments import WORKSPACE_MOUNTED
from agents_runner.environments import WORKSPACE_NONE
from agents_runner.prompt_sanitizer import sanitize_prompt
from agents_runner.prompts import load_prompt
from agents_runner.terminal_apps import detect_terminal_options
from agents_runner.ui.icons import mic_icon
from agents_runner.ui.graphics import _EnvironmentTintOverlay
from agents_runner.ui.lucide_icons import lucide_icon
from agents_runner.ui.utils import _apply_environment_combo_tint
from agents_runner.ui.utils import _stain_color
from agents_runner.ui.widgets import SpellTextEdit
from agents_runner.ui.widgets import StainedGlassButton
from agents_runner.stt.mic_recorder import FfmpegPulseRecorder
from agents_runner.stt.mic_recorder import MicRecorderError
from agents_runner.stt.mic_recorder import MicRecording
from agents_runner.ui.stt.qt_worker import SttWorker
from midori_ai_logger import MidoriAiLogger

logger = MidoriAiLogger(channel=None, name=__name__)


class NewTaskPage(QWidget):
    requested_run = Signal(str, str, str, str)
    requested_launch = Signal(str, str, str, str, str, str, str)
    back_requested = Signal()
    environment_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._env_stains: dict[str, str] = {}
        self._known_environment_ids: set[str] = set()
        self._active_env_id = ""
        self._env_workspace_types: dict[
            str, str
        ] = {}  # Track workspace types for environments
        self._env_template_injection: dict[str, bool] = {}
        self._env_desktop_enabled: dict[str, bool] = {}
        self._repo_controls_visible = False
        self._base_branch_host_active = False
        self._host_codex_dir = os.path.expanduser("~/.codex")
        self._workspace_ready = False
        self._workspace_error = ""
        self._spellcheck_enabled = True  # Default to enabled
        self._terminal_id = ""
        self._terminal_options: dict[str, str] = {}
        self._terminal_available = False
        self._stt_mode = "offline"
        self._mic_recording: MicRecording | None = None
        self._stt_thread: QThread | None = None
        self._stt_worker: SttWorker | None = None
        self._current_interactive_slot: Callable | None = None
        self._base_branch_visibility_animation: QPropertyAnimation | None = None
        self._base_branch_support_transition_pending = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._base_branch_controls = QWidget(self)
        base_branch_layout = QHBoxLayout(self._base_branch_controls)
        base_branch_layout.setContentsMargins(0, 0, 0, 0)
        base_branch_layout.setSpacing(6)
        self._base_branch_label = QLabel("Base branch")
        self._base_branch = QComboBox()
        self._base_branch.setFixedWidth(240)
        self._base_branch.setToolTip(
            "Base branch for the per-task branch (only shown for repo environments)."
        )
        self.set_repo_branches([])
        self._base_branch_controls.setVisible(False)
        base_branch_layout.addWidget(self._base_branch_label)
        base_branch_layout.addWidget(self._base_branch)
        base_branch_opacity = QGraphicsOpacityEffect(self._base_branch_controls)
        base_branch_opacity.setOpacity(0.0)
        self._base_branch_controls.setGraphicsEffect(base_branch_opacity)

        card = QWidget()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 16, 18, 16)
        card_layout.setSpacing(10)

        prompt_title = QLabel("Prompt")
        prompt_title.setStyleSheet("font-size: 14px; font-weight: 650;")

        # Separator between Prompt and agent chain
        self._prompt_separator = QLabel("::")
        self._prompt_separator.setStyleSheet(
            "color: rgba(237, 239, 245, 160); margin-left: 6px; margin-right: 4px;"
        )

        # Agent chain display - inline with prompt label
        self._agent_chain = QLabel("—")
        self._agent_chain.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._agent_chain.setStyleSheet("color: rgba(237, 239, 245, 200);")
        self._agent_chain.setToolTip(
            "Agents will be used in this order for new tasks in this environment."
        )

        # Prompt title row with agent chain
        prompt_title_row = QHBoxLayout()
        prompt_title_row.setSpacing(0)
        prompt_title_row.addWidget(prompt_title)
        prompt_title_row.addWidget(self._prompt_separator)
        prompt_title_row.addWidget(self._agent_chain)
        prompt_title_row.addStretch(1)

        self._prompt = SpellTextEdit(spellcheck_enabled=self._spellcheck_enabled)
        self._prompt.setPlaceholderText("Describe what you want the agent to do…")
        self._prompt.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._prompt.setTabChangesFocus(True)

        self._template_prompt_indicator = QLabel("(i)")
        self._template_prompt_indicator.setVisible(False)
        self._template_prompt_indicator.setToolTip(
            "Midori AI Agents Template detected, adding prompt to enforce usage."
        )
        self._template_prompt_indicator.setStyleSheet(
            "color: rgba(237, 239, 245, 160); margin: 8px;"
        )

        self._voice_btn = QToolButton()
        self._voice_btn.setIcon(mic_icon(size=18))
        self._voice_btn.setIconSize(QSize(18, 18))
        self._voice_btn.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self._voice_btn.setCheckable(True)
        self._voice_btn.setToolTip("Speech-to-text into the prompt editor.")
        self._voice_btn.setStyleSheet("margin: 8px;")
        self._voice_btn.toggled.connect(self._on_voice_toggled)

        prompt_container = QWidget()
        prompt_container_layout = QGridLayout(prompt_container)
        prompt_container_layout.setContentsMargins(0, 0, 0, 0)
        prompt_container_layout.setSpacing(0)
        prompt_container_layout.addWidget(self._prompt, 0, 0)
        prompt_container_layout.addWidget(
            self._template_prompt_indicator, 0, 0, Qt.AlignRight | Qt.AlignTop
        )
        prompt_container_layout.addWidget(
            self._voice_btn, 0, 0, Qt.AlignRight | Qt.AlignBottom
        )

        interactive_hint = QLabel(
            "Interactive: opens a terminal and runs the container with TTY/stdin for agent TUIs."
        )
        interactive_hint.setStyleSheet("color: rgba(237, 239, 245, 160);")

        self._terminal_display = QLabel("No terminals detected")
        self._terminal_display.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._terminal_display.setStyleSheet("color: rgba(237, 239, 245, 200);")

        self._command = QLineEdit("--sandbox danger-full-access")
        self._command.setPlaceholderText(
            "Args for the Agent CLI (e.g. --sandbox danger-full-access or --add-dir …), or a full container command (e.g. bash)"
        )
        # Hidden from UI but functionality preserved
        self._command.setVisible(False)

        interactive_grid = QGridLayout()
        interactive_grid.setHorizontalSpacing(10)
        interactive_grid.setVerticalSpacing(10)
        interactive_grid.setColumnStretch(1, 1)
        interactive_grid.setColumnStretch(3, 1)
        interactive_grid.addWidget(QLabel("Terminal"), 0, 0)
        interactive_grid.addWidget(self._terminal_display, 0, 1)

        # Workspace display for mounted folder environments (shown on terminal line)
        self._terminal_workspace_label = QLabel("Workspace")
        self._terminal_workspace = QLabel("—")
        self._terminal_workspace.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._terminal_workspace.setStyleSheet("color: rgba(237, 239, 245, 200);")
        interactive_grid.addWidget(self._terminal_workspace_label, 0, 2)
        interactive_grid.addWidget(self._terminal_workspace, 0, 3)
        # Initially hidden, shown for mounted folder environments
        self._terminal_workspace_label.setVisible(False)
        self._terminal_workspace.setVisible(False)

        cfg_grid = QGridLayout()
        cfg_grid.setHorizontalSpacing(10)
        cfg_grid.setVerticalSpacing(10)
        self._workspace = QLabel("—")
        self._workspace.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._workspace_hint = QLabel("")
        self._workspace_hint.setStyleSheet("color: rgba(237, 239, 245, 160);")
        self._workspace_hint.setWordWrap(True)

        self._workspace_label = QLabel("Workspace")
        cfg_grid.addWidget(self._workspace_label, 0, 0)
        cfg_grid.addWidget(self._workspace, 0, 1, 1, 2)
        cfg_grid.addWidget(self._workspace_hint, 1, 1, 1, 2)

        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        self._get_agent_help = StainedGlassButton("Get Agent Help")
        self._get_agent_help.set_glass_enabled(False)
        self._get_agent_help.clicked.connect(self._on_get_agent_help)
        self._get_agent_help.setEnabled(False)
        buttons.addWidget(self._get_agent_help)
        buttons.addStretch(1)
        self._run_interactive = StainedGlassButton("Run Interactive")
        self._run_interactive.set_glass_enabled(False)
        self._run_interactive.clicked.connect(self._on_launch)
        self._current_interactive_slot = self._on_launch

        self._run_interactive_menu = QMenu(self)
        self._run_interactive_no_desktop = self._run_interactive_menu.addAction(
            "Without desktop"
        )
        self._run_interactive_no_desktop.triggered.connect(
            self._on_launch_without_desktop
        )
        self._run_interactive.set_menu(None)

        self._run_agent = StainedGlassButton("Run Agent")
        self._run_agent.set_glass_enabled(False)
        self._run_agent.clicked.connect(self._on_run)
        self._run_interactive.setEnabled(False)
        self._run_agent.setEnabled(False)
        buttons.addWidget(self._run_interactive)
        buttons.addWidget(self._run_agent)

        card_layout.addLayout(prompt_title_row)
        card_layout.addWidget(prompt_container, 1)
        card_layout.addWidget(interactive_hint)
        card_layout.addLayout(interactive_grid)
        card_layout.addLayout(cfg_grid)
        card_layout.addLayout(buttons)

        layout.addWidget(card, 1)

        self._tint_overlay = _EnvironmentTintOverlay(self, alpha=13)
        self._tint_overlay.raise_()
        self._refresh_terminal_selection("")
        self._update_run_buttons()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._tint_overlay.setGeometry(self.rect())
        self._tint_overlay.raise_()

    def _confirm_auto_base_branch(self, env_id: str, base_branch: str) -> bool:
        """Show confirmation dialog for auto base branch in cloned repo environments.

        Args:
            env_id: The environment ID to check
            base_branch: The selected base branch (empty string or "auto" for auto mode)

        Returns:
            True if user confirmed or confirmation not needed, False if cancelled
        """
        # Only show confirmation for cloned environments with auto base branch
        workspace_type = self._env_workspace_types.get(env_id, WORKSPACE_NONE)
        is_auto_branch = not base_branch or base_branch.lower() == "auto"

        if not (workspace_type == WORKSPACE_CLONED and is_auto_branch):
            return True

        # Show confirmation dialog
        reply = QMessageBox.question(
            self,
            "Confirm Auto Base Branch",
            "You have selected 'Auto' as the base branch.\n\n"
            "Auto uses the repository's default branch as the base "
            "(commonly 'main' or 'master').\n\n"
            "If you need a specific base branch, select it from the dropdown.\n\n"
            "Do you want to proceed?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,  # Default to No for safety
        )

        return reply == QMessageBox.Yes

    def _update_run_buttons(self) -> None:
        has_terminal = bool(self._terminal_available and self._terminal_id)
        can_launch = bool(self._workspace_ready and has_terminal)
        self._run_agent.setEnabled(self._workspace_ready)
        self._run_interactive.setEnabled(can_launch)
        self._get_agent_help.setEnabled(can_launch)

    def _refresh_terminal_selection(self, terminal_id: str) -> None:
        options = detect_terminal_options()
        self._terminal_options = {opt.terminal_id: opt.label for opt in options}

        selected_id = str(terminal_id or "").strip()
        if selected_id and selected_id in self._terminal_options:
            self._terminal_id = selected_id
        elif self._terminal_id and self._terminal_id in self._terminal_options:
            pass
        elif options:
            self._terminal_id = str(options[0].terminal_id or "").strip()
        else:
            self._terminal_id = ""

        self._terminal_available = bool(
            self._terminal_id and self._terminal_id in self._terminal_options
        )

        if self._terminal_available:
            label = str(
                self._terminal_options.get(self._terminal_id, self._terminal_id) or ""
            )
            self._terminal_display.setText(label)
            self._terminal_display.setToolTip(label)
        elif self._terminal_id:
            unavailable = f"{self._terminal_id} (not detected)"
            self._terminal_display.setText(unavailable)
            self._terminal_display.setToolTip(unavailable)
        else:
            self._terminal_display.setText("No terminals detected")
            self._terminal_display.setToolTip("No terminals detected")

        if hasattr(self, "_run_interactive"):
            self._update_run_buttons()

    def _resolve_terminal_for_launch(self) -> str:
        self._refresh_terminal_selection(self._terminal_id)
        terminal_id = str(self._terminal_id or "").strip()
        if terminal_id and terminal_id in self._terminal_options:
            return terminal_id
        QMessageBox.warning(
            self,
            "No terminals found",
            "Could not detect an installed terminal emulator to launch.",
        )
        return ""

    def _on_run(self) -> None:
        prompt = (self._prompt.toPlainText() or "").strip()
        if not prompt:
            QMessageBox.warning(self, "Missing prompt", "Enter a prompt first.")
            return
        prompt = sanitize_prompt(prompt)

        if not self._workspace_ready:
            QMessageBox.warning(
                self,
                "Workspace not configured",
                self._workspace_error
                or "Pick an environment with a local folder or GitHub repo configured.",
            )
            return

        host_codex = os.path.expanduser(str(self._host_codex_dir or "").strip())

        env_id = self._active_env_id
        base_branch = str(self._base_branch.currentData() or "")

        # Confirm auto base branch for cloned repo environments
        if not self._confirm_auto_base_branch(env_id, base_branch):
            return

        self.requested_run.emit(prompt, host_codex, env_id, base_branch)

    def _on_get_agent_help(self) -> None:
        if not self._workspace_ready:
            QMessageBox.warning(
                self,
                "Workspace not configured",
                self._workspace_error
                or "Pick an environment with a local folder or GitHub repo configured.",
            )
            return

        user_question = sanitize_prompt((self._prompt.toPlainText() or "").strip())
        if not user_question:
            QMessageBox.warning(
                self,
                "Missing question",
                "Please type your question to get started with the help agent.",
            )
            return

        terminal_id = self._resolve_terminal_for_launch()
        if not terminal_id:
            return

        helpme_path = (
            Path(__file__).resolve().parent.parent.parent / "preflights" / "helpme.sh"
        )
        try:
            helpme_script = helpme_path.read_text(encoding="utf-8")
        except Exception:
            helpme_script = ""
        if not helpme_script.strip():
            QMessageBox.warning(
                self, "Missing preflight", f"Could not load {helpme_path}"
            )
            return

        host_codex = os.path.expanduser(str(self._host_codex_dir or "").strip())
        env_id = self._active_env_id
        base_branch = str(self._base_branch.currentData() or "")

        # Confirm auto base branch for cloned repo environments
        if not self._confirm_auto_base_branch(env_id, base_branch):
            return

        command = (self._command.text() or "").strip()

        prompt = load_prompt(
            "help_request_template",
            USER_QUESTION=user_question,
        )
        self.requested_launch.emit(
            prompt,
            command,
            host_codex,
            env_id,
            terminal_id,
            base_branch,
            helpme_script,
        )

    def _reconnect_interactive_button(self, new_slot) -> None:
        """Safely reconnect the interactive button click handler."""
        if (
            hasattr(self, "_current_interactive_slot")
            and self._current_interactive_slot
        ):
            try:
                self._run_interactive.clicked.disconnect(self._current_interactive_slot)
            except (RuntimeError, TypeError):
                pass  # Already disconnected
        self._run_interactive.clicked.connect(new_slot)
        self._current_interactive_slot = new_slot

    def _sync_interactive_options(self) -> None:
        env_id = self._active_env_id
        desktop_enabled = self._env_desktop_enabled.get(env_id, False)

        if env_id and desktop_enabled:
            # Desktop enabled: show dropdown with "Without desktop" option
            self._run_interactive.set_menu(self._run_interactive_menu)
            # Wire primary button to launch WITH desktop
            self._reconnect_interactive_button(self._on_launch_with_desktop)
        else:
            # Desktop not enabled: no dropdown
            self._run_interactive.set_menu(None)
            # Wire primary button to launch without desktop
            self._reconnect_interactive_button(self._on_launch)

    def _emit_interactive_launch(self, *, extra_preflight_script: str = "") -> None:
        prompt = sanitize_prompt((self._prompt.toPlainText() or "").strip())
        command = (self._command.text() or "").strip()

        if not self._workspace_ready:
            QMessageBox.warning(
                self,
                "Workspace not configured",
                self._workspace_error
                or "Pick an environment with a local folder or GitHub repo configured.",
            )
            return

        host_codex = os.path.expanduser(str(self._host_codex_dir or "").strip())

        terminal_id = self._resolve_terminal_for_launch()
        if not terminal_id:
            return

        env_id = self._active_env_id
        base_branch = str(self._base_branch.currentData() or "")

        # Confirm auto base branch for cloned repo environments
        if not self._confirm_auto_base_branch(env_id, base_branch):
            return

        self.requested_launch.emit(
            prompt,
            command,
            host_codex,
            env_id,
            terminal_id,
            base_branch,
            extra_preflight_script,
        )

    def _on_launch(self) -> None:
        self._emit_interactive_launch(extra_preflight_script="")

    def _on_launch_without_desktop(self) -> None:
        self._emit_interactive_launch(extra_preflight_script="")

    def _on_launch_with_desktop(self) -> None:
        desktop_path = (
            Path(__file__).resolve().parent.parent.parent
            / "preflights"
            / "headless_desktop_novnc.sh"
        )
        try:
            desktop_script = desktop_path.read_text(encoding="utf-8")
        except Exception:
            desktop_script = ""
        if not desktop_script.strip():
            QMessageBox.warning(
                self, "Missing preflight", f"Could not load {desktop_path}"
            )
            return
        self._emit_interactive_launch(extra_preflight_script=desktop_script)

    def _apply_environment_tints(self) -> None:
        env_id = self._active_env_id
        stain = (self._env_stains.get(env_id) or "").strip().lower() if env_id else ""
        if not stain:
            self._base_branch.setStyleSheet("")
            self._tint_overlay.set_tint_color(None)
            self._get_agent_help.set_tint_color(None)
            self._run_interactive.set_tint_color(None)
            self._run_agent.set_tint_color(None)
            return

        _apply_environment_combo_tint(self._base_branch, stain)
        tint = _stain_color(stain)
        self._tint_overlay.set_tint_color(tint)
        self._get_agent_help.set_tint_color(tint)
        self._run_interactive.set_tint_color(tint)
        self._run_agent.set_tint_color(tint)

    def set_environment_stains(self, stains: dict[str, str]) -> None:
        self._env_stains = {str(k): str(v) for k, v in (stains or {}).items()}
        self._apply_environment_tints()

    def set_environment_workspace_types(self, workspace_types: dict[str, str]) -> None:
        """Set the workspace types for environments.

        Args:
            workspace_types: Dictionary mapping environment IDs to their workspace type
                           (WORKSPACE_CLONED, WORKSPACE_MOUNTED, or WORKSPACE_NONE)
        """
        self._env_workspace_types = {
            str(k): str(v) for k, v in (workspace_types or {}).items()
        }
        self._update_workspace_visibility()
        self._sync_interactive_options()

    def set_environment_template_injection_status(
        self, statuses: dict[str, bool]
    ) -> None:
        self._env_template_injection = {
            str(k): bool(v) for k, v in (statuses or {}).items()
        }
        self._sync_template_prompt_indicator()

    def set_environment_desktop_enabled(self, desktop_enabled: dict[str, bool]) -> None:
        """Set desktop enablement status for environments.

        Args:
            desktop_enabled: Dictionary mapping environment IDs to desktop enablement status
        """
        self._env_desktop_enabled = {
            str(k): bool(v) for k, v in (desktop_enabled or {}).items()
        }
        self._sync_interactive_options()

    def _sync_template_prompt_indicator(self) -> None:
        env_id = self._active_env_id
        should_show = bool(self._env_template_injection.get(env_id, False))
        self._template_prompt_indicator.setVisible(should_show)

    def _update_workspace_visibility(self) -> None:
        """Update workspace line visibility based on workspace type."""
        env_id = self._active_env_id
        workspace_type = self._env_workspace_types.get(env_id, WORKSPACE_NONE)

        # Cloned environments: hide workspace line completely
        if workspace_type == WORKSPACE_CLONED:
            self._workspace_label.setVisible(False)
            self._workspace.setVisible(False)
            self._workspace_hint.setVisible(False)
            self._terminal_workspace_label.setVisible(False)
            self._terminal_workspace.setVisible(False)
        # Mounted environments: move workspace to terminal line
        elif workspace_type == WORKSPACE_MOUNTED:
            self._workspace_label.setVisible(False)
            self._workspace.setVisible(False)
            self._workspace_hint.setVisible(False)
            self._terminal_workspace_label.setVisible(True)
            self._terminal_workspace.setVisible(True)
        # Other environments: show in normal position
        else:
            self._workspace_label.setVisible(True)
            self._workspace.setVisible(True)
            # workspace_hint visibility is controlled by set_workspace_status
            self._terminal_workspace_label.setVisible(False)
            self._terminal_workspace.setVisible(False)

    def set_environments(self, envs: list[tuple[str, str]], active_id: str) -> None:
        ordered_ids: list[str] = []
        for env_id, _name in envs:
            parsed_env_id = str(env_id or "").strip()
            if parsed_env_id:
                ordered_ids.append(parsed_env_id)

        self._known_environment_ids = set(ordered_ids)
        desired = str(active_id or "").strip() or self._active_env_id
        if desired not in self._known_environment_ids and ordered_ids:
            desired = ordered_ids[0]
        if desired not in self._known_environment_ids:
            desired = ""

        self.set_environment_id(desired)

    def set_environment_id(self, env_id: str) -> None:
        desired = str(env_id or "").strip()
        if (
            desired
            and self._known_environment_ids
            and desired not in self._known_environment_ids
        ):
            desired = ""
        previous = self._active_env_id
        self._active_env_id = desired
        self._apply_environment_tints()
        self._sync_interactive_options()
        self._update_workspace_visibility()
        self._sync_template_prompt_indicator()
        if previous != self._active_env_id:
            self.environment_changed.emit(self._active_env_id)

    def set_defaults(self, host_codex: str) -> None:
        if host_codex:
            self._host_codex_dir = host_codex

    def set_spellcheck_enabled(self, enabled: bool) -> None:
        """Enable or disable spellcheck in the prompt editor."""
        self._spellcheck_enabled = enabled
        self._prompt.set_spellcheck_enabled(enabled)

    def set_stt_mode(self, mode: str) -> None:
        self._stt_mode = "offline"

    def set_workspace_status(self, *, path: str, ready: bool, message: str) -> None:
        self._workspace.setText(str(path or "—"))
        self._terminal_workspace.setText(str(path or "—"))  # Also update terminal line
        self._workspace_ready = bool(ready)
        self._workspace_error = str(message or "")

        hint = (
            ""
            if self._workspace_ready
            else (self._workspace_error or "Workspace not configured.")
        )
        self._workspace_hint.setText(hint)
        self._workspace_hint.setVisible(bool(hint))

        self._update_run_buttons()
        self._update_workspace_visibility()  # Update visibility after status change

    def _on_voice_toggled(self, enabled: bool) -> None:
        # Check if STT is already running
        if self._stt_thread is not None:
            logger.rprint(
                "[STT] Voice toggle rejected: thread still running", mode="debug"
            )
            self._voice_btn.blockSignals(True)
            try:
                self._voice_btn.setChecked(False)
            finally:
                self._voice_btn.blockSignals(False)
            return

        if enabled:
            logger.rprint("[STT] Starting voice recording", mode="normal")
            self._start_voice_recording()
            return
        logger.rprint("[STT] Stopping voice recording", mode="normal")
        self._stop_voice_recording_and_transcribe()

    def _start_voice_recording(self) -> None:
        if not FfmpegPulseRecorder.is_available():
            QMessageBox.warning(
                self,
                "Voice input unavailable",
                "Could not find `ffmpeg` in PATH (needed to record audio).",
            )
            self._voice_btn.setIcon(mic_icon(size=18))
            self._voice_btn.blockSignals(True)
            try:
                self._voice_btn.setChecked(False)
            finally:
                self._voice_btn.blockSignals(False)
            return

        try:
            recorder = FfmpegPulseRecorder()
            self._mic_recording = recorder.start()
        except MicRecorderError as exc:
            QMessageBox.warning(
                self, "Microphone error", str(exc) or "Could not start recording."
            )
            self._voice_btn.setIcon(mic_icon(size=18))
            self._voice_btn.blockSignals(True)
            try:
                self._voice_btn.setChecked(False)
            finally:
                self._voice_btn.blockSignals(False)
            return
        self._voice_btn.setIcon(lucide_icon("square"))
        self._voice_btn.setToolTip(
            "Stop recording and transcribe into the prompt editor."
        )

    def _stop_voice_recording_and_transcribe(self) -> None:
        recording = self._mic_recording
        self._mic_recording = None
        if recording is None:
            self._voice_btn.setIcon(mic_icon(size=18))
            self._voice_btn.setToolTip("Speech-to-text into the prompt editor.")
            return

        self._voice_btn.setEnabled(False)

        recorder = FfmpegPulseRecorder(output_dir=recording.output_path.parent)
        try:
            logger.rprint("[STT] Stopping recorder", mode="debug")
            audio_path = recorder.stop(recording)
            logger.rprint(f"[STT] Recorder stopped: {audio_path}", mode="debug")
        except MicRecorderError as exc:
            logger.rprint(f"[STT] Recorder error: {exc!r}", mode="error")
            QMessageBox.warning(
                self, "Microphone error", str(exc) or "Could not stop recording."
            )
            self._voice_btn.setEnabled(True)
            self._voice_btn.setIcon(mic_icon(size=18))
            self._voice_btn.setToolTip("Speech-to-text into the prompt editor.")
            return

        self._voice_btn.setIcon(lucide_icon("refresh-cw"))
        self._voice_btn.setToolTip("Transcribing speech-to-text…")

        logger.rprint("[STT] Creating worker and thread", mode="debug")
        worker = SttWorker(mode=self._stt_mode, audio_path=str(audio_path))
        thread = QThread(self)
        worker.moveToThread(thread)

        # Connect signals first, before starting
        thread.started.connect(worker.run)
        worker.done.connect(self._on_stt_done)
        worker.error.connect(self._on_stt_error)

        # Ensure thread.quit() is called on both done and error
        worker.done.connect(thread.quit)
        worker.error.connect(thread.quit)

        # Clean up worker after signals fire
        worker.done.connect(worker.deleteLater)
        worker.error.connect(worker.deleteLater)

        # Clean up thread when finished, ensure _on_stt_finished is called
        thread.finished.connect(self._on_stt_finished)
        thread.finished.connect(thread.deleteLater)

        self._stt_worker = worker
        self._stt_thread = thread
        logger.rprint("[STT] Starting thread", mode="debug")
        thread.start()
        logger.rprint(
            f"[STT] Thread started (is_running={thread.isRunning()})", mode="debug"
        )

    def _on_stt_done(self, text: str, audio_path: str) -> None:
        logger.rprint(
            f"[STT] Done signal received (text_length={len(text)})", mode="debug"
        )
        audio_path_p = Path(str(audio_path or ""))
        text = str(text or "").strip()
        if text:
            cursor = self._prompt.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            if self._prompt.toPlainText().strip():
                cursor.insertText("\n")
            cursor.insertText(text)
            self._prompt.setTextCursor(cursor)
        else:
            QMessageBox.information(
                self,
                "No speech detected",
                "Speech-to-text did not return any text.",
            )

        try:
            audio_path_p.unlink(missing_ok=True)
            logger.rprint(f"[STT] Audio file deleted: {audio_path}", mode="debug")
        except Exception as exc:
            logger.rprint(f"[STT] Failed to delete audio: {exc!r}", mode="warn")

    def _on_stt_error(self, message: str, audio_path: str) -> None:
        logger.rprint(f"[STT] Error signal received: {message}", mode="error")
        audio_path_p = Path(str(audio_path or ""))
        msg = str(message or "").strip() or "Speech-to-text failed."
        QMessageBox.warning(self, "Speech-to-text error", msg)
        try:
            audio_path_p.unlink(missing_ok=True)
            logger.rprint(
                f"[STT] Audio file deleted after error: {audio_path}", mode="debug"
            )
        except Exception as exc:
            logger.rprint(
                f"[STT] Failed to delete audio after error: {exc!r}", mode="warn"
            )

    def _on_stt_finished(self) -> None:
        logger.rprint(
            f"[STT] Finished signal received (thread={self._stt_thread})", mode="debug"
        )
        self._stt_thread = None
        self._stt_worker = None
        self._voice_btn.setEnabled(True)
        self._voice_btn.setIcon(mic_icon(size=18))
        self._voice_btn.setToolTip("Speech-to-text into the prompt editor.")
        logger.rprint(
            "[STT] Thread cleanup complete, ready for next recording", mode="debug"
        )

    def set_repo_controls_visible(self, visible: bool) -> None:
        desired = bool(visible)
        if desired != self._repo_controls_visible:
            self._base_branch_support_transition_pending = True
        self._repo_controls_visible = desired
        self._sync_base_branch_controls_visibility()

    def set_base_branch_host_active(self, active: bool) -> None:
        self._base_branch_host_active = bool(active)
        self._sync_base_branch_controls_visibility()

    def base_branch_controls_widget(self) -> QWidget:
        return self._base_branch_controls

    def _base_branch_opacity_effect(self) -> QGraphicsOpacityEffect:
        effect = self._base_branch_controls.graphicsEffect()
        if isinstance(effect, QGraphicsOpacityEffect):
            return effect
        effect = QGraphicsOpacityEffect(self._base_branch_controls)
        effect.setOpacity(1.0 if self._base_branch_controls.isVisible() else 0.0)
        self._base_branch_controls.setGraphicsEffect(effect)
        return effect

    def _set_base_branch_visibility_immediate(self, *, visible: bool) -> None:
        if self._base_branch_visibility_animation is not None:
            self._base_branch_visibility_animation.stop()
            self._base_branch_visibility_animation = None
        effect = self._base_branch_opacity_effect()
        effect.setOpacity(1.0 if visible else 0.0)
        self._base_branch_controls.setVisible(visible)

    def _animate_base_branch_visibility(self, *, show: bool) -> None:
        if show and self._base_branch_controls.isVisible():
            return
        if not show and not self._base_branch_controls.isVisible():
            return

        if self._base_branch_visibility_animation is not None:
            self._base_branch_visibility_animation.stop()
            self._base_branch_visibility_animation = None

        effect = self._base_branch_opacity_effect()
        if show:
            start_opacity = 0.0
            end_opacity = 1.0
            self._base_branch_controls.setVisible(True)
        else:
            start_opacity = float(effect.opacity())
            if start_opacity < 0.01:
                start_opacity = 1.0
            end_opacity = 0.0

        effect.setOpacity(start_opacity)

        animation = QPropertyAnimation(effect, b"opacity", self)
        animation.setDuration(220)
        animation.setStartValue(start_opacity)
        animation.setEndValue(end_opacity)
        animation.setEasingCurve(QEasingCurve.Type.InOutCubic)

        def _on_finished() -> None:
            self._base_branch_visibility_animation = None
            if show:
                effect.setOpacity(1.0)
                return
            self._base_branch_controls.setVisible(False)
            effect.setOpacity(0.0)

        animation.finished.connect(_on_finished)
        animation.start()
        self._base_branch_visibility_animation = animation

    def _sync_base_branch_controls_visibility(self) -> None:
        should_show = bool(
            self._repo_controls_visible and self._base_branch_host_active
        )
        support_transition = bool(self._base_branch_support_transition_pending)
        self._base_branch_support_transition_pending = False

        if support_transition and self._base_branch_host_active:
            self._animate_base_branch_visibility(show=should_show)
            return
        self._set_base_branch_visibility_immediate(visible=should_show)

    def set_repo_branches(
        self, branches: list[str], selected: str | None = None
    ) -> None:
        wanted = str(selected or "").strip()
        self._base_branch.blockSignals(True)
        try:
            self._base_branch.clear()
            self._base_branch.addItem("Auto", "")
            for name in branches or []:
                b = str(name or "").strip()
                if not b:
                    continue
                self._base_branch.addItem(b, b)
            if wanted:
                idx = self._base_branch.findData(wanted)
                if idx >= 0:
                    self._base_branch.setCurrentIndex(idx)
                    return
            self._base_branch.setCurrentIndex(0)
        finally:
            self._base_branch.blockSignals(False)

    def set_interactive_defaults(self, terminal_id: str, command: str) -> None:
        if command:
            self._command.setText(command)
        self._refresh_terminal_selection(str(terminal_id or ""))

    @staticmethod
    def _friendly_agent_label(label: str) -> str:
        raw = str(label or "").strip()
        if not raw:
            return ""

        lower = raw.lower()
        if lower.startswith("fallback:"):
            raw = raw[len("fallback:") :].strip()

        cli = raw
        suffix = ""
        split_idx = raw.find(" (")
        if split_idx > 0 and raw.endswith(")"):
            cli = raw[:split_idx].strip()
            suffix = raw[split_idx:]

        friendly = str(get_agent_display_name(cli) or cli).strip()
        return f"{friendly}{suffix}"

    def _format_agent_info_text(self, agent: str, next_agent: str = "") -> str:
        current = self._friendly_agent_label(agent)
        upcoming = self._friendly_agent_label(next_agent)
        if upcoming and current and upcoming == current:
            upcoming = ""
        if current and upcoming:
            return f"{current} | {upcoming}"
        if current:
            return current
        return upcoming

    def set_agent_info(self, agent: str, next_agent: str = "") -> None:
        """Update inline and tooltip labels using the selected and next agent."""
        display_text = self._format_agent_info_text(agent, next_agent)

        if display_text:
            self._agent_chain.setText(display_text)
            self._agent_chain.setVisible(True)
            self._prompt_separator.setVisible(True)
        else:
            self._agent_chain.setText("")
            self._agent_chain.setVisible(False)
            self._prompt_separator.setVisible(False)

        self._agent_chain.setToolTip(display_text)
        self._run_interactive.setToolTip(display_text)
        self._run_agent.setToolTip(display_text)

    def reset_for_new_run(self) -> None:
        self._prompt.setPlainText("")
        self._prompt.setFocus(Qt.OtherFocusReason)

    def append_prompt_text(self, text: str) -> None:
        addition = str(text or "").strip()
        if not addition:
            return

        current = str(self._prompt.toPlainText() or "").rstrip()
        if current:
            combined = f"{current}\n\n{addition}"
        else:
            combined = addition
        self._prompt.setPlainText(combined)
        cursor = self._prompt.textCursor()
        cursor.movePosition(QTextCursor.End)
        self._prompt.setTextCursor(cursor)
        self._prompt.setFocus(Qt.OtherFocusReason)

    def focus_prompt(self) -> None:
        self._prompt.setFocus(Qt.OtherFocusReason)
