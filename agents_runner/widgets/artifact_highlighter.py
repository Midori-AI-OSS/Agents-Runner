from __future__ import annotations

import re
from typing import TYPE_CHECKING

from PySide6.QtGui import QColor, QSyntaxHighlighter, QTextCharFormat

if TYPE_CHECKING:
    from PySide6.QtGui import QTextDocument


class ArtifactSyntaxHighlighter(QSyntaxHighlighter):
    """Syntax highlighter for artifact text previews using Pygments."""

    def __init__(self, document: QTextDocument) -> None:
        super().__init__(document)
        self._lexer = None
        self._token_formats: dict[object, QTextCharFormat] = {}
        self._initialize_formats()

    def _initialize_formats(self) -> None:
        """Initialize text formats for different token types."""
        from pygments.token import (
            Comment,
            Error,
            Keyword,
            Name,
            Number,
            Operator,
            String,
            Text,
            Generic,
            Literal,
        )

        def fmt(color: QColor, bold: bool = False, italic: bool = False) -> QTextCharFormat:
            f = QTextCharFormat()
            f.setForeground(color)
            if bold:
                f.setFontWeight(700)
            if italic:
                f.setFontItalic(True)
            return f

        # Color palette similar to log_highlighter.py
        slate = QColor(148, 163, 184, 235)
        cyan = QColor(56, 189, 248, 235)
        emerald = QColor(16, 185, 129, 235)
        rose = QColor(244, 63, 94, 235)
        amber = QColor(245, 158, 11, 235)
        violet = QColor(168, 85, 247, 235)
        zinc = QColor(226, 232, 240, 235)
        blue = QColor(59, 130, 246, 235)
        fuchsia = QColor(217, 70, 239, 235)

        # Map token types to formats
        self._token_formats = {
            Comment: fmt(slate, italic=True),
            Comment.Preproc: fmt(violet, bold=True),
            Comment.Special: fmt(cyan, italic=True),
            Keyword: fmt(fuchsia, bold=True),
            Keyword.Constant: fmt(violet, bold=True),
            Keyword.Namespace: fmt(violet, bold=True),
            Keyword.Type: fmt(blue, bold=True),
            Name.Builtin: fmt(cyan),
            Name.Function: fmt(blue),
            Name.Class: fmt(emerald, bold=True),
            Name.Decorator: fmt(amber),
            Name.Exception: fmt(rose, bold=True),
            Name.Variable: fmt(zinc),
            String: fmt(emerald),
            String.Doc: fmt(slate, italic=True),
            Number: fmt(amber),
            Operator: fmt(violet),
            Operator.Word: fmt(fuchsia, bold=True),
            Generic.Heading: fmt(zinc, bold=True),
            Generic.Subheading: fmt(blue, bold=True),
            Generic.Deleted: fmt(rose),
            Generic.Inserted: fmt(emerald),
            Generic.Error: fmt(rose, bold=True),
            Generic.Emph: fmt(zinc, italic=True),
            Generic.Strong: fmt(zinc, bold=True),
            Literal: fmt(amber),
            Error: fmt(rose, bold=True),
        }

    def set_language(self, language: str) -> None:
        """Set the lexer based on language name."""
        try:
            from pygments import lexers

            if language.lower() == "text" or not language:
                self._lexer = None
            else:
                self._lexer = lexers.get_lexer_by_name(language)
        except Exception:
            # Fallback to plain text if lexer not found
            self._lexer = None

    def highlightBlock(self, text: str) -> None:
        """Highlight a single block of text."""
        if not self._lexer:
            return

        try:
            from pygments import lex

            # Get all tokens for this line
            tokens = list(lex(text, self._lexer))

            # Apply formatting for each token
            position = 0
            for token_type, token_text in tokens:
                length = len(token_text)

                # Find matching format (check parent types too)
                fmt = None
                while token_type and not fmt:
                    fmt = self._token_formats.get(token_type)
                    if not fmt:
                        token_type = token_type.parent

                if fmt:
                    self.setFormat(position, length, fmt)

                position += length

        except Exception:
            # Silently fail and show plain text
            pass


def detect_language(filename: str, content: str) -> str:
    """
    Detect programming language from filename and content.

    Args:
        filename: Name of the file
        content: File content (first few KB is enough)

    Returns:
        Language name for Pygments lexer, or "text" for plain text
    """
    from pathlib import Path

    # Extension mapping
    ext = Path(filename).suffix.lower()
    extension_map = {
        ".py": "python",
        ".md": "markdown",
        ".json": "json",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".toml": "toml",
        ".sh": "bash",
        ".bash": "bash",
        ".zsh": "bash",
        ".ini": "ini",
        ".cfg": "ini",
        ".conf": "ini",
        ".xml": "xml",
        ".html": "html",
        ".htm": "html",
        ".css": "css",
        ".js": "javascript",
        ".ts": "typescript",
        ".tsx": "jsx",
        ".jsx": "jsx",
        ".diff": "diff",
        ".patch": "diff",
    }

    # Special case for Dockerfile
    if filename.lower() in ("dockerfile", ".dockerfile"):
        return "dockerfile"

    # Try extension mapping first
    if ext in extension_map:
        return extension_map[ext]

    # Try shebang detection for files without extensions
    if content and content.startswith("#!"):
        shebang_line = content.split("\n", 1)[0].lower()
        if "python" in shebang_line:
            return "python"
        elif "bash" in shebang_line or "sh" in shebang_line:
            return "bash"
        elif "node" in shebang_line:
            return "javascript"

    # Default to plain text
    return "text"
