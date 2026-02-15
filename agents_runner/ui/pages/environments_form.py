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
from agents_runner.ui.constants import (
    BUTTON_ROW_SPACING,
    GRID_HORIZONTAL_SPACING,
    GRID_VERTICAL_SPACING,
    STANDARD_BUTTON_WIDTH,
)
from agents_runner.ui.pages.github_trust import collect_seed_usernames_for_environment
from agents_runner.ui.pages.github_username_list import GitHubUsernameListWidget
from agents_runner.ui.pages.environments_agents import AgentsTabWidget
from agents_runner.ui.pages.environments_env_vars import EnvVarsTabWidget
from agents_runner.ui.pages.environments_mounts import MountsTabWidget
from agents_runner.ui.pages.environments_ports import PortsTabWidget
from agents_runner.ui.pages.environments_prompts import PromptsTabWidget


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
                key="github",
                title="GitHub",
                subtitle="GitHub context, polling, and trusted actor controls for this environment.",
                section="Collaboration",
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
                subtitle="Container setup scripts executed before tasks run.",
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
            "Requires global GitHub polling in Settings. When enabled, this environment participates in app-wide polling."
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

        self._preflight_enabled = QCheckBox("Enable environment preflight")
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
        grid.setHorizontalSpacing(GRID_HORIZONTAL_SPACING)
        grid.setVerticalSpacing(GRID_VERTICAL_SPACING)
        grid.setContentsMargins(0, 0, 0, 0)

        max_agents_row = QWidget(general_page)
        max_agents_row_layout = QHBoxLayout(max_agents_row)
        max_agents_row_layout.setContentsMargins(0, 0, 0, 0)
        max_agents_row_layout.setSpacing(BUTTON_ROW_SPACING)
        max_agents_row_layout.addWidget(self._max_agents_running)
        max_agents_row_layout.addStretch(1)

        headless_desktop_row = QWidget(general_page)
        headless_desktop_layout = QHBoxLayout(headless_desktop_row)
        headless_desktop_layout.setContentsMargins(0, 0, 0, 0)
        headless_desktop_layout.setSpacing(BUTTON_ROW_SPACING)
        headless_desktop_layout.addWidget(self._headless_desktop_enabled)
        headless_desktop_layout.addStretch(1)

        cross_agents_row = QWidget(general_page)
        cross_agents_layout = QHBoxLayout(cross_agents_row)
        cross_agents_layout.setContentsMargins(0, 0, 0, 0)
        cross_agents_layout.setSpacing(BUTTON_ROW_SPACING)
        cross_agents_layout.addWidget(self._use_cross_agents)
        cross_agents_layout.addStretch(1)

        grid.addWidget(QLabel("Name"), 0, 0)
        grid.addWidget(self._name, 0, 1, 1, 2)
        grid.addWidget(QLabel("Color"), 1, 0)
        grid.addWidget(self._color, 1, 1, 1, 2)
        grid.addWidget(QLabel("Max agents running"), 3, 0)
        grid.addWidget(max_agents_row, 3, 1, 1, 2)
        grid.addWidget(QLabel("Headless desktop"), 4, 0)
        grid.addWidget(headless_desktop_row, 4, 1, 1, 2)
        grid.addWidget(QLabel("Cross agents"), 5, 0)
        grid.addWidget(cross_agents_row, 5, 1, 1, 2)

        general_body.addLayout(grid)
        general_body.addStretch(1)
        self._register_page("general", general_page)

        agents_page, agents_body = self._create_page(specs_by_key["agents"])
        agents_body.addWidget(self._agents_tab, 1)
        self._register_page("agents", agents_page)

        prompts_page, prompts_body = self._create_page(specs_by_key["prompts"])
        prompts_body.addWidget(self._prompts_tab, 1)
        self._register_page("prompts", prompts_page)

        github_page, github_body = self._create_page(specs_by_key["github"])
        github_body.addWidget(self._gh_context_enabled)
        github_body.addWidget(self._github_polling_enabled)

        trusted_label = QLabel("Trusted GitHub users")
        trusted_label.setObjectName("SettingsPaneSubtitle")
        github_body.addWidget(trusted_label)
        github_body.addWidget(self._agentsnova_trusted_users_env, 1)

        github_actions = QHBoxLayout()
        github_actions.setSpacing(BUTTON_ROW_SPACING)
        github_actions.addWidget(self._add_trusted_user_env)
        github_actions.addStretch(1)
        github_actions.addWidget(self._setup_github_defaults_env)
        github_actions.addWidget(self._agentsnova_trusted_mode)
        github_body.addLayout(github_actions)
        self._register_page("github", github_page)

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
        preflight_body.addWidget(self._preflight_enabled)
        preflight_body.addWidget(QLabel("Environment preflight script"))
        preflight_body.addWidget(self._preflight_script, 1)
        self._register_page("preflight", preflight_page)

        caching_page, caching_body = self._create_page(specs_by_key["caching"])
        caching_body.addWidget(self._container_caching_enabled)
        caching_body.addWidget(self._cache_desktop_build)
        caching_body.addWidget(self._cache_system_preflight_enabled)
        caching_body.addWidget(self._cache_settings_preflight_enabled)
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
        page_layout.setSpacing(10)

        title = QLabel(spec.title)
        title.setObjectName("SettingsPaneTitle")

        subtitle = QLabel(spec.subtitle)
        subtitle.setObjectName("SettingsPaneSubtitle")
        subtitle.setWordWrap(True)

        body = QWidget(page)
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(GRID_VERTICAL_SPACING)

        page_layout.addWidget(title)
        page_layout.addWidget(subtitle)
        page_layout.addWidget(body, 1)
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
