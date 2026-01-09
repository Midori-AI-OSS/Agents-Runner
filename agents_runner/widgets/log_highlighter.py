import re

from PySide6.QtGui import QColor
from PySide6.QtGui import QSyntaxHighlighter
from PySide6.QtGui import QTextCharFormat
from PySide6.QtGui import QTextDocument


class LogHighlighter(QSyntaxHighlighter):
    # Host scopes that should use neutral/accent colors
    HOST_SCOPES = {
        "host",
        "ui",
        "gh",
        "docker",
        "desktop",
        "artifacts",
        "env",
        "supervisor",
        "cleanup",
        "mcp",
    }

    # Canonical log format - supports both raw and aligned display formats:
    # Raw:     [{scope}/{subscope}][{LEVEL}] {message}
    # Aligned: [ {scope}/{subscope}     ][{LEVEL} ] {message}
    # The regex allows optional spaces after opening bracket and before closing bracket
    CANONICAL_LOG_RE = re.compile(r"^\[\s*([^/\]]+)/([^\]]+?)\s*\]\[\s*([A-Z]+)\s*\]\s(.*)$")

    def __init__(self, document: QTextDocument) -> None:
        super().__init__(document)

        def fmt(color: QColor, bold: bool = False) -> QTextCharFormat:
            f = QTextCharFormat()
            f.setForeground(color)
            if bold:
                f.setFontWeight(700)
            return f

        def fmt_block(
            foreground: QColor,
            *,
            background: QColor | None = None,
            bold: bool = False,
            italic: bool = False,
        ) -> QTextCharFormat:
            f = QTextCharFormat()
            f.setForeground(foreground)
            if background is not None:
                f.setBackground(background)
            if bold:
                f.setFontWeight(700)
            if italic:
                f.setFontItalic(True)
            return f

        slate = QColor(148, 163, 184, 235)
        cyan = QColor(56, 189, 248, 235)
        emerald = QColor(16, 185, 129, 235)
        rose = QColor(244, 63, 94, 235)
        amber = QColor(245, 158, 11, 235)
        violet = QColor(168, 85, 247, 235)
        zinc = QColor(226, 232, 240, 235)
        blue = QColor(59, 130, 246, 235)
        fuchsia = QColor(217, 70, 239, 235)

        # Color mappings for canonical log format
        self._host_scope_color = slate  # Neutral color for host scopes
        self._container_scope_color = QColor(56, 189, 248)  # Blue/cyan for container IDs
        self._level_colors = {
            "DEBUG": QColor(107, 114, 128),  # Gray/muted
            "INFO": QColor(209, 213, 219),   # Neutral/normal
            "WARN": QColor(245, 158, 11),    # Amber/yellow
            "ERROR": QColor(239, 68, 68),    # Red
        }
        self._default_text_color = QColor(209, 213, 219)  # Default for message body

        self._rules: list[tuple[object, QTextCharFormat]] = [
            (r"\[host\]", fmt(cyan, True)),
            (r"\[preflight\]", fmt(emerald, True)),
            (r"\[gh\]", fmt(violet, True)),
            (r"\[git\]", fmt(violet, True)),
            (r"\[docker\]", fmt(blue, True)),
            (r"\[desktop\]", fmt(fuchsia, True)),
            (r"\[cleanup\]", fmt(amber, True)),
            (r"\[queue\]", fmt(slate, True)),
            (r"\[interactive\]", fmt(cyan, True)),
            (r"\bpull complete\b", fmt(emerald, True)),
            (r"\bdocker pull\b", fmt(cyan, True)),
            (r"\b(exit|exited)\b", fmt(amber, True)),
            (r"\b(error|failed|fatal|exception)\b", fmt(rose, True)),
            # Markdown-ish extras (syntax highlighting, not rich-text rendering).
            (r"^#{1,6}\s+.*$", fmt(zinc, True)),
            (r"^\s*(?:[-*+]|\d+\.)\s+", fmt(amber, True)),
            (r"^\s*>\s+.*$", fmt(slate, False)),
            (r"\*\*[^*]+\*\*", fmt(zinc, True)),
            (r"__[^_]+__", fmt(zinc, True)),
            (r"`[^`]+`", fmt_block(violet, background=QColor(168, 85, 247, 28))),
            (
                r"```.*$",
                fmt_block(violet, background=QColor(168, 85, 247, 28), bold=True),
            ),
            (r"https?://\S+", fmt(cyan, False)),
            (r"\bTODO\b", fmt(amber, True)),
            (r"\bNOTE\b", fmt(slate, True)),
        ]

    def highlightBlock(self, text: str) -> None:
        # Skip blank lines - don't apply any formatting
        if not text or text.isspace():
            return

        in_fence = self.previousBlockState() == 1
        fence_line = bool(re.match(r"^```", text))
        if fence_line:
            self.setCurrentBlockState(0 if in_fence else 1)
        else:
            self.setCurrentBlockState(1 if in_fence else 0)

        if in_fence and not fence_line:
            code_format = QTextCharFormat()
            code_format.setForeground(QColor(226, 232, 240, 215))
            code_format.setBackground(QColor(15, 23, 42, 90))
            self.setFormat(0, len(text), code_format)
            return

        # Try to match canonical log format first
        canonical_match = self.CANONICAL_LOG_RE.match(text)
        if canonical_match:
            scope = canonical_match.group(1).strip()
            subscope = canonical_match.group(2).strip()
            level = canonical_match.group(3).strip()
            message = canonical_match.group(4)

            # Find actual positions in the original text to handle aligned format
            # The format could be either:
            # Raw:     [scope/subscope][LEVEL] message
            # Aligned: [ scope/subscope     ][LEVEL ] message
            
            # Find the scope bracket (from start to first ']')
            scope_bracket_end = text.find(']') + 1
            
            # Find the level bracket (from scope_bracket_end to next ']')
            level_bracket_start = scope_bracket_end
            level_bracket_end = text.find(']', level_bracket_start) + 1
            
            # Message starts after the level bracket and any whitespace
            # The regex captures message after '\s', so we need to find where it actually starts
            message_start = level_bracket_end
            # Skip the space(s) that separate level bracket from message
            while message_start < len(text) and text[message_start] == ' ':
                message_start += 1

            # Color the scope bracket
            scope_format = QTextCharFormat()
            if scope in self.HOST_SCOPES:
                scope_format.setForeground(self._host_scope_color)
            else:
                # Container scope (4-char container ID)
                scope_format.setForeground(self._container_scope_color)
            self.setFormat(0, scope_bracket_end, scope_format)

            # Color the level bracket
            level_format = QTextCharFormat()
            level_color = self._level_colors.get(level, self._default_text_color)
            level_format.setForeground(level_color)
            self.setFormat(
                level_bracket_start, level_bracket_end - level_bracket_start, level_format
            )

            # Message body uses default color (no explicit formatting needed)
            # Apply additional highlighting rules to the message portion only
            for pattern, style in self._rules:
                for match in re.finditer(pattern, message, flags=re.IGNORECASE):
                    # Offset match positions to account for the log prefix
                    self.setFormat(
                        message_start + match.start(),
                        match.end() - match.start(),
                        style,
                    )
        else:
            # Fall back to legacy highlighting rules if not canonical format
            for pattern, style in self._rules:
                for match in re.finditer(pattern, text, flags=re.IGNORECASE):
                    self.setFormat(match.start(), match.end() - match.start(), style)
