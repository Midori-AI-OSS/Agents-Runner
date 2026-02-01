from __future__ import annotations

import re
from typing import TYPE_CHECKING

from PySide6.QtGui import QColor, QSyntaxHighlighter, QTextCharFormat

if TYPE_CHECKING:
    from PySide6.QtGui import QTextDocument


# Language aliases for normalization
LANGUAGE_ALIASES = {
    "py": "python",
    "js": "javascript",
    "ts": "typescript",
    "sh": "bash",
    "shell": "bash",
    "yml": "yaml",
}


class ArtifactSyntaxHighlighter(QSyntaxHighlighter):
    """Syntax highlighter for artifact text previews using Pygments."""

    def __init__(self, document: QTextDocument) -> None:
        super().__init__(document)
        self._lexer = None
        self._token_formats: dict[object, QTextCharFormat] = {}
        self._is_markdown: bool = False
        self._lexer_cache: dict[str, object] = {}
        self._codeblock_lexers: list[object] = []
        self._fence_format: QTextCharFormat | None = None
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
            Generic,
            Literal,
        )

        def fmt(
            color: QColor, bold: bool = False, italic: bool = False
        ) -> QTextCharFormat:
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

        # Format for fence lines (backticks/tildes)
        self._fence_format = QTextCharFormat()
        self._fence_format.setForeground(QColor(148, 163, 184, 180))  # Dimmed slate

    def _get_cached_lexer(self, lang: str) -> object | None:
        """Get or create a cached lexer for the given language."""
        if not lang:
            return None

        # Normalize language name
        normalized = LANGUAGE_ALIASES.get(lang.lower(), lang.lower())

        # Check cache
        if normalized in self._lexer_cache:
            return self._lexer_cache[normalized]

        # Try to create lexer
        try:
            from pygments import lexers

            lexer = lexers.get_lexer_by_name(normalized)
            self._lexer_cache[normalized] = lexer
            return lexer
        except Exception:
            # Cache the None result to avoid repeated lookup failures
            self._lexer_cache[normalized] = None
            return None

    def _encode_state(self, fence_type: int, lexer_index: int) -> int:
        """
        Encode fence type and lexer index into a block state.

        Args:
            fence_type: 0 for backticks (```), 1 for tildes (~~~)
            lexer_index: Index into self._codeblock_lexers list

        Returns:
            Encoded state integer (0 means normal markdown)
        """
        # State encoding: (fence_type << 16) | (lexer_index + 1)
        # Add 1 to lexer_index so that state 0 means "not in code block"
        return (fence_type << 16) | (lexer_index + 1)

    def _decode_state(self, state: int) -> tuple[int, int]:
        """
        Decode block state into fence type and lexer index.

        Args:
            state: Encoded state integer

        Returns:
            Tuple of (fence_type, lexer_index)
        """
        fence_type = (state >> 16) & 0xFFFF
        lexer_index = (state & 0xFFFF) - 1
        return fence_type, lexer_index

    def set_language(self, language: str) -> None:
        """Set the lexer based on language name."""
        try:
            from pygments import lexers

            if language.lower() == "text" or not language:
                self._lexer = None
                self._is_markdown = False
            elif language.lower() == "markdown":
                self._lexer = lexers.get_lexer_by_name("markdown")
                self._is_markdown = True
                # Clear code block lexer cache when switching files
                self._codeblock_lexers = []
            else:
                self._lexer = lexers.get_lexer_by_name(language)
                self._is_markdown = False
        except Exception:
            # Fallback to plain text if lexer not found
            self._lexer = None
            self._is_markdown = False

    def highlightBlock(self, text: str) -> None:
        """Highlight a single block of text."""
        if not self._lexer:
            return

        # Special handling for Markdown files with fenced code blocks
        if self._is_markdown:
            self._highlight_markdown_block(text)
        else:
            self._highlight_normal_block(text)

    def _highlight_normal_block(self, text: str) -> None:
        """Highlight a block using the main lexer (non-Markdown)."""
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

    def _highlight_markdown_block(self, text: str) -> None:
        """Highlight a Markdown block, with special handling for fenced code blocks."""
        # Patterns for fence detection - use [^\s]* to support languages like c++, c#, f#
        backtick_fence_pattern = re.compile(r"^```([^\s]*)\s*$")
        tilde_fence_pattern = re.compile(r"^~~~([^\s]*)\s*$")

        prev_state = self.previousBlockState()

        # Qt returns -1 for uninitialized state, normalize to 0
        if prev_state < 0:
            prev_state = 0

        # Check if we're inside a code block
        if prev_state > 0:
            fence_type, lexer_index = self._decode_state(prev_state)

            # Check for closing fence
            if fence_type == 0:  # backticks
                if re.match(r"^```\s*$", text):
                    # Closing fence - style it and exit code block
                    self.setFormat(0, len(text), self._fence_format)
                    self.setCurrentBlockState(0)  # Back to normal markdown
                    return
            elif fence_type == 1:  # tildes
                if re.match(r"^~~~\s*$", text):
                    # Closing fence - style it and exit code block
                    self.setFormat(0, len(text), self._fence_format)
                    self.setCurrentBlockState(0)  # Back to normal markdown
                    return

            # Still inside code block - apply language-specific highlighting
            if 0 <= lexer_index < len(self._codeblock_lexers):
                code_lexer = self._codeblock_lexers[lexer_index]
                if code_lexer:
                    try:
                        from pygments import lex

                        tokens = list(lex(text, code_lexer))
                        position = 0
                        for token_type, token_text in tokens:
                            length = len(token_text)
                            fmt = None
                            while token_type and not fmt:
                                fmt = self._token_formats.get(token_type)
                                if not fmt:
                                    token_type = token_type.parent
                            if fmt:
                                self.setFormat(position, length, fmt)
                            position += length
                    except Exception:
                        pass

            # Maintain state
            self.setCurrentBlockState(prev_state)
            return

        # Not in code block - check for opening fence
        backtick_match = backtick_fence_pattern.match(text)
        tilde_match = tilde_fence_pattern.match(text)

        if backtick_match or tilde_match:
            # Opening fence detected
            match = backtick_match if backtick_match else tilde_match
            fence_type = 0 if backtick_match else 1
            lang = match.group(1) if match.group(1) else ""

            # Style the fence line
            self.setFormat(0, len(text), self._fence_format)

            # Get or create lexer for this language
            code_lexer = self._get_cached_lexer(lang) if lang else None

            # Add to codeblock lexers if not already present
            try:
                lexer_index = self._codeblock_lexers.index(code_lexer)
            except ValueError:
                # Not in list, add it
                self._codeblock_lexers.append(code_lexer)
                lexer_index = len(self._codeblock_lexers) - 1

            # Set state to indicate we're in a code block
            new_state = self._encode_state(fence_type, lexer_index)
            self.setCurrentBlockState(new_state)
            return

        # Normal markdown - use markdown lexer
        self._highlight_normal_block(text)


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
        ".markdown": "markdown",
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
