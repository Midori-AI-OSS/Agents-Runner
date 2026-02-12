from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QEasingCurve
from PySide6.QtCore import QParallelAnimationGroup
from PySide6.QtCore import QPoint
from PySide6.QtCore import QPropertyAnimation
from PySide6.QtCore import QSignalBlocker
from PySide6.QtCore import Qt
from PySide6.QtCore import QTimer
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox
from PySide6.QtWidgets import QGraphicsOpacityEffect
from PySide6.QtWidgets import QHBoxLayout
from PySide6.QtWidgets import QLabel
from PySide6.QtWidgets import QStackedWidget
from PySide6.QtWidgets import QToolButton
from PySide6.QtWidgets import QVBoxLayout
from PySide6.QtWidgets import QWidget

from agents_runner.environments import Environment
from agents_runner.environments import resolve_environment_github_repo
from agents_runner.ui.constants import CARD_MARGINS
from agents_runner.ui.constants import CARD_SPACING
from agents_runner.ui.constants import HEADER_MARGINS
from agents_runner.ui.constants import HEADER_SPACING
from agents_runner.ui.constants import MAIN_LAYOUT_MARGINS
from agents_runner.ui.constants import MAIN_LAYOUT_SPACING
from agents_runner.ui.graphics import _EnvironmentTintOverlay
from agents_runner.ui.pages.github_work_list import GitHubWorkListPage
from agents_runner.ui.pages.new_task import NewTaskPage
from agents_runner.ui.utils import _apply_environment_combo_tint
from agents_runner.ui.utils import _stain_color
from agents_runner.ui.widgets import GlassCard


@dataclass(frozen=True)
class _TasksPaneSpec:
    key: str
    title: str
    requires_github: bool


