# Artifacts Tab Visibility - Quick Fix Guide

## The Bug in 3 Sentences

1. The Artifacts tab visibility is checked ONLY in `show_task()` (initial display), never in `update_task()` (status updates)
2. The visibility check only looks at `task.artifacts` (encrypted UUIDs), which is empty during task execution
3. Staging artifacts exist and are monitored, but the tab stays hidden because visibility is never rechecked

## Root Cause

**File:** `agents_runner/ui/pages/task_details.py`

The Desktop tab pattern (line 449) is correct:
```python
def update_task(self, task: Task) -> None:
    # ...
    self._sync_desktop(task)  # ✓ Desktop tab synced on every update
```

But the Artifacts tab is broken (missing call):
```python
def update_task(self, task: Task) -> None:
    # ...
    # ✗ self._sync_artifacts(task) is NOT called here!
```

## The Fix (3 changes, ~20 lines total)

### Change 1: Add _sync_artifacts() call
**File:** `agents_runner/ui/pages/task_details.py`  
**Line:** 454 (after `self._sync_review_menu(task)`)

```python
def update_task(self, task: Task) -> None:
    if self._current_task_id != task.task_id:
        return
    self._last_task = task
    self._container.setText(task.container_id or "—")
    self._sync_desktop(task)
    self._sync_container_actions(task)
    self._exit.setText("—" if task.exit_code is None else str(task.exit_code))
    self._apply_status(task)
    self._tick_uptime()
    self._sync_review_menu(task)
    
    # ADD THIS LINE:
    self._sync_artifacts(task)
    
    # Notify artifacts tab of status changes
    if self._artifacts_tab_visible:
        self._artifacts_tab.on_task_status_changed(task)
```

### Change 2: Check staging directory in _sync_artifacts()
**File:** `agents_runner/ui/pages/task_details.py`  
**Lines:** 516-521 (replace entire function)

```python
def _sync_artifacts(self, task: Task) -> None:
    # Check encrypted artifacts (for completed tasks)
    has_encrypted = bool(task.artifacts)
    
    # Check staging artifacts (for running tasks)
    has_staging = False
    if task.status in ["running", "queued", "created", "starting"]:
        from agents_runner.artifacts import get_staging_dir
        staging_dir = get_staging_dir(task.task_id)
        try:
            has_staging = staging_dir.exists() and any(
                f.is_file() for f in staging_dir.iterdir()
            )
        except Exception:
            has_staging = False
    
    # Show tab if either encrypted or staging artifacts exist
    has_artifacts = has_encrypted or has_staging
    
    if has_artifacts:
        self._show_artifacts_tab()
    else:
        self._hide_artifacts_tab()
```

### Change 3: Load content when tab appears (BONUS)
**File:** `agents_runner/ui/pages/task_details.py`  
**Lines:** 358-363 (add one line to _show_artifacts_tab)

```python
def _show_artifacts_tab(self) -> None:
    """Show the Artifacts tab if not already visible."""
    if self._artifacts_tab_visible:
        return
    self._artifacts_tab_index = self._tabs.addTab(self._artifacts_tab_widget, "Artifacts")
    self._artifacts_tab_visible = True
    
    # ADD THIS LINE:
    from PySide6.QtCore import QTimer
    QTimer.singleShot(0, self._load_artifacts)
```

## Testing

1. Start a task with an agent
2. Open the task details view (click on task in dashboard)
3. Inside the container, write a file: `echo "test" > /tmp/agents-artifacts/test.txt`
4. **Expected:** Artifacts tab appears within 1 second (green "Live Artifacts" label)
5. Let task complete
6. **Expected:** Tab switches to "Archived Artifacts" (gray label)

## Impact

- **Before:** Artifacts tab never appears, even when artifacts exist
- **After:** Artifacts tab appears dynamically during execution (live) and after completion (archived)
- **Risk:** MINIMAL - Following existing Desktop tab pattern
- **Effort:** 5 minutes to implement, 5 minutes to test

## Files Modified

1. `agents_runner/ui/pages/task_details.py` - 3 changes, ~20 lines

## Full Details

See `ARTIFACTS_TAB_AUDIT_REPORT.md` for complete analysis including:
- Detailed code flow diagrams
- Artifact storage architecture
- File watcher implementation
- Edge cases and testing checklist
