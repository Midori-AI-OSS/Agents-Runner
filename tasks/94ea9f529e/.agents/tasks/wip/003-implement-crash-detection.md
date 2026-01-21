# Task: Implement QT Web Engine Crash Detection

## Objective
Add crash detection to the QWebEngineView in desktop_viewer/app.py.

## Context
Issue #140: Need to detect when QT web engine crashes to trigger fallback mechanism.

## Actions
1. Add signal handlers for QWebEngineView crash events
2. Implement renderProcessTerminated signal handler
3. Add loadFinished error detection
4. Store the current URL before potential crash
5. Add logging for crash events

## Success Criteria
- Crash detection implemented in desktop_viewer/app.py
- Current URL is tracked and accessible
- Crash events are logged
- Code follows Python 3.13+ type hints standard
- Changes are minimal (design constraint)

## Dependencies
- Task 002 (design completed) - MUST review design doc first

## Estimated Effort
1 hour

## Implementation Specifications

### File to Modify
`agents_runner/desktop_viewer/app.py`

### Code Changes Required

#### 1. Add Instance Variable for URL Tracking
```python
class DesktopViewer:  # Or whatever the class name is
    def __init__(self):
        self._current_url: str | None = None
        # ... existing code
```

#### 2. Connect Crash Signal Handler
```python
def setup_webengine(self):
    # ... existing setup code
    
    # Track URL changes
    self.web_view.urlChanged.connect(self._on_url_changed)
    
    # Detect crashes
    self.web_view.page().renderProcessTerminated.connect(
        self._on_render_process_terminated
    )
    
    # Detect load failures
    self.web_view.loadFinished.connect(self._on_load_finished)
```

#### 3. Implement Signal Handlers
```python
def _on_url_changed(self, url: QUrl) -> None:
    """Track current URL for crash recovery."""
    self._current_url = url.toString()
    logger.debug(f"URL changed: {self._current_url}")

def _on_render_process_terminated(
    self,
    termination_status: QWebEnginePage.RenderProcessTerminationStatus,
    exit_code: int
) -> None:
    """Handle render process crashes."""
    logger.error(
        f"Render process terminated: status={termination_status}, "
        f"exit_code={exit_code}, url={self._current_url}"
    )
    # Fallback logic will be added in Task 005
    self._trigger_fallback()

def _on_load_finished(self, ok: bool) -> None:
    """Detect load failures."""
    if not ok:
        logger.warning(f"Page load failed: {self._current_url}")
        # May trigger fallback depending on design
```

### Type Hints Required
- Import: `from typing import Optional` (if not using `|` syntax)
- Import: `from PyQt6.QtWebEngineCore import QWebEnginePage` (or PyQt5)
- Use Python 3.13+ style: `str | None` instead of `Optional[str]`

### Logging Setup
- Use existing logger or add: `import logging; logger = logging.getLogger(__name__)`
- Log levels:
  - `DEBUG`: URL changes, normal operations
  - `WARNING`: Load failures
  - `ERROR`: Render process termination

### Testing Plan
- Manual test: Force crash by loading problematic URL
- Verify logging output contains correct information
- Verify `_current_url` is populated before crash

## Acceptance Checklist
- [ ] Instance variable `_current_url` added with type hint
- [ ] Signal handlers connected in initialization
- [ ] All handler methods implement proper type hints
- [ ] Logging added at appropriate levels
- [ ] No existing functionality broken
- [ ] Code follows project style (PEP 8)
- [ ] Placeholder for `_trigger_fallback()` added (implemented in Task 005)
