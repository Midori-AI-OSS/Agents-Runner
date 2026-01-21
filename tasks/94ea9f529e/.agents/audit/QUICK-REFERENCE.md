# Task Execution Quick Reference

## Overview
9 tasks to implement QT web engine crash fallback mechanism for Issue #140.
**Estimated Total Time**: 6.5-7 hours

## Before You Start

### Prerequisites Checklist
- [ ] Verify QT version (PyQt5 or PyQt6)
- [ ] Confirm file exists: `agents_runner/desktop_viewer/app.py`
- [ ] Create audit directory: `mkdir -p .agents/audit`
- [ ] Review Issue #140 for context
- [ ] Set up development environment

### Quick Setup
```bash
# Create audit directory
mkdir -p .agents/audit

# Verify target file exists
ls -l agents_runner/desktop_viewer/app.py

# Check QT version
python -c "import PyQt6; print('PyQt6')" 2>/dev/null || \
python -c "import PyQt5; print('PyQt5')" 2>/dev/null
```

---

## Task Execution Checklist

### ✅ Task 001: Investigate QT Crash Scenarios (30 min)
**Do**:
- [ ] Read `agents_runner/desktop_viewer/app.py`
- [ ] Identify QWebEngineView usage
- [ ] Document QT signals available
- [ ] List crash scenarios

**Output**: Create `.agents/audit/001-crash-scenarios.md`

**Key Signals to Find**:
- `renderProcessTerminated`
- `loadFinished`
- `urlChanged`

---

### ✅ Task 002: Design Fallback Mechanism (45 min)
**Do**:
- [ ] Review findings from Task 001
- [ ] Make 4 design decisions (see task file)
- [ ] Document architecture approach
- [ ] Define error handling strategy

**Output**: Create `.agents/audit/002-fallback-design.md`

**Decisions Required**:
1. Crash detection method
2. URL tracking strategy
3. Browser opening method
4. User notification approach

**⚠️ CHECKPOINT**: Review design before coding

---

### ✅ Task 003: Implement Crash Detection (60 min)
**Do**:
- [ ] Add `_current_url` instance variable
- [ ] Connect `urlChanged` signal
- [ ] Implement `_on_url_changed()` handler
- [ ] Connect `renderProcessTerminated` signal
- [ ] Implement `_on_render_process_terminated()` handler
- [ ] Add logging
- [ ] Add type hints

**File Modified**: `agents_runner/desktop_viewer/app.py`

**Quick Test**:
```python
# Verify URL tracking is working
# Navigate to a URL and check logs for "URL changed" messages
```

---

### ✅ Task 004: Implement Browser Opener (30 min)
**Do**:
- [ ] Add `import webbrowser`
- [ ] Implement `_open_in_default_browser()` method
- [ ] Add error handling (None/empty URL)
- [ ] Add logging
- [ ] Add type hints and docstring

**File Modified**: `agents_runner/desktop_viewer/app.py`

**Quick Test**:
```python
# Test in Python REPL:
import webbrowser
webbrowser.open("https://example.com")
# Browser should open
```

---

### ✅ Task 005: Integrate Fallback (45 min)
**Do**:
- [ ] Implement `_trigger_fallback()` method
- [ ] Update `_on_render_process_terminated()` to call fallback
- [ ] Add placeholder `_show_fallback_notification()`
- [ ] Handle error paths (no URL, browser fails)
- [ ] Add comprehensive logging

**File Modified**: `agents_runner/desktop_viewer/app.py`

**⚠️ CHECKPOINT**: Manual smoke test
```bash
# Force a crash and verify:
# 1. Browser opens with URL
# 2. Logs show correct messages
# 3. No exceptions thrown
```

---

### ✅ Task 006: Add User Notification (30 min)
**Do**:
- [ ] Import QMessageBox
- [ ] Implement `_show_fallback_notification()` fully
- [ ] Add StyleSheet for sharp corners
- [ ] Handle 3 scenarios (success, failure, no URL)
- [ ] Make non-blocking (NonModal)

**File Modified**: `agents_runner/desktop_viewer/app.py`

**Style to Apply**:
```python
border-radius: 0px  # Sharp corners
```

---

### ✅ Task 007: Test Fallback Mechanism (90 min)
**Do**:
- [ ] Run TC1: Normal crash with URL
- [ ] Run TC2: Crash without URL
- [ ] Run TC3: Browser opener fails
- [ ] Run TC4: Load failure
- [ ] Run TC5: Multiple crashes
- [ ] Review logs for errors
- [ ] Document results

**Output**: Create `.agents/audit/007-test-results.md`

**Test Commands**:
```bash
# Launch app
python agents_runner/desktop_viewer/app.py

# Force crash methods:
# 1. Navigate to chrome://crash (if supported)
# 2. Manually trigger signal in debugger
# 3. Kill render process
```

