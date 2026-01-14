# Task 019: New Task Interactive Desktop for Mounted Environments - Implementation Plan

## Overview
This is the implementation breakdown for task-019-new-task-interactive-desktop-mounted.md.

The bug: `Run Interactive` button on New Task page only exposes desktop launch for cloned repo environments, but not for mounted-folder environments.

## Root Cause
In `agents_runner/ui/pages/new_task.py`, the method `_sync_interactive_options()` only shows the desktop dropdown menu when `workspace_type == WORKSPACE_CLONED`, excluding mounted environments even when they have desktop enabled.

## Solution Approach
Instead of gating desktop menu on workspace type, gate it on desktop enablement status (computed from per-environment `headless_desktop_enabled` OR global `Force headless desktop` setting).

## Subtasks (in order)

### Task 019-01: Add desktop enablement setter to NewTaskPage
**File:** `task-019-01-add-desktop-enablement-setter.md`
**Summary:** Add `_desktop_enabled` flag and `set_desktop_enabled()` method to NewTaskPage. Update `_sync_interactive_options()` to check this flag instead of workspace type.

### Task 019-02: Compute and pass desktop enablement to NewTaskPage
**File:** `task-019-02-compute-desktop-enablement.md`
**Summary:** In MainWindow `_populate_environment_pickers()`, compute desktop enablement per environment (env OR global setting) and pass to NewTaskPage via new setter method.

### Task 019-03: Update interactive launch behavior with desktop defaults
**File:** `task-019-03-update-launch-behavior.md`
**Summary:** When desktop enabled, primary button launches WITH desktop by default. Dropdown provides "Without desktop" override. Reverse of current behavior.

### Task 019-04: Verify desktop launch for mounted environments
**File:** `task-019-04-verify-desktop-launch.md`
**Summary:** End-to-end testing of all scenarios (mounted with desktop, mounted without desktop, cloned with desktop, cloned without desktop, per-env vs global settings).

## Key Files
- `agents_runner/ui/pages/new_task.py` - Menu logic and launch handlers
  - `_sync_interactive_options()` (line ~422)
  - `_on_launch()` and `_on_launch_with_desktop()` methods
- `agents_runner/ui/main_window_environment.py` - Desktop enablement computation
  - `_populate_environment_pickers()` (line ~160)
- `agents_runner/environments/model.py` - Environment.headless_desktop_enabled field (line ~81)
- `agents_runner/ui/main_window.py` - Settings headless_desktop_enabled field (line ~97)

## Dependencies
- Tasks must be completed in order (019-01 → 019-02 → 019-03 → 019-04)
- Task 019-04 is verification only (no code changes)

## Success Criteria
- Mounted environments can launch interactive with desktop when desktop is enabled
- Desktop menu shows for any environment type when desktop enabled
- Primary button defaults to WITH desktop when enabled
- Dropdown provides WITHOUT desktop override when enabled
- No dropdown when desktop not enabled
- Cloned environments continue to work (no regression)
