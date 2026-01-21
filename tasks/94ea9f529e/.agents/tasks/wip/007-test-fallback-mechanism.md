# Task: Test Fallback Mechanism

## Objective
Verify the fallback mechanism works correctly across different crash scenarios.

## Context
Issue #140: Ensure fallback to default browser works reliably when QT web engine crashes.

## Actions
1. Test with simulated crash (force render process termination)
2. Test with network failure scenarios
3. Test with invalid URLs
4. Test on different platforms (if available)
5. Verify URL opens correctly in default browser
6. Verify user notification appears
7. Check logs for proper error recording

## Success Criteria
- Fallback triggers correctly in crash scenarios
- URL opens in default browser successfully
- User notification appears as expected
- No exceptions or errors in logs
- Works on primary target platform

## Dependencies
- Task 006 (user notification completed) - MUST complete first

## Estimated Effort
1 hour

## Test Plan Specifications

### Test Environment Setup
```bash
# 1. Ensure desktop viewer is running
cd agents_runner/desktop_viewer
python app.py  # or however it's launched

# 2. Enable debug logging
export LOG_LEVEL=DEBUG  # or configure in app

# 3. Identify test URLs
# - Valid URL: https://www.example.com
# - Heavy page: https://www.theverge.com (lots of media)
# - Invalid: https://invalid-url-that-does-not-exist-12345.com
```

### Test Cases

#### TC1: Normal Crash with Valid URL
**Objective**: Verify fallback works when render process terminates

**Steps**:
1. Launch desktop viewer
2. Navigate to: `https://www.example.com`
3. Force crash (method depends on QT version):
   - Option A: Navigate to `chrome://crash` (if supported)
   - Option B: Manually trigger `renderProcessTerminated` signal
   - Option C: Use QT inspector to kill render process
4. Observe behavior

**Expected Results**:
- [ ] Crash is logged: "Render process terminated: status=..."
- [ ] Fallback is triggered: "Triggering fallback: Web viewer crashed"
- [ ] Browser opens with `https://www.example.com`
- [ ] Notification appears with message about crash
- [ ] No unhandled exceptions

**Actual Results**:
```
[Document findings here during test execution]
```

---

#### TC2: Crash with No URL (Edge Case)
**Objective**: Verify graceful handling when crash occurs before URL is set

**Steps**:
1. Launch desktop viewer (no navigation yet)
2. Force crash before loading any URL
3. Observe behavior

**Expected Results**:
- [ ] Warning logged: "Fallback triggered but no URL available"
- [ ] Notification appears: "Web viewer crashed - No URL available"
- [ ] No browser window opens
- [ ] No exceptions

**Actual Results**:
```
[Document findings here]
```

---

#### TC3: Browser Opener Fails
**Objective**: Verify error handling when default browser fails to open

**Steps**:
1. Mock `_open_in_default_browser()` to return False (temporary code change)
2. Trigger crash with valid URL
3. Observe behavior

**Expected Results**:
- [ ] Error logged: "Fallback failed: [URL]"
- [ ] Notification shows failure message with URL
- [ ] User is told to copy/paste URL manually
- [ ] No exceptions

**Actual Results**:
```
[Document findings here]
```

---

#### TC4: Load Failure (Non-Crash)
**Objective**: Verify behavior on network/load failures

**Steps**:
1. Navigate to invalid URL: `https://invalid-url-12345.com`
2. Wait for load failure
3. Observe behavior

**Expected Results**:
- [ ] Warning logged: "Page load failed: [URL]"
- [ ] Determine: Should this trigger fallback? (Check design doc)
- [ ] Behavior matches design decision

**Actual Results**:
```
[Document findings here]
```

---

#### TC5: Rapid Multiple Crashes
**Objective**: Verify system handles multiple crashes without breaking

**Steps**:
1. Navigate to URL 1, force crash
2. Immediately navigate to URL 2, force crash
3. Navigate to URL 3, force crash
4. Observe behavior

**Expected Results**:
- [ ] Each crash triggers separate fallback
- [ ] All three URLs open in browser (three tabs/windows)
- [ ] All three notifications appear
- [ ] No crashes or exceptions in viewer app

**Actual Results**:
```
[Document findings here]
```

---

### Cross-Platform Testing (if available)

#### Linux
- [ ] Test on Linux (primary platform?)
- [ ] Verify `xdg-open` or equivalent opens browser
- [ ] Check notification styling (sharp corners)

#### macOS
- [ ] Test on macOS (if available)
- [ ] Verify `open` command works
- [ ] Check notification appearance

#### Windows
- [ ] Test on Windows (if available)
- [ ] Verify `start` command works
- [ ] Check notification appearance

### Log Analysis Checklist
Review logs after all tests:
- [ ] DEBUG level: URL tracking working (`_on_url_changed`)
- [ ] ERROR level: Crashes logged with details
- [ ] INFO level: Successful browser opens logged
- [ ] WARNING level: Edge cases logged (no URL, load failures)
- [ ] No unexpected ERROR or EXCEPTION messages
- [ ] Log messages are clear and actionable

### Performance Considerations
- [ ] Fallback triggers within 2 seconds of crash
- [ ] Browser opens within 3 seconds of fallback trigger
- [ ] Notification appears immediately after browser open attempt
- [ ] No UI freeze or blocking behavior

## Test Execution Instructions

### Manual Testing
```bash
# 1. Create test log file
touch test-results.log

# 2. Run each test case, document in test-results.log

# 3. Collect logs
cp ~/.local/share/agents_runner/logs/* ./test-logs/
# (adjust log path as needed)
```

### Automated Testing (Optional Enhancement)
```python
# Create test file: tests/test_fallback_mechanism.py
import pytest
from unittest.mock import Mock, patch

def test_crash_with_url():
    """Test TC1: Normal crash with valid URL"""
    viewer = DesktopViewer()
    viewer._current_url = "https://example.com"
    
    with patch.object(viewer, '_open_in_default_browser') as mock_open:
        mock_open.return_value = True
        viewer._trigger_fallback("Test crash")
        
        mock_open.assert_called_once_with("https://example.com")

# Add more test cases...
```

## Acceptance Checklist
- [ ] All test cases executed and documented
- [ ] TC1 (normal crash) passes
- [ ] TC2 (no URL) passes
- [ ] TC3 (browser fails) passes
- [ ] TC4 (load failure) behaves as designed
- [ ] TC5 (multiple crashes) passes
- [ ] Logs reviewed and contain expected messages
- [ ] No unexpected errors or exceptions
- [ ] Performance acceptable (< 5 seconds end-to-end)
- [ ] Notification styling verified (sharp corners)
- [ ] Cross-platform testing completed (at least primary platform)

## Deliverables
- Create file: `.agents/audit/007-test-results.md`
  - Test execution results for each test case
  - Screenshots of notifications (if possible)
  - Log excerpts showing correct behavior
  - Any issues found and resolution
  - Platform compatibility notes

## Issues Found
Document any bugs or issues discovered:
```markdown
### Issue 1: [Title]
- **Severity**: Critical/High/Medium/Low
- **Description**: [What went wrong]
- **Steps to Reproduce**: [How to trigger]
- **Expected**: [What should happen]
- **Actual**: [What actually happened]
- **Fix Required**: [What needs to change]
```