**⚠️ CHECKPOINT**: All tests passing

---

### ✅ Task 008: Document Feature (30 min)
**Do**:
- [ ] Add module-level comment to app.py
- [ ] Verify all docstrings complete
- [ ] Create architecture document
- [ ] Update README (if exists)
- [ ] Update CHANGELOG (if exists)

**Output**: Create `.agents/audit/008-fallback-architecture.md`

**Quick Verification**:
```bash
# Check docstrings
grep -A 5 "def _on_url_changed" agents_runner/desktop_viewer/app.py
grep -A 5 "def _trigger_fallback" agents_runner/desktop_viewer/app.py
```

---

### ✅ Task 009: Create Close Summary (15 min)
**Do**:
- [ ] Fill in summary template from task file
- [ ] List all files modified
- [ ] Summarize test results
- [ ] Document known limitations
- [ ] Prepare GitHub comment

**Output**: Create `.agents/audit/009-issue-140-close-summary.md`

**Final Checklist**:
- [ ] All 9 tasks complete
- [ ] All 5 audit documents created
- [ ] All tests passing
- [ ] Code committed
- [ ] Ready to close Issue #140

---

## Files Modified (Expected)

### Source Code
- `agents_runner/desktop_viewer/app.py` (~150-200 lines added)

### Documentation Created
- `.agents/audit/001-crash-scenarios.md`
- `.agents/audit/002-fallback-design.md`
- `.agents/audit/007-test-results.md`
- `.agents/audit/008-fallback-architecture.md`
- `.agents/audit/009-issue-140-close-summary.md`
- `.agents/audit/AUDIT-REPORT.md` (this audit)

---

## Common Issues & Solutions

### Issue: Can't find QWebEngineView
**Solution**: Check if using PyQt5 or PyQt6, adjust imports
```python
# PyQt6
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEnginePage

# PyQt5
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtWebEngineCore import QWebEnginePage
```

### Issue: Signal not connecting
**Solution**: Check signal syntax
```python
# Correct
self.web_view.urlChanged.connect(self._on_url_changed)

# Incorrect (missing .connect)
self.web_view.urlChanged(self._on_url_changed)
```

### Issue: Browser not opening
**Solution**: Test webbrowser module directly
```bash
python -c "import webbrowser; webbrowser.open('https://example.com')"
```

### Issue: Type hints causing errors
**Solution**: Ensure Python 3.10+ for `|` syntax, or use `Optional`
```python
# Modern (Python 3.10+)
def func(url: str | None) -> bool:

# Legacy
from typing import Optional
def func(url: Optional[str]) -> bool:
```

---

## Time Tracking Template

| Task | Estimated | Actual | Notes |
|------|-----------|--------|-------|
| 001  | 30 min    |        |       |
| 002  | 45 min    |        |       |
| 003  | 60 min    |        |       |
| 004  | 30 min    |        |       |
| 005  | 45 min    |        |       |
| 006  | 30 min    |        |       |
| 007  | 90 min    |        |       |
| 008  | 30 min    |        |       |
| 009  | 15 min    |        |       |
| **Total** | **6.5 hrs** |    |       |

---

## Quality Gates

### After Task 003
- [ ] Code compiles without errors
- [ ] URL tracking logs appear
- [ ] Type hints validate with mypy (if using)

### After Task 005
- [ ] Can trigger manual crash
- [ ] Browser opens automatically
- [ ] Logs show complete flow
- [ ] No exceptions

### After Task 006
- [ ] Notification appears on crash
- [ ] Notification has sharp corners
- [ ] Message is clear and helpful

### After Task 007
- [ ] All 5 test cases pass
- [ ] Test results documented
- [ ] No critical issues found

### Final (After Task 009)
- [ ] All code documented
- [ ] All audit files created
- [ ] Issue close summary complete
- [ ] Ready to merge/deploy

---

## Getting Help

### If Stuck on Design (Task 002)
- Review Task 001 findings
- Consider user experience impact
- Choose simplest reliable option
- Document decision rationale

### If Stuck on Implementation (Tasks 003-006)
- Review code examples in task files
- Check QT version compatibility
- Test components in isolation
- Add debug logging liberally

### If Tests Fail (Task 007)
- Check logs for exceptions
- Verify signal connections
- Test browser opener separately
- Simplify crash trigger method

---

## Success Indicators

You're done when:
- ✅ App doesn't crash user workflow
- ✅ URLs open in browser on crash
- ✅ Users understand what happened
- ✅ Logs capture crash details
- ✅ All tests pass
- ✅ Code is documented
- ✅ Issue #140 can be closed

**Good luck!** 🚀
