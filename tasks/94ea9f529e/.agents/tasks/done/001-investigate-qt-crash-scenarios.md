# Task: Investigate QT Web Engine Crash Scenarios

## Objective
Understand when and why the QT web engine crashes in the desktop viewer.

## Context
Issue #140: Desktop crashes - The QT web engine occasionally crashes and we need a fallback mechanism.

## Actions
1. Review the `agents_runner/desktop_viewer/app.py` file
2. Check for existing error handling around QWebEngineView
3. Identify crash scenarios (e.g., network issues, memory issues, rendering failures)
4. Look for existing crash logs or error patterns in the code
5. Document common crash triggers

## Success Criteria
- List of potential crash scenarios documented
- Understanding of current error handling (if any)
- Clear picture of where fallback is needed

## Dependencies
None

## Estimated Effort
30 minutes

## Deliverables
- Create file: `.agents/audit/001-crash-scenarios.md` with findings
  - List of crash scenarios discovered
  - Current error handling analysis
  - QT signals that can be hooked for crash detection
  - Recommendations for crash detection implementation

## Technical Details
**Key QT Signals to Investigate:**
- `renderProcessTerminated(terminationStatus, exitCode)` - Primary crash signal
- `loadFinished(bool ok)` - Detects load failures
- `loadStarted()` - Track when loads begin

**File Locations:**
- Primary file: `agents_runner/desktop_viewer/app.py`
- Look for: QWebEngineView, QWebEnginePage usage

**Output Format:**
```markdown
# QT Web Engine Crash Investigation Results

## Crash Scenarios Found
1. [Scenario name]: [Description and trigger]

## Current Error Handling
- [Current implementation analysis]

## Recommended Detection Approach
- [Technical recommendations]
```
