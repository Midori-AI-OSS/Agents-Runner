from __future__ import annotations

import re
from typing import TYPE_CHECKING

from PySide6.QtGui import QSyntaxHighlighter
from PySide6.QtGui import QTextCharFormat
from PySide6.QtGui import QColor

if TYPE_CHECKING:
    from PySide6.QtGui import QTextDocument

try:
    from spellchecker import SpellChecker
    SPELLCHECK_AVAILABLE = True
except ImportError:
    SPELLCHECK_AVAILABLE = False
    SpellChecker = None  # type: ignore


class SpellHighlighter(QSyntaxHighlighter):
    """
    Syntax highlighter that underlines misspelled words in red.
    
    Uses pyspellchecker for dictionary-based spell checking (no network requests).
    Words are checked as they are typed, with misspelled words getting a red wavy underline.
    """

    # Pattern to extract words (alphanumeric sequences, including apostrophes for contractions)
    WORD_PATTERN = re.compile(r"\b[a-zA-Z][a-zA-Z']*\b")

    def __init__(self, document: QTextDocument, enabled: bool = True) -> None:
        super().__init__(document)
        
        self._enabled = enabled
        self._spell_checker: SpellChecker | None = None
        
        if SPELLCHECK_AVAILABLE and enabled:
            try:
                self._spell_checker = SpellChecker()
            except Exception:
                # Silently fail if spell checker initialization fails
                self._spell_checker = None
        
        # Format for misspelled words
        self._error_format = QTextCharFormat()
        self._error_format.setUnderlineColor(QColor("#E06C75"))  # Red color
        self._error_format.setUnderlineStyle(
            QTextCharFormat.UnderlineStyle.WaveUnderline
        )

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable spell checking."""
        if self._enabled == enabled:
            return
        
        self._enabled = enabled
        
        if enabled and self._spell_checker is None and SPELLCHECK_AVAILABLE:
            try:
                self._spell_checker = SpellChecker()
            except Exception:
                self._spell_checker = None
        
        # Re-highlight entire document
        self.rehighlight()

    def highlightBlock(self, text: str) -> None:
        """
        Highlight misspelled words in the given text block.
        
        This is called by Qt whenever a block of text needs to be highlighted.
        """
        if not self._enabled or not self._spell_checker:
            return
        
        # Find all words in the text
        for match in self.WORD_PATTERN.finditer(text):
            word = match.group()
            start = match.start()
            length = match.end() - start
            
            # Skip very short words (1-2 characters) as they're often acronyms
            if length <= 2:
                continue
            
            # Skip words that are all uppercase (likely acronyms)
            if word.isupper():
                continue
            
            # Check if word is misspelled
            if self._is_misspelled(word):
                self.setFormat(start, length, self._error_format)

    def _is_misspelled(self, word: str) -> bool:
        """Check if a word is misspelled."""
        if not self._spell_checker:
            return False
        
        # Convert to lowercase for checking
        word_lower = word.lower()
        
        # Check if the word is known (correctly spelled)
        return word_lower not in self._spell_checker

    def add_word_to_dictionary(self, word: str) -> None:
        """Add a word to the personal dictionary."""
        if self._spell_checker:
            self._spell_checker.word_frequency.load_words([word.lower()])
            self.rehighlight()

    def get_suggestions(self, word: str) -> list[str]:
        """Get spelling suggestions for a misspelled word."""
        if not self._spell_checker:
            return []
        
        # Get candidates and return as a list
        candidates = self._spell_checker.candidates(word.lower())
        if not candidates:
            return []
        
        # Return up to 5 suggestions
        return sorted(list(candidates))[:5]
