from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtCore import QPoint
from PySide6.QtCore import QTimer
from PySide6.QtCore import Signal
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import QComboBox
from PySide6.QtWidgets import QHBoxLayout
from PySide6.QtWidgets import QLabel
from PySide6.QtWidgets import QStackedWidget
from PySide6.QtWidgets import QToolButton
from PySide6.QtWidgets import QVBoxLayout
from PySide6.QtWidgets import QWidget

from agents_runner.environments import Environment
from agents_runner.environments import WORKSPACE_CLONED
from agents_runner.environments import WORKSPACE_MOUNTED
from agents_runner.environments import WORKSPACE_NONE
from agents_runner.environments import managed_repo_checkout_path
from agents_runner.environments.model import (
    GH_TASK_BRANCH_CUSTOM_TEMPLATE_DEFAULT,
    INTERACTIVE_PR_NO_PROMPT_MODE_AUTO_CREATE,
    normalize_agentsnova_auto_mode,
    normalize_interactive_pr_no_prompt_mode,
    normalize_agentsnova_marker_comment_mode,
    normalize_gh_branch_work_mode,
    normalize_gh_task_branch_custom_template,
    normalize_gh_task_branch_naming_style,
)
from agents_runner.gh_management import is_gh_available
from agents_runner.persistence import default_state_path
from agents_runner.setup_agents import resolve_setup_agents_preview
from agents_runner.ui.constants import (
    AUTOSAVE_DISCRETE_MS,
    AUTOSAVE_IDLE_MS,
    CARD_MARGINS,
    CARD_SPACING,
    HEADER_MARGINS,
    HEADER_SPACING,
    LEFT_NAV_BUTTON_SPACING,
    LEFT_NAV_PANEL_WIDTH,
    MAIN_LAYOUT_MARGINS,
    MAIN_LAYOUT_SPACING,
)
from agents_runner.ui.graphics import EnvironmentTintOverlay
from agents_runner.ui.pages.environments_actions import EnvironmentsPageActionsMixin
from agents_runner.ui.pages.environments_form import EnvironmentsFormMixin
from agents_runner.ui.pages.environments_navigation import EnvironmentsNavigationMixin
from agents_runner.ui.pages.github_trust import normalize_trusted_mode
from agents_runner.ui.utils import apply_environment_combo_tint
from agents_runner.ui.utils import stain_color
from agents_runner.ui.widgets import EdgeFadeScrollArea, GlassCard


