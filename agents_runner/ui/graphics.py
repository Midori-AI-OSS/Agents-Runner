from __future__ import annotations

import importlib
import time
from pathlib import Path

from PySide6.QtCore import (
    QEasingCurve,
    Property,
    QPropertyAnimation,
    Qt,
    QTimer,
)
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QResizeEvent
from PySide6.QtWidgets import QWidget

from agents_runner.ui.themes.types import ThemeBackground

_BACKGROUND_CACHE: dict[str, ThemeBackground | None] = {}


def _load_background(theme_name: str) -> ThemeBackground | None:
    theme_name = str(theme_name or "").strip().lower()
    if not theme_name:
        return None
    if theme_name in _BACKGROUND_CACHE:
        return _BACKGROUND_CACHE[theme_name]

    module_name = f"agents_runner.ui.themes.{theme_name}.background"
    try:
        module = importlib.import_module(module_name)
    except Exception:
        module = None

    background = getattr(module, "BACKGROUND", None) if module is not None else None
    if background is not None and not isinstance(background, ThemeBackground):
        background = None

    _BACKGROUND_CACHE[theme_name] = background
    return background


def _fallback_theme_name() -> str:
    return "midoriai_dark"


def discover_theme_module_names() -> list[str]:
    """Discover available background theme modules from ui/themes."""
    root = Path(__file__).resolve().parent / "themes"
    discovered: list[str] = []
    try:
        entries = sorted(root.iterdir(), key=lambda path: path.name.lower())
    except Exception:
        return discovered

    for entry in entries:
        if not entry.is_dir() or entry.name.startswith("__"):
            continue
        if not (entry / "background.py").is_file():
            continue
        name = str(entry.name or "").strip().lower()
        if not name:
            continue
        if _load_background(name) is None:
            continue
        discovered.append(name)
    return discovered


def discover_plugin_theme_names() -> list[str]:
    """Discover theme names declared by agent system plugins."""
    try:
        from agents_runner.agent_systems import available_agent_system_names
        from agents_runner.agent_systems import get_agent_system
    except Exception:
        return []

    discovered: list[str] = []
    for agent_name in available_agent_system_names():
        try:
            plugin = get_agent_system(agent_name)
        except Exception:
            continue
        theme_name = ""
        if getattr(plugin, "ui_theme", None) is not None:
            theme_name = str(getattr(plugin.ui_theme, "theme_name", "") or "").strip()
        normalized = theme_name.lower()
        if not normalized or normalized in discovered:
            continue
        if _load_background(normalized) is None:
            continue
        discovered.append(normalized)
    return discovered


def available_ui_theme_names() -> list[str]:
    """Return selectable UI theme names discovered from plugins and theme modules."""
    ordered: list[str] = []
    for name in discover_plugin_theme_names():
        if name not in ordered:
            ordered.append(name)
    for name in discover_theme_module_names():
        if name not in ordered:
            ordered.append(name)
    fallback = _fallback_theme_name()
    if fallback not in ordered and _load_background(fallback) is not None:
        ordered.append(fallback)
    return ordered


def normalize_ui_theme_name(theme_name: str | None, *, allow_auto: bool = True) -> str:
    """Normalize a persisted theme setting to a discovered value."""
    raw = str(theme_name or "").strip().lower()
    if allow_auto and (not raw or raw == "auto"):
        return "auto"

    available = set(available_ui_theme_names())
    if raw in available:
        return raw

    if allow_auto:
        return "auto"
    return _fallback_theme_name()


def _resolve_theme_name(theme_name: str) -> str:
    candidate = str(theme_name or "").strip().lower()
    if not candidate:
        candidate = _fallback_theme_name()
    if _load_background(candidate) is not None:
        return candidate
    fallback = _fallback_theme_name()
    if candidate != fallback and _load_background(fallback) is not None:
        return fallback
    return candidate


