from __future__ import annotations

import os
import re
import random
import shutil
import hashlib
from uuid import uuid4
from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtCore import QPoint
from PySide6.QtCore import QTimer
from PySide6.QtCore import Signal
from PySide6.QtCore import QEasingCurve
from PySide6.QtCore import QSignalBlocker
from PySide6.QtCore import QPropertyAnimation
from PySide6.QtCore import QParallelAnimationGroup
from PySide6.QtGui import QResizeEvent
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import QLabel
from PySide6.QtWidgets import QWidget
from PySide6.QtWidgets import QCheckBox
from PySide6.QtWidgets import QComboBox
from PySide6.QtWidgets import QLineEdit
from PySide6.QtWidgets import QPushButton
from PySide6.QtWidgets import QGridLayout
from PySide6.QtWidgets import QHBoxLayout
from PySide6.QtWidgets import QVBoxLayout
from PySide6.QtWidgets import QFileDialog
from PySide6.QtWidgets import QSizePolicy
from PySide6.QtWidgets import QToolButton
from PySide6.QtWidgets import QStackedWidget
from PySide6.QtWidgets import QGraphicsOpacityEffect

from agents_runner.environments import ALLOWED_STAINS
from agents_runner.environments import Environment
from agents_runner.environments import WORKSPACE_CLONED
from agents_runner.environments import WORKSPACE_MOUNTED
from agents_runner.environments import save_environment
from agents_runner.environments import load_environments
from agents_runner.environments import delete_environment
from agents_runner.environments.model import AGENTSNOVA_AUTO_MODES
from agents_runner.environments.model import GH_BRANCH_WORK_MODES
from agents_runner.environments.model import GPU_OVERRIDE_MODES
from agents_runner.environments.model import INTERACTIVE_PR_NO_PROMPT_MODES
from agents_runner.environments.model import AGENTSNOVA_MARKER_COMMENT_MODES
from agents_runner.environments.model import GH_TASK_BRANCH_NAMING_STYLES
from agents_runner.environments.model import OPENCODE_INTERACTIVE_OVERRIDE_MODES
from agents_runner.environments.model import GH_TASK_BRANCH_CUSTOM_TEMPLATE_DEFAULT
from agents_runner.environments.model import INTERACTIVE_PR_NO_PROMPT_MODE_AUTO_CREATE
from agents_runner.environments.model import INTERACTIVE_PR_NO_PROMPT_MODE_MANUAL_REVIEW
from agents_runner.gh.git_ops import parse_github_url
from agents_runner.terminal_apps import detect_terminal_options
from agents_runner.terminal_apps import launch_in_terminal
from agents_runner.ui.constants import CARD_MARGINS
from agents_runner.ui.constants import CARD_SPACING
from agents_runner.ui.constants import HEADER_MARGINS
from agents_runner.ui.constants import HEADER_SPACING
from agents_runner.ui.constants import GRID_VERTICAL_SPACING
from agents_runner.ui.constants import LEFT_NAV_BUTTON_SPACING
from agents_runner.ui.constants import LEFT_NAV_COMPACT_THRESHOLD
from agents_runner.ui.constants import LEFT_NAV_PANEL_WIDTH
from agents_runner.ui.dialogs.themed_dialog import ThemedDialog
from agents_runner.ui.graphics import EnvironmentTintOverlay
from agents_runner.ui.utils import apply_environment_combo_tint
from agents_runner.ui.utils import stain_color
from agents_runner.ui.utils.form_helpers import add_grid_row
from agents_runner.ui.utils.form_helpers import configure_form_grid
from agents_runner.ui.utils.form_helpers import create_stretch_row
from agents_runner.ui.widgets import GlassCard
from agents_runner.ui.widgets import EdgeFadeScrollArea


@dataclass(frozen=True)
class _WizardPaneSpec:
    key: str
    title: str
    subtitle: str
    section: str


@dataclass(frozen=True)
class _WizardEnvironmentData:
    env_id: str
    name: str
    color: str
    workspace_type: str
    workspace_target: str
    headless_desktop_enabled: bool
    container_caching_enabled: bool
    gh_context_enabled: bool
    agentsnova_auto_review_mode: str
    agentsnova_auto_reactions_mode: str
    agentsnova_marker_comment_mode: str
    interactive_pr_prompt_enabled: bool
    interactive_pr_no_prompt_mode: str
    gpu_override_mode: str
    opencode_interactive_mode: str
    max_agents_running: int
    use_cross_agents: bool
    cache_desktop_build: bool
    cache_system_preflight_enabled: bool
    cache_settings_preflight_enabled: bool
    gh_branch_work_mode: str
    gh_task_branch_naming_style: str
    gh_task_branch_custom_template: str


