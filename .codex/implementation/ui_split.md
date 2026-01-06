# Qt UI Split (app.py)

- `agents_runner/app.py` is now a thin entrypoint (≤ 300 lines) that defines `run_app(argv)`.
- UI implementation moved under `agents_runner/ui/` (main window, pages, bridges, task model, helpers).
- The GUI entrypoint stays stable (`from agents_runner.app import run_app`).
- Refactor is structural: no UX/style changes intended, and modules stay under the size limits.

