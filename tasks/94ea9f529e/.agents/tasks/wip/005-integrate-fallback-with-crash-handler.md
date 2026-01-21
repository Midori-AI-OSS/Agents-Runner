# Task: Integrate Fallback with Crash Handler

## Objective
Connect crash detection with the default browser opener to complete the fallback mechanism.

## Context
Issue #140: When crash is detected, automatically open the URL in default browser.

## Actions
1. Call browser opener function from crash detection handler
2. Pass the stored URL to the browser opener
3. Show user notification about fallback (dialog or message)
4. Ensure proper error handling for the entire flow
5. Add appropriate logging

## Success Criteria
- Crash triggers fallback to default browser automatically
- User is notified about the fallback
- URL opens correctly in default browser
- No unhandled exceptions
- Follows design constraints (minimal diff)

## Dependencies
- Task 003 (crash detection implemented) - MUST complete first
- Task 004 (browser opener implemented) - MUST complete first

## Estimated Effort
45 minutes

## Implementation Specifications

### File to Modify
`agents_runner/desktop_viewer/app.py`

### Integration Points

#### 1. Update `_on_render_process_terminated` Handler
```python
def _on_render_process_terminated(
    self,
    termination_status: QWebEnginePage.RenderProcessTerminationStatus,
    exit_code: int
) -> None:
    """
    Handle render process crashes with fallback to default browser.
    
    When the QT web engine crashes, this handler:
    1. Logs the crash details
    2. Opens the URL in the default browser
    3. Notifies the user (Task 006)
    """
    logger.error(
        f"Render process terminated: status={termination_status}, "
        f"exit_code={exit_code}, url={self._current_url}"
    )
    
    # Trigger fallback mechanism
    self._trigger_fallback("Web viewer crashed")
```

#### 2. Implement `_trigger_fallback` Method
```python
def _trigger_fallback(self, reason: str) -> None:
    """
    Trigger fallback mechanism to open URL in default browser.
    
    Args:
        reason: Human-readable reason for triggering fallback
                (e.g., "Web viewer crashed", "Page load failed")
    
    This method:
    1. Validates URL is available
    2. Attempts to open in default browser
    3. Shows user notification (Task 006 will implement)
    4. Logs the outcome
    """
    logger.info(f"Triggering fallback: {reason}")
    
    if not self._current_url:
        logger.warning("Fallback triggered but no URL available")
        # Still show notification that crash occurred
        self._show_fallback_notification(success=False, reason=reason)
        return
    
    # Attempt to open in default browser
    success = self._open_in_default_browser(self._current_url)
    
    # Notify user (implementation in Task 006)
    self._show_fallback_notification(
        success=success,
        reason=reason,
        url=self._current_url
    )
    
    if success:
        logger.info(f"Fallback successful: {self._current_url}")
    else:
        logger.error(f"Fallback failed: {self._current_url}")
```

#### 3. Add Placeholder for Notification (Task 006)
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
        reason: Why fallback was triggered
        url: The URL being opened (if available)
    
    NOTE: Full implementation in Task 006
    """
    # Placeholder - Task 006 will implement UI notification
    if success:
        logger.info(f"TODO: Show notification - {reason}, opening: {url}")
    else:
        logger.warning(f"TODO: Show notification - {reason}, failed to open URL")
    pass  # Task 006 will add QMessageBox or other notification
```

### Error Handling Flow
```
Crash Detected
    ↓
Check if URL available
    ↓ (no URL)          ↓ (has URL)
Log warning          Attempt browser open
    ↓                    ↓
Notify user         Check result
(no URL)                ↓
                   ↓(success)  ↓(failure)
                Notify user   Log error
                (opened)      Notify user
                              (failed)
```

### Edge Cases to Handle
1. **No URL available**: Log warning, notify user without opening browser
2. **Browser open fails**: Log error, notify user of failure
3. **Multiple rapid crashes**: Each crash triggers fallback (no debouncing needed)
4. **Empty URL string**: Treated same as None

### Integration Testing
```python
# Test scenarios:
# 1. Trigger crash with valid URL → should open browser
# 2. Trigger crash with no URL → should show notification only
# 3. Simulate browser open failure → should log error and notify
# 4. Check logging output for all scenarios
```

## Acceptance Checklist
- [ ] `_trigger_fallback()` method implemented with type hints
- [ ] Calls `_open_in_default_browser()` from Task 004
- [ ] Calls `_show_fallback_notification()` (placeholder for Task 006)
- [ ] `_on_render_process_terminated()` updated to call `_trigger_fallback()`
- [ ] All error paths handled (no URL, browser open fails)
- [ ] Logging at appropriate levels throughout flow
- [ ] No unhandled exceptions
- [ ] Tested with manual crash trigger
- [ ] Code follows Python 3.13+ type hints
- [ ] Docstrings complete for all new methods

## Files Modified
- `agents_runner/desktop_viewer/app.py` (only file modified)
