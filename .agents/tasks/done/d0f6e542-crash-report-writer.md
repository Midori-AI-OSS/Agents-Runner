# Task: Implement crash report writer

## Description
Create a crash report system that captures unhandled exceptions and writes detailed crash information to disk for later review.

## Requirements
1. Create a `crash_handler.py` module
2. Implement crash report data collection:
   - Exception type
   - Exception message
   - Full stack trace
   - Timestamp
   - Application version
   - Breadcrumb log of recent events (if available)
3. Write crash reports as JSON or text files with timestamp in filename
4. Store in the crash reports subdirectory
5. Apply secret redaction to stack traces and error messages
6. Implement a function to install the global exception handler

## Acceptance Criteria
- [ ] Crash reports include exception type, message, and full stack trace
- [ ] Crash reports include timestamp and application version
- [ ] Crash reports include breadcrumb log if available
- [ ] All crash report content is redacted for secrets
- [ ] Crash reports are saved to the crash reports directory
- [ ] Filename format: `crash-YYYY-MM-DD-HHMMSS.json` or `.txt`
- [ ] Function to install global exception handler is provided
- [ ] Code has proper error handling (crash handler must not crash)

## Related Tasks
- Depends on: a7f3e219, b8d4c320
- Blocks: f2g8h764

## Notes
- Use `sys.excepthook` for global exception handling
- Consider using `traceback` module for stack trace formatting
- Ensure crash handler itself is bulletproof with try-except
- Create module at: `agents_runner/diagnostics/crash_handler.py`
- Function signatures:
  - `def install_crash_handler() -> None:` - Install global exception handler
  - `def write_crash_report(exc_type, exc_value, exc_traceback) -> str:` - Write crash report, return path
- Application version: Get from `pyproject.toml` (version = "0.1.0")
- Breadcrumb integration: Import from `agents_runner/diagnostics/breadcrumbs.py` (to be created in task i5j1k097)
- Use JSON format for structured crash data: `crash-YYYY-MM-DD-HHMMSS.json`
