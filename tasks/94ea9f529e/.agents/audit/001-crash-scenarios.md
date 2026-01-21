# QT Web Engine Crash Investigation Results

## Executive Summary
This document outlines common crash scenarios in QT WebEngine applications, detection mechanisms, and implementation recommendations for a fallback system in the desktop viewer.

---

## Crash Scenarios Found

### 1. Render Process Termination
**Description**: The Chromium render process crashes unexpectedly  
**Trigger**: Memory exhaustion, GPU driver issues, or renderer bugs  
**Severity**: HIGH  
**Frequency**: Common in heavy web applications

**Technical Details**:
- Signal: `renderProcessTerminated(terminationStatus, exitCode)`
- Exit codes vary by termination reason:
  - `NormalTerminationStatus` (0): Clean shutdown
  - `AbnormalTerminationStatus` (1): Crash or forced kill
  - `CrashedTerminationStatus` (2): Segfault or similar
  - `KilledTerminationStatus` (3): Killed by OS (OOM killer)

### 2. Network Load Failures
**Description**: Web content fails to load due to network issues  
**Trigger**: DNS failures, connection timeouts, SSL errors  
**Severity**: MEDIUM  
**Frequency**: Moderate, depends on network stability

**Technical Details**:
- Signal: `loadFinished(bool ok)` where ok=false
- Can detect via: `QWebEnginePage::loadingChanged(const QWebEngineLoadingInfo &loadingInfo)`
- Error types include: DNS resolution, connection refused, timeout

### 3. Out of Memory (OOM) Crashes
**Description**: Application runs out of memory while rendering complex pages  
**Trigger**: Large DOM trees, memory leaks, excessive JavaScript heap  
**Severity**: HIGH  
**Frequency**: Rare but catastrophic

**Technical Details**:
- Often results in renderProcessTerminated with KilledTerminationStatus
- May not always trigger signals if main process is affected
- Platform-dependent (Linux OOM killer, Windows memory limits)

### 4. GPU/Graphics Driver Issues
**Description**: Graphics driver crashes or hangs during hardware acceleration  
**Trigger**: Outdated drivers, incompatible GPU, complex WebGL content  
**Severity**: MEDIUM  
**Frequency**: Platform-specific, more common on Linux

**Technical Details**:
- May cause render process to hang or crash
- Can be mitigated with software rendering fallback
- Detection: renderProcessTerminated or hung render detection

### 5. JavaScript Execution Errors
**Description**: Uncaught JavaScript exceptions or infinite loops  
**Trigger**: Buggy web application code, compatibility issues  
**Severity**: LOW to MEDIUM  
**Frequency**: Common but usually non-fatal

**Technical Details**:
- May not crash render process but can freeze UI
- Detection: `javaScriptConsoleMessage` signal for errors
- Timeout mechanisms needed for hung scripts

### 6. SSL/Certificate Errors
**Description**: HTTPS pages fail to load due to certificate issues  
**Trigger**: Expired certificates, self-signed certificates, invalid chains  
**Severity**: LOW  
**Frequency**: Common in development environments

**Technical Details**:
- Signal: `loadFinished(false)` with SSL error codes
- Can be detected via: `QWebEngineCertificateError`
- May require user interaction or automatic bypass

### 7. Plugin/Extension Crashes
**Description**: Browser plugins or extensions crash  
**Trigger**: Flash, PDF viewers, or other NPAPI plugins (deprecated in modern QT)  
**Severity**: LOW  
**Frequency**: Rare in modern QT WebEngine

**Technical Details**:
- Less common with QT WebEngine (uses Chromium architecture)
- Isolated from main render process
- Detection via renderProcessTerminated

---

## Current Error Handling

### Expected Implementation Status
Without access to the actual codebase, typical QT WebEngine applications have:

#### Minimal Error Handling (Common)
```python
# Basic QWebEngineView setup
view = QWebEngineView()
view.load(QUrl("https://example.com"))
```
**Issues**:
- ❌ No crash detection
- ❌ No error recovery
- ❌ No user notification
- ❌ Application becomes unresponsive on crash

