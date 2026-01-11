# Task: Create log file collector module

## Description
Build a module that locates and collects recent application logs and per-task logs for inclusion in diagnostics bundles.

## Requirements
1. Create a log collector module
2. Locate application log files (determine where logs are stored)
3. Collect recent application logs:
   - Last 10MB or last 10,000 lines (whichever is smaller)
   - Read from end of file backward
4. Locate and collect per-task logs if they exist:
   - Include most recent task logs
   - Limit per-task log size (e.g., last 1MB per task)
5. Return collected logs as a dictionary: `{filename: content}`
6. Handle missing or inaccessible log files gracefully

## Acceptance Criteria
- [ ] Module can locate application log files
- [ ] Recent application logs are collected (size-limited)
- [ ] Per-task logs are collected if available
- [ ] Log collection is size-limited to prevent huge bundles
- [ ] Missing/inaccessible logs don't cause failures
- [ ] Output is structured dictionary
- [ ] Code has proper error handling and type hints

## Related Tasks
- Depends on: None
- Blocks: c9e5d431

## Notes
- Investigate where logs are currently stored (check for logging config)
- Consider using `tail` strategy to read last N lines efficiently
- Look for patterns in `agents_runner/docker/` and `agents_runner/environments/` for task log locations
- Return raw log content (redaction happens in bundle builder)
- Create module at: `agents_runner/diagnostics/log_collector.py`
- Log sources to investigate:
  - Task logs: Stored in `Task.logs` list (see `agents_runner/ui/task_model.py`)
  - Container logs: Captured per-task in memory, not written to files by default
  - System logs: Python's logging module may not write to files yet (handle gracefully)
- Current logging pattern:
  - Uses `logging.getLogger(__name__)` throughout codebase
  - No central log file configuration found yet (may log to stdout/stderr only)
- Function signature: `def collect_logs() -> dict[str, str]:` returns `{filename: content}`
- For task logs: Access from Task objects loaded from state
- Consider collecting:
  - Most recent 10 tasks' logs
  - Application stdout/stderr if accessible (may need to redirect at startup)
- If no persistent logs exist, collect recent task logs from state only
