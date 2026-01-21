# Task: Document Fallback Feature

## Objective
Document the new fallback mechanism for future reference and user knowledge.

## Context
Issue #140: Document how the fallback mechanism works for maintainers and users.

## Actions
1. Update code comments in desktop_viewer/app.py
2. Add docstrings to new functions
3. Update AGENTS.md if relevant
4. Add brief user-facing note (if user docs exist)
5. Document known limitations or edge cases

## Success Criteria
- Code is well-commented
- Functions have clear docstrings with type hints
- Any relevant documentation files are updated
- Future maintainers can understand the implementation

## Dependencies
- Task 007 (testing completed) - MUST complete first to document actual behavior

## Estimated Effort
30 minutes

## Documentation Specifications

### 1. Code Documentation (In-file)

#### File: `agents_runner/desktop_viewer/app.py`

**Add Module-Level Comment** (at top of relevant section):
```python
# ==============================================================================
# QT Web Engine Crash Fallback Mechanism (Issue #140)
# ==============================================================================
# When the QT web engine crashes, we automatically fallback to opening the
# URL in the user's default system browser. This provides graceful degradation
# and ensures users can still access the content.
#
# Components:
# - URL tracking: _current_url instance variable, updated via urlChanged signal
# - Crash detection: renderProcessTerminated signal handler
# - Browser opener: _open_in_default_browser() method using webbrowser module
# - User notification: _show_fallback_notification() via QMessageBox
# - Integration: _trigger_fallback() orchestrates the fallback flow
#
# See methods below for implementation details.
# ==============================================================================
```

**Verify All Methods Have Docstrings**:
- [x] `_on_url_changed()` - Task 003
- [x] `_on_render_process_terminated()` - Task 003  
- [x] `_on_load_finished()` - Task 003
- [x] `_open_in_default_browser()` - Task 004
- [x] `_trigger_fallback()` - Task 005
- [x] `_show_fallback_notification()` - Task 006

Ensure each docstring includes:
- One-line summary
- Args section with type information
- Returns section (if applicable)
- Brief description of behavior
- Example usage (where helpful)

### 2. Architecture Documentation

#### Create: `.agents/audit/008-fallback-architecture.md`

```markdown
# QT Web Engine Fallback Mechanism - Architecture

## Overview
Provides graceful degradation when QT web engine crashes by automatically 
opening URLs in the user's default system browser.

## Component Diagram
```
User Action
    ↓
QWebEngineView loads URL
    ↓
urlChanged signal → _on_url_changed() → stores _current_url
    ↓
[Render process crashes]
    ↓
renderProcessTerminated signal → _on_render_process_terminated()
    ↓
_trigger_fallback("Web viewer crashed")
    ↓
_open_in_default_browser(_current_url)
    ↓
_show_fallback_notification(success, reason, url)
    ↓
User sees notification + browser opens with URL
```

## Data Flow
1. **URL Tracking**: Every URL change is captured and stored in `_current_url`
2. **Crash Detection**: QT signals when render process terminates
3. **Fallback Trigger**: Handler checks for URL, initiates browser open
4. **Browser Open**: Python `webbrowser` module handles cross-platform opening
5. **User Notification**: QMessageBox informs user of what happened

## Error Handling
- **No URL available**: Logs warning, shows notification without opening browser
- **Browser open fails**: Logs error, shows failure notification with manual instructions
- **Multiple crashes**: Each crash independently triggers fallback

## Design Constraints Met
- **Minimal changes**: Single file modified (app.py)
- **Sharp corners**: StyleSheet enforces border-radius: 0px
- **Python 3.13+ type hints**: All methods use modern type syntax

## Known Limitations
1. Cannot recover QT web engine after crash - requires app restart
2. No crash prevention, only graceful fallback
3. Notification is modal (blocks other actions until dismissed)
4. No user preference storage (can't disable notifications persistently)

## Future Enhancements
- Automatic QT web engine restart after crash
- User preference to disable notifications
- Crash analytics to identify common patterns
- Fallback to embedded lightweight browser (e.g., tkinter HTML viewer)

## Testing Coverage
- TC1: Normal crash with valid URL ✓
- TC2: Crash with no URL ✓
- TC3: Browser opener failure ✓
- TC4: Load failure handling ✓
- TC5: Multiple rapid crashes ✓

See `.agents/audit/007-test-results.md` for detailed test results.

## Maintainer Notes
- All crash handling code is in `app.py`
- Signal handlers follow QT naming: `_on_<signal_name>()`
- Private methods use leading underscore
- Logging uses module-level logger at appropriate levels
```

