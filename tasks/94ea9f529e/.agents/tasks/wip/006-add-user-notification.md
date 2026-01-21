# Task: Add User Notification for Fallback

## Objective
Implement user notification when fallback mechanism is triggered.

## Context
Issue #140: Users should be informed when the web engine crashes and their link opens in default browser.

## Actions
1. Create a simple QMessageBox notification or status message
2. Message should inform: "Web viewer crashed, opening in default browser"
3. Make it non-blocking (auto-dismiss or quick close)
4. Follow design constraint: sharp corners, no rounded borders
5. Add option to suppress future notifications (optional)

## Success Criteria
- Clear, concise notification message
- Non-intrusive UX
- Follows design constraints (sharp corners)
- User understands what happened

## Dependencies
- Task 005 (fallback integration completed) - MUST complete first

## Estimated Effort
30 minutes

## Implementation Specifications

### File to Modify
`agents_runner/desktop_viewer/app.py`

### Method to Implement
Update the placeholder `_show_fallback_notification()` from Task 005:

```python
def _show_fallback_notification(
    self,
    success: bool,
    reason: str,
    url: str | None = None
) -> None:
    """
    Show user notification about fallback attempt.
    
    Args:
        success: Whether browser opened successfully
        reason: Why fallback was triggered (e.g., "Web viewer crashed")
        url: The URL being opened (if available)
    
    Displays a non-blocking message box informing the user that
    the web viewer encountered an issue and the link has been
    opened (or attempted to be opened) in their default browser.
    """
    from PyQt6.QtWidgets import QMessageBox
    from PyQt6.QtCore import Qt
    
    # Prepare message based on outcome
    if success and url:
        title = "Web Viewer Issue"
        message = (
            f"{reason}\n\n"
            f"Opening in your default browser:\n{url}"
        )
        icon = QMessageBox.Icon.Information
    elif not success and url:
        title = "Web Viewer Error"
        message = (
            f"{reason}\n\n"
            f"Failed to open in default browser:\n{url}\n\n"
            f"Please copy and paste this URL manually."
        )
        icon = QMessageBox.Icon.Warning
    else:
        title = "Web Viewer Error"
        message = f"{reason}\n\nNo URL available to open."
        icon = QMessageBox.Icon.Warning
    
    # Create message box
    msg_box = QMessageBox(self)  # self = parent window
    msg_box.setWindowTitle(title)
    msg_box.setText(message)
    msg_box.setIcon(icon)
    msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
    
    # Apply design constraints: sharp corners
    msg_box.setStyleSheet("""
        QMessageBox {
            border-radius: 0px;
        }
        QPushButton {
            border-radius: 0px;
            min-width: 80px;
            padding: 5px;
        }
    """)
    
    # Show non-blocking (returns immediately)
    msg_box.setWindowModality(Qt.WindowModality.NonModal)
    msg_box.show()
    
    logger.debug(f"Notification shown: {title}")
```

### Alternative: Status Bar Message (Lighter Weight)
If QMessageBox is too intrusive:

```python
def _show_fallback_notification(
    self,
    success: bool,
    reason: str,
    url: str | None = None
) -> None:
    """Show notification in status bar instead of dialog."""
    if hasattr(self, 'statusBar'):
        if success:
            message = f"{reason} - Opened in default browser"
        else:
            message = f"{reason} - Failed to open browser"
        
        self.statusBar().showMessage(message, 10000)  # 10 seconds
        logger.debug(f"Status message shown: {message}")
```

### Design Constraints Applied
1. **Sharp corners**: `border-radius: 0px` for all elements
2. **Non-blocking**: `WindowModality.NonModal` or status bar
3. **Quick to dismiss**: Single OK button or auto-dismiss status
4. **Minimal styling**: Only border-radius override, use system defaults

### Message Content Guidelines
- **Success**: Informative, reassuring
  - "Web viewer crashed"
  - "Opening in your default browser: [URL]"
- **Failure**: Helpful, actionable
  - "Web viewer crashed"
  - "Failed to open in default browser: [URL]"
  - "Please copy and paste this URL manually"
- **No URL**: Honest, simple
  - "Web viewer crashed"
  - "No URL available to open"

### Optional Enhancement: "Don't Show Again"
```python
# Add checkbox to message box
msg_box.setCheckBox(QCheckBox("Don't show this message again"))

# Store preference (requires settings mechanism)
if msg_box.checkBox().isChecked():
    self._save_notification_preference(False)
```

### Import Statements Required
```python
from PyQt6.QtWidgets import QMessageBox
from PyQt6.QtCore import Qt
# Optional: from PyQt6.QtWidgets import QCheckBox
```

### Testing Plan
1. **Test success notification**: Trigger crash with valid URL
2. **Test failure notification**: Mock browser opener to return False
3. **Test no URL notification**: Trigger crash with `_current_url = None`
4. **Verify styling**: Check that corners are sharp, not rounded
5. **Verify non-blocking**: Confirm you can interact with other windows
6. **Test message clarity**: Have someone else read it and confirm understanding

## Acceptance Checklist
- [ ] `_show_fallback_notification()` fully implemented
- [ ] Handles all three scenarios (success, failure, no URL)
- [ ] Messages are clear and actionable
- [ ] StyleSheet applied for sharp corners
- [ ] Non-blocking (NonModal or status bar)
- [ ] Type hints on all parameters
- [ ] Logging added
- [ ] Tested all three notification scenarios
- [ ] Follows design constraints (sharp corners verified)
- [ ] No new dependencies added (uses existing PyQt)

## Design Decision
**Choose notification method:**
- [ ] **QMessageBox** (recommended for visibility)
- [ ] **Status Bar** (less intrusive)
- [ ] **System Tray** (requires QSystemTrayIcon)

Document choice in implementation comments.
