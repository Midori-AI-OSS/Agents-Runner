from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, cast

from PySide6.QtCore import QEasingCurve
from PySide6.QtCore import QParallelAnimationGroup
from PySide6.QtCore import QPoint
from PySide6.QtCore import QPropertyAnimation
from PySide6.QtCore import Qt
from PySide6.QtCore import QSize
from PySide6.QtCore import Signal
from PySide6.QtCore import QTimer
from PySide6.QtCore import QThread
from PySide6.QtGui import QColor
from PySide6.QtGui import QResizeEvent
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

from agents_runner.agent_configs.model import AgentConfig
from agents_runner.agent_configs.storage import load_agent_configs
from agents_runner.agent_configs.storage import resolve_agent_config
from agents_runner.agent_cli import available_agents
from agents_runner.agent_cli import normalize_agent
from agents_runner.agent_display import get_agent_display_name
from agents_runner.environments import WORKSPACE_CLONED
from agents_runner.environments import WORKSPACE_MOUNTED
from agents_runner.environments import WORKSPACE_NONE
from agents_runner.environments.model import AgentInstance
from agents_runner.prompts.magic_prompts import load_magic_prompts
from agents_runner.persistence import default_state_path
from agents_runner.prompt_sanitizer import sanitize_prompt
from agents_runner.terminal_apps import detect_terminal_options
from agents_runner.ui.icons import mic_icon
from agents_runner.ui.graphics import EnvironmentTintOverlay
from agents_runner.ui.lucide_icons import lucide_icon
from agents_runner.ui.utils import apply_environment_combo_tint
from agents_runner.ui.utils import stain_color
from agents_runner.ui.widgets import SpellTextEdit
from agents_runner.ui.widgets import StainedGlassButton
from agents_runner.stt.mic_recorder import FfmpegPulseRecorder
from agents_runner.stt.mic_recorder import MicRecorderError
from agents_runner.stt.mic_recorder import MicRecording
from agents_runner.ui.stt.qt_worker import SttWorker
from midori_ai_logger import MidoriAiLogger

logger = MidoriAiLogger(channel=None, name=__name__)


