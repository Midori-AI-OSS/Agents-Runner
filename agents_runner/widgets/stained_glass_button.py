from __future__ import annotations

from PySide6.QtCore import QAbstractAnimation, QEvent, QEasingCurve, Property, QPropertyAnimation, QRect, QSize, Qt
from PySide6.QtGui import QBrush, QColor, QLinearGradient, QMouseEvent, QPainter, QPainterPath
from PySide6.QtWidgets import QMenu, QPushButton, QWidget


def _clamp_u8(value: int) -> int:
    return int(min(255, max(0, value)))


def _scale_rgb(color: QColor, scale: float) -> QColor:
    s = float(max(0.0, scale))
    return QColor(
        _clamp_u8(int(round(color.red() * s))),
        _clamp_u8(int(round(color.green() * s))),
        _clamp_u8(int(round(color.blue() * s))),
        color.alpha(),
    )


def _blend_rgb(a: QColor, b: QColor, t: float) -> QColor:
    tt = float(min(max(t, 0.0), 1.0))
    return QColor(
        int(round(a.red() + (b.red() - a.red()) * tt)),
        int(round(a.green() + (b.green() - a.green()) * tt)),
        int(round(a.blue() + (b.blue() - a.blue()) * tt)),
    )


class StainedGlassButton(QPushButton):
    """Environment-tinted, square-corner 'stained glass' button with a slow pulse."""

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setObjectName("StainedGlassButton")
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAutoFillBackground(False)
        self._tint_color: QColor | None = None
        self._glass_enabled = True
        self._pulse = 0.0
        self._menu: QMenu | None = None
        self._menu_width = 22

        anim = QPropertyAnimation(self, b"pulse", self)
        anim.setDuration(24000)
        anim.setStartValue(0.0)
        anim.setKeyValueAt(0.5, 1.0)
        anim.setEndValue(0.0)
        anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        anim.setLoopCount(-1)
        anim.valueChanged.connect(lambda: self.update())
        self._pulse_anim = anim

    def set_glass_enabled(self, enabled: bool) -> None:
        self._glass_enabled = bool(enabled)
        if not self._glass_enabled and self._pulse_anim.state() == QAbstractAnimation.State.Running:
            self._pulse_anim.stop()
        elif (
            self._glass_enabled
            and self.isEnabled()
            and self.isVisible()
            and self._pulse_anim.state() != QAbstractAnimation.State.Running
        ):
            self._pulse_anim.start()
        self.update()

    def set_tint_color(self, color: QColor | None) -> None:
        if color is None:
            self._tint_color = None
        else:
            self._tint_color = QColor(color.red(), color.green(), color.blue(), 255)
        self.update()

    def set_menu(self, menu: QMenu | None) -> None:
        self._menu = menu
        self.update()

    def _menu_rect(self, rect) -> QRect:
        if self._menu is None:
            return QRect()
        w = int(self._menu_width)
        return QRect(rect.right() - w + 1, rect.top(), w, rect.height())

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if (
            self._menu is not None
            and self.isEnabled()
            and event.button() == Qt.MouseButton.LeftButton
            and self._menu_rect(self.rect().adjusted(1, 1, -1, -1)).contains(event.position().toPoint())
        ):
            self._menu.exec(event.globalPosition().toPoint())
            return
        super().mouseReleaseEvent(event)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self._glass_enabled and self.isEnabled() and self._pulse_anim.state() != QAbstractAnimation.State.Running:
            self._pulse_anim.start()

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        if self._pulse_anim.state() == QAbstractAnimation.State.Running:
            self._pulse_anim.stop()

    def changeEvent(self, event) -> None:
        super().changeEvent(event)
        if event.type() == QEvent.Type.EnabledChange:
            if self._glass_enabled and self.isEnabled():
                if self.isVisible() and self._pulse_anim.state() != QAbstractAnimation.State.Running:
                    self._pulse_anim.start()
            else:
                if self._pulse_anim.state() == QAbstractAnimation.State.Running:
                    self._pulse_anim.stop()
            self.update()

    def get_pulse(self) -> float:
        return float(self._pulse)

    def set_pulse(self, value: float) -> None:
        self._pulse = float(min(max(value, 0.0), 1.0))
        self.update()

    pulse = Property(float, get_pulse, set_pulse)

    def sizeHint(self) -> QSize:
        base = super().sizeHint()
        return QSize(base.width() + 24, base.height())

    def minimumSizeHint(self) -> QSize:
        base = super().minimumSizeHint()
        return QSize(base.width() + 24, base.height())

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        rect = self.rect().adjusted(1, 1, -1, -1)
        if rect.width() <= 4 or rect.height() <= 4:
            return

        path = QPainterPath()
        path.addRect(rect)

        if not self._glass_enabled:
            if not self.isEnabled():
                bg = QColor(18, 20, 28, 90)
                border = QColor(255, 255, 255, 14)
                text_color = QColor(237, 239, 245, 130)
            else:
                if self.isDown():
                    bg = QColor(56, 189, 248, 70)
                    border = QColor(56, 189, 248, 100)
                elif self.underMouse():
                    bg = QColor(56, 189, 248, 30)
                    border = QColor(56, 189, 248, 80)
                else:
                    bg = QColor(18, 20, 28, 135)
                    border = QColor(255, 255, 255, 22)
                if not self.isDown() and not self.underMouse() and self.hasFocus():
                    border = QColor(56, 189, 248, 105)
                text_color = QColor(237, 239, 245, 240)

            painter.fillPath(path, bg)
            painter.setPen(border)
            painter.drawRect(rect)
            painter.setPen(text_color)
            menu_rect = self._menu_rect(rect)
            text_rect = rect.adjusted(10, 0, -10, 0)
            if not menu_rect.isNull():
                text_rect = text_rect.adjusted(0, 0, -menu_rect.width(), 0)
            painter.drawText(text_rect, Qt.AlignCenter, self.text())
            if not menu_rect.isNull():
                painter.drawText(menu_rect, Qt.AlignCenter, "▾")
            return

        base = QColor(18, 20, 28)
        env = self._tint_color or QColor(148, 163, 184)

        # Slightly darker than the surrounding menu tint, with a very slow, subtle bright pulse.
        pulse = float(self._pulse)
        brightness = 0.84 + 0.12 * pulse
        if self.isDown():
            brightness *= 0.92
        elif self.underMouse():
            brightness *= 1.03

        tinted = _blend_rgb(base, env, 0.34)
        tinted = _scale_rgb(tinted, brightness)

        if self._glass_enabled:
            fill_alpha = 95 if self.isEnabled() else 45
            if self.underMouse():
                fill_alpha = min(135, fill_alpha + 18)
            if self.isDown():
                fill_alpha = max(55, fill_alpha - 16)
            painter.fillPath(path, QColor(tinted.red(), tinted.green(), tinted.blue(), fill_alpha))

            grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
            grad.setColorAt(0.0, QColor(255, 255, 255, 14 + int(10 * pulse)))
            grad.setColorAt(0.55, QColor(env.red(), env.green(), env.blue(), 16 + int(10 * pulse)))
            grad.setColorAt(1.0, QColor(0, 0, 0, 24))
            painter.fillPath(path, QBrush(grad))

            # Stained-glass shards (environment-colored) for texture.
            w = max(1, rect.width())
            h = max(1, rect.height())
            x0 = rect.left()
            y0 = rect.top()

            shard_color = QColor(env.red(), env.green(), env.blue(), 22 + int(12 * pulse))
            shard_color_2 = QColor(*_blend_rgb(env, QColor(255, 255, 255), 0.25).getRgb()[:3], 16 + int(10 * pulse))
            edge = QColor(255, 255, 255, 12 + int(6 * pulse))

            shards = [
                (shard_color, [(0.00, 0.10), (0.30, 0.00), (0.55, 0.28), (0.18, 0.40)]),
                (shard_color_2, [(0.56, 0.00), (1.00, 0.18), (0.88, 0.52), (0.56, 0.36)]),
                (shard_color, [(0.05, 0.62), (0.28, 0.44), (0.56, 0.72), (0.22, 0.96)]),
                (shard_color_2, [(0.62, 0.58), (0.92, 0.44), (1.00, 0.88), (0.76, 1.00)]),
            ]

            for color, points in shards:
                shard_path = QPainterPath()
                px, py = points[0]
                shard_path.moveTo(int(x0 + px * w), int(y0 + py * h))
                for sx, sy in points[1:]:
                    shard_path.lineTo(int(x0 + sx * w), int(y0 + sy * h))
                shard_path.closeSubpath()
                painter.fillPath(shard_path, color)
                painter.setPen(edge)
                painter.drawPath(shard_path)

        # Frame/border.
        if not self.isEnabled():
            border = QColor(255, 255, 255, 16)
        elif self.hasFocus():
            border = QColor(env.red(), env.green(), env.blue(), 110)
        else:
            border = QColor(255, 255, 255, 24)
        painter.setPen(border)
        painter.drawRect(rect)

        # Label.
        if not self.isEnabled():
            text_color = QColor(237, 239, 245, 130)
        else:
            text_color = QColor(237, 239, 245, 240)
        painter.setPen(text_color)
        menu_rect = self._menu_rect(rect)
        text_rect = rect.adjusted(10, 0, -10, 0)
        if not menu_rect.isNull():
            text_rect = text_rect.adjusted(0, 0, -menu_rect.width(), 0)
        painter.drawText(text_rect, Qt.AlignCenter, self.text())
        if not menu_rect.isNull():
            painter.drawText(menu_rect, Qt.AlignCenter, "▾")
