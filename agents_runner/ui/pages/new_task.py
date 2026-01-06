from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox
from PySide6.QtWidgets import QGridLayout
from PySide6.QtWidgets import QHBoxLayout
from PySide6.QtWidgets import QLabel
from PySide6.QtWidgets import QLineEdit
from PySide6.QtWidgets import QMenu
from PySide6.QtWidgets import QMessageBox
from PySide6.QtWidgets import QPlainTextEdit
from PySide6.QtWidgets import QSizePolicy
from PySide6.QtWidgets import QToolButton
from PySide6.QtWidgets import QVBoxLayout
from PySide6.QtWidgets import QWidget

from agents_runner.prompt_sanitizer import sanitize_prompt
from agents_runner.terminal_apps import detect_terminal_options
from agents_runner.ui.graphics import _EnvironmentTintOverlay
from agents_runner.ui.utils import _apply_environment_combo_tint
from agents_runner.ui.utils import _stain_color
from agents_runner.widgets import GlassCard
from agents_runner.widgets import StainedGlassButton


class NewTaskPage(QWidget):
    requested_run = Signal(str, str, str, str)
    requested_launch = Signal(str, str, str, str, str, str, str)
    back_requested = Signal()
    environment_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._env_stains: dict[str, str] = {}
        self._gh_locked_envs: set[str] = set()
        self._host_codex_dir = os.path.expanduser("~/.codex")
        self._workspace_ready = False
        self._workspace_error = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        self._environment = QComboBox()
        self._environment.currentIndexChanged.connect(self._on_environment_changed)

        header = GlassCard()
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(18, 16, 18, 16)
        header_layout.setSpacing(6)

        top_row = QHBoxLayout()
        top_row.setSpacing(10)
        title = QLabel("New task")
        title.setStyleSheet("font-size: 18px; font-weight: 750;")

        env_label = QLabel("Environment")
        env_label.setStyleSheet("color: rgba(237, 239, 245, 160);")

        back = QToolButton()
        back.setText("Back")
        back.setToolButtonStyle(Qt.ToolButtonTextOnly)
        back.clicked.connect(self.back_requested.emit)

        top_row.addWidget(title)
        top_row.addWidget(env_label)
        top_row.addWidget(self._environment)
        top_row.addStretch(1)
        top_row.addWidget(back, 0, Qt.AlignRight)

        header_layout.addLayout(top_row)
        layout.addWidget(header)

        card = GlassCard()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 16, 18, 16)
        card_layout.setSpacing(10)

        prompt_title = QLabel("Prompt")
        prompt_title.setStyleSheet("font-size: 14px; font-weight: 650;")
        self._prompt = QPlainTextEdit()
        self._prompt.setPlaceholderText("Describe what you want the agent to do…")
        self._prompt.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._prompt.setTabChangesFocus(True)

        interactive_hint = QLabel(
            "Interactive: opens a terminal and runs the container with TTY/stdin for agent TUIs."
        )
        interactive_hint.setStyleSheet("color: rgba(237, 239, 245, 160);")

        self._terminal = QComboBox()
        self._refresh_terminals()

        refresh_terminals = QToolButton()
        refresh_terminals.setText("Refresh")
        refresh_terminals.setToolButtonStyle(Qt.ToolButtonTextOnly)
        refresh_terminals.clicked.connect(self._refresh_terminals)

        self._command = QLineEdit("--sandbox danger-full-access")
        self._command.setPlaceholderText(
            "Args for the Agent CLI (e.g. --sandbox danger-full-access or --add-dir …), or a full container command (e.g. bash)"
        )

        interactive_grid = QGridLayout()
        interactive_grid.setHorizontalSpacing(10)
        interactive_grid.setVerticalSpacing(10)
        interactive_grid.setColumnStretch(4, 1)
        interactive_grid.addWidget(QLabel("Terminal"), 0, 0)
        interactive_grid.addWidget(self._terminal, 0, 1)
        interactive_grid.addWidget(refresh_terminals, 0, 2)
        interactive_grid.addWidget(QLabel("Container command args"), 0, 3)
        interactive_grid.addWidget(self._command, 0, 4)

        cfg_grid = QGridLayout()
        cfg_grid.setHorizontalSpacing(10)
        cfg_grid.setVerticalSpacing(10)
        self._workspace = QLabel("—")
        self._workspace.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._workspace_hint = QLabel("")
        self._workspace_hint.setStyleSheet("color: rgba(237, 239, 245, 160);")
        self._workspace_hint.setWordWrap(True)

        cfg_grid.addWidget(QLabel("Workspace"), 0, 0)
        cfg_grid.addWidget(self._workspace, 0, 1, 1, 2)
        cfg_grid.addWidget(self._workspace_hint, 1, 1, 1, 2)

        self._base_branch_label = QLabel("Base branch")
        self._base_branch = QComboBox()
        self._base_branch.setToolTip(
            "Base branch for the per-task branch (only shown for repo environments)."
        )
        self.set_repo_branches([])
        cfg_grid.addWidget(self._base_branch_label, 2, 0)
        cfg_grid.addWidget(self._base_branch, 2, 1, 1, 2)
        self.set_repo_controls_visible(False)

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

        self._run_interactive_menu = QMenu(self)
        self._run_interactive_desktop = self._run_interactive_menu.addAction(
            "With desktop"
        )
        self._run_interactive_desktop.triggered.connect(self._on_launch_with_desktop)
        self._run_interactive.set_menu(None)

        self._run_agent = StainedGlassButton("Run Agent")
        self._run_agent.set_glass_enabled(False)
        self._run_agent.clicked.connect(self._on_run)
        self._run_interactive.setEnabled(False)
        self._run_agent.setEnabled(False)
        buttons.addWidget(self._run_interactive)
        buttons.addWidget(self._run_agent)

        card_layout.addWidget(prompt_title)
        card_layout.addWidget(self._prompt, 1)
        card_layout.addWidget(interactive_hint)
        card_layout.addLayout(interactive_grid)
        card_layout.addLayout(cfg_grid)
        card_layout.addLayout(buttons)

        layout.addWidget(card, 1)

        self._tint_overlay = _EnvironmentTintOverlay(self, alpha=13)
        self._tint_overlay.raise_()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._tint_overlay.setGeometry(self.rect())
        self._tint_overlay.raise_()

    def _update_run_buttons(self) -> None:
        has_terminal = bool(str(self._terminal.currentData() or "").strip())
        can_launch = bool(self._workspace_ready and has_terminal)
        self._run_agent.setEnabled(self._workspace_ready)
        self._run_interactive.setEnabled(can_launch)
        self._get_agent_help.setEnabled(can_launch)

    def _refresh_terminals(self) -> None:
        current = str(self._terminal.currentData() or "")
        options = detect_terminal_options()
        self._terminal.blockSignals(True)
        try:
            self._terminal.clear()
            if not options:
                self._terminal.addItem("No terminals detected", "")
                self._terminal.setCurrentIndex(0)
            else:
                selected = False
                for opt in options:
                    self._terminal.addItem(opt.label, opt.terminal_id)
                desired = current
                if desired:
                    idx = self._terminal.findData(desired)
                    if idx >= 0:
                        self._terminal.setCurrentIndex(idx)
                        selected = True
                if not selected and self._terminal.count() > 0:
                    self._terminal.setCurrentIndex(0)
        finally:
            self._terminal.blockSignals(False)
        if hasattr(self, "_run_interactive"):
            self._update_run_buttons()

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

        env_id = str(self._environment.currentData() or "")
        base_branch = str(self._base_branch.currentData() or "")
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

        terminal_id = str(self._terminal.currentData() or "").strip()
        if not terminal_id:
            QMessageBox.warning(
                self,
                "No terminals found",
                "Could not detect an installed terminal emulator to launch.",
            )
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
        env_id = str(self._environment.currentData() or "")
        base_branch = str(self._base_branch.currentData() or "")

        command = (self._command.text() or "").strip()

        prompt = "\n".join(
            [
                "Agents Runner - Help Request",
                "",
                "Question:",
                user_question,
                "",
                "You're helping a user who is using Agents Runner and its GUI.",
                "",
                "Environment:",
                "- PixelArch Linux container (passwordless sudo).",
                "- Install/update packages with `yay -Syu`.",
                "",
                "Repositories:",
                "- Available under `~/.agent-help/repos/` (the preflight clones if needed).",
                "- Includes `Agents-Runner` plus `codex`, `claude-code`, `copilot-cli`, and `gemini-cli`.",
                "",
                "Instructions:",
                "- Answer the question directly; do not ask what they need help with again.",
                "- If you need one missing detail (repo/path/version), ask one short clarifying question, then proceed.",
            ]
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

    def _sync_interactive_options(self) -> None:
        env_id = str(self._environment.currentData() or "")
        self._run_interactive.set_menu(
            self._run_interactive_menu
            if (env_id and env_id in self._gh_locked_envs)
            else None
        )

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

        terminal_id = str(self._terminal.currentData() or "").strip()
        if not terminal_id:
            QMessageBox.warning(
                self,
                "No terminals found",
                "Could not detect an installed terminal emulator to launch.",
            )
            return

        env_id = str(self._environment.currentData() or "")
        base_branch = str(self._base_branch.currentData() or "")
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

    def _on_environment_changed(self, index: int) -> None:
        self._apply_environment_tints()
        self._sync_interactive_options()
        self.environment_changed.emit(str(self._environment.currentData() or ""))

    def _apply_environment_tints(self) -> None:
        env_id = str(self._environment.currentData() or "")
        stain = (self._env_stains.get(env_id) or "").strip().lower() if env_id else ""
        if not stain:
            self._environment.setStyleSheet("")
            self._tint_overlay.set_tint_color(None)
            self._get_agent_help.set_tint_color(None)
            self._run_interactive.set_tint_color(None)
            self._run_agent.set_tint_color(None)
            return

        _apply_environment_combo_tint(self._environment, stain)
        tint = _stain_color(stain)
        self._tint_overlay.set_tint_color(tint)
        self._get_agent_help.set_tint_color(tint)
        self._run_interactive.set_tint_color(tint)
        self._run_agent.set_tint_color(tint)

    def set_environment_stains(self, stains: dict[str, str]) -> None:
        self._env_stains = {str(k): str(v) for k, v in (stains or {}).items()}
        self._apply_environment_tints()

    def set_gh_locked_envs(self, env_ids: set[str]) -> None:
        self._gh_locked_envs = {str(e) for e in (env_ids or set()) if str(e).strip()}
        self._sync_interactive_options()

    def set_environments(self, envs: list[tuple[str, str]], active_id: str) -> None:
        current = str(self._environment.currentData() or "")
        self._environment.blockSignals(True)
        try:
            self._environment.clear()
            for env_id, name in envs:
                self._environment.addItem(name, env_id)
            desired = active_id or current
            idx = self._environment.findData(desired)
            if idx >= 0:
                self._environment.setCurrentIndex(idx)
        finally:
            self._environment.blockSignals(False)
        self._apply_environment_tints()
        self._sync_interactive_options()

    def set_environment_id(self, env_id: str) -> None:
        idx = self._environment.findData(env_id)
        if idx >= 0:
            self._environment.setCurrentIndex(idx)
        self._apply_environment_tints()

    def set_defaults(self, host_codex: str) -> None:
        if host_codex:
            self._host_codex_dir = host_codex

    def set_workspace_status(self, *, path: str, ready: bool, message: str) -> None:
        self._workspace.setText(str(path or "—"))
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

    def set_repo_controls_visible(self, visible: bool) -> None:
        visible = bool(visible)
        self._base_branch_label.setVisible(visible)
        self._base_branch.setVisible(visible)

    def set_repo_branches(
        self, branches: list[str], selected: str | None = None
    ) -> None:
        wanted = str(selected or "").strip()
        self._base_branch.blockSignals(True)
        try:
            self._base_branch.clear()
            self._base_branch.addItem("Auto (default)", "")
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
        terminal_id = str(terminal_id or "")
        if terminal_id:
            idx = self._terminal.findData(terminal_id)
            if idx >= 0:
                self._terminal.setCurrentIndex(idx)

    def set_agent_info(self, agent: str, next_agent: str = "") -> None:
        """Set tooltip info showing current and next agent."""
        agent = str(agent or "").strip()
        next_agent = str(next_agent or "").strip()

        if next_agent and next_agent != agent:
            if str(next_agent).startswith("Fallback:"):
                tooltip = f"Using: {agent} | {next_agent}"
            else:
                tooltip = f"Using: {agent} | Next: {next_agent}"
        elif agent:
            tooltip = f"Using: {agent}"
        else:
            tooltip = ""

        self._run_interactive.setToolTip(tooltip)
        self._run_agent.setToolTip(tooltip)

    def reset_for_new_run(self) -> None:
        self._prompt.setPlainText("")
        self._prompt.setFocus(Qt.OtherFocusReason)

    def focus_prompt(self) -> None:
        self._prompt.setFocus(Qt.OtherFocusReason)
