from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QPlainTextEdit
from PySide6.QtWidgets import QMenu

from agents_runner.widgets.spell_highlighter import SpellHighlighter

if TYPE_CHECKING:
    from PySide6.QtGui import QContextMenuEvent


class SpellTextEdit(QPlainTextEdit):
    """
    QPlainTextEdit with spell checking support.
    
    Features:
    - Red wavy underlines for misspelled words
    - Right-click context menu with spelling suggestions
    - "Add to dictionary" option
    - Can be enabled/disabled dynamically
    """

    def __init__(self, parent=None, spellcheck_enabled: bool = True) -> None:
        super().__init__(parent)
        
        # Create spell highlighter
        self._spell_highlighter = SpellHighlighter(self.document(), enabled=spellcheck_enabled)

    def set_spellcheck_enabled(self, enabled: bool) -> None:
        """Enable or disable spell checking."""
        self._spell_highlighter.set_enabled(enabled)

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        """
        Override context menu to add spelling suggestions.
        
        If the cursor is over a misspelled word, show suggestions at the top
        of the context menu.
        """
        # Get the cursor at the click position
        cursor = self.cursorForPosition(event.pos())
        
        # Get the word under the cursor
        word = self._get_word_under_cursor(cursor)
        
        # Create the standard context menu
        menu = self.createStandardContextMenu()
        
        # If we have a word and spell checking is enabled, add suggestions
        if word and self._spell_highlighter._enabled and self._spell_highlighter._spell_checker:
            # Check if word is misspelled
            if self._spell_highlighter._is_misspelled(word):
                # Get suggestions
                suggestions = self._spell_highlighter.get_suggestions(word)
                
                # Add suggestions to the top of the menu
                if suggestions:
                    # Add separator
                    first_action = menu.actions()[0] if menu.actions() else None
                    
                    # Add suggestion actions
                    for suggestion in suggestions:
                        action = menu.addAction(f"Replace with '{suggestion}'")
                        action.triggered.connect(
                            lambda checked=False, s=suggestion, c=cursor: self._replace_word(c, s)
                        )
                        if first_action:
                            menu.insertAction(first_action, action)
                            first_action = action
                        else:
                            menu.addAction(action)
                    
                    # Add separator after suggestions
                    if first_action:
                        separator = menu.insertSeparator(menu.actions()[len(suggestions)])
                    else:
                        menu.addSeparator()
                
                # Add "Add to dictionary" option
                add_to_dict_action = menu.addAction(f"Add '{word}' to dictionary")
                add_to_dict_action.triggered.connect(
                    lambda checked=False, w=word: self._add_to_dictionary(w)
                )
                
                # Insert at top if we have actions
                if menu.actions():
                    if suggestions:
                        # Insert after suggestions and separator
                        insert_index = len(suggestions) + 1
                        if insert_index < len(menu.actions()):
                            menu.insertAction(menu.actions()[insert_index], add_to_dict_action)
                    else:
                        # Insert at very top
                        menu.insertAction(menu.actions()[0], add_to_dict_action)
                        menu.insertSeparator(menu.actions()[1])
        
        # Show the menu
        menu.exec(event.globalPos())

    def _get_word_under_cursor(self, cursor: QTextCursor) -> str:
        """Extract the word under the cursor."""
        # Select the word under cursor
        cursor.select(QTextCursor.SelectionType.WordUnderCursor)
        word = cursor.selectedText().strip()
        
        # Only return if it looks like a word (letters only, possibly with apostrophe)
        if word and all(c.isalpha() or c == "'" for c in word):
            return word
        
        return ""

    def _replace_word(self, cursor: QTextCursor, new_word: str) -> None:
        """Replace the word at the cursor position with a new word."""
        # Select the word
        cursor.select(QTextCursor.SelectionType.WordUnderCursor)
        
        # Replace with new word
        cursor.insertText(new_word)

    def _add_to_dictionary(self, word: str) -> None:
        """Add a word to the personal dictionary."""
        self._spell_highlighter.add_word_to_dictionary(word)
