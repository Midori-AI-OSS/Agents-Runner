from __future__ import annotations

import os
from dataclasses import dataclass

from PySide6.QtCore import Qt
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
from PySide6.QtWidgets import QSizePolicy
from PySide6.QtWidgets import QToolButton
from PySide6.QtWidgets import QVBoxLayout
from PySide6.QtWidgets import QWidget

from agents_runner.environments import ALLOWED_STAINS
from agents_runner.environments import Environment
from agents_runner.environments import WORKSPACE_CLONED
from agents_runner.environments import WORKSPACE_MOUNTED
from agents_runner.environments import WORKSPACE_NONE
from agents_runner.environments.model import (
    GH_TASK_BRANCH_CUSTOM_TEMPLATE_DEFAULT,
    INTERACTIVE_PR_NO_PROMPT_MODE_AUTO_CREATE,
    INTERACTIVE_PR_NO_PROMPT_MODE_MANUAL_REVIEW,
)
from agents_runner.ui.constants import (
    BUTTON_ROW_SPACING,
    GRID_VERTICAL_SPACING,
    STANDARD_BUTTON_WIDTH,
)
from agents_runner.ui.utils.form_helpers import (
    add_grid_row,
    configure_form_grid,
    create_stretch_row,
)
from agents_runner.ui.pages.github_trust import collect_seed_usernames_for_environment
from agents_runner.ui.pages.github_username_list import GitHubUsernameListWidget
from agents_runner.ui.pages.environments_agents import AgentsTabWidget
from agents_runner.ui.pages.environments_env_vars import EnvVarsTabWidget
from agents_runner.ui.pages.environments_mounts import MountsTabWidget
from agents_runner.ui.pages.environments_ports import PortsTabWidget
from agents_runner.ui.pages.environments_prompts import PromptsTabWidget
from agents_runner.ui.widgets import ArtifactSyntaxHighlighter, EdgeFadeScrollArea


@dataclass(frozen=True)
class _EnvironmentPaneSpec:
    key: str
    title: str
    subtitle: str
    section: str


