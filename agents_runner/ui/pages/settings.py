from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QCheckBox
from PySide6.QtWidgets import QComboBox
from PySide6.QtWidgets import QFileDialog
from PySide6.QtWidgets import QGridLayout
from PySide6.QtWidgets import QHBoxLayout
from PySide6.QtWidgets import QLabel
from PySide6.QtWidgets import QLineEdit
from PySide6.QtWidgets import QPlainTextEdit
from PySide6.QtWidgets import QPushButton
from PySide6.QtWidgets import QToolButton
from PySide6.QtWidgets import QVBoxLayout
from PySide6.QtWidgets import QWidget

from agents_runner.agent_cli import normalize_agent
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
)


class SettingsPage(QWidget):
    back_requested = Signal()
    saved = Signal(dict)
    test_preflight_requested = Signal(dict)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(*MAIN_LAYOUT_MARGINS)
        layout.setSpacing(MAIN_LAYOUT_SPACING)

        header = GlassCard()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(*HEADER_MARGINS)
        header_layout.setSpacing(HEADER_SPACING)

        title = QLabel("Settings")
        title.setStyleSheet("font-size: 18px; font-weight: 750;")
        title.setToolTip(
            "Settings are saved locally in:\n~/.midoriai/agents-runner/state.json"
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

        grid = QGridLayout()
        grid.setHorizontalSpacing(GRID_HORIZONTAL_SPACING)
        grid.setVerticalSpacing(GRID_VERTICAL_SPACING)
        grid.setColumnStretch(1, 1)

        self._use = QComboBox()
        self._use.addItem("OpenAI Codex", "codex")
        self._use.addItem("Claude Code", "claude")
        self._use.addItem("Github Copilot", "copilot")
        self._use.addItem("Google Gemini", "gemini")

        self._shell = QComboBox()
        for label, value in [
            ("bash", "bash"),
            ("sh", "sh"),
            ("zsh", "zsh"),
            ("fish", "fish"),
            ("tmux", "tmux"),
        ]:
            self._shell.addItem(label, value)

        self._host_codex_dir = QLineEdit()
        self._host_codex_dir.setPlaceholderText(os.path.expanduser("~/.codex"))
        browse_codex = QPushButton("Browse…")
        browse_codex.setFixedWidth(STANDARD_BUTTON_WIDTH)
        browse_codex.clicked.connect(self._pick_codex_dir)

        self._host_claude_dir = QLineEdit()
        self._host_claude_dir.setPlaceholderText(os.path.expanduser("~/.claude"))
        browse_claude = QPushButton("Browse…")
        browse_claude.setFixedWidth(STANDARD_BUTTON_WIDTH)
        browse_claude.clicked.connect(self._pick_claude_dir)

        self._host_copilot_dir = QLineEdit()
        self._host_copilot_dir.setPlaceholderText(os.path.expanduser("~/.copilot"))
        browse_copilot = QPushButton("Browse…")
        browse_copilot.setFixedWidth(STANDARD_BUTTON_WIDTH)
        browse_copilot.clicked.connect(self._pick_copilot_dir)

        self._host_gemini_dir = QLineEdit()
        self._host_gemini_dir.setPlaceholderText(os.path.expanduser("~/.gemini"))
        browse_gemini = QPushButton("Browse…")
        browse_gemini.setFixedWidth(STANDARD_BUTTON_WIDTH)
        browse_gemini.clicked.connect(self._pick_gemini_dir)

        self._preflight_enabled = QCheckBox(
            "Enable settings preflight bash"
        )
        self._preflight_enabled.setToolTip(
            "Runs on all environments before environment-specific preflight.\n"
            "Useful for global setup tasks like installing system packages."
        )
        self._append_pixelarch_context = QCheckBox("Append PixelArch context")
        self._append_pixelarch_context.setToolTip(
            "When enabled, appends a short note to the end of the prompt passed to Run Agent.\n"
            "This never affects Run Interactive."
        )
        self._headless_desktop_enabled = QCheckBox(
            "Force headless desktop (noVNC) for all environments"
        )
        self._headless_desktop_enabled.setToolTip(
            "When enabled, this overrides the per-environment headless desktop setting."
        )
        
        self._gh_context_default = QCheckBox(
            "Enable GitHub context by default for new environments"
        )
        self._gh_context_default.setToolTip(
            "When enabled, new environments will have GitHub context enabled by default.\n"
            "This only affects newly created environments, not existing ones.\n"
            "Users can still disable it per-environment in the Environments editor."
        )
        
        self._spellcheck_enabled = QCheckBox(
            "Enable spellcheck in prompt editor"
        )
        self._spellcheck_enabled.setToolTip(
            "When enabled, misspelled words in the prompt editor will be underlined in red.\n"
            "Right-click on a misspelled word to see suggestions or add it to your dictionary."
        )
        
        self._preflight_script = QPlainTextEdit()
        self._preflight_script.setPlaceholderText(
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            "\n"
            "# Runs inside the container before the agent command.\n"
            "# Runs on every environment, before environment preflight (if enabled).\n"
            "# This script is mounted read-only and deleted from the host after the task finishes.\n"
        )
        self._preflight_script.setTabChangesFocus(True)
        self._preflight_enabled.toggled.connect(self._preflight_script.setEnabled)
        self._preflight_script.setEnabled(False)

        grid.addWidget(QLabel("Agent CLI"), 0, 0)
        grid.addWidget(self._use, 0, 1)
        grid.addWidget(QLabel("Shell"), 0, 2)
        grid.addWidget(self._shell, 0, 3)
        codex_label = QLabel("Codex Config folder")
        claude_label = QLabel("Claude Config folder")
        copilot_label = QLabel("Copilot Config folder")
        gemini_label = QLabel("Gemini Config folder")

        grid.addWidget(codex_label, 1, 0)
        grid.addWidget(self._host_codex_dir, 1, 1, 1, 2)
        grid.addWidget(browse_codex, 1, 3)
        grid.addWidget(claude_label, 2, 0)
        grid.addWidget(self._host_claude_dir, 2, 1, 1, 2)
        grid.addWidget(browse_claude, 2, 3)
        grid.addWidget(copilot_label, 3, 0)
        grid.addWidget(self._host_copilot_dir, 3, 1, 1, 2)
        grid.addWidget(browse_copilot, 3, 3)
        grid.addWidget(gemini_label, 4, 0)
        grid.addWidget(self._host_gemini_dir, 4, 1, 1, 2)
        grid.addWidget(browse_gemini, 4, 3)
        grid.addWidget(self._preflight_enabled, 5, 0, 1, 4)
        grid.addWidget(self._append_pixelarch_context, 6, 0, 1, 4)
        grid.addWidget(self._headless_desktop_enabled, 7, 0, 1, 4)
        grid.addWidget(self._gh_context_default, 8, 0, 1, 4)
        grid.addWidget(self._spellcheck_enabled, 9, 0, 1, 4)

        self._agent_config_widgets: dict[str, tuple[QWidget, ...]] = {
            "codex": (codex_label, self._host_codex_dir, browse_codex),
            "claude": (claude_label, self._host_claude_dir, browse_claude),
            "copilot": (copilot_label, self._host_copilot_dir, browse_copilot),
            "gemini": (gemini_label, self._host_gemini_dir, browse_gemini),
        }
        self._use.currentIndexChanged.connect(self._sync_agent_config_widgets)
        self._sync_agent_config_widgets()

        buttons = QHBoxLayout()
        buttons.setSpacing(BUTTON_ROW_SPACING)
        save = QToolButton()
        save.setText("Save")
        save.setToolButtonStyle(Qt.ToolButtonTextOnly)
        save.clicked.connect(self._on_save)
        test = QToolButton()
        test.setText("Test preflights (all envs)")
        test.setToolButtonStyle(Qt.ToolButtonTextOnly)
        test.clicked.connect(self._on_test_preflight)
        buttons.addWidget(test)
        buttons.addWidget(save)
        buttons.addStretch(1)

        card_layout.addLayout(grid)
        card_layout.addWidget(QLabel("Preflight script"))
        card_layout.addWidget(self._preflight_script, 1)
        card_layout.addLayout(buttons)
        layout.addWidget(card, 1)

    def set_settings(self, settings: dict) -> None:
        use_value = normalize_agent(str(settings.get("use") or "codex"))
        self._set_combo_value(self._use, use_value, fallback="codex")
        self._sync_agent_config_widgets()

        shell_value = str(settings.get("shell") or "bash").strip().lower()
        self._set_combo_value(self._shell, shell_value, fallback="bash")

        host_codex_dir = os.path.expanduser(
            str(settings.get("host_codex_dir") or "").strip()
        )
        if not host_codex_dir:
            host_codex_dir = os.path.expanduser("~/.codex")
        self._host_codex_dir.setText(host_codex_dir)

        host_claude_dir = os.path.expanduser(
            str(settings.get("host_claude_dir") or "").strip()
        )
        self._host_claude_dir.setText(host_claude_dir)

        host_copilot_dir = os.path.expanduser(
            str(settings.get("host_copilot_dir") or "").strip()
        )
        self._host_copilot_dir.setText(host_copilot_dir)

        host_gemini_dir = os.path.expanduser(
            str(settings.get("host_gemini_dir") or "").strip()
        )
        self._host_gemini_dir.setText(host_gemini_dir)

        enabled = bool(settings.get("preflight_enabled") or False)
        self._preflight_enabled.setChecked(enabled)
        self._preflight_script.setEnabled(enabled)
        self._preflight_script.setPlainText(str(settings.get("preflight_script") or ""))

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

    def get_settings(self) -> dict:
        return {
            "use": str(self._use.currentData() or "codex"),
            "shell": str(self._shell.currentData() or "bash"),
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
            "gh_context_default_enabled": bool(
                self._gh_context_default.isChecked()
            ),
            "spellcheck_enabled": bool(
                self._spellcheck_enabled.isChecked()
            ),
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

    def _on_save(self) -> None:
        self.try_autosave()

    def try_autosave(self) -> bool:
        self.saved.emit(self.get_settings())
        return True

    def _on_test_preflight(self) -> None:
        self.test_preflight_requested.emit(self.get_settings())

    def _sync_agent_config_widgets(self) -> None:
        use_value = normalize_agent(str(self._use.currentData() or "codex"))
        for agent, widgets in self._agent_config_widgets.items():
            visible = agent == use_value
            for widget in widgets:
                widget.setVisible(visible)

    @staticmethod
    def _set_combo_value(combo: QComboBox, value: str, fallback: str) -> None:
        idx = combo.findData(value)
        if idx >= 0:
            combo.setCurrentIndex(idx)
            return
        idx = combo.findData(fallback)
        if idx >= 0:
            combo.setCurrentIndex(idx)
