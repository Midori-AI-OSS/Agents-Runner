from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtCore import Signal
from PySide6.QtGui import QFocusEvent
from PySide6.QtWidgets import QCheckBox
from PySide6.QtWidgets import QHBoxLayout
from PySide6.QtWidgets import QLabel
from PySide6.QtWidgets import QMessageBox
from PySide6.QtWidgets import QPlainTextEdit
from PySide6.QtWidgets import QPushButton
from PySide6.QtWidgets import QTabWidget
from PySide6.QtWidgets import QVBoxLayout
from PySide6.QtWidgets import QWidget

from agents_runner.environments import Environment
from agents_runner.environments.model import PromptConfig


class FocusOutPlainTextEdit(QPlainTextEdit):
    """QPlainTextEdit that emits a signal when focus is lost.
    
    Emits focusLost signal when the widget loses focus, allowing consumers
    to delay processing until the user finishes editing.
    """
    focusLost = Signal()

    def focusOutEvent(self, event: QFocusEvent) -> None:
        super().focusOutEvent(event)
        self.focusLost.emit()


class PromptsTabWidget(QWidget):
    prompts_changed = Signal()

    MAX_PROMPTS = 20

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._unlocked = False
        self._prompt_tabs: list[tuple[QWidget, QCheckBox, QPlainTextEdit]] = []
        self._current_visible_count = 0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 16, 0, 12)
        layout.setSpacing(10)

        unlock_row = QHBoxLayout()
        unlock_row.setSpacing(10)
        self._unlock_btn = QPushButton("Unlock Prompts")
        self._unlock_btn.setToolTip("Enable custom prompt injection for this environment")
        self._unlock_btn.clicked.connect(self._on_unlock_clicked)
        unlock_row.addWidget(self._unlock_btn)
        unlock_row.addStretch(1)
        layout.addLayout(unlock_row)

        self._warning_label = QLabel(
            "⚠️  Prompts are locked. Click 'Unlock Prompts' to enable."
        )
        self._warning_label.setStyleSheet("color: rgba(237, 239, 245, 160);")
        layout.addWidget(self._warning_label)

        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)
        self._tabs.setVisible(False)
        layout.addWidget(self._tabs, 1)

        self._init_prompt_tabs()

    def _init_prompt_tabs(self) -> None:
        for i in range(self.MAX_PROMPTS):
            tab = QWidget()
            tab_layout = QVBoxLayout(tab)
            tab_layout.setContentsMargins(0, 10, 0, 0)
            tab_layout.setSpacing(10)

            enabled_cb = QCheckBox(f"Enable Prompt {i + 1}")
            enabled_cb.toggled.connect(self._on_prompt_changed)

            text_edit = FocusOutPlainTextEdit()
            text_edit.setPlaceholderText(
                f"Enter custom prompt text for prompt #{i + 1}...\n\n"
                "This will be appended to the agent's system prompt before starting (non-interactive only)."
            )
            text_edit.setTabChangesFocus(True)
            text_edit.focusLost.connect(self._on_prompt_text_focus_lost)

            tab_layout.addWidget(enabled_cb)
            tab_layout.addWidget(text_edit, 1)

            self._prompt_tabs.append((tab, enabled_cb, text_edit))

    def _on_unlock_clicked(self) -> None:
        if self._unlocked:
            return

        result = QMessageBox.warning(
            self,
            "Warning: Unlock Prompts",
            "Using bad prompts lowers the agent's skill level and will end up with wasted time and effort.\n\n"
            "Only edit if you really know what you're doing.\n\n"
            "Do you want to proceed?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if result == QMessageBox.Yes:
            self._unlocked = True
            self._unlock_btn.setEnabled(False)
            self._unlock_btn.setText("Prompts Unlocked")
            self._warning_label.setText("✓ Prompts are unlocked. Configure up to 20 custom prompts below.")
            self._warning_label.setStyleSheet("color: rgba(80, 250, 123, 200);")
            self._tabs.setVisible(True)
            self._sync_visible_tabs()
            self.prompts_changed.emit()

    def _calculate_visible_count(self) -> int:
        """Calculate how many tabs should be visible based on prompt content."""
        last_nonempty_index = -1
        for i, (tab, enabled_cb, text_edit) in enumerate(self._prompt_tabs):
            if text_edit.toPlainText().strip():
                last_nonempty_index = i
        return min(last_nonempty_index + 2, self.MAX_PROMPTS)

    def _on_prompt_text_focus_lost(self) -> None:
        """Handle when prompt text loses focus."""
        if self._unlocked:
            # Only sync tabs if the visible count changed
            new_visible_count = self._calculate_visible_count()
            if new_visible_count != self._current_visible_count:
                self._sync_visible_tabs()

            self.prompts_changed.emit()

    def _on_prompt_changed(self) -> None:
        """Handle when checkbox state changes."""
        if self._unlocked:
            self.prompts_changed.emit()

    def _sync_visible_tabs(self) -> None:
        if not self._unlocked:
            return

        self._tabs.clear()

        visible_count = self._calculate_visible_count()
        self._current_visible_count = visible_count

        for i in range(visible_count):
            tab, enabled_cb, text_edit = self._prompt_tabs[i]
            self._tabs.addTab(tab, f"Prompt {i + 1}")

    def set_prompts(self, prompts: list[PromptConfig], unlocked: bool) -> None:
        self._unlocked = unlocked

        if unlocked:
            self._unlock_btn.setEnabled(False)
            self._unlock_btn.setText("Prompts Unlocked")
            self._warning_label.setText("✓ Prompts are unlocked. Configure up to 20 custom prompts below.")
            self._warning_label.setStyleSheet("color: rgba(80, 250, 123, 200);")
            self._tabs.setVisible(True)
        else:
            self._unlock_btn.setEnabled(True)
            self._unlock_btn.setText("Unlock Prompts")
            self._warning_label.setText("⚠️  Prompts are locked. Click 'Unlock Prompts' to enable.")
            self._warning_label.setStyleSheet("color: rgba(237, 239, 245, 160);")
            self._tabs.setVisible(False)

        for i, (tab, enabled_cb, text_edit) in enumerate(self._prompt_tabs):
            if i < len(prompts):
                p = prompts[i]
                enabled_cb.blockSignals(True)
                text_edit.blockSignals(True)
                enabled_cb.setChecked(p.enabled)
                text_edit.setPlainText(p.text)
                enabled_cb.blockSignals(False)
                text_edit.blockSignals(False)
            else:
                enabled_cb.blockSignals(True)
                text_edit.blockSignals(True)
                enabled_cb.setChecked(False)
                text_edit.setPlainText("")
                enabled_cb.blockSignals(False)
                text_edit.blockSignals(False)

        self._sync_visible_tabs()

    def get_prompts(self) -> tuple[list[PromptConfig], bool]:
        prompts = []
        for tab, enabled_cb, text_edit in self._prompt_tabs:
            text = text_edit.toPlainText().strip()
            if text:
                prompts.append(PromptConfig(
                    enabled=enabled_cb.isChecked(),
                    text=text
                ))
        return prompts, self._unlocked
