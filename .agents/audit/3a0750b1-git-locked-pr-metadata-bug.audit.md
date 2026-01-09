# Audit Report: Git-Locked Environment PR Metadata Failure

**Audit ID:** 3a0750b1  
**Date:** 2026-01-09  
**Auditor:** Auditor #1  
**Issue:** Git-locked environments sometimes fail to provide PR metadata to tasks

---

## Executive Summary

**Severity:** HIGH  
**Impact:** Users unable to create PRs even when git operations succeed  
**Root Cause:** Silent exception handling causes metadata file to remain unpopulated

The investigation revealed a critical bug where the GitHub context file is created empty for git-locked environments but may never be populated with actual repository data due to silent exception handling. This causes PR creation to fail with "This task is missing repo/branch metadata" even though logs show successful GitHub context updates.

---

## Problem Analysis

### User-Reported Symptoms

1. Git-locked environment tasks complete successfully
2. Logs show:
   ```
   [gh] GitHub context enabled; mounted -> /tmp/github-context-0673ef05d3.json
   [gh] updated GitHub context file
   ```
3. After task completion, attempting to create a PR shows error modal:
   ```
   "This task is missing repo/branch metadata."
   ```
4. The error appears AFTER the task completes, when user clicks "Create PR"

### Investigation Findings

#### Finding 1: Two-Phase GitHub Context File Creation (CRITICAL BUG)

**Location:** `agents_runner/ui/main_window_tasks_agent.py:386-415`

For git-locked environments (`GH_MANAGEMENT_GITHUB`), the code follows a two-phase approach:

**Phase 1: File Creation (Before Container Launch)**
```python
elif gh_mode == GH_MANAGEMENT_GITHUB:
    # Git-locked: Will populate after clone
    should_generate = True

# Later...
if should_generate:
    ensure_github_context_file(
        host_path, 
        task_id=task_id,
        github_context=github_context,  # THIS IS None FOR GIT-LOCKED!
    )
```

Looking at `agents_runner/pr_metadata.py:93-141`:
```python
def ensure_github_context_file(
    path: str,
    *,
    task_id: str,
    github_context: GitHubContext | None = None,
) -> None:
    # ...
    if github_context:
        payload["github"] = {
            "repo_url": github_context.repo_url,
            # ... full context
        }
    else:
        payload["github"] = None  # <-- FILE CONTAINS NULL!
```

**Result:** The file is created with `"github": null` before the container starts.

**Phase 2: File Population (After Repository Clone)**
```python
# agents_runner/docker/agent_worker.py:128-152
if self._config.gh_context_file_path and self._gh_repo_root:
    try:
        git_info = get_git_info(self._gh_repo_root)
        if git_info:
            github_context = GitHubContext(...)
            update_github_context_after_clone(
                self._config.gh_context_file_path,
                github_context=github_context,
            )
            self._on_log("[gh] updated GitHub context file")
    except Exception as exc:
        self._on_log(f"[gh] failed to update GitHub context: {exc}")
        # Don't fail the task if context update fails  <-- SILENT FAILURE!
```

**THE BUG:** If any exception occurs during Phase 2:
- The exception is caught and logged
- Execution continues normally
- The GitHub context file remains with `"github": null`
- The task completes "successfully"
- When user tries to create PR, `task.gh_repo_root` is empty because it was never populated

#### Finding 2: Multiple Failure Points in Phase 2

The Phase 2 update can fail silently for several reasons:

**Failure Point A: `get_git_info()` returns `None`**
```python
# agents_runner/environments/git_operations.py:40-116
def get_git_info(path: str) -> Optional[GitInfo]:
    try:
        if not is_git_repo(path):
            logger.debug(f"[gh] path is not a git repository: {path}")
            return None  # <-- SILENT RETURN
        
        repo_root = git_repo_root(path)
        if not repo_root:
            logger.warning(f"[gh] could not determine git repo root: {path}")
            return None  # <-- SILENT RETURN
        
        # ... more checks that can return None
    except Exception as exc:
        logger.error(f"[gh] unexpected error during git detection: {exc}")
        return None  # <-- SILENT RETURN
```

When `get_git_info()` returns `None`, the code in agent_worker.py does:
```python
git_info = get_git_info(self._gh_repo_root)
if git_info:
    # ... update context
    self._on_log("[gh] updated GitHub context file")
# ELSE: NOTHING! No log, no error, file stays with null github object
```

**Failure Point B: `update_github_context_after_clone()` throws exception**
```python
# agents_runner/pr_metadata.py:144-183
def update_github_context_after_clone(...) -> None:
    if not path or not os.path.exists(path):
        raise ValueError(f"GitHub context file does not exist: {path}")
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except Exception as exc:
        raise ValueError(f"Failed to read GitHub context file: {exc}") from exc
    # ... any of these can throw
```

