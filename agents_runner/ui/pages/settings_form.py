from __future__ import annotations

import os
from dataclasses import dataclass

from PySide6.QtCore import QSignalBlocker, Qt
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

from agents_runner.agent_cli import normalize_agent
from agents_runner.agent_systems import available_agent_system_names
from agents_runner.agent_systems import get_agent_system
from agents_runner.agent_systems import get_default_agent_system_name
from agents_runner.ui.graphics import available_ui_theme_names
from agents_runner.ui.graphics import normalize_ui_theme_name
from agents_runner.ui.constants import (
    GRID_HORIZONTAL_SPACING,
    GRID_VERTICAL_SPACING,
    BUTTON_ROW_SPACING,
    STANDARD_BUTTON_WIDTH,
)


@dataclass(frozen=True)
class _SettingsPaneSpec:
    key: str
    title: str
    subtitle: str
    section: str


class _SettingsFormMixin:
    def _default_pane_specs(self) -> list[_SettingsPaneSpec]:
        return [
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
                key="config_paths",
                title="Config Paths",
                subtitle="Host config folders used by each agent.",
                section="Agent Setup",
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
                subtitle="Global setup script executed before environment scripts.",
                section="Runtime",
            ),
        ]

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

        self._ui_theme = QComboBox()
        self._ui_theme.setToolTip(
            "Auto syncs background theme to the active agent.\n"
            "Select a specific theme to force an override."
        )
        self._refresh_theme_options(selected="auto")

        self._host_codex_dir = QLineEdit()
        self._host_codex_dir.setPlaceholderText(os.path.expanduser("~/.codex"))
        self._host_claude_dir = QLineEdit()
        self._host_claude_dir.setPlaceholderText(os.path.expanduser("~/.claude"))
        self._host_copilot_dir = QLineEdit()
        self._host_copilot_dir.setPlaceholderText(os.path.expanduser("~/.copilot"))
        self._host_gemini_dir = QLineEdit()
        self._host_gemini_dir.setPlaceholderText(os.path.expanduser("~/.gemini"))

        self._browse_codex = QPushButton("Browse…")
        self._browse_codex.setFixedWidth(STANDARD_BUTTON_WIDTH)
        self._browse_codex.clicked.connect(self._pick_codex_dir)

        self._browse_claude = QPushButton("Browse…")
        self._browse_claude.setFixedWidth(STANDARD_BUTTON_WIDTH)
        self._browse_claude.clicked.connect(self._pick_claude_dir)

        self._browse_copilot = QPushButton("Browse…")
        self._browse_copilot.setFixedWidth(STANDARD_BUTTON_WIDTH)
        self._browse_copilot.clicked.connect(self._pick_copilot_dir)

        self._browse_gemini = QPushButton("Browse…")
        self._browse_gemini.setFixedWidth(STANDARD_BUTTON_WIDTH)
        self._browse_gemini.clicked.connect(self._pick_gemini_dir)

        self._preflight_enabled = QCheckBox("Enable settings preflight")
        self._preflight_enabled.setToolTip(
            "Runs on all environments before environment-specific preflight.\n"
            "Useful for global setup tasks like installing system packages."
        )

        self._append_pixelarch_context = QCheckBox("Append PixelArch context")
        self._append_pixelarch_context.setToolTip(
            "When enabled, appends a short note to prompts passed to Run Agent.\n"
            "This does not affect Run Interactive."
        )

        self._headless_desktop_enabled = QCheckBox(
            "Force headless desktop for all environments"
        )
        self._headless_desktop_enabled.setToolTip(
            "When enabled, this overrides per-environment headless desktop settings."
        )

        self._gh_context_default = QCheckBox(
            "Enable GitHub context by default for new environments"
        )
        self._gh_context_default.setToolTip(
            "Only affects newly created environments. Existing environments keep their settings."
        )

        self._spellcheck_enabled = QCheckBox("Enable spellcheck in prompt editor")
        self._spellcheck_enabled.setToolTip(
            "Underlines misspelled words in the prompt editor and provides suggestions."
        )

        self._mount_host_cache = QCheckBox("Mount host cache into containers")
        self._mount_host_cache.setToolTip(
            "Mounts ~/.cache to speed up package manager installs across environments."
        )

        self._preflight_script = QPlainTextEdit()
        self._preflight_script.setPlaceholderText(
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            "\n"
            "# Runs inside the container before the agent command.\n"
            "# Runs on every environment, before environment preflight (if enabled).\n"
            "# This script is mounted read-only and deleted from the host after task finish.\n"
        )
        self._preflight_script.setTabChangesFocus(True)
        self._preflight_script.setEnabled(False)
        self._preflight_enabled.toggled.connect(self._preflight_script.setEnabled)

        self._test_preflights = QToolButton()
        self._test_preflights.setText("Test preflights (all envs)")
        self._test_preflights.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self._test_preflights.clicked.connect(self._on_test_preflight)

    def _build_pages(self) -> None:
        specs_by_key = {spec.key: spec for spec in self._pane_specs}

        general_page, general_body = self._create_page(
            specs_by_key["general_preferences"]
        )
        general_body.addWidget(self._spellcheck_enabled)
        general_body.addWidget(self._gh_context_default)
        general_body.addWidget(self._append_pixelarch_context)
        general_body.addStretch(1)
        self._register_page("general_preferences", general_page)

        themes_page, themes_body = self._create_page(specs_by_key["themes"])
        themes_grid = QGridLayout()
        themes_grid.setHorizontalSpacing(GRID_HORIZONTAL_SPACING)
        themes_grid.setVerticalSpacing(GRID_VERTICAL_SPACING)
        themes_grid.setColumnStretch(1, 1)
        themes_grid.addWidget(QLabel("Theme"), 0, 0)
        themes_grid.addWidget(self._ui_theme, 0, 1)
        themes_body.addLayout(themes_grid)
        themes_body.addStretch(1)
        self._register_page("themes", themes_page)

        agent_page, agent_body = self._create_page(specs_by_key["agent_defaults"])
        agent_grid = QGridLayout()
        agent_grid.setHorizontalSpacing(GRID_HORIZONTAL_SPACING)
        agent_grid.setVerticalSpacing(GRID_VERTICAL_SPACING)
        agent_grid.setColumnStretch(1, 1)
        agent_grid.addWidget(QLabel("Agent CLI"), 0, 0)
        agent_grid.addWidget(self._use, 0, 1)
        agent_grid.addWidget(QLabel("Shell"), 1, 0)
        agent_grid.addWidget(self._shell, 1, 1)
        agent_body.addLayout(agent_grid)
        agent_body.addStretch(1)
        self._register_page("agent_defaults", agent_page)

        paths_page, paths_body = self._create_page(specs_by_key["config_paths"])
        paths_grid = QGridLayout()
        paths_grid.setHorizontalSpacing(GRID_HORIZONTAL_SPACING)
        paths_grid.setVerticalSpacing(GRID_VERTICAL_SPACING)
        paths_grid.setColumnStretch(1, 1)
        paths_grid.addWidget(QLabel("Codex Config folder"), 0, 0)
        paths_grid.addWidget(self._host_codex_dir, 0, 1)
        paths_grid.addWidget(self._browse_codex, 0, 2)
        paths_grid.addWidget(QLabel("Claude Config folder"), 1, 0)
        paths_grid.addWidget(self._host_claude_dir, 1, 1)
        paths_grid.addWidget(self._browse_claude, 1, 2)
        paths_grid.addWidget(QLabel("Copilot Config folder"), 2, 0)
        paths_grid.addWidget(self._host_copilot_dir, 2, 1)
        paths_grid.addWidget(self._browse_copilot, 2, 2)
        paths_grid.addWidget(QLabel("Gemini Config folder"), 3, 0)
        paths_grid.addWidget(self._host_gemini_dir, 3, 1)
        paths_grid.addWidget(self._browse_gemini, 3, 2)
        paths_body.addLayout(paths_grid)
        paths_body.addStretch(1)
        self._register_page("config_paths", paths_page)

        runtime_page, runtime_body = self._create_page(specs_by_key["runtime_behavior"])
        runtime_body.addWidget(self._headless_desktop_enabled)
        runtime_body.addWidget(self._mount_host_cache)
        runtime_body.addStretch(1)
        self._register_page("runtime_behavior", runtime_page)

        preflight_page, preflight_body = self._create_page(
            specs_by_key["preflight_script"]
        )
        preflight_body.addWidget(self._preflight_enabled)
        preflight_body.addWidget(QLabel("Preflight script"))
        preflight_body.addWidget(self._preflight_script, 1)
        preflight_actions = QHBoxLayout()
        preflight_actions.setSpacing(BUTTON_ROW_SPACING)
        preflight_actions.addWidget(self._test_preflights)
        preflight_actions.addStretch(1)
        autosave_hint = QLabel("Changes save automatically.")
        autosave_hint.setObjectName("SettingsPaneSubtitle")
        preflight_actions.addWidget(autosave_hint)
        preflight_body.addLayout(preflight_actions)
        self._register_page("preflight_script", preflight_page)

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
                button.setText(spec.title)
                button.setToolTip(spec.subtitle)
                button.setCheckable(True)
                button.setAutoExclusive(True)
                button.setToolButtonStyle(Qt.ToolButtonTextOnly)
                button.setFixedHeight(40)
                button.setSizePolicy(
                    QSizePolicy.Policy.Fixed,
                    QSizePolicy.Policy.Fixed,
                )
                button.clicked.connect(
                    lambda checked=False, key=spec.key: self._on_nav_button_clicked(key)
                )
                nav_layout.addWidget(button)
                self._nav_buttons[spec.key] = button
                self._compact_nav.addItem(spec.title, spec.key)

        nav_layout.addStretch(1)

    def _create_page(self, spec: _SettingsPaneSpec) -> tuple[QWidget, QVBoxLayout]:
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

    def _populate_agent_combo(self) -> None:
        selected = str(self._use.currentData() or "") if hasattr(self, "_use") else ""

        with QSignalBlocker(self._use):
            self._use.clear()
            for agent_name in available_agent_system_names():
                label = self._format_key_label(agent_name)
                try:
                    plugin = get_agent_system(agent_name)
                    display_name = str(
                        getattr(plugin, "display_name", "") or ""
                    ).strip()
                    if display_name:
                        label = display_name
                except Exception:
                    pass
                self._use.addItem(label, agent_name)

            if self._use.count() == 0:
                default_name = get_default_agent_system_name()
                self._use.addItem(self._format_key_label(default_name), default_name)

        preferred = normalize_agent(selected or str(self._use.itemData(0) or ""))
        self._set_combo_value(self._use, preferred, fallback=preferred)

    def _refresh_theme_options(self, selected: str | None) -> None:
        normalized_selected = normalize_ui_theme_name(selected, allow_auto=True)

        with QSignalBlocker(self._ui_theme):
            self._ui_theme.clear()
            self._ui_theme.addItem("Auto (sync to active agent)", "auto")
            for theme_name in available_ui_theme_names():
                self._ui_theme.addItem(self._format_key_label(theme_name), theme_name)
            self._set_combo_value(self._ui_theme, normalized_selected, fallback="auto")

    @staticmethod
    def _format_key_label(value: str) -> str:
        words = str(value or "").strip().replace("-", " ").replace("_", " ").split()
        if not words:
            return "Unknown"
        return " ".join(word.capitalize() for word in words)

    def set_settings(self, settings: dict) -> None:
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

            self._host_codex_dir.setText(
                os.path.expanduser(
                    str(
                        settings.get("host_codex_dir") or os.path.expanduser("~/.codex")
                    )
                )
            )
            self._host_claude_dir.setText(
                os.path.expanduser(
                    str(
                        settings.get("host_claude_dir")
                        or os.path.expanduser("~/.claude")
                    )
                )
            )
            self._host_copilot_dir.setText(
                os.path.expanduser(
                    str(
                        settings.get("host_copilot_dir")
                        or os.path.expanduser("~/.copilot")
                    )
                )
            )
            self._host_gemini_dir.setText(
                os.path.expanduser(
                    str(
                        settings.get("host_gemini_dir")
                        or os.path.expanduser("~/.gemini")
                    )
                )
            )

            enabled = bool(settings.get("preflight_enabled") or False)
            self._preflight_enabled.setChecked(enabled)
            self._preflight_script.setEnabled(enabled)
            self._preflight_script.setPlainText(
                str(settings.get("preflight_script") or "")
            )

            self._append_pixelarch_context.setChecked(
                bool(settings.get("append_pixelarch_context") or False)
            )
            self._headless_desktop_enabled.setChecked(
                bool(settings.get("headless_desktop_enabled") or False)
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
        finally:
            self._suppress_autosave = False

    def get_settings(self) -> dict:
        return {
            "use": str(self._use.currentData() or get_default_agent_system_name()),
            "shell": str(self._shell.currentData() or "bash"),
            "ui_theme": normalize_ui_theme_name(
                str(self._ui_theme.currentData() or "auto"), allow_auto=True
            ),
            "host_codex_dir": os.path.expanduser(
                str(self._host_codex_dir.text() or "").strip()
            ),
            "host_claude_dir": os.path.expanduser(
                str(self._host_claude_dir.text() or "").strip()
            ),
            "host_copilot_dir": os.path.expanduser(
                str(self._host_copilot_dir.text() or "").strip()
            ),
            "host_gemini_dir": os.path.expanduser(
                str(self._host_gemini_dir.text() or "").strip()
            ),
            "preflight_enabled": bool(self._preflight_enabled.isChecked()),
            "preflight_script": str(self._preflight_script.toPlainText() or ""),
            "append_pixelarch_context": bool(
                self._append_pixelarch_context.isChecked()
            ),
            "headless_desktop_enabled": bool(
                self._headless_desktop_enabled.isChecked()
            ),
            "gh_context_default_enabled": bool(self._gh_context_default.isChecked()),
            "spellcheck_enabled": bool(self._spellcheck_enabled.isChecked()),
            "mount_host_cache": bool(self._mount_host_cache.isChecked()),
        }

    def _pick_codex_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self,
            "Select Host Config folder",
            self._host_codex_dir.text() or os.path.expanduser("~/.codex"),
        )
        if path:
            self._host_codex_dir.setText(path)

    def _pick_claude_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self,
            "Select Host Claude Config folder",
            self._host_claude_dir.text() or os.path.expanduser("~/.claude"),
        )
        if path:
            self._host_claude_dir.setText(path)

    def _pick_copilot_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self,
            "Select Host Copilot Config folder",
            self._host_copilot_dir.text() or os.path.expanduser("~/.copilot"),
        )
        if path:
            self._host_copilot_dir.setText(path)

    def _pick_gemini_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self,
            "Select Host Gemini Config folder",
            self._host_gemini_dir.text() or os.path.expanduser("~/.gemini"),
        )
        if path:
            self._host_gemini_dir.setText(path)

    @staticmethod
    def _set_combo_value(combo: QComboBox, value: str, fallback: str) -> None:
        idx = combo.findData(value)
        if idx >= 0:
            combo.setCurrentIndex(idx)
            return
        idx = combo.findData(fallback)
        if idx >= 0:
            combo.setCurrentIndex(idx)
