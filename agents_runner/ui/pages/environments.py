from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtCore import Signal
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import QCheckBox
from PySide6.QtWidgets import QComboBox
from PySide6.QtWidgets import QFileDialog
from PySide6.QtWidgets import QGridLayout
from PySide6.QtWidgets import QHBoxLayout
from PySide6.QtWidgets import QLabel
from PySide6.QtWidgets import QLineEdit
from PySide6.QtWidgets import QPlainTextEdit
from PySide6.QtWidgets import QPushButton
from PySide6.QtWidgets import QTabWidget
from PySide6.QtWidgets import QToolButton
from PySide6.QtWidgets import QVBoxLayout
from PySide6.QtWidgets import QWidget

from agents_runner.environments import ALLOWED_STAINS
from agents_runner.environments import Environment
from agents_runner.environments import GH_MANAGEMENT_GITHUB
from agents_runner.environments import GH_MANAGEMENT_LOCAL
from agents_runner.environments import GH_MANAGEMENT_NONE
from agents_runner.environments import normalize_gh_management_mode
from agents_runner.gh_management import is_gh_available
from agents_runner.widgets import GlassCard

from agents_runner.ui.pages.environments_actions import _EnvironmentsPageActionsMixin
from agents_runner.ui.pages.environments_prompts import PromptsTabWidget
from agents_runner.ui.pages.environments_agents import AgentsTabWidget


