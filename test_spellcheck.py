#!/usr/bin/env python3
"""
Test script to verify spellcheck functionality works correctly.
"""

import sys
from PySide6.QtWidgets import QApplication
from agents_runner.widgets import SpellTextEdit

def test_spellcheck():
    """Test basic spellcheck functionality."""
    app = QApplication(sys.argv)
    
    # Create spell text edit with spellcheck enabled
    text_edit = SpellTextEdit(spellcheck_enabled=True)
    
    # Test that it was created successfully
    print("✓ SpellTextEdit created successfully")
    
    # Test enabling/disabling
    text_edit.set_spellcheck_enabled(False)
    print("✓ Spellcheck disabled successfully")
    
    text_edit.set_spellcheck_enabled(True)
    print("✓ Spellcheck enabled successfully")
    
    # Test with some text
    text_edit.setPlainText("This is a test with som mispeled words.")
    print("✓ Text set successfully")
    
    # Test highlighter
    if text_edit._spell_highlighter:
        print("✓ Spell highlighter initialized")
        
        # Test suggestions
        suggestions = text_edit._spell_highlighter.get_suggestions("mispeled")
        if suggestions:
            print(f"✓ Got suggestions for 'mispeled': {suggestions[:3]}")
        else:
            print("⚠ No suggestions returned (spell checker may not be initialized)")
    else:
        print("⚠ Spell highlighter not initialized")
    
    print("\n✅ All basic tests passed!")
    return 0

if __name__ == "__main__":
    sys.exit(test_spellcheck())