class EnvironmentsFormMixin:
    def _default_pane_specs(self) -> list[_EnvironmentPaneSpec]:
        return [
            _EnvironmentPaneSpec(
                key="general",
                title="Preferences",
                subtitle="Core environment identity, limits, and runtime toggles.",
                section="General",
            ),
            _EnvironmentPaneSpec(
                key="agents",
                title="Agents",
                subtitle="Agent selection, chain behavior, and cross-agent controls.",
                section="Collaboration",
            ),
            _EnvironmentPaneSpec(
                key="prompts",
                title="Prompts",
                subtitle="Prompt snippets and unlock behavior for this environment.",
                section="Collaboration",
            ),
            _EnvironmentPaneSpec(
                key="github_config",
                title="Config",
                subtitle="GitHub context, polling, and trust mode controls for this environment.",
                section="GitHub",
            ),
            _EnvironmentPaneSpec(
                key="github_trusted_users",
                title="Trusted Users",
                subtitle="Environment-specific trusted usernames for @agentsnova checks.",
                section="GitHub",
            ),
            _EnvironmentPaneSpec(
                key="env_vars",
                title="Environment Variables",
                subtitle="Container environment variables injected at runtime.",
                section="Container",
            ),
            _EnvironmentPaneSpec(
                key="mounts",
                title="Mounts",
                subtitle="Additional bind mounts exposed to task containers.",
                section="Container",
            ),
            _EnvironmentPaneSpec(
                key="ports",
                title="Ports",
                subtitle="Port mapping policy for task containers.",
                section="Container",
            ),
            _EnvironmentPaneSpec(
                key="preflight",
                title="Preflight",
                subtitle="Read-only setup-agents.sh preview.",
                section="Automation",
            ),
            _EnvironmentPaneSpec(
                key="caching",
                title="Caching",
                subtitle="Container and desktop caching controls for this environment.",
                section="Automation",
            ),
        ]

    def _build_controls(self) -> None:
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

        self._headless_desktop_enabled = QCheckBox("Enable headless desktop")
        self._headless_desktop_enabled.setToolTip(
            "When enabled, agent runs for this environment will start a noVNC desktop.\n"
            "Settings → Force headless desktop overrides this setting."
        )
        self._headless_desktop_enabled.stateChanged.connect(
            self._on_headless_desktop_toggled
        )
        self._gpu_override_mode = QComboBox()
        self._gpu_override_mode.addItem("Inherit global setting", "inherit")
        self._gpu_override_mode.addItem("Enabled", "enabled")
        self._gpu_override_mode.addItem("Disabled", "disabled")
        self._gpu_override_mode.setToolTip(
            "Override the global GPU runtime setting for this environment."
        )
        self._opencode_interactive_mode = QComboBox()
        self._opencode_interactive_mode.addItem("Inherit global setting", "inherit")
        self._opencode_interactive_mode.addItem("Terminal", "terminal")
        self._opencode_interactive_mode.addItem("Web", "web")
        self._opencode_interactive_mode.addItem("Ask", "ask")
        self._opencode_interactive_mode.setToolTip(
            "Override the global OpenCode Run Interactive launch mode."
        )

        self._cache_desktop_build = QCheckBox("Cache desktop build")
        self._cache_desktop_build.setToolTip(
            "When enabled, desktop components are pre-installed in a cached Docker image.\n"
            "This reduces task startup time from 45-90s to 2-5s.\n"
            "Requires 'Enable headless desktop' to be enabled.\n\n"
            "Image is automatically rebuilt when scripts change."
        )
        self._cache_desktop_build.setEnabled(False)

        self._container_caching_enabled = QCheckBox("Enable container caching")
        self._container_caching_enabled.setToolTip(
            "When enabled, selected preflight phases build cached Docker layers.\n"
            "Configure phase cache toggles in the Caching pane."
        )
        self._container_caching_enabled.stateChanged.connect(
            self._on_container_caching_toggled
        )

        self._use_cross_agents = QCheckBox("Use cross agents")
        self._use_cross_agents.setToolTip(
            "When enabled, allows agent instances from the Agents pane to be mounted\n"
            "as cross-agents in task containers. Configure the allowlist in the Agents pane."
        )
        self._use_cross_agents.stateChanged.connect(self._on_use_cross_agents_toggled)

        self._gh_context_enabled = QCheckBox("Provide GitHub context to agent")
        self._gh_context_enabled.setToolTip(
            "When enabled, repository context (URL, branch, commit) is provided to the agent.\n"
            "For GitHub-managed environments: Always available.\n"
            "For folder-managed environments: Only if folder is a git repository.\n\n"
            "Note: This does NOT provide GitHub authentication - that is separate."
        )
        self._gh_context_enabled.setEnabled(False)
        self._gh_context_enabled.setVisible(True)
        self._github_polling_enabled = QCheckBox(
            "Enable background GitHub polling for this environment"
        )
        self._github_polling_enabled.setToolTip(
            "Used only when global GitHub polling is disabled. "
            "This control is hidden while global GitHub polling is enabled."
        )
        self._agentsnova_trusted_mode = QComboBox()
        self._agentsnova_trusted_mode.addItem("Inherit global trusted users", "inherit")
        self._agentsnova_trusted_mode.addItem(
            "Add environment trusted users", "additive"
        )
        self._agentsnova_trusted_mode.addItem(
            "Replace with environment trusted users", "replace"
        )
        self._agentsnova_trusted_mode.setToolTip(
            "Controls how this environment resolves trusted usernames for auto-review mention checks."
        )
        self._agentsnova_auto_review_mode = QComboBox()
        self._agentsnova_auto_review_mode.addItem("Inherit global setting", "inherit")
        self._agentsnova_auto_review_mode.addItem("Enabled", "enabled")
        self._agentsnova_auto_review_mode.addItem("Disabled", "disabled")
        self._agentsnova_auto_review_mode.setToolTip(
            "Override whether @agentsnova mentions auto-queue review work for this environment."
        )
        self._agentsnova_auto_reactions_mode = QComboBox()
        self._agentsnova_auto_reactions_mode.addItem(
            "Inherit global setting", "inherit"
        )
        self._agentsnova_auto_reactions_mode.addItem("Enabled", "enabled")
        self._agentsnova_auto_reactions_mode.addItem("Disabled", "disabled")
        self._agentsnova_auto_reactions_mode.setToolTip(
            "Override whether @agentsnova queue triggers add GitHub reactions for this environment."
        )
        self._agentsnova_marker_comment_mode = QComboBox()
        self._agentsnova_marker_comment_mode.addItem(
            "Inherit global setting", "inherit"
        )
        self._agentsnova_marker_comment_mode.addItem("Keep", "keep")
        self._agentsnova_marker_comment_mode.addItem(
            "Delete after 15s", "delete_after_15s"
        )
        self._agentsnova_marker_comment_mode.addItem("Disabled", "disabled")
        self._agentsnova_marker_comment_mode.setToolTip(
            "Override marker-comment behavior for @agentsnova auto-review activity in this environment."
        )
        self._interactive_pr_prompt_enabled = QCheckBox("Show interactive PR prompt")
        self._interactive_pr_prompt_enabled.setToolTip(
            "When enabled, interactive GitHub work can keep showing the PR prompt for this environment."
        )
        self._interactive_pr_no_prompt_mode = QComboBox()
        self._interactive_pr_no_prompt_mode.addItem(
            "Auto-create PR after interactive run",
            INTERACTIVE_PR_NO_PROMPT_MODE_AUTO_CREATE,
        )
        self._interactive_pr_no_prompt_mode.addItem(
            "Manual only (Review -> Create PR)",
            INTERACTIVE_PR_NO_PROMPT_MODE_MANUAL_REVIEW,
        )
        self._interactive_pr_no_prompt_mode.setToolTip(
            "Used when 'Show interactive PR prompt' is disabled.\n"
            "Manual mode means you can enter the task, then click Review -> Create PR yourself."
        )
        self._interactive_pr_no_prompt_mode.setVisible(False)
        self._interactive_pr_prompt_enabled.toggled.connect(
            self._sync_interactive_pr_controls
        )
        self._setup_agents_missing_prompt_enabled = QCheckBox(
            "Inject missing setup-agents prompt"
        )
        self._setup_agents_missing_prompt_enabled.setToolTip(
            "When enabled, missing setup-agents guidance can be injected for this environment."
        )
        self._interactive_pull_before_run_enabled = QCheckBox(
            "Pull before interactive run"
        )
        self._interactive_pull_before_run_enabled.setToolTip(
            "When enabled, interactive runs can pull/update before starting for this environment."
        )
        self._gh_branch_work_mode = QComboBox()
        self._gh_branch_work_mode.addItem("Use task branches", "task_branch")
        self._gh_branch_work_mode.addItem("Work on direct base", "direct_base")
        self._gh_branch_work_mode.setToolTip(
            "Controls whether GitHub work for this environment uses per-task branches or works directly on the selected base branch."
        )
        self._gh_task_branch_naming_style = QComboBox()
        self._gh_task_branch_naming_style.addItem("Standard", "standard")
        self._gh_task_branch_naming_style.addItem("Songs", "songs")
        self._gh_task_branch_naming_style.addItem("Foods", "foods")
        self._gh_task_branch_naming_style.addItem("Animals", "animals")
        self._gh_task_branch_naming_style.addItem("Colors", "colors")
        self._gh_task_branch_naming_style.addItem("Space", "space")
        self._gh_task_branch_naming_style.addItem("Custom", "custom")
        self._gh_task_branch_naming_style.setToolTip(
            "Controls how future task branches are named for this environment."
        )
        self._gh_task_branch_custom_template = QLineEdit()
        self._gh_task_branch_custom_template.setPlaceholderText(
            GH_TASK_BRANCH_CUSTOM_TEMPLATE_DEFAULT
        )
        self._gh_task_branch_custom_template.setToolTip(
            "Custom template used when task branch naming style is set to Custom."
        )
        self._gh_task_branch_custom_template_helper = QLabel(
            "Custom templates can use placeholders like {task_id}."
        )
        self._gh_task_branch_custom_template_helper.setObjectName(
            "SettingsPaneSubtitle"
        )
        self._gh_task_branch_custom_template.setVisible(False)
        self._gh_task_branch_custom_template_helper.setVisible(False)
        self._gh_branch_work_mode.currentIndexChanged.connect(
            self._sync_github_branch_naming_controls
        )
        self._gh_task_branch_naming_style.currentIndexChanged.connect(
            self._sync_github_branch_naming_controls
        )
        self._agentsnova_trusted_users_env = GitHubUsernameListWidget()
        self._agentsnova_trusted_users_env.set_add_button_visible(False)
        self._add_trusted_user_env = (
            self._agentsnova_trusted_users_env.create_add_button(self)
        )
        self._setup_github_defaults_env = QToolButton()
        self._setup_github_defaults_env.setText("Setup Defaults")
        self._setup_github_defaults_env.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self._setup_github_defaults_env.setToolTip(
            "Seed trusted users from this environment's repo owner/org members and current gh login."
        )
        self._setup_github_defaults_env.clicked.connect(
            self._on_setup_environment_github_defaults
        )

        # Workspace controls are retained for compatibility with existing logic but remain hidden.
        self._workspace_type_combo = QComboBox()
        self._workspace_type_combo.addItem("Use Settings workdir", WORKSPACE_NONE)
        self._workspace_type_combo.addItem("Mount local folder", WORKSPACE_MOUNTED)
        self._workspace_type_combo.addItem("Clone GitHub repo", WORKSPACE_CLONED)
        self._workspace_type_combo.currentIndexChanged.connect(
            self._sync_workspace_controls
        )

        self._workspace_target = QLineEdit()
        self._workspace_target.setPlaceholderText(
            "owner/repo, https://github.com/owner/repo, or /path/to/folder"
        )
        self._workspace_target.textChanged.connect(self._sync_workspace_controls)

        self._gh_management_browse = QPushButton("Browse…")
        self._gh_management_browse.setFixedWidth(STANDARD_BUTTON_WIDTH)
        self._gh_management_browse.clicked.connect(self._pick_gh_management_folder)

        self._gh_use_host_cli = QCheckBox("Use host `gh` CLI")
        self._gh_use_host_cli.setToolTip(
            "Use the host system's `gh` CLI for cloning and PR creation (if installed).\n"
            "When disabled or unavailable, cloning uses `git` and PR creation is skipped."
        )

        self._workspace_type_combo.setVisible(False)
        self._workspace_target.setVisible(False)
        self._gh_management_browse.setVisible(False)

        self._setup_agents_preview = QPlainTextEdit()
        self._setup_agents_preview.setReadOnly(True)
        self._setup_agents_preview.setPlaceholderText(
            "# setup-agents.sh is not available for this environment."
        )
        self._setup_agents_preview.setToolTip("Create in repo: .agents/setup-agents.sh")
        self._setup_agents_preview.setTabChangesFocus(True)
        self._setup_agents_preview_highlighter = ArtifactSyntaxHighlighter(
            self._setup_agents_preview.document()
        )
        self._setup_agents_preview_highlighter.set_language("bash")

        self._cache_system_preflight_enabled = QCheckBox("Cache system phase")
        self._cache_system_preflight_enabled.setToolTip(
            "When enabled, the system preflight (`pixelarch_yay.sh`) is cached as an image layer."
        )
        self._cache_system_preflight_enabled.setEnabled(False)

        self._cache_settings_preflight_enabled = QCheckBox("Cache settings phase")
        self._cache_settings_preflight_enabled.setToolTip(
            "When enabled, the Settings preflight script is cached as an image layer."
        )
        self._cache_settings_preflight_enabled.setEnabled(False)

        self._env_vars_tab = EnvVarsTabWidget()
        self._env_vars_tab.env_vars_changed.connect(self._queue_advanced_autosave)

        self._mounts_tab = MountsTabWidget()
        self._mounts_tab.mounts_changed.connect(self._queue_advanced_autosave)

        self._ports_tab = PortsTabWidget()
        self._ports_tab.ports_changed.connect(self._on_ports_changed)

        self._prompts_tab = PromptsTabWidget()
        self._prompts_tab.prompts_changed.connect(self._on_prompts_changed)

        self._agents_tab = AgentsTabWidget()
        self._agents_tab.agents_changed.connect(self._on_agents_changed)

    def _build_pages(self) -> None:
        specs_by_key = {spec.key: spec for spec in self._pane_specs}

        general_page, general_body = self._create_page(specs_by_key["general"])
        grid = QGridLayout()
        configure_form_grid(grid)

        max_agents_row = create_stretch_row(self._max_agents_running, stretch_index=1)
        self._headless_desktop_label = QLabel("Headless desktop")
        self._headless_desktop_row = create_stretch_row(
            self._headless_desktop_enabled,
            stretch_index=1,
        )
        cross_agents_row = create_stretch_row(self._use_cross_agents, stretch_index=1)

        add_grid_row(grid, 0, QLabel("Name"), self._name)
        add_grid_row(grid, 1, QLabel("Color"), self._color)
        add_grid_row(grid, 3, QLabel("Max agents running"), max_agents_row)
        add_grid_row(grid, 4, self._headless_desktop_label, self._headless_desktop_row)
        add_grid_row(grid, 5, QLabel("GPU runtime"), self._gpu_override_mode)
        add_grid_row(
            grid,
            6,
            QLabel("OpenCode interactive"),
            self._opencode_interactive_mode,
        )
        add_grid_row(grid, 7, QLabel("Cross agents"), cross_agents_row)

        general_body.addLayout(grid)
        general_body.addStretch(1)
        self._register_page("general", general_page)

        agents_page, agents_body = self._create_page(specs_by_key["agents"])
        agents_body.addWidget(self._agents_tab, 1)
        self._register_page("agents", agents_page)

        prompts_page, prompts_body = self._create_page(specs_by_key["prompts"])
        prompts_body.addWidget(self._prompts_tab, 1)
        self._register_page("prompts", prompts_page)

        github_config_page, github_config_body = self._create_page(
            specs_by_key["github_config"]
        )
        github_grid = QGridLayout()
        configure_form_grid(github_grid)

        gh_context_row = create_stretch_row(self._gh_context_enabled, stretch_index=1)
        self._github_polling_enabled_label = QLabel("GitHub polling")
        self._github_polling_enabled_row = create_stretch_row(
            self._github_polling_enabled,
            stretch_index=1,
        )
        trusted_mode_row = self._agentsnova_trusted_mode
        auto_review_row = self._agentsnova_auto_review_mode
        auto_reactions_row = self._agentsnova_auto_reactions_mode
        marker_comment_row = self._agentsnova_marker_comment_mode
        interactive_pr_prompt_row = create_stretch_row(
            self._interactive_pr_prompt_enabled,
            stretch_index=1,
        )
        self._interactive_pr_no_prompt_mode_label = QLabel("When prompt is disabled")
        self._interactive_pr_no_prompt_mode_row = create_stretch_row(
            self._interactive_pr_no_prompt_mode,
            stretch_index=1,
        )
        setup_agents_missing_prompt_row = create_stretch_row(
            self._setup_agents_missing_prompt_enabled,
            stretch_index=1,
        )
        interactive_pull_before_run_row = create_stretch_row(
            self._interactive_pull_before_run_enabled,
            stretch_index=1,
        )
        branch_work_mode_row = self._gh_branch_work_mode
        task_branch_naming_row = self._gh_task_branch_naming_style
        self._gh_task_branch_custom_template_label = QLabel("Custom branch template")
        self._gh_task_branch_custom_template_row = QWidget(github_config_page)
        gh_custom_template_layout = QVBoxLayout(
            self._gh_task_branch_custom_template_row
        )
        gh_custom_template_layout.setContentsMargins(0, 0, 0, 0)
        gh_custom_template_layout.setSpacing(GRID_VERTICAL_SPACING)
        gh_custom_template_layout.addWidget(self._gh_task_branch_custom_template)
        gh_custom_template_layout.addWidget(self._gh_task_branch_custom_template_helper)

        add_grid_row(github_grid, 0, QLabel("GitHub context"), gh_context_row)
        add_grid_row(
            github_grid,
            1,
            self._github_polling_enabled_label,
            self._github_polling_enabled_row,
        )
        add_grid_row(
            github_grid,
            2,
            QLabel("Interactive PR prompt"),
            interactive_pr_prompt_row,
        )
        add_grid_row(
            github_grid,
            3,
            self._interactive_pr_no_prompt_mode_label,
            self._interactive_pr_no_prompt_mode_row,
        )
        add_grid_row(
            github_grid,
            4,
            QLabel("Missing setup-agents prompt injection"),
            setup_agents_missing_prompt_row,
        )
        add_grid_row(
            github_grid,
            5,
            QLabel("Interactive pull before run"),
            interactive_pull_before_run_row,
        )
        add_grid_row(github_grid, 6, QLabel("Trusted mode"), trusted_mode_row)
        add_grid_row(github_grid, 7, QLabel("Auto review"), auto_review_row)
        add_grid_row(github_grid, 8, QLabel("Auto reactions"), auto_reactions_row)
        add_grid_row(github_grid, 9, QLabel("Marker comments"), marker_comment_row)
        add_grid_row(github_grid, 10, QLabel("Branch workflow"), branch_work_mode_row)
        add_grid_row(
            github_grid, 11, QLabel("Task branch naming"), task_branch_naming_row
        )
        add_grid_row(
            github_grid,
            12,
            self._gh_task_branch_custom_template_label,
            self._gh_task_branch_custom_template_row,
        )
        self._interactive_pr_no_prompt_mode_label.setVisible(False)
        self._interactive_pr_no_prompt_mode_row.setVisible(False)
        self._gh_task_branch_custom_template_label.setVisible(False)
        self._gh_task_branch_custom_template_row.setVisible(False)

        github_config_body.addLayout(github_grid)
        github_config_body.addStretch(1)
        self._register_page("github_config", github_config_page)

        github_trusted_page, github_trusted_body = self._create_page(
            specs_by_key["github_trusted_users"]
        )
        github_trusted_body.addWidget(self._agentsnova_trusted_users_env, 1)

        github_actions = QHBoxLayout()
        github_actions.setSpacing(BUTTON_ROW_SPACING)
        github_actions.addWidget(self._add_trusted_user_env)
        github_actions.addStretch(1)
        github_actions.addWidget(self._setup_github_defaults_env)
        github_trusted_body.addLayout(github_actions)
        self._register_page("github_trusted_users", github_trusted_page)

        env_vars_page, env_vars_body = self._create_page(specs_by_key["env_vars"])
        env_vars_body.addWidget(self._env_vars_tab, 1)
        self._register_page("env_vars", env_vars_page)

        mounts_page, mounts_body = self._create_page(specs_by_key["mounts"])
        mounts_body.addWidget(self._mounts_tab, 1)
        self._register_page("mounts", mounts_page)

        ports_page, ports_body = self._create_page(specs_by_key["ports"])
        ports_body.addWidget(self._ports_tab, 1)
        self._register_page("ports", ports_page)

        preflight_page, preflight_body = self._create_page(specs_by_key["preflight"])
        preflight_body.addWidget(self._setup_agents_preview, 1)
        self._register_page("preflight", preflight_page)

        caching_page, caching_body = self._create_page(specs_by_key["caching"])
        caching_grid = QGridLayout()
        configure_form_grid(caching_grid)

        container_caching_row = create_stretch_row(
            self._container_caching_enabled,
            stretch_index=1,
        )
        desktop_build_cache_row = create_stretch_row(
            self._cache_desktop_build,
            stretch_index=1,
        )
        system_phase_cache_row = create_stretch_row(
            self._cache_system_preflight_enabled,
            stretch_index=1,
        )
        settings_phase_cache_row = create_stretch_row(
            self._cache_settings_preflight_enabled,
            stretch_index=1,
        )

        add_grid_row(
            caching_grid, 0, QLabel("Container caching"), container_caching_row
        )
        add_grid_row(
            caching_grid, 1, QLabel("Desktop build cache"), desktop_build_cache_row
        )
        add_grid_row(
            caching_grid, 2, QLabel("System phase cache"), system_phase_cache_row
        )
        add_grid_row(
            caching_grid,
            3,
            QLabel("Settings phase cache"),
            settings_phase_cache_row,
        )

        caching_body.addLayout(caching_grid)
        caching_body.addStretch(1)
        self._register_page("caching", caching_page)

    def _build_navigation(self, nav_layout: QVBoxLayout) -> None:
        sections: dict[str, list[_EnvironmentPaneSpec]] = {}
        for spec in self._pane_specs:
            sections.setdefault(spec.section, []).append(spec)

        for section_title, specs in sections.items():
            section_label = QLabel(section_title)
            section_label.setObjectName("SettingsNavSection")
            nav_layout.addWidget(section_label)

            for spec in specs:
                button = QToolButton()
                button.setObjectName("SettingsNavButton")
                button.setText(self._pane_button_label(spec.key, spec.title))
                button.setToolTip(spec.subtitle)
                button.setCheckable(True)
                button.setAutoExclusive(True)
                button.setToolButtonStyle(Qt.ToolButtonTextOnly)
                button.setFixedHeight(40)
                button.setSizePolicy(
                    QSizePolicy.Policy.Expanding,
                    QSizePolicy.Policy.Fixed,
                )
                button.clicked.connect(
                    lambda checked=False, key=spec.key: self._on_nav_button_clicked(key)
                )
                nav_layout.addWidget(button)
                self._nav_buttons[spec.key] = button
                self._compact_nav.addItem(spec.title, spec.key)

        nav_layout.addStretch(1)

    def _create_page(self, spec: _EnvironmentPaneSpec) -> tuple[QWidget, QVBoxLayout]:
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

        title = QLabel(spec.title)
        title.setObjectName("SettingsPaneTitle")

        body = QWidget(content)
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(GRID_VERTICAL_SPACING)

        content_layout.addWidget(title)
        content_layout.addWidget(body)

        scroll.setWidget(content)
        page_layout.addWidget(scroll, 1)
        return page, body_layout

    def _register_page(self, key: str, widget: QWidget) -> None:
        index = self._page_stack.addWidget(widget)
        self._pane_index_by_key[key] = index

    @staticmethod
    def _pane_button_label(key: str, title: str) -> str:
        return title

    def _current_environment(self) -> Environment | None:
        envs = getattr(self, "_environments", {})
        if not isinstance(envs, dict):
            return None
        env_id = str(getattr(self, "_current_env_id", "") or "").strip()
        env = envs.get(env_id)
        return env if isinstance(env, Environment) else None

    def _on_setup_environment_github_defaults(self) -> None:
        env = self._current_environment()
        seeded = collect_seed_usernames_for_environment(env)
        if not seeded:
            return
        self._agentsnova_trusted_users_env.merge_usernames(seeded)
        try:
            self._queue_advanced_autosave()
        except Exception:
            pass

    def _pick_gh_management_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self,
            "Select locked Workdir folder",
            self._workspace_target.text() or os.getcwd(),
        )
        if path:
            self._workspace_target.setText(path)
