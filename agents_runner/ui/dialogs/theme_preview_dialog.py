from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from agents_runner.ui.widgets.theme_preview import ThemePreviewWidget


class ThemePreviewDialog(QDialog):
    """Modal dialog that previews and optionally applies a single theme."""

    def __init__(
        self,
        *,
        theme_name: str,
        theme_label: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._theme_name = str(theme_name or "").strip().lower()
        self._applied = False

        self.setWindowTitle(f"Theme Preview - {theme_label}")
        self.setModal(True)
        self.setMinimumSize(760, 460)
        self.resize(940, 560)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        title = QLabel(f"{theme_label} Preview")
        title.setObjectName("SettingsPaneTitle")
        layout.addWidget(title)

        subtitle = QLabel("Live background preview. Apply to set this theme.")
        subtitle.setObjectName("SettingsPaneSubtitle")
        layout.addWidget(subtitle)

        preview_frame = QWidget(self)
        preview_frame.setObjectName("ThemePreviewDialogFrame")
        preview_layout = QVBoxLayout(preview_frame)
        preview_layout.setContentsMargins(8, 8, 8, 8)
        preview_layout.setSpacing(0)

        self._preview = ThemePreviewWidget(self._theme_name, preview_frame)
        self._preview.setObjectName("ThemePreviewDialogCanvas")
        self._preview.setMinimumHeight(380)
        preview_layout.addWidget(self._preview, 1)

        layout.addWidget(preview_frame, 1)

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