#### Intermediate Error Handling (Some projects)
```python
# With basic load error handling
def on_load_finished(ok):
    if not ok:
        print("Failed to load page")

view.loadFinished.connect(on_load_finished)
```
**Issues**:
- ⚠️ Detects load failures only
- ❌ No render process crash handling
- ❌ No fallback mechanism
- ⚠️ Limited error context

#### Advanced Error Handling (Rare)
```python
# With render process monitoring
def on_render_terminated(status, code):
    if status == QWebEnginePage.AbnormalTerminationStatus:
        # Attempt recovery
        view.reload()

page.renderProcessTerminated.connect(on_render_terminated)
```
**Issues**:
- ✅ Detects render crashes
- ⚠️ Recovery attempts same page (may crash again)
- ❌ No fallback to external browser
- ⚠️ Limited user notification

---

## QT Signals for Crash Detection

### Primary Signals (Essential)

#### 1. renderProcessTerminated(terminationStatus, exitCode)
**Purpose**: Detect when render process crashes  
**Source**: `QWebEnginePage`  
**Priority**: CRITICAL

```python
def handle_render_crash(status, exit_code):
    """
    Handle render process termination.
    
    Args:
        status: QWebEnginePage.RenderProcessTerminationStatus
        exit_code: int - Process exit code
    """
    status_map = {
        QWebEnginePage.NormalTerminationStatus: "Normal",
        QWebEnginePage.AbnormalTerminationStatus: "Abnormal",
        QWebEnginePage.CrashedTerminationStatus: "Crashed",
        QWebEnginePage.KilledTerminationStatus: "Killed"
    }
    
    logging.error(
        f"Render process terminated: {status_map.get(status, 'Unknown')} "
        f"(exit code: {exit_code})"
    )
    
    # Trigger fallback mechanism
    if status != QWebEnginePage.NormalTerminationStatus:
        trigger_fallback()

page.renderProcessTerminated.connect(handle_render_crash)
```

#### 2. loadFinished(bool ok)
**Purpose**: Detect page load failures  
**Source**: `QWebEngineView` or `QWebEnginePage`  
**Priority**: HIGH

```python
def handle_load_finished(success):
    """
    Handle page load completion.
    
    Args:
        success: bool - True if load succeeded
    """
    if not success:
        current_url = view.url().toString()
        logging.warning(f"Failed to load: {current_url}")
        
        # Check if this is a persistent failure
        if retry_count >= MAX_RETRIES:
            trigger_fallback()
        else:
            schedule_retry()

view.loadFinished.connect(handle_load_finished)
```

### Secondary Signals (Recommended)

#### 3. loadStarted()
**Purpose**: Track load attempts and detect hangs  
**Source**: `QWebEngineView` or `QWebEnginePage`  
**Priority**: MEDIUM

```python
load_start_time = None

def handle_load_started():
    """Track when page load begins."""
    global load_start_time
    load_start_time = time.time()
    logging.info("Page load started")

def check_load_timeout():
    """Check if load is taking too long."""
    if load_start_time and (time.time() - load_start_time) > LOAD_TIMEOUT:
        logging.error("Page load timeout exceeded")
        trigger_fallback()

view.loadStarted.connect(handle_load_started)
# Set up periodic timeout checker with QTimer
```

#### 4. loadProgress(int progress)
**Purpose**: Monitor load progress and detect stalls  
**Source**: `QWebEngineView` or `QWebEnginePage`  
**Priority**: LOW

```python
last_progress = 0
stall_count = 0

def handle_load_progress(progress):
    """Monitor load progress."""
    global last_progress, stall_count
    
    if progress == last_progress:
        stall_count += 1
        if stall_count > STALL_THRESHOLD:
            logging.warning("Load appears stalled")
    else:
        stall_count = 0
    
    last_progress = progress

view.loadProgress.connect(handle_load_progress)
```

#### 5. javaScriptConsoleMessage(level, message, lineNumber, sourceID)
**Purpose**: Monitor JavaScript errors  
**Source**: `QWebEnginePage` (override method)  
**Priority**: LOW

```python
class CustomWebPage(QWebEnginePage):
    def javaScriptConsoleMessage(self, level, message, line_number, source_id):
        """Log JavaScript console messages."""
        if level == QWebEnginePage.ErrorMessageLevel:
            logging.warning(
                f"JS Error at {source_id}:{line_number}: {message}"
            )
        
        # Count critical errors
        if is_critical_js_error(message):
            increment_error_count()
            if error_count >= ERROR_THRESHOLD:
                trigger_fallback()
```

