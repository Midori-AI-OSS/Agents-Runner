from __future__ import annotations

from pathlib import Path
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QSignalBlocker, Qt
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import QCheckBox
from PySide6.QtWidgets import QComboBox
from PySide6.QtWidgets import QDoubleSpinBox
from PySide6.QtWidgets import QGridLayout
from PySide6.QtWidgets import QHBoxLayout
from PySide6.QtWidgets import QLabel
from PySide6.QtWidgets import QLineEdit
from PySide6.QtWidgets import QDialog
from PySide6.QtWidgets import QMessageBox
from PySide6.QtWidgets import QPlainTextEdit
from PySide6.QtWidgets import QSizePolicy
from PySide6.QtWidgets import QSlider
from PySide6.QtWidgets import QToolButton
from PySide6.QtWidgets import QVBoxLayout
from PySide6.QtWidgets import QWidget

from agents_runner.agent_cli import normalize_agent
from agents_runner.agent_labels import format_agent_ui_label
from agents_runner.agent_systems import available_agent_system_names
from agents_runner.agent_systems import get_default_agent_system_name
from agents_runner.environments import load_environments
from agents_runner.environments import normalize_opencode_interactive_mode
from agents_runner.terminal_apps import detect_terminal_options
from agents_runner.ui.pages.github_trust import (
    collect_seed_usernames_for_cloned_environments,
)
from agents_runner.ui.pages.github_username_list import GitHubUsernameListWidget
from agents_runner.ui.radio import RadioController
from agents_runner.ui.dialogs.theme_preview_dialog import ThemePreviewDialog
from agents_runner.ui.graphics import available_ui_theme_names
from agents_runner.ui.graphics import normalize_ui_theme_name
from agents_runner.ui.widgets import EdgeFadeScrollArea
from agents_runner.ui.widgets.artifact_highlighter import ArtifactSyntaxHighlighter
from agents_runner.ui.widgets.theme_preview import ThemePreviewTile
from agents_runner.ui.constants import (
    GRID_HORIZONTAL_SPACING,
    GRID_VERTICAL_SPACING,
    BUTTON_ROW_SPACING,
)
from agents_runner.ui.utils.form_helpers import (
    add_grid_row,
    configure_form_grid,
    create_stretch_row,
)
from agents_runner.gh.automation_policy import normalize_default_marker_comment_mode


@dataclass(frozen=True)
class _SettingsPaneSpec:
    key: str
    title: str
    subtitle: str
    section: str


