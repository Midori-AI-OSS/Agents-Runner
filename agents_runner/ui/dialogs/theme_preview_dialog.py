from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)

from agents_runner.ui.dialogs.themed_dialog import ThemedDialog


class ThemePreviewDialog(ThemedDialog):
    """Modal dialog that previews and optionally applies a single theme."""

    def __init__(
        self,
        *,
        theme_name: str,
        theme_label: str,
        parent: QWidget | None = None,
    ) -> None:
        self._theme_name = str(theme_name or "").strip().lower()
        self._applied = False
        super().__init__(parent, theme_name=self._theme_name)

        self.setWindowTitle(f"Theme Preview - {theme_label}")
        self.setModal(True)
        self.setMinimumSize(760, 360)
        self.resize(940, 420)

        layout = self.content_layout()
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        title = QLabel(f"{theme_label} Preview")
        title.setObjectName("SettingsPaneTitle")
        layout.addWidget(title)

        subtitle = QLabel("Live background preview. Apply to set this theme.")
        subtitle.setObjectName("SettingsPaneSubtitle")
        layout.addWidget(subtitle)

        details = QLabel(
            "This dialog surface is the live theme preview. "
            "Apply to switch the app background."
        )
        details.setWordWrap(True)
        details.setObjectName("SettingsPaneSubtitle")
        layout.addWidget(details)

        layout.addStretch(1)

        actions = QHBoxLayout()
        actions.setSpacing(10)
        actions.addStretch(1)

        apply_button = QPushButton("Apply")
        apply_button.clicked.connect(self._on_apply_clicked)
        actions.addWidget(apply_button)

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.reject)
        actions.addWidget(close_button)

        layout.addLayout(actions)

    def applied_theme_name(self) -> str | None:
        if not self._applied:
            return None
        return self._theme_name

    def _on_apply_clicked(self) -> None:
        self._applied = True
        self.accept()
