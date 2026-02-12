from __future__ import annotations

import threading

from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtCore import QTimer
from PySide6.QtCore import Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtGui import QEnterEvent
from PySide6.QtGui import QMouseEvent
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QComboBox
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
from agents_runner.gh.work_items import add_issue_comment_reaction
from agents_runner.gh.work_items import list_issue_comments
from agents_runner.gh.work_items import list_open_issues
from agents_runner.gh.work_items import list_open_pull_requests
from agents_runner.prompts import load_prompt
from agents_runner.ui.dialogs.github_workroom_dialog import GitHubWorkroomDialog
from agents_runner.ui.lucide_icons import lucide_icon
from agents_runner.ui.widgets import GlassCard


class _GitHubWorkRow(QWidget):
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

        self._state = QLabel("—")
        self._state.setStyleSheet("color: rgba(237, 239, 245, 190); font-weight: 700;")
        self._state.setMinimumWidth(110)

        self._meta = QLabel("—")
        self._meta.setStyleSheet("color: rgba(237, 239, 245, 160);")

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

        layout.addWidget(self._title, 5)
        layout.addWidget(self._state, 0)
        layout.addWidget(self._meta, 4)
        layout.addWidget(self._btn_primary, 0)
        layout.addWidget(self._btn_open, 0)

        self._configure_actions()
        self._set_actions_visible(False)

    def _configure_actions(self) -> None:
        if self._item_type == "pr":
            self._btn_primary.setIcon(lucide_icon("git-pull-request"))
            self._btn_primary.setToolTip("Review PR")
        else:
            self._btn_primary.setIcon(lucide_icon("bug"))
            self._btn_primary.setToolTip("Fix Issue")

        self._btn_open.setIcon(lucide_icon("eye"))
        self._btn_open.setToolTip("Open workroom")

    def _set_actions_visible(self, visible: bool) -> None:
        self._btn_primary.setVisible(bool(visible))
        self._btn_open.setVisible(bool(visible))

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

        state = str(item.state or "").strip().lower()
        if item.item_type == "pr" and item.is_draft and state == "open":
            self._state.setText("Draft")
        else:
            self._state.setText(state.title() if state else "—")

        self._meta.setText(meta_text)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self._item)
        super().mousePressEvent(event)

    def enterEvent(self, event: QEnterEvent) -> None:
        self._set_actions_visible(True)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._set_actions_visible(False)
        super().leaveEvent(event)


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

        self._rows: dict[int, _GitHubWorkRow] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(14)

        header = GlassCard()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 14, 16, 14)
        header_layout.setSpacing(10)

        title = "Pull Requests" if self._item_type == "pr" else "Issues"
        self._title = QLabel(title)
        self._title.setStyleSheet("font-size: 16px; font-weight: 750;")

        self._environment = QComboBox()
        self._environment.setFixedWidth(260)
        self._environment.currentIndexChanged.connect(self._on_environment_changed)

        self._refresh = QToolButton()
        self._refresh.setText("Refresh")
        self._refresh.setIcon(lucide_icon("refresh-cw"))
        self._refresh.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self._refresh.clicked.connect(self.refresh)

        header_layout.addWidget(self._title)
        header_layout.addStretch(1)
        header_layout.addWidget(self._environment)
        header_layout.addWidget(self._refresh)
        root.addWidget(header)

        card = GlassCard()
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
        c2 = QLabel("State")
        c2.setStyleSheet("color: rgba(237, 239, 245, 150); font-weight: 650;")
        c2.setMinimumWidth(110)
        c3 = QLabel("Info")
        c3.setStyleSheet("color: rgba(237, 239, 245, 150); font-weight: 650;")

        columns_layout.addWidget(c1, 5)
        columns_layout.addWidget(c2, 0)
        columns_layout.addWidget(c3, 4)

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

        self._status = QLabel("Select an environment to load data.")
        self._status.setStyleSheet("color: rgba(237, 239, 245, 160);")

        card_layout.addWidget(columns)
        card_layout.addWidget(self._scroll, 1)
        card_layout.addWidget(self._status)
        root.addWidget(card, 1)

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(max(5, int(self._poll_interval_s)) * 1000)
        self._poll_timer.timeout.connect(self.refresh)

        self._fetch_completed.connect(self._on_fetch_completed)

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

        self._environment.blockSignals(True)
        try:
            self._environment.clear()
            ordered = sorted(
                self._environments.values(),
                key=lambda e: (str(e.name or e.env_id).lower(), str(e.env_id).lower()),
            )
            for env in ordered:
                self._environment.addItem(env.name or env.env_id, env.env_id)

            idx = self._environment.findData(desired)
            if idx < 0 and self._environment.count() > 0:
                idx = 0
            if idx >= 0:
                self._environment.setCurrentIndex(idx)
        finally:
            self._environment.blockSignals(False)

        if self._environment.count() > 0:
            self._active_env_id = str(self._environment.currentData() or "")

    def set_active_environment_id(self, env_id: str) -> None:
        desired = str(env_id or "").strip()
        if not desired:
            return
        idx = self._environment.findData(desired)
        if idx >= 0 and self._environment.currentIndex() != idx:
            self._environment.setCurrentIndex(idx)
            return
        self._active_env_id = desired

    def _on_environment_changed(self, _index: int) -> None:
        self._active_env_id = str(self._environment.currentData() or "")
        self.environment_changed.emit(self._active_env_id)
        self.refresh()

    def refresh(self) -> None:
        env_id = str(
            self._active_env_id or self._environment.currentData() or ""
        ).strip()
        if not env_id:
            self._status.setText("Select an environment to load data.")
            self._clear_rows()
            return

        self._fetch_seq += 1
        seq = int(self._fetch_seq)
        queued_snapshot = set(self._auto_review_seen_comment_ids)
        auto_review_enabled = bool(
            self._auto_review_enabled and self._item_type == "pr"
        )

        self._status.setText("Loading...")

        worker = threading.Thread(
            target=self._fetch_worker,
            args=(seq, env_id, queued_snapshot, auto_review_enabled),
            daemon=True,
        )
        worker.start()

    def _fetch_worker(
        self,
        seq: int,
        env_id: str,
        queued_snapshot: set[int],
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
    ) -> list[dict[str, object]]:
        results: list[dict[str, object]] = []

        for item in items:
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
                if reactions.eyes > 0:
                    continue

                try:
                    add_issue_comment_reaction(
                        repo_owner,
                        repo_name,
                        comment_id=comment.comment_id,
                        reaction="eyes",
                    )
                except Exception:
                    continue

                results.append(
                    {
                        "comment_id": comment.comment_id,
                        "pr_number": item.number,
                        "pr_url": item.url,
                        "pr_title": item.title,
                    }
                )

                if len(results) >= 3:
                    return results
                break

        return results

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
                widget.deleteLater()
        self._rows.clear()

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

        if item.item_type == "pr":
            prompt = load_prompt(
                "pr_review_template",
                REPO_OWNER=repo_owner,
                REPO_NAME=repo_name,
                PR_NUMBER=item.number,
                PR_URL=item.url,
                PR_TITLE=item.title,
                MENTION_COMMENT_ID="",
            ).strip()
        else:
            prompt = load_prompt(
                "issue_fix_template",
                REPO_OWNER=repo_owner,
                REPO_NAME=repo_name,
                ISSUE_NUMBER=item.number,
                ISSUE_URL=item.url,
                ISSUE_TITLE=item.title,
            ).strip()

        if not prompt:
            return

        self.prompt_append_requested.emit(self._active_env_id, prompt)

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
            self._status.setText("GitHub is unavailable for this environment.")
            return

        rows = [
            item
            for item in (items if isinstance(items, list) else [])
            if isinstance(item, GitHubWorkItem)
        ]
        env = self._environments.get(self._active_env_id)
        stain = str(getattr(env, "color", "slate") or "slate").strip().lower()

        if error:
            self._clear_rows()
            self._status.setText(f"Load failed: {error}")
            return

        self._render_rows(rows, stain=stain)
        kind = "pull request" if self._item_type == "pr" else "issue"
        if rows:
            self._status.setText(f"Loaded {len(rows)} open {kind}(s).")
        else:
            self._status.setText(f"No open {kind}s found.")

        reviews = auto_reviews if isinstance(auto_reviews, list) else []
        for review in reviews:
            if not isinstance(review, dict):
                continue

            comment_id = int(review.get("comment_id") or 0)
            if comment_id <= 0 or comment_id in self._auto_review_seen_comment_ids:
                continue

            pr_number = int(review.get("pr_number") or 0)
            pr_url = str(review.get("pr_url") or "").strip()
            pr_title = str(review.get("pr_title") or "").strip()

            prompt = load_prompt(
                "pr_review_template",
                REPO_OWNER=str(getattr(repo_context, "repo_owner", "") or ""),
                REPO_NAME=str(getattr(repo_context, "repo_name", "") or ""),
                PR_NUMBER=pr_number,
                PR_URL=pr_url,
                PR_TITLE=pr_title,
                MENTION_COMMENT_ID=comment_id,
            ).strip()
            if not prompt:
                continue

            self._auto_review_seen_comment_ids.add(comment_id)
            self.auto_review_requested.emit(self._active_env_id, prompt)
