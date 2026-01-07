from PySide6.QtGui import QColor
from PySide6.QtGui import QSyntaxHighlighter
from PySide6.QtGui import QTextCharFormat
from PySide6.QtGui import QTextDocument


class LogHighlighter(QSyntaxHighlighter):
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
        import re

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

        for pattern, style in self._rules:
            for match in re.finditer(pattern, text, flags=re.IGNORECASE):
                self.setFormat(match.start(), match.end() - match.start(), style)
