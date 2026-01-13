# Workspace Type Refactor Status (Remaining Work)

This task is **partially implemented** on the current branch but **not finished**.

## What’s Already Done (present in branch)

- Added `WORKSPACE_*` constants + `Environment.workspace_type/workspace_target` (still alongside `gh_management_*`).
- Added `Task.workspace_type` + changed PR gating to use `Task.requires_git_metadata()` → `workspace_type == WORKSPACE_CLONED`.
- Added migration in `agents_runner/persistence.py` and `agents_runner/environments/serialize.py` to derive `workspace_type` from legacy `gh_management_mode`.
- Fixed repo-root lookup in PR flow to prefer `env.workspace_target` / `env.gh_management_target` over `env.host_workdir`.

## Work Remaining (must do to meet spec)

### 1) Remove `gh_management_mode` from runtime logic (core requirement)

- Remove `Environment.gh_management_mode` from `agents_runner/environments/model.py` and eliminate `normalize_gh_management_mode()` usage from all runtime paths.
- Keep **read-time** migration only (deserialize old `gh_management_mode` → `workspace_type`) but stop persisting/depending on it in memory/UI.
- Remove `Task.gh_management_mode` usage for any gating; derive everything from `Task.workspace_type` and `Environment.workspace_type`.

High-impact call sites still using `gh_management_mode` today:
- `agents_runner/ui/main_window_environment.py` (template detection gating, management_modes map)
- `agents_runner/ui/pages/new_task.py` (workspace line placement uses `mode == "local"`)
- `agents_runner/ui/pages/environments.py` + `agents_runner/ui/pages/environments_actions.py` (still centered on `gh_management_mode` even if hidden)
- `agents_runner/ui/main_window_tasks_agent.py` / `agents_runner/ui/main_window_tasks_interactive.py` (still set `task.gh_management_mode=...`)
- `agents_runner/ui/main_window_preflight.py` (still uses `gh_mode`/`gh_locked` for recreate logic)

### 2) Stop copying `gh_management_locked` onto tasks (prevents future regressions)

- Remove `task.gh_management_locked = env.gh_management_locked` assignments:
  - `agents_runner/ui/main_window_tasks_agent.py`
  - `agents_runner/ui/main_window_tasks_interactive.py`
  - `agents_runner/ui/main_window_preflight.py`
- Keep `gh_management_locked` only if it truly means “environment editing locked”; otherwise rename/remove it entirely.

### 3) Replace “mode map” in New Task UI with workspace-type map/sets

Current bug risk: `NewTaskPage` still uses an env “management mode” map and checks `mode == "local"` to decide mounted behavior.

- Replace `set_environment_management_modes()` with `set_environment_workspace_types()` (or similar).
- Drive workspace placement from `workspace_type`:
  - `WORKSPACE_CLONED`: hide workspace line
  - `WORKSPACE_MOUNTED`: show workspace on terminal line
  - `WORKSPACE_NONE`: show normal workspace line

### 4) Terms sweep (repo-wide)

- Replace UI strings and identifiers that still say “git locked / folder locked / gh management mode”.
- Prefer “Cloned repo” / “Mounted folder” terminology consistently.

### 5) Cleanup / coordination fixups

- Restore `.agents/audit/AGENTS.md` content (it was blanked) so agents don’t reintroduce audit artifacts into the repo.

## Acceptance Checks (manual)

- Mounted env task: **no PR/review UI**, no PR actions, workspace path behaves as mounted.
- Cloned env task: PR/review UI visible, PR creation works, repo root resolves correctly.
- Reload archived tasks: PR/review visibility is correct based on stored `Task.workspace_type` (not env lookups).

