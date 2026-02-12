from __future__ import annotations

from PySide6.QtCore import (
    QEasingCurve,
    QParallelAnimationGroup,
    QPoint,
    QPropertyAnimation,
    QSignalBlocker,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtWidgets import QComboBox
from PySide6.QtWidgets import QGraphicsOpacityEffect
from PySide6.QtWidgets import QHBoxLayout
from PySide6.QtWidgets import QLabel
from PySide6.QtWidgets import QStackedWidget
from PySide6.QtWidgets import QToolButton
from PySide6.QtWidgets import QVBoxLayout
from PySide6.QtWidgets import QWidget

from agents_runner.ui.widgets import GlassCard
from agents_runner.ui.constants import (
    MAIN_LAYOUT_MARGINS,
    MAIN_LAYOUT_SPACING,
    HEADER_MARGINS,
    HEADER_SPACING,
    CARD_MARGINS,
    CARD_SPACING,
)
from agents_runner.ui.pages.settings_form import _SettingsFormMixin


class SettingsPage(QWidget, _SettingsFormMixin):
    back_requested = Signal()
    saved = Signal(dict)
    test_preflight_requested = Signal(dict)

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        radio_supported: bool = True,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("SettingsPageRoot")
        self._radio_supported = bool(radio_supported)

        self._suppress_autosave = False
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setSingleShot(True)
        self._autosave_timer.setInterval(450)
        self._autosave_timer.timeout.connect(self._emit_saved)

        self._pane_animation: QParallelAnimationGroup | None = None
        self._pane_rest_pos: QPoint | None = None
        self._compact_mode = False
        self._active_pane_key = ""

        self._pane_specs = self._default_pane_specs()
        self._pane_index_by_key: dict[str, int] = {}
        self._nav_buttons: dict[str, QToolButton] = {}

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
        back.clicked.connect(self._on_back)

        header_layout.addWidget(title)
        header_layout.addStretch(1)
        header_layout.addWidget(back, 0, Qt.AlignRight)
        layout.addWidget(header)

        card = GlassCard()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(*CARD_MARGINS)
        card_layout.setSpacing(CARD_SPACING)

        self._compact_nav = QComboBox()
        self._compact_nav.setObjectName("SettingsCompactNav")
        self._compact_nav.setVisible(False)
        self._compact_nav.currentIndexChanged.connect(self._on_compact_nav_changed)
        card_layout.addWidget(self._compact_nav)

        panes_layout = QHBoxLayout()
        panes_layout.setContentsMargins(0, 0, 0, 0)
        panes_layout.setSpacing(14)

        self._nav_panel = QWidget()
        self._nav_panel.setObjectName("SettingsNavPanel")
        self._nav_panel.setMinimumWidth(250)
        self._nav_panel.setMaximumWidth(320)
        nav_layout = QVBoxLayout(self._nav_panel)
        nav_layout.setContentsMargins(10, 10, 10, 10)
        nav_layout.setSpacing(6)

        self._right_panel = QWidget()
        self._right_panel.setObjectName("SettingsPaneHost")
        right_layout = QVBoxLayout(self._right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        self._page_stack = QStackedWidget()
        self._page_stack.setObjectName("SettingsPageStack")
        right_layout.addWidget(self._page_stack, 1)

        panes_layout.addWidget(self._nav_panel)
        panes_layout.addWidget(self._right_panel, 1)

        card_layout.addLayout(panes_layout, 1)
        layout.addWidget(card, 1)

        self._build_controls()
        self._build_pages()
        self._build_navigation(nav_layout)
        self._sync_nav_button_sizes()
        self._connect_autosave_signals()

        if self._pane_specs:
            first_key = self._pane_specs[0].key
            self._set_active_navigation(first_key)
            self._set_current_pane(first_key, animate=False)

        self._update_navigation_mode()
        QTimer.singleShot(0, self._sync_nav_button_sizes)

    def _connect_autosave_signals(self) -> None:
        for combo in (
            self._use,
            self._shell,
            self._ui_theme,
            self._radio_channel,
            self._radio_quality,
            self._github_write_confirmation_mode,
        ):
            combo.currentIndexChanged.connect(self._trigger_immediate_autosave)

        for checkbox in (
            self._preflight_enabled,
            self._append_pixelarch_context,
            self._github_workroom_prefer_browser,
            self._agentsnova_auto_review_enabled,
            self._headless_desktop_enabled,
            self._gh_context_default,
            self._spellcheck_enabled,
            self._mount_host_cache,
            self._radio_enabled,
            self._radio_autostart,
            self._radio_loudness_boost_enabled,
        ):
            checkbox.toggled.connect(self._trigger_immediate_autosave)

        for line_edit in (
            self._host_codex_dir,
            self._host_claude_dir,
            self._host_copilot_dir,
            self._host_gemini_dir,
        ):
            line_edit.textChanged.connect(self._queue_debounced_autosave)

        self._preflight_script.textChanged.connect(self._queue_debounced_autosave)
        self._radio_volume.valueChanged.connect(self._queue_debounced_autosave)
        self._radio_loudness_boost_factor.valueChanged.connect(
            self._queue_debounced_autosave
        )

    def _on_back(self) -> None:
        self.try_autosave()
        self.back_requested.emit()

    def _on_test_preflight(self) -> None:
        self.try_autosave()
        self.test_preflight_requested.emit(self.get_settings())

    def _on_nav_button_clicked(self, key: str) -> None:
        self._navigate_to_pane(key, user_initiated=True)

    def _on_compact_nav_changed(self, _index: int) -> None:
        key = str(self._compact_nav.currentData() or "").strip()
        if not key:
            return
        self._navigate_to_pane(key, user_initiated=True)

    def _navigate_to_pane(self, key: str, *, user_initiated: bool) -> None:
        key = str(key or "").strip()
        if not key or key not in self._pane_index_by_key:
            return
        if key == self._active_pane_key:
            self._set_active_navigation(key)
            return

        if user_initiated:
            self.try_autosave()

        self._set_current_pane(key, animate=True)
        self._set_active_navigation(key)

    def _set_active_navigation(self, key: str) -> None:
        self._active_pane_key = key
        for pane_key, button in self._nav_buttons.items():
            button.setChecked(pane_key == key)

        idx = self._compact_nav.findData(key)
        if idx >= 0:
            with QSignalBlocker(self._compact_nav):
                self._compact_nav.setCurrentIndex(idx)

    def _set_current_pane(self, key: str, *, animate: bool) -> None:
        target_index = self._pane_index_by_key.get(key)
        if target_index is None:
            return

        current_index = self._page_stack.currentIndex()
        if current_index == target_index:
            self._active_pane_key = key
            return

        if current_index < 0 or not animate:
            self._page_stack.setCurrentIndex(target_index)
            self._active_pane_key = key
            return

        forward = target_index > current_index
        self._page_stack.setCurrentIndex(target_index)
        self._animate_stack(forward=forward)
        self._active_pane_key = key

    def _animate_stack(self, *, forward: bool) -> None:
        if self._pane_animation is not None:
            self._pane_animation.stop()
            self._pane_animation = None

        if self._pane_rest_pos is not None:
            self._page_stack.move(self._pane_rest_pos)
        self._page_stack.setGraphicsEffect(None)

        base_pos = self._page_stack.pos()
        self._pane_rest_pos = QPoint(base_pos)

        offset = 16 if forward else -16
        start_pos = QPoint(base_pos.x() + offset, base_pos.y())

        effect = QGraphicsOpacityEffect(self._page_stack)
        effect.setOpacity(0.0)
        self._page_stack.setGraphicsEffect(effect)
        self._page_stack.move(start_pos)

        pos_anim = QPropertyAnimation(self._page_stack, b"pos", self)
        pos_anim.setDuration(210)
        pos_anim.setStartValue(start_pos)
        pos_anim.setEndValue(base_pos)
        pos_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        opacity_anim = QPropertyAnimation(effect, b"opacity", self)
        opacity_anim.setDuration(210)
        opacity_anim.setStartValue(0.0)
        opacity_anim.setEndValue(1.0)
        opacity_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        group = QParallelAnimationGroup(self)
        group.addAnimation(pos_anim)
        group.addAnimation(opacity_anim)

        def _cleanup() -> None:
            if self._pane_rest_pos is not None:
                self._page_stack.move(self._pane_rest_pos)
            self._page_stack.setGraphicsEffect(None)
            self._pane_animation = None

        group.finished.connect(_cleanup)
        group.start()
        self._pane_animation = group

    def _queue_debounced_autosave(self, *_args: object) -> None:
        if self._suppress_autosave:
            return
        self._autosave_timer.start()

    def _trigger_immediate_autosave(self, *_args: object) -> None:
        if self._suppress_autosave:
            return
        if self._autosave_timer.isActive():
            self._autosave_timer.stop()
        self._emit_saved()

    def _emit_saved(self) -> None:
        if self._suppress_autosave:
            return
        self.saved.emit(self.get_settings())

    def try_autosave(self) -> bool:
        if self._autosave_timer.isActive():
            self._autosave_timer.stop()
        self._emit_saved()
        return True

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_navigation_mode()
        self._sync_nav_button_sizes()

    def _update_navigation_mode(self) -> None:
        compact = self.width() < 1080
        if compact == self._compact_mode:
            return
        self._compact_mode = compact
        self._compact_nav.setVisible(compact)
        self._nav_panel.setVisible(not compact)
        if not compact:
            QTimer.singleShot(0, self._sync_nav_button_sizes)

    def _sync_nav_button_sizes(self) -> None:
        if self._compact_mode or not self._nav_buttons:
            return

        panel_width = self._nav_panel.width()
        if panel_width <= 0:
            return

        inner_width = panel_width
        nav_layout = self._nav_panel.layout()
        if nav_layout is not None:
            margins = nav_layout.contentsMargins()
            inner_width -= margins.left() + margins.right()

        target_width = max(1, inner_width - 2)
        for button in self._nav_buttons.values():
            button.setFixedWidth(target_width)