class TasksPage(QWidget):
    auto_review_requested = Signal(str, str)

    def __init__(
        self,
        *,
        new_task_page: NewTaskPage,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("TasksPageRoot")

        self._new_task = new_task_page
        self._environments: dict[str, Environment] = {}
        self._active_env_id = ""

        self._compact_mode = False
        self._active_pane_key = ""
        self._github_supported = False
        self._last_support_state: bool | None = None
        self._has_animated_supported_slide_in = False
        self._pending_supported_slide_in = False

        self._pane_animation: QParallelAnimationGroup | None = None
        self._pane_rest_pos: QPoint | None = None
        self._nav_animation: QParallelAnimationGroup | None = None

        self._nav_expanded_width = 280
        self._nav_panel_target_visible = True

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

        self._title = QLabel("Tasks")
        self._title.setStyleSheet("font-size: 18px; font-weight: 750;")
        self._subtitle = QLabel("Workflow")
        self._subtitle.setObjectName("SettingsPaneSubtitle")

        header_layout.addWidget(self._title)
        header_layout.addWidget(self._subtitle)
        header_layout.addStretch(1)
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

        self._nav_host = QWidget()
        self._nav_host.setObjectName("TasksNavHost")
        self._nav_host.setMinimumWidth(self._nav_expanded_width)
        self._nav_host.setMaximumWidth(self._nav_expanded_width)
        nav_host_layout = QVBoxLayout(self._nav_host)
        nav_host_layout.setContentsMargins(0, 0, 0, 0)
        nav_host_layout.setSpacing(0)

        self._nav_panel = QWidget(self._nav_host)
        self._nav_panel.setObjectName("SettingsNavPanel")
        self._nav_panel.setMinimumWidth(self._nav_expanded_width)
        self._nav_panel.setMaximumWidth(self._nav_expanded_width)
        nav_layout = QVBoxLayout(self._nav_panel)
        nav_layout.setContentsMargins(10, 10, 10, 10)
        nav_layout.setSpacing(6)
        nav_host_layout.addWidget(self._nav_panel)

        self._right_panel = QWidget()
        self._right_panel.setObjectName("SettingsPaneHost")
        right_layout = QVBoxLayout(self._right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        self._page_stack = QStackedWidget()
        self._page_stack.setObjectName("SettingsPageStack")
        right_layout.addWidget(self._page_stack, 1)

        panes_layout.addWidget(self._nav_host)
        panes_layout.addWidget(self._right_panel, 1)

        card_layout.addLayout(panes_layout, 1)
        layout.addWidget(card, 1)

        self._prs = GitHubWorkListPage(item_type="pr")
        self._issues = GitHubWorkListPage(item_type="issue")

        self._build_pages()
        self._build_navigation(nav_layout)
        self._sync_nav_button_sizes()

        self._new_task.environment_changed.connect(
            self._on_new_task_environment_changed
        )
        self._prs.environment_changed.connect(self._on_work_environment_changed)
        self._issues.environment_changed.connect(self._on_work_environment_changed)

        self._prs.prompt_append_requested.connect(self._append_prompt_to_new_task)
        self._issues.prompt_append_requested.connect(self._append_prompt_to_new_task)

        self._prs.auto_review_requested.connect(self.auto_review_requested.emit)
        self._issues.auto_review_requested.connect(self.auto_review_requested.emit)

        self._set_current_pane("new_task", animate=False)
        self._set_active_navigation("new_task")
        self._refresh_navigation_controls()

        self._update_navigation_mode(force=True)
        QTimer.singleShot(0, self._sync_nav_button_sizes)

        self._tint_overlay = _EnvironmentTintOverlay(self, alpha=13)
        self._tint_overlay.raise_()

    def _default_pane_specs(self) -> list[_TasksPaneSpec]:
        return [
            _TasksPaneSpec(
                key="new_task",
                title="New Task",
                requires_github=False,
            ),
            _TasksPaneSpec(
                key="pull_requests",
                title="Pull Requests",
                requires_github=True,
            ),
            _TasksPaneSpec(
                key="issues",
                title="Issues",
                requires_github=True,
            ),
        ]

    def _visible_pane_specs(self) -> list[_TasksPaneSpec]:
        if self._github_supported:
            return list(self._pane_specs)
        return [spec for spec in self._pane_specs if not spec.requires_github]

    def _is_pane_key_visible(self, key: str) -> bool:
        for spec in self._visible_pane_specs():
            if spec.key == key:
                return True
        return False

    def _build_pages(self) -> None:
        widget_for_key = {
            "new_task": self._new_task,
            "pull_requests": self._prs,
            "issues": self._issues,
        }
        for spec in self._pane_specs:
            widget = widget_for_key[spec.key]
            index = self._page_stack.addWidget(widget)
            self._pane_index_by_key[spec.key] = index

    def _build_navigation(self, nav_layout: QVBoxLayout) -> None:
        for spec in self._pane_specs:
            button = QToolButton()
            button.setObjectName("SettingsNavButton")
            button.setText(spec.title)
            button.setToolButtonStyle(Qt.ToolButtonTextOnly)
            button.setCheckable(True)
            button.clicked.connect(
                lambda _checked=False, pane_key=spec.key: self._on_nav_button_clicked(
                    pane_key
                )
            )
            self._nav_buttons[spec.key] = button
            nav_layout.addWidget(button)

        nav_layout.addStretch(1)

    def _sync_nav_button_sizes(self) -> None:
        if not self._nav_buttons:
            return
        width = 0
        for button in self._nav_buttons.values():
            width = max(width, button.sizeHint().width())
        width = min(max(width, 220), 300)
        for button in self._nav_buttons.values():
            button.setMinimumWidth(width)

    def _refresh_navigation_controls(self) -> None:
        visible_specs = self._visible_pane_specs()
        visible_keys = {spec.key for spec in visible_specs}

        for key, button in self._nav_buttons.items():
            button.setVisible(key in visible_keys)

        active_key = self._active_pane_key
        if not self._is_pane_key_visible(active_key):
            active_key = "new_task"
            self._set_current_pane(active_key, animate=True)

        self._set_active_navigation(active_key)

        with QSignalBlocker(self._compact_nav):
            self._compact_nav.clear()
            for spec in visible_specs:
                self._compact_nav.addItem(spec.title, spec.key)

            idx = self._compact_nav.findData(active_key)
            if idx < 0 and self._compact_nav.count() > 0:
                idx = 0
            if idx >= 0:
                self._compact_nav.setCurrentIndex(idx)

    def _on_nav_button_clicked(self, key: str) -> None:
        self._navigate_to_pane(key)

    def _on_compact_nav_changed(self, _index: int) -> None:
        key = str(self._compact_nav.currentData() or "").strip()
        if not key:
            return
        self._navigate_to_pane(key)

    def _navigate_to_pane(self, key: str) -> None:
        key = str(key or "").strip()
        if not key:
            return
        if not self._is_pane_key_visible(key):
            return
        if key == self._active_pane_key:
            self._set_active_navigation(key)
            return
        self._set_current_pane(key, animate=True)
        self._set_active_navigation(key)

    def _set_active_navigation(self, key: str) -> None:
        key = str(key or "").strip()
        self._active_pane_key = key

        for pane_key, button in self._nav_buttons.items():
            button.setChecked(pane_key == key and button.isVisible())

        idx = self._compact_nav.findData(key)
        if idx >= 0:
            with QSignalBlocker(self._compact_nav):
                self._compact_nav.setCurrentIndex(idx)

        if key == "new_task":
            self._subtitle.setText("Workflow")
        elif key == "pull_requests":
            self._subtitle.setText("Pull Requests")
        elif key == "issues":
            self._subtitle.setText("Issues")
        else:
            self._subtitle.setText("Workflow")

    def _set_current_pane(self, key: str, *, animate: bool) -> None:
        target_index = self._pane_index_by_key.get(key)
        if target_index is None:
            return

        current_index = self._page_stack.currentIndex()
        if current_index == target_index:
            self._active_pane_key = key
            self._sync_active_page_runtime()
            return

        if current_index < 0 or not animate:
            self._page_stack.setCurrentIndex(target_index)
            self._active_pane_key = key
            self._sync_active_page_runtime()
            return

        forward = target_index > current_index
        self._page_stack.setCurrentIndex(target_index)
        self._animate_stack(forward=forward)
        self._active_pane_key = key
        self._sync_active_page_runtime()

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

    def _sync_active_page_runtime(self) -> None:
        active = self._active_pane_key
        self._prs.set_polling_enabled(active == "pull_requests")
        self._issues.set_polling_enabled(active == "issues")

    def _apply_environment_tints(self) -> None:
        stain = ""
        env = self._environments.get(self._active_env_id)
        if env is not None:
            stain = str(env.normalized_color() or "").strip().lower()

        if not stain:
            self._compact_nav.setStyleSheet("")
            self._tint_overlay.set_tint_color(None)
            return

        _apply_environment_combo_tint(self._compact_nav, stain)
        self._tint_overlay.set_tint_color(_stain_color(stain))

    def _set_nav_panel_visible(self, visible: bool, *, animate: bool) -> None:
        visible = bool(visible)
        self._nav_panel_target_visible = visible

        if self._nav_animation is not None:
            self._nav_animation.stop()
            self._nav_animation = None

        effect = self._nav_panel.graphicsEffect()
        if not isinstance(effect, QGraphicsOpacityEffect):
            effect = QGraphicsOpacityEffect(self._nav_panel)
            self._nav_panel.setGraphicsEffect(effect)

        target_x = 0 if visible else -self._nav_expanded_width
        target_opacity = 1.0 if visible else 0.0
        current_x = int(self._nav_panel.pos().x())
        current_visible = bool(self._nav_host.isVisible())
        current_opacity = float(effect.opacity())
        if (
            current_x == target_x
            and current_visible == visible
            and abs(current_opacity - target_opacity) < 0.01
        ):
            return

        if not animate:
            if visible:
                self._nav_host.setVisible(True)
            else:
                self._nav_host.setVisible(False)
            self._nav_panel.move(target_x, 0)
            effect.setOpacity(target_opacity)
            return

        if visible:
            if not self._nav_host.isVisible():
                self._nav_host.setVisible(True)
                current_x = -self._nav_expanded_width
                current_opacity = 0.0
                self._nav_panel.move(current_x, 0)
                effect.setOpacity(current_opacity)
        elif not self._nav_host.isVisible():
            self._nav_panel.move(target_x, 0)
            effect.setOpacity(target_opacity)
            return

        start_x = current_x
        start_opacity = current_opacity
        if visible:
            if start_x == 0:
                start_x = -self._nav_expanded_width
            if start_opacity < 0.01:
                start_opacity = 0.0
        else:
            if start_x <= -self._nav_expanded_width:
                start_x = 0
            if start_opacity < 0.01:
                start_opacity = 1.0

        self._nav_panel.move(start_x, 0)
        effect.setOpacity(start_opacity)

        end_opacity = target_opacity

        pos_anim = QPropertyAnimation(self._nav_panel, b"pos", self)
        pos_anim.setDuration(220)
        pos_anim.setStartValue(QPoint(start_x, 0))
        pos_anim.setEndValue(QPoint(target_x, 0))
        pos_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)

        opacity_anim = QPropertyAnimation(effect, b"opacity", self)
        opacity_anim.setDuration(200)
        opacity_anim.setStartValue(start_opacity)
        opacity_anim.setEndValue(end_opacity)
        opacity_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)

        group = QParallelAnimationGroup(self)
        group.addAnimation(pos_anim)
        group.addAnimation(opacity_anim)

        def _cleanup() -> None:
            self._nav_panel.move(target_x, 0)
            effect.setOpacity(end_opacity)
            if not visible:
                self._nav_host.setVisible(False)
            self._nav_animation = None

        group.finished.connect(_cleanup)
        group.start()
        self._nav_animation = group

    def _sync_visibility_for_active_environment(self) -> None:
        env = self._environments.get(self._active_env_id)
        previous_supported = self._last_support_state
        supported = resolve_environment_github_repo(env) is not None

        self._github_supported = supported
        self._last_support_state = supported

        self._refresh_navigation_controls()
        self._apply_environment_tints()

        is_visible = bool(self.isVisible())

        if not supported:
            self._pending_supported_slide_in = False
            should_slide_out = bool(previous_supported is True and is_visible)
            self._update_navigation_mode(
                force=not is_visible,
                animate_override=should_slide_out,
            )
            return

        if not self._has_animated_supported_slide_in:
            if is_visible:
                self._has_animated_supported_slide_in = True
                self._pending_supported_slide_in = False
                self._update_navigation_mode(force=False, animate_override=True)
            else:
                self._pending_supported_slide_in = True
                self._update_navigation_mode(force=True, animate_override=False)
            return

        if previous_supported is False:
            if is_visible:
                self._pending_supported_slide_in = False
                self._update_navigation_mode(force=False, animate_override=True)
            else:
                self._pending_supported_slide_in = True
                self._update_navigation_mode(force=True, animate_override=False)
            return

        self._pending_supported_slide_in = False
        self._update_navigation_mode(force=not is_visible, animate_override=False)

    def set_environments(self, envs: dict[str, Environment], active_id: str) -> None:
        self._environments = dict(envs or {})
        self._active_env_id = str(active_id or "").strip()

        self._prs.set_environments(self._environments, self._active_env_id)
        self._issues.set_environments(self._environments, self._active_env_id)

        self._sync_visibility_for_active_environment()

    def set_settings_data(self, settings_data: dict[str, object]) -> None:
        self._prs.set_settings_data(settings_data)
        self._issues.set_settings_data(settings_data)

    def show_new_task_tab(self, *, focus_prompt: bool = True) -> None:
        self._set_current_pane("new_task", animate=True)
        self._set_active_navigation("new_task")
        if focus_prompt:
            self._new_task.focus_prompt()

    def _append_prompt_to_new_task(self, env_id: str, prompt: str) -> None:
        target_env_id = str(env_id or "").strip()
        if target_env_id:
            self._new_task.set_environment_id(target_env_id)

        self._new_task.append_prompt_text(prompt)
        self.show_new_task_tab(focus_prompt=True)

    def _on_new_task_environment_changed(self, env_id: str) -> None:
        env_id = str(env_id or "").strip()
        self._active_env_id = env_id
        self._prs.set_active_environment_id(env_id)
        self._issues.set_active_environment_id(env_id)
        self._sync_visibility_for_active_environment()

    def _on_work_environment_changed(self, env_id: str) -> None:
        env_id = str(env_id or "").strip()
        if env_id:
            self._new_task.set_environment_id(env_id)

    def is_new_task_tab_active(self) -> bool:
        return self._active_pane_key == "new_task"

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_navigation_mode(force=not self.isVisible())
        self._sync_nav_button_sizes()
        self._tint_overlay.setGeometry(self.rect())
        self._tint_overlay.raise_()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self._pending_supported_slide_in and self._github_supported:
            self._pending_supported_slide_in = False
            self._has_animated_supported_slide_in = True
            self._update_navigation_mode(force=False, animate_override=True)
        else:
            self._update_navigation_mode(force=True, animate_override=False)
        self._tint_overlay.setGeometry(self.rect())
        self._tint_overlay.raise_()

    def _update_navigation_mode(
        self, *, force: bool, animate_override: bool | None = None
    ) -> None:
        is_visible = bool(self.isVisible())
        should_animate_override = bool(
            animate_override is True and not force and is_visible
        )

        if not self._github_supported:
            self._compact_mode = False
            self._compact_nav.setVisible(False)
            if animate_override is None:
                animate_panel = bool(not force and self._nav_panel_target_visible)
                animate_panel = bool(animate_panel and is_visible)
            else:
                animate_panel = should_animate_override
            self._set_nav_panel_visible(False, animate=animate_panel)
            return

        compact = self.width() < 1080
        mode_changed = compact != self._compact_mode
        self._compact_mode = compact

        self._compact_nav.setVisible(compact)

        target_visible = not compact
        if animate_override is None:
            animate_panel = bool(
                (mode_changed or target_visible != self._nav_panel_target_visible)
                and not force
                and is_visible
            )
        else:
            animate_panel = should_animate_override
        self._set_nav_panel_visible(target_visible, animate=animate_panel)
