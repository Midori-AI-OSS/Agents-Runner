from __future__ import annotations

import threading

from datetime import datetime

from PySide6.QtCore import QEasingCurve
from PySide6.QtCore import QParallelAnimationGroup
from PySide6.QtCore import QPoint
from PySide6.QtCore import QPropertyAnimation
from PySide6.QtCore import Qt
from PySide6.QtCore import QUrl
from PySide6.QtCore import QTimer
from PySide6.QtCore import Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtGui import QEnterEvent
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QHBoxLayout
from PySide6.QtWidgets import QGraphicsOpacityEffect
from PySide6.QtWidgets import QLabel
from PySide6.QtWidgets import QScrollArea
from PySide6.QtWidgets import QSizePolicy
from PySide6.QtWidgets import QToolButton
from PySide6.QtWidgets import QVBoxLayout
from PySide6.QtWidgets import QWidget

from agents_runner.environments import Environment
from agents_runner.environments import resolve_environment_github_repo
from agents_runner.gh.work_items import GitHubWorkItem
from agents_runner.gh.work_items import add_issue_comment_reaction
from agents_runner.gh.work_items import list_issue_comments
from agents_runner.gh.work_items import list_open_issues
from agents_runner.gh.work_items import list_open_pull_requests
from agents_runner.prompts import load_prompt
from agents_runner.ui.dialogs.github_workroom_dialog import GitHubWorkroomDialog
from agents_runner.ui.lucide_icons import lucide_icon
from agents_runner.ui.utils import _stain_color
from agents_runner.ui.widgets import BouncingLoadingBar
from midori_ai_logger import MidoriAiLogger

logger = MidoriAiLogger(channel=None, name=__name__)


class _GitHubWorkRow(QWidget):
    _ACTION_PANEL_HIDDEN_OFFSET = 14
    _ACTION_PANEL_WIDTH = 86

    clicked = Signal(object)
    primary_requested = Signal(object)
    open_requested = Signal(object)

    def __init__(self, *, item_type: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._item = None
        self._item_type = str(item_type or "issue").strip().lower()

        self.setObjectName("TaskRow")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setProperty("stain", "slate")
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(56)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)

        self._title = QLabel("—")
        self._title.setStyleSheet("font-weight: 650; color: rgba(237, 239, 245, 235);")
        self._title.setMinimumWidth(260)

        self._meta = QLabel("—")
        self._meta.setStyleSheet("color: rgba(237, 239, 245, 160);")

        self._actions_host = QWidget(self)
        self._actions_host.setFixedWidth(self._ACTION_PANEL_WIDTH)
        self._actions_host.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        self._actions_panel = QWidget(self._actions_host)
        actions_layout = QHBoxLayout(self._actions_panel)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(8)

        self._btn_primary = QToolButton()
        self._btn_primary.setObjectName("RowTrash")
        self._btn_primary.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self._btn_primary.clicked.connect(
            lambda: self.primary_requested.emit(self._item)
        )

        self._btn_open = QToolButton()
        self._btn_open.setObjectName("RowTrash")
        self._btn_open.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self._btn_open.clicked.connect(lambda: self.open_requested.emit(self._item))

        actions_layout.addWidget(self._btn_primary, 0, Qt.AlignRight)
        actions_layout.addWidget(self._btn_open, 0, Qt.AlignRight)

        layout.addWidget(self._title, 6)
        layout.addWidget(self._meta, 5)
        layout.addWidget(self._actions_host, 0)

        self._actions_animation: QParallelAnimationGroup | None = None
        self._actions_visible = False
        self._configure_actions()
        self._set_actions_visible(False, animate=False)

    def _configure_actions(self) -> None:
        if self._item_type == "pr":
            self._btn_primary.setIcon(lucide_icon("git-pull-request"))
            self._btn_primary.setToolTip("Review PR")
        else:
            self._btn_primary.setIcon(lucide_icon("bug"))
            self._btn_primary.setToolTip("Fix Issue")

        self._btn_open.setIcon(lucide_icon("eye"))
        self._btn_open.setToolTip("Open workroom")

    def _actions_opacity_effect(self) -> QGraphicsOpacityEffect:
        effect = self._actions_panel.graphicsEffect()
        if isinstance(effect, QGraphicsOpacityEffect):
            return effect
        effect = QGraphicsOpacityEffect(self._actions_panel)
        effect.setOpacity(1.0 if self._actions_visible else 0.0)
        self._actions_panel.setGraphicsEffect(effect)
        return effect

    def _layout_actions_panel(self) -> None:
        panel_width = int(self._actions_host.width())
        panel_height = int(self._actions_host.height())
        self._actions_panel.resize(panel_width, panel_height)
        x = 0 if self._actions_visible else self._ACTION_PANEL_HIDDEN_OFFSET
        self._actions_panel.move(x, 0)

    def _set_actions_visible(self, visible: bool, *, animate: bool = True) -> None:
        target_visible = bool(visible)
        self._actions_visible = target_visible

        if self._actions_animation is not None:
            self._actions_animation.stop()
            self._actions_animation = None

        effect = self._actions_opacity_effect()
        target_x = 0 if target_visible else self._ACTION_PANEL_HIDDEN_OFFSET
        target_opacity = 1.0 if target_visible else 0.0

        self._actions_panel.setAttribute(
            Qt.WA_TransparentForMouseEvents, not target_visible
        )

        if not animate:
            current_y = int(self._actions_panel.pos().y())
            self._actions_panel.move(target_x, current_y)
            effect.setOpacity(target_opacity)
            return

        start_pos = QPoint(
            int(self._actions_panel.pos().x()), int(self._actions_panel.pos().y())
        )
        end_pos = QPoint(target_x, int(self._actions_panel.pos().y()))
        start_opacity = float(effect.opacity())

        pos_anim = QPropertyAnimation(self._actions_panel, b"pos", self)
        pos_anim.setDuration(180)
        pos_anim.setStartValue(start_pos)
        pos_anim.setEndValue(end_pos)
        pos_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)

        opacity_anim = QPropertyAnimation(effect, b"opacity", self)
        opacity_anim.setDuration(180)
        opacity_anim.setStartValue(start_opacity)
        opacity_anim.setEndValue(target_opacity)
        opacity_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)

        group = QParallelAnimationGroup(self)
        group.addAnimation(pos_anim)
        group.addAnimation(opacity_anim)

        def _on_finished() -> None:
            self._actions_animation = None
            if not self._actions_visible:
                self._actions_panel.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        group.finished.connect(_on_finished)
        group.start()
        self._actions_animation = group

    def set_stain(self, stain: str) -> None:
        value = str(stain or "slate").strip().lower() or "slate"
        if str(self.property("stain") or "") == value:
            return
        self.setProperty("stain", value)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def set_item(self, item: GitHubWorkItem, *, meta_text: str) -> None:
        self._item = item
        prefix = "PR" if item.item_type == "pr" else "Issue"
        self._title.setText(f"{prefix} #{item.number}: {item.title}")

        self._meta.setText(meta_text)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self._item)
        super().mousePressEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._layout_actions_panel()

    def enterEvent(self, event: QEnterEvent) -> None:
        self._set_actions_visible(True, animate=True)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._set_actions_visible(False, animate=True)
        super().leaveEvent(event)


