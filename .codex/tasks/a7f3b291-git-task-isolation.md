# Git Task Isolation for Concurrent Operations

**Status:** Ready for Implementation  
**Priority:** High (P1)  
**Complexity:** Medium  
**Estimated Effort:** 4-6 hours  

## Problem Statement

When multiple tasks use the same GitHub repository with `GH_MANAGEMENT_GITHUB` mode, concurrent git operations on a shared `host_workdir` cause:

1. **Git index lock collisions** - `.git/index.lock` errors when multiple tasks run git commands simultaneously
2. **Working tree contamination** - Task A's changes can appear in Task B's workspace
3. **Branch conflicts** - Tasks can interfere with each other's branch operations
4. **Repository corruption** - Race conditions can corrupt the git repository state

**Current Architecture:**
- Each task has a unique ID (10-char hex)
- Each task creates a unique branch: `midoriaiagents/{task_id}`
- For `GH_MANAGEMENT_GITHUB` mode, checkout path is: `~/.midoriai/agents-runner/managed-repos/{env_id}/`
- **Issue**: Multiple tasks using the same environment share the same checkout directory

## Solution Overview

Implement task-specific git working directories to eliminate shared state:

1. **Per-Task Checkout Directories** - Each task gets its own isolated git clone
2. **Backward Compatibility** - Existing single-task environments work unchanged
3. **Optional Git Locking** - Add file-based locking for shared scenarios (if needed)
4. **Clean Resource Management** - Auto-cleanup of old task directories

## Implementation Plan

### Phase 1: Core Infrastructure (Priority: Critical)

#### Task 1.1: Update Checkout Path Logic
**File:** `agents_runner/environments/paths.py`

**Changes:**
```python
def managed_repo_checkout_path(
    env_id: str, 
    data_dir: str | None = None,
    task_id: str | None = None  # NEW parameter
) -> str:
    base = os.path.join(managed_repos_dir(data_dir=data_dir), _safe_env_id(env_id))
    if task_id:
        # Task-specific isolation: managed-repos/{env_id}/tasks/{task_id}/
        return os.path.join(base, "tasks", _safe_task_id(task_id))
    # Fallback for single-task or legacy: managed-repos/{env_id}/
    return base

def _safe_task_id(task_id: str) -> str:
    """Sanitize task_id for filesystem use."""
    safe = "".join(
        ch for ch in (task_id or "").strip() if ch.isalnum() or ch in {"-", "_"}
    )
    return safe or "default"
```

**Acceptance Criteria:**
- ✅ Returns task-specific path when `task_id` is provided
- ✅ Returns environment path when `task_id` is None (backward compatible)
- ✅ Path is filesystem-safe (no special characters)

---

#### Task 1.2: Update Task Workspace Allocation
**File:** `agents_runner/ui/main_window_environment.py`

**Changes:**
In `_new_task_workspace()` method (line 64):
```python
if gh_mode == GH_MANAGEMENT_GITHUB:
    # Generate task_id early for workspace isolation
    # (task_id will be passed from calling code)
    path = managed_repo_checkout_path(
        env.env_id, 
        data_dir=os.path.dirname(self._state_path),
        task_id=task_id  # NEW: pass task_id for isolation
    )
    # ... rest of logic
```

**Note:** This requires refactoring to pass `task_id` earlier in the flow.

**Acceptance Criteria:**
- ✅ Each task gets a unique checkout directory
- ✅ Path includes task_id in the structure
- ✅ Existing behavior maintained when task_id is not provided

---

#### Task 1.3: Update Agent Worker to Use Task-Specific Paths
**File:** `agents_runner/docker/agent_worker.py`

**Changes:**
In `DockerAgentWorker.run()` method (line 104):
```python
# GitHub repo preparation (clone + branch prep)
if self._config.gh_repo:
    try:
        # Use task-specific checkout directory
        task_workdir = self._config.host_workdir  # Already task-specific from UI
        result = prepare_github_repo_for_task(
            self._config.gh_repo,
            task_workdir,  # Now isolated per task
            task_id=self._config.task_id,
            base_branch=self._config.gh_base_branch or None,
            prefer_gh=self._config.gh_prefer_gh_cli,
            recreate_if_needed=self._config.gh_recreate_if_needed,
            on_log=self._on_log,
        )
```

**Acceptance Criteria:**
- ✅ Worker uses the task-specific workdir from config
- ✅ No changes needed to git operation logic (already isolated by workdir)
- ✅ Lock detection warning still functional

---

#### Task 1.4: Update Task Creation Flow
**File:** `agents_runner/ui/main_window_tasks_agent.py`

