from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout
from PySide6.QtWidgets import QLabel
from PySide6.QtWidgets import QPushButton
from PySide6.QtWidgets import QVBoxLayout
from PySide6.QtWidgets import QWidget

from agents_runner.ui.dialogs.themed_dialog import ThemedDialog
from agents_runner.ui.widgets import GlassCard


PORT_CONFLICT_CANCEL = "cancel"
PORT_CONFLICT_USE_RANDOM = "use_random"


class PortConflictDialog(ThemedDialog):
    """Themed dialog for launch-time host port conflicts."""

    def __init__(self, parent: QWidget | None, *, preview_lines: list[str]) -> None:
        super().__init__(parent)
        self._result = PORT_CONFLICT_CANCEL

        self.setWindowTitle("Host Port Conflict")
        self.setModal(True)
        self.setMinimumWidth(760)
        self.setMinimumHeight(420)

        layout = self.content_layout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        title = QLabel("One or more configured host ports are already in use.")
        title.setWordWrap(True)
        title.setStyleSheet(
            "font-size: 15px; font-weight: 700; color: rgba(237, 239, 245, 255);"
        )
        layout.addWidget(title)

        subtitle = QLabel(
            "You can cancel launch, or continue with runtime-only remaps to random free host ports."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("font-size: 12px; color: rgba(237, 239, 245, 200);")
        layout.addWidget(subtitle)

        preview_card = GlassCard()
        preview_layout = QVBoxLayout(preview_card)
        preview_layout.setContentsMargins(14, 14, 14, 14)
        preview_layout.setSpacing(8)

        preview_title = QLabel("Remap preview (this run only):")
        preview_title.setStyleSheet(
            "font-size: 12px; font-weight: 600; color: rgba(237, 239, 245, 255);"
        )
        preview_layout.addWidget(preview_title)

        preview_text = "\n".join(
            f"{line}" for line in (preview_lines or []) if str(line or "").strip()
        )
        if not preview_text:
            preview_text = "(No preview available)"
        preview = QLabel(preview_text)
        preview.setWordWrap(True)
        preview.setStyleSheet(
            "font-family: monospace; font-size: 12px; color: rgba(237, 239, 245, 210);"
        )
        preview_layout.addWidget(preview)

        layout.addWidget(preview_card, 1)
        layout.addStretch(1)

        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        buttons.addStretch(1)

        cancel_button = QPushButton("Cancel launch")
        cancel_button.setMinimumWidth(150)
        cancel_button.clicked.connect(self._on_cancel)
        buttons.addWidget(cancel_button)

        use_random_button = QPushButton("Use random free host ports")
        use_random_button.setMinimumWidth(240)
        use_random_button.setDefault(True)
        use_random_button.setAutoDefault(True)
        use_random_button.clicked.connect(self._on_use_random)
        buttons.addWidget(use_random_button)
        use_random_button.setFocus()

        layout.addLayout(buttons)

    def choice(self) -> str:
        return self._result

    def _on_cancel(self) -> None:
        self._result = PORT_CONFLICT_CANCEL
        self.reject()

    def _on_use_random(self) -> None:
        self._result = PORT_CONFLICT_USE_RANDOM
        self.accept()
