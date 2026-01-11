# Task: Create diagnostics bundle builder

## Description
Build a module that collects application information, logs, and task state to create a comprehensive diagnostics bundle as a single zip file.

## Requirements
1. Create a `bundle_builder.py` module
2. Implement collection of:
   - Application version (from package metadata)
   - OS name and version
   - Python version
   - Current application settings (redacted, no secrets)
   - Recent application logs (last 10MB or 10k lines, whichever is smaller)
   - Per-task logs if available (most recent tasks)
   - List of tasks with their status values
   - Most recent task details: status, agent name, failure category
3. Apply secret redaction to all collected content
4. Create a timestamped zip file in the diagnostics bundles directory
5. Return the path to the created bundle file

## Acceptance Criteria
- [ ] Bundle includes application version, OS info, Python version
- [ ] Bundle includes recent application logs (redacted)
- [ ] Bundle includes task logs if available (redacted)
- [ ] Bundle includes task state information
- [ ] All content is redacted using the redaction utility
- [ ] Output is a single zip file with timestamp in filename
- [ ] Function returns the path to the created bundle
- [ ] Code has proper error handling for missing/inaccessible logs

## Related Tasks
- Depends on: a7f3e219, b8d4c320
- Blocks: e1f7f653

## Notes
- Use zipfile module for bundle creation
- Filename format: `diagnostics-YYYY-MM-DD-HHMMSS.zip`
- Structure bundle with clear subdirectories: `info/`, `logs/`, `tasks/`
- Create module at: `agents_runner/diagnostics/bundle_builder.py`
- Function signature: `def create_diagnostics_bundle() -> str:` (returns bundle path)
- Application version: Get from `pyproject.toml` (currently "0.1.0")
- OS info: Use `platform.system()`, `platform.release()`, `platform.version()`
- Python version: Use `sys.version`
- Settings: Look at `MainWindow._settings_data` in `agents_runner/ui/main_window.py` for structure
- Tasks: Use `Task` dataclass from `agents_runner/ui/task_model.py` (task_id, status, agent_cli, error, etc.)
- Logs: Container logs are captured per-task in `Task.logs` list; system logs may not exist yet (handle gracefully)