**Changes:**
In `_start_task_from_ui()` method (line 58):

1. Generate `task_id` earlier (before workspace calculation)
2. Pass `task_id` to `_new_task_workspace()`
3. Ensure effective_workdir is task-specific

```python
def _start_task_from_ui(
    self,
    prompt: str,
    host_codex: str,
    env_id: str,
    base_branch: str,
) -> None:
    # ... validation ...
    
    task_id = uuid4().hex[:10]  # Generate early
    
    # ... environment resolution ...
    
    # Pass task_id for workspace isolation
    effective_workdir, ready, message = self._new_task_workspace(env, task_id=task_id)
    
    # ... rest of task creation ...
```

**Acceptance Criteria:**
- ✅ task_id generated before workspace allocation
- ✅ Workspace path includes task_id
- ✅ Each concurrent task gets isolated directory

---

### Phase 2: Cleanup & Resource Management (Priority: High)

#### Task 2.1: Implement Task Directory Cleanup
**File:** `agents_runner/environments/cleanup.py` (NEW)

**Purpose:** Clean up old task-specific checkout directories to prevent disk bloat.

```python
import os
import shutil
import time
from typing import Callable

def cleanup_old_task_repos(
    env_id: str,
    data_dir: str | None = None,
    max_age_days: int = 7,
    on_log: Callable[[str], None] | None = None
) -> int:
    """
    Remove task checkout directories older than max_age_days.
    
    Returns:
        Number of directories removed.
    """
    from .paths import managed_repo_checkout_path, _safe_env_id
    
    base_path = managed_repo_checkout_path(env_id, data_dir=data_dir)
    tasks_dir = os.path.join(base_path, "tasks")
    
    if not os.path.isdir(tasks_dir):
        return 0
    
    now = time.time()
    max_age_s = max_age_days * 86400
    removed_count = 0
    
    for task_id_dir in os.listdir(tasks_dir):
        task_path = os.path.join(tasks_dir, task_id_dir)
        if not os.path.isdir(task_path):
            continue
        
        try:
            mtime = os.path.getmtime(task_path)
            age_s = now - mtime
            
            if age_s > max_age_s:
                if on_log:
                    on_log(f"[cleanup] removing old task repo: {task_id_dir} (age: {age_s/86400:.1f} days)")
                shutil.rmtree(task_path)
                removed_count += 1
        except Exception as exc:
            if on_log:
                on_log(f"[cleanup] failed to remove {task_id_dir}: {exc}")
    
    return removed_count


def cleanup_on_task_completion(
    task_id: str,
    env_id: str,
    data_dir: str | None = None,
    keep_on_error: bool = True,
    on_log: Callable[[str], None] | None = None
) -> bool:
    """
    Remove task-specific checkout directory after task completes.
    
    Args:
        keep_on_error: If True, keep directory when task failed (for debugging)
    
    Returns:
        True if removed, False if kept or error
    """
    from .paths import managed_repo_checkout_path
    
    task_path = managed_repo_checkout_path(env_id, data_dir=data_dir, task_id=task_id)
    
    if not os.path.isdir(task_path):
        return False
    
    try:
        if on_log:
            on_log(f"[cleanup] removing task checkout: {task_id}")
        shutil.rmtree(task_path)
        return True
    except Exception as exc:
        if on_log:
            on_log(f"[cleanup] failed to remove task checkout: {exc}")
        return False
```

**Integration Points:**
- Call `cleanup_on_task_completion()` in `_clean_old_tasks()` (main_window_tasks_agent.py)
- Add periodic cleanup trigger (e.g., on app startup, or manual button in UI)

**Acceptance Criteria:**
- ✅ Removes task directories older than N days
- ✅ Optional immediate cleanup on task completion
- ✅ Keeps failed task dirs if configured (for debugging)
- ✅ Safe error handling (no crash on permission errors)

---

#### Task 2.2: Add Cleanup Integration
**File:** `agents_runner/ui/main_window_tasks_agent.py`

**Changes:**
```python
def _clean_old_tasks(self) -> None:
    from agents_runner.environments.cleanup import cleanup_on_task_completion
    
    to_remove: set[str] = set()
    for task_id, task in self._tasks.items():
        status = (task.status or "").lower()
        if status in {"done", "failed", "error"} and not task.is_active():
            to_remove.add(task_id)
            
            # Clean up task-specific git repo (if using GH_MANAGEMENT_GITHUB)
            if hasattr(task, "environment_id") and task.environment_id:
                env = self._environments.get(task.environment_id)
                if env and env.gh_management_mode == GH_MANAGEMENT_GITHUB:
                    keep_on_error = (status == "failed" or status == "error")
                    cleanup_on_task_completion(
                        task_id=task.task_id,
                        env_id=env.env_id,
                        data_dir=os.path.dirname(self._state_path),
                        keep_on_error=keep_on_error,
                        on_log=lambda msg: None  # Silent cleanup
                    )
    # ... rest of existing cleanup logic ...
```

