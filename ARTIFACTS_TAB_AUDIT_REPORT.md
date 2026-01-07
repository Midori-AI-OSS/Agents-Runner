# Artifacts Tab Visibility Audit Report

**Date:** 2025-01-07  
**Auditor:** AI Assistant (Auditor Mode)  
**Issue:** Artifacts tab not appearing despite artifacts being collected

---

## Executive Summary

**ROOT CAUSE IDENTIFIED:** The Artifacts tab visibility logic checks `task.artifacts` (a list of UUIDs), but this field is ONLY populated during task finalization in `_on_bridge_done()`. The `update_task()` method, which is called during status updates, does NOT call `_sync_artifacts()`, so the tab never appears even when artifacts exist.

**SEVERITY:** High - Feature is completely broken for live artifact viewing
**IMPACT:** Users cannot see artifacts in the UI despite artifacts being successfully collected

---

## 1. Current Tab Visibility Logic

### Location: `agents_runner/ui/pages/task_details.py`

#### Initial Display (show_task, line 417-434):
```python
def show_task(self, task: Task) -> None:
    # ... setup code ...
    self._sync_artifacts(task)  # ✓ Called on initial display
    # ...
```

#### Status Updates (update_task, line 444-458):
```python
def update_task(self, task: Task) -> None:
    if self._current_task_id != task.task_id:
        return
    self._last_task = task
    self._container.setText(task.container_id or "—")
    self._sync_desktop(task)  # ✓ Desktop tab is synced
    self._sync_container_actions(task)
    self._exit.setText("—" if task.exit_code is None else str(task.exit_code))
    self._apply_status(task)
    self._tick_uptime()
    self._sync_review_menu(task)
    
    # Notify artifacts tab of status changes
    if self._artifacts_tab_visible:
        self._artifacts_tab.on_task_status_changed(task)
    
    # ✗ MISSING: self._sync_artifacts(task) is NOT called!
```

#### Tab Visibility Check (_sync_artifacts, line 516-521):
```python
def _sync_artifacts(self, task: Task) -> None:
    has_artifacts = bool(task.artifacts)  # Checks task.artifacts list
    if has_artifacts:
        self._show_artifacts_tab()
    else:
        self._hide_artifacts_tab()
```

**CRITICAL ISSUE:** `update_task()` does NOT call `_sync_artifacts()`, unlike how it calls `_sync_desktop()`.

---

## 2. Artifact Storage Locations

### Container Side (Inside Docker)
- **Path:** `/tmp/agents-artifacts/`
- **Mounted from host:** Yes (bind mount)
- **Created by:** `agent_worker.py` line 176-181

```python
artifacts_staging_dir = (
    Path.home() / ".midoriai" / "agents-runner" / "artifacts" 
    / task_token / "staging"
)
artifacts_staging_dir.mkdir(parents=True, exist_ok=True)
```

### Host Side
- **Staging directory:** `~/.midoriai/agents-runner/artifacts/{task_id}/staging/`
- **Encrypted storage:** `~/.midoriai/agents-runner/artifacts/{task_id}/`
- **Files:** `{uuid}.enc` (encrypted) + `{uuid}.meta` (JSON metadata)

### Single Source of Truth
**ANSWER:** The staging directory on the HOST is the single source of truth because it's bind-mounted into the container. Files written by the agent to `/tmp/agents-artifacts/` inside the container immediately appear in the host's staging directory.

---

## 3. Artifact Collection/Finalization Flow

### During Task Execution
1. Agent writes files to `/tmp/agents-artifacts/` (inside container)
2. Files appear in `~/.midoriai/agents-runner/artifacts/{task_id}/staging/` (host)
3. `ArtifactFileWatcher` monitors staging directory (if implemented)
4. UI can show "Live Artifacts" via `list_staging_artifacts()`

### After Task Completion
**Location:** `agents_runner/docker/agent_worker.py` lines 496-513

```python
# Collect artifacts before removing container
if self._container_id:
    try:
        self._on_log("[host] collecting artifacts from container...")
        task_dict = {
            "task_id": self._config.task_id,
            "image": self._config.image,
            "agent_cli": agent_cli,
            "created_at": time.time(),
        }
        self._collected_artifacts = collect_artifacts_from_container(
            self._container_id, task_dict, self._config.environment_id
        )
        if self._collected_artifacts:
            self._on_log(
                f"[host] collected {len(self._collected_artifacts)} artifact(s)"
            )
    except Exception as e:
        self._on_log(f"[host] artifact collection failed: {e}")
```

### Artifact Finalization Function
**Location:** `agents_runner/artifacts.py` lines 268-346