class SettingsFormMixin:
    _PREFLIGHT_PRESETS_DIRNAME = "preflight-scripts"
    _PREFLIGHT_PRESET_SUFFIXES = {".sh", ".bash", ".zsh"}

    def _default_pane_specs(self) -> list[_SettingsPaneSpec]:
        specs = [
            _SettingsPaneSpec(
                key="general_preferences",
                title="General Preferences",
                subtitle="Global editor and default behavior toggles.",
                section="General",
            ),
            _SettingsPaneSpec(
                key="themes",
                title="Themes",
                subtitle="Background theme behavior and overrides.",
                section="Appearance",
            ),
            _SettingsPaneSpec(
                key="agent_defaults",
                title="Agent Defaults",
                subtitle="Default agent and shell behavior.",
                section="Agent Setup",
            ),
            _SettingsPaneSpec(
                key="github_config",
                title="Config",
                subtitle="GitHub polling, auto-review, and write confirmation controls.",
                section="GitHub",
            ),
            _SettingsPaneSpec(
                key="github_trusted_users",
                title="Trusted Users",
                subtitle="Global trusted usernames for @agentsnova auto-review checks.",
                section="GitHub",
            ),
            _SettingsPaneSpec(
                key="runtime_behavior",
                title="Runtime Behavior",
                subtitle="Container and desktop runtime toggles.",
                section="Runtime",
            ),
            _SettingsPaneSpec(
                key="preflight_script",
                title="Preflight Script",
                subtitle="Global setup script executed before setup-agents.sh.",
                section="Runtime",
            ),
        ]
        if bool(getattr(self, "_radio_supported", True)):
            specs.append(
                _SettingsPaneSpec(
                    key="radio",
                    title="Radio",
                    subtitle="Midori AI Radio playback controls and defaults.",
                    section="Runtime",
                )
            )
        return specs

    def _build_controls(self) -> None:
        self._use = QComboBox()
        self._populate_agent_combo()

        self._shell = QComboBox()
        for label, value in [
            ("bash", "bash"),
            ("sh", "sh"),
            ("zsh", "zsh"),
            ("fish", "fish"),
            ("tmux", "tmux"),
        ]:
            self._shell.addItem(label, value)

        self._interactive_terminal = QComboBox()
        self._interactive_terminal.setToolTip(
            "Default terminal used by Run Interactive and Get Agent Help."
        )
        self._refresh_terminal_options(selected_terminal_id="")

        self._refresh_interactive_terminal = QToolButton()
        self._refresh_interactive_terminal.setText("Refresh")
        self._refresh_interactive_terminal.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self._refresh_interactive_terminal.clicked.connect(
            self._on_refresh_terminal_options_clicked
        )

        self._opencode_interactive_mode = QComboBox()
        self._opencode_interactive_mode.addItem("Terminal", "terminal")
        self._opencode_interactive_mode.addItem("Web", "web")
        self._opencode_interactive_mode.addItem("Ask", "ask")
        self._opencode_interactive_mode.setToolTip(
            "Default OpenCode launch mode for Run Interactive."
        )

        self._ui_theme = QComboBox()
        self._ui_theme.setToolTip(
            "Auto syncs background theme to the active agent.\n"
            "Select a specific theme to force an override."
        )
        self._popup_theme_animation_enabled = QCheckBox("Enabled")
        self._popup_theme_animation_enabled.setToolTip(
            "When enabled, themed popup backgrounds stay animated. "
            "Disable to render popups as static backgrounds."
        )
        self._popup_theme_animation_enabled.setChecked(True)
        self._theme_preview_tiles: dict[str, ThemePreviewTile] = {}
        self._theme_preview_order: list[str] = []
        self._theme_preview_grid: QGridLayout | None = None
        self._theme_preview_host: QWidget | None = None
        self._ui_theme.currentIndexChanged.connect(self._on_theme_combo_changed)
        self._refresh_theme_options(selected="auto")

        self._preflight_enabled = QToolButton()
        self._preflight_enabled.setCheckable(True)
        self._preflight_enabled.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self._preflight_enabled.setToolTip(
            "Run global preflight before setup-agents.sh."
        )
        self._preflight_enabled.toggled.connect(self._on_preflight_enabled_toggled)

        self._append_pixelarch_context = QCheckBox("Enabled")
        self._append_pixelarch_context.setToolTip(
            "When enabled, appends a short note to prompts passed to Run Agent.\n"
            "This does not affect Run Interactive."
        )

        self._headless_desktop_enabled = QCheckBox("Enabled")
        self._headless_desktop_enabled.setToolTip(
            "When enabled, this overrides per-environment headless desktop settings."
        )
        self._gpu_enabled = QCheckBox("Enabled")
        self._gpu_enabled.setToolTip(
            "When enabled, task containers request GPU runtime access (`--gpus all`) "
            "for Agent and Interactive runs."
        )
        self._auto_navigate_on_run_agent_start = QCheckBox("Enabled")
        self._auto_navigate_on_run_agent_start.setToolTip(
            "When enabled, starting a Run Agent task switches to the Home dashboard."
        )
        self._auto_navigate_on_run_interactive_start = QCheckBox("Enabled")
        self._auto_navigate_on_run_interactive_start.setToolTip(
            "When enabled, starting a Run Interactive task switches to the Home dashboard."
        )

        self._gh_context_default = QCheckBox("Enabled")
        self._gh_context_default.setToolTip(
            "Only affects newly created environments. Existing environments keep their settings."
        )

        self._spellcheck_enabled = QCheckBox("Enabled")
        self._spellcheck_enabled.setToolTip(
            "Underlines misspelled words in the prompt editor and provides suggestions."
        )

        self._mount_host_cache = QCheckBox("Enabled")
        self._mount_host_cache.setToolTip(
            "Mounts ~/.cache to speed up package manager installs across environments."
        )

        self._github_workroom_prefer_browser = QCheckBox("Enabled")
        self._github_workroom_prefer_browser.setToolTip(
            "When enabled, opening an issue or pull request goes directly to the system browser."
        )

        self._github_write_confirmation_mode = QComboBox()
        self._github_write_confirmation_mode.addItem("Always confirm", "always")
        self._github_write_confirmation_mode.addItem(
            "Confirm destructive only",
            "destructive_only",
        )
        self._github_write_confirmation_mode.addItem("No confirmations", "never")
        self._github_write_confirmation_mode.setToolTip(
            "Controls confirmation prompts for GitHub write actions "
            "(open/close, comments, reaction markers)."
        )

        self._agentsnova_auto_review_enabled = QCheckBox("Enabled")
        self._agentsnova_auto_review_enabled.setToolTip(
            "When enabled, PR/Issue mentions of @agentsnova can auto-queue tasks."
        )
        self._agentsnova_auto_marker_comments_mode = QComboBox()
        self._agentsnova_auto_marker_comments_mode.addItem(
            "Keep",
            "keep",
        )
        self._agentsnova_auto_marker_comments_mode.addItem(
            "Delete after 15s",
            "delete_after_15s",
        )
        self._agentsnova_auto_marker_comments_mode.addItem(
            "Disabled",
            "disabled",
        )
        self._agentsnova_auto_marker_comments_mode.setToolTip(
            "Default mode for @agentsnova marker comments. Environments can inherit "
            "this mode or override it."
        )
        self._agentsnova_auto_reactions_enabled = QCheckBox("Enabled")
        self._agentsnova_auto_reactions_enabled.setToolTip(
            "When enabled, @agentsnova queue triggers apply GitHub `eyes` reactions."
        )
        self._github_polling_enabled = QCheckBox("Enabled")
        self._github_polling_enabled.setToolTip(
            "When enabled, GitHub Issues/PRs poll in the background across enabled environments."
        )
        self._github_poll_startup_delay_s = QLineEdit()
        self._github_poll_startup_delay_s.setValidator(QIntValidator(0, 3600, self))
        self._github_poll_startup_delay_s.setPlaceholderText("35")
        self._github_poll_startup_delay_s.setMaximumWidth(120)
        self._github_poll_startup_delay_s.setToolTip(
            "Seconds to wait after app startup before beginning background GitHub polling."
        )
        self._agentsnova_trusted_users_global = GitHubUsernameListWidget()
        self._agentsnova_trusted_users_global.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self._agentsnova_trusted_users_global.set_add_button_visible(False)
        self._add_trusted_user_global = (
            self._agentsnova_trusted_users_global.create_add_button(self)
        )
        self._setup_github_defaults_global = QToolButton()
        self._setup_github_defaults_global.setText("Setup Defaults")
        self._setup_github_defaults_global.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self._setup_github_defaults_global.setToolTip(
            "Seed trusted users from cloned environment owners/org members and current gh login."
        )
        self._setup_github_defaults_global.clicked.connect(
            self._on_setup_global_github_defaults
        )

        self._preflight_script = QPlainTextEdit()
        self._preflight_script.setPlaceholderText(
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            "\n"
            "# Runs inside the container before the agent command.\n"
            "# Runs on every environment, before setup-agents.sh.\n"
            "# This script is mounted read-only and deleted from the host after task finish.\n"
        )
        self._preflight_script.setTabChangesFocus(True)
        self._preflight_script.setEnabled(False)
        self._on_preflight_enabled_toggled(bool(self._preflight_enabled.isChecked()))
        self._preflight_script.textChanged.connect(
            self._on_preflight_script_text_changed
        )
        self._preflight_script_highlighter = ArtifactSyntaxHighlighter(
            self._preflight_script.document()
        )
        self._refresh_preflight_script_highlighting(
            str(self._preflight_script.toPlainText() or "")
        )

        self._recommended_preflights = QComboBox()
        self._recommended_preflights.setToolTip("Load a recommended preflight script.")
        self._populate_recommended_preflights()
        self._recommended_preflights.currentIndexChanged.connect(
            self._on_recommended_preflight_selected
        )

        self._test_preflights = QToolButton()
        self._test_preflights.setText("Run preflight checks")
        self._test_preflights.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self._test_preflights.setToolTip(
            "Run preflight smoke test for all environments."
        )
        self._test_preflights.clicked.connect(self._on_test_preflight)

        self._radio_enabled = QCheckBox("Enabled")
        self._radio_enabled.setToolTip(
            "Controls whether the navbar radio system is enabled."
        )
        self._radio_autostart = QCheckBox("Enabled")
        self._radio_autostart.setToolTip(
            "Starts playback automatically at launch when radio is enabled."
        )
        self._radio_autostart.setEnabled(False)

        self._radio_channel_values: list[str] = []
        self._radio_channel_enabled = False
        self._radio_channel = QComboBox()
        self._radio_channel.setToolTip(
            "Select a radio channel. All channels uses the server default behavior."
        )
        self._radio_channel.setEnabled(False)
        self.set_radio_channel_options([], selected="", enabled=False)

        self._radio_quality = QComboBox()
        self._radio_quality.addItem("Low (96 kbps)", "low")
        self._radio_quality.addItem("Medium (160 kbps)", "medium")
        self._radio_quality.addItem("High (320 kbps)", "high")

        self._radio_volume = QSlider(Qt.Horizontal)
        self._radio_volume.setObjectName("SettingsVolumeSlider")
        self._radio_volume.setRange(0, 100)
        self._radio_volume.setValue(70)
        self._radio_volume_value = QLabel("70%")
        self._radio_volume_value.setObjectName("SettingsPaneSubtitle")
        self._radio_volume.valueChanged.connect(self._on_radio_volume_value_changed)

        self._radio_loudness_boost_enabled = QCheckBox("Enabled")
        self._radio_loudness_boost_enabled.setToolTip(
            "Applies a gain multiplier to radio volume mapping."
        )
        self._radio_loudness_boost_enabled.toggled.connect(
            self._on_radio_loudness_boost_toggled
        )

        self._radio_loudness_boost_factor = QDoubleSpinBox()
        self._radio_loudness_boost_factor.setObjectName("SettingsBoostSpinBox")
        self._radio_loudness_boost_factor.setRange(
            RadioController.LOUDNESS_BOOST_MIN,
            RadioController.LOUDNESS_BOOST_MAX,
        )
        self._radio_loudness_boost_factor.setSingleStep(
            RadioController.LOUDNESS_BOOST_STEP
        )
        self._radio_loudness_boost_factor.setDecimals(2)
        self._radio_loudness_boost_factor.setValue(
            RadioController.LOUDNESS_BOOST_DEFAULT
        )
        self._radio_loudness_boost_factor.setSuffix("x")
        self._radio_loudness_boost_factor.setEnabled(False)
        self._radio_loudness_boost_factor.setToolTip(
            "Boost multiplier for radio loudness. Effective output is capped by Qt "
            "audio output at 100%."
        )
        self._radio_loudness_boost_factor.valueChanged.connect(
            self._on_radio_loudness_boost_factor_changed
        )

        self._radio_enabled.toggled.connect(self._radio_autostart.setEnabled)

    def _build_pages(self) -> None:
        specs_by_key = {spec.key: spec for spec in self._pane_specs}

        general_page, general_body = self._create_page(
            specs_by_key["general_preferences"]
        )
        terminal_layout = QGridLayout()
        configure_form_grid(terminal_layout)
        add_grid_row(terminal_layout, 0, QLabel("Spellcheck"), self._spellcheck_enabled)
        add_grid_row(
            terminal_layout,
            1,
            QLabel("GitHub context default"),
            self._gh_context_default,
        )
        add_grid_row(
            terminal_layout,
            2,
            QLabel("Append PixelArch context"),
            self._append_pixelarch_context,
        )
        add_grid_row(
            terminal_layout,
            3,
            QLabel("Interactive terminal"),
            self._interactive_terminal,
            self._refresh_interactive_terminal,
        )
        general_body.addLayout(terminal_layout)
        general_body.addStretch(1)
        self._register_page("general_preferences", general_page)

        themes_page, themes_body = self._create_page(specs_by_key["themes"])
        themes_grid = QGridLayout()
        configure_form_grid(themes_grid)
        add_grid_row(
            themes_grid,
            0,
            QLabel("Animate popup backgrounds"),
            self._popup_theme_animation_enabled,
        )
        add_grid_row(themes_grid, 1, QLabel("Theme"), self._ui_theme)
        themes_body.addLayout(themes_grid)
        previews_heading = QLabel("Theme previews")
        previews_heading.setObjectName("SettingsPaneSubtitle")
        themes_body.addWidget(previews_heading)

        self._theme_preview_host = QWidget(themes_page)
        self._theme_preview_host.setObjectName("ThemePreviewGridHost")
        self._theme_preview_grid = QGridLayout(self._theme_preview_host)
        self._theme_preview_grid.setContentsMargins(0, 0, 0, 0)
        self._theme_preview_grid.setHorizontalSpacing(GRID_HORIZONTAL_SPACING)
        self._theme_preview_grid.setVerticalSpacing(GRID_VERTICAL_SPACING)
        themes_body.addWidget(self._theme_preview_host)
        self._refresh_theme_preview_tiles(selected="auto")
        themes_body.addStretch(1)
        self._register_page("themes", themes_page)

        agent_page, agent_body = self._create_page(specs_by_key["agent_defaults"])
        agent_grid = QGridLayout()
        configure_form_grid(agent_grid)
        add_grid_row(agent_grid, 0, QLabel("Agent CLI"), self._use)
        add_grid_row(agent_grid, 1, QLabel("Agent Shell"), self._shell)
        add_grid_row(
            agent_grid,
            2,
            QLabel("OpenCode interactive"),
            self._opencode_interactive_mode,
        )
        agent_body.addLayout(agent_grid)
        agent_body.addStretch(1)
        self._register_page("agent_defaults", agent_page)

        github_config_page, github_config_body = self._create_page(
            specs_by_key["github_config"]
        )
        github_grid = QGridLayout()
        configure_form_grid(github_grid)
        add_grid_row(
            github_grid,
            0,
            QLabel("Workroom browser"),
            self._github_workroom_prefer_browser,
        )
        add_grid_row(
            github_grid,
            1,
            QLabel("Auto-review queueing"),
            self._agentsnova_auto_review_enabled,
        )
        add_grid_row(
            github_grid,
            2,
            QLabel("Auto reactions"),
            self._agentsnova_auto_reactions_enabled,
        )
        add_grid_row(
            github_grid,
            3,
            QLabel("GitHub polling"),
            self._github_polling_enabled,
        )
        add_grid_row(
            github_grid,
            4,
            QLabel("Default marker comments"),
            self._agentsnova_auto_marker_comments_mode,
        )
        add_grid_row(
            github_grid,
            5,
            QLabel("GitHub write confirmations"),
            self._github_write_confirmation_mode,
        )
        add_grid_row(
            github_grid,
            6,
            QLabel("Polling startup delay (s)"),
            self._github_poll_startup_delay_s,
        )
        github_config_body.addLayout(github_grid)
        github_config_body.addStretch(1)
        self._register_page("github_config", github_config_page)

        github_trusted_page, github_trusted_body = self._create_page(
            specs_by_key["github_trusted_users"]
        )
        github_trusted_body.addWidget(self._agentsnova_trusted_users_global, 1)

        github_actions = QHBoxLayout()
        github_actions.setSpacing(BUTTON_ROW_SPACING)
        github_actions.addWidget(self._add_trusted_user_global)
        github_actions.addStretch(1)
        github_actions.addWidget(self._setup_github_defaults_global)
        github_trusted_body.addLayout(github_actions)
        self._register_page("github_trusted_users", github_trusted_page)

        runtime_page, runtime_body = self._create_page(specs_by_key["runtime_behavior"])
        runtime_grid = QGridLayout()
        configure_form_grid(runtime_grid)
        add_grid_row(
            runtime_grid,
            0,
            QLabel("Force headless desktop"),
            self._headless_desktop_enabled,
        )
        add_grid_row(
            runtime_grid,
            1,
            QLabel("Enable GPU"),
            self._gpu_enabled,
        )
        add_grid_row(
            runtime_grid,
            2,
            QLabel("Navigate Home on Run Agent start"),
            self._auto_navigate_on_run_agent_start,
        )
        add_grid_row(
            runtime_grid,
            3,
            QLabel("Navigate Home on Run Interactive start"),
            self._auto_navigate_on_run_interactive_start,
        )
        add_grid_row(
            runtime_grid,
            4,
            QLabel("Mount host cache"),
            self._mount_host_cache,
        )
        runtime_body.addLayout(runtime_grid)
        runtime_body.addStretch(1)
        self._register_page("runtime_behavior", runtime_page)

        preflight_page, preflight_body = self._create_page(
            specs_by_key["preflight_script"]
        )
        preflight_body.addWidget(self._preflight_script, 1)
        preflight_actions = QHBoxLayout()
        preflight_actions.setSpacing(BUTTON_ROW_SPACING)
        preflight_actions.addWidget(self._preflight_enabled)
        preflight_actions.addWidget(self._recommended_preflights)
        preflight_actions.addWidget(self._test_preflights)
        preflight_actions.addStretch(1)
        autosave_hint = QLabel("Changes save automatically.")
        autosave_hint.setObjectName("SettingsPaneSubtitle")
        preflight_actions.addWidget(autosave_hint)
        preflight_body.addLayout(preflight_actions)
        self._register_page("preflight_script", preflight_page)

        radio_spec = specs_by_key.get("radio")
        if radio_spec is not None:
            radio_page, radio_body = self._create_page(radio_spec)
            radio_grid = QGridLayout()
            configure_form_grid(radio_grid)
            add_grid_row(radio_grid, 0, QLabel("Midori AI Radio"), self._radio_enabled)
            add_grid_row(
                radio_grid, 1, QLabel("Radio auto-start"), self._radio_autostart
            )
            add_grid_row(radio_grid, 2, QLabel("Channel"), self._radio_channel)
            add_grid_row(radio_grid, 3, QLabel("Stream quality"), self._radio_quality)

            volume_row = QWidget(radio_page)
            volume_layout = QHBoxLayout(volume_row)
            volume_layout.setContentsMargins(0, 0, 0, 0)
            volume_layout.setSpacing(BUTTON_ROW_SPACING)
            volume_layout.addWidget(self._radio_volume, 1)
            volume_layout.addWidget(self._radio_volume_value)
            add_grid_row(radio_grid, 4, QLabel("Volume"), volume_row)

            boost_row = create_stretch_row(
                self._radio_loudness_boost_enabled,
                self._radio_loudness_boost_factor,
                stretch_index=2,
            )
            add_grid_row(radio_grid, 5, QLabel("Loudness"), boost_row)

            radio_body.addLayout(radio_grid)
            radio_body.addStretch(1)
            self._register_page("radio", radio_page)

    def _build_navigation(self, nav_layout: QVBoxLayout) -> None:
        sections: dict[str, list[_SettingsPaneSpec]] = {}
        for spec in self._pane_specs:
            sections.setdefault(spec.section, []).append(spec)

        for section_title, specs in sections.items():
            section_label = QLabel(section_title)
            section_label.setObjectName("SettingsNavSection")
            nav_layout.addWidget(section_label)

            for spec in specs:
                button = QToolButton()
                button.setObjectName("SettingsNavButton")
                button_label = (
                    "Preferences" if spec.key == "general_preferences" else spec.title
                )
                button.setText(button_label)
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
                self._compact_nav.addItem(button_label, spec.key)

        nav_layout.addStretch(1)

    def _create_page(self, spec: _SettingsPaneSpec) -> tuple[QWidget, QVBoxLayout]:
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

    def _populate_agent_combo(self) -> None:
        selected = str(self._use.currentData() or "") if hasattr(self, "_use") else ""

        with QSignalBlocker(self._use):
            self._use.clear()
            for agent_name in available_agent_system_names(include_internal=False):
                label = format_agent_ui_label(agent_name)
                self._use.addItem(label, agent_name)

            if self._use.count() == 0:
                default_name = get_default_agent_system_name()
                self._use.addItem(format_agent_ui_label(default_name), default_name)

        preferred = normalize_agent(selected or str(self._use.itemData(0) or ""))
        self._set_combo_value(self._use, preferred, fallback=preferred)

    def _refresh_theme_options(self, selected: str | None) -> None:
        normalized_selected = normalize_ui_theme_name(selected, allow_auto=True)

        with QSignalBlocker(self._ui_theme):
            self._ui_theme.clear()
            self._ui_theme.addItem("Auto (sync to active agent)", "auto")
            for theme_name in available_ui_theme_names():
                self._ui_theme.addItem(self._format_theme_label(theme_name), theme_name)
            self._set_combo_value(self._ui_theme, normalized_selected, fallback="auto")
        self._refresh_theme_preview_tiles(selected=normalized_selected)

    def _refresh_theme_preview_tiles(self, selected: str | None) -> None:
        if self._theme_preview_grid is None:
            return

        normalized_selected = normalize_ui_theme_name(selected, allow_auto=True)
        theme_names = [name for name in available_ui_theme_names() if str(name).strip()]
        if theme_names != self._theme_preview_order:
            self._rebuild_theme_preview_tiles(theme_names)

        for theme_name, tile in self._theme_preview_tiles.items():
            tile.set_selected(
                normalized_selected != "auto" and theme_name == normalized_selected
            )

    def _rebuild_theme_preview_tiles(self, theme_names: list[str]) -> None:
        if self._theme_preview_grid is None:
            return

        self._theme_preview_order = list(theme_names)
        self._theme_preview_tiles.clear()
        self._clear_layout(self._theme_preview_grid)

        columns = 3
        if not theme_names:
            empty = QLabel("No themes available.")
            empty.setObjectName("SettingsPaneSubtitle")
            self._theme_preview_grid.addWidget(empty, 0, 0, 1, columns)
            for col in range(columns):
                self._theme_preview_grid.setColumnStretch(col, 1)
            return

        for index, theme_name in enumerate(theme_names):
            row = index // columns
            col = index % columns
            tile = ThemePreviewTile(
                theme_name=theme_name,
                label=self._format_theme_label(theme_name),
                parent=self._theme_preview_host,
            )
            tile.clicked.connect(self._on_theme_preview_tile_clicked)
            self._theme_preview_grid.addWidget(tile, row, col)
            self._theme_preview_tiles[theme_name] = tile

        for col in range(columns):
            self._theme_preview_grid.setColumnStretch(col, 1)

        trailing_row = (len(theme_names) + columns - 1) // columns
        self._theme_preview_grid.setRowStretch(trailing_row, 1)

    def _on_theme_combo_changed(self, _index: int) -> None:
        theme_value = normalize_ui_theme_name(
            str(self._ui_theme.currentData() or "auto"),
            allow_auto=True,
        )
        self._refresh_theme_preview_tiles(selected=theme_value)

    def _on_theme_preview_tile_clicked(self, theme_name: str) -> None:
        normalized_theme = normalize_ui_theme_name(theme_name, allow_auto=False)
        dialog = ThemePreviewDialog(
            theme_name=normalized_theme,
            theme_label=self._format_theme_label(normalized_theme),
            parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        applied_theme = dialog.applied_theme_name()
        if not applied_theme:
            return

        normalized_selected = normalize_ui_theme_name(applied_theme, allow_auto=True)
        self._set_combo_value(self._ui_theme, normalized_selected, fallback="auto")
        self._refresh_theme_preview_tiles(selected=normalized_selected)

    @staticmethod
    def _clear_layout(layout: QGridLayout) -> None:
        while layout.count() > 0:
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    @staticmethod
    def _format_theme_label(value: str) -> str:
        normalized = str(value or "").strip().lower()
        if normalized == "midoriai_dark":
            return "Midori AI (Dark Theme)"
        if normalized == "midoriai_light":
            return "Midori AI (Light Theme)"
        try:
            return format_agent_ui_label(normalized)
        except Exception:
            pass
        return SettingsFormMixin._format_key_label(normalized)

    @staticmethod
    def _format_key_label(value: str) -> str:
        words = str(value or "").strip().replace("-", " ").replace("_", " ").split()
        if not words:
            return "Unknown"
        return " ".join(word.capitalize() for word in words)

    def _on_radio_volume_value_changed(self, value: int) -> None:
        _ = value
        self._refresh_radio_volume_label()

    def _on_radio_loudness_boost_toggled(self, enabled: bool) -> None:
        self._radio_loudness_boost_factor.setEnabled(bool(enabled))
        self._refresh_radio_volume_label()

    def _on_radio_loudness_boost_factor_changed(self, _value: float) -> None:
        self._refresh_radio_volume_label()

    def set_radio_channel_options(
        self,
        channels: list[str],
        *,
        selected: object,
        enabled: bool,
    ) -> None:
        normalized_selected = RadioController.normalize_channel(selected)
        normalized_channels: list[str] = []
        for raw in channels:
            channel = RadioController.normalize_channel(raw)
            if not channel or channel in normalized_channels:
                continue
            normalized_channels.append(channel)
        normalized_channels.sort()

        self._radio_channel_values = normalized_channels
        self._radio_channel_enabled = bool(enabled)

        with QSignalBlocker(self._radio_channel):
            self._radio_channel.clear()
            self._radio_channel.addItem("All channels", "")
            for channel in normalized_channels:
                self._radio_channel.addItem(channel, channel)
            if normalized_selected and normalized_selected not in normalized_channels:
                self._radio_channel.addItem(
                    f"Custom: {normalized_selected}",
                    normalized_selected,
                )
            self._set_combo_value(self._radio_channel, normalized_selected, fallback="")
        self._radio_channel.setEnabled(self._radio_channel_enabled)

    def _refresh_radio_volume_label(self) -> None:
        raw = max(0, min(100, int(self._radio_volume.value())))
        effective = self._effective_radio_volume_percent(raw)
        self._radio_volume_value.setText(f"{effective}%")

    def _effective_radio_volume_percent(self, value: int) -> int:
        raw = max(0, min(100, int(value)))
        if not self._radio_loudness_boost_enabled.isChecked():
            return raw
        factor = RadioController.normalize_loudness_boost_factor(
            self._radio_loudness_boost_factor.value()
        )
        return max(0, int(round(raw * factor)))

    def set_settings(self, settings: dict[str, Any]) -> None:
        self._suppress_autosave = True
        try:
            self._populate_agent_combo()
            use_value = normalize_agent(str(settings.get("use") or ""))
            self._set_combo_value(
                self._use,
                use_value,
                fallback=str(self._use.itemData(0) or get_default_agent_system_name()),
            )

            shell_value = str(settings.get("shell") or "bash").strip().lower()
            self._set_combo_value(self._shell, shell_value, fallback="bash")
            self._set_combo_value(
                self._opencode_interactive_mode,
                normalize_opencode_interactive_mode(
                    str(settings.get("opencode_interactive_mode") or "terminal")
                ),
                fallback="terminal",
            )
            self._refresh_terminal_options(
                selected_terminal_id=str(
                    settings.get("interactive_terminal_id") or ""
                ).strip()
            )
            enabled = bool(settings.get("preflight_enabled") or False)
            self._preflight_enabled.setChecked(enabled)
            self._preflight_script.setEnabled(enabled)
            self._preflight_script.setPlainText(
                str(settings.get("preflight_script") or "")
            )
            self._refresh_preflight_script_highlighting(
                str(self._preflight_script.toPlainText() or "")
            )
            self._reset_recommended_preflight_selection()

            self._append_pixelarch_context.setChecked(
                bool(settings.get("append_pixelarch_context") or False)
            )
            self._github_workroom_prefer_browser.setChecked(
                bool(settings.get("github_workroom_prefer_browser") or False)
            )
            self._agentsnova_auto_review_enabled.setChecked(
                bool(settings.get("agentsnova_auto_review_enabled", True))
            )
            self._set_combo_value(
                self._agentsnova_auto_marker_comments_mode,
                normalize_default_marker_comment_mode(
                    settings.get(
                        "agentsnova_auto_marker_comments_mode",
                        settings.get("agentsnova_auto_marker_comments_enabled", True),
                    )
                ),
                fallback="keep",
            )
            self._agentsnova_auto_reactions_enabled.setChecked(
                bool(settings.get("agentsnova_auto_reactions_enabled", True))
            )
            self._github_polling_enabled.setChecked(
                bool(settings.get("github_polling_enabled") or False)
            )
            try:
                poll_startup_delay_s = max(
                    0, int(settings.get("github_poll_startup_delay_s", 35))
                )
            except Exception:
                poll_startup_delay_s = 35
            self._github_poll_startup_delay_s.setText(str(poll_startup_delay_s))
            trusted_users_raw = settings.get("agentsnova_trusted_users_global", [])
            trusted_users = (
                trusted_users_raw if isinstance(trusted_users_raw, list) else []
            )
            self._agentsnova_trusted_users_global.set_usernames(trusted_users)
            self._headless_desktop_enabled.setChecked(
                bool(settings.get("headless_desktop_enabled") or False)
            )
            self._gpu_enabled.setChecked(bool(settings.get("gpu_enabled") or False))
            self._auto_navigate_on_run_agent_start.setChecked(
                bool(settings.get("auto_navigate_on_run_agent_start") or False)
            )
            self._auto_navigate_on_run_interactive_start.setChecked(
                bool(settings.get("auto_navigate_on_run_interactive_start") or False)
            )
            confirmation_mode = str(
                settings.get("github_write_confirmation_mode") or "always"
            ).strip()
            self._set_combo_value(
                self._github_write_confirmation_mode,
                confirmation_mode,
                fallback="always",
            )
            self._gh_context_default.setChecked(
                bool(settings.get("gh_context_default_enabled") or False)
            )
            self._spellcheck_enabled.setChecked(
                bool(settings.get("spellcheck_enabled", True))
            )
            self._mount_host_cache.setChecked(
                bool(settings.get("mount_host_cache", False))
            )
            theme_value = normalize_ui_theme_name(
                settings.get("ui_theme"), allow_auto=True
            )
            self._refresh_theme_options(selected=theme_value)
            self._popup_theme_animation_enabled.setChecked(
                bool(settings.get("popup_theme_animation_enabled", True))
            )

            radio_enabled = bool(settings.get("radio_enabled") or False)
            self._radio_enabled.setChecked(radio_enabled)
            self._radio_autostart.setChecked(
                bool(settings.get("radio_autostart") or False)
            )
            self._radio_autostart.setEnabled(radio_enabled)
            radio_channel = RadioController.normalize_channel(
                settings.get("radio_channel")
            )
            self.set_radio_channel_options(
                self._radio_channel_values,
                selected=radio_channel,
                enabled=self._radio_channel_enabled,
            )
            radio_quality = RadioController.normalize_quality(
                settings.get("radio_quality")
            )
            self._set_combo_value(self._radio_quality, radio_quality, fallback="medium")
            radio_volume = RadioController.clamp_volume(settings.get("radio_volume"))
            self._radio_volume.setValue(radio_volume)
            radio_loudness_boost_enabled = bool(
                settings.get("radio_loudness_boost_enabled") or False
            )
            self._radio_loudness_boost_enabled.setChecked(radio_loudness_boost_enabled)
            radio_loudness_boost_factor = (
                RadioController.normalize_loudness_boost_factor(
                    settings.get("radio_loudness_boost_factor")
                )
            )
            self._radio_loudness_boost_factor.setValue(radio_loudness_boost_factor)
            self._radio_loudness_boost_factor.setEnabled(radio_loudness_boost_enabled)
            self._refresh_radio_volume_label()
        finally:
            self._suppress_autosave = False

    def _on_preflight_enabled_toggled(self, enabled: bool) -> None:
        self._preflight_enabled.setText(
            "Preflight Enabled" if bool(enabled) else "Enable Preflight"
        )
        if hasattr(self, "_preflight_script"):
            self._preflight_script.setEnabled(bool(enabled))

    def _on_preflight_script_text_changed(self) -> None:
        self._refresh_preflight_script_highlighting(
            str(self._preflight_script.toPlainText() or "")
        )

    @staticmethod
    def _detect_preflight_script_language(script: str) -> str:
        shebang = str(script or "").split("\n", 1)[0].strip().lower()
        if shebang.startswith("#!"):
            if "fish" in shebang:
                return "fish"
            if "bash" in shebang or "zsh" in shebang or "sh" in shebang:
                return "bash"
        return "bash"

    def _refresh_preflight_script_highlighting(self, script: str) -> None:
        self._preflight_script_highlighter.set_language(
            self._detect_preflight_script_language(script)
        )

    @staticmethod
    def _recommended_preflights_dir() -> Path:
        return (
            Path(__file__).resolve().parents[2]
            / SettingsFormMixin._PREFLIGHT_PRESETS_DIRNAME
        )

    def _load_recommended_preflights(self) -> list[tuple[str, str]]:
        scripts_dir = self._recommended_preflights_dir()
        if not scripts_dir.is_dir():
            return []

        presets: list[tuple[str, str]] = []
        for file_path in scripts_dir.iterdir():
            if not file_path.is_file():
                continue
            if file_path.suffix.lower() not in self._PREFLIGHT_PRESET_SUFFIXES:
                continue
            try:
                content = file_path.read_text(encoding="utf-8")
            except Exception:
                continue
            label = self._format_key_label(file_path.stem)
            presets.append((label, content))
        presets.sort(key=lambda item: item[0].lower())
        return presets

    def _populate_recommended_preflights(self) -> None:
        with QSignalBlocker(self._recommended_preflights):
            self._recommended_preflights.clear()
            self._recommended_preflights.addItem("Recommended preflights...", None)
            for label, content in self._load_recommended_preflights():
                self._recommended_preflights.addItem(label, content)
            self._recommended_preflights.setCurrentIndex(0)

    def _reset_recommended_preflight_selection(self) -> None:
        with QSignalBlocker(self._recommended_preflights):
            self._recommended_preflights.setCurrentIndex(0)

    def _on_recommended_preflight_selected(self, index: int) -> None:
        if index <= 0:
            return

        preset_script = str(self._recommended_preflights.itemData(index) or "")
        if not preset_script.strip():
            self._reset_recommended_preflight_selection()
            return

        current_script = str(self._preflight_script.toPlainText() or "")
        should_replace = True
        if current_script.strip():
            should_replace = (
                QMessageBox.question(
                    None,
                    "Replace preflight script?",
                    "Would you like to replace what you have with the recommended preflight?",
                )
                == QMessageBox.StandardButton.Yes
            )

        if should_replace:
            self._preflight_script.setPlainText(preset_script)
            self._refresh_preflight_script_highlighting(preset_script)
        self._reset_recommended_preflight_selection()

    def get_settings(self) -> dict[str, Any]:
        poll_startup_delay_text = str(
            self._github_poll_startup_delay_s.text() or "35"
        ).strip()
        try:
            poll_startup_delay_s = max(0, int(poll_startup_delay_text or "35"))
        except Exception:
            poll_startup_delay_s = 35
        return {
            "use": str(self._use.currentData() or get_default_agent_system_name()),
            "shell": str(self._shell.currentData() or "bash"),
            "opencode_interactive_mode": normalize_opencode_interactive_mode(
                str(self._opencode_interactive_mode.currentData() or "terminal")
            ),
            "interactive_terminal_id": str(
                self._interactive_terminal.currentData() or ""
            ),
            "ui_theme": normalize_ui_theme_name(
                str(self._ui_theme.currentData() or "auto"), allow_auto=True
            ),
            "popup_theme_animation_enabled": bool(
                self._popup_theme_animation_enabled.isChecked()
            ),
            "preflight_enabled": bool(self._preflight_enabled.isChecked()),
            "preflight_script": str(self._preflight_script.toPlainText() or ""),
            "append_pixelarch_context": bool(
                self._append_pixelarch_context.isChecked()
            ),
            "github_workroom_prefer_browser": bool(
                self._github_workroom_prefer_browser.isChecked()
            ),
            "github_write_confirmation_mode": str(
                self._github_write_confirmation_mode.currentData() or "always"
            ),
            "agentsnova_auto_review_enabled": bool(
                self._agentsnova_auto_review_enabled.isChecked()
            ),
            "agentsnova_auto_marker_comments_mode": (
                normalize_default_marker_comment_mode(
                    self._agentsnova_auto_marker_comments_mode.currentData()
                )
            ),
            "agentsnova_auto_reactions_enabled": bool(
                self._agentsnova_auto_reactions_enabled.isChecked()
            ),
            "github_polling_enabled": bool(self._github_polling_enabled.isChecked()),
            "github_poll_startup_delay_s": poll_startup_delay_s,
            "agentsnova_trusted_users_global": self._agentsnova_trusted_users_global.get_usernames(),
            "headless_desktop_enabled": bool(
                self._headless_desktop_enabled.isChecked()
            ),
            "gpu_enabled": bool(self._gpu_enabled.isChecked()),
            "auto_navigate_on_run_agent_start": bool(
                self._auto_navigate_on_run_agent_start.isChecked()
            ),
            "auto_navigate_on_run_interactive_start": bool(
                self._auto_navigate_on_run_interactive_start.isChecked()
            ),
            "gh_context_default_enabled": bool(self._gh_context_default.isChecked()),
            "spellcheck_enabled": bool(self._spellcheck_enabled.isChecked()),
            "mount_host_cache": bool(self._mount_host_cache.isChecked()),
            "radio_enabled": bool(self._radio_enabled.isChecked()),
            "radio_autostart": bool(self._radio_autostart.isChecked()),
            "radio_channel": RadioController.normalize_channel(
                str(self._radio_channel.currentData() or "")
            ),
            "radio_quality": RadioController.normalize_quality(
                str(self._radio_quality.currentData() or "medium")
            ),
            "radio_volume": RadioController.clamp_volume(self._radio_volume.value()),
            "radio_loudness_boost_enabled": bool(
                self._radio_loudness_boost_enabled.isChecked()
            ),
            "radio_loudness_boost_factor": (
                RadioController.normalize_loudness_boost_factor(
                    self._radio_loudness_boost_factor.value()
                )
            ),
        }

    def _on_setup_global_github_defaults(self) -> None:
        environments = load_environments().values()
        seeded = collect_seed_usernames_for_cloned_environments(environments)
        if not seeded:
            return
        self._agentsnova_trusted_users_global.merge_usernames(seeded)
        try:
            self._queue_debounced_autosave()
        except Exception:
            pass

    def _refresh_terminal_options(self, *, selected_terminal_id: str) -> None:
        selected_id = str(selected_terminal_id or "").strip()
        current_id = str(self._interactive_terminal.currentData() or "").strip()
        options = detect_terminal_options()

        with QSignalBlocker(self._interactive_terminal):
            self._interactive_terminal.clear()
            if not options:
                self._interactive_terminal.addItem("No terminals detected", "")
                self._interactive_terminal.setCurrentIndex(0)
                return

            for option in options:
                self._interactive_terminal.addItem(option.label, option.terminal_id)

            desired = selected_id or current_id
            if not desired:
                desired = str(options[0].terminal_id or "").strip()
            self._set_combo_value(
                self._interactive_terminal,
                desired,
                fallback=str(options[0].terminal_id or "").strip(),
            )

    def _on_refresh_terminal_options_clicked(self) -> None:
        self._refresh_terminal_options(
            selected_terminal_id=str(
                self._interactive_terminal.currentData() or ""
            ).strip()
        )
        self._queue_debounced_autosave()

    @staticmethod
    def _set_combo_value(combo: QComboBox, value: str, fallback: str) -> None:
        idx = combo.findData(value)
        if idx >= 0:
            combo.setCurrentIndex(idx)
            return
        idx = combo.findData(fallback)
        if idx >= 0:
            combo.setCurrentIndex(idx)
