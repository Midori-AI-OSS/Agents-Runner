"""Diff parsing and line alignment utilities for side-by-side display."""

from __future__ import annotations
from dataclasses import dataclass
import difflib


@dataclass
class DiffLine:
    """A single line in the side-by-side diff."""

    before_line_no: int | None  # Line number in before file (None for additions)
    before_text: str  # Text content (empty string for additions)
    after_line_no: int | None  # Line number in after file (None for deletions)
    after_text: str  # Text content (empty string for deletions)
    change_type: str  # "unchanged", "added", "deleted", "modified"


def compute_side_by_side_diff(before_text: str, after_text: str) -> list[DiffLine]:
    """Compute side-by-side diff lines using difflib.SequenceMatcher.

    Returns DiffLine objects where unchanged lines have both before/after content,
    deleted lines have before content only, and added lines have after content only.
    Lines are aligned for side-by-side scrolling.
    """
    before_lines = before_text.splitlines() if before_text else []
    after_lines = after_text.splitlines() if after_text else []
    matcher = difflib.SequenceMatcher(None, before_lines, after_lines)
    diff_lines: list[DiffLine] = []
    before_idx = after_idx = 0

    for before_start, after_start, size in matcher.get_matching_blocks():
        # Process gap (deletions and additions) before this matching block
        if before_idx < before_start or after_idx < after_start:
            deleted_lines = before_lines[before_idx:before_start]
            added_lines = after_lines[after_idx:after_start]

            # Add all deletions, then all additions
            for i, line in enumerate(deleted_lines):
                diff_lines.append(
                    DiffLine(before_idx + i + 1, line, None, "", "deleted")
                )
            for i, line in enumerate(added_lines):
                diff_lines.append(
                    DiffLine(None, "", after_idx + i + 1, line, "added")
                )

        # Process matching block (unchanged lines)
        for i in range(size):
            diff_lines.append(
                DiffLine(
                    before_start + i + 1,
                    before_lines[before_start + i],
                    after_start + i + 1,
                    after_lines[after_start + i],
                    "unchanged",
                )
            )

        before_idx = before_start + size
        after_idx = after_start + size

    return diff_lines


def format_line_number(num: int | None, width: int = 4) -> str:
    """Format line number for display, or spaces if None."""
    if num is None:
        return " " * width
    return str(num).rjust(width)
