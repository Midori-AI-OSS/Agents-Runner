# [BUG] New Task: Interactive desktop missing for mounted envs

## Summary
On the `New task` page, the `Run Interactive` button only exposes desktop launch via its dropdown menu for cloned repo environments. Mounted-folder environments cannot launch interactive with desktop even when the environment is configured with `Enable headless desktop`.

## Current behavior
- In `agents_runner/ui/pages/new_task.py`, `NewTaskPage._sync_interactive_options()` only attaches the `Run Interactive` menu when `workspace_type == WORKSPACE_CLONED`.
- Result: mounted environments never show the dropdown and cannot select `With desktop`.

## Expected behavior
- If desktop is enabled (either environment `Enable headless desktop` or Settings `Force headless desktop`):
  - Primary click on `Run Interactive` launches interactive **with desktop** by default.
  - Dropdown arrow is available as an override to launch interactive **without desktop**.
- If desktop is not enabled:
  - No dropdown is shown.
  - Primary click launches interactive **without desktop**.

## Repro
1. Create/select an environment with `Workspace` = mounted folder and check `Enable headless desktop`.
2. Open `New task`.
3. Observe `Run Interactive` has no desktop option (no dropdown).

## Acceptance criteria
- Mounted-folder envs with desktop enabled can launch interactive with desktop from the `Run Interactive` button.
- Desktop enablement is gated to:
  - env setting: `Environment.headless_desktop_enabled`, OR
  - settings flag: `settings_data["headless_desktop_enabled"]` (Force headless desktop).
- When desktop enabled, the dropdown provides an explicit `Without desktop` override.
- When desktop not enabled, the dropdown is hidden and no desktop preflight is injected.

## Implementation notes (code pointers)
- Menu gating currently lives in `agents_runner/ui/pages/new_task.py`:
  - `NewTaskPage._sync_interactive_options()`
  - `NewTaskPage._on_launch()` / `NewTaskPage._on_launch_with_desktop()`
- `Environment.headless_desktop_enabled` exists in `agents_runner/environments/model.py`.
- `Force headless desktop` is stored in main settings as `headless_desktop_enabled` (`agents_runner/ui/main_window.py` defaults).
- Interactive docker launcher detects desktop mode only via `extra_preflight_script` content (`agents_runner/ui/main_window_tasks_interactive_docker.py`).
- NewTaskPage likely needs a setter from MainWindow to learn whether force-desktop is enabled (and/or per-env desktop enabled), then compute `desktop_allowed` and `default_desktop`.