These exceptions are caught by the outer try/except and logged but not re-raised.

**Failure Point C: Race condition with file system**

The context file is created on the host, then mounted into the container. Between creation and mounting, or during the git clone operation, file system issues could occur:
- File deleted/moved by another process
- Permission changes
- Mount fails silently

#### Finding 3: Lack of Validation Before Task Completion

**Location:** `agents_runner/docker/agent_worker.py:128-152`

There is NO validation to ensure the GitHub context file was successfully populated before the task is considered complete. The code logs success but never verifies:

```python
self._on_log("[gh] updated GitHub context file")
```

This log message appears ONLY if `git_info` is not None AND no exception was thrown. However:
- If `git_info` is None, no log appears at all
- User sees the earlier log "[gh] GitHub context enabled; mounted -> ..." from Phase 1
- User assumes everything is working

#### Finding 4: Error Detection Deferred Until PR Creation

**Location:** `agents_runner/ui/main_window_task_review.py:44-58`

The actual error is only detected when the user tries to create a PR:

```python
repo_root = str(task.gh_repo_root or "").strip()
# ... attempt to set from env ...
if not repo_root:
    QMessageBox.warning(
        self, "PR not available", "This task is missing repo/branch metadata."
    )
    return
```

The `task.gh_repo_root` comes from the worker:
```python
# agents_runner/docker/agent_worker.py:122
self._gh_repo_root = str(result.get("repo_root") or "") or None
```

This is set during `prepare_github_repo_for_task()`. However, if the GitHub context file update fails, the task still has this value. The disconnect is:
- `task.gh_repo_root` comes from the worker's `prepare_github_repo_for_task()` result
- But this is NOT persisted correctly if the task is reloaded from state
- The GitHub context file SHOULD contain this data but doesn't if Phase 2 failed

#### Finding 5: State Persistence Gap

**Location:** `agents_runner/persistence.py:307` and `agents_runner/ui/main_window_task_events.py:345-350`

When a task completes, its properties are saved:
```python
# Serialization
"gh_repo_root": getattr(task, "gh_repo_root", ""),
```

The `gh_repo_root` is populated from the bridge:
```python
# agents_runner/ui/main_window_task_events.py:345-346
if bridge.gh_repo_root:
    task.gh_repo_root = bridge.gh_repo_root
```

**CRITICAL TIMING ISSUE:** This happens in the `_on_done` handler. However, if the worker completes before the bridge property is read, or if the application is restarted before this is saved, the task will have an empty `gh_repo_root`.

The GitHub context file is supposed to be the source of truth for this data, but it contains `null` due to the Phase 2 failure.

---

## Specific Code Sections with Issues

### Issue 1: Silent Failure in Context Update (HIGH PRIORITY)

**File:** `agents_runner/docker/agent_worker.py`  
**Lines:** 150-152  
**Problem:**
```python
except Exception as exc:
    self._on_log(f"[gh] failed to update GitHub context: {exc}")
    # Don't fail the task if context update fails
```

This catches ALL exceptions and continues silently. The task appears to succeed but PR creation is broken.

**Recommended Fix:**
```python
except Exception as exc:
    self._on_log(f"[gh] ERROR: failed to update GitHub context: {exc}")
    self._on_log("[gh] WARNING: PR creation may fail due to missing metadata")
    # Set a flag that PR creation is unavailable
    # OR: Mark the task with a warning state
```

### Issue 2: Missing Logging When git_info is None (MEDIUM PRIORITY)

**File:** `agents_runner/docker/agent_worker.py`  
**Lines:** 135-149  
**Problem:**
```python
git_info = get_git_info(self._gh_repo_root)
if git_info:
    # ... update and log success
# MISSING: else clause to log failure!
```

When `get_git_info()` returns None, there's NO log message, leaving the user confused.

**Recommended Fix:**
```python
git_info = get_git_info(self._gh_repo_root)
if git_info:
    github_context = GitHubContext(...)
    update_github_context_after_clone(...)
    self._on_log("[gh] updated GitHub context file")
else:
    self._on_log("[gh] WARNING: could not detect git info after clone")
    self._on_log("[gh] WARNING: PR creation may fail due to missing metadata")
```

### Issue 3: Overly Aggressive Error Suppression in get_git_info (MEDIUM PRIORITY)

**File:** `agents_runner/environments/git_operations.py`  
**Lines:** 113-116  
**Problem:**
```python
except Exception as exc:
    # Catch-all to ensure we never raise
    logger.error(f"[gh] unexpected error during git detection: {exc}", exc_info=True)
    return None
```

