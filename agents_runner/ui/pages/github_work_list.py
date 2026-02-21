from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QPropertyAnimation
from PySide6.QtCore import Qt
from PySide6.QtCore import QTimer
from PySide6.QtCore import QUrl
from PySide6.QtCore import Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtGui import QMouseEvent
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import QGraphicsOpacityEffect
from PySide6.QtWidgets import QHBoxLayout
from PySide6.QtWidgets import QLabel
from PySide6.QtWidgets import QScrollArea
from PySide6.QtWidgets import QSizePolicy
from PySide6.QtWidgets import QToolButton
from PySide6.QtWidgets import QVBoxLayout
from PySide6.QtWidgets import QWidget

from agents_runner.environments import Environment
from agents_runner.environments import resolve_environment_github_repo
from agents_runner.gh.work_items import GitHubWorkItem
from agents_runner.gh.work_items import get_authenticated_github_login
from agents_runner.prompts import load_prompt
from agents_runner.ui.dialogs.github_workroom_dialog import GitHubWorkroomDialog
from agents_runner.ui.lucide_icons import lucide_icon
from agents_runner.ui.utils import resolve_chat_bubble_tone
from agents_runner.ui.utils import stain_color
from agents_runner.ui.widgets import BouncingLoadingBar
from agents_runner.ui.widgets import ChatBubbleAction
from agents_runner.ui.widgets import ChatBubbleData
from agents_runner.ui.widgets import ChatBubbleWidget
from midori_ai_logger import MidoriAiLogger

logger = MidoriAiLogger(channel=None, name=__name__)


