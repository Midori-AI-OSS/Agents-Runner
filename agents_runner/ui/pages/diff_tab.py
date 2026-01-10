from __future__ import annotations

import logging
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QPlainTextEdit, QSplitter,
)
from PySide6.QtGui import QFont, QTextCharFormat, QColor, QTextCursor

from agents_runner.gh.git_diff import (
    git_merge_base, git_changed_files, git_file_at_commit,
    read_workspace_file, ChangedFile
)
from agents_runner.style.palette import (
    GIT_STATUS_ADDED, GIT_STATUS_MODIFIED, GIT_STATUS_DELETED,
    GIT_STATUS_RENAMED, GIT_STATUS_UNTRACKED
)
from agents_runner.ui.diff_utils import compute_side_by_side_diff, DiffLine, format_line_number
from agents_runner.ui.task_model import Task
from agents_runner.widgets.glass_card import GlassCard

logger = logging.getLogger(__name__)


# Status colors
STATUS_COLORS = {
    "A": GIT_STATUS_ADDED,
    "M": GIT_STATUS_MODIFIED,
    "D": GIT_STATUS_DELETED,
    "R": GIT_STATUS_RENAMED,
    "U": GIT_STATUS_UNTRACKED,
}

STATUS_LABELS = {
    "A": "A",
    "M": "M",
    "D": "D",
    "R": "R",
    "U": "U",
}