class EnvironmentsPage(
    QWidget,
    EnvironmentsNavigationMixin,
    EnvironmentsFormMixin,
    EnvironmentsPageActionsMixin,
):
    back_requested = Signal()
    updated = Signal(str)
    test_preflight_requested = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("EnvironmentsPageRoot")

        self._environments: dict[str, Environment] = {}
        self._current_env_id: str | None = None
        self._settings_data: dict[str, object] = {}

        self._suppress_autosave = False
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setSingleShot(True)
        self._autosave_timer.setInterval(AUTOSAVE_DISCRETE_MS)
        self._autosave_timer.timeout.connect(self._emit_autosave)
        self._advanced_autosave_timer = QTimer(self)
        self._advanced_autosave_timer.setSingleShot(True)
        self._advanced_autosave_timer.setInterval(AUTOSAVE_IDLE_MS)
        self._advanced_autosave_timer.timeout.connect(self._emit_autosave)

        self._pane_animation = None
        self._pane_rest_pos: QPoint | None = None
        self._compact_mode = False
        self._active_pane_key = ""

        self._pane_specs = self._default_pane_specs()
        self._pane_index_by_key: dict[str, int] = {}
        self._nav_buttons: dict[str, QToolButton] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(*MAIN_LAYOUT_MARGINS)
        layout.setSpacing(MAIN_LAYOUT_SPACING)

        header = GlassCard()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(*HEADER_MARGINS)
        header_layout.setSpacing(HEADER_SPACING)

        title = QLabel("Environments")
        title.setStyleSheet("font-size: 18px; font-weight: 750;")
        envs_path = os.path.join(
            os.path.dirname(default_state_path()),
            "environments.json",
        )
        title.setToolTip(f"Environments are saved locally in:\n{envs_path}")

        self._env_select = QComboBox()
        self._env_select.setFixedWidth(240)
        self._env_select.currentIndexChanged.connect(self._on_env_selected)

        new_btn = QToolButton()
        new_btn.setText("New")
        new_btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
        new_btn.clicked.connect(self._on_new)

        delete_btn = QToolButton()
        delete_btn.setText("Delete")
        delete_btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
        delete_btn.clicked.connect(self._on_delete)

        test_btn = QToolButton()
        test_btn.setText("Test preflight")
        test_btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
        test_btn.clicked.connect(self._on_test_preflight)

        header_layout.addWidget(title)
        header_layout.addStretch(1)
        header_layout.addWidget(QLabel("Environments"))
        header_layout.addWidget(self._env_select)
        header_layout.addWidget(new_btn)
        header_layout.addWidget(delete_btn)
        header_layout.addWidget(test_btn)
        layout.addWidget(header)

        card = GlassCard()
        card_layout = QVBoxLayout(card)
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

        layout.addWidget(card, 1)

        self._build_controls()
        self._build_pages()
        self._build_navigation(nav_layout)
        self._connect_autosave_signals()
        self._sync_github_branch_naming_controls()
        self._sync_interactive_pr_controls()

        if self._pane_specs:
            first_key = self._pane_specs[0].key
            self._set_active_navigation(first_key)
            self._set_current_pane(first_key, animate=False)

        self._update_navigation_mode()

        self._tint_overlay = EnvironmentTintOverlay(self, alpha=13)
        self._tint_overlay.raise_()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._update_navigation_mode()
        self._tint_overlay.setGeometry(self.rect())
        self._tint_overlay.raise_()

    def _apply_environment_tints(self) -> None:
        stain = str(self._color.currentData() or "").strip().lower()
        if not stain:
            env_id = str(self._env_select.currentData() or "")
            env = self._environments.get(env_id)
            stain = (env.normalized_color() if env else "").strip().lower()

        if not stain:
            self._apply_nav_button_stain("")
            self._env_select.setStyleSheet("")
            self._tint_overlay.set_tint_color(None)
            self._color.setStyleSheet("")
            return

        self._apply_nav_button_stain(stain)
        apply_environment_combo_tint(self._env_select, stain)
        tint = stain_color(stain)
        self._tint_overlay.set_tint_color(tint)
        apply_environment_combo_tint(self._color, stain)

    def _apply_nav_button_stain(self, stain: str) -> None:
        normalized = str(stain or "").strip().lower()
        for button in self._nav_buttons.values():
            if str(button.property("env_stain") or "") == normalized:
                continue
            button.setProperty("env_stain", normalized)
            style = button.style()
            style.unpolish(button)
            style.polish(button)
            button.update()

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
        self._settings_data = settings_data
        self._sync_headless_desktop_override_visibility()
        self._sync_github_polling_override_visibility()
        self._refresh_setup_agents_preview(self._current_environment())

    def _effective_desktop_enabled(self) -> bool:
        force = bool(self._settings_data.get("headless_desktop_enabled") or False)
        env_enabled = bool(self._headless_desktop_enabled.isChecked())
        return bool(force or env_enabled)

    def _sync_github_polling_override_visibility(self) -> None:
        app_wide_polling = bool(
            self._settings_data.get("github_polling_enabled") or False
        )
        polling_visible = not app_wide_polling

        polling_label = getattr(self, "_github_polling_enabled_label", None)
        if isinstance(polling_label, QWidget):
            polling_label.setVisible(polling_visible)

        polling_row = getattr(self, "_github_polling_enabled_row", None)
        if isinstance(polling_row, QWidget):
            polling_row.setVisible(polling_visible)

        self._github_polling_enabled.setVisible(polling_visible)

    def _sync_headless_desktop_override_visibility(self) -> None:
        force_headless = bool(
            self._settings_data.get("headless_desktop_enabled") or False
        )

        headless_label = getattr(self, "_headless_desktop_label", None)
        if isinstance(headless_label, QWidget):
            headless_label.setVisible(not force_headless)

        headless_row = getattr(self, "_headless_desktop_row", None)
        if isinstance(headless_row, QWidget):
            headless_row.setVisible(not force_headless)

        self._ports_tab.set_desktop_effective_enabled(self._effective_desktop_enabled())
        self._cache_desktop_build.setEnabled(self._effective_desktop_enabled())

    def _sync_interactive_pr_controls(self) -> None:
        show_no_prompt_mode = not bool(self._interactive_pr_prompt_enabled.isChecked())
        no_prompt_mode_label = getattr(
            self, "_interactive_pr_no_prompt_mode_label", None
        )
        if isinstance(no_prompt_mode_label, QWidget):
            no_prompt_mode_label.setVisible(show_no_prompt_mode)
        no_prompt_mode_row = getattr(self, "_interactive_pr_no_prompt_mode_row", None)
        if isinstance(no_prompt_mode_row, QWidget):
            no_prompt_mode_row.setVisible(show_no_prompt_mode)
        self._interactive_pr_no_prompt_mode.setVisible(show_no_prompt_mode)
        self._interactive_pr_no_prompt_mode.setEnabled(show_no_prompt_mode)

    def _sync_github_branch_naming_controls(self) -> None:
        workspace_type = str(self._workspace_type_combo.currentData() or "").strip()
        branch_work_mode = normalize_gh_branch_work_mode(
            self._gh_branch_work_mode.currentData() or "task_branch"
        )
        naming_style = normalize_gh_task_branch_naming_style(
            self._gh_task_branch_naming_style.currentData() or "standard"
        )
        branch_controls_enabled = workspace_type == WORKSPACE_CLONED
        naming_enabled = branch_controls_enabled and branch_work_mode != "direct_base"
        show_custom_template = branch_controls_enabled and naming_style == "custom"
        self._gh_branch_work_mode.setEnabled(branch_controls_enabled)
        self._gh_task_branch_naming_style.setEnabled(naming_enabled)
        custom_template_label = getattr(
            self, "_gh_task_branch_custom_template_label", None
        )
        if isinstance(custom_template_label, QWidget):
            custom_template_label.setVisible(show_custom_template)

        custom_template_row = getattr(self, "_gh_task_branch_custom_template_row", None)
        if isinstance(custom_template_row, QWidget):
            custom_template_row.setVisible(show_custom_template)

        self._gh_task_branch_custom_template.setVisible(show_custom_template)
        self._gh_task_branch_custom_template_helper.setVisible(show_custom_template)
        self._gh_task_branch_custom_template.setEnabled(naming_enabled)
        self._gh_task_branch_custom_template_helper.setEnabled(naming_enabled)

    def _load_selected(self) -> None:
        if self._autosave_timer.isActive():
            self._autosave_timer.stop()
        if self._advanced_autosave_timer.isActive():
            self._advanced_autosave_timer.stop()

        env_id = str(self._env_select.currentData() or "")
        env = self._environments.get(env_id)
        self._current_env_id = env_id if env else None
        self._sync_github_polling_override_visibility()

        self._suppress_autosave = True
        try:
            if not env:
                self._name.setText("")
                self._max_agents_running.setText("-1")
                self._headless_desktop_enabled.setChecked(False)
                self._ide_system_override.setCurrentIndex(0)
                self._cache_desktop_build.setChecked(False)
                self._cache_desktop_build.setEnabled(False)
                self._container_caching_enabled.setChecked(False)
                self._use_cross_agents.setChecked(False)
                self._gh_context_enabled.setChecked(False)
                self._gh_context_enabled.setEnabled(False)
                self._github_polling_enabled.setChecked(False)
                trusted_mode_idx = self._agentsnova_trusted_mode.findData("inherit")
                if trusted_mode_idx < 0:
                    trusted_mode_idx = 0
                if trusted_mode_idx >= 0:
                    self._agentsnova_trusted_mode.setCurrentIndex(trusted_mode_idx)
                auto_review_idx = self._agentsnova_auto_review_mode.findData("inherit")
                if auto_review_idx < 0:
                    auto_review_idx = 0
                if auto_review_idx >= 0:
                    self._agentsnova_auto_review_mode.setCurrentIndex(auto_review_idx)
                auto_reactions_idx = self._agentsnova_auto_reactions_mode.findData(
                    "inherit"
                )
                if auto_reactions_idx < 0:
                    auto_reactions_idx = 0
                if auto_reactions_idx >= 0:
                    self._agentsnova_auto_reactions_mode.setCurrentIndex(
                        auto_reactions_idx
                    )
                marker_comment_idx = self._agentsnova_marker_comment_mode.findData(
                    "inherit"
                )
                if marker_comment_idx < 0:
                    marker_comment_idx = 0
                if marker_comment_idx >= 0:
                    self._agentsnova_marker_comment_mode.setCurrentIndex(
                        marker_comment_idx
                    )
                self._interactive_pr_prompt_enabled.setChecked(True)
                no_prompt_mode_idx = self._interactive_pr_no_prompt_mode.findData(
                    INTERACTIVE_PR_NO_PROMPT_MODE_AUTO_CREATE
                )
                if no_prompt_mode_idx < 0:
                    no_prompt_mode_idx = 0
                if no_prompt_mode_idx >= 0:
                    self._interactive_pr_no_prompt_mode.setCurrentIndex(
                        no_prompt_mode_idx
                    )
                self._setup_agents_missing_prompt_enabled.setChecked(False)
                self._interactive_pull_before_run_enabled.setChecked(True)
                branch_work_idx = self._gh_branch_work_mode.findData("task_branch")
                if branch_work_idx < 0:
                    branch_work_idx = 0
                if branch_work_idx >= 0:
                    self._gh_branch_work_mode.setCurrentIndex(branch_work_idx)
                naming_style_idx = self._gh_task_branch_naming_style.findData(
                    "standard"
                )
                if naming_style_idx < 0:
                    naming_style_idx = 0
                if naming_style_idx >= 0:
                    self._gh_task_branch_naming_style.setCurrentIndex(naming_style_idx)
                self._gh_task_branch_custom_template.setText(
                    GH_TASK_BRANCH_CUSTOM_TEMPLATE_DEFAULT
                )
                self._agentsnova_trusted_users_env.set_usernames([])
                self._workspace_type_combo.setCurrentIndex(0)
                self._workspace_target.setText("")
                self._gh_use_host_cli.setChecked(bool(is_gh_available()))
                self._refresh_setup_agents_preview(None)
                self._cache_system_preflight_enabled.setChecked(False)
                self._cache_settings_preflight_enabled.setChecked(False)
                self._cache_ide_preflight_enabled.setChecked(False)
                self._on_container_caching_toggled(Qt.CheckState.Unchecked.value)
                self._env_vars_tab.set_env_vars(
                    {},
                    advanced_mode=False,
                    advanced_acknowledged=False,
                )
                self._mounts_tab.set_mounts(
                    [],
                    advanced_mode=False,
                    advanced_acknowledged=False,
                )
                self._ports_tab.set_desktop_effective_enabled(
                    self._effective_desktop_enabled()
                )
                self._ports_tab.set_ports([], False, False)
                self._prompts_tab.set_prompts([], False)
                self._agents_tab.set_agent_selection(None)
                self._sync_github_branch_naming_controls()
                self._sync_workspace_controls()
                self._sync_headless_desktop_override_visibility()
                self._sync_interactive_pr_controls()
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
            ide_system_override = str(getattr(env, "ide_system_override", "") or "")
            ide_system_idx = self._ide_system_override.findData(ide_system_override)
            if ide_system_idx < 0:
                ide_system_idx = 0
            self._ide_system_override.setCurrentIndex(ide_system_idx)
            self._ports_tab.set_desktop_effective_enabled(
                self._effective_desktop_enabled()
            )
            self._cache_desktop_build.setChecked(
                bool(getattr(env, "cache_desktop_build", False))
            )
            self._cache_desktop_build.setEnabled(self._effective_desktop_enabled())
            self._container_caching_enabled.setChecked(
                bool(getattr(env, "container_caching_enabled", False))
            )
            self._use_cross_agents.setChecked(
                bool(getattr(env, "use_cross_agents", False))
            )
            workspace_type = env.workspace_type or WORKSPACE_NONE
            is_github_env = workspace_type == WORKSPACE_CLONED
            is_local_env = workspace_type == WORKSPACE_MOUNTED

            is_git_repo = False
            if is_local_env:
                is_git_repo = env.detect_git_if_mounted_folder()

            context_available = is_github_env or (is_local_env and is_git_repo)

            self._gh_context_enabled.setChecked(
                bool(getattr(env, "gh_context_enabled", False))
            )
            self._gh_context_enabled.setEnabled(context_available)
            self._github_polling_enabled.setChecked(
                bool(getattr(env, "github_polling_enabled", False))
            )
            trusted_mode = normalize_trusted_mode(
                getattr(env, "agentsnova_trusted_mode", "inherit")
            )
            trusted_mode_idx = self._agentsnova_trusted_mode.findData(trusted_mode)
            if trusted_mode_idx >= 0:
                self._agentsnova_trusted_mode.setCurrentIndex(trusted_mode_idx)
            auto_review_mode = normalize_agentsnova_auto_mode(
                getattr(env, "agentsnova_auto_review_mode", "inherit")
            )
            auto_review_idx = self._agentsnova_auto_review_mode.findData(
                auto_review_mode
            )
            if auto_review_idx >= 0:
                self._agentsnova_auto_review_mode.setCurrentIndex(auto_review_idx)
            auto_reactions_mode = normalize_agentsnova_auto_mode(
                getattr(env, "agentsnova_auto_reactions_mode", "inherit")
            )
            auto_reactions_idx = self._agentsnova_auto_reactions_mode.findData(
                auto_reactions_mode
            )
            if auto_reactions_idx >= 0:
                self._agentsnova_auto_reactions_mode.setCurrentIndex(auto_reactions_idx)
            marker_comment_mode = normalize_agentsnova_marker_comment_mode(
                getattr(env, "agentsnova_marker_comment_mode", "inherit")
            )
            marker_comment_idx = self._agentsnova_marker_comment_mode.findData(
                marker_comment_mode
            )
            if marker_comment_idx >= 0:
                self._agentsnova_marker_comment_mode.setCurrentIndex(marker_comment_idx)
            self._interactive_pr_prompt_enabled.setChecked(
                bool(getattr(env, "interactive_pr_prompt_enabled", True))
            )
            interactive_pr_no_prompt_mode = normalize_interactive_pr_no_prompt_mode(
                getattr(env, "interactive_pr_no_prompt_mode", "auto_create_pr")
            )
            interactive_pr_no_prompt_idx = self._interactive_pr_no_prompt_mode.findData(
                interactive_pr_no_prompt_mode
            )
            if interactive_pr_no_prompt_idx < 0:
                interactive_pr_no_prompt_idx = 0
            if interactive_pr_no_prompt_idx >= 0:
                self._interactive_pr_no_prompt_mode.setCurrentIndex(
                    interactive_pr_no_prompt_idx
                )
            self._setup_agents_missing_prompt_enabled.setChecked(
                bool(getattr(env, "setup_agents_missing_prompt_enabled", False))
            )
            self._interactive_pull_before_run_enabled.setChecked(
                bool(getattr(env, "interactive_pull_before_run_enabled", True))
            )
            branch_work_mode = normalize_gh_branch_work_mode(
                getattr(env, "gh_branch_work_mode", "task_branch")
            )
            branch_work_idx = self._gh_branch_work_mode.findData(branch_work_mode)
            if branch_work_idx >= 0:
                self._gh_branch_work_mode.setCurrentIndex(branch_work_idx)
            naming_style = normalize_gh_task_branch_naming_style(
                getattr(env, "gh_task_branch_naming_style", "standard")
            )
            naming_style_idx = self._gh_task_branch_naming_style.findData(naming_style)
            if naming_style_idx >= 0:
                self._gh_task_branch_naming_style.setCurrentIndex(naming_style_idx)
            self._gh_task_branch_custom_template.setText(
                normalize_gh_task_branch_custom_template(
                    getattr(
                        env,
                        "gh_task_branch_custom_template",
                        GH_TASK_BRANCH_CUSTOM_TEMPLATE_DEFAULT,
                    )
                )
            )
            self._agentsnova_trusted_users_env.set_usernames(
                list(getattr(env, "agentsnova_trusted_users_env", []) or [])
            )

            idx = self._workspace_type_combo.findData(workspace_type)
            if idx >= 0:
                self._workspace_type_combo.setCurrentIndex(idx)
            self._workspace_target.setText(str(env.workspace_target or ""))
            self._gh_use_host_cli.setChecked(
                bool(getattr(env, "gh_use_host_cli", True))
            )
            self._sync_workspace_controls(env=env)
            self._refresh_setup_agents_preview(env)
            self._cache_system_preflight_enabled.setChecked(
                bool(getattr(env, "cache_system_preflight_enabled", False))
            )
            self._cache_settings_preflight_enabled.setChecked(
                bool(getattr(env, "cache_settings_preflight_enabled", False))
            )
            self._cache_ide_preflight_enabled.setChecked(
                bool(getattr(env, "cache_ide_preflight_enabled", False))
            )
            self._on_container_caching_toggled(
                Qt.CheckState.Checked.value
                if bool(getattr(env, "container_caching_enabled", False))
                else Qt.CheckState.Unchecked.value
            )

            self._env_vars_tab.set_env_vars(
                env.env_vars,
                advanced_mode=bool(getattr(env, "env_vars_advanced_mode", False)),
                advanced_acknowledged=bool(
                    getattr(env, "env_vars_advanced_acknowledged", False)
                ),
            )
            self._mounts_tab.set_mounts(
                env.extra_mounts,
                advanced_mode=bool(getattr(env, "mounts_advanced_mode", False)),
                advanced_acknowledged=bool(
                    getattr(env, "mounts_advanced_acknowledged", False)
                ),
            )
            self._ports_tab.set_ports(
                getattr(env, "ports", []) or [],
                bool(getattr(env, "ports_unlocked", False)),
                bool(getattr(env, "ports_advanced_acknowledged", False)),
            )
            self._prompts_tab.set_prompts(
                env.prompts or [], env.prompts_unlocked or False
            )

            use_cross_agents = bool(getattr(env, "use_cross_agents", False))
            cross_agent_allowlist = list(getattr(env, "cross_agent_allowlist", []))
            self._agents_tab.set_cross_agent_allowlist(cross_agent_allowlist)
            self._agents_tab.set_agent_selection(env.agent_selection)
            self._agents_tab.set_cross_agents_enabled(use_cross_agents)
            self._sync_github_branch_naming_controls()
            self._sync_headless_desktop_override_visibility()
            self._sync_interactive_pr_controls()
        finally:
            self._suppress_autosave = False

    def _on_prompts_changed(self) -> None:
        self._queue_advanced_autosave()

    def _on_agents_changed(self) -> None:
        self._queue_advanced_autosave()

    def _on_ports_changed(self) -> None:
        self._queue_advanced_autosave()

    def _queue_advanced_autosave(self, *_args: object) -> None:
        if self._suppress_autosave:
            return
        self._advanced_autosave_timer.start()

    def _on_headless_desktop_toggled(self, state: int) -> None:
        _ = state
        effective_desktop_enabled = self._effective_desktop_enabled()
        self._ports_tab.set_desktop_effective_enabled(effective_desktop_enabled)
        self._cache_desktop_build.setEnabled(effective_desktop_enabled)
        if not effective_desktop_enabled:
            self._cache_desktop_build.setChecked(False)

    def _on_container_caching_toggled(self, state: int) -> None:
        is_enabled = state == Qt.CheckState.Checked.value
        for checkbox in (
            self._cache_system_preflight_enabled,
            self._cache_settings_preflight_enabled,
            self._cache_ide_preflight_enabled,
        ):
            checkbox.setEnabled(is_enabled)

    def _on_use_cross_agents_toggled(self, state: int) -> None:
        is_enabled = state == Qt.CheckState.Checked.value
        self._agents_tab.set_cross_agents_enabled(is_enabled)

    def _on_env_selected(self, index: int) -> None:
        old_env_id = self._current_env_id
        new_env_id = str(self._env_select.currentData() or "")
        if not self.try_autosave(preferred_env_id=new_env_id):
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

    @staticmethod
    def _setup_agents_preview_language(script: str) -> str:
        shebang = str(script or "").split("\n", 1)[0].strip().lower()
        if shebang.startswith("#!"):
            if "fish" in shebang:
                return "fish"
            if "bash" in shebang or "sh" in shebang:
                return "bash"
        return "bash"

    @staticmethod
    def _path_label(*, repo_root: str, path: str | None) -> str:
        if not path:
            return ""
        root = os.path.abspath(os.path.expanduser(str(repo_root or "").strip()))
        candidate = os.path.abspath(os.path.expanduser(str(path or "").strip()))
        if root and candidate.startswith(root + os.sep):
            return os.path.relpath(candidate, root)
        return candidate

    @staticmethod
    def _setup_agents_preview_workdir(env: Environment) -> str:
        workspace_type = str(getattr(env, "workspace_type", "") or "")
        if workspace_type == WORKSPACE_MOUNTED:
            candidate = str(getattr(env, "workspace_target", "") or "").strip()
        elif workspace_type == WORKSPACE_CLONED:
            candidate = managed_repo_checkout_path(
                env.env_id, data_dir=os.path.dirname(default_state_path())
            )
        else:
            candidate = str(getattr(env, "host_workdir", "") or "").strip()
        candidate = os.path.expanduser(candidate) if candidate else ""
        return candidate or os.getcwd()

    @staticmethod
    def _load_direct_setup_agents_script(path: str | None) -> str | None:
        script_path = str(path or "").strip()
        if not script_path:
            return None
        try:
            with open(script_path, "r", encoding="utf-8") as handle:
                return handle.read()
        except Exception:
            return None

    def _refresh_setup_agents_preview(self, env: Environment | None) -> None:
        if env is None:
            self._setup_agents_preview.setPlainText("")
            self._setup_agents_preview.setToolTip(
                "Create in repo: .agents/setup-agents.sh"
            )
            self._setup_agents_preview_highlighter.set_language("bash")
            return

        workspace_type = str(getattr(env, "workspace_type", "") or "")
        host_workdir = self._setup_agents_preview_workdir(env)

        gh_repo: str | None = None
        if workspace_type == WORKSPACE_CLONED:
            candidate = str(getattr(env, "workspace_target", "") or "").strip()
            gh_repo = candidate or None

        preview = None
        try:
            preview = resolve_setup_agents_preview(
                host_workdir=host_workdir,
                environment_id=env.env_id,
                workspace_type=workspace_type,
                workspace_target=str(getattr(env, "workspace_target", "") or ""),
                gh_repo=gh_repo,
                data_dir=os.path.dirname(default_state_path()),
            )
        except Exception:
            preview = None

        repo_edit_path = ".agents/setup-agents.sh"
        if preview is not None:
            repo_edit_path = self._path_label(
                repo_root=preview.repo_root,
                path=preview.preferred_repo_script_path,
            )
        if not repo_edit_path:
            repo_edit_path = ".agents/setup-agents.sh"

        direct_script = self._load_direct_setup_agents_script(
            preview.repo_script_path if preview is not None else None
        )
        if direct_script is not None:
            preview_text = direct_script
            tooltip = f"Edit in repo: {repo_edit_path}"
        elif preview is not None:
            preview_text = str(preview.setup_script or "")
            if preview_text:
                tooltip = f"Create in repo: {repo_edit_path} (showing metadata mirror)"
            else:
                tooltip = f"Create in repo: {repo_edit_path}"
        else:
            preview_text = ""
            tooltip = f"Create in repo: {repo_edit_path}"
        self._setup_agents_preview.setToolTip(tooltip)

        self._setup_agents_preview.setPlainText(preview_text)
        if preview_text.strip():
            self._setup_agents_preview_highlighter.set_language(
                self._setup_agents_preview_language(preview_text)
            )
        else:
            self._setup_agents_preview_highlighter.set_language("bash")
        self._setup_agents_preview.document().setModified(False)