---

## Recommended Detection Approach

### Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    Desktop Viewer                        │
│                                                          │
│  ┌────────────────────────────────────────────────┐    │
│  │          QWebEngineView                        │    │
│  │  ┌──────────────────────────────────────────┐  │    │
│  │  │       QWebEnginePage                     │  │    │
│  │  │                                          │  │    │
│  │  │  [Signals Connected]                    │  │    │
│  │  │  • renderProcessTerminated    ─────┐    │  │    │
│  │  │  • loadFinished               ─────┤    │  │    │
│  │  │  • loadStarted                ─────┤    │  │    │
│  │  └──────────────────────────────────────────┘  │    │
│  └────────────────────────────────────────────────┘    │
│                                           │             │
│                                           ▼             │
│  ┌────────────────────────────────────────────────┐    │
│  │       Crash Detection Manager                  │    │
│  │  • Aggregate signals                          │    │
│  │  • Track retry attempts                       │    │
│  │  • Decide on fallback trigger                 │    │
│  └────────────────────────────────────────────────┘    │
│                                           │             │
│                                           ▼             │
│  ┌────────────────────────────────────────────────┐    │
│  │       Fallback Handler                         │    │
│  │  • Show user notification                     │    │
│  │  • Open default browser                       │    │
│  │  • Log incident                               │    │
│  └────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
```

### Implementation Strategy

#### Phase 1: Basic Crash Detection (MVP)
1. **Connect renderProcessTerminated signal**
   - Handle all non-normal termination statuses
   - Log crash details with timestamp and URL
   - Trigger fallback immediately

2. **Connect loadFinished signal**
   - Track consecutive load failures
   - Implement retry logic with exponential backoff
   - Trigger fallback after N failures

#### Phase 2: Enhanced Detection
3. **Add timeout mechanism**
   - Use QTimer to detect hung loads
   - Set reasonable timeout (30-60 seconds)
   - Consider network conditions

4. **Implement retry logic**
   - Maximum 3 retry attempts
   - Exponential backoff: 1s, 2s, 4s
   - Clear retry counter on successful load

#### Phase 3: Advanced Monitoring
5. **Add health checks**
   - Periodic ping to verify render process
   - Monitor memory usage trends
   - Detect progressive degradation

6. **Implement graceful degradation**
   - Disable hardware acceleration on GPU errors
   - Reduce quality settings if performance degrades
   - Cache last known good state

### Decision Tree for Fallback Trigger

```
Is render process terminated?
├─ Yes, status != Normal → TRIGGER FALLBACK
└─ No
    ├─ Load failed?
    │   └─ Yes
    │       ├─ Retry count < MAX_RETRIES? → RETRY
    │       └─ Retry count >= MAX_RETRIES → TRIGGER FALLBACK
    └─ Load hanging?
        ├─ Duration > TIMEOUT? → TRIGGER FALLBACK
        └─ Duration <= TIMEOUT → CONTINUE WAITING
```

### Recommended Constants

```python
# Retry configuration
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 1.0  # seconds
RETRY_BACKOFF_MULTIPLIER = 2.0

# Timeout configuration
LOAD_TIMEOUT = 45.0  # seconds
RENDER_HANG_TIMEOUT = 30.0  # seconds

# Error thresholds
JS_ERROR_THRESHOLD = 10  # critical JS errors before fallback
LOAD_FAILURE_THRESHOLD = 3  # consecutive failures before fallback
```

### Error Context to Capture

```python
class CrashContext:
    """Store context about a crash for debugging."""
    
    def __init__(self):
        self.timestamp = datetime.now()
        self.url = None
        self.termination_status = None
        self.exit_code = None
        self.retry_count = 0
        self.load_failures = []
        self.js_errors = []
        self.memory_usage = None
        self.platform_info = None
    
    def to_dict(self):
        """Serialize for logging."""
        return {
            'timestamp': self.timestamp.isoformat(),
            'url': self.url,
            'termination_status': self.termination_status,
            'exit_code': self.exit_code,
            'retry_count': self.retry_count,
            'load_failures': len(self.load_failures),
            'js_errors': len(self.js_errors),
            'memory_usage_mb': self.memory_usage,
            'platform': self.platform_info
        }
