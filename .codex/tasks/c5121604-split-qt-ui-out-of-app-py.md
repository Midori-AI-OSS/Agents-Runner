# Split Qt UI out of `codex_local_conatinerd/app.py`

## Context
`codex_local_conatinerd/app.py` is a multi-thousand-line module mixing:
- Qt widgets/pages
- animations/painting helpers
- task state/model
- thread/worker bridges
- glue logic (docker, environments, GH management, persistence)

This violates the project guideline to avoid monolith files (soft max 300 lines, hard max 600 lines).

## Goal
Refactor the UI code into a small set of cohesive modules so no single file exceeds the line limits, while keeping behavior and public entrypoints stable.

## Proposed module layout
- `codex_local_conatinerd/app.py`: thin shim that keeps `run_app(argv)` and imports the real implementation.
- `codex_local_conatinerd/ui/main_window.py`: `MainWindow` + top-level wiring
- `codex_local_conatinerd/ui/pages/`: `DashboardPage`, `TaskDetailsPage`, `NewTaskPage`, `EnvironmentsPage`, `SettingsPage`
- `codex_local_conatinerd/ui/task_model.py`: `Task` dataclass + status helpers
- `codex_local_conatinerd/ui/bridges.py`: `TaskRunnerBridge`, `DockerPruneBridge`, `HostCleanupBridge`
- `codex_local_conatinerd/ui/graphics.py`: `_EnvironmentTintOverlay`, `_BackgroundOrb`, color/blend helpers
- `codex_local_conatinerd/ui/icons.py`: `_app_icon()` and asset helpers (if needed)
- `codex_local_conatinerd/ui/utils.py`: safe string/formatting/time parsing helpers used by UI

## Acceptance criteria
- `uv run main.py` still launches and all existing pages render and function.
- `codex_local_conatinerd/app.py` stays ≤ 300 lines and is primarily re-exports/glue.
- No single new module exceeds 600 lines; prefer ≤ 300.
- Public imports used elsewhere remain valid (or are re-exported from the old locations).
- Minimal diff behavior: no UX/style changes unless necessary for the refactor.

## Notes
- Avoid circular imports by keeping Qt-only helpers in `ui/*` and domain logic in existing modules (`docker_runner`, `environments`, `persistence`, `gh_management`).
- Keep square-corner UI constraint (no rounded corners) unchanged during refactor.

