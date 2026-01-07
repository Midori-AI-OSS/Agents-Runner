from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel


class HelpIcon(QLabel):
    """A small help icon that displays a tooltip on hover.
    
    Usage:
        help_icon = HelpIcon("This is helpful information")
        layout.addWidget(help_icon)
    """

    def __init__(self, tooltip_text: str, parent=None) -> None:
        """Initialize help icon with tooltip text.
        
        Args:
            tooltip_text: The text to display in the tooltip
            parent: Optional parent widget
        """
        super().__init__(parent)
        
        # Use the info symbol ⓘ
        self.setText("ⓘ")
        
        # Set tooltip
        self.setToolTip(tooltip_text)
        
        # Style the icon
        self.setStyleSheet(
            "color: rgba(237, 239, 245, 160);"  # Secondary text color
            "font-size: 14px;"
            "padding: 0px 4px;"
        )
        
        # Set fixed size to prevent layout issues
        self.setFixedSize(20, 20)
        
        # Center align the icon
        self.setAlignment(Qt.AlignCenter)
        
        # Change cursor to indicate help
        self.setCursor(Qt.WhatsThisCursor)
        
        # Disable text selection
        self.setTextInteractionFlags(Qt.NoTextInteraction)