class EnvironmentsPage(QWidget, _EnvironmentsPageActionsMixin):
    back_requested = Signal()
    updated = Signal(str)
    test_preflight_requested = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._environments: dict[str, Environment] = {}
        self._current_env_id: str | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        header = GlassCard()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(18, 16, 18, 16)
        header_layout.setSpacing(10)

        title = QLabel("Environments")
        title.setStyleSheet("font-size: 18px; font-weight: 750;")
        subtitle = QLabel("Saved locally in ~/.midoriai/agents-runner/state.json")
        subtitle.setStyleSheet("color: rgba(237, 239, 245, 160);")

        back = QToolButton()
        back.setText("Back")
        back.setToolButtonStyle(Qt.ToolButtonTextOnly)
        back.clicked.connect(self.back_requested.emit)

        header_layout.addWidget(title)
        header_layout.addWidget(subtitle, 1)
        header_layout.addWidget(back, 0, Qt.AlignRight)
        layout.addWidget(header)

        card = GlassCard()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 16, 18, 16)
        card_layout.setSpacing(12)

        top_row = QHBoxLayout()
        top_row.setSpacing(10)
        self._env_select = QComboBox()
        self._env_select.currentIndexChanged.connect(self._on_env_selected)

        new_btn = QToolButton()
        new_btn.setText("New")
        new_btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
        new_btn.clicked.connect(self._on_new)

        delete_btn = QToolButton()
        delete_btn.setText("Delete")
        delete_btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
        delete_btn.clicked.connect(self._on_delete)

        save_btn = QToolButton()
        save_btn.setText("Save")
        save_btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
        save_btn.clicked.connect(self._on_save)

        test_btn = QToolButton()
        test_btn.setText("Test preflight")
        test_btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
        test_btn.clicked.connect(self._on_test_preflight)

        top_row.addWidget(QLabel("Environment"))
        top_row.addWidget(self._env_select, 1)
        top_row.addWidget(new_btn)
        top_row.addWidget(delete_btn)
        top_row.addWidget(test_btn)
        top_row.addWidget(save_btn)
        card_layout.addLayout(top_row)

        tabs = QTabWidget()
        tabs.setDocumentMode(True)

        general_tab = QWidget()
        general_layout = QVBoxLayout(general_tab)
        general_layout.setContentsMargins(0, 16, 0, 12)
        general_layout.setSpacing(10)

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)
        grid.setContentsMargins(0, 0, 0, 0)

        self._name = QLineEdit()
        self._color = QComboBox()
        for stain in ALLOWED_STAINS:
            self._color.addItem(stain.title(), stain)

        self._host_codex_dir = QLineEdit()
        self._agent_cli_args = QLineEdit()
        self._agent_cli_args.setPlaceholderText("--model … (optional)")
        self._agent_cli_args.setToolTip(
            "Extra CLI flags appended to the agent command inside the container."
        )

        self._max_agents_running = QLineEdit()
        self._max_agents_running.setPlaceholderText("-1 (unlimited)")
        self._max_agents_running.setToolTip(
            "Maximum agents running at the same time for this environment. Set to -1 for no limit.\n"
            "Tip: For local-folder workspaces, set this to 1 to avoid agents fighting over setup/files."
        )
        self._max_agents_running.setValidator(QIntValidator(-1, 10_000_000, self))
        self._max_agents_running.setMaximumWidth(150)

        browse_codex = QPushButton("Browse…")
        browse_codex.setFixedWidth(100)
        browse_codex.clicked.connect(self._pick_codex_dir)

        grid.addWidget(QLabel("Name"), 0, 0)
        grid.addWidget(self._name, 0, 1, 1, 2)
        grid.addWidget(QLabel("Color"), 1, 0)
        grid.addWidget(self._color, 1, 1, 1, 2)
        grid.addWidget(QLabel("Default Host Config folder"), 2, 0)
        grid.addWidget(self._host_codex_dir, 2, 1)
        grid.addWidget(browse_codex, 2, 2)
        grid.addWidget(QLabel("Agent CLI Flags"), 3, 0)
        grid.addWidget(self._agent_cli_args, 3, 1, 1, 2)

        self._gh_pr_metadata_enabled = QCheckBox(
            "Allow agent to set PR title/body (non-interactive only)"
        )
        self._gh_pr_metadata_enabled.setToolTip(
            "When enabled and Workspace is a GitHub repo (clone), a per-task JSON file is mounted into the container.\n"
            "The agent is prompted to update it with a PR title/body, which will be used when opening the PR."
        )
        self._gh_pr_metadata_enabled.setEnabled(False)
        self._gh_pr_metadata_enabled.setVisible(True)

        max_agents_row = QWidget(general_tab)
        max_agents_row_layout = QHBoxLayout(max_agents_row)
        max_agents_row_layout.setContentsMargins(0, 0, 0, 0)
        max_agents_row_layout.setSpacing(10)
        max_agents_row_layout.addWidget(self._max_agents_running)
        max_agents_row_layout.addStretch(1)

        grid.addWidget(QLabel("Max agents running"), 4, 0)
        grid.addWidget(max_agents_row, 4, 1, 1, 2)

        self._gh_pr_metadata_label = QLabel("PR title/body")
        self._gh_pr_metadata_row = QWidget(general_tab)
        gh_pr_metadata_layout = QHBoxLayout(self._gh_pr_metadata_row)
        gh_pr_metadata_layout.setContentsMargins(0, 0, 0, 0)
        gh_pr_metadata_layout.setSpacing(10)
        gh_pr_metadata_layout.addWidget(self._gh_pr_metadata_enabled)
        gh_pr_metadata_layout.addStretch(1)

        self._gh_pr_metadata_label.setVisible(False)
        self._gh_pr_metadata_row.setVisible(False)
        grid.addWidget(self._gh_pr_metadata_label, 5, 0)
        grid.addWidget(self._gh_pr_metadata_row, 5, 1, 1, 2)

        self._gh_management_mode = QComboBox(general_tab)
        self._gh_management_mode.addItem("Use Settings workdir", GH_MANAGEMENT_NONE)
        self._gh_management_mode.addItem("Lock to local folder", GH_MANAGEMENT_LOCAL)
        self._gh_management_mode.addItem(
            "Lock to GitHub repo (clone)", GH_MANAGEMENT_GITHUB
        )
        self._gh_management_mode.currentIndexChanged.connect(
            self._sync_gh_management_controls
        )

        self._gh_management_target = QLineEdit(general_tab)
        self._gh_management_target.setPlaceholderText(
            "owner/repo, https://github.com/owner/repo, or /path/to/folder"
        )
        self._gh_management_target.textChanged.connect(
            self._sync_gh_management_controls
        )

        self._gh_management_browse = QPushButton("Browse…", general_tab)
        self._gh_management_browse.setFixedWidth(100)
        self._gh_management_browse.clicked.connect(self._pick_gh_management_folder)

        self._gh_use_host_cli = QCheckBox(
            "Use host `gh` for clone/PR (if installed)", general_tab
        )
        self._gh_use_host_cli.setToolTip(
            "When disabled, cloning uses `git` and PR creation is skipped."
        )
        self._gh_use_host_cli.setVisible(False)

        self._gh_management_hint = QLabel(
            "Creates a per-task branch (midoriaiagents/<task_id>) and can push + open a PR via `gh`.\n"
            "Once saved, the target is locked; create a new environment to change it.",
            general_tab,
        )
        self._gh_management_hint.setStyleSheet("color: rgba(237, 239, 245, 150);")
        self._gh_management_mode.setVisible(False)
        self._gh_management_target.setVisible(False)
        self._gh_management_browse.setVisible(False)
        self._gh_management_hint.setVisible(False)

        general_layout.addLayout(grid)
        general_layout.addStretch(1)

        self._preflight_enabled = QCheckBox(
            "Enable environment preflight bash (runs after Settings preflight)"
        )
        self._preflight_script = QPlainTextEdit()
        self._preflight_script.setPlaceholderText(
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            "\n"
            "# Runs inside the container before the agent command.\n"
            "# Runs after Settings preflight (if enabled).\n"
        )
        self._preflight_script.setTabChangesFocus(True)
        self._preflight_enabled.toggled.connect(self._preflight_script.setEnabled)
        self._preflight_script.setEnabled(False)

        preflight_tab = QWidget()
        preflight_layout = QVBoxLayout(preflight_tab)
        preflight_layout.setSpacing(10)
        preflight_layout.setContentsMargins(0, 16, 0, 12)
        preflight_layout.addWidget(self._preflight_enabled)
        preflight_layout.addWidget(QLabel("Preflight script"))
        preflight_layout.addWidget(self._preflight_script, 1)

        self._env_vars = QPlainTextEdit()
        self._env_vars.setPlaceholderText("# KEY=VALUE (one per line)\n")
        self._env_vars.setTabChangesFocus(True)
        env_vars_tab = QWidget()
        env_vars_layout = QVBoxLayout(env_vars_tab)
        env_vars_layout.setSpacing(10)
        env_vars_layout.setContentsMargins(0, 16, 0, 12)
        env_vars_layout.addWidget(QLabel("Container env vars"))
        env_vars_layout.addWidget(self._env_vars, 1)

        self._mounts = QPlainTextEdit()
        self._mounts.setPlaceholderText("# host_path:container_path[:ro]\n")
        self._mounts.setTabChangesFocus(True)
        mounts_tab = QWidget()
        mounts_layout = QVBoxLayout(mounts_tab)
        mounts_layout.setSpacing(10)
        mounts_layout.setContentsMargins(0, 16, 0, 12)
        mounts_layout.addWidget(QLabel("Extra bind mounts"))
        mounts_layout.addWidget(self._mounts, 1)

        self._prompts_tab = PromptsTabWidget()
        self._prompts_tab.prompts_changed.connect(self._on_prompts_changed)

        self._agents_tab = AgentsTabWidget()
        self._agents_tab.agents_changed.connect(self._on_agents_changed)

        tabs.addTab(general_tab, "General")
        tabs.addTab(preflight_tab, "Preflight")
        tabs.addTab(env_vars_tab, "Env Vars")
        tabs.addTab(mounts_tab, "Mounts")
        tabs.addTab(self._prompts_tab, "Prompts")
        tabs.addTab(self._agents_tab, "Agents")

        card_layout.addWidget(tabs, 1)

        layout.addWidget(card, 1)

    def set_environments(self, envs: dict[str, Environment], active_id: str) -> None:
        self._environments = dict(envs)
        current = str(self._env_select.currentData() or "")

        self._env_select.blockSignals(True)
        try:
            self._env_select.clear()
            ordered = sorted(
                self._environments.values(), key=lambda e: (e.name or e.env_id).lower()
            )
            for env in ordered:
                self._env_select.addItem(env.name or env.env_id, env.env_id)
            desired = active_id or current
            idx = self._env_select.findData(desired)
            if idx < 0 and self._env_select.count() > 0:
                idx = 0
            if idx >= 0:
                self._env_select.setCurrentIndex(idx)
        finally:
            self._env_select.blockSignals(False)

        self._load_selected()

    def _load_selected(self) -> None:
        env_id = str(self._env_select.currentData() or "")
        env = self._environments.get(env_id)
        self._current_env_id = env_id if env else None
        if not env:
            self._name.setText("")
            self._host_codex_dir.setText("")
            self._agent_cli_args.setText("")
            self._max_agents_running.setText("-1")
            self._gh_pr_metadata_enabled.setChecked(False)
            self._gh_pr_metadata_enabled.setEnabled(False)
            self._gh_pr_metadata_label.setVisible(False)
            self._gh_pr_metadata_row.setVisible(False)
            self._gh_management_mode.setCurrentIndex(0)
            self._gh_management_target.setText("")
            self._gh_use_host_cli.setChecked(bool(is_gh_available()))
            self._preflight_enabled.setChecked(False)
            self._preflight_script.setPlainText("")
            self._env_vars.setPlainText("")
            self._mounts.setPlainText("")
            self._prompts_tab.set_prompts([], False)
            self._agents_tab.set_agent_selection(None)
            self._sync_gh_management_controls()
            return

        self._name.setText(env.name)
        idx = self._color.findData(env.color)
        if idx >= 0:
            self._color.setCurrentIndex(idx)
        self._host_codex_dir.setText(env.host_codex_dir)
        self._agent_cli_args.setText(env.agent_cli_args)
        self._max_agents_running.setText(
            str(int(getattr(env, "max_agents_running", -1)))
        )
        is_github_env = (
            normalize_gh_management_mode(
                str(env.gh_management_mode or GH_MANAGEMENT_NONE)
            )
            == GH_MANAGEMENT_GITHUB
        )
        self._gh_pr_metadata_enabled.setChecked(
            bool(getattr(env, "gh_pr_metadata_enabled", False))
        )
        self._gh_pr_metadata_enabled.setEnabled(is_github_env)
        self._gh_pr_metadata_label.setVisible(is_github_env)
        self._gh_pr_metadata_row.setVisible(is_github_env)
        idx = self._gh_management_mode.findData(
            normalize_gh_management_mode(env.gh_management_mode)
        )
        if idx >= 0:
            self._gh_management_mode.setCurrentIndex(idx)
        self._gh_management_target.setText(str(env.gh_management_target or ""))
        self._gh_use_host_cli.setChecked(bool(getattr(env, "gh_use_host_cli", True)))
        self._sync_gh_management_controls(env=env)
        self._preflight_enabled.setChecked(bool(env.preflight_enabled))
        self._preflight_script.setEnabled(bool(env.preflight_enabled))
        self._preflight_script.setPlainText(env.preflight_script or "")
        env_lines = "\n".join(f"{k}={v}" for k, v in sorted(env.env_vars.items()))
        self._env_vars.setPlainText(env_lines)
        self._mounts.setPlainText("\n".join(env.extra_mounts))
        self._prompts_tab.set_prompts(env.prompts or [], env.prompts_unlocked or False)
        self._agents_tab.set_agent_selection(env.agent_selection)

    def _on_prompts_changed(self) -> None:
        pass

    def _on_agents_changed(self) -> None:
        pass

    def _on_env_selected(self, index: int) -> None:
        old_env_id = self._current_env_id
        new_env_id = str(self._env_select.currentData() or "")
        if not self.try_autosave(preferred_env_id=new_env_id):
            # Autosave failed, revert dropdown selection
            if old_env_id:
                self._env_select.blockSignals(True)
                try:
                    idx = self._env_select.findData(old_env_id)
                    if idx >= 0:
                        self._env_select.setCurrentIndex(idx)
                finally:
                    self._env_select.blockSignals(False)
            return
        self._load_selected()

    def _pick_codex_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, "Select default host Config folder", self._host_codex_dir.text()
        )
        if path:
            self._host_codex_dir.setText(path)

    def _pick_gh_management_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self,
            "Select locked Workdir folder",
            self._gh_management_target.text() or os.getcwd(),
        )
        if path:
            self._gh_management_target.setText(path)
