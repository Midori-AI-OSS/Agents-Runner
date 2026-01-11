# Task: Install crash handler on application startup

## Description
Integrate the crash handler into the application startup sequence so unhandled exceptions are captured automatically.

## Requirements
1. In `main.py` or the application initialization code, install the global crash handler
2. Ensure crash handler is installed as early as possible in the startup process
3. Verify crash handler doesn't interfere with normal exception handling in debug mode

## Acceptance Criteria
- [ ] Crash handler is installed during application startup
- [ ] Installation happens before main application logic
- [ ] Crash reports are written when unhandled exceptions occur
- [ ] Normal application exception handling still works
- [ ] No regression in application startup or behavior

## Related Tasks
- Depends on: d0f6e542
- Blocks: g3h9i875

## Notes
- Review `main.py` to understand current startup sequence
- Consider adding a command-line flag to disable crash handler for debugging
- Test by intentionally causing an exception
- Main entry point: `main.py` calls `agents_runner.app.run_app(sys.argv)`
- Application initialization happens in `agents_runner/app.py:run_app()`
- Install crash handler early, right after imports in `run_app()` function
- Add call like: `from agents_runner.diagnostics.crash_handler import install_crash_handler; install_crash_handler()`
- Place before QApplication creation (line ~75 in app.py)