### 3. User-Facing Documentation

#### Check for Existing User Documentation
```bash
# Search for user docs
find . -name "README.md" -o -name "USER_GUIDE.md" -o -name "docs"
```

#### If README.md exists, add section:
```markdown
## Web Viewer Crash Handling

The desktop viewer includes automatic fallback handling for web engine crashes.

**What happens when the web viewer crashes:**
1. The application detects the crash automatically
2. Your browser opens with the URL you were viewing
3. A notification explains what happened
4. You can continue working without restarting the app

**Note:** If the browser fails to open automatically, the notification will 
display the URL so you can copy and paste it manually.
```

### 4. Code Comments (Inline)

**Add comments for non-obvious behavior**:
```python
# Store URL before navigation completes - needed for crash recovery
self._current_url = url.toString()

# Non-blocking notification - user can dismiss when ready
msg_box.setWindowModality(Qt.WindowModality.NonModal)

# webbrowser module handles platform differences (xdg-open, open, start)
webbrowser.open(url)
```

### 5. CHANGELOG Entry (if exists)

```markdown
## [Version X.Y.Z] - YYYY-MM-DD

### Added
- Automatic fallback to default browser when QT web engine crashes (#140)
  - Crash detection via renderProcessTerminated signal
  - Cross-platform browser opening with webbrowser module
  - User notification with crash details
  - Comprehensive logging of crash events

### Fixed
- Desktop viewer no longer becomes unusable when web engine crashes (#140)
```

## Documentation Checklist

### Code Documentation
- [ ] Module-level comment added explaining fallback mechanism
- [ ] All methods have complete docstrings
- [ ] Type hints verified on all parameters and returns
- [ ] Inline comments added for non-obvious behavior
- [ ] Complex logic has explanatory comments

### Architecture Documentation
- [ ] `.agents/audit/008-fallback-architecture.md` created
- [ ] Component diagram (text-based) included
- [ ] Data flow documented
- [ ] Error handling paths explained
- [ ] Known limitations listed
- [ ] Future enhancements suggested

### User Documentation
- [ ] Searched for existing user docs
- [ ] README.md updated (if exists)
- [ ] USER_GUIDE.md updated (if exists)
- [ ] CHANGELOG updated (if exists)

### Maintenance Documentation
- [ ] Signal handler naming conventions documented
- [ ] Logging strategy explained
- [ ] File locations clearly stated
- [ ] Dependencies listed (none added)

## Acceptance Criteria
- [ ] All code has docstrings with type hints
- [ ] Architecture document created and complete
- [ ] User documentation updated (where applicable)
- [ ] Known limitations documented
- [ ] Future maintainers can understand implementation without asking
- [ ] No undocumented "magic" behavior

## Deliverables
1. **Updated**: `agents_runner/desktop_viewer/app.py` with complete documentation
2. **Created**: `.agents/audit/008-fallback-architecture.md`
3. **Updated**: README.md or similar (if found)
4. **Updated**: CHANGELOG (if found)

## Validation
Have another developer review the documentation:
- [ ] Can understand what the fallback does without reading code
- [ ] Can locate the implementation quickly
- [ ] Can identify edge cases and limitations
- [ ] Can extend or modify the feature with confidence