def _theme_name_for_agent(agent_cli: str) -> str:
    agent_cli = str(agent_cli or "").strip().lower()
    if not agent_cli:
        return _fallback_theme_name()

    try:
        from agents_runner.agent_systems import get_agent_system

        plugin = get_agent_system(agent_cli)
    except Exception:
        return _fallback_theme_name()

    theme_name = ""
    if getattr(plugin, "ui_theme", None) is not None:
        theme_name = str(getattr(plugin.ui_theme, "theme_name", "") or "").strip()
    return theme_name.lower() or _fallback_theme_name()


class _EnvironmentTintOverlay(QWidget):
    def __init__(self, parent: QWidget | None = None, alpha: int = 13) -> None:
        super().__init__(parent)
        self._alpha = int(min(max(alpha, 0), 255))
        self._color = QColor(0, 0, 0, 0)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAutoFillBackground(False)

    def set_tint_color(self, color: QColor | None) -> None:
        if color is None:
            self._color = QColor(0, 0, 0, 0)
        else:
            self._color = QColor(color.red(), color.green(), color.blue(), self._alpha)
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        if self._color.alpha() <= 0:
            return
        painter = QPainter(self)
        painter.fillRect(self.rect(), self._color)


class GlassRoot(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._theme_name = _fallback_theme_name()
        self._theme_to_name: str | None = None
        self._theme_blend = 0.0
        self._theme_anim: QPropertyAnimation | None = None
        self._startup_black_active = True
        self._startup_theme_applied = False
        self._startup_blend_from_black = False
        self._startup_pending_theme: str | None = None

        self._theme_runtimes: dict[str, object] = {}
        self._tick_last_s = time.monotonic()

        self._ensure_theme_runtime(self._theme_name)

        ticker = QTimer(self)
        ticker.setInterval(100)
        ticker.timeout.connect(self._update_background_animation)
        ticker.start()

    def _ensure_theme_runtime(self, theme_name: str) -> object | None:
        resolved = _resolve_theme_name(theme_name)
        background = _load_background(resolved)
        if background is None:
            return None
        if resolved not in self._theme_runtimes:
            try:
                self._theme_runtimes[resolved] = background.init_runtime(widget=self)
            except Exception:
                return None
        return self._theme_runtimes.get(resolved)

    def _paint_theme(self, painter: QPainter, theme_name: str) -> int:
        resolved = _resolve_theme_name(theme_name)
        rect = self.rect()
        background = _load_background(resolved)
        runtime = self._ensure_theme_runtime(resolved)

        if background is None or runtime is None:
            painter.fillRect(rect, QColor(10, 11, 13))
            return 32

        try:
            background.paint(painter=painter, rect=rect, runtime=runtime)
        except Exception:
            painter.fillRect(rect, background.base_color())

        try:
            return int(background.overlay_alpha())
        except Exception:
            return 32

    def _animate_theme_transition(self, theme_name: str, *, from_black: bool) -> None:
        theme_name = _resolve_theme_name(theme_name)
        if not from_black and theme_name == self._theme_name:
            return

        self._ensure_theme_runtime(theme_name)
        background = _load_background(theme_name)
        runtime = self._theme_runtimes.get(theme_name)
        if background is not None and runtime is not None:
            try:
                background.tick(
                    runtime=runtime, widget=self, now_s=time.monotonic(), dt_s=0.0
                )
            except Exception:
                pass

        self._theme_to_name = theme_name
        self._startup_blend_from_black = bool(from_black)
        self._set_theme_blend(0.0)

        if self._theme_anim is not None:
            self._theme_anim.stop()

        anim = QPropertyAnimation(self, b"themeBlend", self)
        anim.setDuration(7000)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.InOutCubic)

        def _finish() -> None:
            self._theme_name = theme_name
            self._theme_to_name = None
            self._startup_blend_from_black = False
            self._set_theme_blend(0.0)
            if from_black:
                self._startup_black_active = False

        anim.finished.connect(_finish)
        anim.start()
        self._theme_anim = anim

    def _transition_to_theme(self, theme_name: str) -> None:
        self._animate_theme_transition(theme_name, from_black=False)

    def set_theme_name(self, theme_name: str) -> None:
        if self._startup_black_active:
            self.apply_startup_theme_name(theme_name)
            return
        self._transition_to_theme(theme_name)

    def set_agent_theme(self, agent_cli: str) -> None:
        if self._startup_black_active:
            self.apply_startup_agent_theme(agent_cli)
            return
        self._transition_to_theme(_theme_name_for_agent(agent_cli))

    def apply_startup_theme_name(self, theme_name: str) -> None:
        resolved = _resolve_theme_name(theme_name)

        if not self._startup_black_active:
            self._transition_to_theme(resolved)
            return

        self._startup_pending_theme = resolved
        if not self.isVisible():
            self.update()
            return

        if self._startup_theme_applied:
            if self._theme_to_name != resolved or not self._startup_blend_from_black:
                self._animate_theme_transition(resolved, from_black=True)
            return

        self._startup_theme_applied = True
        self._animate_theme_transition(resolved, from_black=True)

    def apply_startup_agent_theme(self, agent_cli: str) -> None:
        self.apply_startup_theme_name(_theme_name_for_agent(agent_cli))

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._startup_black_active or self._startup_theme_applied:
            return
        target = self._startup_pending_theme or self._theme_name
        self.apply_startup_theme_name(target)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        candidates = {self._theme_name}
        if self._theme_to_name:
            candidates.add(self._theme_to_name)

        for theme_name in candidates:
            resolved = _resolve_theme_name(theme_name)
            background = _load_background(resolved)
            runtime = self._theme_runtimes.get(resolved)
            if background is None or runtime is None:
                continue
            try:
                background.on_resize(runtime=runtime, widget=self)
            except Exception:
                pass

    def _get_theme_blend(self) -> float:
        return float(self._theme_blend)

    def _set_theme_blend(self, value: float) -> None:
        self._theme_blend = float(min(max(value, 0.0), 1.0))
        self.update()

    themeBlend = Property(float, _get_theme_blend, _set_theme_blend)

    def _update_background_animation(self) -> None:
        now_s = time.monotonic()
        dt_s = float(now_s - float(self._tick_last_s))
        if dt_s <= 0.0:
            return
        self._tick_last_s = now_s
        dt_s = float(min(dt_s, 0.25))

        repaint = False
        candidates = [self._theme_name]
        if self._theme_to_name:
            candidates.append(self._theme_to_name)

        for theme_name in candidates:
            resolved = _resolve_theme_name(theme_name)
            background = _load_background(resolved)
            runtime = self._ensure_theme_runtime(resolved)
            if background is None or runtime is None:
                continue
            try:
                repaint = bool(
                    repaint
                    or background.tick(
                        runtime=runtime,
                        widget=self,
                        now_s=now_s,
                        dt_s=dt_s,
                    )
                )
            except Exception:
                repaint = True

        if repaint:
            self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        if self._startup_black_active and self._theme_to_name is None:
            painter.fillRect(self.rect(), QColor(0, 0, 0))
            return

        if self._theme_to_name is not None and self._startup_blend_from_black:
            painter.fillRect(self.rect(), QColor(0, 0, 0))
        else:
            alpha = self._paint_theme(painter, self._theme_name)
            painter.fillRect(self.rect(), QColor(0, 0, 0, int(alpha)))

        if self._theme_to_name is not None and self._theme_blend > 0.0:
            painter.save()
            painter.setOpacity(float(self._theme_blend))
            alpha_to = self._paint_theme(painter, self._theme_to_name)
            painter.fillRect(self.rect(), QColor(0, 0, 0, int(alpha_to)))
            painter.restore()
