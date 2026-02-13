from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtCore import QTimer
from PySide6.QtCore import Signal
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
from agents_runner.gh_management import is_gh_available
from agents_runner.persistence import default_state_path
from agents_runner.ui.constants import (
    BUTTON_ROW_SPACING,
    CARD_MARGINS,
    CARD_SPACING,
    HEADER_MARGINS,
    HEADER_SPACING,
    LEFT_NAV_PANEL_WIDTH,
    MAIN_LAYOUT_MARGINS,
    MAIN_LAYOUT_SPACING,
)
from agents_runner.ui.graphics import _EnvironmentTintOverlay
from agents_runner.ui.pages.environments_actions import _EnvironmentsPageActionsMixin
from agents_runner.ui.pages.environments_form import _EnvironmentsFormMixin
from agents_runner.ui.pages.environments_navigation import _EnvironmentsNavigationMixin
from agents_runner.ui.utils import _apply_environment_combo_tint
from agents_runner.ui.utils import _stain_color
from agents_runner.ui.widgets import GlassCard


class EnvironmentsPage(
    QWidget,
    _EnvironmentsNavigationMixin,
    _EnvironmentsFormMixin,
    _EnvironmentsPageActionsMixin,
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
        self._autosave_timer.setInterval(450)
        self._autosave_timer.timeout.connect(self._emit_autosave)

        self._pane_animation = None
        self._pane_rest_pos = None
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

        back = QToolButton()
        back.setText("Back")
        back.setToolButtonStyle(Qt.ToolButtonTextOnly)
        back.clicked.connect(self._on_back)

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

        test_btn = QToolButton()
        test_btn.setText("Test preflight")
        test_btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
        test_btn.clicked.connect(self._on_test_preflight)

        top_row.addWidget(QLabel("Environment"))
        top_row.addWidget(self._env_select, 1)
        top_row.addWidget(new_btn)
        top_row.addWidget(delete_btn)
        top_row.addWidget(test_btn)
        card_layout.addLayout(top_row)

        self._compact_nav = QComboBox()
        self._compact_nav.setObjectName("SettingsCompactNav")
        self._compact_nav.setVisible(False)
        self._compact_nav.currentIndexChanged.connect(self._on_compact_nav_changed)
        card_layout.addWidget(self._compact_nav)

        panes_layout = QHBoxLayout()
        panes_layout.setContentsMargins(0, 0, 0, 0)
        panes_layout.setSpacing(14)

        self._nav_panel = QWidget()
        self._nav_panel.setObjectName("SettingsNavPanel")
        self._nav_panel.setFixedWidth(LEFT_NAV_PANEL_WIDTH)
        nav_layout = QVBoxLayout(self._nav_panel)
        nav_layout.setContentsMargins(10, 10, 10, 10)
        nav_layout.setSpacing(6)

        self._right_panel = QWidget()
        self._right_panel.setObjectName("SettingsPaneHost")
        right_layout = QVBoxLayout(self._right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        self._page_stack = QStackedWidget()
        self._page_stack.setObjectName("SettingsPageStack")
        right_layout.addWidget(self._page_stack, 1)

        panes_layout.addWidget(self._nav_panel)
        panes_layout.addWidget(self._right_panel, 1)
        card_layout.addLayout(panes_layout, 1)

        layout.addWidget(card, 1)

        self._build_controls()
        self._build_pages()
        self._build_navigation(nav_layout)
        self._connect_autosave_signals()

        if self._pane_specs:
            first_key = self._pane_specs[0].key
            self._set_active_navigation(first_key)
            self._set_current_pane(first_key, animate=False)

        self._update_navigation_mode()

        self._tint_overlay = _EnvironmentTintOverlay(self, alpha=13)
        self._tint_overlay.raise_()

    def resizeEvent(self, event) -> None:
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
        self._settings_data = settings_data
        self._ports_tab.set_desktop_effective_enabled(self._effective_desktop_enabled())

    def _effective_desktop_enabled(self) -> bool:
        force = bool(self._settings_data.get("headless_desktop_enabled") or False)
        env_enabled = bool(self._headless_desktop_enabled.isChecked())
        return bool(force or env_enabled)

    def _load_selected(self) -> None:
        if self._autosave_timer.isActive():
            self._autosave_timer.stop()

        env_id = str(self._env_select.currentData() or "")
        env = self._environments.get(env_id)
        self._current_env_id = env_id if env else None

        self._suppress_autosave = True
        try:
            if not env:
                self._name.setText("")
                self._max_agents_running.setText("-1")
                self._headless_desktop_enabled.setChecked(False)
                self._cache_desktop_build.setChecked(False)
                self._cache_desktop_build.setEnabled(False)
                self._container_caching_enabled.setChecked(False)
                self._use_cross_agents.setChecked(False)
                self._gh_context_enabled.setChecked(False)
                self._gh_context_enabled.setEnabled(False)
                self._gh_context_label.setVisible(False)
                self._gh_context_row.setVisible(False)
                self._workspace_type_combo.setCurrentIndex(0)
                self._workspace_target.setText("")
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
                self._ports_tab.set_desktop_effective_enabled(
                    self._effective_desktop_enabled()
                )
                self._ports_tab.set_ports([], False, False)
                self._prompts_tab.set_prompts([], False)
                self._agents_tab.set_agent_selection(None)
                self._sync_workspace_controls()
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
            self._ports_tab.set_desktop_effective_enabled(
                self._effective_desktop_enabled()
            )
            self._cache_desktop_build.setChecked(
                bool(getattr(env, "cache_desktop_build", False))
            )
            self._cache_desktop_build.setEnabled(
                bool(getattr(env, "headless_desktop_enabled", False))
            )
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
            self._gh_context_label.setVisible(context_available)
            self._gh_context_row.setVisible(context_available)

            idx = self._workspace_type_combo.findData(workspace_type)
            if idx >= 0:
                self._workspace_type_combo.setCurrentIndex(idx)
            self._workspace_target.setText(str(env.workspace_target or ""))
            self._gh_use_host_cli.setChecked(
                bool(getattr(env, "gh_use_host_cli", True))
            )
            self._sync_workspace_controls(env=env)

            container_caching = bool(getattr(env, "container_caching_enabled", False))

            self._preflight_enabled.setChecked(bool(env.preflight_enabled))
            self._preflight_script.setEnabled(bool(env.preflight_enabled))
            self._preflight_script.setPlainText(env.preflight_script or "")

            cached_script = str(getattr(env, "cached_preflight_script", "") or "")
            has_cached = bool(cached_script.strip())
            self._cached_preflight_enabled.setChecked(has_cached)
            self._cached_preflight_script.setEnabled(has_cached)
            self._cached_preflight_script.setPlainText(cached_script)

            self._run_preflight_enabled.setChecked(bool(env.preflight_enabled))
            self._run_preflight_script.setEnabled(bool(env.preflight_enabled))
            self._run_preflight_script.setPlainText(env.preflight_script or "")

            self._preflight_stack.setCurrentIndex(1 if container_caching else 0)

            env_lines = "\n".join(f"{k}={v}" for k, v in sorted(env.env_vars.items()))
            self._env_vars.setPlainText(env_lines)
            self._mounts.setPlainText("\n".join(env.extra_mounts))
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
        finally:
            self._suppress_autosave = False

    def _on_prompts_changed(self) -> None:
        self._queue_debounced_autosave()

    def _on_agents_changed(self) -> None:
        self._queue_debounced_autosave()

    def _on_ports_changed(self) -> None:
        self._queue_debounced_autosave()

    def _on_headless_desktop_toggled(self, state: int) -> None:
        is_enabled = state == Qt.CheckState.Checked.value
        self._ports_tab.set_desktop_effective_enabled(self._effective_desktop_enabled())
        self._cache_desktop_build.setEnabled(is_enabled)
        if not is_enabled:
            self._cache_desktop_build.setChecked(False)

    def _on_container_caching_toggled(self, state: int) -> None:
        is_enabled = state == Qt.CheckState.Checked.value
        self._preflight_stack.setCurrentIndex(1 if is_enabled else 0)

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
