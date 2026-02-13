# Task: Fix Failing Test - test_tasks_nav_button_fade_behavior.py

**Type:** Bug Fix  
**Priority:** Critical  
**Estimated Effort:** 10 minutes  
**Blocks:** Task 001 (PR #215 review), PR #215 merge

## Objective
Fix 2 failing tests in `test_tasks_nav_button_fade_behavior.py` caused by PR #215 changes.

## Context
- **Related PR:** #215 - "[UI] Move env controls into page headers"
- **Current PR Status:** OPEN, lint-and-test check failing due to these test failures
- **Impact:** Blocks PR #215 from merging and accurate code review

## Problem
Tests fail with:
```
AttributeError: '_DummyNewTaskPage' object has no attribute 'base_branch_controls_widget'
```

## Root Cause
PR #215 added a new method `base_branch_controls_widget()` to NewTaskPage (line 100 in tasks.py):
```python
self._base_branch_controls = self._new_task.base_branch_controls_widget()
```

The test's `_DummyNewTaskPage` mock class doesn't implement this method.

## Solution
Add the missing `base_branch_controls_widget()` method to `_DummyNewTaskPage` in the test file.

## Files to Modify
- `agents_runner/tests/test_tasks_nav_button_fade_behavior.py`

## Steps
1. **Verification-first**: Read current test file structure
   ```bash
   cat agents_runner/tests/test_tasks_nav_button_fade_behavior.py
   ```
2. Review the actual `base_branch_controls_widget()` implementation in `agents_runner/ui/pages/new_task.py`
3. Add a minimal stub implementation to `_DummyNewTaskPage` that returns an appropriate QWidget
4. Format code: `uv run ruff format .`
5. Lint code: `uv run ruff check .`
6. Run specific tests: `uv run pytest agents_runner/tests/test_tasks_nav_button_fade_behavior.py -v`
7. Verify both tests pass
8. Run full test suite: `uv run pytest`
9. Commit with proper format: `[TEST] Fix test_tasks_nav_button_fade_behavior for PR #215 changes`
10. Update `/tmp/agents-artifacts/agent-output.md` with results

## Success Criteria
- Both tests pass:
  - `test_tasks_github_buttons_fade_only_on_support_flip`
  - `test_tasks_github_button_fade_ignores_mid_animation_changes`
- No new test failures introduced
- Full test suite passes
- Code passes ruff format and lint checks
- Changes committed with proper message format

## Deliverables
- Updated test file: `agents_runner/tests/test_tasks_nav_button_fade_behavior.py`
- Git commit following AGENTS.md format: `[TEST] Fix test_tasks_nav_button_fade_behavior for PR #215 changes`

## Post-Completion Actions
1. Update `/tmp/agents-artifacts/agent-output.md` with fix summary and test results
2. Move this task file from `.agents/tasks/wip/` to `.agents/tasks/done/` after fix is complete and committed
3. Do NOT bump version (per AGENTS.md: only bump when moving task files from wip to done, and this is just a test fix)
4. Task 001 can now be executed once this fix is committed
