from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtCore import QTimer
from PySide6.QtCore import QUrl
from PySide6.QtCore import Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication
from PySide6.QtWidgets import QHBoxLayout
from PySide6.QtWidgets import QLabel
from PySide6.QtWidgets import QLineEdit
from PySide6.QtWidgets import QMessageBox
from PySide6.QtWidgets import QScrollArea
from PySide6.QtWidgets import QToolButton
from PySide6.QtWidgets import QVBoxLayout
from PySide6.QtWidgets import QWidget

from agents_runner.gh.work_items import GitHubWorkroom
from agents_runner.gh.work_items import get_authenticated_github_login
from agents_runner.gh.work_items import get_issue_workroom
from agents_runner.gh.work_items import get_pull_request_workroom
from agents_runner.gh.work_items import post_comment
from agents_runner.gh.work_items import set_item_open_state
from agents_runner.prompts import load_prompt
from agents_runner.ui.dialogs.themed_dialog import ThemedDialog
from agents_runner.ui.lucide_icons import lucide_icon
from agents_runner.ui.utils import resolve_chat_bubble_tone
from agents_runner.ui.widgets import ChatBubbleAction
from agents_runner.ui.widgets import ChatBubbleData
from agents_runner.ui.widgets import ChatBubbleWidget
from agents_runner.ui.widgets import GlassCard


