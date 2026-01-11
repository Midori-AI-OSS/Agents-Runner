# Diagnostics System

## Overview

The diagnostics system provides issue reporting and crash capture capabilities for Agents Runner. It collects application data, redacts sensitive information, and creates bundles that users can attach to issue reports.

## Architecture

### Core Components

1. **Directory Infrastructure** (`agents_runner/diagnostics/paths.py`)
   - Manages diagnostics directory structure
   - Location: `~/.midoriai/agents-runner/diagnostics/`
   - Subdirectories: `bundles/` and `crash_reports/`

2. **Secret Redaction** (`agents_runner/diagnostics/redaction.py`)
   - Pattern-based detection of sensitive information
   - Redacts: authorization headers, bearer tokens, cookies, API keys, secrets, passwords
   - Handles GitHub tokens (ghp_, gho_, ghs_, etc.)
   - Maintains line structure while replacing sensitive values with [REDACTED]

3. **Breadcrumb Logging** (`agents_runner/diagnostics/breadcrumbs.py`)
   - Lightweight event tracking with circular buffer
   - Stores last 100 events with timestamps
   - Simple API: `add_breadcrumb(message)`, `get_breadcrumbs()`
   - Global logger instance for easy integration

### Data Collectors

4. **Settings Collector** (`agents_runner/diagnostics/settings_collector.py`)
   - Collects application settings using allowlist approach
   - Excludes sensitive settings (commands, scripts, paths with tokens)
   - Applies additional redaction as safety layer
   - Returns JSON-serializable dictionary

5. **Log Collector** (`agents_runner/diagnostics/log_collector.py`)
   - Collects logs from recent tasks in state
   - Limits: 1MB per task, 10MB total, up to 10 recent tasks
   - Handles missing/inaccessible logs gracefully
   - Returns dictionary mapping filename to content

6. **Task State Collector** (`agents_runner/diagnostics/task_collector.py`)
   - Gathers task list with status and basic info
   - Includes detailed info for most recent task
   - Captures failure information and attempt history
   - Handles missing/incomplete task data gracefully

### Bundle & Crash Systems

7. **Bundle Builder** (`agents_runner/diagnostics/bundle_builder.py`)
   - Creates timestamped zip bundles with all diagnostics
   - Includes: system info, settings, task state, logs
   - Applies secret redaction to all collected content
   - Organizes bundle with clear directory structure
   - Filename format: `diagnostics-YYYY-MM-DD-HHMMSS.zip`

8. **Crash Handler** (`agents_runner/diagnostics/crash_handler.py`)
   - Captures unhandled exceptions via sys.excepthook
   - Writes crash reports as JSON with timestamps
   - Includes: exception type, message, stack trace, breadcrumbs, app version
   - Applies secret redaction to all crash data
   - Bulletproof error handling (crash handler must not crash)
   - Filename format: `crash-YYYY-MM-DD-HHMMSS.json`

9. **Crash Detection** (`agents_runner/diagnostics/crash_detection.py`)
   - Checks for crash reports on startup
   - Tracks notified crashes to avoid repeat notifications
   - Shows user-friendly notification dialog
   - Offers to open crash reports folder

### UI Components

10. **Report Issue Button** (`agents_runner/ui/main_window.py`)
    - Added to main toolbar
    - Uses information icon for visibility
    - Triggers diagnostics dialog

11. **Diagnostics Dialog** (`agents_runner/ui/dialogs/diagnostics_dialog.py`)
    - Qt dialog for diagnostics bundle creation
    - Shows clear explanation of bundle contents
    - Creates bundle in background worker thread
    - Provides buttons to create bundle and open folder
    - Shows success message with bundle location

## Integration Points

### Application Startup

Crash handler is installed in `agents_runner/app.py:run_app()`:
- Installed as early as possible (before QApplication creation)
- Ensures all unhandled exceptions are captured

Crash detection runs after QtWebEngine initialization:
- Checks for previous crash reports
- Shows notification dialog if crashes detected
- Offers to open crash reports folder

### Breadcrumb Integration Points

Key locations where breadcrumbs should be added:

1. **Task Lifecycle** (`agents_runner/ui/main_window_task_events.py`)
   - Task started, completed, failed
   - Example: `add_breadcrumb(f"Task {task_id[:8]} started")`

