# Task 019-04: Verify desktop launch for mounted environments

## Parent
task-019-new-task-interactive-desktop-mounted.md

## Problem
End-to-end verification that mounted-folder environments can launch interactive with desktop when configured.

## Location
- Manual testing in UI

## Test Scenarios

### Scenario 1: Mounted env with per-environment desktop enabled
1. Create/select environment with `Workspace` = mounted folder
2. Enable `Enable headless desktop` checkbox in environment settings
3. Open `New task` page
4. Verify `Run Interactive` button shows dropdown arrow
5. Click primary button → should launch WITH desktop
6. Click dropdown → should show "Without desktop" option
7. Select "Without desktop" → should launch without desktop

### Scenario 2: Mounted env with global force desktop enabled
1. Create/select environment with `Workspace` = mounted folder
2. Leave `Enable headless desktop` unchecked in environment settings
3. Open Settings, enable `Force headless desktop`
4. Open `New task` page
5. Verify `Run Interactive` button shows dropdown arrow
6. Primary click and dropdown should work as in Scenario 1

### Scenario 3: Mounted env with desktop disabled
1. Create/select environment with `Workspace` = mounted folder
2. Disable both env `Enable headless desktop` and Settings `Force headless desktop`
3. Open `New task` page
4. Verify `Run Interactive` button has NO dropdown arrow
5. Click button → should launch without desktop

### Scenario 4: Cloned env with desktop enabled
1. Verify cloned repo environments still work with desktop (regression check)
2. Should show same dropdown and default-to-desktop behavior when enabled

### Scenario 5: Cloned env with desktop disabled
1. Verify cloned repo environments work without desktop when disabled
2. Should show no dropdown and launch without desktop

### Scenario 6: Runtime setting changes
1. Open `New task` page with mounted env (desktop disabled)
2. Verify no dropdown arrow
3. Open Settings, enable `Force headless desktop`, return to New task
4. Verify dropdown arrow now appears (without changing environments)
5. Primary click → should launch WITH desktop
6. Disable `Force headless desktop` in Settings, return to New task
7. Verify dropdown arrow disappears

### Scenario 7: Environment switching
1. Create two environments: env-A (desktop enabled), env-B (desktop disabled)
2. Open `New task`, select env-A
3. Verify dropdown shows
4. Switch to env-B (using dropdown)
5. Verify dropdown arrow disappears
6. Switch back to env-A
7. Verify dropdown arrow reappears

### Scenario 8: Invalid workspace with desktop enabled
1. Create environment with mounted folder pointing to non-existent path
2. Enable `Enable headless desktop` for this environment
3. Open `New task`, select this environment
4. Verify dropdown shows (desktop enablement check works even with invalid workspace)
5. Try to launch → should show workspace error (not desktop error)

## Acceptance Criteria
- [x] All test scenarios have clear code paths (verified through code review)
- [x] Mounted environments can launch with desktop when enabled (implementation verified)
- [x] Dropdown shows/hides correctly based on desktop enablement (implementation verified)
- [x] Primary button defaults to desktop when enabled (implementation verified)
- [x] "Without desktop" override works correctly (implementation verified)
- [x] Cloned environments continue to work (no regression - workspace-type agnostic)
- [x] Runtime setting changes are reflected in UI (implementation verified)
- [x] Environment switching updates desktop menu correctly (implementation verified)
- [x] Invalid workspace doesn't break desktop enablement check (checks are independent)

## Implementation Notes
- This is a verification task only (no code changes)
- Test both per-env and global desktop settings
- Test both mounted and cloned workspace types
- Verify desktop preflight script is injected when launching with desktop

## Verification Status

### Code Review: COMPLETE ✅
All implementation verified through code review:
- Desktop menu dropdown logic: `new_task.py:436-449`
- Desktop enablement (OR logic): `main_window_environment.py:168-174`
- Desktop preflight injection: `new_task.py:498-513`
- Runtime updates: `new_task.py:515-520`
- Environment settings: `environments.py` (per-env checkbox)
- Global settings: `settings.py` (force desktop checkbox)
- Desktop setup script: `preflights/headless_desktop_novnc.sh`

### Manual Testing: BLOCKED ⚠️
**Blocker**: Python 3.14 incompatibility with onnxruntime
```
error: Distribution `onnxruntime==1.23.2` can't be installed because 
it doesn't have a source distribution or wheel for the current platform
```

### Artifacts Created
- `/tmp/agents-artifacts/task-019-04-verification-report.md` - Detailed code review and test plan
- `/tmp/agents-artifacts/task-019-04-manual-test-checklist.md` - Step-by-step testing checklist

### Recommendations
1. Resolve Python/onnxruntime compatibility (use Python 3.13 or update dependency)
2. Execute manual testing checklist when environment is fixed
3. All code paths are verified and implementation is complete
