# Task: Design Fallback Mechanism for Browser Links

## Objective
Design a fallback mechanism to open links in the user's default web browser when QT web engine crashes.

## Context
Issue #140: When QWebEngineView crashes, we need to gracefully fallback to opening the link in the system default browser.

## Actions
1. Design the fallback trigger logic (detect crash/error state)
2. Plan how to extract the URL from the crashed web engine view
3. Choose method to open system default browser (webbrowser module, xdg-open, etc.)
4. Define user notification strategy (dialog, message, logging)
5. Document the design approach

## Success Criteria
- Clear design document for fallback mechanism
- Decision on crash detection approach
- Decision on browser opening method
- User notification strategy defined

## Dependencies
- Task 001 (understanding crash scenarios) - MUST complete first

## Estimated Effort
45 minutes

## Deliverables
- Create file: `.agents/audit/002-fallback-design.md` with design specifications

## Design Decisions Required

### 1. Crash Detection Method
**Options to evaluate:**
- A) Use `renderProcessTerminated` signal (recommended)
- B) Use `loadFinished` with error checking
- C) Combination approach

**Decision criteria:** Reliability, false positives, performance

### 2. URL Tracking Strategy
**Options:**
- A) Track URL on every load via `urlChanged` signal
- B) Read from `webEngineView.url()` when crash detected
- C) Store URL in instance variable

**Decision criteria:** Reliability when crashed, memory overhead

### 3. Browser Opening Method
**Options:**
- A) Python `webbrowser.open()` (cross-platform)
- B) Platform-specific: `xdg-open` (Linux), `open` (macOS), `start` (Windows)
- C) QDesktopServices.openUrl()

**Decision criteria:** Cross-platform support, reliability, dependencies

### 4. User Notification Approach
**Options:**
- A) QMessageBox (blocking)
- B) QSystemTrayIcon notification (non-blocking)
- C) Status bar message
- D) Logging only

**Decision criteria:** UX impact, visibility, design constraints (sharp corners)

## Output Format
```markdown
# Fallback Mechanism Design

## Architecture Overview
[High-level flow diagram in text]

## Component Specifications

### Crash Detection
- **Method chosen:** [Selection]
- **Implementation:** [Pseudo-code]

### URL Tracking
- **Method chosen:** [Selection]
- **Implementation:** [Pseudo-code]

### Browser Opening
- **Method chosen:** [Selection]
- **Dependencies:** [Library/module]
- **Error handling:** [Approach]

### User Notification
- **Method chosen:** [Selection]
- **Message text:** [Exact text]
- **Styling:** [Design constraints applied]

## Edge Cases Handled
1. [Edge case and solution]

## Non-Goals / Future Work
- [Items explicitly out of scope]
```