```python
def collect_artifacts_from_container(
    container_id: str, task_dict: dict[str, Any], env_name: str
) -> list[str]:
    """
    Collect artifacts from task's staging directory.
    Returns list of artifact UUIDs that were collected and encrypted.
    """
    # 1. Get staging directory
    # 2. Encrypt each file to permanent storage
    # 3. Clean up staging directory
    # 4. Return list of UUIDs
```

### Task.artifacts Population
**Location:** `agents_runner/ui/main_window_task_events.py` lines 274-290

```python
def _on_bridge_done(
    self, exit_code: int, error: object, artifacts: list, metadata: dict | None = None
) -> None:
    bridge = self.sender()
    if isinstance(bridge, TaskRunnerBridge):
        task = self._tasks.get(bridge.task_id)
        if task is not None:
            # ... other updates ...
            # Store collected artifacts
            if artifacts:
                task.artifacts = list(artifacts)  # ✓ This is where task.artifacts is set
```

**CRITICAL:** `task.artifacts` is ONLY set in `_on_bridge_done()`, which happens when the task completes. It is NEVER updated during task execution.

---

## 4. Root Cause Analysis

### The Bug: Multi-layered Issue

#### Problem 1: Tab Visibility Check Timing
- **Current behavior:** Tab visibility is checked ONLY in `show_task()` (initial display)
- **Expected behavior:** Tab visibility should be checked in `update_task()` (status updates)
- **Impact:** Even if `task.artifacts` is populated, the tab won't appear unless you navigate away and back

#### Problem 2: Wrong Data Source for Live Artifacts
- **Current check:** `has_artifacts = bool(task.artifacts)` 
- **Problem:** `task.artifacts` contains encrypted artifact UUIDs, populated ONLY after task completion
- **Missing:** No check for staging artifacts during active tasks

#### Problem 3: Staging vs Encrypted Logic Gap
- **Architecture intent:** Show "Live Artifacts" during execution, switch to "Archived Artifacts" after completion
- **Implementation:** `artifacts_tab.py` has dual-mode support (lines 173-228)
- **Gap:** Tab visibility logic doesn't know about staging artifacts

### Visual Timeline

```
Task Lifecycle:          Tab Visibility:        task.artifacts value:
─────────────────────────────────────────────────────────────────────
┌─ Task Created          [Task]                  []
│
├─ Task Running          [Task] [Desktop]        []  ← No staging check!
│  └─ Agent writes files                         []  ← Still empty!
│     to staging/                                []  ← Files exist but 
│                                                     field not updated!
├─ Task Completes        [Task] [Desktop]        []
│  └─ Artifacts          
│     encrypted                                  
│
├─ _on_bridge_done()     [Task] [Desktop]        [uuid1, uuid2, ...]
│  └─ task.artifacts                             ↑ NOW populated
│     populated                                  
│
└─ User navigates away   [Task] [Desktop]        [uuid1, uuid2, ...]
   and back                                      ↓ _sync_artifacts() 
                         [Task][Desktop][Artifacts]  runs on show_task()
                         ↑ Tab finally appears!
```

---

## 5. Why Tab Never Appears During Execution

### Expected Flow (per ARCHITECTURE.md lines 246-286):
1. Task starts → staging directory created
2. Agent writes files → file watcher detects changes
3. UI shows "Artifacts" tab with "Live Artifacts" label (green)
4. User can view/edit staging files in real-time
5. Task completes → artifacts encrypted → tab switches to "Archived Artifacts"

### Actual Flow:
1. Task starts → staging directory created ✓
2. Agent writes files → **tab visibility never checked** ✗
3. Task completes → artifacts encrypted ✓
4. `task.artifacts` populated → **`update_task()` doesn't call `_sync_artifacts()`** ✗
5. Tab remains hidden until user navigates away and back ✗

### Code Evidence:

**Desktop tab (WORKS):**
```python
# In update_task() line 449:
self._sync_desktop(task)  # ✓ Always called on updates
```

**Artifacts tab (BROKEN):**
```python
# In update_task() line 457-458:
if self._artifacts_tab_visible:  # Only notifies if already visible
    self._artifacts_tab.on_task_status_changed(task)
# ✗ Missing: self._sync_artifacts(task)
```

---

## 6. Filesystem Watching (Live Updates)

### Current Implementation Status

#### File Watcher Exists: ✓
**Location:** `agents_runner/docker/artifact_file_watcher.py`

```python
class ArtifactFileWatcher(QObject):
    """
    Watch artifact staging directory for changes.
    Emits files_changed signal when files are added, modified, or deleted.
    Changes are debounced to avoid excessive UI updates.
    """
    files_changed = Signal()
    
    def __init__(self, staging_dir: Path, debounce_ms: int = 500):
        # Uses QFileSystemWatcher with 500ms debouncing
```