**Acceptance Criteria:**
- ✅ Task repos cleaned up when tasks archived
- ✅ Failed task repos optionally kept for debugging
- ✅ No cleanup for non-GitHub environments
- ✅ Silent operation (no user-facing errors)

---

### Phase 3: Safety & Locking (Priority: Medium - Optional)

#### Task 3.1: Add Git Operation Lock (Optional)
**File:** `agents_runner/gh/git_lock.py` (NEW)

**Purpose:** File-based locking for shared repository scenarios (edge cases).

```python
import os
import time
import fcntl
from contextlib import contextmanager
from typing import Generator

class GitLockTimeout(Exception):
    """Raised when git lock acquisition times out."""
    pass


@contextmanager
def git_operation_lock(
    repo_path: str,
    timeout_s: float = 30.0,
    lock_name: str = "agents-runner"
) -> Generator[None, None, None]:
    """
    File-based lock for git operations in shared repositories.
    
    Usage:
        with git_operation_lock("/path/to/repo"):
            # perform git operations
            git("fetch")
    """
    lock_dir = os.path.join(repo_path, ".git")
    if not os.path.isdir(lock_dir):
        # Not a git repo, no locking needed
        yield
        return
    
    lock_file_path = os.path.join(lock_dir, f"{lock_name}.lock")
    lock_fd = None
    
    try:
        lock_fd = os.open(lock_file_path, os.O_CREAT | os.O_RDWR, 0o644)
        
        start = time.time()
        while True:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                elapsed = time.time() - start
                if elapsed >= timeout_s:
                    raise GitLockTimeout(
                        f"Could not acquire git lock after {timeout_s}s: {repo_path}"
                    )
                time.sleep(0.1)
        
        yield
        
    finally:
        if lock_fd is not None:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
                os.close(lock_fd)
            except Exception:
                pass
            try:
                os.unlink(lock_file_path)
            except Exception:
                pass
```

**Integration:** Wrap git operations in `git_ops.py` with lock context.

**Acceptance Criteria:**
- ✅ Prevents concurrent git operations in same repo
- ✅ Times out gracefully with clear error
- ✅ Cleans up lock file on exit
- ✅ No deadlocks

**Note:** This is **optional** because Phase 1 already isolates tasks. Only needed if:
- Users manually share task directories
- Future feature requires shared git state

---

### Phase 4: Testing & Validation (Priority: High)

#### Task 4.1: Manual Testing Checklist

**Test Case 1: Concurrent Task Isolation**
- [ ] Create environment with `GH_MANAGEMENT_GITHUB` mode
- [ ] Start Task A with prompt "Create file A.txt"
- [ ] Immediately start Task B with prompt "Create file B.txt"
- [ ] Verify both tasks complete successfully without conflicts
- [ ] Verify Task A has only A.txt, Task B has only B.txt
- [ ] Check no `.git/index.lock` errors in logs

**Test Case 2: Unique Checkout Directories**
- [ ] Create 3 tasks in same environment
- [ ] Verify 3 separate directories under `managed-repos/{env_id}/tasks/`
- [ ] Verify each has its own `.git` directory
- [ ] Verify each has correct branch checked out

**Test Case 3: Backward Compatibility**
- [ ] Create environment with `GH_MANAGEMENT_LOCAL` mode
- [ ] Verify tasks use the configured local directory
- [ ] Verify no task-specific subdirectories created

**Test Case 4: Cleanup**
- [ ] Complete a task successfully
- [ ] Archive the task
- [ ] Verify task checkout directory is removed
- [ ] Verify failed task directories are kept (if configured)

**Test Case 5: Branch Management**
- [ ] Start task, let it create branch `midoriaiagents/{task_id}`
- [ ] Verify branch only exists in that task's checkout
- [ ] Start another task, verify it gets different branch
- [ ] Verify no branch name conflicts

**Test Case 6: PR Creation**
- [ ] Complete task with changes
- [ ] Verify PR is created from correct branch
- [ ] Verify PR targets correct base branch
- [ ] Verify no interference between concurrent task PRs

---

#### Task 4.2: Edge Case Testing