class NewEnvironmentWizard(ThemedDialog):
    environment_created = Signal(object)

    TEST_DIR_BASE = "/tmp/agent-runner-env-test"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("NewEnvironmentWizard")
        self._clone_test_passed = False
        self._test_folder = ""
        self._advanced_modified = False
        self._clone_check_count = 0
        self._clone_test_url = ""
        self._current_page_index = 0
        self._pane_animation: QParallelAnimationGroup | None = None
        self._pane_rest_pos: QPoint | None = None
        self._compact_mode = False
        self._active_pane_key = ""
        self._pane_index_by_key: dict[str, int] = {}
        self._nav_buttons: dict[str, QToolButton] = {}
        self._suggested_color: str = self._pick_new_environment_color()
        self._pane_specs = self._default_pane_specs()
        self.setWindowTitle("New Environment Wizard")
        self.setMinimumWidth(900)
        self.setMinimumHeight(620)

        layout = self.content_layout()
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(CARD_SPACING)

        header = GlassCard()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(*HEADER_MARGINS)
        header_layout.setSpacing(HEADER_SPACING)

        title = QLabel("New Environment Wizard")
        title.setStyleSheet("font-size: 18px; font-weight: 750;")
        header_layout.addWidget(title)
        header_layout.addStretch(1)
        layout.addWidget(header)

        self._card = GlassCard()
        card_layout = QVBoxLayout(self._card)
        card_layout.setContentsMargins(*CARD_MARGINS)
        card_layout.setSpacing(CARD_SPACING)

        self._compact_nav = QComboBox()
        self._compact_nav.setObjectName("SettingsCompactNav")
        self._compact_nav.setVisible(False)
        self._compact_nav.currentIndexChanged.connect(self._on_compact_nav_changed)
        card_layout.addWidget(self._compact_nav)

        panes_layout = QHBoxLayout()
        panes_layout.setContentsMargins(0, 0, 0, 0)
        panes_layout.setSpacing(14)

        self._nav_scroll = EdgeFadeScrollArea()
        self._nav_scroll.setObjectName("SettingsNavScrollArea")
        self._nav_scroll.setFixedWidth(LEFT_NAV_PANEL_WIDTH)

        self._nav_panel = QWidget()
        self._nav_panel.setObjectName("SettingsNavPanel")
        nav_layout = QVBoxLayout(self._nav_panel)
        nav_layout.setContentsMargins(10, 10, 10, 10)
        nav_layout.setSpacing(LEFT_NAV_BUTTON_SPACING)
        self._nav_scroll.setWidget(self._nav_panel)

        self._right_panel = QWidget()
        self._right_panel.setObjectName("SettingsPaneHost")
        right_layout = QVBoxLayout(self._right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        self._page_stack = QStackedWidget()
        self._page_stack.setObjectName("SettingsPageStack")
        right_layout.addWidget(self._page_stack, 1)

        panes_layout.addWidget(self._nav_scroll)
        panes_layout.addWidget(self._right_panel, 1)
        card_layout.addLayout(panes_layout, 1)
        layout.addWidget(self._card, 1)

        self._build_controls()
        self._build_pages()
        self._build_navigation(nav_layout)
        self._build_button_bar(layout)
        self._connect_dependency_signals()
        self._sync_dependent_controls()
        self._connect_advanced_signals()
        self._set_current_page(0, animate=False)
        self._on_source_changed(0)
        self._update_navigation_mode()

        self._tint_overlay = EnvironmentTintOverlay(self, alpha=13)
        self._tint_overlay.setGeometry(self.rect())
        self._tint_overlay.raise_()
        self._apply_environment_tint()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._update_navigation_mode()
        if not hasattr(self, "_tint_overlay"):
            return
        self._tint_overlay.setGeometry(self.rect())
        self._tint_overlay.raise_()

    def _default_pane_specs(self) -> list[_WizardPaneSpec]:
        return [
            _WizardPaneSpec(
                key="general",
                title="General Info",
                subtitle="Name the environment and choose where its workspace comes from.",
                section="Setup",
            ),
            _WizardPaneSpec(
                key="runtime_agents",
                title="Runtime & Agents",
                subtitle="Runtime overrides, agent capacity, and cross-agent controls.",
                section="Runtime",
            ),
            _WizardPaneSpec(
                key="desktop_cache",
                title="Desktop & Cache",
                subtitle="Desktop runtime and cached setup layer behavior.",
                section="Runtime",
            ),
            _WizardPaneSpec(
                key="github_behavior",
                title="GitHub Behavior",
                subtitle="Repository context, branch workflow, and interactive PR handling.",
                section="Automation",
            ),
            _WizardPaneSpec(
                key="agentsnova_automation",
                title="AgentsNova Automation",
                subtitle="Environment overrides for @agentsnova automation.",
                section="Automation",
            ),
        ]

    def _build_controls(self) -> None:
        self._name_input = QLineEdit()
        self._name_input.setPlaceholderText("e.g., 'My Repo (Remote)'")
        self._name_input.setToolTip("A label you'll recognize later (e.g., 'My Repo (Remote)')")
        self._name_input.textChanged.connect(self._update_next_button)

        self._source_combo = QComboBox()
        self._source_combo.addItem("Use a folder workspace", WORKSPACE_MOUNTED)
        self._source_combo.addItem("Clone a repo workspace", WORKSPACE_CLONED)
        self._source_combo.setToolTip("Both run in a container; this only changes the workspace source")
        self._source_combo.currentIndexChanged.connect(self._on_source_changed)

        self._folder_widget = QWidget()
        f_layout = QVBoxLayout(self._folder_widget)
        f_layout.setContentsMargins(0, 0, 0, 0)
        f_layout.setSpacing(4)
        folder_label = QLabel("Folder Path:")
        folder_label.setToolTip("Path to an existing folder that will be used as the workspace")
        f_layout.addWidget(folder_label)
        f_row = QHBoxLayout()
        f_row.setSpacing(4)
        self._folder_input = QLineEdit()
        self._folder_input.setToolTip("Path to an existing folder that will be used as the workspace")
        self._folder_input.textChanged.connect(self._validate_folder)
        f_row.addWidget(self._folder_input, 1)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_folder)
        f_row.addWidget(browse_btn, 0)
        f_layout.addLayout(f_row)
        self._folder_validation = QLabel()
        self._folder_validation.setStyleSheet("font-size: 11px;")
        f_layout.addWidget(self._folder_validation)

        self._clone_widget = QWidget()
        c_layout = QVBoxLayout(self._clone_widget)
        c_layout.setContentsMargins(0, 0, 0, 0)
        c_layout.setSpacing(4)
        repo_label = QLabel("Repository URL:")
        repo_label.setToolTip("GitHub shorthand (owner/repo) or full URL (https://github.com/owner/repo.git)")
        c_layout.addWidget(repo_label)
        self._clone_input = QLineEdit()
        self._clone_input.setPlaceholderText("owner/repo or full URL")
        self._clone_input.setToolTip("GitHub shorthand (owner/repo) or full URL (https://github.com/owner/repo.git)")
        self._clone_input.textChanged.connect(self._validate_clone)
        c_layout.addWidget(self._clone_input)
        self._clone_validation = QLabel()
        self._clone_validation.setStyleSheet("font-size: 11px;")
        c_layout.addWidget(self._clone_validation)

        self._color_combo = QComboBox()
        self._color_combo.setToolTip("Used for identifying environments in the UI")
        for stain in ALLOWED_STAINS:
            self._color_combo.addItem(stain.title(), stain)
        idx = self._color_combo.findData(self._suggested_color)
        if idx >= 0:
            self._color_combo.blockSignals(True)
            try:
                self._color_combo.setCurrentIndex(idx)
            finally:
                self._color_combo.blockSignals(False)
        self._color_combo.currentIndexChanged.connect(self._on_color_changed)

        self._gpu_override_combo = QComboBox()
        for label, value in (
            ("Inherit global setting", "inherit"),
            ("Enabled", "enabled"),
            ("Disabled", "disabled"),
        ):
            if value in GPU_OVERRIDE_MODES:
                self._gpu_override_combo.addItem(label, value)
        self._gpu_override_combo.setToolTip("Override the global GPU runtime setting for this environment.")

        self._opencode_interactive_combo = QComboBox()
        for label, value in (
            ("Inherit global setting", "inherit"),
            ("Terminal", "terminal"),
            ("Web", "web"),
            ("Ask", "ask"),
        ):
            if value in OPENCODE_INTERACTIVE_OVERRIDE_MODES:
                self._opencode_interactive_combo.addItem(label, value)
        self._opencode_interactive_combo.setToolTip("Override the global OpenCode Run Interactive launch mode.")

        self._max_agents_running = QLineEdit()
        self._max_agents_running.setPlaceholderText("-1")
        self._max_agents_running.setToolTip(
            "Maximum agents running at the same time for this environment. Set to -1 for no limit.\n"
            "Tip: For local-folder workspaces, set this to 1 to avoid agents fighting over setup/files."
        )
        self._max_agents_running.setValidator(QIntValidator(-1, 10_000_000, self))
        self._max_agents_running.setMaximumWidth(150)

        self._use_cross_agents = QCheckBox("Use cross agents")
        self._use_cross_agents.setToolTip(
            "When enabled, allows agent instances from the Agents pane to be mounted\n"
            "as cross-agents in task containers. Configure the allowlist in the Agents pane."
        )

        self._headless_desktop_enabled = QCheckBox("Enable headless desktop")
        self._headless_desktop_enabled.setToolTip(
            "When enabled, agent runs for this environment will start a noVNC desktop.\n"
            "Settings → Force headless desktop overrides this setting."
        )

        self._cache_desktop_build = QCheckBox("Cache desktop build")
        self._cache_desktop_build.setToolTip(
            "When enabled, desktop components are pre-installed in a cached Docker image.\n"
            "This reduces task startup time from 45-90s to 2-5s.\n"
            "Requires 'Enable headless desktop' to be enabled.\n\n"
            "Image is automatically rebuilt when scripts change."
        )
        self._cache_desktop_build.setEnabled(False)

        self._cache_system_preflight_enabled = QCheckBox("Cache system preflight")
        self._cache_system_preflight_enabled.setToolTip(
            "When enabled, the system preflight (pixelarch_yay.sh) is cached as an image layer."
        )
        self._cache_system_preflight_enabled.setEnabled(False)

        self._cache_settings_preflight_enabled = QCheckBox("Cache settings preflight")
        self._cache_settings_preflight_enabled.setToolTip(
            "When enabled, the Settings preflight script is cached as an image layer."
        )
        self._cache_settings_preflight_enabled.setEnabled(False)

        self._container_caching_enabled = QCheckBox("Enable container caching")
        self._container_caching_enabled.setToolTip(
            "When enabled, selected preflight phases build cached Docker layers.\n"
            "Configure phase cache toggles in the Caching pane."
        )

        self._gh_context_enabled = QCheckBox("Enable GitHub context")
        self._gh_context_enabled.setToolTip(
            "When enabled, repository context (URL, branch, commit) is provided to the agent.\n"
            "For GitHub-managed environments: Always available.\n"
            "For folder-managed environments: Only if folder is a git repository.\n\n"
            "Note: This does NOT provide GitHub authentication - that is separate."
        )

        self._gh_branch_work_mode = QComboBox()
        for label, value in (
            ("Use task branches", "task_branch"),
            ("Work on direct base", "direct_base"),
        ):
            if value in GH_BRANCH_WORK_MODES:
                self._gh_branch_work_mode.addItem(label, value)
        self._gh_branch_work_mode.setToolTip(
            "Controls whether GitHub work for this environment uses per-task branches or works directly on the selected base branch."
        )

        self._gh_task_branch_naming_style = QComboBox()
        for label, value in (
            ("Standard", "standard"),
            ("Songs", "songs"),
            ("Foods", "foods"),
            ("Animals", "animals"),
            ("Colors", "colors"),
            ("Space", "space"),
            ("Custom", "custom"),
        ):
            if value in GH_TASK_BRANCH_NAMING_STYLES:
                self._gh_task_branch_naming_style.addItem(label, value)
        self._gh_task_branch_naming_style.setToolTip(
            "Controls how future task branches are named for this environment."
        )

        self._gh_task_branch_custom_template = QLineEdit()
        self._gh_task_branch_custom_template.setPlaceholderText(GH_TASK_BRANCH_CUSTOM_TEMPLATE_DEFAULT)
        self._gh_task_branch_custom_template.setToolTip(
            "Custom template used when task branch naming style is set to Custom."
        )
        self._gh_task_branch_custom_template_helper = QLabel("Custom templates can use placeholders like {task_id}.")
        self._gh_task_branch_custom_template_helper.setObjectName("SettingsPaneSubtitle")

        self._interactive_pr_prompt_enabled = QCheckBox("Show interactive PR prompt")
        self._interactive_pr_prompt_enabled.setToolTip(
            "When enabled, interactive GitHub work can keep showing the PR prompt for this environment."
        )
        self._interactive_pr_prompt_enabled.setChecked(True)

        self._interactive_pr_no_prompt_mode = QComboBox()
        for label, value in (
            ("Auto-create PR after interactive run", INTERACTIVE_PR_NO_PROMPT_MODE_AUTO_CREATE),
            ("Manual only (Review -> Create PR)", INTERACTIVE_PR_NO_PROMPT_MODE_MANUAL_REVIEW),
        ):
            if value in INTERACTIVE_PR_NO_PROMPT_MODES:
                self._interactive_pr_no_prompt_mode.addItem(label, value)
        self._interactive_pr_no_prompt_mode.setToolTip(
            "Used when 'Show interactive PR prompt' is disabled.\n"
            "Manual mode means you can enter the task, then click Review -> Create PR yourself."
        )

        self._auto_review_combo = QComboBox()
        for label, value in (
            ("Inherit global setting", "inherit"),
            ("Enabled", "enabled"),
            ("Disabled", "disabled"),
        ):
            if value in AGENTSNOVA_AUTO_MODES:
                self._auto_review_combo.addItem(label, value)
        self._auto_review_combo.setToolTip(
            "Override whether @agentsnova mentions auto-queue review work for this environment."
        )

        self._auto_reactions_combo = QComboBox()
        for label, value in (
            ("Inherit global setting", "inherit"),
            ("Enabled", "enabled"),
            ("Disabled", "disabled"),
        ):
            if value in AGENTSNOVA_AUTO_MODES:
                self._auto_reactions_combo.addItem(label, value)
        self._auto_reactions_combo.setToolTip(
            "Override whether @agentsnova queue triggers add GitHub reactions for this environment."
        )

        self._marker_comment_combo = QComboBox()
        for label, value in (
            ("Inherit global setting", "inherit"),
            ("Keep", "keep"),
            ("Delete after 15s", "delete_after_15s"),
            ("Disabled", "disabled"),
        ):
            if value in AGENTSNOVA_MARKER_COMMENT_MODES:
                self._marker_comment_combo.addItem(label, value)
        self._marker_comment_combo.setToolTip(
            "Override marker-comment behavior for @agentsnova auto-review activity in this environment."
        )

    def _build_pages(self) -> None:
        general_page, general_body = self._create_wizard_page(self._pane_specs[0].title, self._pane_specs[0].subtitle)
        general_grid = QGridLayout()
        configure_form_grid(general_grid)
        name_label = QLabel("Environment Name:")
        name_label.setToolTip("A label you'll recognize later (e.g., 'My Repo (Remote)')")
        source_label = QLabel("Workspace Source Type:")
        source_label.setToolTip("Both run in a container; this only changes the workspace source")
        add_grid_row(general_grid, 0, name_label, self._name_input)
        add_grid_row(general_grid, 1, source_label, self._source_combo)
        general_body.addLayout(general_grid)
        general_body.addWidget(self._folder_widget)
        general_body.addWidget(self._clone_widget)
        color_grid = QGridLayout()
        configure_form_grid(color_grid)
        color_label = QLabel("Color:")
        color_label.setToolTip("Used for identifying environments in the UI")
        add_grid_row(color_grid, 0, color_label, self._color_combo)
        general_body.addLayout(color_grid)
        warning = QLabel(
            "⚠ Step 1 choices (workspace source + path/URL) cannot be edited later. To change them, create a new environment."
        )
        warning.setWordWrap(True)
        warning.setStyleSheet(
            "color: #ff9800; font-weight: bold; margin-top: 10px; padding: 8px; background: rgba(255,152,0,0.1);"
        )
        general_body.addWidget(warning)
        general_body.addStretch(1)
        self._register_page("general", general_page)

        runtime_page, runtime_body = self._create_wizard_page(self._pane_specs[1].title, self._pane_specs[1].subtitle)
        runtime_grid = QGridLayout()
        configure_form_grid(runtime_grid)
        cross_agents_row = create_stretch_row(self._use_cross_agents, stretch_index=1)
        add_grid_row(runtime_grid, 0, QLabel("GPU runtime override"), self._gpu_override_combo)
        add_grid_row(runtime_grid, 1, QLabel("OpenCode interactive mode"), self._opencode_interactive_combo)
        add_grid_row(runtime_grid, 2, QLabel("Max agents running"), self._max_agents_running)
        add_grid_row(runtime_grid, 3, QLabel("Cross agents"), cross_agents_row)
        runtime_body.addLayout(runtime_grid)
        runtime_body.addStretch(1)
        self._register_page("runtime_agents", runtime_page)

        desktop_page, desktop_body = self._create_wizard_page(self._pane_specs[2].title, self._pane_specs[2].subtitle)
        desktop_grid = QGridLayout()
        configure_form_grid(desktop_grid)
        headless_desktop_row = create_stretch_row(self._headless_desktop_enabled, stretch_index=1)
        desktop_build_cache_row = create_stretch_row(self._cache_desktop_build, stretch_index=1)
        system_preflight_cache_row = create_stretch_row(self._cache_system_preflight_enabled, stretch_index=1)
        settings_preflight_cache_row = create_stretch_row(self._cache_settings_preflight_enabled, stretch_index=1)
        container_caching_row = create_stretch_row(self._container_caching_enabled, stretch_index=1)
        add_grid_row(desktop_grid, 0, QLabel("Headless desktop"), headless_desktop_row)
        add_grid_row(desktop_grid, 1, QLabel("Desktop build cache"), desktop_build_cache_row)
        add_grid_row(desktop_grid, 2, QLabel("System preflight cache"), system_preflight_cache_row)
        add_grid_row(desktop_grid, 3, QLabel("Settings preflight cache"), settings_preflight_cache_row)
        add_grid_row(desktop_grid, 4, QLabel("Container caching"), container_caching_row)
        desktop_body.addLayout(desktop_grid)
        desktop_body.addStretch(1)
        self._register_page("desktop_cache", desktop_page)

        github_page, github_body = self._create_wizard_page(self._pane_specs[3].title, self._pane_specs[3].subtitle)
        github_grid = QGridLayout()
        configure_form_grid(github_grid)
        custom_template_layout = QVBoxLayout()
        custom_template_layout.setContentsMargins(0, 0, 0, 0)
        custom_template_layout.setSpacing(GRID_VERTICAL_SPACING)
        self._gh_task_branch_custom_template_row = QWidget(github_page)
        self._gh_task_branch_custom_template_row.setLayout(custom_template_layout)
        custom_template_layout.addWidget(self._gh_task_branch_custom_template)
        custom_template_layout.addWidget(self._gh_task_branch_custom_template_helper)
        self._gh_task_branch_custom_template_label = QLabel("Custom branch template")
        self._interactive_pr_no_prompt_mode_label = QLabel("When prompt is disabled")
        gh_context_row = create_stretch_row(self._gh_context_enabled, stretch_index=1)
        interactive_pr_prompt_row = create_stretch_row(self._interactive_pr_prompt_enabled, stretch_index=1)
        self._interactive_pr_no_prompt_mode_row = create_stretch_row(
            self._interactive_pr_no_prompt_mode, stretch_index=1
        )
        add_grid_row(github_grid, 0, QLabel("GitHub context"), gh_context_row)
        add_grid_row(github_grid, 1, QLabel("Branch workflow"), self._gh_branch_work_mode)
        add_grid_row(github_grid, 2, QLabel("Task branch naming"), self._gh_task_branch_naming_style)
        add_grid_row(
            github_grid, 3, self._gh_task_branch_custom_template_label, self._gh_task_branch_custom_template_row
        )
        add_grid_row(github_grid, 4, QLabel("Interactive PR prompt"), interactive_pr_prompt_row)
        add_grid_row(github_grid, 5, self._interactive_pr_no_prompt_mode_label, self._interactive_pr_no_prompt_mode_row)
        github_body.addLayout(github_grid)
        github_body.addStretch(1)
        self._register_page("github_behavior", github_page)

        agentsnova_page, agentsnova_body = self._create_wizard_page(
            self._pane_specs[4].title, self._pane_specs[4].subtitle
        )
        agentsnova_grid = QGridLayout()
        configure_form_grid(agentsnova_grid)
        add_grid_row(agentsnova_grid, 0, QLabel("Auto review mode"), self._auto_review_combo)
        add_grid_row(agentsnova_grid, 1, QLabel("Auto reactions mode"), self._auto_reactions_combo)
        add_grid_row(agentsnova_grid, 2, QLabel("Marker comment mode"), self._marker_comment_combo)
        agentsnova_body.addLayout(agentsnova_grid)
        agentsnova_body.addStretch(1)
        self._register_page("agentsnova_automation", agentsnova_page)

    def _build_navigation(self, nav_layout: QVBoxLayout) -> None:
        sections: dict[str, list[_WizardPaneSpec]] = {}
        for spec in self._pane_specs:
            sections.setdefault(spec.section, []).append(spec)

        for section_title, specs in sections.items():
            section_label = QLabel(section_title)
            section_label.setObjectName("SettingsNavSection")
            nav_layout.addWidget(section_label)

            for spec in specs:
                button = QToolButton()
                button.setObjectName("SettingsNavButton")
                button.setText(spec.title)
                button.setToolTip(spec.subtitle)
                button.setCheckable(True)
                button.setAutoExclusive(True)
                button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
                button.setFixedHeight(40)
                button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
                button.clicked.connect(lambda checked=False, key=spec.key: self._on_nav_button_clicked(key))
                nav_layout.addWidget(button)
                self._nav_buttons[spec.key] = button
                self._compact_nav.addItem(spec.title, spec.key)
        nav_layout.addStretch(1)

    def _register_page(self, key: str, widget: QWidget) -> None:
        index = self._page_stack.addWidget(widget)
        self._pane_index_by_key[key] = index

    def _on_nav_button_clicked(self, key: str) -> None:
        self._navigate_to_page(key)

    def _on_compact_nav_changed(self, _index: int) -> None:
        key = str(self._compact_nav.currentData() or "").strip()
        if key:
            self._navigate_to_page(key)

    def _navigate_to_page(self, key: str) -> None:
        page_index = self._pane_index_by_key.get(key)
        if page_index is None:
            return
        if page_index > 0 and not self._is_general_info_complete():
            self._set_active_navigation(self._active_pane_key or self._pane_specs[0].key)
            self._update_next_button()
            return
        self._set_current_page(page_index)

    def _build_button_bar(self, parent_layout: QVBoxLayout) -> None:
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        btn_layout.addStretch(1)
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self._on_cancel)
        btn_layout.addWidget(self._cancel_btn)
        self._back_btn = QPushButton("Back")
        self._back_btn.clicked.connect(self._on_back)
        btn_layout.addWidget(self._back_btn)
        self._next_btn = QPushButton("Next")
        self._next_btn.clicked.connect(self._on_next)
        btn_layout.addWidget(self._next_btn)
        parent_layout.addLayout(btn_layout)

    def _create_wizard_page(self, title_text: str, subtitle_text: str) -> tuple[QWidget, QVBoxLayout]:
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(0)

        scroll = EdgeFadeScrollArea(page)
        scroll.setObjectName("SettingsPaneScrollArea")

        content = QWidget(scroll)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(10)

        title = QLabel(title_text)
        title.setObjectName("SettingsPaneTitle")
        subtitle = QLabel(subtitle_text)
        subtitle.setObjectName("SettingsPaneSubtitle")
        subtitle.setWordWrap(True)

        body = QWidget(content)
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(GRID_VERTICAL_SPACING)

        content_layout.addWidget(title)
        content_layout.addWidget(subtitle)
        content_layout.addWidget(body)
        scroll.setWidget(content)
        page_layout.addWidget(scroll, 1)
        return page, body_layout

    def _connect_dependency_signals(self) -> None:
        self._headless_desktop_enabled.toggled.connect(self._on_headless_desktop_toggled)
        self._container_caching_enabled.toggled.connect(self._on_container_caching_toggled)
        self._gh_task_branch_naming_style.currentIndexChanged.connect(self._sync_github_branch_naming_controls)
        self._interactive_pr_prompt_enabled.toggled.connect(self._sync_interactive_pr_controls)

    def _connect_advanced_signals(self) -> None:
        self._gpu_override_combo.currentIndexChanged.connect(self._on_advanced_changed)
        self._opencode_interactive_combo.currentIndexChanged.connect(self._on_advanced_changed)
        self._max_agents_running.textChanged.connect(self._on_advanced_changed)
        self._use_cross_agents.toggled.connect(self._on_advanced_changed)
        self._headless_desktop_enabled.toggled.connect(self._on_advanced_changed)
        self._cache_desktop_build.toggled.connect(self._on_advanced_changed)
        self._cache_system_preflight_enabled.toggled.connect(self._on_advanced_changed)
        self._cache_settings_preflight_enabled.toggled.connect(self._on_advanced_changed)
        self._container_caching_enabled.toggled.connect(self._on_advanced_changed)
        self._gh_context_enabled.toggled.connect(self._on_advanced_changed)
        self._gh_branch_work_mode.currentIndexChanged.connect(self._on_advanced_changed)
        self._gh_task_branch_naming_style.currentIndexChanged.connect(self._on_advanced_changed)
        self._gh_task_branch_custom_template.textChanged.connect(self._on_advanced_changed)
        self._interactive_pr_prompt_enabled.toggled.connect(self._on_advanced_changed)
        self._interactive_pr_no_prompt_mode.currentIndexChanged.connect(self._on_advanced_changed)
        self._auto_review_combo.currentIndexChanged.connect(self._on_advanced_changed)
        self._auto_reactions_combo.currentIndexChanged.connect(self._on_advanced_changed)
        self._marker_comment_combo.currentIndexChanged.connect(self._on_advanced_changed)

    def _sync_dependent_controls(self) -> None:
        self._on_headless_desktop_toggled(self._headless_desktop_enabled.isChecked())
        self._on_container_caching_toggled(self._container_caching_enabled.isChecked())
        self._sync_github_branch_naming_controls()
        self._sync_interactive_pr_controls()

    def _current_stain(self) -> str:
        combo = getattr(self, "_color_combo", None)
        stain = str(combo.currentData() or "").strip().lower() if combo is not None else ""
        return stain or str(self._suggested_color or "").strip().lower()

    def _apply_environment_tint(self) -> None:
        if not hasattr(self, "_tint_overlay"):
            return
        stain = self._current_stain()
        if not stain:
            self._tint_overlay.set_tint_color(None)
            return
        self._tint_overlay.set_tint_color(stain_color(stain))
        if hasattr(self, "_color_combo"):
            apply_environment_combo_tint(self._color_combo, stain)

    def _on_source_changed(self, index: int) -> None:
        is_folder = index == 0
        self._folder_widget.setVisible(is_folder)
        self._clone_widget.setVisible(not is_folder)
        if is_folder:
            self._validate_folder()
        else:
            self._clone_test_passed = False
            self._clone_test_url = ""
            self._validate_clone()
        self._update_next_button()

    def _browse_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select Workspace Folder")
        if folder:
            self._folder_input.setText(folder)

    def _validate_folder(self) -> None:
        path = self._folder_input.text().strip()
        if not path:
            self._folder_validation.setText("")
            self._update_next_button()
            return
        if not os.path.exists(path):
            self._folder_validation.setText("✗ Path does not exist")
            self._folder_validation.setStyleSheet("color: #f44336; font-size: 11px;")
            self._update_next_button()
            return
        if not os.path.isdir(path):
            self._folder_validation.setText("✗ Path is not a directory")
            self._folder_validation.setStyleSheet("color: #f44336; font-size: 11px;")
            self._update_next_button()
            return
        if not os.access(path, os.R_OK):
            self._folder_validation.setText("✗ Path is not readable")
            self._folder_validation.setStyleSheet("color: #f44336; font-size: 11px;")
            self._update_next_button()
            return
        if not os.access(path, os.W_OK):
            self._folder_validation.setText("✗ Path is not writable")
            self._folder_validation.setStyleSheet("color: #f44336; font-size: 11px;")
            self._update_next_button()
            return
        self._folder_validation.setText("✓ Valid folder")
        self._folder_validation.setStyleSheet("color: #4caf50; font-size: 11px;")
        self._update_next_button()

    def _expand_repo_url(self, url: str) -> str:
        """Convert GitHub shorthand (owner/repo) to full URL."""
        url = url.strip()
        if not url:
            return ""
        if url.startswith(("https://", "http://", "git@", "ssh://")):
            return url
        owner, repo = parse_github_url(url)
        if owner and repo:
            return f"https://github.com/{owner}/{repo}.git"
        return url

    def _validate_clone(self) -> None:
        url = self._clone_input.text().strip()
        expanded_url = self._expand_repo_url(url) if url and " " not in url else ""
        if self._clone_test_passed and expanded_url != self._clone_test_url:
            self._clone_test_passed = False
        if not url:
            self._clone_validation.setText("")
            self._update_next_button()
            return
        if " " in url:
            self._clone_validation.setText("✗ URL cannot contain spaces")
            self._clone_validation.setStyleSheet("color: #f44336; font-size: 11px;")
            self._update_next_button()
            return
        owner, repo = parse_github_url(url)
        if owner and repo:
            self._clone_validation.setText("✓ Valid format")
            self._clone_validation.setStyleSheet("color: #4caf50; font-size: 11px;")
        else:
            self._clone_validation.setText("✗ Use owner/repo or a valid GitHub URL")
            self._clone_validation.setStyleSheet("color: #f44336; font-size: 11px;")
        self._update_next_button()

    def _update_next_button(self) -> None:
        if not hasattr(self, "_next_btn"):
            return
        self._back_btn.setEnabled(self._current_page_index > 0)
        self._update_page_lock_state()
        if self._current_page_index == 0:
            if self._source_combo.currentIndex() == 0:
                self._next_btn.setText("Next")
                self._next_btn.setEnabled(self._validate_step1())
            elif self._clone_test_passed:
                self._next_btn.setText("Next")
                self._next_btn.setEnabled(True)
            else:
                name_valid = bool(self._name_input.text().strip())
                clone_valid = bool(self._clone_input.text().strip() and "✓" in self._clone_validation.text())
                self._next_btn.setText("Test")
                self._next_btn.setEnabled(name_valid and clone_valid)
            return
        if self._current_page_index >= len(self._pane_specs) - 1:
            self._next_btn.setText("OK" if self._advanced_modified else "Skip")
            self._next_btn.setEnabled(True)
            return
        self._next_btn.setText("Next")
        self._next_btn.setEnabled(True)

    def _is_general_info_complete(self) -> bool:
        if not self._validate_step1():
            return False
        return self._source_combo.currentIndex() == 0 or self._clone_test_passed

    def _update_page_lock_state(self) -> None:
        pages_unlocked = self._is_general_info_complete()
        for spec in self._pane_specs:
            page_index = self._pane_index_by_key.get(spec.key, 0)
            button = self._nav_buttons.get(spec.key)
            if button is not None:
                button.setEnabled(page_index == 0 or pages_unlocked)

    def _validate_step1(self) -> bool:
        if not self._name_input.text().strip():
            return False
        if self._source_combo.currentIndex() == 0:
            path = self._folder_input.text().strip()
            if not path or not os.path.isdir(path):
                return False
            if not os.access(path, os.R_OK | os.W_OK):
                return False
            return True
        url = self._clone_input.text().strip()
        if not url or " " in url:
            return False
        owner, repo = parse_github_url(url)
        return bool(owner and repo)

    def _set_current_page(self, index: int, *, animate: bool = True) -> None:
        max_index = max(0, self._page_stack.count() - 1)
        page_index = min(max(index, 0), max_index)
        if page_index > 0 and not self._is_general_info_complete():
            page_index = 0

        current_index = self._page_stack.currentIndex()
        self._current_page_index = page_index
        if current_index != page_index:
            if current_index < 0 or not animate:
                self._page_stack.setCurrentIndex(page_index)
            else:
                forward = page_index > current_index
                self._page_stack.setCurrentIndex(page_index)
                self._animate_stack(forward=forward)

        key = self._pane_specs[page_index].key if self._pane_specs else ""
        if key:
            self._set_active_navigation(key)
        self._update_next_button()

    def _set_active_navigation(self, key: str) -> None:
        self._active_pane_key = key
        for pane_key, button in self._nav_buttons.items():
            with QSignalBlocker(button):
                button.setChecked(pane_key == key)

        idx = self._compact_nav.findData(key)
        if idx >= 0:
            with QSignalBlocker(self._compact_nav):
                self._compact_nav.setCurrentIndex(idx)

    def _animate_stack(self, *, forward: bool) -> None:
        if self._pane_animation is not None:
            self._pane_animation.stop()
            self._pane_animation = None

        if self._pane_rest_pos is not None:
            self._page_stack.move(self._pane_rest_pos)
        self._page_stack.setGraphicsEffect(None)  # pyright: ignore[reportArgumentType]

        base_pos = self._page_stack.pos()
        self._pane_rest_pos = QPoint(base_pos)

        offset = 16 if forward else -16
        start_pos = QPoint(base_pos.x() + offset, base_pos.y())

        effect = QGraphicsOpacityEffect(self._page_stack)
        effect.setOpacity(0.0)
        self._page_stack.setGraphicsEffect(effect)
        self._page_stack.move(start_pos)

        pos_anim = QPropertyAnimation(self._page_stack, b"pos", self)
        pos_anim.setDuration(210)
        pos_anim.setStartValue(start_pos)
        pos_anim.setEndValue(base_pos)
        pos_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        opacity_anim = QPropertyAnimation(effect, b"opacity", self)
        opacity_anim.setDuration(210)
        opacity_anim.setStartValue(0.0)
        opacity_anim.setEndValue(1.0)
        opacity_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        group = QParallelAnimationGroup(self)
        group.addAnimation(pos_anim)
        group.addAnimation(opacity_anim)

        def _cleanup() -> None:
            if self._pane_rest_pos is not None:
                self._page_stack.move(self._pane_rest_pos)
            self._page_stack.setGraphicsEffect(None)  # pyright: ignore[reportArgumentType]
            self._pane_animation = None

        group.finished.connect(_cleanup)
        group.start()
        self._pane_animation = group

    def _update_navigation_mode(self) -> None:
        compact = self.width() < LEFT_NAV_COMPACT_THRESHOLD
        if compact == self._compact_mode:
            return
        self._compact_mode = compact
        self._compact_nav.setVisible(compact)
        self._nav_scroll.setVisible(not compact)

    def _on_next(self) -> None:
        if self._current_page_index == 0:
            if self._source_combo.currentIndex() == 1 and not self._clone_test_passed:
                self._run_clone_test()
                return
            if not self._validate_step1():
                return
        if self._current_page_index >= len(self._pane_specs) - 1:
            self._on_finish()
            return
        self._set_current_page(self._current_page_index + 1)

    def _run_clone_test(self) -> None:
        url = self._expand_repo_url(self._clone_input.text().strip())
        self._clone_test_passed = False
        self._clone_test_url = url
        name = self._name_input.text().strip() or "test"
        sanitized = re.sub(r"[^a-zA-Z0-9_-]", "_", name)[:50]
        test_id = hashlib.md5(url.encode()).hexdigest()[:8]
        self._test_folder = os.path.join(self.TEST_DIR_BASE, f"{sanitized}-{test_id}")
        if os.path.exists(self._test_folder):
            shutil.rmtree(self._test_folder, ignore_errors=True)
        os.makedirs(self.TEST_DIR_BASE, exist_ok=True)
        self._clone_check_count = 0
        terminals = detect_terminal_options()
        if not terminals:
            self._clone_validation.setText("✗ No terminal found on system")
            self._clone_validation.setStyleSheet("color: #f44336; font-size: 11px;")
            self._next_btn.setText("Try test again")
            return
        script = f"""
echo "Testing git clone..."
echo "URL: {url}"
echo "Target: {self._test_folder}"
echo ""
git clone "{url}" "{self._test_folder}"
echo ""
echo "Test complete. Press Enter to close..."
read
"""
        terminal_launched = False
        for terminal in terminals:
            try:
                launch_in_terminal(terminal, script, cwd="/tmp")
                terminal_launched = True
                QTimer.singleShot(2000, self._check_clone_result)
                break
            except Exception:
                continue
        if not terminal_launched:
            self._clone_validation.setText("✗ Failed to launch terminal")
            self._clone_validation.setStyleSheet("color: #f44336; font-size: 11px;")
            self._next_btn.setText("Try test again")

    def _check_clone_result(self) -> None:
        self._clone_check_count += 1
        if os.path.isdir(self._test_folder) and os.path.isdir(os.path.join(self._test_folder, ".git")):
            if self._expand_repo_url(self._clone_input.text().strip()) != self._clone_test_url:
                self._clone_test_passed = False
                self._clone_validation.setText("✗ URL changed after clone test")
                self._clone_validation.setStyleSheet("color: #f44336; font-size: 11px;")
                self._update_next_button()
                return
            self._clone_test_passed = True
            self._clone_validation.setText("✓ Clone test passed")
            self._clone_validation.setStyleSheet("color: #4caf50; font-size: 11px;")
            self._update_next_button()
        elif self._clone_check_count >= 30:
            self._clone_validation.setText("✗ Clone test timeout (60s)")
            self._clone_validation.setStyleSheet("color: #f44336; font-size: 11px;")
            self._next_btn.setText("Try test again")
        else:
            QTimer.singleShot(2000, self._check_clone_result)

    def _on_back(self) -> None:
        self._set_current_page(self._current_page_index - 1)

    def _on_cancel(self) -> None:
        self.reject()

    def _on_advanced_changed(self, *_args: object) -> None:
        self._advanced_modified = True
        self._update_next_button()

    def _on_color_changed(self) -> None:
        self._apply_environment_tint()

    def _on_headless_desktop_toggled(self, checked: bool) -> None:
        self._cache_desktop_build.setEnabled(checked)
        if not checked:
            self._cache_desktop_build.setChecked(False)

    def _on_container_caching_toggled(self, checked: bool) -> None:
        for checkbox in (
            self._cache_system_preflight_enabled,
            self._cache_settings_preflight_enabled,
        ):
            checkbox.setEnabled(checked)
            if not checked:
                checkbox.setChecked(False)

    def _sync_github_branch_naming_controls(self) -> None:
        show_custom_template = self._current_combo_data(self._gh_task_branch_naming_style, "standard") == "custom"
        self._gh_task_branch_custom_template_label.setVisible(show_custom_template)
        self._gh_task_branch_custom_template_row.setVisible(show_custom_template)
        self._gh_task_branch_custom_template.setVisible(show_custom_template)
        self._gh_task_branch_custom_template_helper.setVisible(show_custom_template)

    def _sync_interactive_pr_controls(self) -> None:
        show_no_prompt_mode = not bool(self._interactive_pr_prompt_enabled.isChecked())
        self._interactive_pr_no_prompt_mode_label.setVisible(show_no_prompt_mode)
        self._interactive_pr_no_prompt_mode_row.setVisible(show_no_prompt_mode)
        self._interactive_pr_no_prompt_mode.setVisible(show_no_prompt_mode)
        self._interactive_pr_no_prompt_mode.setEnabled(show_no_prompt_mode)

    def _on_finish(self) -> None:
        if not self._validate_step1() or (self._source_combo.currentIndex() == 1 and not self._clone_test_passed):
            self._set_current_page(0)
            return
        env = self._create_environment()
        save_environment(env)

        environments = load_environments()
        if "default" in environments and env.env_id != "default":
            delete_environment("default")

        self.environment_created.emit(env)
        self.accept()

    def _create_environment(self) -> Environment:
        data = self._collect_wizard_data()
        env = Environment(
            env_id=data.env_id,
            name=data.name,
            color=data.color,
            gh_management_locked=True,
            workspace_type=data.workspace_type,
            workspace_target=data.workspace_target,
            headless_desktop_enabled=data.headless_desktop_enabled,
            container_caching_enabled=data.container_caching_enabled,
            gh_context_enabled=data.gh_context_enabled,
            agentsnova_auto_review_mode=data.agentsnova_auto_review_mode,
            agentsnova_auto_reactions_mode=data.agentsnova_auto_reactions_mode,
            agentsnova_marker_comment_mode=data.agentsnova_marker_comment_mode,
            interactive_pr_prompt_enabled=data.interactive_pr_prompt_enabled,
            interactive_pr_no_prompt_mode=data.interactive_pr_no_prompt_mode,
            setup_agents_missing_prompt_enabled=False,
            interactive_pull_before_run_enabled=True,
            gpu_override_mode=data.gpu_override_mode,
            opencode_interactive_mode=data.opencode_interactive_mode,
            max_agents_running=data.max_agents_running,
            use_cross_agents=data.use_cross_agents,
            cache_desktop_build=data.cache_desktop_build,
            cache_system_preflight_enabled=data.cache_system_preflight_enabled,
            cache_settings_preflight_enabled=data.cache_settings_preflight_enabled,
            gh_branch_work_mode=data.gh_branch_work_mode,
            gh_task_branch_naming_style=data.gh_task_branch_naming_style,
            gh_task_branch_custom_template=data.gh_task_branch_custom_template,
        )
        return env

    def _collect_wizard_data(self) -> _WizardEnvironmentData:
        env_id = f"env-{uuid4().hex[:8]}"
        name = self._name_input.text().strip()
        if self._source_combo.currentIndex() == 0:
            workspace_target = self._folder_input.text().strip()
            workspace_type = WORKSPACE_MOUNTED
        else:
            workspace_target = self._expand_repo_url(self._clone_input.text().strip())
            workspace_type = WORKSPACE_CLONED
        max_agents_text = str(self._max_agents_running.text() or "-1").strip()
        try:
            max_agents_running = int(max_agents_text)
        except ValueError:
            max_agents_running = -1
        return _WizardEnvironmentData(
            env_id=env_id,
            name=name,
            color=self._current_stain(),
            workspace_type=workspace_type,
            workspace_target=workspace_target,
            headless_desktop_enabled=self._headless_desktop_enabled.isChecked(),
            container_caching_enabled=self._container_caching_enabled.isChecked(),
            gh_context_enabled=self._gh_context_enabled.isChecked(),
            agentsnova_auto_review_mode=self._current_combo_data(self._auto_review_combo, "inherit"),
            agentsnova_auto_reactions_mode=self._current_combo_data(self._auto_reactions_combo, "inherit"),
            agentsnova_marker_comment_mode=self._current_combo_data(self._marker_comment_combo, "inherit"),
            interactive_pr_prompt_enabled=self._interactive_pr_prompt_enabled.isChecked(),
            interactive_pr_no_prompt_mode=self._current_combo_data(
                self._interactive_pr_no_prompt_mode,
                INTERACTIVE_PR_NO_PROMPT_MODE_AUTO_CREATE,
            ),
            gpu_override_mode=self._current_combo_data(self._gpu_override_combo, "inherit"),
            opencode_interactive_mode=self._current_combo_data(self._opencode_interactive_combo, "inherit"),
            max_agents_running=max_agents_running,
            use_cross_agents=self._use_cross_agents.isChecked(),
            cache_desktop_build=self._cache_desktop_build.isChecked(),
            cache_system_preflight_enabled=self._cache_system_preflight_enabled.isChecked(),
            cache_settings_preflight_enabled=self._cache_settings_preflight_enabled.isChecked(),
            gh_branch_work_mode=self._current_combo_data(self._gh_branch_work_mode, "task_branch"),
            gh_task_branch_naming_style=self._current_combo_data(self._gh_task_branch_naming_style, "standard"),
            gh_task_branch_custom_template=self._gh_task_branch_custom_template.text().strip()
            or GH_TASK_BRANCH_CUSTOM_TEMPLATE_DEFAULT,
        )

    @staticmethod
    def _current_combo_data(combo: QComboBox, default: str) -> str:
        value = combo.currentData()
        selected = str(default if value is None else value).strip()
        return selected or default

    def _pick_new_environment_color(self) -> str:
        envs = load_environments()
        used = {env.normalized_color() for env in envs.values()}
        unused = [stain for stain in ALLOWED_STAINS if stain not in used]
        if unused and random.random() < 0.9:
            return random.choice(unused)
        return random.choice(ALLOWED_STAINS)