#### Watcher Integration: ✓
**Location:** `agents_runner/ui/pages/artifacts_tab.py` lines 192-210

```python
def _switch_to_staging_mode(self) -> None:
    """Switch to staging (live) mode."""
    self._mode = "staging"
    self._mode_label.setText("Live Artifacts")
    
    # Start file watcher
    if self._current_task:
        staging_dir = get_staging_dir(self._current_task.task_id)
        if self._file_watcher:
            self._file_watcher.stop()
        self._file_watcher = ArtifactFileWatcher(staging_dir)
        self._file_watcher.files_changed.connect(self._on_files_changed)
        self._file_watcher.start()  # ✓ Watcher is started
```

#### Live Update Flow: ✓
```python
def _on_files_changed(self) -> None:
    """Handle file watcher notification (debounced)."""
    self._refresh_timer.start(500)  # Additional 500ms debounce

def _refresh_file_list(self) -> None:
    """Refresh artifact list from current mode."""
    if self._mode == "staging":
        self._artifacts = list_staging_artifacts(self._current_task.task_id)
    else:
        self._artifacts = list_artifacts(self._current_task.task_id)
    self._update_artifact_list()  # Updates UI
```

**VERDICT:** Live artifact watching is fully implemented and functional. The ONLY problem is that the tab never appears because visibility is never updated.

---

## 7. Recommended Fix Approach

### Fix 1: Add _sync_artifacts() to update_task()
**Priority:** CRITICAL  
**File:** `agents_runner/ui/pages/task_details.py`  
**Line:** 454 (after `_sync_review_menu(task)`)

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
    
    # FIX: Add this line
    self._sync_artifacts(task)  # ← Sync artifacts like we sync desktop
    
    # Notify artifacts tab of status changes
    if self._artifacts_tab_visible:
        self._artifacts_tab.on_task_status_changed(task)
```

### Fix 2: Update _sync_artifacts() Logic to Check Staging
**Priority:** CRITICAL  
**File:** `agents_runner/ui/pages/task_details.py`  
**Lines:** 516-521

```python
def _sync_artifacts(self, task: Task) -> None:
    # Check encrypted artifacts (for completed tasks)
    has_encrypted = bool(task.artifacts)
    
    # Check staging artifacts (for running tasks)
    has_staging = False
    if task.status in ["running", "queued", "created"]:
        from agents_runner.artifacts import get_staging_dir
        staging_dir = get_staging_dir(task.task_id)
        has_staging = staging_dir.exists() and any(
            f.is_file() for f in staging_dir.iterdir()
        )
    
    # Show tab if either encrypted or staging artifacts exist
    has_artifacts = has_encrypted or has_staging
    
    if has_artifacts:
        self._show_artifacts_tab()
        # Load artifacts when tab appears
        if not self._artifacts_tab_visible:
            QTimer.singleShot(0, self._load_artifacts)
    else:
        self._hide_artifacts_tab()
```

### Fix 3: Optimize Staging Check (Performance Concern)
**Priority:** MEDIUM  
**Rationale:** Calling `iterdir()` on every status update might be expensive

**Option A: Cache staging status**
```python
def _sync_artifacts(self, task: Task) -> None:
    has_encrypted = bool(task.artifacts)
    
    # Use cached staging status during execution
    has_staging = False
    if task.status in ["running", "queued", "created"]:
        # Check if we already showed staging artifacts
        if self._artifacts_tab_visible and self._artifacts_tab._mode == "staging":
            has_staging = True  # Trust the watcher to hide if needed
        else:
            # Initial check only
            from agents_runner.artifacts import get_staging_dir
            staging_dir = get_staging_dir(task.task_id)
            has_staging = staging_dir.exists() and any(
                f.is_file() for f in staging_dir.iterdir()
            )
    
    has_artifacts = has_encrypted or has_staging
    # ... rest of logic
```

**Option B: Add task.has_staging_artifacts flag**
- Set flag when staging directory is created
- Clear flag when artifacts are finalized
- Check flag in `_sync_artifacts()`

---

## 8. Additional Issues Found

### Issue 1: Tab Loaded but Content Not Initialized
**Location:** `task_details.py` line 338-338

```python
if index == getattr(self, "_artifacts_tab_index", -1) and index >= 0:
    QTimer.singleShot(0, self._load_artifacts)
```

**Problem:** `_load_artifacts()` is only called when user manually switches to the tab. If tab appears via `_show_artifacts_tab()` during a status update, content is never loaded.

**Fix:** Call `_load_artifacts()` in `_show_artifacts_tab()`:

```python
def _show_artifacts_tab(self) -> None:
    """Show the Artifacts tab if not already visible."""
    if self._artifacts_tab_visible:
        return
    self._artifacts_tab_index = self._tabs.addTab(self._artifacts_tab_widget, "Artifacts")
    self._artifacts_tab_visible = True
    # FIX: Load artifacts when tab appears
    QTimer.singleShot(0, self._load_artifacts)