```

---

## Implementation Recommendations

### 1. Create Crash Detection Manager Class
```python
class CrashDetectionManager:
    """
    Manages crash detection and fallback triggering.
    """
    
    def __init__(self, web_view: QWebEngineView):
        self.view = web_view
        self.page = web_view.page()
        self.retry_count = 0
        self.crash_context = CrashContext()
        self.fallback_callback = None
        
        self._connect_signals()
    
    def _connect_signals(self):
        """Connect all crash detection signals."""
        self.page.renderProcessTerminated.connect(
            self._on_render_terminated
        )
        self.view.loadFinished.connect(self._on_load_finished)
        self.view.loadStarted.connect(self._on_load_started)
    
    def set_fallback_callback(self, callback):
        """Set the function to call when fallback is triggered."""
        self.fallback_callback = callback
    
    def _trigger_fallback(self):
        """Trigger the fallback mechanism."""
        if self.fallback_callback:
            self.fallback_callback(self.crash_context)
```

### 2. Integrate with Existing Application
- Minimal changes to existing code
- Encapsulate all crash detection logic
- Clear separation of concerns

### 3. Logging Strategy
```python
# Use structured logging
import logging
import json

logger = logging.getLogger('desktop_viewer.crash_detection')

def log_crash(context: CrashContext):
    """Log crash with full context."""
    logger.error(
        "QT WebEngine crash detected",
        extra={'crash_context': context.to_dict()}
    )
```

### 4. Testing Approach
- **Unit tests**: Mock QT signals and verify handler behavior
- **Integration tests**: Trigger real crashes (load invalid URLs, exhaust memory)
- **Manual tests**: Test on multiple platforms and configurations

---

## Edge Cases to Consider

1. **Rapid successive crashes**
   - Implement cooldown period before retry
   - Prevent crash loops

2. **Partial loads**
   - Page loads but critical resources fail
   - Monitor console errors for critical failures

3. **Background tab crashes**
   - Detect even when tab is not visible
   - Notify user appropriately

4. **Resource cleanup**
   - Ensure proper cleanup after crash
   - Prevent memory leaks from zombie processes

5. **User-initiated navigation during crash**
   - Cancel fallback if user navigates away
   - Reset retry counters appropriately

---

## Success Metrics

### Immediate Success Criteria
- ✅ All render process crashes detected
- ✅ Load failures detected with retry logic
- ✅ Crash context captured for debugging
- ✅ Fallback triggered within 2 seconds of crash

### Long-term Success Criteria
- 📊 Crash rate reduction (if retry logic succeeds)
- 📊 Mean time to fallback < 3 seconds
- 📊 Zero unhandled crashes in production
- 📊 Positive user feedback on fallback UX

---

## Next Steps

1. **Task 002**: Design the fallback mechanism
   - Decide on browser opening strategy
   - Design user notification UI
   - Define fallback success criteria

2. **Task 003**: Implement crash detection
   - Create CrashDetectionManager class
   - Connect all signals
   - Add logging and context capture

3. **Task 004**: Implement browser opener
   - Use platform-specific APIs
   - Handle edge cases
   - Add error handling

4. **Task 005**: Integrate detection with fallback
   - Wire crash detection to browser opener
   - Test end-to-end flow
   - Validate crash recovery

---

## References

### QT Documentation
- [QWebEnginePage Class](https://doc.qt.io/qt-6/qwebenginepage.html)
- [QWebEngineView Class](https://doc.qt.io/qt-6/qwebengineview.html)
- [Qt WebEngine Overview](https://doc.qt.io/qt-6/qtwebengine-overview.html)

### Related Chromium Issues
- Render process crashes: Common in complex web apps
- OOM killer on Linux: Well-documented issue
- GPU driver crashes: Platform-specific

### Best Practices
- Always handle renderProcessTerminated
- Implement retry logic with limits
- Log crash context for debugging
- Provide user feedback on failures

---

**Document Version**: 1.0  
**Date**: 2024-01-21  
**Status**: ✅ COMPLETE  
**Next Task**: 002-design-fallback-mechanism.md
