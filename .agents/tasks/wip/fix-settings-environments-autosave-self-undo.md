# Stabilize Settings and Environments Autosave

## Status
- Planning complete.
- Do not implement in this task.

## Problem
- Settings edits can appear to undo themselves while typing.
- Autosave timing does not match expected behavior (`15s` idle, page switch, app exit).

## Goal
- Save only on:
  - page switch
  - 15 seconds after user input stops
  - app exit
- Apply the same policy to both Settings and Environments pages.

## Root Cause to Address
- `450ms` autosave timers in:
  - `agents_runner/ui/pages/settings.py`
  - `agents_runner/ui/pages/environments.py`
- Settings autosave can trigger a save/apply cycle that rebinds visible Settings widgets and can reset in-progress input.

## Implementation Plan (For Later)
1. Add a shared UI constant `AUTOSAVE_IDLE_MS = 15000` in `agents_runner/ui/constants.py`.
2. Replace hardcoded `450` autosave timer intervals in Settings and Environments pages with `AUTOSAVE_IDLE_MS`.
3. Keep existing page-switch autosave flow (`try_autosave`) intact.
4. Prevent Settings self-rebind while Settings page is visible during its own save cycle.
5. In `MainWindow.closeEvent`, flush pending autosaves before `_save_state()`:
   - Settings: `self._settings.try_autosave()`
   - Environments: `self._envs_page.try_autosave(show_validation_errors=False)`
6. Keep path default auto-fill normalization behavior unchanged in `_apply_settings`.

## User Decisions Locked
- Autosave policy: `15s` idle + page switch + app exit.
- Scope: apply to both Settings and Environments.
- Empty path behavior: auto-fill defaults.
- Exit with invalid environment input: best effort save, do not block close.
- Settings rebind preference: never rebind while Settings page is visible.

## Acceptance Criteria
1. Editing Settings fields does not self-reset while the page is visible.
2. Idle autosave occurs after ~15 seconds of no input.
3. Switching pages triggers immediate autosave.
4. Closing app flushes pending edits without blocking on environment validation dialogs.
5. Default config path auto-fill behavior remains intact.

## Manual Verification Checklist
1. Edit Settings text continuously and confirm no reset while visible.
2. Stop input and confirm save after ~15 seconds.
3. Change value and switch pages; confirm it persists.
4. Create invalid environment input, close app, confirm close is not blocked.
5. Reopen app and confirm latest valid data persisted.