```

### Issue 2: Artifacts Tab Mode Not Updated After Finalization
**Location:** `artifacts_tab.py` line 178-190

**Current:** `on_task_status_changed()` checks if mode should switch
**Problem:** This is only called if `self._artifacts_tab_visible` is True (line 457 in task_details.py)

**Scenario:**
1. Task completes while tab is hidden
2. Artifacts are finalized
3. User navigates away and back
4. Tab appears but stays in "staging" mode (wrong!)

**Fix:** `set_task()` should also check mode (it already does, line 173-176, so this is OK)

### Issue 3: Staging Directory Not Cleaned Up on Error
**Location:** `artifacts.py` lines 328-344

**Current:** Staging cleanup happens in `finally` block ✓
**Status:** No issue, this is correct

### Issue 4: Task.artifacts Not Updated During Execution
**Status:** This is by design
**Rationale:** Artifacts are encrypted only after task completion
**Consequence:** Tab visibility MUST check staging directory, not just task.artifacts

---

## 9. Implementation Priority

### Phase 1: Critical (Minimum Viable Fix)
1. Add `self._sync_artifacts(task)` to `update_task()` 
2. Update `_sync_artifacts()` to check staging directory
3. Test: Create task, write file to staging, verify tab appears

### Phase 2: Polish (Prevent Edge Cases)
4. Add `_load_artifacts()` call to `_show_artifacts_tab()`
5. Optimize staging check (caching or flag)
6. Test: Multiple tasks, rapid file creation, task cancellation

### Phase 3: Future Enhancement
7. Add proactive staging directory creation in worker
8. Emit staging status updates via bridge signals
9. Add UI indicator for "N new artifacts" during execution

---

## 10. Testing Checklist

### Manual Test Cases
- [ ] Start task → write file to staging → verify tab appears (green "Live")
- [ ] Task running → write multiple files → verify tab updates
- [ ] Task completes → verify tab switches to "Archived" (gray)
- [ ] Navigate away during execution → return → verify tab still shows
- [ ] Task completes while viewing different task → switch back → verify tab shows
- [ ] Task fails during execution → verify tab shows staging files (if any)
- [ ] Task with no artifacts → verify tab never appears
- [ ] Multiple tasks running → verify each task's tab behavior

### Edge Cases
- [ ] Staging directory exists but empty
- [ ] Artifacts finalization fails (encryption error)
- [ ] Rapid artifact creation (test debouncing)
- [ ] Container crash before finalization
- [ ] User deletes staging files manually while task running

---

## 11. Code Locations Reference

| Component | File | Lines | Purpose |
|-----------|------|-------|---------|
| Tab visibility logic | `ui/pages/task_details.py` | 516-521 | `_sync_artifacts()` - Show/hide tab |
| Status update handler | `ui/pages/task_details.py` | 444-458 | `update_task()` - Missing `_sync_artifacts()` call |
| Initial display | `ui/pages/task_details.py` | 417-434 | `show_task()` - Calls `_sync_artifacts()` |
| Tab content loader | `ui/pages/task_details.py` | 337-338, 523-525 | `_load_artifacts()` |
| Artifacts tab widget | `ui/pages/artifacts_tab.py` | 167-228 | Dual-mode (staging/encrypted) |
| File watcher | `docker/artifact_file_watcher.py` | 18-121 | QFileSystemWatcher wrapper |
| Staging functions | `artifacts.py` | 349-433 | `get_staging_dir()`, `list_staging_artifacts()` |
| Artifact finalization | `docker/agent_worker.py` | 496-513 | Encrypt + cleanup |
| Collection function | `artifacts.py` | 268-346 | `collect_artifacts_from_container()` |
| Task.artifacts population | `ui/main_window_task_events.py` | 274-290 | `_on_bridge_done()` |

---

## 12. Conclusion

**Root Cause:** Tab visibility logic is incomplete and inconsistent:
1. `update_task()` doesn't call `_sync_artifacts()` (unlike Desktop tab)
2. `_sync_artifacts()` only checks `task.artifacts`, which is empty during execution
3. Staging artifacts exist but are never checked for visibility

**Fix Complexity:** LOW - Single-line addition + 10-line logic update
**Risk:** MINIMAL - Mirroring existing Desktop tab pattern

**Recommended Action:** Implement Phase 1 fixes immediately (2 changes, ~15 minutes)

---

**Report End**
