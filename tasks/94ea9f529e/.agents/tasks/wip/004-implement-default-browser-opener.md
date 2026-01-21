# Task: Implement Default Browser Opener Utility

## Objective
Create a utility function to open URLs in the user's default web browser.

## Context
Issue #140: Fallback mechanism needs to open links in default browser when QT web engine crashes.

## Actions
1. Create a utility function (possibly in desktop_viewer/app.py or a new utils file)
2. Use Python's webbrowser module to open URLs
3. Add error handling for browser opening failures
4. Add type hints (Python 3.13+)
5. Add logging for successful/failed browser opens

## Success Criteria
- Function successfully opens URL in default browser
- Cross-platform compatibility (Linux, macOS, Windows)
- Proper error handling
- Type hints included
- Logging implemented

## Dependencies
- Task 002 (design completed) - MUST review design doc first

## Estimated Effort
30 minutes

## Implementation Specifications

### File Location
**Option A:** Add to existing `agents_runner/desktop_viewer/app.py` as method
**Option B:** Create new `agents_runner/desktop_viewer/browser_utils.py`

Recommendation: Option A for minimal changes (single file modification)

### Code Implementation

#### Import Required
```python
import webbrowser
import logging
from typing import NoReturn

logger = logging.getLogger(__name__)
```

#### Function/Method to Add
```python
def _open_in_default_browser(self, url: str | None) -> bool:
    """
    Open URL in the user's default web browser.
    
    Args:
        url: The URL to open. If None or empty, logs warning and returns False.
    
    Returns:
        True if browser opened successfully, False otherwise.
    
    Raises:
        No exceptions raised - all errors are caught and logged.
    
    Example:
        >>> self._open_in_default_browser("https://example.com")
        True
    """
    if not url:
        logger.warning("Cannot open browser: URL is empty or None")
        return False
    
    try:
        logger.info(f"Opening URL in default browser: {url}")
        webbrowser.open(url)
        logger.info("Browser opened successfully")
        return True
        
    except Exception as e:
        logger.error(
            f"Failed to open URL in default browser: {url}",
            exc_info=True
        )
        return False
```

### Alternative Implementation (QT-native)
If design doc specifies QDesktopServices:
```python
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtCore import QUrl

def _open_in_default_browser(self, url: str | None) -> bool:
    """Open URL using QT's desktop services."""
    if not url:
        logger.warning("Cannot open browser: URL is empty or None")
        return False
    
    try:
        logger.info(f"Opening URL in default browser: {url}")
        qurl = QUrl(url)
        success = QDesktopServices.openUrl(qurl)
        
        if success:
            logger.info("Browser opened successfully")
        else:
            logger.error("QDesktopServices failed to open URL")
        
        return success
        
    except Exception as e:
        logger.error(f"Failed to open URL: {url}", exc_info=True)
        return False
```

### Error Handling Strategy
1. **Null/empty URL**: Log warning, return False
2. **webbrowser.open() fails**: Catch Exception, log with stack trace, return False
3. **Success**: Log at INFO level, return True

### Testing Plan
```python
# Manual testing steps:
# 1. Test with valid URL: https://example.com
# 2. Test with None
# 3. Test with empty string
# 4. Test with invalid URL format
# 5. Verify browser actually opens on your platform
```

### Cross-Platform Considerations
The `webbrowser` module handles platform differences:
- **Linux**: Uses `xdg-open`, `gnome-open`, or `kde-open`
- **macOS**: Uses `open` command
- **Windows**: Uses `start` command

No platform-specific code needed when using `webbrowser.open()`

## Acceptance Checklist
- [ ] Function implemented with full type hints
- [ ] Docstring includes Args, Returns, Example
- [ ] Handles None/empty URL gracefully
- [ ] Catches and logs all exceptions
- [ ] Returns boolean success indicator
- [ ] Tested on primary development platform
- [ ] Logging at appropriate levels (INFO for success, ERROR for failure, WARNING for invalid input)
- [ ] No external dependencies added (webbrowser is stdlib)
