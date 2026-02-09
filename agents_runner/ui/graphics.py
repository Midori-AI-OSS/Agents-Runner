from __future__ import annotations

import importlib
import time

from PySide6.QtCore import QEasingCurve, Property, QPropertyAnimation, Qt, QTimer
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
    return "midoriai"


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

    def set_agent_theme(self, agent_cli: str) -> None:
        theme_name = _resolve_theme_name(_theme_name_for_agent(agent_cli))
        if theme_name == self._theme_name:
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
            self._set_theme_blend(0.0)

        anim.finished.connect(_finish)
        anim.start()
        self._theme_anim = anim

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
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        alpha = self._paint_theme(painter, self._theme_name)
        painter.fillRect(self.rect(), QColor(0, 0, 0, int(alpha)))

        if self._theme_to_name is not None and self._theme_blend > 0.0:
            painter.save()
            painter.setOpacity(float(self._theme_blend))
            alpha_to = self._paint_theme(painter, self._theme_to_name)
            painter.fillRect(self.rect(), QColor(0, 0, 0, int(alpha_to)))
            painter.restore()