class GitHubWorkroomDialog(ThemedDialog):
    prompt_requested = Signal(str)

    def __init__(
        self,
        *,
        repo_owner: str,
        repo_name: str,
        item_type: str,
        number: int,
        item_url: str = "",
        confirmation_mode: str,
        environment_stain: str = "",
        focus_comment: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._repo_owner = str(repo_owner or "").strip()
        self._repo_name = str(repo_name or "").strip()
        self._item_type = str(item_type or "").strip().lower()
        self._number = max(1, int(number))
        self._item_url = str(item_url or "").strip()
        self._confirmation_mode = str(confirmation_mode or "always").strip().lower()
        self._environment_stain = str(environment_stain or "").strip().lower()
        self._focus_comment_on_show = bool(focus_comment)
        self._current_login = (
            str(get_authenticated_github_login() or "").strip().lower()
        )
        self._room: GitHubWorkroom | None = None

        self.setWindowTitle("GitHub Workroom")
        self.setMinimumSize(860, 620)

        layout = self.content_layout()
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        header = GlassCard()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 14, 16, 14)
        header_layout.setSpacing(10)

        self._title = QLabel("Loading...")
        self._title.setStyleSheet("font-size: 16px; font-weight: 750;")
        self._subtitle = QLabel("—")
        self._subtitle.setStyleSheet("color: rgba(237, 239, 245, 160);")

        self._btn_primary = QToolButton()
        self._btn_primary.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self._btn_primary.clicked.connect(self._on_primary)

        self._btn_toggle_state = QToolButton()
        self._btn_toggle_state.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self._btn_toggle_state.clicked.connect(self._on_toggle_open_state)

        self._btn_refresh = QToolButton()
        self._btn_refresh.setText("Refresh")
        self._btn_refresh.setIcon(lucide_icon("refresh-cw"))
        self._btn_refresh.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self._btn_refresh.clicked.connect(self.refresh)

        self._btn_browser = QToolButton()
        self._btn_browser.setText("Browser")
        self._btn_browser.setIcon(lucide_icon("external-link"))
        self._btn_browser.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self._btn_browser.clicked.connect(self._open_in_browser)

        header_layout.addWidget(self._title)
        header_layout.addWidget(self._subtitle, 1)
        header_layout.addWidget(self._btn_primary)
        header_layout.addWidget(self._btn_toggle_state)
        header_layout.addWidget(self._btn_refresh)
        header_layout.addWidget(self._btn_browser)
        layout.addWidget(header)

        timeline_card = GlassCard()
        timeline_layout = QVBoxLayout(timeline_card)
        timeline_layout.setContentsMargins(16, 14, 16, 14)
        timeline_layout.setSpacing(8)

        timeline_title = QLabel("Timeline")
        timeline_title.setStyleSheet("font-size: 13px; font-weight: 700;")

        self._timeline_scroll = QScrollArea()
        self._timeline_scroll.setWidgetResizable(True)
        self._timeline_scroll.setFrameShape(QScrollArea.NoFrame)
        self._timeline_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._timeline_scroll.setObjectName("TaskScroll")

        self._timeline_list = QWidget()
        self._timeline_layout = QVBoxLayout(self._timeline_list)
        self._timeline_layout.setContentsMargins(4, 4, 4, 4)
        self._timeline_layout.setSpacing(8)
        self._timeline_layout.addStretch(1)
        self._timeline_scroll.setWidget(self._timeline_list)

        timeline_layout.addWidget(timeline_title)
        timeline_layout.addWidget(self._timeline_scroll, 1)
        layout.addWidget(timeline_card, 1)

        composer = GlassCard()
        composer_layout = QVBoxLayout(composer)
        composer_layout.setContentsMargins(16, 14, 16, 14)
        composer_layout.setSpacing(8)

        composer_title = QLabel("Comment")
        composer_title.setStyleSheet("font-size: 13px; font-weight: 700;")

        row = QHBoxLayout()
        row.setSpacing(8)

        self._comment = QLineEdit()
        self._comment.setPlaceholderText("Write a comment...")

        self._btn_send = QToolButton()
        self._btn_send.setText("Comment")
        self._btn_send.setIcon(lucide_icon("file-pen-line"))
        self._btn_send.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self._btn_send.clicked.connect(self._on_send_comment)

        row.addWidget(self._comment, 1)
        row.addWidget(self._btn_send)

        self._status = QLabel("Loading...")
        self._status.setStyleSheet("color: rgba(237, 239, 245, 160);")

        composer_layout.addWidget(composer_title)
        composer_layout.addLayout(row)
        composer_layout.addWidget(self._status)

        layout.addWidget(composer)

        self._sync_primary_button()
        self._sync_open_state_button("open")
        self.refresh()

    def _normalize_user(self, username: str) -> str:
        return str(username or "").strip().lower().lstrip("@")

    def _is_self_author(self, username: str) -> bool:
        if not self._current_login:
            return False
        return self._normalize_user(username) == self._current_login

    def _clear_timeline(self) -> None:
        while self._timeline_layout.count() > 1:
            item = self._timeline_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _add_timeline_bubble(self, bubble: ChatBubbleWidget) -> None:
        index = max(0, self._timeline_layout.count() - 1)
        self._timeline_layout.insertWidget(index, bubble)

    def _focus_comment_composer(self) -> None:
        self._comment.setFocus(Qt.OtherFocusReason)
        self._comment.setCursorPosition(len(str(self._comment.text() or "")))

    def _scroll_timeline_to_bottom(self) -> None:
        bar = self._timeline_scroll.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _sync_primary_button(self) -> None:
        if self._item_type == "pr":
            self._btn_primary.setText("Review PR")
            self._btn_primary.setIcon(lucide_icon("git-pull-request"))
            self._btn_primary.setToolTip(
                "Create a review task prompt from this pull request"
            )
            return

        self._btn_primary.setText("Fix Issue")
        self._btn_primary.setIcon(lucide_icon("bug"))
        self._btn_primary.setToolTip("Create a fix task prompt from this issue")

    def _sync_open_state_button(self, state: str) -> None:
        normalized = str(state or "").strip().lower()
        if normalized == "open":
            self._btn_toggle_state.setText("Close")
            self._btn_toggle_state.setIcon(lucide_icon("square"))
            self._btn_toggle_state.setToolTip("Close this item")
            return

        self._btn_toggle_state.setText("Reopen")
        self._btn_toggle_state.setIcon(lucide_icon("play"))
        self._btn_toggle_state.setToolTip("Reopen this item")

    def _format_time(self, value: str) -> str:
        text = str(value or "").strip()
        if not text:
            return "—"
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            return parsed.strftime("%Y-%m-%d %H:%M")
        except Exception:
            return text

    def _render_room(self) -> None:
        room = self._room
        if room is None:
            return

        kind = "PR" if room.item_type == "pr" else "Issue"
        draft_suffix = " (draft)" if room.is_draft else ""
        self._title.setText(f"{kind} #{room.number}: {room.title}{draft_suffix}")
        self._subtitle.setText(
            f"{room.repo_owner}/{room.repo_name}  |  by {room.author or 'unknown'}  |  {self._format_time(room.updated_at)}"
        )
        self._sync_open_state_button(room.state)

        self._clear_timeline()

        issue_role = "self" if self._is_self_author(room.author) else "other"
        issue_actions = (
            ChatBubbleAction(
                action_id="reply",
                label="Reply",
                icon_name="reply",
                tooltip="Focus comment composer",
            ),
            ChatBubbleAction(
                action_id="open",
                label="Open",
                icon_name="external-link",
                tooltip="Open in browser",
            ),
            ChatBubbleAction(
                action_id="primary",
                label="Review PR" if room.item_type == "pr" else "Fix Issue",
                icon_name="git-pull-request" if room.item_type == "pr" else "bug",
                tooltip="Create task prompt",
            ),
        )
        issue_body = room.body or "(empty description)"
        issue_bubble = ChatBubbleWidget()
        issue_bubble.set_tone(
            resolve_chat_bubble_tone(
                role=issue_role,
                env_stain=self._environment_stain,
                username=room.author or "unknown",
            )
        )
        issue_bubble.set_data(
            ChatBubbleData(
                author=f"{kind} #{room.number} · {room.author or 'unknown'}",
                timestamp=f"{self._format_time(room.created_at)} · {room.state}",
                body=issue_body,
                role=issue_role,
                actions=issue_actions,
            )
        )
        issue_bubble.reply_requested.connect(self._focus_comment_composer)
        issue_bubble.open_requested.connect(self._open_in_browser)
        issue_bubble.primary_requested.connect(self._on_primary)
        self._add_timeline_bubble(issue_bubble)

        if not room.comments:
            note = ChatBubbleWidget()
            note.set_tone(
                resolve_chat_bubble_tone(
                    role="other",
                    env_stain=self._environment_stain,
                    username="system",
                )
            )
            note.set_data(
                ChatBubbleData(
                    author="system",
                    timestamp="",
                    body="No comments yet.",
                    role="other",
                    actions=(),
                )
            )
            self._add_timeline_bubble(note)
        else:
            for comment in room.comments:
                reactions = comment.reactions
                reaction_bits: list[str] = []
                if reactions.thumbs_up > 0:
                    reaction_bits.append(f"+1={reactions.thumbs_up}")
                if reactions.thumbs_down > 0:
                    reaction_bits.append(f"-1={reactions.thumbs_down}")
                if reactions.eyes > 0:
                    reaction_bits.append(f"eyes={reactions.eyes}")
                if reactions.rocket > 0:
                    reaction_bits.append(f"rocket={reactions.rocket}")
                if reactions.hooray > 0:
                    reaction_bits.append(f"hooray={reactions.hooray}")
                reaction_text = (
                    f" · {', '.join(reaction_bits)}" if reaction_bits else ""
                )
                role = "self" if self._is_self_author(comment.author) else "other"

                bubble = ChatBubbleWidget()
                bubble.set_tone(
                    resolve_chat_bubble_tone(
                        role=role,
                        env_stain=self._environment_stain,
                        username=comment.author or "unknown",
                    )
                )
                bubble.set_data(
                    ChatBubbleData(
                        author=comment.author or "unknown",
                        timestamp=f"{self._format_time(comment.created_at)}{reaction_text}",
                        body=comment.body or "(empty)",
                        role=role,
                        actions=(
                            ChatBubbleAction(
                                action_id="reply",
                                label="Reply",
                                icon_name="reply",
                                tooltip="Focus comment composer",
                            ),
                            ChatBubbleAction(
                                action_id="open",
                                label="Open",
                                icon_name="external-link",
                                tooltip="Open in browser",
                            ),
                        ),
                    )
                )
                bubble.reply_requested.connect(self._focus_comment_composer)
                bubble.open_requested.connect(self._open_in_browser)
                self._add_timeline_bubble(bubble)

        QTimer.singleShot(0, self._scroll_timeline_to_bottom)
        self._status.setText(f"Loaded {len(room.comments)} comment(s).")
        if self._focus_comment_on_show:
            QTimer.singleShot(0, self._focus_comment_composer)
            self._focus_comment_on_show = False

    def _with_wait_cursor(self, fn: Callable[[], None]) -> None:
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            fn()
        finally:
            QApplication.restoreOverrideCursor()

    def _confirm_write(self, *, message: str, destructive: bool) -> bool:
        mode = self._confirmation_mode
        if mode == "never":
            return True
        if mode == "destructive_only" and not destructive:
            return True

        answer = QMessageBox.question(
            self,
            "Confirm GitHub action",
            message,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        return answer == QMessageBox.Yes

    def refresh(self) -> None:
        self._status.setText("Refreshing...")

        def _load() -> None:
            if self._item_type == "pr":
                self._room = get_pull_request_workroom(
                    self._repo_owner,
                    self._repo_name,
                    number=self._number,
                )
                return
            self._room = get_issue_workroom(
                self._repo_owner,
                self._repo_name,
                number=self._number,
            )

        try:
            self._with_wait_cursor(_load)
        except Exception as exc:
            self._status.setText(f"Failed to load: {exc}")
            QMessageBox.warning(self, "GitHub load failed", str(exc))
            return

        self._render_room()

    def _open_in_browser(self) -> None:
        room = self._room
        url = ""
        if room is not None:
            url = str(room.url or "").strip()
        if not url:
            url = str(self._item_url or "").strip()
        if not url:
            return
        QDesktopServices.openUrl(QUrl(url))

    def _build_prompt(self) -> str:
        room = self._room
        if room is None:
            return ""

        if room.item_type == "pr":
            return load_prompt(
                "pr_review_template",
                REPO_OWNER=room.repo_owner,
                REPO_NAME=room.repo_name,
                PR_NUMBER=room.number,
                PR_URL=room.url,
                PR_TITLE=room.title,
                MENTION_COMMENT_ID="",
                TRIGGER_SOURCE="manual",
            )

        return load_prompt(
            "issue_fix_template",
            REPO_OWNER=room.repo_owner,
            REPO_NAME=room.repo_name,
            ISSUE_NUMBER=room.number,
            ISSUE_URL=room.url,
            ISSUE_TITLE=room.title,
            MENTION_COMMENT_ID="",
            TRIGGER_SOURCE="manual",
        )

    def _on_primary(self) -> None:
        prompt = self._build_prompt().strip()
        if not prompt:
            QMessageBox.warning(
                self,
                "Prompt unavailable",
                "Could not build a task prompt for this item.",
            )
            return
        self.prompt_requested.emit(prompt)
        self.accept()

    def _on_toggle_open_state(self) -> None:
        room = self._room
        if room is None:
            return

        currently_open = room.state == "open"
        target_open = not currently_open
        action = "reopen" if target_open else "close"

        if not self._confirm_write(
            message=(
                f"Do you want to {action} {room.item_type} #{room.number} in "
                f"{room.repo_owner}/{room.repo_name}?"
            ),
            destructive=True,
        ):
            return

        def _write() -> None:
            set_item_open_state(
                room.repo_owner,
                room.repo_name,
                item_type=room.item_type,
                number=room.number,
                open_state=target_open,
            )

        try:
            self._with_wait_cursor(_write)
        except Exception as exc:
            QMessageBox.warning(self, "GitHub update failed", str(exc))
            return

        self.refresh()

    def _on_send_comment(self) -> None:
        room = self._room
        if room is None:
            return

        comment = str(self._comment.text() or "").strip()
        if not comment:
            QMessageBox.warning(self, "Missing comment", "Enter a comment first.")
            return

        if not self._confirm_write(
            message=(
                f"Post this comment to {room.item_type} #{room.number} in "
                f"{room.repo_owner}/{room.repo_name}?"
            ),
            destructive=False,
        ):
            return

        def _write() -> None:
            post_comment(
                room.repo_owner,
                room.repo_name,
                item_type=room.item_type,
                number=room.number,
                body=comment,
            )

        try:
            self._with_wait_cursor(_write)
        except Exception as exc:
            QMessageBox.warning(self, "Comment failed", str(exc))
            return

        self._comment.clear()
        self.refresh()