While this prevents task failures, it makes debugging extremely difficult. The error is logged to the logger but not to the user-visible task log.

**Recommended Fix:**
```python
except Exception as exc:
    logger.error(f"[gh] unexpected error during git detection: {exc}", exc_info=True)
    # Return a minimal GitInfo with error indication, or
    # Re-raise as a specific exception type that caller can handle
    return None
```

### Issue 4: No Validation Before Container Launch (MEDIUM PRIORITY)

**File:** `agents_runner/docker/agent_worker.py`  
**Lines:** After line 152  
**Problem:** No validation that the GitHub context file was successfully populated.

**Recommended Fix:**
```python
except Exception as exc:
    self._on_log(f"[gh] failed to update GitHub context: {exc}")
    # Validate that the file was populated
    try:
        from agents_runner.pr_metadata import load_github_metadata
        metadata = load_github_metadata(self._config.gh_context_file_path)
        if metadata is None or metadata.github is None:
            self._on_log("[gh] WARNING: GitHub context file not populated")
            self._on_log("[gh] WARNING: PR creation will be unavailable")
    except Exception:
        pass  # Already logged the main error
```

### Issue 5: Misleading Success Log (LOW PRIORITY)

**File:** `agents_runner/ui/main_window_tasks_agent.py`  
**Lines:** 413-415  
**Problem:**
```python
self._on_task_log(
    task_id, f"[gh] GitHub context enabled; mounted -> {container_path}"
)
```

This log appears immediately after file creation (Phase 1) but before population (Phase 2), giving a false sense of success.

**Recommended Fix:**
```python
self._on_task_log(
    task_id, f"[gh] GitHub context file mounted -> {container_path} (will populate after clone)"
)
```

---

## Root Cause Summary

The bug has three contributing factors:

1. **Design Issue:** Two-phase file creation with async population creates a window for failure
2. **Error Handling Issue:** Silent exception catching hides failures from users
3. **Validation Gap:** No verification that Phase 2 succeeded before task completion

The combination means:
- File created successfully (Phase 1 ✓)
- Clone succeeds (git operations ✓)
- Phase 2 fails silently (exception caught ✗)
- User sees "GitHub context enabled" log from Phase 1
- User sees "updated GitHub context file" log if git_info was valid
- Task completes successfully
- PR creation fails because file contains `"github": null`

---

## Recommended Fixes (Priority Order)

### Fix 1: Add Explicit Logging for git_info Failure (IMMEDIATE)

**File:** `agents_runner/docker/agent_worker.py:135-149`

```python
git_info = get_git_info(self._gh_repo_root)
if git_info:
    github_context = GitHubContext(
        repo_url=git_info.repo_url,
        repo_owner=git_info.repo_owner,
        repo_name=git_info.repo_name,
        base_branch=self._gh_base_branch or git_info.branch,
        task_branch=self._gh_branch,
        head_commit=git_info.commit_sha,
    )
    update_github_context_after_clone(
        self._config.gh_context_file_path,
        github_context=github_context,
    )
    self._on_log("[gh] updated GitHub context file")
else:
    self._on_log("[gh] WARNING: git detection failed after clone")
    self._on_log(f"[gh] WARNING: could not read git info from {self._gh_repo_root}")
    self._on_log("[gh] WARNING: PR creation will be unavailable for this task")
```

### Fix 2: Improve Exception Logging (IMMEDIATE)

**File:** `agents_runner/docker/agent_worker.py:150-152`

```python
except Exception as exc:
    self._on_log(f"[gh] ERROR: failed to update GitHub context: {exc}")
    self._on_log(f"[gh] ERROR: exception type: {type(exc).__name__}")
    self._on_log("[gh] WARNING: PR creation will be unavailable for this task")
    # Still don't fail the task, but make the problem visible
```

### Fix 3: Add Validation After Clone (HIGH PRIORITY)

**File:** `agents_runner/docker/agent_worker.py` (after line 152)

Add validation to ensure the file was populated:

```python
# After the try/except block for update_github_context_after_clone
# Validate that the GitHub context file was successfully populated
if self._config.gh_context_file_path:
    try:
        from agents_runner.pr_metadata import load_github_metadata
        metadata = load_github_metadata(self._config.gh_context_file_path)
        if metadata is None:
            self._on_log("[gh] WARNING: could not read GitHub context file")
            self._on_log("[gh] WARNING: PR creation will be unavailable")
        elif metadata.github is None:
            self._on_log("[gh] WARNING: GitHub context file not populated with repo data")
            self._on_log("[gh] WARNING: PR creation will be unavailable")
        else:
            # Success - file is properly populated
            self._on_log(f"[gh] verified context: {metadata.github.repo_name}")
    except Exception as validation_exc:
        self._on_log(f"[gh] WARNING: could not validate context file: {validation_exc}")
```