**Edge Case 1: Rapid Task Creation**
- [ ] Create 5 tasks within 1 second
- [ ] Verify all get unique task_ids
- [ ] Verify all get unique checkout directories
- [ ] Verify no race conditions

**Edge Case 2: Disk Space Exhaustion**
- [ ] Simulate low disk space scenario
- [ ] Verify graceful error handling
- [ ] Verify no repository corruption

**Edge Case 3: Stale Lock Detection**
- [ ] Manually create `.git/index.lock` in task directory
- [ ] Start task
- [ ] Verify warning message appears
- [ ] Verify task can proceed after manual cleanup

---

### Phase 5: Documentation (Priority: Medium)

#### Task 5.1: Update Implementation Docs
**File:** `.codex/implementation/gh_management.md`

Add section:
```markdown
## Task Isolation Architecture

### Directory Structure
- Shared environment: `~/.midoriai/agents-runner/managed-repos/{env_id}/`
- Task-specific: `~/.midoriai/agents-runner/managed-repos/{env_id}/tasks/{task_id}/`

### Isolation Strategy
Each task using GH_MANAGEMENT_GITHUB gets its own git clone to prevent:
- Index lock collisions
- Working tree contamination
- Branch conflicts

### Cleanup Policy
- Successful tasks: Cleanup on archive (default)
- Failed tasks: Keep for debugging (configurable)
- Old tasks: Auto-cleanup after 7 days (configurable)
```

#### Task 5.2: Update User Documentation
**File:** `README.md` (if requested)

Add note about concurrent task support in GitHub management mode.

---

## Dependencies & Order

**Critical Path:**
1. Task 1.1 (paths) → Task 1.2 (workspace) → Task 1.3 (worker) → Task 1.4 (UI)
2. Task 2.1 (cleanup module) → Task 2.2 (cleanup integration)

**Parallel Work:**
- Task 3.1 (optional locking) - can be done independently
- Task 5.1 & 5.2 (docs) - can be done after Phase 1 completes

**Testing:**
- Task 4.1 & 4.2 - after Phase 1 & 2 complete

---

## Rollout Strategy

### Stage 1: Development (Local Testing)
- Implement Phase 1 & 2
- Manual testing with 2-3 concurrent tasks
- Verify no regressions

### Stage 2: Beta (Opt-In)
- Deploy to test users
- Monitor for issues
- Collect feedback on cleanup behavior

### Stage 3: Production
- Enable for all users
- Monitor disk usage
- Adjust cleanup thresholds based on usage

---

## Risk Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| Disk space exhaustion | High | Aggressive cleanup policy, monitoring |
| Race conditions during cleanup | Medium | Use atomic operations, exception handling |
| Breaking existing workflows | High | Extensive backward compatibility testing |
| Performance degradation | Low | Cloning is async, minimal UI impact |

---

## Success Metrics

- ✅ Zero `.git/index.lock` errors in concurrent scenarios
- ✅ Zero working tree contamination reports
- ✅ 100% backward compatibility with single-task environments
- ✅ Disk usage under control (<1GB per 100 tasks)
- ✅ No performance regressions in task startup time

---

## Open Questions

1. **Cleanup Timing**: Should cleanup be:
   - Immediate on task archive? (current plan)
   - Delayed (background job)?
   - Manual only?

2. **Failed Task Retention**: How long to keep failed task repos?
   - Default: Keep indefinitely (for debugging)
   - Or: Auto-cleanup after 7 days with warning?

3. **Disk Quota**: Should we enforce per-environment disk limits?
   - Probably not in v1 - add monitoring first

4. **Shared Base Repository**: Should we optimize by having a shared `.git` and task-specific worktrees?
   - No - adds complexity, git worktrees have their own issues
   - Current approach is simple and robust

---

## Acceptance Criteria (Overall)

- [x] Requirements documented
- [ ] All Phase 1 tasks completed
- [ ] All Phase 2 tasks completed
- [ ] Phase 3 decision made (implement or defer)
- [ ] All test cases pass
- [ ] Documentation updated
- [ ] No regressions in existing functionality
- [ ] Code review approved
- [ ] Deployed to production

---

## Notes

- This plan prioritizes **simplicity** and **robustness** over optimization
- Each task gets a full clone rather than worktrees - more disk, but simpler logic
- Cleanup is aggressive by default to prevent disk bloat
- Git locking (Phase 3) is optional - Phase 1 isolation should be sufficient

---

**Created:** 2025-01-06  
**Author:** Task Master  
**Reviewed By:** (pending)  
**Status:** Ready for Coder pickup
