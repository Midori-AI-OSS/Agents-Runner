from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtCore import QThread
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

from agents_runner.gh.work_items import delete_issue_comment
from agents_runner.gh.work_items import GitHubWorkroom
from agents_runner.gh.work_items import get_authenticated_github_login
from agents_runner.gh.work_items import get_issue_workroom
from agents_runner.gh.work_items import get_pull_request_workroom
from agents_runner.gh.work_items import post_comment
from agents_runner.gh.work_items import set_item_open_state
from agents_runner.prompts import load_prompt
from agents_runner.prompts.github_prompting import build_default_request_line
from agents_runner.prompts.github_prompting import build_primary_request
from agents_runner.stt.mic_recorder import FfmpegPulseRecorder
from agents_runner.stt.mic_recorder import MicRecorderError
from agents_runner.stt.mic_recorder import MicRecording
from agents_runner.ui.dialogs.themed_dialog import ThemedDialog
from agents_runner.ui.icons import mic_icon
from agents_runner.ui.lucide_icons import lucide_icon
from agents_runner.ui.stt.qt_worker import SttWorker
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

        self._stt_mode = "offline"
        self._mic_recording: MicRecording | None = None
        self._stt_thread: QThread | None = None
        self._stt_worker: SttWorker | None = None

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

        composer_input = QWidget()
        composer_input.setObjectName("WorkroomComposerInput")
        composer_input.setStyleSheet(
            "\n".join(
                [
                    "QWidget#WorkroomComposerInput {",
                    "  border: 1px solid rgba(115, 124, 143, 140);",
                    "  background-color: rgba(26, 28, 37, 185);",
                    "  border-radius: 0px;",
                    "}",
                    "QWidget#WorkroomComposerInput QLineEdit {",
                    "  border: 0px;",
                    "  background: transparent;",
                    "  color: rgba(237, 239, 245, 235);",
                    "  padding: 7px 4px;",
                    "}",
                    "QWidget#WorkroomComposerInput QToolButton {",
                    "  border: 0px;",
                    "  border-radius: 0px;",
                    "  background: transparent;",
                    "  color: rgba(237, 239, 245, 210);",
                    "  padding: 6px;",
                    "}",
                    "QWidget#WorkroomComposerInput QToolButton:hover:!disabled {",
                    "  background: rgba(112, 124, 156, 60);",
                    "}",
                    "QWidget#WorkroomComposerInput QToolButton:pressed:!disabled {",
                    "  background: rgba(112, 124, 156, 90);",
                    "}",
                    "QWidget#WorkroomComposerInput QToolButton:disabled {",
                    "  color: rgba(237, 239, 245, 95);",
                    "}",
                ]
            )
        )

        row = QHBoxLayout(composer_input)
        row.setContentsMargins(4, 2, 4, 2)
        row.setSpacing(4)

        self._voice_btn = QToolButton()
        self._voice_btn.setCheckable(True)
        self._voice_btn.setIcon(mic_icon(size=18))
        self._voice_btn.setIconSize(self._voice_btn.iconSize())
        self._voice_btn.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self._voice_btn.setToolTip("Speech-to-text into the comment input.")
        self._voice_btn.toggled.connect(self._on_voice_toggled)

        self._comment = QLineEdit()
        self._comment.setPlaceholderText("Write a comment...")
        self._comment.textChanged.connect(self._sync_send_button_state)
        self._comment.returnPressed.connect(self._on_comment_return_pressed)

        self._btn_send = QToolButton()
        self._btn_send.setIcon(lucide_icon("arrow-up"))
        self._btn_send.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self._btn_send.setToolTip("Post comment")
        self._btn_send.clicked.connect(self._on_send_comment)

        row.addWidget(self._voice_btn, 0)
        row.addWidget(self._comment, 1)
        row.addWidget(self._btn_send, 0)

        composer_layout.addWidget(composer_title)
        composer_layout.addWidget(composer_input)

        layout.addWidget(composer)

        self._sync_primary_button()
        self._sync_open_state_button("open")
        self._sync_send_button_state()
        self.refresh()

    def _normalize_user(self, username: str) -> str:
        return str(username or "").strip().lower().lstrip("@")

    def _is_self_author(self, username: str) -> bool:
        if not self._current_login:
            return False
        return self._normalize_user(username) == self._current_login

    def _item_kind_label(self, item_type: str) -> str:
        return "PR" if str(item_type or "").strip().lower() == "pr" else "Issue"

    def _clear_timeline(self) -> None:
        while self._timeline_layout.count() > 1:
            item = self._timeline_layout.takeAt(0)
            if item is None:
                continue
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
        item_label = self._item_kind_label(self._item_type)
        if normalized == "open":
            self._btn_toggle_state.setText(f"Close ({item_label})")
            self._btn_toggle_state.setIcon(lucide_icon("square"))
            self._btn_toggle_state.setToolTip("Close this item")
            return

        self._btn_toggle_state.setText(f"Reopen ({item_label})")
        self._btn_toggle_state.setIcon(lucide_icon("play"))
        self._btn_toggle_state.setToolTip("Reopen this item")

    def _sync_send_button_state(self) -> None:
        self._btn_send.setEnabled(bool(str(self._comment.text() or "").strip()))

    def _on_comment_return_pressed(self) -> None:
        if self._btn_send.isEnabled():
            self._on_send_comment()

    def _reset_voice_button(self) -> None:
        self._voice_btn.setEnabled(True)
        self._voice_btn.setIcon(mic_icon(size=18))
        self._voice_btn.setToolTip("Speech-to-text into the comment input.")

    def _on_voice_toggled(self, enabled: bool) -> None:
        if self._stt_thread is not None:
            self._voice_btn.blockSignals(True)
            try:
                self._voice_btn.setChecked(False)
            finally:
                self._voice_btn.blockSignals(False)
            return

        if enabled:
            self._start_voice_recording()
            return

        self._stop_voice_recording_and_transcribe()

    def _start_voice_recording(self) -> None:
        if not FfmpegPulseRecorder.is_available():
            QMessageBox.warning(
                self,
                "Voice input unavailable",
                "Could not find `ffmpeg` in PATH (needed to record audio).",
            )
            self._voice_btn.blockSignals(True)
            try:
                self._voice_btn.setChecked(False)
            finally:
                self._voice_btn.blockSignals(False)
            self._reset_voice_button()
            return

        try:
            recorder = FfmpegPulseRecorder()
            self._mic_recording = recorder.start()
        except MicRecorderError as exc:
            QMessageBox.warning(
                self, "Microphone error", str(exc) or "Could not start recording."
            )
            self._voice_btn.blockSignals(True)
            try:
                self._voice_btn.setChecked(False)
            finally:
                self._voice_btn.blockSignals(False)
            self._reset_voice_button()
            return

        self._voice_btn.setIcon(lucide_icon("square"))
        self._voice_btn.setToolTip("Stop recording and transcribe into the comment.")

    def _stop_voice_recording_and_transcribe(self) -> None:
        recording = self._mic_recording
        self._mic_recording = None
        if recording is None:
            self._reset_voice_button()
            return

        self._voice_btn.setEnabled(False)

        recorder = FfmpegPulseRecorder(output_dir=recording.output_path.parent)
        try:
            audio_path = recorder.stop(recording)
        except MicRecorderError as exc:
            QMessageBox.warning(
                self, "Microphone error", str(exc) or "Could not stop recording."
            )
            self._voice_btn.blockSignals(True)
            try:
                self._voice_btn.setChecked(False)
            finally:
                self._voice_btn.blockSignals(False)
            self._reset_voice_button()
            return

        self._voice_btn.setIcon(lucide_icon("refresh-cw"))
        self._voice_btn.setToolTip("Transcribing speech-to-text…")

        worker = SttWorker(mode=self._stt_mode, audio_path=str(audio_path))
        thread = QThread(self)
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.done.connect(self._on_stt_done)
        worker.error.connect(self._on_stt_error)

        worker.done.connect(thread.quit)
        worker.error.connect(thread.quit)

        worker.done.connect(worker.deleteLater)
        worker.error.connect(worker.deleteLater)

        thread.finished.connect(self._on_stt_finished)
        thread.finished.connect(thread.deleteLater)

        self._stt_worker = worker
        self._stt_thread = thread
        thread.start()

    def _on_stt_done(self, text: str, audio_path: str) -> None:
        value = str(text or "").strip()
        if value:
            current = str(self._comment.text() or "").strip()
            next_value = f"{current} {value}".strip() if current else value
            self._comment.setText(next_value)
            self._comment.setCursorPosition(len(next_value))
        else:
            QMessageBox.information(
                self,
                "No speech detected",
                "Speech-to-text did not return any text.",
            )

        try:
            Path(str(audio_path or "")).unlink(missing_ok=True)
        except Exception:
            pass

    def _on_stt_error(self, message: str, audio_path: str) -> None:
        msg = str(message or "").strip() or "Speech-to-text failed."
        QMessageBox.warning(self, "Speech-to-text error", msg)
        try:
            Path(str(audio_path or "")).unlink(missing_ok=True)
        except Exception:
            pass

    def _on_stt_finished(self) -> None:
        self._stt_thread = None
        self._stt_worker = None
        self._voice_btn.blockSignals(True)
        try:
            self._voice_btn.setChecked(False)
        finally:
            self._voice_btn.blockSignals(False)
        self._reset_voice_button()

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

        kind = self._item_kind_label(room.item_type)
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
                icon_name="corner-up-right",
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
            reaction_text = f" · {', '.join(reaction_bits)}" if reaction_bits else ""
            role = "self" if self._is_self_author(comment.author) else "other"

            actions: list[ChatBubbleAction] = [
                ChatBubbleAction(
                    action_id="reply",
                    label="Reply",
                    icon_name="corner-up-right",
                    tooltip="Focus comment composer",
                ),
                ChatBubbleAction(
                    action_id="open",
                    label="Open",
                    icon_name="external-link",
                    tooltip="Open in browser",
                ),
            ]
            if self._is_self_author(comment.author):
                actions.append(
                    ChatBubbleAction(
                        action_id="delete",
                        label="Delete",
                        icon_name="trash-2",
                        tooltip="Delete this comment",
                    )
                )

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
                    actions=tuple(actions),
                )
            )
            bubble.reply_requested.connect(self._focus_comment_composer)
            bubble.open_requested.connect(self._open_in_browser)
            bubble.delete_requested.connect(
                lambda cid=comment.comment_id: self._on_delete_comment(cid)
            )
            self._add_timeline_bubble(bubble)

        QTimer.singleShot(0, self._scroll_timeline_to_bottom)
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

        default_request = build_default_request_line(
            item_type=room.item_type,
            repo_owner=room.repo_owner,
            repo_name=room.repo_name,
            number=room.number,
        )
        primary_request = build_primary_request(
            mention_text="",
            fallback=default_request,
        )

        if room.item_type == "pr":
            return load_prompt(
                "pr_review_template",
                REPO_OWNER=room.repo_owner,
                REPO_NAME=room.repo_name,
                PR_NUMBER=room.number,
                PR_URL=room.url,
                PR_TITLE=room.title,
                PRIMARY_REQUEST=primary_request,
            )

        return load_prompt(
            "issue_fix_template",
            REPO_OWNER=room.repo_owner,
            REPO_NAME=room.repo_name,
            ISSUE_NUMBER=room.number,
            ISSUE_URL=room.url,
            ISSUE_TITLE=room.title,
            PRIMARY_REQUEST=primary_request,
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

    def _on_delete_comment(self, comment_id: int) -> None:
        room = self._room
        if room is None:
            return

        if not self._confirm_write(
            message=(
                f"Delete comment #{int(comment_id)} on {room.item_type} "
                f"#{room.number} in {room.repo_owner}/{room.repo_name}?"
            ),
            destructive=True,
        ):
            return

        def _write() -> None:
            delete_issue_comment(
                room.repo_owner,
                room.repo_name,
                comment_id=int(comment_id),
            )

        try:
            self._with_wait_cursor(_write)
        except Exception as exc:
            QMessageBox.warning(self, "Comment delete failed", str(exc))
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
        self._sync_send_button_state()
        self.refresh()