2. **Container Operations** (`agents_runner/docker/agent_worker.py`)
   - Container launched, stopped
   - Example: `add_breadcrumb(f"Container {container_id[:12]} launched")`

3. **Agent Selection** (`agents_runner/ui/main_window_tasks_agent.py`)
   - Agent selected, changed
   - Example: `add_breadcrumb(f"Agent selected: {agent_name}")`

4. **Retry Operations**
   - Retry scheduled, started
   - Example: `add_breadcrumb(f"Retry scheduled for task {task_id[:8]}")`

## Bundle Contents

Diagnostics bundles contain:

### info/system.json
- Application version
- Python version
- OS name, release, version
- Platform and architecture

### info/settings.json
- Safe application settings (allowlisted)
- Environment variable flags (non-sensitive)
- All secrets redacted

### tasks/state.json
- List of all tasks with status
- Most recent task details
- Attempt history summary

### logs/
- Recent task logs (up to 10 tasks)
- Each task as separate file
- All secrets redacted

### README.txt
- Explanation of bundle contents
- Confirmation of redaction

## Crash Report Contents

Crash reports contain:

- Timestamp (ISO format)
- Application version
- Exception type
- Exception message
- Full stack trace
- Recent breadcrumbs (last 100 events)
- All secrets redacted

## Redaction Rules

The redaction system identifies and redacts:

1. **Authorization Headers**
   - Pattern: `Authorization: Bearer [token]`
   - Replaced with: `Authorization: Bearer [REDACTED]`

2. **Cookie Headers**
   - Pattern: `Cookie: [values]`
   - Replaced with: `Cookie: [REDACTED]`

3. **GitHub Tokens**
   - Pattern: `ghp_`, `gho_`, `ghs_`, `ghu_`, `ghr_` followed by 36-255 chars
   - Replaced with: `[REDACTED]`

4. **Key-Value Pairs**
   - Keys: token, api_key, secret, password, access_token, refresh_token
   - Pattern: `key=value` or `key: value`
   - Replaced with: `key=[REDACTED]`

5. **Generic Tokens**
   - Long base64-like strings (40+ chars)
   - Context-dependent replacement

## Usage

### For Users

#### Creating Diagnostics Bundle

1. Click "Report Issue" button in main toolbar
2. Review explanation of bundle contents
3. Click "Create Diagnostics Bundle"
4. Wait for bundle creation (runs in background)
5. Click "Yes" to open bundles folder when prompted
6. Attach the generated zip file to your issue report

#### After Crash

1. Restart application
2. If crash detected, notification dialog appears
3. Click "Yes" to open crash reports folder
4. Attach crash report JSON to issue report

### For Developers

#### Adding Breadcrumbs

```python
from agents_runner.diagnostics.breadcrumbs import add_breadcrumb

# In key application events
add_breadcrumb("Task started")
add_breadcrumb(f"Agent selected: {agent_name}")
add_breadcrumb(f"Container {container_id[:12]} launched")
```

#### Testing Crash Handler

```python
# Trigger test exception
raise Exception("Test crash handler")
```

Crash report will be written to `~/.midoriai/agents-runner/diagnostics/crash_reports/`

#### Creating Bundle Programmatically

```python
from agents_runner.diagnostics.bundle_builder import create_diagnostics_bundle

bundle_path = create_diagnostics_bundle(settings_data)
print(f"Bundle created: {bundle_path}")
```

## Security Considerations

1. **Redaction Coverage**
   - All collected data passes through redaction
   - Multiple pattern-based checks
   - Allowlist approach for settings prevents exposure

2. **User Control**
   - Users manually trigger bundle creation
   - Clear explanation of contents shown
   - Users choose when to share bundles

3. **Local Storage**
   - All diagnostics stored locally in user directory
   - No automatic upload or transmission
   - User controls what gets shared in issue reports

## Future Enhancements

Potential improvements:

1. Add application log file support (currently only task logs)
2. Include environment configuration details
3. Add system resource information (CPU, memory, disk)
4. Support for custom data collectors via plugins
5. Compress crash reports older than N days
6. Add bundle encryption option for sensitive environments
7. Support for automatic bundle upload to issue tracker