### Fix 4: Propagate get_git_info Errors to User Log (MEDIUM PRIORITY)

**File:** `agents_runner/environments/git_operations.py:40-116`

Modify to accept an optional logging callback:

```python
def get_git_info(path: str, *, on_log: Callable[[str], None] | None = None) -> Optional[GitInfo]:
    """Detect git repository context for a given path.
    
    Args:
        path: File system path to check
        on_log: Optional callback for user-visible log messages
    """
    def _log(msg: str) -> None:
        if on_log:
            on_log(msg)
        logger.debug(msg)
    
    try:
        if not is_git_repo(path):
            _log(f"[gh] path is not a git repository: {path}")
            return None
        
        repo_root = git_repo_root(path)
        if not repo_root:
            _log(f"[gh] could not determine git repo root: {path}")
            return None
        
        # ... rest of function with _log calls
```

Then call it with the logging callback:

```python
# In agent_worker.py:135
git_info = get_git_info(self._gh_repo_root, on_log=self._on_log)
```

### Fix 5: Improve Early Log Message (LOW PRIORITY)

**File:** `agents_runner/ui/main_window_tasks_agent.py:413-415`

```python
self._on_task_log(
    task_id, f"[gh] GitHub context file created and mounted -> {container_path}"
)
self._on_task_log(
    task_id, "[gh] context will be populated after repository clone"
)
```

---

## Testing Recommendations

After implementing fixes, test these scenarios:

1. **Normal Case:** Git-locked environment with valid repository
   - Expected: Both Phase 1 and Phase 2 succeed, PR creation works

2. **Invalid Path:** Git-locked environment where `_gh_repo_root` points to non-existent path
   - Expected: Clear error logs, PR creation fails gracefully

3. **Not a Git Repo:** Path exists but is not a git repository
   - Expected: Clear warning logs, PR creation unavailable

4. **Git Operations Fail:** Repository exists but git commands timeout
   - Expected: Error logged, PR creation unavailable

5. **File System Issues:** Context file deleted between Phase 1 and Phase 2
   - Expected: Error caught and logged, PR creation unavailable

6. **State Reload:** Complete task, restart app, try to create PR
   - Expected: Should work if context file was properly populated

---

## Impact Assessment

**Current State:**
- Users encounter confusing errors after successful task completion
- No clear indication that PR creation will fail
- Debugging requires checking context file manually
- Support burden increased due to unclear error messages

**After Fixes:**
- Clear, actionable error messages when git detection fails
- Users know immediately if PR creation will be unavailable
- Easier debugging with detailed logs
- Reduced support burden

---

## Additional Observations

1. The two-phase approach is architecturally sound but needs better error handling
2. The logging system has two levels (Python logger vs task log) which can cause confusion
3. The `get_git_info()` function's "never raise" guarantee makes error propagation difficult
4. Consider adding a health check endpoint that validates GitHub context files

---

## Files Analyzed

- `/home/runner/work/Agents-Runner/Agents-Runner/agents_runner/docker/agent_worker.py` (lines 111-157)
- `/home/runner/work/Agents-Runner/Agents-Runner/agents_runner/pr_metadata.py` (lines 93-183)
- `/home/runner/work/Agents-Runner/Agents-Runner/agents_runner/environments/git_operations.py` (complete)
- `/home/runner/work/Agents-Runner/Agents-Runner/agents_runner/ui/main_window_tasks_agent.py` (lines 340-420)
- `/home/runner/work/Agents-Runner/Agents-Runner/agents_runner/ui/main_window_task_review.py` (complete)
- `/home/runner/work/Agents-Runner/Agents-Runner/agents_runner/ui/main_window_tasks_interactive_finalize.py` (complete)
- `/home/runner/work/Agents-Runner/Agents-Runner/agents_runner/persistence.py` (lines 300-360)

---

## Conclusion

The bug is caused by silent exception handling in the GitHub context file population phase (Phase 2) combined with lack of validation before task completion. The recommended fixes focus on:

1. Making failures visible to users through improved logging
2. Adding validation to detect population failures
3. Providing clear warnings when PR creation will be unavailable

The fixes are designed to be minimal and surgical, focusing on error visibility rather than architectural changes. This allows users to understand what went wrong and take appropriate action (e.g., manually creating PRs, checking repository paths, etc.).

All recommended changes maintain backward compatibility and don't change the core two-phase approach, which is fundamentally sound but needs better observability.
