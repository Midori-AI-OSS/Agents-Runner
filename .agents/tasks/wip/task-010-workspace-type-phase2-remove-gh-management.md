# Task 010: Workspace Type Phase 2 (Remove `gh_management_mode`)

## Goal

Finish the refactor so the app uses **only**:
- `Environment.workspace_type` (`WORKSPACE_CLONED` / `WORKSPACE_MOUNTED` / `WORKSPACE_NONE`)
- `Environment.workspace_target`
- `Task.workspace_type`

`gh_management_mode` must be removed from **runtime/UI logic**. Legacy fields may be supported for **read-time migration only**.

## Requirements

### A) Eliminate `gh_management_mode` from runtime behavior

- Remove or stop using:
  - `Environment.gh_management_mode`
  - `normalize_gh_management_mode()` in runtime/UI code
  - `GH_MANAGEMENT_*` constants in runtime/UI code
- Allowed: keep a tiny compatibility mapper during deserialization only (env/task load).

### B) Environment UI must select workspace type directly

Environment editing/creation UI must operate on:
- workspace type: “Cloned repo” vs “Mounted folder” (and optionally “Use Settings workdir”/none)
- workspace target: repo slug/URL for cloned, folder path for mounted

It must not expose or depend on “gh management mode”.

Files likely involved:
- `agents_runner/ui/pages/environments.py`
- `agents_runner/ui/pages/environments_actions.py`
- `agents_runner/ui/dialogs/new_environment_wizard.py`

### C) New Task UI must not use “management mode” maps

`agents_runner/ui/pages/new_task.py` currently uses an env “management mode” map and checks `mode == "local"` to decide mounted behavior for workspace-line layout.

Replace this with workspace-type tracking:
- cloned: hide workspace line completely
- mounted: show workspace on terminal line
- none/other: show normal workspace line

Update the plumbing in `agents_runner/ui/main_window_environment.py` accordingly (stop passing management mode maps).

### D) Stop propagating `gh_management_locked` onto tasks

Remove these assignments:
- `task.gh_management_locked = env.gh_management_locked`

in:
- `agents_runner/ui/main_window_tasks_agent.py`
- `agents_runner/ui/main_window_tasks_interactive.py`
- `agents_runner/ui/main_window_preflight.py`

After this, PR gating must be determined by `Task.workspace_type` only.

### E) Serialization/persistence

- Environment serialization should write `workspace_type` + `workspace_target`.
- Environment deserialization may read old `gh_management_mode/target` only to migrate into `workspace_*` without keeping `gh_management_mode` around in memory.
- Task persistence should write `workspace_type`.
- Task deserialization may read old `gh_management_mode` only to migrate into `workspace_type`.

### F) Cleanup + correctness

- Do not modify `README.md`.
- Do not create/update extra docs; keep changes code-focused.
- Ensure `.agents/audit/AGENTS.md` remains intact (do not blank it).

## Definition of Done (checks)

- `rg -n "\\bgh_management_mode\\b|normalize_gh_management_mode\\b|GH_MANAGEMENT_" agents_runner` returns **only** migration/deserialization compatibility code (or zero).
- `rg -n "\\bgh_management_locked\\b" agents_runner/ui` shows it’s no longer copied onto tasks.
- App starts: `uv run main.py` reaches GUI startup (no import errors).