class NewTaskPage(QWidget):
    _BASE_BRANCH_LOADING_SENTINEL = "__loading__"
    _BASE_BRANCH_LOADING_DELAY_MS = 250

    requested_run = Signal(str, str, str, str, object, object)
    requested_launch = Signal(str, str, str, str, str, str, object, str)
    back_requested = Signal()
    environment_changed = Signal(str)
    base_branch_changed = Signal(str, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._env_stains: dict[str, str] = {}
        self._known_environment_ids: set[str] = set()
        self._active_env_id = ""
        self._env_workspace_types: dict[str, str] = {}  # Track workspace types for environments
        self._env_template_injection: dict[str, bool] = {}
        self._env_desktop_enabled: dict[str, bool] = {}
        self._env_agents: dict[str, list[AgentInstance]] = {}
        self._repo_controls_visible = False
        self._base_branch_host_active = False
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
        self._current_interactive_slot: Callable[..., Any] | None = None
        self._base_branch_visibility_animation: QParallelAnimationGroup | None = None
        self._base_branch_loading = False
        self._base_branch_loading_requested = False
        self._base_branch_loading_snapshot: list[tuple[str, str]] = []
        self._base_branch_loading_selected = ""
        self._base_branch_loading_animation: QPropertyAnimation | None = None
        self._base_branch_loading_delay_timer = QTimer(self)
        self._base_branch_loading_delay_timer.setSingleShot(True)
        self._base_branch_loading_delay_timer.setInterval(self._BASE_BRANCH_LOADING_DELAY_MS)
        self._base_branch_loading_delay_timer.timeout.connect(self._activate_base_branch_loading_visual)
        self._pending_repo_branches_update: tuple[list[str], str | None, bool] | None = None
        self._pending_repo_branches_timer = QTimer(self)
        self._pending_repo_branches_timer.setSingleShot(True)
        self._pending_repo_branches_timer.setInterval(120)
        self._pending_repo_branches_timer.timeout.connect(self._apply_pending_repo_branches_update)
        self._pending_pr_context: dict[str, object] | None = None
        self._agent_override: dict[str, str] | None = None
        self._base_agent_info: tuple[str, str] = ("", "")

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
        self._base_branch.setToolTip("Base branch for the per-task branch (only shown for repo environments).")
        self.set_repo_branches([])
        self._base_branch.currentIndexChanged.connect(self._on_base_branch_changed)
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
        self._prompt_separator.setStyleSheet("color: rgba(237, 239, 245, 160); margin-left: 6px; margin-right: 4px;")

        # Agent chain display - inline with prompt label
        self._agent_chain = QLabel("—")
        self._agent_chain.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._agent_chain.setStyleSheet("color: rgba(237, 239, 245, 200);")
        self._agent_chain.setToolTip("Agents will be used in this order for new tasks in this environment.")

        # Prompt title row with agent chain
        prompt_title_row = QHBoxLayout()
        prompt_title_row.setSpacing(0)
        prompt_title_row.addWidget(prompt_title)
        prompt_title_row.addWidget(self._prompt_separator)
        prompt_title_row.addWidget(self._agent_chain)
        prompt_title_row.addStretch(1)

        self._prompt = SpellTextEdit(spellcheck_enabled=self._spellcheck_enabled)
        self._prompt.setPlaceholderText("Describe what you want the agent to do…")
        self._prompt.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._prompt.setTabChangesFocus(True)

        self._template_prompt_indicator = QLabel("(i)")
        self._template_prompt_indicator.setVisible(False)
        self._template_prompt_indicator.setToolTip(
            "Midori AI Agents Template detected, adding prompt to enforce usage."
        )
        self._template_prompt_indicator.setStyleSheet("color: rgba(237, 239, 245, 160); margin: 8px;")

        self._voice_btn = QToolButton()
        self._voice_btn.setIcon(mic_icon(size=18))
        self._voice_btn.setIconSize(QSize(18, 18))
        self._voice_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
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
            self._template_prompt_indicator,
            0,
            0,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop,
        )
        prompt_container_layout.addWidget(
            self._voice_btn,
            0,
            0,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom,
        )

        self._terminal_display = QLabel("No terminals detected")
        self._terminal_display.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._terminal_display.setStyleSheet("color: rgba(237, 239, 245, 200);")

        self._command = QLineEdit("--sandbox danger-full-access")
        self._command.setPlaceholderText(
            "Args for the Agent CLI (e.g. --sandbox danger-full-access or --add-dir "
            "…), or a full container command (e.g. bash)"
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
        self._terminal_workspace.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
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
        self._workspace.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._workspace_hint = QLabel("")
        self._workspace_hint.setStyleSheet("color: rgba(237, 239, 245, 160);")
        self._workspace_hint.setWordWrap(True)

        self._workspace_label = QLabel("Workspace")
        cfg_grid.addWidget(self._workspace_label, 0, 0)
        cfg_grid.addWidget(self._workspace, 0, 1, 1, 2)
        cfg_grid.addWidget(self._workspace_hint, 1, 1, 1, 2)

        buttons = QHBoxLayout()
        buttons.setSpacing(10)

        self._magic_prompts_btn = StainedGlassButton("Magic Prompts")
        self._magic_prompts_btn.set_glass_enabled(False)
        self._magic_prompts_btn.set_texture_enabled(False)
        self._magic_prompts_btn.clicked.connect(self._on_magic_prompts_clicked)
        buttons.addWidget(self._magic_prompts_btn)

        buttons.addStretch(1)
        self._run_interactive = StainedGlassButton("Run Interactive")
        self._run_interactive.set_glass_enabled(False)
        self._run_interactive.set_texture_enabled(False)
        self._run_interactive.clicked.connect(self._on_launch)
        self._current_interactive_slot = self._on_launch

        self._run_interactive_menu = QMenu(self)
        self._run_interactive_no_desktop = self._run_interactive_menu.addAction("Without desktop")
        self._run_interactive_no_desktop.triggered.connect(self._on_launch_without_desktop)
        self._run_interactive_to_shell = self._run_interactive_menu.addAction("To Shell")
        self._run_interactive_to_shell.triggered.connect(self._on_launch_to_shell)
        self._run_interactive.set_menu(None)

        self._run_agent = StainedGlassButton("Run Agent")
        self._run_agent.set_glass_enabled(False)
        self._run_agent.set_texture_enabled(False)
        self._run_agent.clicked.connect(self._on_run)
        self._run_interactive.setEnabled(False)
        self._run_agent.setEnabled(False)
        self._override_menu = QMenu(self)
        self._override_menu.aboutToShow.connect(self._rebuild_override_menu)
        self._run_interactive.set_context_menu(self._override_menu)
        self._run_agent.set_context_menu(self._override_menu)
        buttons.addWidget(self._run_interactive)
        buttons.addWidget(self._run_agent)

        card_layout.addLayout(prompt_title_row)
        card_layout.addWidget(prompt_container, 1)

        card_layout.addLayout(interactive_grid)
        card_layout.addLayout(cfg_grid)
        card_layout.addLayout(buttons)

        layout.addWidget(card, 1)

        self._tint_overlay = EnvironmentTintOverlay(self, alpha=13)
        self._tint_overlay.raise_()
        self._refresh_terminal_selection("")
        self._update_run_buttons()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._tint_overlay.setGeometry(self.rect())
        self._tint_overlay.raise_()
        self._raise_override_buttons()

    def _raise_override_buttons(self) -> None:
        if not self._agent_override:
            return
        self._run_interactive.raise_()
        self._run_agent.raise_()

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
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,  # Default to No for safety
        )

        return reply == QMessageBox.StandardButton.Yes  # pyright: ignore[reportUnknownVariableType]

    def _update_run_buttons(self) -> None:
        has_terminal = bool(self._terminal_available and self._terminal_id)
        can_launch = bool(self._workspace_ready and has_terminal)
        self._run_agent.setEnabled(self._workspace_ready)
        self._run_interactive.setEnabled(can_launch)

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

        self._terminal_available = bool(self._terminal_id and self._terminal_id in self._terminal_options)

        if self._terminal_available:
            label = str(self._terminal_options.get(self._terminal_id, self._terminal_id) or "")
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
                self._workspace_error or "Pick an environment with a local folder or GitHub repo configured.",
            )
            return

        env_id = self._active_env_id
        base_branch = str(self._base_branch.currentData() or "")

        # Confirm auto base branch for cloned repo environments
        if not self._confirm_auto_base_branch(env_id, base_branch):
            return

        pr_context = self._pending_pr_context
        agent_override = dict(self._agent_override) if self._agent_override else None
        self.requested_run.emit(
            prompt,
            "",
            env_id,
            base_branch,
            pr_context,
            agent_override,
        )
        self._pending_pr_context = None
        self._clear_agent_override()

    def _reconnect_interactive_button(self, new_slot: object) -> None:
        """Safely reconnect the interactive button click handler."""
        if hasattr(self, "_current_interactive_slot") and self._current_interactive_slot:
            try:
                self._run_interactive.clicked.disconnect(self._current_interactive_slot)
            except (RuntimeError, TypeError):
                pass  # Already disconnected
        self._run_interactive.clicked.connect(new_slot)
        self._current_interactive_slot = cast(Callable[..., Any], new_slot)

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
                self._workspace_error or "Pick an environment with a local folder or GitHub repo configured.",
            )
            return

        terminal_id = self._resolve_terminal_for_launch()
        if not terminal_id:
            return

        env_id = self._active_env_id
        base_branch = str(self._base_branch.currentData() or "")

        # Confirm auto base branch for cloned repo environments
        if not self._confirm_auto_base_branch(env_id, base_branch):
            return

        agent_override = dict(self._agent_override) if self._agent_override else None
        self.requested_launch.emit(
            prompt,
            command,
            "",
            env_id,
            terminal_id,
            base_branch,
            agent_override,
            extra_preflight_script,
        )
        self._clear_agent_override()

    def _on_launch(self) -> None:
        self._emit_interactive_launch(extra_preflight_script="")

    def _on_launch_without_desktop(self) -> None:
        self._emit_interactive_launch(extra_preflight_script="")

    def _on_launch_with_desktop(self) -> None:
        desktop_path = Path(__file__).resolve().parent.parent.parent / "preflights" / "headless_desktop_novnc.sh"
        try:
            desktop_script = desktop_path.read_text(encoding="utf-8")
        except Exception:
            desktop_script = ""
        if not desktop_script.strip():
            QMessageBox.warning(self, "Missing preflight", f"Could not load {desktop_path}")
            return
        self._emit_interactive_launch(extra_preflight_script=desktop_script)

    def _get_shell_from_settings(self) -> str:
        """Get the preferred shell from settings (key: 'shell', default: 'bash')."""
        settings = getattr(self.parent(), "_settings_data", None) or {}  # pyright: ignore[reportUnknownVariableType]
        shell = str(settings.get("shell") or "bash").strip().lower()
        valid_shells = {"bash", "sh", "zsh", "fish", "tmux"}
        if shell not in valid_shells:
            return "bash"
        return shell

    def _on_launch_to_shell(self) -> None:
        shell = self._get_shell_from_settings()
        self._agent_override = {"mode": "shell", "shell": shell}

        env_id = self._active_env_id
        if env_id and self._env_desktop_enabled.get(env_id, False):
            desktop_path = Path(__file__).resolve().parent.parent.parent / "preflights" / "headless_desktop_novnc.sh"
            try:
                desktop_script = desktop_path.read_text(encoding="utf-8")
                if desktop_script.strip():
                    self._emit_interactive_launch(extra_preflight_script=desktop_script)
                    return
            except Exception:
                pass
            QMessageBox.warning(
                self,
                "Desktop Unavailable",
                "Could not load desktop preflight. Launching shell only.",
            )

        self._emit_interactive_launch()

    @staticmethod
    def _override_tint_color() -> QColor:
        return QColor(248, 58, 58)

    def _apply_run_button_tints(self, base_tint: QColor | None) -> None:
        override_tint = self._override_tint_color()

        agent_override_active = bool(self._agent_override)
        self._run_interactive.set_glass_enabled(agent_override_active)
        self._run_agent.set_glass_enabled(agent_override_active)
        self._run_interactive.set_tint_color(override_tint if agent_override_active else base_tint)
        self._run_agent.set_tint_color(override_tint if agent_override_active else base_tint)

        if agent_override_active:
            self._raise_override_buttons()
        self._tint_overlay.raise_()

    def _apply_environment_tints(self) -> None:
        env_id = self._active_env_id
        stain = (self._env_stains.get(env_id) or "").strip().lower() if env_id else ""
        base_tint: QColor | None = None
        if not stain:
            self._base_branch.setStyleSheet("")
            self._tint_overlay.set_tint_color(None)
        else:
            apply_environment_combo_tint(self._base_branch, stain)
            base_tint = stain_color(stain)
            self._tint_overlay.set_tint_color(base_tint)
        self._apply_run_button_tints(base_tint)

    def set_environment_stains(self, stains: dict[str, str]) -> None:
        self._env_stains = {str(k): str(v) for k, v in (stains or {}).items()}
        self._apply_environment_tints()

    def set_environment_agents(self, env_agents: dict[str, list[AgentInstance]]) -> None:
        cleaned: dict[str, list[AgentInstance]] = {}
        for env_id, agents in (env_agents or {}).items():
            cleaned[str(env_id)] = list(agents or [])
        self._env_agents = cleaned
        self._clear_override_if_invalid()

    def set_environment_workspace_types(self, workspace_types: dict[str, str]) -> None:
        """Set the workspace types for environments.

        Args:
            workspace_types: Dictionary mapping environment IDs to their workspace type
                           (WORKSPACE_CLONED, WORKSPACE_MOUNTED, or WORKSPACE_NONE)
        """
        self._env_workspace_types = {str(k): str(v) for k, v in (workspace_types or {}).items()}
        self._update_workspace_visibility()
        self._sync_interactive_options()

    def set_environment_template_injection_status(self, statuses: dict[str, bool]) -> None:
        self._env_template_injection = {str(k): bool(v) for k, v in (statuses or {}).items()}
        self._sync_template_prompt_indicator()

    def set_environment_desktop_enabled(self, desktop_enabled: dict[str, bool]) -> None:
        """Set desktop enablement status for environments.

        Args:
            desktop_enabled: Dictionary mapping environment IDs to desktop enablement status
        """
        self._env_desktop_enabled = {str(k): bool(v) for k, v in (desktop_enabled or {}).items()}
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
        if desired and self._known_environment_ids and desired not in self._known_environment_ids:
            desired = ""
        previous = self._active_env_id
        self._active_env_id = desired
        self._apply_environment_tints()
        self._sync_interactive_options()
        self._update_workspace_visibility()
        self._sync_template_prompt_indicator()
        self._clear_override_if_invalid()
        if previous != self._active_env_id:
            self.environment_changed.emit(self._active_env_id)

    def _on_base_branch_changed(self, _index: int) -> None:
        env_id = str(self._active_env_id or "").strip()
        if not env_id:
            return
        selected = str(self._base_branch.currentData() or "").strip()
        if selected == self._BASE_BRANCH_LOADING_SENTINEL:
            return
        self.base_branch_changed.emit(env_id, selected)

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

        hint = "" if self._workspace_ready else (self._workspace_error or "Workspace not configured.")
        self._workspace_hint.setText(hint)
        self._workspace_hint.setVisible(bool(hint))

        self._update_run_buttons()
        self._update_workspace_visibility()  # Update visibility after status change

    def _on_voice_toggled(self, enabled: bool) -> None:
        # Check if STT is already running
        if self._stt_thread is not None:
            logger.rprint("[STT] Voice toggle rejected: thread still running", mode="debug")
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
            QMessageBox.warning(self, "Microphone error", str(exc) or "Could not start recording.")
            self._voice_btn.setIcon(mic_icon(size=18))
            self._voice_btn.blockSignals(True)
            try:
                self._voice_btn.setChecked(False)
            finally:
                self._voice_btn.blockSignals(False)
            return
        self._voice_btn.setIcon(lucide_icon("square"))
        self._voice_btn.setToolTip("Stop recording and transcribe into the prompt editor.")

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
            QMessageBox.warning(self, "Microphone error", str(exc) or "Could not stop recording.")
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
        logger.rprint(f"[STT] Thread started (is_running={thread.isRunning()})", mode="debug")

    def _on_stt_done(self, text: str, audio_path: str) -> None:
        logger.rprint(f"[STT] Done signal received (text_length={len(text)})", mode="debug")
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
            logger.rprint(f"[STT] Audio file deleted after error: {audio_path}", mode="debug")
        except Exception as exc:
            logger.rprint(f"[STT] Failed to delete audio after error: {exc!r}", mode="warn")

    def _on_stt_finished(self) -> None:
        logger.rprint(f"[STT] Finished signal received (thread={self._stt_thread})", mode="debug")
        self._stt_thread = None
        self._stt_worker = None
        self._voice_btn.setEnabled(True)
        self._voice_btn.setIcon(mic_icon(size=18))
        self._voice_btn.setToolTip("Speech-to-text into the prompt editor.")
        logger.rprint("[STT] Thread cleanup complete, ready for next recording", mode="debug")

    def set_repo_controls_visible(self, visible: bool) -> None:
        desired = bool(visible)
        changed = desired != self._repo_controls_visible
        self._repo_controls_visible = desired
        self._sync_base_branch_controls_visibility(animate_transition=bool(changed and self._base_branch_host_active))

    def set_base_branch_host_active(self, active: bool) -> None:
        self._base_branch_host_active = bool(active)
        self._sync_base_branch_controls_visibility(animate_transition=False)

    def base_branch_controls_widget(self) -> QWidget:
        return self._base_branch_controls

    def is_base_branch_controls_visible(self) -> bool:
        return bool(self._base_branch_controls.isVisible())

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
        if visible:
            target_width = max(1, int(self._base_branch_controls.sizeHint().width()))
            self._base_branch_controls.setMaximumWidth(target_width)
            self._base_branch_controls.setVisible(True)
            effect.setOpacity(1.0)
            return
        self._base_branch_controls.setMaximumWidth(0)
        self._base_branch_controls.setVisible(False)
        effect.setOpacity(0.0)

    def _animate_base_branch_visibility(self, *, show: bool) -> None:
        if show and self._base_branch_controls.isVisible():
            return
        if not show and not self._base_branch_controls.isVisible():
            return

        if self._base_branch_visibility_animation is not None:
            self._base_branch_visibility_animation.stop()
            self._base_branch_visibility_animation = None

        effect = self._base_branch_opacity_effect()
        target_width = max(1, int(self._base_branch_controls.sizeHint().width()))
        if show:
            start_width = 0
            end_width = target_width
            start_opacity = 0.0
            end_opacity = 1.0
            self._base_branch_controls.setVisible(True)
            self._base_branch_controls.setMaximumWidth(start_width)
        else:
            start_width = int(self._base_branch_controls.maximumWidth() or target_width or 0)
            if start_width <= 0:
                start_width = target_width
            end_width = 0
            start_opacity = float(effect.opacity())
            if start_opacity < 0.01:
                start_opacity = 1.0
            end_opacity = 0.0
            self._base_branch_controls.setMaximumWidth(start_width)

        effect.setOpacity(start_opacity)

        width_animation = QPropertyAnimation(self._base_branch_controls, b"maximumWidth", self)
        width_animation.setDuration(220)
        width_animation.setStartValue(start_width)
        width_animation.setEndValue(end_width)
        width_animation.setEasingCurve(QEasingCurve.Type.InOutCubic)

        opacity_animation = QPropertyAnimation(effect, b"opacity", self)
        opacity_animation.setDuration(220)
        opacity_animation.setStartValue(start_opacity)
        opacity_animation.setEndValue(end_opacity)
        opacity_animation.setEasingCurve(QEasingCurve.Type.InOutCubic)

        animation = QParallelAnimationGroup(self)
        animation.addAnimation(width_animation)
        animation.addAnimation(opacity_animation)

        def _on_finished() -> None:
            self._base_branch_visibility_animation = None
            if show:
                effect.setOpacity(1.0)
                self._base_branch_controls.setMaximumWidth(target_width)
                return
            self._base_branch_controls.setMaximumWidth(0)
            self._base_branch_controls.setVisible(False)
            effect.setOpacity(0.0)

        animation.finished.connect(_on_finished)
        animation.start()
        self._base_branch_visibility_animation = animation

    def _sync_base_branch_controls_visibility(self, *, animate_transition: bool) -> None:
        should_show = bool(self._repo_controls_visible and self._base_branch_host_active)
        if animate_transition:
            self._animate_base_branch_visibility(show=should_show)
            return
        self._set_base_branch_visibility_immediate(visible=should_show)

    def _base_branch_loading_effect(self) -> QGraphicsOpacityEffect:
        effect = self._base_branch.graphicsEffect()
        if isinstance(effect, QGraphicsOpacityEffect):
            return effect
        effect = QGraphicsOpacityEffect(self._base_branch)
        effect.setOpacity(1.0)
        self._base_branch.setGraphicsEffect(effect)
        return effect

    def _start_base_branch_loading_animation(self) -> None:
        effect = self._base_branch_loading_effect()
        if self._base_branch_loading_animation is None:
            animation = QPropertyAnimation(effect, b"opacity", self)
            animation.setDuration(880)
            animation.setKeyValueAt(0.0, 1.0)
            animation.setKeyValueAt(0.5, 0.78)
            animation.setKeyValueAt(1.0, 1.0)
            animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
            animation.setLoopCount(-1)
            self._base_branch_loading_animation = animation
        else:
            self._base_branch_loading_animation.stop()
        effect.setOpacity(1.0)
        self._base_branch_loading_animation.start()

    def _stop_base_branch_loading_animation(self) -> None:
        if self._base_branch_loading_animation is not None:
            self._base_branch_loading_animation.stop()
        effect = self._base_branch.graphicsEffect()
        if isinstance(effect, QGraphicsOpacityEffect):
            effect.setOpacity(1.0)

    def _capture_base_branch_items(self) -> list[tuple[str, str]]:
        entries: list[tuple[str, str]] = []
        for index in range(int(self._base_branch.count())):
            text = str(self._base_branch.itemText(index) or "")
            data = str(self._base_branch.itemData(index) or "")
            entries.append((text, data))
        return entries

    def _restore_base_branch_loading_snapshot(self) -> None:
        snapshot = list(self._base_branch_loading_snapshot)
        selected = str(self._base_branch_loading_selected or "").strip()
        self._base_branch.blockSignals(True)
        try:
            self._base_branch.clear()
            if snapshot:
                for text, data in snapshot:
                    label = str(text or "").strip()
                    value = str(data or "").strip()
                    if not label and not value:
                        label = "Auto"
                    elif not label:
                        label = value
                    self._base_branch.addItem(label, value)
            else:
                self._base_branch.addItem("Auto", "")

            idx = -1
            if selected:
                idx = self._base_branch.findData(selected)
            if idx < 0:
                idx = self._base_branch.findData("")
            if idx < 0 and self._base_branch.count() > 0:
                idx = 0
            if idx >= 0:
                self._base_branch.setCurrentIndex(idx)
        finally:
            self._base_branch.blockSignals(False)

    def _selected_base_branch_for_preserve(self) -> str:
        current = str(self._base_branch.currentData() or "").strip()
        if current and current != self._BASE_BRANCH_LOADING_SENTINEL:
            return current
        loading_selected = str(self._base_branch_loading_selected or "").strip()
        return loading_selected

    def _activate_base_branch_loading_visual(self) -> None:
        if not self._base_branch_loading_requested or self._base_branch_loading:
            return
        if self._base_branch.view().isVisible():
            self._base_branch_loading_delay_timer.start()
            return
        self._pending_repo_branches_update = None
        self._pending_repo_branches_timer.stop()
        self._base_branch_loading = True
        self._base_branch_loading_snapshot = self._capture_base_branch_items()
        self._base_branch_loading_selected = self._selected_base_branch_for_preserve()
        self._base_branch.blockSignals(True)
        try:
            self._base_branch.clear()
            self._base_branch.addItem("Loading...", self._BASE_BRANCH_LOADING_SENTINEL)
            self._base_branch.setCurrentIndex(0)
        finally:
            self._base_branch.blockSignals(False)
        self._base_branch.setEnabled(False)
        self._start_base_branch_loading_animation()

    def set_repo_branches_loading(self, loading: bool) -> None:
        should_load = bool(loading)
        if should_load:
            self._base_branch_loading_requested = True
            if self._base_branch_loading:
                return
            self._base_branch_loading_delay_timer.start()
            return

        self._base_branch_loading_requested = False
        self._base_branch_loading_delay_timer.stop()
        if not self._base_branch_loading:
            return

        self._base_branch_loading = False
        self._stop_base_branch_loading_animation()
        self._base_branch.setEnabled(True)

        is_loading_placeholder = (
            self._base_branch.count() == 1
            and str(self._base_branch.itemData(0) or "") == self._BASE_BRANCH_LOADING_SENTINEL
        )
        if is_loading_placeholder:
            self._restore_base_branch_loading_snapshot()

        self._base_branch_loading_snapshot = []
        self._base_branch_loading_selected = ""

    def _apply_repo_branches_now(
        self,
        *,
        branches: list[str],
        selected: str | None,
        preserve_current_selection: bool,
    ) -> None:
        wanted = str(selected or "").strip()
        preserved = self._selected_base_branch_for_preserve() if preserve_current_selection else ""
        self.set_repo_branches_loading(False)

        self._base_branch.blockSignals(True)
        try:
            self._base_branch.clear()
            self._base_branch.addItem("Auto", "")
            seen: set[str] = set()
            for name in branches or []:
                branch = str(name or "").strip()
                if not branch or branch in seen:
                    continue
                seen.add(branch)
                self._base_branch.addItem(branch, branch)

            target = ""
            if wanted and wanted in seen:
                target = wanted
            elif preserve_current_selection and preserved and preserved in seen:
                target = preserved

            idx = self._base_branch.findData(target)
            if idx < 0:
                idx = self._base_branch.findData("")
            if idx < 0 and self._base_branch.count() > 0:
                idx = 0
            if idx >= 0:
                self._base_branch.setCurrentIndex(idx)
        finally:
            self._base_branch.blockSignals(False)

    def _apply_pending_repo_branches_update(self) -> None:
        pending = self._pending_repo_branches_update
        if pending is None:
            return
        if self._base_branch.view().isVisible():
            self._pending_repo_branches_timer.start()
            return

        self._pending_repo_branches_update = None
        branches, selected, preserve = pending
        self._apply_repo_branches_now(
            branches=list(branches),
            selected=selected,
            preserve_current_selection=bool(preserve),
        )

    def set_repo_branches(
        self,
        branches: list[str],
        selected: str | None = None,
        preserve_current_selection: bool = False,
    ) -> None:
        normalized = [str(name or "").strip() for name in branches or []]
        normalized = [name for name in normalized if name]
        if preserve_current_selection and self._base_branch.view().isVisible():
            self.set_repo_branches_loading(False)
            self._pending_repo_branches_update = (
                list(normalized),
                str(selected or "").strip() or None,
                bool(preserve_current_selection),
            )
            self._pending_repo_branches_timer.start()
            return

        self._pending_repo_branches_update = None
        self._pending_repo_branches_timer.stop()
        self._apply_repo_branches_now(
            branches=normalized,
            selected=selected,
            preserve_current_selection=preserve_current_selection,
        )

    def set_interactive_defaults(self, terminal_id: str, command: str) -> None:
        if command:
            self._command.setText(command)
        self._refresh_terminal_selection(str(terminal_id or ""))

    @staticmethod
    def _format_agent_menu_label(value: str) -> str:
        display = str(get_agent_display_name(value) or "").strip()
        if display:
            return display
        words = str(value or "").strip().replace("-", " ").replace("_", " ").split()
        if not words:
            return "Unknown"
        return " ".join(word.capitalize() for word in words)

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
        self._base_agent_info = (agent, next_agent)
        self._refresh_agent_info_display()

    def _refresh_agent_info_display(self) -> None:
        if self._agent_override:
            label = str(self._agent_override.get("label") or "").strip()
            display_text = f"Override: {label}" if label else "Override"
        else:
            agent, next_agent = self._base_agent_info
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

    def _resolve_state_path(self) -> str:
        window = self.window()
        state_path = str(getattr(window, "_state_path", "") or "").strip()
        if state_path:
            return state_path
        return default_state_path()

    def _agent_configs_by_id(self) -> dict[str, AgentConfig]:
        try:
            return {
                config_id: config
                for config in load_agent_configs(self._resolve_state_path())
                if (config_id := str(getattr(config, "config_id", "") or "").strip())
            }
        except Exception:
            return {}

    def _resolve_env_agent_cli(self, inst: AgentInstance) -> str:
        config = resolve_agent_config(
            str(getattr(inst, "config_id", "") or "").strip(),
            self._agent_configs_by_id(),
        )
        agent_cli = str(getattr(config, "agent_cli", "") or "").strip()
        return normalize_agent(agent_cli) if agent_cli else ""

    def _resolve_env_agent_cli_flags(self, inst: AgentInstance) -> str:
        config = resolve_agent_config(
            str(getattr(inst, "config_id", "") or "").strip(),
            self._agent_configs_by_id(),
        )
        return str(getattr(config, "cli_flags", "") or "").strip()

    def _resolve_env_agent_config_dir(self, inst: AgentInstance) -> str:
        config = resolve_agent_config(
            str(getattr(inst, "config_id", "") or "").strip(),
            self._agent_configs_by_id(),
        )
        return str(getattr(config, "config_dir", "") or "").strip()

    def _format_env_agent_entry_label(self, inst: AgentInstance) -> str:
        agent_id = str(getattr(inst, "agent_id", "") or "").strip()
        agent_cli = self._resolve_env_agent_cli(inst)
        display_name = str(get_agent_display_name(agent_cli) or "").strip()
        agent_id_label = ""
        if agent_id:
            agent_id_label = f"{agent_id[:1].upper()}{agent_id[1:]}"
        if agent_id_label and display_name:
            return f"{agent_id_label} ({display_name})"
        if agent_id_label:
            return agent_id_label
        return display_name or "Unknown"

    def _active_env_agent_entries(self) -> list[AgentInstance]:
        return list(self._env_agents.get(self._active_env_id, []) or [])

    def _build_env_override(self, *, inst: AgentInstance, env_id: str) -> dict[str, str]:
        agent_cli = self._resolve_env_agent_cli(inst)
        return {
            "source": "env",
            "env_id": str(env_id or ""),
            "agent_cli": agent_cli,
            "agent_id": str(getattr(inst, "agent_id", "") or "").strip(),
            "config_id": str(getattr(inst, "config_id", "") or "").strip(),
            "config_dir": self._resolve_env_agent_config_dir(inst),
            "cli_flags": self._resolve_env_agent_cli_flags(inst),
            "label": self._format_env_agent_entry_label(inst),
        }

    def _build_global_override(self, agent_cli: str) -> dict[str, str]:
        normalized = normalize_agent(str(agent_cli or ""))
        return {
            "source": "global",
            "env_id": "",
            "agent_cli": normalized,
            "agent_id": "",
            "config_id": "",
            "config_dir": "",
            "cli_flags": "",
            "label": self._format_agent_menu_label(normalized),
        }

    def _rebuild_override_menu(self) -> None:
        self._override_menu.clear()

        entries = self._active_env_agent_entries()
        if entries:
            for inst in entries:
                label = self._format_env_agent_entry_label(inst)
                action = self._override_menu.addAction(label)
                payload = self._build_env_override(inst=inst, env_id=self._active_env_id)
                action.triggered.connect(lambda _checked=False, override=payload: self._set_agent_override(override))
        else:
            agents = list(available_agents(include_internal=False))
            if not agents:
                action = self._override_menu.addAction("No agents available")
                action.setEnabled(False)
            else:
                for agent in agents:
                    normalized = normalize_agent(str(agent or ""))
                    label = self._format_agent_menu_label(normalized)
                    action = self._override_menu.addAction(label)
                    payload = self._build_global_override(normalized)
                    action.triggered.connect(
                        lambda _checked=False, override=payload: self._set_agent_override(override)
                    )

        self._override_menu.addSeparator()
        clear_action = self._override_menu.addAction("Clear override")
        clear_action.setEnabled(bool(self._agent_override))
        clear_action.triggered.connect(self._clear_agent_override)

    def _set_agent_override(self, override: dict[str, str] | None) -> None:
        self._agent_override = dict(override) if override else None
        self._refresh_agent_info_display()
        self._apply_environment_tints()

    def _clear_agent_override(self) -> None:
        if not self._agent_override:
            return
        self._set_agent_override(None)

    def _clear_override_if_invalid(self) -> None:
        if not self._agent_override:
            return
        if str(self._agent_override.get("source") or "") != "env":
            return
        override_env = str(self._agent_override.get("env_id") or "")
        override_id = str(self._agent_override.get("agent_id") or "")
        if override_env and override_env != self._active_env_id:
            self._set_agent_override(None)
            return
        if not override_id:
            return
        for inst in self._active_env_agent_entries():
            if str(getattr(inst, "agent_id", "") or "").strip() == override_id:
                return
        self._set_agent_override(None)

    @staticmethod
    def _format_key_label(value: str) -> str:
        words = str(value or "").strip().replace("-", " ").replace("_", " ").split()
        if not words:
            return "Unknown"
        return " ".join(word.capitalize() for word in words)

    def reset_for_new_run(self) -> None:
        self._prompt.setPlainText("")
        self._prompt.setFocus(Qt.FocusReason.OtherFocusReason)
        self._pending_pr_context = None

    def _build_magic_prompts_menu(self) -> QMenu:
        prompts = load_magic_prompts()
        menu = QMenu(self)
        for entry in prompts:
            title = entry["title"]
            prompt_text = entry["prompt"]
            action = menu.addAction(title)
            action.triggered.connect(lambda checked=False, pt=prompt_text: self._prompt.setPlainText(pt))
        return menu

    def _on_magic_prompts_clicked(self) -> None:
        menu = self._build_magic_prompts_menu()
        menu.exec_(self._magic_prompts_btn.mapToGlobal(QPoint(0, self._magic_prompts_btn.height())))

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
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self._prompt.setTextCursor(cursor)
        self._prompt.setFocus(Qt.FocusReason.OtherFocusReason)

    def set_pending_pr_context(self, context: dict[str, object] | None) -> None:
        self._pending_pr_context = context if isinstance(context, dict) else None

    def focus_prompt(self) -> None:
        self._prompt.setFocus(Qt.FocusReason.OtherFocusReason)