class _GitHubWorkRow(QWidget):
    clicked = Signal(object)
    primary_requested = Signal(object)
    reply_requested = Signal(object)
    open_requested = Signal(object)

    def __init__(self, *, item_type: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._item: GitHubWorkItem | None = None
        self._item_type = str(item_type or "issue").strip().lower()
        self._stain = "slate"
        self._current_login = ""
        self._row_animation: QPropertyAnimation | None = None

        self.setObjectName("TaskRow")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setProperty("stain", "slate")
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(108)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(0)

        self._bubble = ChatBubbleWidget()
        self._bubble.reply_requested.connect(
            lambda: self.reply_requested.emit(self._item)
        )
        self._bubble.open_requested.connect(
            lambda: self.open_requested.emit(self._item)
        )
        self._bubble.primary_requested.connect(
            lambda: self.primary_requested.emit(self._item)
        )
        layout.addWidget(self._bubble, 1)

    def _normalize_user(self, username: str) -> str:
        return str(username or "").strip().lower().lstrip("@")

    def _is_self_author(self, author: str) -> bool:
        return bool(self._current_login) and self._normalize_user(author) == str(
            self._current_login or ""
        )

    def _format_time(self, value: str) -> str:
        text = str(value or "").strip()
        if not text:
            return "—"
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            return parsed.strftime("%Y-%m-%d %H:%M")
        except Exception:
            return text

    def _opacity_effect(self) -> QGraphicsOpacityEffect:
        effect = self.graphicsEffect()
        if isinstance(effect, QGraphicsOpacityEffect):
            return effect
        effect = QGraphicsOpacityEffect(self)
        effect.setOpacity(1.0)
        self.setGraphicsEffect(effect)
        return effect

    def play_entrance(self, *, delay_ms: int = 0) -> None:
        effect = self._opacity_effect()
        effect.setOpacity(0.0)
        if self._row_animation is not None:
            self._row_animation.stop()
            self._row_animation = None

        def _start() -> None:
            anim = QPropertyAnimation(effect, b"opacity", self)
            anim.setDuration(220)
            anim.setStartValue(0.0)
            anim.setEndValue(1.0)
            anim.finished.connect(self._on_entrance_finished)
            anim.start()
            self._row_animation = anim

        if delay_ms > 0:
            QTimer.singleShot(delay_ms, _start)
        else:
            _start()

    def _on_entrance_finished(self) -> None:
        self._row_animation = None
        effect = self.graphicsEffect()
        if isinstance(effect, QGraphicsOpacityEffect):
            effect.setOpacity(1.0)
            self.setGraphicsEffect(None)

    def set_stain(self, stain: str) -> None:
        value = str(stain or "slate").strip().lower() or "slate"
        self._stain = value
        if str(self.property("stain") or "") == value:
            self._refresh_bubble()
            return
        self.setProperty("stain", value)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()
        self._refresh_bubble()

    def _refresh_bubble(self) -> None:
        item = self._item
        if item is None:
            return
        preview = str(item.body or "").strip().replace("\n", " ")
        if not preview:
            preview = "(no preview)"
        if len(preview) > 200:
            preview = f"{preview[:197].rstrip()}..."
        role = "self" if self._is_self_author(item.author) else "other"
        prefix = "PR" if item.item_type == "pr" else "Issue"
        title = f"{prefix} #{item.number}: {item.title}"
        timestamp = f"by {item.author or 'unknown'} · updated {self._format_time(item.updated_at)}"
        if self._item_type == "pr":
            primary_label = "Review"
            primary_icon = "git-pull-request"
        else:
            primary_label = "Fix"
            primary_icon = "bug"

        self._bubble.set_tone(
            resolve_chat_bubble_tone(
                role=role,
                env_stain=self._stain,
                username=item.author or "unknown",
            )
        )
        self._bubble.set_data(
            ChatBubbleData(
                author=title,
                timestamp=timestamp,
                body=preview,
                role=role,
                actions=(
                    ChatBubbleAction(
                        action_id="reply",
                        label="Reply",
                        icon_name="reply",
                        tooltip="Open thread and focus composer",
                    ),
                    ChatBubbleAction(
                        action_id="primary",
                        label=primary_label,
                        icon_name=primary_icon,
                        tooltip="Generate task prompt",
                    ),
                    ChatBubbleAction(
                        action_id="open",
                        label="Open",
                        icon_name="external-link",
                        tooltip="Open full workroom",
                    ),
                ),
            )
        )

    def set_item(
        self,
        item: GitHubWorkItem,
        *,
        current_login: str,
    ) -> None:
        self._item = item
        self._current_login = str(current_login or "").strip().lower()
        self._refresh_bubble()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        target = self.childAt(event.position().toPoint())
        if event.button() == Qt.LeftButton and not isinstance(target, QToolButton):
            self.clicked.emit(self._item)
        super().mousePressEvent(event)


class _GitHubWorkSkeletonRow(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("TaskRow")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setProperty("stain", "slate")
        self.setFixedHeight(108)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(0)
        self._pulse = BouncingLoadingBar(width=240, height=76, chunk_fraction=0.40)
        self._pulse.set_mode("shimmer_sweep")
        self._pulse.start()
        layout.addWidget(self._pulse, 1)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._pulse.setFixedWidth(max(120, int(self.width()) - 24))

    def set_stain(self, stain: str) -> None:
        value = str(stain or "slate").strip().lower() or "slate"
        if str(self.property("stain") or "") != value:
            self.setProperty("stain", value)
            self.style().unpolish(self)
            self.style().polish(self)
            self.update()
        tint = stain_color(value)
        self._pulse.set_color(tint)

    def stop(self) -> None:
        self._pulse.stop()


class GitHubWorkListPage(QWidget):
    environment_changed = Signal(str)
    prompt_append_requested = Signal(str, str)

    def __init__(
        self,
        *,
        item_type: str,
        coordinator: object,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        normalized = str(item_type or "").strip().lower()
        self._item_type = "pr" if normalized == "pr" else "issue"
        self._coordinator = coordinator

        self._environments: dict[str, Environment] = {}
        self._active_env_id = ""
        self._pane_active = False
        self._prefer_browser = False
        self._confirmation_mode = "always"
        self._active_stain = ""
        self._last_fetch_issue = ""
        self._current_login = (
            str(get_authenticated_github_login() or "").strip().lower()
        )

        self._rows: dict[int, _GitHubWorkRow] = {}
        self._skeleton_rows: list[_GitHubWorkSkeletonRow] = []
        self._initial_load_seen_keys: set[str] = set()
        self._render_items: list[GitHubWorkItem] = []
        self._render_index = 0
        self._render_batch_size = 12

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        self._refresh = QToolButton()
        self._refresh.setIcon(lucide_icon("refresh-cw"))
        self._refresh.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self._refresh.setToolTip("Refresh")
        self._refresh.clicked.connect(self.refresh)

        card = QWidget()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 12, 0, 12)
        card_layout.setSpacing(8)

        columns = QWidget()
        columns_layout = QHBoxLayout(columns)
        columns_layout.setContentsMargins(12, 0, 12, 0)
        columns_layout.setSpacing(12)

        c1 = QLabel("Item")
        c1.setStyleSheet("color: rgba(237, 239, 245, 150); font-weight: 650;")
        c1.setMinimumWidth(260)
        c3 = QLabel("Thread")
        c3.setStyleSheet("color: rgba(237, 239, 245, 150); font-weight: 650;")
        self._column_labels = (c1, c3)

        columns_layout.addWidget(c1, 6)
        columns_layout.addWidget(c3, 5)
        columns_layout.addWidget(self._refresh, 0, Qt.AlignRight)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QScrollArea.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setObjectName("TaskScroll")

        self._list = QWidget()
        self._list.setObjectName("TaskList")
        self._list_layout = QVBoxLayout(self._list)
        self._list_layout.setContentsMargins(12, 8, 12, 8)
        self._list_layout.setSpacing(6)
        self._list_layout.addStretch(1)
        self._scroll.setWidget(self._list)
        self._scroll.verticalScrollBar().valueChanged.connect(
            self._on_scroll_value_changed
        )

        card_layout.addWidget(columns)
        card_layout.addWidget(self._scroll, 1)
        root.addWidget(card, 1)

        self._coordinator.cache_updated.connect(self._on_cache_updated)
        self._apply_environment_tints("")

    def set_settings_data(self, settings_data: dict[str, object]) -> None:
        settings = dict(settings_data or {})
        self._prefer_browser = bool(
            settings.get("github_workroom_prefer_browser") or False
        )
        self._confirmation_mode = (
            str(settings.get("github_write_confirmation_mode") or "always")
            .strip()
            .lower()
        )
        self._sync_refresh_visibility()

    def set_polling_enabled(self, enabled: bool) -> None:
        self.set_pane_active(enabled)

    def set_pane_active(self, active: bool) -> None:
        self._pane_active = bool(active)
        if self._pane_active:
            self._sync_from_cache(show_loading_if_missing=True)

    def set_environments(self, envs: dict[str, Environment], active_id: str) -> None:
        self._environments = dict(envs or {})
        desired = str(active_id or "").strip()

        if desired and desired not in self._environments:
            desired = ""
        if not desired and self._environments:
            ordered = sorted(
                self._environments.values(),
                key=lambda e: (str(e.name or e.env_id).lower(), str(e.env_id).lower()),
            )
            if ordered:
                desired = str(ordered[0].env_id or "").strip()

        self._active_env_id = desired
        self._sync_environment_stain()
        self._sync_refresh_visibility()
        self._sync_from_cache(show_loading_if_missing=self._pane_active)

    def set_active_environment_id(self, env_id: str) -> None:
        desired = str(env_id or "").strip()
        if not desired:
            return
        if desired not in self._environments:
            return
        if desired == self._active_env_id:
            return
        self._active_env_id = desired
        self._sync_environment_stain()
        self._sync_refresh_visibility()
        self._sync_from_cache(show_loading_if_missing=self._pane_active)

    def set_environment_stain(self, stain: str) -> None:
        normalized = str(stain or "").strip().lower()
        if normalized == self._active_stain:
            return
        self._active_stain = normalized
        self._apply_environment_tints(normalized)

    def refresh(self) -> None:
        env_id = str(self._active_env_id or "").strip()
        if not env_id:
            self._clear_rows()
            self._last_fetch_issue = ""
            return

        load_key = self._first_load_key(env_id)
        entry = self._coordinator.get_cache_entry(
            item_type=self._item_type, env_id=env_id
        )
        if entry is None and load_key not in self._initial_load_seen_keys:
            self._initial_load_seen_keys.add(load_key)
            self._render_loading_rows(stain=self._current_stain())

        self._coordinator.request_refresh(
            item_type=self._item_type,
            env_id=env_id,
            force=True,
        )

    def _on_cache_updated(self, item_type: str, env_id: str) -> None:
        if str(item_type or "").strip().lower() != self._item_type:
            return
        if str(env_id or "").strip() != str(self._active_env_id or "").strip():
            return
        self._sync_from_cache(show_loading_if_missing=False)

    def _sync_from_cache(self, *, show_loading_if_missing: bool) -> None:
        env_id = str(self._active_env_id or "").strip()
        if not env_id:
            self._clear_rows()
            self._last_fetch_issue = ""
            return

        entry = self._coordinator.get_cache_entry(
            item_type=self._item_type, env_id=env_id
        )
        if entry is None:
            if show_loading_if_missing:
                load_key = self._first_load_key(env_id)
                if load_key not in self._initial_load_seen_keys:
                    self._initial_load_seen_keys.add(load_key)
                    self._render_loading_rows(stain=self._current_stain())
            if self._pane_active:
                self._coordinator.request_refresh(
                    item_type=self._item_type,
                    env_id=env_id,
                    force=True,
                )
            return

        if entry.repo_context is None:
            self._clear_rows()
            self._log_fetch_issue_once(
                (
                    f"[github-{self._item_type}] GitHub is unavailable for "
                    f"environment '{self._active_env_id}'."
                ),
                mode="warn",
            )
            return

        env = self._environments.get(self._active_env_id)
        stain = (
            self._active_stain
            or str(getattr(env, "color", "slate") or "").strip().lower()
        )
        if not stain:
            stain = "slate"

        if entry.error and not entry.items:
            self._clear_rows()
            self._log_fetch_issue_once(
                (
                    f"[github-{self._item_type}] Load failed for environment "
                    f"'{self._active_env_id}': {entry.error}"
                ),
                mode="error",
            )
            return

        self._render_rows(list(entry.items), stain=stain)
        self._last_fetch_issue = ""
        if self._pane_active:
            self._coordinator.request_refresh_if_stale(
                item_type=self._item_type,
                env_id=env_id,
            )

    def _format_time(self, value: str) -> str:
        text = str(value or "").strip()
        if not text:
            return "—"
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            return parsed.strftime("%Y-%m-%d %H:%M")
        except Exception:
            return text

    def _clear_rows(self) -> None:
        while self._list_layout.count() > 1:
            item = self._list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                if isinstance(widget, _GitHubWorkSkeletonRow):
                    widget.stop()
                widget.deleteLater()
        self._rows.clear()
        self._skeleton_rows.clear()
        self._render_items = []
        self._render_index = 0

    def _render_loading_rows(self, *, stain: str) -> None:
        self._clear_rows()
        for _ in range(6):
            row = _GitHubWorkSkeletonRow()
            row.set_stain(stain)
            self._list_layout.insertWidget(self._list_layout.count() - 1, row)
            self._skeleton_rows.append(row)

    def _render_rows(self, items: list[GitHubWorkItem], *, stain: str) -> None:
        self._clear_rows()
        self._render_items = list(items)
        self._render_index = 0
        self._append_next_batch(stain=stain)

    def _append_next_batch(self, *, stain: str) -> None:
        total = len(self._render_items)
        if self._render_index >= total:
            return

        start = self._render_index
        end = min(total, start + self._render_batch_size)
        delay = 0
        for item in self._render_items[start:end]:
            row = _GitHubWorkRow(item_type=self._item_type)
            row.set_stain(stain)
            row.set_item(item, current_login=self._current_login)
            row.clicked.connect(self._open_item)
            row.open_requested.connect(self._open_item)
            row.reply_requested.connect(self._reply_to_item)
            row.primary_requested.connect(self._request_prompt_from_item)
            self._list_layout.insertWidget(self._list_layout.count() - 1, row)
            row.play_entrance(delay_ms=delay)
            delay += 30
            self._rows[item.number] = row

        self._render_index = end

    def _on_scroll_value_changed(self, value: int) -> None:
        _ = value
        if not self._render_items or self._render_index >= len(self._render_items):
            return
        bar = self._scroll.verticalScrollBar()
        if bar.value() + bar.pageStep() >= bar.maximum() - 48:
            self._append_next_batch(stain=self._current_stain())

    def _open_item(self, item: object) -> None:
        if not isinstance(item, GitHubWorkItem):
            return
        self._open_item_dialog(item, focus_comment=False)

    def _reply_to_item(self, item: object) -> None:
        if not isinstance(item, GitHubWorkItem):
            return
        self._open_item_dialog(item, focus_comment=True)

    def _open_item_dialog(self, item: GitHubWorkItem, *, focus_comment: bool) -> None:
        if self._prefer_browser and item.url:
            QDesktopServices.openUrl(QUrl(item.url))
            return

        repo_context = resolve_environment_github_repo(
            self._environments.get(self._active_env_id)
        )
        if repo_context is None:
            return

        dialog = GitHubWorkroomDialog(
            repo_owner=repo_context.repo_owner,
            repo_name=repo_context.repo_name,
            item_type=item.item_type,
            number=item.number,
            item_url=item.url,
            confirmation_mode=self._confirmation_mode,
            environment_stain=self._current_stain(),
            focus_comment=focus_comment,
            parent=self,
        )
        dialog.prompt_requested.connect(
            lambda prompt: self.prompt_append_requested.emit(
                self._active_env_id, prompt
            )
        )
        dialog.exec()

    def _request_prompt_from_item(self, item: object) -> None:
        if not isinstance(item, GitHubWorkItem):
            return

        repo_context = resolve_environment_github_repo(
            self._environments.get(self._active_env_id)
        )
        repo_owner = str(getattr(repo_context, "repo_owner", "") or "")
        repo_name = str(getattr(repo_context, "repo_name", "") or "")

        prompt = self._build_task_prompt(
            item_type=item.item_type,
            repo_owner=repo_owner,
            repo_name=repo_name,
            number=item.number,
            url=item.url,
            title=item.title,
            trigger_source="manual",
            mention_comment_id=0,
        )

        if not prompt:
            return

        self.prompt_append_requested.emit(self._active_env_id, prompt)

    def _build_task_prompt(
        self,
        *,
        item_type: str,
        repo_owner: str,
        repo_name: str,
        number: int,
        url: str,
        title: str,
        trigger_source: str,
        mention_comment_id: int,
    ) -> str:
        normalized_item_type = str(item_type or "").strip().lower()
        try:
            parsed_mention_comment_id = int(mention_comment_id)
        except Exception:
            parsed_mention_comment_id = 0
        mention_id = (
            str(parsed_mention_comment_id) if parsed_mention_comment_id > 0 else ""
        )
        source = str(trigger_source or "").strip().lower() or "manual"

        if normalized_item_type == "pr":
            return load_prompt(
                "pr_review_template",
                REPO_OWNER=repo_owner,
                REPO_NAME=repo_name,
                PR_NUMBER=number,
                PR_URL=url,
                PR_TITLE=title,
                MENTION_COMMENT_ID=mention_id,
                TRIGGER_SOURCE=source,
            ).strip()

        return load_prompt(
            "issue_fix_template",
            REPO_OWNER=repo_owner,
            REPO_NAME=repo_name,
            ISSUE_NUMBER=number,
            ISSUE_URL=url,
            ISSUE_TITLE=title,
            MENTION_COMMENT_ID=mention_id,
            TRIGGER_SOURCE=source,
        ).strip()

    def _sync_refresh_visibility(self) -> None:
        hide_refresh = self._coordinator.is_polling_effective_for_env(
            str(self._active_env_id or "").strip()
        )
        self._refresh.setVisible(not hide_refresh)

    def _current_stain(self) -> str:
        env = self._environments.get(self._active_env_id)
        stain = (
            self._active_stain or str(getattr(env, "color", "") or "").strip().lower()
        )
        if not stain:
            return "slate"
        return stain

    def _first_load_key(self, env_id: str) -> str:
        normalized_env_id = str(env_id or "").strip().lower()
        return f"{self._item_type}:{normalized_env_id}"

    def _sync_environment_stain(self) -> None:
        env = self._environments.get(self._active_env_id)
        stain = str(getattr(env, "color", "") or "").strip().lower()
        self.set_environment_stain(stain)

    def _apply_environment_tints(self, stain: str) -> None:
        stain = str(stain or "").strip().lower()
        if not stain:
            self._refresh.setStyleSheet("")
            self._list.setStyleSheet("")
            return

        tint = stain_color(stain)
        r = int(tint.red())
        g = int(tint.green())
        b = int(tint.blue())

        self._refresh.setStyleSheet(
            "\n".join(
                [
                    "QToolButton {",
                    f"  background-color: rgba({r}, {g}, {b}, 28);",
                    f"  border: 1px solid rgba({r}, {g}, {b}, 110);",
                    "  border-radius: 0px;",
                    "}",
                    "QToolButton:hover {",
                    f"  background-color: rgba({r}, {g}, {b}, 42);",
                    f"  border: 1px solid rgba({r}, {g}, {b}, 150);",
                    "}",
                    "QToolButton:pressed {",
                    f"  background-color: rgba({r}, {g}, {b}, 68);",
                    f"  border: 1px solid rgba({r}, {g}, {b}, 176);",
                    "}",
                ]
            )
        )
        self._list.setStyleSheet("")
        for row in self._rows.values():
            row.set_stain(stain)
        for row in self._skeleton_rows:
            row.set_stain(stain)

    def _log_fetch_issue_once(self, message: str, *, mode: str) -> None:
        text = str(message or "").strip()
        if not text or text == self._last_fetch_issue:
            return
        self._last_fetch_issue = text
        logger.rprint(text, mode=mode)
