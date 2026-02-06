# Replace `print()` in cleanup path

Issue
- `agents_runner/ui/runtime/app.py` uses `print()` for cleanup messages (non-CLI output).

Goal
- Use the standard logger instead of `print()` for these messages.

Constraints
- Minimal diffs; preserve behavior.

Verify
- `uv run ruff check .`
- `uv run ruff format .`

