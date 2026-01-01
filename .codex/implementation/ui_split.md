# Qt UI Split (app.py)

- `codex_local_conatinerd/app.py` is now a thin entrypoint (≤ 300 lines) that defines `run_app(argv)`.
- UI implementation moved under `codex_local_conatinerd/ui/` (main window, pages, bridges, task model, helpers).
- The GUI entrypoint stays stable (`from codex_local_conatinerd.app import run_app`).
- Refactor is structural: no UX/style changes intended, and modules stay under the size limits.

