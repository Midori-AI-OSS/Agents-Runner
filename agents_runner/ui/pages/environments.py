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
from PySide6.QtWidgets import QSplitter
from PySide6.QtWidgets import QStackedWidget
from PySide6.QtWidgets import QStyle
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
from agents_runner.ui.constants import (
    MAIN_LAYOUT_MARGINS,
    MAIN_LAYOUT_SPACING,
    HEADER_MARGINS,
    HEADER_SPACING,
    CARD_MARGINS,
    CARD_SPACING,
    GRID_HORIZONTAL_SPACING,
    GRID_VERTICAL_SPACING,
    BUTTON_ROW_SPACING,
    STANDARD_BUTTON_WIDTH,
    TAB_CONTENT_MARGINS,
    TAB_CONTENT_SPACING,
)

from agents_runner.ui.pages.environments_actions import _EnvironmentsPageActionsMixin
from agents_runner.ui.pages.environments_prompts import PromptsTabWidget
from agents_runner.ui.pages.environments_agents import AgentsTabWidget
from agents_runner.ui.graphics import _EnvironmentTintOverlay
from agents_runner.ui.utils import _apply_environment_combo_tint
from agents_runner.ui.utils import _stain_color


class EnvironmentsPage(QWidget, _EnvironmentsPageActionsMixin):
    back_requested = Signal()
    updated = Signal(str)
    test_preflight_requested = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._environments: dict[str, Environment] = {}
        self._current_env_id: str | None = None
        self._settings_data: dict[str, object] = {}  # Reference to main window settings

        layout = QVBoxLayout(self)
        layout.setContentsMargins(*MAIN_LAYOUT_MARGINS)
        layout.setSpacing(MAIN_LAYOUT_SPACING)

        header = GlassCard()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(*HEADER_MARGINS)
        header_layout.setSpacing(HEADER_SPACING)

        title = QLabel("Environments")
        title.setStyleSheet("font-size: 18px; font-weight: 750;")
        title.setToolTip(
            "Environments are saved locally in:\n~/.midoriai/agents-runner/state.json"
        )

        back = QToolButton()
        back.setText("Back")
        back.setToolButtonStyle(Qt.ToolButtonTextOnly)
        back.clicked.connect(self.back_requested.emit)

        header_layout.addWidget(title)
        header_layout.addStretch(1)
        header_layout.addWidget(back, 0, Qt.AlignRight)
        layout.addWidget(header)

        card = GlassCard()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(*CARD_MARGINS)
        card_layout.setSpacing(CARD_SPACING)

        top_row = QHBoxLayout()
        top_row.setSpacing(BUTTON_ROW_SPACING)
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
        general_layout.setContentsMargins(*TAB_CONTENT_MARGINS)
        general_layout.setSpacing(TAB_CONTENT_SPACING)

        grid = QGridLayout()
        grid.setHorizontalSpacing(GRID_HORIZONTAL_SPACING)
        grid.setVerticalSpacing(GRID_VERTICAL_SPACING)
        grid.setContentsMargins(0, 0, 0, 0)

        self._name = QLineEdit()
        self._color = QComboBox()
        for stain in ALLOWED_STAINS:
            self._color.addItem(stain.title(), stain)
        self._color.currentIndexChanged.connect(self._apply_environment_tints)

        self._max_agents_running = QLineEdit()
        self._max_agents_running.setPlaceholderText("-1")
        self._max_agents_running.setToolTip(
            "Maximum agents running at the same time for this environment. Set to -1 for no limit.\n"
            "Tip: For local-folder workspaces, set this to 1 to avoid agents fighting over setup/files."
        )
        self._max_agents_running.setValidator(QIntValidator(-1, 10_000_000, self))
        self._max_agents_running.setMaximumWidth(150)

        grid.addWidget(QLabel("Name"), 0, 0)
        grid.addWidget(self._name, 0, 1, 1, 2)
        grid.addWidget(QLabel("Color"), 1, 0)
        grid.addWidget(self._color, 1, 1, 1, 2)

        self._headless_desktop_enabled = QCheckBox(
            "Enable headless desktop"
        )
        self._headless_desktop_enabled.setToolTip(
            "When enabled, agent runs for this environment will start a noVNC desktop.\n"
            "Settings → Force headless desktop overrides this setting."
        )
        
        self._cache_desktop_build = QCheckBox(
            "Cache desktop build"
        )
        self._cache_desktop_build.setToolTip(
            "When enabled, desktop components are pre-installed in a cached Docker image.\n"
            "This reduces task startup time from 45-90s to 2-5s.\n"
            "Requires 'Enable headless desktop' to be enabled.\n\n"
            "Image is automatically rebuilt when scripts change."
        )
        self._cache_desktop_build.setEnabled(False)  # Disabled until desktop is enabled
        
        # Connect desktop enabled checkbox to cache checkbox state
        self._headless_desktop_enabled.stateChanged.connect(
            self._on_headless_desktop_toggled
        )

        self._container_caching_enabled = QCheckBox(
            "Enable container caching"
        )
        self._container_caching_enabled.setToolTip(
            "When enabled, environment preflight scripts are executed at Docker build time.\n"
            "This creates a cached image with pre-installed dependencies, speeding up task startup.\n\n"
            "The cached preflight script is configured in the Preflight tab.\n"
            "Image is automatically rebuilt when the cached preflight script changes."
        )
        self._container_caching_enabled.stateChanged.connect(
            self._on_container_caching_toggled
        )

        self._gh_context_enabled = QCheckBox(
            "Provide GitHub context to agent"
        )
        self._gh_context_enabled.setToolTip(
            "When enabled, repository context (URL, branch, commit) is provided to the agent.\n"
            "For GitHub-managed environments: Always available.\n"
            "For folder-managed environments: Only if folder is a git repository.\n\n"
            "Note: This does NOT provide GitHub authentication - that is separate."
        )
        self._gh_context_enabled.setEnabled(False)
        self._gh_context_enabled.setVisible(True)

        self._merge_agent_auto_start_enabled = QCheckBox(
            "Auto merge pull request"
        )
        self._merge_agent_auto_start_enabled.setToolTip(
            "When enabled, after a pull request creation task finishes, the program waits about 30 seconds\n"
            "and then starts a merge-agent task that resolves merge conflicts (if any) and merges the pull request."
        )

        self._merge_agent_label = QLabel("Merge agent")
        self._merge_agent_row = QWidget(general_tab)
        merge_agent_layout = QHBoxLayout(self._merge_agent_row)
        merge_agent_layout.setContentsMargins(0, 0, 0, 0)
        merge_agent_layout.setSpacing(BUTTON_ROW_SPACING)
        merge_agent_layout.addWidget(self._merge_agent_auto_start_enabled)
        merge_agent_layout.addStretch(1)

        max_agents_row = QWidget(general_tab)
        max_agents_row_layout = QHBoxLayout(max_agents_row)
        max_agents_row_layout.setContentsMargins(0, 0, 0, 0)
        max_agents_row_layout.setSpacing(BUTTON_ROW_SPACING)
        max_agents_row_layout.addWidget(self._max_agents_running)
        max_agents_row_layout.addStretch(1)

        headless_desktop_row = QWidget(general_tab)
        headless_desktop_layout = QHBoxLayout(headless_desktop_row)
        headless_desktop_layout.setContentsMargins(0, 0, 0, 0)
        headless_desktop_layout.setSpacing(BUTTON_ROW_SPACING)
        headless_desktop_layout.addWidget(self._headless_desktop_enabled)
        headless_desktop_layout.addWidget(self._cache_desktop_build)
        headless_desktop_layout.addStretch(1)

        container_caching_row = QWidget(general_tab)
        container_caching_layout = QHBoxLayout(container_caching_row)
        container_caching_layout.setContentsMargins(0, 0, 0, 0)
        container_caching_layout.setSpacing(BUTTON_ROW_SPACING)
        container_caching_layout.addWidget(self._container_caching_enabled)
        container_caching_layout.addStretch(1)

        grid.addWidget(QLabel("Max agents running"), 3, 0)
        grid.addWidget(max_agents_row, 3, 1, 1, 2)
        grid.addWidget(QLabel("Headless desktop"), 5, 0)
        grid.addWidget(headless_desktop_row, 5, 1, 1, 2)
        grid.addWidget(QLabel("Container caching"), 6, 0)
        grid.addWidget(container_caching_row, 6, 1, 1, 2)
        self._merge_agent_label.setVisible(False)
        self._merge_agent_row.setVisible(False)
        grid.addWidget(self._merge_agent_label, 7, 0)
        grid.addWidget(self._merge_agent_row, 7, 1, 1, 2)

        self._gh_context_label = QLabel("GitHub context")
        self._gh_context_row = QWidget(general_tab)
        gh_context_layout = QHBoxLayout(self._gh_context_row)
        gh_context_layout.setContentsMargins(0, 0, 0, 0)
        gh_context_layout.setSpacing(BUTTON_ROW_SPACING)
        gh_context_layout.addWidget(self._gh_context_enabled)
        gh_context_layout.addStretch(1)

        self._gh_context_label.setVisible(False)
        self._gh_context_row.setVisible(False)
        grid.addWidget(self._gh_context_label, 4, 0)
        grid.addWidget(self._gh_context_row, 4, 1, 1, 2)

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
        self._gh_management_browse.setFixedWidth(STANDARD_BUTTON_WIDTH)
        self._gh_management_browse.clicked.connect(self._pick_gh_management_folder)

        self._gh_use_host_cli = QCheckBox(
            "Use host `gh` CLI", general_tab
        )
        self._gh_use_host_cli.setToolTip(
            "Use the host system's `gh` CLI for cloning and PR creation (if installed).\n"
            "When disabled or unavailable, cloning uses `git` and PR creation is skipped."
        )
        self._gh_use_host_cli.setVisible(False)

        self._gh_management_mode.setVisible(False)
        self._gh_management_target.setVisible(False)
        self._gh_management_browse.setVisible(False)

        general_layout.addLayout(grid)
        general_layout.addStretch(1)

        # Single-editor mode widgets (caching OFF)
        self._preflight_enabled = QCheckBox(
            "Enable environment preflight"
        )
        self._preflight_enabled.setToolTip(
            "Runs after Settings preflight script.\n"
            "Use for environment-specific setup tasks."
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

        # Dual-editor mode widgets (caching ON)
        self._cached_preflight_enabled = QCheckBox(
            "Enable cached preflight"
        )
        self._cached_preflight_enabled.setToolTip(
            "Runs at Docker build time to pre-install dependencies.\n"
            "Creates a cached image for faster task startup."
        )
        self._cached_preflight_script = QPlainTextEdit()
        self._cached_preflight_script.setPlaceholderText(
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            "\n"
            "# Runs at Docker build time.\n"
            "# Use for installing packages and dependencies.\n"
        )
        self._cached_preflight_script.setTabChangesFocus(True)
        self._cached_preflight_enabled.toggled.connect(self._cached_preflight_script.setEnabled)
        self._cached_preflight_script.setEnabled(False)

        self._run_preflight_enabled = QCheckBox(
            "Enable run preflight"
        )
        self._run_preflight_enabled.setToolTip(
            "Runs at task startup after cached preflight.\n"
            "Use for runtime setup and validation."
        )
        self._run_preflight_script = QPlainTextEdit()
        self._run_preflight_script.setPlaceholderText(
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            "\n"
            "# Runs at task startup (after cached layer).\n"
            "# Use for runtime-specific setup.\n"
        )
        self._run_preflight_script.setTabChangesFocus(True)
        self._run_preflight_enabled.toggled.connect(self._run_preflight_script.setEnabled)
        self._run_preflight_script.setEnabled(False)

        # Build single-editor container (caching OFF)
        self._preflight_single_container = QWidget()
        single_layout = QVBoxLayout(self._preflight_single_container)
        single_layout.setSpacing(TAB_CONTENT_SPACING)
        single_layout.setContentsMargins(0, 0, 0, 0)
        single_layout.addWidget(self._preflight_enabled)
        single_layout.addWidget(QLabel("Preflight script"))
        single_layout.addWidget(self._preflight_script, 1)

        # Build dual-editor container (caching ON)
        self._preflight_dual_container = QWidget()
        dual_layout = QVBoxLayout(self._preflight_dual_container)
        dual_layout.setSpacing(TAB_CONTENT_SPACING)
        dual_layout.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)

        # Left panel: Cached preflight
        left_panel = GlassCard()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(18, 16, 18, 16)
        left_layout.setSpacing(10)

        cached_label = QLabel("Cached preflight")
        cached_label.setStyleSheet("font-size: 14px; font-weight: 650;")

        left_layout.addWidget(self._cached_preflight_enabled)
        left_layout.addWidget(cached_label)
        left_layout.addWidget(self._cached_preflight_script, 1)

        # Right panel: Run preflight
        right_panel = GlassCard()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(18, 16, 18, 16)
        right_layout.setSpacing(10)

        run_label = QLabel("Run preflight")
        run_label.setStyleSheet("font-size: 14px; font-weight: 650;")

        right_layout.addWidget(self._run_preflight_enabled)
        right_layout.addWidget(run_label)
        right_layout.addWidget(self._run_preflight_script, 1)

        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)

        dual_layout.addWidget(splitter, 1)

        # Create stacked widget for layout switching
        self._preflight_stack = QStackedWidget()
        self._preflight_stack.addWidget(self._preflight_single_container)  # Index 0: caching OFF
        self._preflight_stack.addWidget(self._preflight_dual_container)    # Index 1: caching ON

        preflight_tab = QWidget()
        preflight_layout = QVBoxLayout(preflight_tab)
        preflight_layout.setSpacing(TAB_CONTENT_SPACING)
        preflight_layout.setContentsMargins(*TAB_CONTENT_MARGINS)
        preflight_layout.addWidget(self._preflight_stack, 1)

        self._env_vars = QPlainTextEdit()
        self._env_vars.setPlaceholderText("# KEY=VALUE (one per line)\n")
        self._env_vars.setTabChangesFocus(True)
        env_vars_tab = QWidget()
        env_vars_layout = QVBoxLayout(env_vars_tab)
        env_vars_layout.setSpacing(TAB_CONTENT_SPACING)
        env_vars_layout.setContentsMargins(*TAB_CONTENT_MARGINS)
        env_vars_layout.addWidget(QLabel("Container env vars"))
        env_vars_layout.addWidget(self._env_vars, 1)

        self._mounts = QPlainTextEdit()
        self._mounts.setPlaceholderText("# host_path:container_path[:ro]\n")
        self._mounts.setTabChangesFocus(True)
        mounts_tab = QWidget()
        mounts_layout = QVBoxLayout(mounts_tab)
        mounts_layout.setSpacing(TAB_CONTENT_SPACING)
        mounts_layout.setContentsMargins(*TAB_CONTENT_MARGINS)
        mounts_layout.addWidget(QLabel("Extra bind mounts"))
        mounts_layout.addWidget(self._mounts, 1)

        self._prompts_tab = PromptsTabWidget()
        self._prompts_tab.prompts_changed.connect(self._on_prompts_changed)

        self._agents_tab = AgentsTabWidget()
        self._agents_tab.agents_changed.connect(self._on_agents_changed)

        tabs.addTab(general_tab, "General")
        tabs.addTab(self._agents_tab, "Agents")
        tabs.addTab(self._prompts_tab, "Prompts")
        tabs.addTab(env_vars_tab, "Env Vars")
        tabs.addTab(mounts_tab, "Mounts")
        tabs.addTab(preflight_tab, "Preflight")

        card_layout.addWidget(tabs, 1)

        layout.addWidget(card, 1)

        self._tint_overlay = _EnvironmentTintOverlay(self, alpha=13)
        self._tint_overlay.raise_()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._tint_overlay.setGeometry(self.rect())
        self._tint_overlay.raise_()

    def _apply_environment_tints(self) -> None:
        stain = str(self._color.currentData() or "").strip().lower()
        if not stain:
            env_id = str(self._env_select.currentData() or "")
            env = self._environments.get(env_id)
            stain = (env.normalized_color() if env else "").strip().lower()

        if not stain:
            self._env_select.setStyleSheet("")
            self._tint_overlay.set_tint_color(None)
            self._color.setStyleSheet("")
            return

        _apply_environment_combo_tint(self._env_select, stain)
        tint = _stain_color(stain)
        self._tint_overlay.set_tint_color(tint)
        _apply_environment_combo_tint(self._color, stain)

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
        self._apply_environment_tints()
    
    def set_settings_data(self, settings_data: dict[str, object]) -> None:
        """Set reference to main window settings data."""
        self._settings_data = settings_data

    def _load_selected(self) -> None:
        env_id = str(self._env_select.currentData() or "")
        env = self._environments.get(env_id)
        self._current_env_id = env_id if env else None
        if not env:
            self._name.setText("")
            self._max_agents_running.setText("-1")
            self._headless_desktop_enabled.setChecked(False)
            self._cache_desktop_build.setChecked(False)
            self._cache_desktop_build.setEnabled(False)
            self._container_caching_enabled.setChecked(False)
            self._gh_context_enabled.setChecked(False)
            self._gh_context_enabled.setEnabled(False)
            self._gh_context_label.setVisible(False)
            self._gh_context_row.setVisible(False)
            self._merge_agent_auto_start_enabled.setChecked(False)
            self._merge_agent_label.setVisible(False)
            self._merge_agent_row.setVisible(False)
            self._gh_management_mode.setCurrentIndex(0)
            self._gh_management_target.setText("")
            self._gh_use_host_cli.setChecked(bool(is_gh_available()))
            self._preflight_enabled.setChecked(False)
            self._preflight_script.setPlainText("")
            self._cached_preflight_enabled.setChecked(False)
            self._cached_preflight_script.setPlainText("")
            self._run_preflight_enabled.setChecked(False)
            self._run_preflight_script.setPlainText("")
            self._preflight_stack.setCurrentIndex(0)
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
        self._max_agents_running.setText(
            str(int(getattr(env, "max_agents_running", -1)))
        )
        self._headless_desktop_enabled.setChecked(
            bool(getattr(env, "headless_desktop_enabled", False))
        )
        self._cache_desktop_build.setChecked(
            bool(getattr(env, "cache_desktop_build", False))
        )
        # Update cache checkbox enabled state based on desktop enabled state
        self._cache_desktop_build.setEnabled(
            bool(getattr(env, "headless_desktop_enabled", False))
        )
        self._container_caching_enabled.setChecked(
            bool(getattr(env, "container_caching_enabled", False))
        )
        is_github_env = (
            normalize_gh_management_mode(
                str(env.gh_management_mode or GH_MANAGEMENT_NONE)
            )
            == GH_MANAGEMENT_GITHUB
        )
        is_local_env = (
            normalize_gh_management_mode(
                str(env.gh_management_mode or GH_MANAGEMENT_NONE)
            )
            == GH_MANAGEMENT_LOCAL
        )
        
        # Check if folder-locked environment is a git repo
        is_git_repo = False
        if is_local_env:
            is_git_repo = env.detect_git_if_folder_locked()
        
        # Enable GitHub context for git-locked or folder-locked git repos
        context_available = is_github_env or (is_local_env and is_git_repo)
        
        self._gh_context_enabled.setChecked(
            bool(getattr(env, "gh_context_enabled", False))
        )
        self._gh_context_enabled.setEnabled(context_available)
        self._gh_context_label.setVisible(context_available)
        self._gh_context_row.setVisible(context_available)

        merge_supported = bool(
            is_github_env
            and bool(getattr(env, "gh_management_locked", False))
            and bool(getattr(env, "gh_context_enabled", False))
        )
        is_github_env = env.gh_management_mode == GH_MANAGEMENT_GITHUB
        is_git_locked = bool(getattr(env, "gh_management_locked", False))
        show_merge_controls = is_github_env and is_git_locked
        self._merge_agent_label.setVisible(show_merge_controls)
        self._merge_agent_row.setVisible(show_merge_controls)
        self._merge_agent_auto_start_enabled.setChecked(
            bool(getattr(env, "merge_agent_auto_start_enabled", False))
        )

        idx = self._gh_management_mode.findData(
            normalize_gh_management_mode(env.gh_management_mode)
        )
        if idx >= 0:
            self._gh_management_mode.setCurrentIndex(idx)
        self._gh_management_target.setText(str(env.gh_management_target or ""))
        self._gh_use_host_cli.setChecked(bool(getattr(env, "gh_use_host_cli", True)))
        self._sync_gh_management_controls(env=env)
        
        # Load preflight scripts based on container caching state
        container_caching = bool(getattr(env, "container_caching_enabled", False))
        
        # Single-editor mode (caching OFF)
        self._preflight_enabled.setChecked(bool(env.preflight_enabled))
        self._preflight_script.setEnabled(bool(env.preflight_enabled))
        self._preflight_script.setPlainText(env.preflight_script or "")
        
        # Dual-editor mode (caching ON)
        cached_script = str(getattr(env, "cached_preflight_script", "") or "")
        has_cached = bool(cached_script.strip())
        self._cached_preflight_enabled.setChecked(has_cached)
        self._cached_preflight_script.setEnabled(has_cached)
        self._cached_preflight_script.setPlainText(cached_script)
        
        self._run_preflight_enabled.setChecked(bool(env.preflight_enabled))
        self._run_preflight_script.setEnabled(bool(env.preflight_enabled))
        self._run_preflight_script.setPlainText(env.preflight_script or "")
        
        # Set layout state
        self._preflight_stack.setCurrentIndex(1 if container_caching else 0)
        
        env_lines = "\n".join(f"{k}={v}" for k, v in sorted(env.env_vars.items()))
        self._env_vars.setPlainText(env_lines)
        self._mounts.setPlainText("\n".join(env.extra_mounts))
        self._prompts_tab.set_prompts(env.prompts or [], env.prompts_unlocked or False)
        self._agents_tab.set_agent_selection(env.agent_selection)

    def _on_prompts_changed(self) -> None:
        pass

    def _on_agents_changed(self) -> None:
        pass
    
    def _on_headless_desktop_toggled(self, state: int) -> None:
        """Handle headless desktop checkbox state change.
        
        When desktop is disabled, also disable and uncheck cache checkbox.
        When desktop is enabled, enable cache checkbox (but leave unchecked by default).
        """
        is_enabled = state == Qt.CheckState.Checked.value
        self._cache_desktop_build.setEnabled(is_enabled)
        if not is_enabled:
            # Desktop disabled, also disable cache
            self._cache_desktop_build.setChecked(False)

    def _on_container_caching_toggled(self, state: int) -> None:
        """Switch preflight tab layout based on container caching state."""
        is_enabled = state == Qt.CheckState.Checked.value
        self._preflight_stack.setCurrentIndex(1 if is_enabled else 0)

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
        self._apply_environment_tints()

    def _pick_gh_management_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self,
            "Select locked Workdir folder",
            self._gh_management_target.text() or os.getcwd(),
        )
        if path:
            self._gh_management_target.setText(path)