class _GitHubWorkSkeletonRow(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("TaskRow")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setProperty("stain", "slate")
        self.setFixedHeight(56)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(0)
        self._pulse = BouncingLoadingBar(width=240, height=40, chunk_fraction=0.40)
        self._pulse.set_mode("shimmer_sweep")
        self._pulse.start()
        layout.addWidget(self._pulse, 1)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._pulse.setFixedWidth(max(120, int(self.width()) - 24))

    def set_stain(self, stain: str) -> None:
        value = str(stain or "slate").strip().lower() or "slate"
        if str(self.property("stain") or "") != value:
            self.setProperty("stain", value)
            self.style().unpolish(self)
            self.style().polish(self)
            self.update()
        tint = _stain_color(value)
        self._pulse.set_color(tint)

    def stop(self) -> None:
        self._pulse.stop()


class GitHubWorkListPage(QWidget):
    environment_changed = Signal(str)
    prompt_append_requested = Signal(str, str)
    auto_review_requested = Signal(str, str)

    _fetch_completed = Signal(int, object, str, object, object)

    def __init__(self, *, item_type: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        normalized = str(item_type or "").strip().lower()
        self._item_type = "pr" if normalized == "pr" else "issue"

        self._environments: dict[str, Environment] = {}
        self._active_env_id = ""
        self._fetch_seq = 0
        self._polling_enabled = False
        self._prefer_browser = False
        self._confirmation_mode = "always"
        self._auto_review_enabled = True
        self._poll_interval_s = 30
        self._auto_review_seen_comment_ids: set[int] = set()
        self._auto_review_seen_item_mentions: set[str] = set()
        self._active_stain = ""
        self._last_fetch_issue = ""

        self._rows: dict[int, _GitHubWorkRow] = {}
        self._skeleton_rows: list[_GitHubWorkSkeletonRow] = []
        self._initial_load_seen_keys: set[str] = set()

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
        c3 = QLabel("Info")
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

        card_layout.addWidget(columns)
        card_layout.addWidget(self._scroll, 1)
        root.addWidget(card, 1)

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(max(5, int(self._poll_interval_s)) * 1000)
        self._poll_timer.timeout.connect(self.refresh)

        self._fetch_completed.connect(self._on_fetch_completed)
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
        self._auto_review_enabled = bool(
            settings.get("agentsnova_auto_review_enabled", True)
        )

        try:
            interval = int(settings.get("github_poll_interval_s", 30))
        except Exception:
            interval = 30
        self._poll_interval_s = max(5, interval)
        self._poll_timer.setInterval(self._poll_interval_s * 1000)

    def set_polling_enabled(self, enabled: bool) -> None:
        self._polling_enabled = bool(enabled)
        if self._polling_enabled:
            self._poll_timer.start()
            self.refresh()
            return
        self._poll_timer.stop()

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
        self.refresh()

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

        self._fetch_seq += 1
        seq = int(self._fetch_seq)
        load_key = self._first_load_key(env_id)
        if load_key not in self._initial_load_seen_keys:
            self._initial_load_seen_keys.add(load_key)
            self._render_loading_rows(stain=self._current_stain())
        queued_snapshot = set(self._auto_review_seen_comment_ids)
        queued_item_snapshot = set(self._auto_review_seen_item_mentions)
        auto_review_enabled = bool(self._auto_review_enabled)

        worker = threading.Thread(
            target=self._fetch_worker,
            args=(
                seq,
                env_id,
                queued_snapshot,
                queued_item_snapshot,
                auto_review_enabled,
            ),
            daemon=True,
        )
        worker.start()

    def _fetch_worker(
        self,
        seq: int,
        env_id: str,
        queued_snapshot: set[int],
        queued_item_snapshot: set[str],
        auto_review_enabled: bool,
    ) -> None:
        repo_context = None
        items: list[GitHubWorkItem] = []
        auto_reviews: list[dict[str, object]] = []
        error = ""

        try:
            env = self._environments.get(env_id)
            repo_context = resolve_environment_github_repo(env)
            if repo_context is None:
                self._fetch_completed.emit(seq, items, "", None, auto_reviews)
                return

            if self._item_type == "pr":
                items = list_open_pull_requests(
                    repo_context.repo_owner,
                    repo_context.repo_name,
                    limit=30,
                )
            else:
                items = list_open_issues(
                    repo_context.repo_owner,
                    repo_context.repo_name,
                    limit=30,
                )

            if auto_review_enabled:
                auto_reviews = self._collect_auto_reviews(
                    repo_owner=repo_context.repo_owner,
                    repo_name=repo_context.repo_name,
                    items=items,
                    queued_snapshot=queued_snapshot,
                    queued_item_snapshot=queued_item_snapshot,
                )
        except Exception as exc:
            error = str(exc)

        self._fetch_completed.emit(seq, items, error, repo_context, auto_reviews)

    def _collect_auto_reviews(
        self,
        *,
        repo_owner: str,
        repo_name: str,
        items: list[GitHubWorkItem],
        queued_snapshot: set[int],
        queued_item_snapshot: set[str],
    ) -> list[dict[str, object]]:
        results: list[dict[str, object]] = []

        for item in items:
            item_key = self._mention_item_key(
                repo_owner=repo_owner,
                repo_name=repo_name,
                item_type=item.item_type,
                number=item.number,
            )
            queued_for_item = False

            comments = list_issue_comments(
                repo_owner,
                repo_name,
                issue_number=item.number,
                limit=100,
            )
            comments = list(comments)
            comments.reverse()

            for comment in comments:
                body = str(comment.body or "")
                if "@agentsnova" not in body.lower():
                    continue

                if comment.comment_id in queued_snapshot:
                    continue

                reactions = comment.reactions
                if reactions.thumbs_up > 0 or reactions.thumbs_down > 0:
                    continue

                marker = "eyes"
                if item.item_type == "pr":
                    if reactions.eyes > 0:
                        continue
                else:
                    marker = "rocket"
                    if reactions.rocket > 0 or reactions.hooray > 0:
                        continue

                try:
                    add_issue_comment_reaction(
                        repo_owner,
                        repo_name,
                        comment_id=comment.comment_id,
                        reaction=marker,
                    )
                except Exception:
                    continue

                results.append(
                    {
                        "item_type": item.item_type,
                        "number": item.number,
                        "url": item.url,
                        "title": item.title,
                        "mention_comment_id": comment.comment_id,
                        "trigger_source": "comment_mention",
                        "item_key": item_key,
                    }
                )
                queued_for_item = True

                if len(results) >= 3:
                    return results
                break

            if queued_for_item:
                continue

            if item_key in queued_item_snapshot:
                continue

            if self._item_has_agentsnova_mention(item):
                results.append(
                    {
                        "item_type": item.item_type,
                        "number": item.number,
                        "url": item.url,
                        "title": item.title,
                        "mention_comment_id": 0,
                        "trigger_source": "body_mention",
                        "item_key": item_key,
                    }
                )
                queued_item_snapshot.add(item_key)
                if len(results) >= 3:
                    return results

        return results

    def _mention_item_key(
        self,
        *,
        repo_owner: str,
        repo_name: str,
        item_type: str,
        number: int,
    ) -> str:
        try:
            normalized_number = max(0, int(number))
        except Exception:
            normalized_number = 0
        return (
            f"{str(repo_owner or '').strip().lower()}/"
            f"{str(repo_name or '').strip().lower()}:"
            f"{str(item_type or '').strip().lower()}:{normalized_number}"
        )

    def _item_has_agentsnova_mention(self, item: GitHubWorkItem) -> bool:
        body = str(getattr(item, "body", "") or "").strip().lower()
        title = str(getattr(item, "title", "") or "").strip().lower()
        return "@agentsnova" in body or "@agentsnova" in title

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

    def _render_loading_rows(self, *, stain: str) -> None:
        self._clear_rows()
        for _ in range(6):
            row = _GitHubWorkSkeletonRow()
            row.set_stain(stain)
            self._list_layout.insertWidget(self._list_layout.count() - 1, row)
            self._skeleton_rows.append(row)

    def _render_rows(self, items: list[GitHubWorkItem], *, stain: str) -> None:
        self._clear_rows()

        for item in items:
            row = _GitHubWorkRow(item_type=self._item_type)
            row.set_stain(stain)
            row.set_item(
                item,
                meta_text=(
                    f"by {item.author or 'unknown'}  |  updated {self._format_time(item.updated_at)}"
                ),
            )
            row.clicked.connect(self._open_item)
            row.open_requested.connect(self._open_item)
            row.primary_requested.connect(self._request_prompt_from_item)
            self._list_layout.insertWidget(self._list_layout.count() - 1, row)
            self._rows[item.number] = row

    def _open_item(self, item: object) -> None:
        if not isinstance(item, GitHubWorkItem):
            return

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

    def _on_fetch_completed(
        self,
        seq: int,
        items: object,
        error: str,
        repo_context: object,
        auto_reviews: object,
    ) -> None:
        if int(seq) != int(self._fetch_seq):
            return

        if repo_context is None:
            self._clear_rows()
            self._log_fetch_issue_once(
                (
                    f"[github-{self._item_type}] GitHub is unavailable for "
                    f"environment '{self._active_env_id}'."
                ),
                mode="warn",
            )
            return

        rows = [
            item
            for item in (items if isinstance(items, list) else [])
            if isinstance(item, GitHubWorkItem)
        ]
        env = self._environments.get(self._active_env_id)
        stain = (
            self._active_stain
            or str(getattr(env, "color", "slate") or "").strip().lower()
        )
        if not stain:
            stain = "slate"

        if error:
            self._clear_rows()
            self._log_fetch_issue_once(
                (
                    f"[github-{self._item_type}] Load failed for environment "
                    f"'{self._active_env_id}': {error}"
                ),
                mode="error",
            )
            return

        self._render_rows(rows, stain=stain)
        self._last_fetch_issue = ""

        reviews = auto_reviews if isinstance(auto_reviews, list) else []
        repo_owner = str(getattr(repo_context, "repo_owner", "") or "")
        repo_name = str(getattr(repo_context, "repo_name", "") or "")
        for review in reviews:
            if not isinstance(review, dict):
                continue

            item_type = str(review.get("item_type") or self._item_type).strip().lower()
            try:
                number = int(review.get("number") or 0)
            except Exception:
                number = 0
            if number <= 0:
                continue

            trigger_source = str(review.get("trigger_source") or "").strip().lower()
            try:
                mention_comment_id = int(review.get("mention_comment_id") or 0)
            except Exception:
                mention_comment_id = 0

            if (
                mention_comment_id > 0
                and mention_comment_id in self._auto_review_seen_comment_ids
            ):
                continue

            item_key = str(review.get("item_key") or "").strip()
            if not item_key:
                item_key = self._mention_item_key(
                    repo_owner=repo_owner,
                    repo_name=repo_name,
                    item_type=item_type,
                    number=number,
                )
            if (
                trigger_source == "body_mention"
                and item_key in self._auto_review_seen_item_mentions
            ):
                continue

            prompt = self._build_task_prompt(
                item_type=item_type,
                repo_owner=repo_owner,
                repo_name=repo_name,
                number=number,
                url=str(review.get("url") or "").strip(),
                title=str(review.get("title") or "").strip(),
                trigger_source=trigger_source,
                mention_comment_id=mention_comment_id,
            )
            if not prompt:
                continue

            if mention_comment_id > 0:
                self._auto_review_seen_comment_ids.add(mention_comment_id)
            if trigger_source == "body_mention":
                self._auto_review_seen_item_mentions.add(item_key)
            self.auto_review_requested.emit(self._active_env_id, prompt)

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

        tint = _stain_color(stain)
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