class DiffTab(QWidget):
    """Side-by-side diff viewer tab."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._current_task: Task | None = None
        self._changed_files: list[ChangedFile] = []
        self._base_commit: str | None = None
        self._syncing_scroll = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        # Main splitter: file list (left) and diff view (right)
        main_splitter = QSplitter(Qt.Horizontal)
        main_splitter.setChildrenCollapsible(False)

        # Left panel: File list
        left_panel = GlassCard()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(18, 16, 18, 16)
        left_layout.setSpacing(10)

        list_header = QHBoxLayout()
        list_header.setSpacing(8)
        list_title = QLabel("Changed Files")
        list_title.setStyleSheet("font-size: 14px; font-weight: 650;")
        self._file_count = QLabel("(0)")
        self._file_count.setStyleSheet("color: rgba(237, 239, 245, 160);")
        list_header.addWidget(list_title)
        list_header.addWidget(self._file_count)
        list_header.addStretch(1)

        self._file_list = QListWidget()
        self._file_list.setSpacing(2)
        self._file_list.currentRowChanged.connect(self._on_file_selected)

        left_layout.addLayout(list_header)
        left_layout.addWidget(self._file_list, 1)

        # Right panel: Diff view
        right_panel = GlassCard()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(18, 16, 18, 16)
        right_layout.setSpacing(10)

        # Headers for diff panes
        headers = QHBoxLayout()
        headers.setSpacing(0)

        before_header = QLabel("Before")
        before_header.setStyleSheet("font-size: 14px; font-weight: 650;")
        after_header = QLabel("After")
        after_header.setStyleSheet("font-size: 14px; font-weight: 650;")

        headers.addWidget(before_header, 1)
        headers.addWidget(after_header, 1)

        # Diff splitter: before (left) and after (right)
        diff_splitter = QSplitter(Qt.Horizontal)
        diff_splitter.setChildrenCollapsible(False)

        # Before pane
        self._before_view = QPlainTextEdit()
        self._before_view.setReadOnly(True)
        self._before_view.setLineWrapMode(QPlainTextEdit.NoWrap)
        font = QFont("Monospace", 9)
        font.setStyleHint(QFont.TypeWriter)
        self._before_view.setFont(font)
        self._before_view.setStyleSheet("""
            QPlainTextEdit {
                background-color: rgba(18, 20, 28, 200);
                color: rgba(237, 239, 245, 230);
                border: 1px solid rgba(255, 255, 255, 25);
                border-radius: 0px;
            }
        """)

        # After pane
        self._after_view = QPlainTextEdit()
        self._after_view.setReadOnly(True)
        self._after_view.setLineWrapMode(QPlainTextEdit.NoWrap)
        self._after_view.setFont(font)
        self._after_view.setStyleSheet("""
            QPlainTextEdit {
                background-color: rgba(18, 20, 28, 200);
                color: rgba(237, 239, 245, 230);
                border: 1px solid rgba(255, 255, 255, 25);
                border-radius: 0px;
            }
        """)

        # Connect scroll bars for sync
        self._before_view.verticalScrollBar().valueChanged.connect(
            self._on_before_scroll_vertical
        )
        self._before_view.horizontalScrollBar().valueChanged.connect(
            self._on_before_scroll_horizontal
        )
        self._after_view.verticalScrollBar().valueChanged.connect(
            self._on_after_scroll_vertical
        )
        self._after_view.horizontalScrollBar().valueChanged.connect(
            self._on_after_scroll_horizontal
        )

        diff_splitter.addWidget(self._before_view)
        diff_splitter.addWidget(self._after_view)
        diff_splitter.setStretchFactor(0, 1)
        diff_splitter.setStretchFactor(1, 1)

        # Empty state
        self._empty_state = QLabel("No changes to display")
        self._empty_state.setAlignment(Qt.AlignCenter)
        self._empty_state.setStyleSheet(
            "color: rgba(237, 239, 245, 120); font-size: 13px;"
        )

        right_layout.addLayout(headers)
        right_layout.addWidget(diff_splitter, 1)
        right_layout.addWidget(self._empty_state, 1)

        main_splitter.addWidget(left_panel)
        main_splitter.addWidget(right_panel)
        main_splitter.setStretchFactor(0, 1)  # 1/4 width for file list
        main_splitter.setStretchFactor(1, 3)  # 3/4 width for diff view

        layout.addWidget(main_splitter, 1)

        # Initially hide diff view, show empty state
        diff_splitter.hide()
        self._empty_state.show()
        self._diff_splitter = diff_splitter

    def set_task(self, task: Task) -> None:
        """Load diff data for the given task."""
        self._current_task = task
        self._changed_files = []
        self._base_commit = None

        if not task.gh_repo_root or not task.gh_base_branch:
            logger.debug("Task has no git repo or base branch configured")
            self._update_file_list()
            return

        # Get base commit
        try:
            base_commit = git_merge_base(task.gh_repo_root, task.gh_base_branch)
            if not base_commit:
                logger.warning(
                    f"Could not find merge-base for {task.gh_base_branch}"
                )
                self._update_file_list()
                return

            self._base_commit = base_commit
            logger.debug(f"Base commit: {base_commit[:8]}")

            # Get changed files
            self._changed_files = git_changed_files(task.gh_repo_root, base_commit)
            logger.debug(f"Found {len(self._changed_files)} changed files")

        except Exception as e:
            logger.error(f"Failed to load git diff: {e}")

        self._update_file_list()

    def refresh(self) -> None:
        """Refresh the changed file list and current diff."""
        if self._current_task:
            selected_row = self._file_list.currentRow()
            self.set_task(self._current_task)
            # Restore selection if possible
            if 0 <= selected_row < len(self._changed_files):
                self._file_list.setCurrentRow(selected_row)

    def has_changes(self) -> bool:
        """Return True if there are any changes to display."""
        return len(self._changed_files) > 0

    def _update_file_list(self) -> None:
        """Update the file list widget."""
        self._file_list.clear()
        self._file_count.setText(f"({len(self._changed_files)})")

        if not self._changed_files:
            self._empty_state.setText("No changes to display")
            self._empty_state.show()
            self._diff_splitter.hide()
            return

        for changed_file in self._changed_files:
            item = QListWidgetItem()
            item.setData(Qt.UserRole, changed_file)

            widget = QWidget()
            layout = QHBoxLayout(widget)
            layout.setContentsMargins(8, 4, 8, 4)
            layout.setSpacing(8)

            # Status marker
            status_label = QLabel(STATUS_LABELS.get(changed_file.status, "?"))
            status_label.setFixedWidth(20)
            status_label.setStyleSheet(
                f"font-weight: 700; color: {STATUS_COLORS.get(changed_file.status, 'white')};"
            )

            # Filename
            filename = QLabel(changed_file.path)
            filename.setStyleSheet("color: rgba(237, 239, 245, 230);")

            layout.addWidget(status_label)
            layout.addWidget(filename, 1)

            item.setSizeHint(widget.sizeHint())
            self._file_list.addItem(item)
            self._file_list.setItemWidget(item, widget)

        # Select first file
        if self._changed_files:
            self._file_list.setCurrentRow(0)

    def _on_file_selected(self, current_row: int) -> None:
        """Handle file selection change."""
        if current_row < 0 or current_row >= len(self._changed_files):
            self._empty_state.show()
            self._diff_splitter.hide()
            return

        changed_file = self._changed_files[current_row]
        self._load_diff(changed_file)

    def _load_diff(self, changed_file: ChangedFile) -> None:
        """Load and display diff for a file."""
        if not self._current_task or not self._base_commit:
            self._show_error("No git information available")
            return

        try:
            repo_root = self._current_task.gh_repo_root

            # Get before content
            if changed_file.status == "A":
                # Added file - no before content
                before_text = ""
            else:
                before_text = git_file_at_commit(
                    repo_root, self._base_commit, changed_file.path
                )
                if before_text is None:
                    self._show_error(
                        "Binary file or too large to display\n\n"
                        "(Files over 1MB or binary files are not shown)"
                    )
                    return

            # Get after content
            if changed_file.status == "D":
                # Deleted file - no after content
                after_text = ""
            else:
                after_text = read_workspace_file(repo_root, changed_file.path)
                if after_text is None:
                    self._show_error(
                        "Binary file or too large to display\n\n"
                        "(Files over 1MB or binary files are not shown)"
                    )
                    return

            # Compute diff
            diff_lines = compute_side_by_side_diff(before_text, after_text)

            # Render diff
            self._render_diff(diff_lines)

        except Exception as e:
            logger.error(f"Failed to load diff for {changed_file.path}: {e}")
            self._show_error(f"Error loading diff:\n{str(e)}")

    def _render_diff(self, diff_lines: list[DiffLine]) -> None:
        """Render diff lines in both panes."""
        self._empty_state.hide()
        self._diff_splitter.show()

        # Clear both views
        self._before_view.clear()
        self._after_view.clear()

        # Build formatted text for both sides
        before_parts: list[str] = []
        after_parts: list[str] = []

        for line in diff_lines:
            # Format before side
            if line.before_line_no is not None:
                before_num = format_line_number(line.before_line_no)
                before_parts.append(f"{before_num} {line.before_text}")
            else:
                # Empty line for additions
                before_parts.append("")

            # Format after side
            if line.after_line_no is not None:
                after_num = format_line_number(line.after_line_no)
                after_parts.append(f"{after_num} {line.after_text}")
            else:
                # Empty line for deletions
                after_parts.append("")

        # Set text
        self._before_view.setPlainText("\n".join(before_parts))
        self._after_view.setPlainText("\n".join(after_parts))

        # Apply highlighting
        self._apply_highlighting(diff_lines)

    def _apply_highlighting(self, diff_lines: list[DiffLine]) -> None:
        """Apply background colors to changed lines."""
        # Create formats
        deleted_format = QTextCharFormat()
        deleted_format.setBackground(QColor(80, 30, 30, 120))

        added_format = QTextCharFormat()
        added_format.setBackground(QColor(30, 80, 30, 120))

        # Apply to before pane (deletions)
        before_cursor = QTextCursor(self._before_view.document())
        for i, line in enumerate(diff_lines):
            if line.change_type == "deleted":
                before_cursor.movePosition(QTextCursor.Start)
                before_cursor.movePosition(QTextCursor.Down, QTextCursor.MoveAnchor, i)
                before_cursor.select(QTextCursor.LineUnderCursor)
                before_cursor.setCharFormat(deleted_format)

        # Apply to after pane (additions)
        after_cursor = QTextCursor(self._after_view.document())
        for i, line in enumerate(diff_lines):
            if line.change_type == "added":
                after_cursor.movePosition(QTextCursor.Start)
                after_cursor.movePosition(QTextCursor.Down, QTextCursor.MoveAnchor, i)
                after_cursor.select(QTextCursor.LineUnderCursor)
                after_cursor.setCharFormat(added_format)

    def _show_error(self, message: str) -> None:
        """Show error message in both panes."""
        self._empty_state.hide()
        self._diff_splitter.show()
        self._before_view.setPlainText(message)
        self._after_view.setPlainText(message)

    # Scroll sync methods
    def _on_before_scroll_vertical(self, value: int) -> None:
        if self._syncing_scroll:
            return
        self._syncing_scroll = True
        self._after_view.verticalScrollBar().setValue(value)
        self._syncing_scroll = False

    def _on_before_scroll_horizontal(self, value: int) -> None:
        if self._syncing_scroll:
            return
        self._syncing_scroll = True
        self._after_view.horizontalScrollBar().setValue(value)
        self._syncing_scroll = False

    def _on_after_scroll_vertical(self, value: int) -> None:
        if self._syncing_scroll:
            return
        self._syncing_scroll = True
        self._before_view.verticalScrollBar().setValue(value)
        self._syncing_scroll = False

    def _on_after_scroll_horizontal(self, value: int) -> None:
        if self._syncing_scroll:
            return
        self._syncing_scroll = True
        self._before_view.horizontalScrollBar().setValue(value)
        self._syncing_scroll = False
