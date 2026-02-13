from __future__ import annotations

from collections.abc import Mapping

from PySide6.QtWidgets import QDialog
from PySide6.QtWidgets import QVBoxLayout
from PySide6.QtWidgets import QWidget

from agents_runner.persistence import default_state_path
from agents_runner.persistence import load_state
from agents_runner.ui.graphics import GlassRoot
from agents_runner.ui.graphics import resolve_effective_ui_theme_name


def _as_settings_dict(value: object) -> dict[str, object] | None:
    if not isinstance(value, Mapping):
        return None
    return {str(key): item for key, item in value.items()}


def _load_persisted_settings() -> dict[str, object]:
    try:
        payload = load_state(default_state_path())
    except Exception:
        return {}
    settings = payload.get("settings") if isinstance(payload, dict) else None
    parsed = _as_settings_dict(settings)
    return parsed or {}


def _find_parent_settings(parent: QWidget | None) -> dict[str, object] | None:
    if parent is None:
        return None

    visited: set[int] = set()
    cursor: QWidget | None = parent
    while cursor is not None and id(cursor) not in visited:
        visited.add(id(cursor))
        parsed = _as_settings_dict(getattr(cursor, "_settings_data", None))
        if parsed is not None:
            return parsed
        cursor = cursor.parentWidget()

    window = parent.window()
    if window is not None and id(window) not in visited:
        parsed = _as_settings_dict(getattr(window, "_settings_data", None))
        if parsed is not None:
            return parsed

    return None


class ThemedDialog(QDialog):
    """Dialog wrapper that renders the active UI theme behind its content."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        theme_name: str | None = None,
        settings_data: Mapping[str, object] | None = None,
    ) -> None:
        super().__init__(parent)

        settings = _as_settings_dict(settings_data)
        if settings is None:
            settings = _find_parent_settings(parent)
        if settings is None:
            settings = _load_persisted_settings()
        self._settings_data = settings

        resolved_theme = str(theme_name or "").strip()
        if not resolved_theme:
            resolved_theme = resolve_effective_ui_theme_name(settings)
        animation_enabled = bool(settings.get("popup_theme_animation_enabled", True))

        dialog_layout = QVBoxLayout(self)
        dialog_layout.setContentsMargins(0, 0, 0, 0)
        dialog_layout.setSpacing(0)

        self._background_root = GlassRoot(self)
        self._background_root.set_animation_enabled(animation_enabled)
        self._background_root.set_theme_name(resolved_theme)
        dialog_layout.addWidget(self._background_root, 1)

        root_layout = QVBoxLayout(self._background_root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self._content_host = QWidget(self._background_root)
        self._content_host.setObjectName("ThemedDialogContentHost")
        root_layout.addWidget(self._content_host, 1)

        self._content_layout = QVBoxLayout(self._content_host)
        self._content_layout.setContentsMargins(16, 16, 16, 16)
        self._content_layout.setSpacing(10)

    def content_layout(self) -> QVBoxLayout:
        return self._content_layout

    def set_dialog_theme_name(self, theme_name: str) -> None:
        self._background_root.set_theme_name(theme_name)

    def set_dialog_theme_animation_enabled(self, enabled: bool) -> None:
        self._background_root.set_animation_enabled(enabled)
