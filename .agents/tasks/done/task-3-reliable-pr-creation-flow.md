# Task 3: Reliable Create Pull Request Flow

## Objective
Implement a robust, user-friendly PR creation workflow that handles all edge cases gracefully. The flow should work reliably for both git-locked environments (auto PR) and folder-locked environments (manual override PR), with clear feedback at every step.

## Current State

### Existing PR Creation Code

#### For Git-Locked Tasks (Auto PR)
File: `agents_runner/ui/main_window_tasks_interactive_finalize.py`
- Line 28-86: `_on_interactive_finished()` - Prompts user after interactive task
- Line 87-221: `_finalize_gh_management_worker()` - Worker thread that creates PR

File: `agents_runner/gh/task_plan.py`
- Line 198-369: `commit_push_and_pr()` - Core PR creation logic
- Handles: commit, push, gh pr create

#### For Folder-Locked Tasks (Manual Override)
File: `agents_runner/ui/main_window_task_review.py`
- Line 16-43: `_on_task_pr_requested()` - Handles "Create PR" button
- Uses same `_finalize_gh_management_worker()` with `is_override=True`

### Known Issues and Gaps

1. **Unclear feedback when PR already exists**
   - `gh pr create` fails with "pull request already exists" error
   - User sees generic error, doesn't know how to proceed
   - Should detect existing PR and show URL instead

2. **No validation of prerequisites**
   - Doesn't check if `gh` CLI is authenticated before starting
   - Doesn't verify repository has remote configured
   - Doesn't check if branch already exists on remote

3. **Dirty worktree edge cases**
   - Current code attempts `--merge` checkout (line 275-290)
   - Can leave repository in conflicted state
   - Error messages are technical and unhelpful

4. **No progress indication**
   - PR creation can take 10-20 seconds
   - User only sees "preparing PR" then success/failure
   - No intermediate status updates

5. **Missing retry logic**
   - Network failures cause complete failure
   - No automatic retry for transient errors
   - User must manually restart entire process

## Requirements

### 1. Pre-flight Validation

Before starting PR creation, validate:

#### Check 1: Git Repository
```python
def _validate_git_repo(repo_root: str) -> tuple[bool, str]:
    """Verify path is a valid git repository."""
    if not os.path.isdir(repo_root):
        return (False, "repository path does not exist")
    
    if not os.path.isdir(os.path.join(repo_root, ".git")):
        return (False, "not a git repository (no .git folder)")
    
    # Test git command works
    proc = _run(["git", "-C", repo_root, "status"], timeout_s=5.0)
    if proc.returncode != 0:
        return (False, "git command failed")
    
    return (True, "ok")
```

#### Check 2: Remote Configuration
```python
def _validate_remote(repo_root: str) -> tuple[bool, str]:
    """Verify origin remote is configured."""
    from agents_runner.gh.git_ops import git_remote_url
    
    remote_url = git_remote_url(repo_root, remote="origin")
    if not remote_url:
        return (False, "no origin remote configured")
    
    return (True, f"remote: {remote_url}")
```

#### Check 3: GitHub CLI
```python
def _validate_gh_cli(use_gh: bool) -> tuple[bool, str]:
    """Verify gh CLI is available and authenticated."""
    if not use_gh:
        return (True, "gh CLI disabled")
    
    from agents_runner.gh.gh_cli import is_gh_available
    
    if not is_gh_available():
        return (False, "gh CLI not installed")
    
    # Check authentication
    proc = _run(["gh", "auth", "status"], timeout_s=10.0)
    if proc.returncode != 0:
        return (False, "gh CLI not authenticated (run 'gh auth login')")
    
    return (True, "gh CLI ready")
```

#### Check 4: Existing PR
```python
def _check_existing_pr(repo_root: str, branch: str) -> str | None:
    """Check if PR already exists for branch. Returns PR URL or None."""
    from agents_runner.gh.gh_cli import is_gh_available
    
    if not is_gh_available():
        return None
    
    proc = _run(
        ["gh", "pr", "list", "--head", branch, "--json", "url", "--jq", ".[0].url"],
        cwd=repo_root,
        timeout_s=15.0,
    )
    
    if proc.returncode == 0 and proc.stdout:
        url = proc.stdout.strip()
        if url.startswith("http"):
            return url
    
    return None
```

### 2. Progressive Status Updates

Modify `_finalize_gh_management_worker()` to emit detailed progress:

```python
# Current: Single "PR preparation started" message
# New: Progress updates at each step

self.host_log.emit(task_id, format_log("gh", "pr", "INFO", "[1/6] Validating repository..."))
# ... validation ...

self.host_log.emit(task_id, format_log("gh", "pr", "INFO", "[2/6] Checking for existing PR..."))
# ... existing PR check ...

self.host_log.emit(task_id, format_log("gh", "pr", "INFO", "[3/6] Switching to task branch..."))
# ... branch checkout ...

self.host_log.emit(task_id, format_log("gh", "pr", "INFO", "[4/6] Committing changes..."))
# ... git add + commit ...

self.host_log.emit(task_id, format_log("gh", "pr", "INFO", "[5/6] Pushing to remote..."))
# ... git push ...

self.host_log.emit(task_id, format_log("gh", "pr", "INFO", "[6/6] Creating pull request..."))
# ... gh pr create ...
```

### 3. Enhanced Error Messages

Replace technical errors with user-friendly messages:

#### Error: PR Already Exists
```python
# Current: "pull request already exists" + failure
# New:
existing_pr_url = _check_existing_pr(repo_root, branch)
if existing_pr_url:
    self.host_log.emit(
        task_id,
        format_log("gh", "pr", "INFO", f"Pull request already exists: {existing_pr_url}")
    )
    self.host_pr_url.emit(task_id, existing_pr_url)
    return  # Success, not error
```

#### Error: Dirty Worktree
```python
# Current: Generic merge conflict error
# New:
if not _porcelain_status().strip():
    self.host_log.emit(
        task_id,
        format_log("gh", "pr", "ERROR", 
                   "Repository has uncommitted changes. Please commit or stash them first.")
    )
    self.host_log.emit(
        task_id,
        format_log("gh", "pr", "INFO",
                   "Run: git stash or git commit -am 'Your message'")
    )
    return
```

#### Error: Not Authenticated
```python
# Current: Generic gh error
# New:
if not gh_is_authenticated():
    self.host_log.emit(
        task_id,
        format_log("gh", "pr", "ERROR",
                   "GitHub CLI is not authenticated")
    )
    self.host_log.emit(
        task_id,
        format_log("gh", "pr", "INFO",
                   "Run: gh auth login")
    )
    return
```

### 4. Retry Logic for Network Failures

Add retry wrapper for network operations:

```python
def _with_retry(
    operation: Callable[[], T],
    *,
    max_attempts: int = 3,
    retry_delay_s: float = 2.0,
    retry_on: tuple[type[Exception], ...] = (OSError, TimeoutError),
) -> T:
    """Retry operation on transient failures."""
    for attempt in range(1, max_attempts + 1):
        try:
            return operation()
        except retry_on as exc:
            if attempt >= max_attempts:
                raise
            time.sleep(retry_delay_s * attempt)  # Exponential backoff
            continue
    raise RuntimeError("unreachable")
```

Apply to:
- `git fetch` (network)
- `git push` (network)
- `gh pr create` (network + API)

### 5. Graceful Degradation

If PR creation fails, ensure:
1. Commits are NOT lost
2. Branch is pushed to remote (even if PR fails)
3. User receives instructions to create PR manually

```python
# After push succeeds but PR fails
self.host_log.emit(
    task_id,
    format_log("gh", "pr", "WARN",
               "Branch pushed successfully but PR creation failed")
)
self.host_log.emit(
    task_id,
    format_log("gh", "pr", "INFO",
               f"Create PR manually at: https://github.com/owner/repo/compare/{branch}")
)
```

### 6. Cancel Button

Add ability to cancel in-progress PR creation:

File: `agents_runner/ui/pages/task_details.py`

```python
# Add "Cancel PR" button when PR creation is in progress
# Signal to worker thread to abort
# Clean up any partial state
```

## Implementation Files

### New Files
1. `agents_runner/gh/pr_validation.py`
   - All pre-flight validation functions
   - `validate_pr_prerequisites()` - Master validator
   - Returns: `list[tuple[str, bool, str]]` (check_name, passed, message)

2. `agents_runner/gh/pr_retry.py`
   - Retry logic wrapper
   - Network failure detection
   - Exponential backoff

### Modified Files
3. `agents_runner/ui/main_window_tasks_interactive_finalize.py`
   - Add validation calls before starting worker
   - Add progress status updates (6 steps)
   - Add existing PR detection
   - Add retry wrappers
   - Improve error messages

4. `agents_runner/ui/main_window_task_review.py`
   - Same validation and improvements
   - Ensure consistent UX for manual PR creation

5. `agents_runner/gh/task_plan.py`
   - Extract reusable helper functions
   - Add better error context to exceptions
   - Add progress callback parameter

6. `agents_runner/ui/pages/task_details.py`
   - Add "Cancel PR" button during PR creation
   - Add signal handler for cancellation

## Testing Scenarios

### Scenario 1: Happy Path
- Git-locked task completes
- User clicks "Create PR"
- All validations pass
- PR created successfully
- URL displayed in logs and task details

### Scenario 2: PR Already Exists
- Task has existing PR
- User clicks "Create PR" again
- System detects existing PR
- Shows existing PR URL
- No error, just info message

### Scenario 3: Not Authenticated
- User hasn't run `gh auth login`
- Clicks "Create PR"
- Validation fails with clear message
- Instructions to authenticate shown
- Process aborts early (before any git operations)

### Scenario 4: Network Failure During Push
- Network drops during `git push`
- Retry logic kicks in (3 attempts)
- If retries succeed: continues to PR creation
- If retries fail: clear error message

### Scenario 5: Dirty Worktree
- User has uncommitted changes in repo
- Tries to create PR
- Clear error about uncommitted changes
- Instructions to stash or commit shown

### Scenario 6: Cancel During PR Creation
- User clicks "Create PR"
- Clicks "Cancel" during push step
- Worker thread stops gracefully
- Partial progress is logged
- Repository state is clean

### Scenario 7: Manual Override PR (Folder-Locked)
- Folder-locked environment
- User clicks "Review" → "Create PR"
- Same validation and flow as git-locked
- PR body includes override note

## Success Criteria

1. **100% validation coverage** - All prerequisites checked before starting
2. **Clear progress indication** - User sees 6 distinct steps with status
3. **Helpful error messages** - No raw git/gh errors, always actionable
4. **Existing PR detection** - Shows existing PR URL, doesn't treat as error
5. **Network resilience** - 3 automatic retries for network operations
6. **No data loss** - Commits and branches always preserved on failure
7. **Cancellable** - User can abort long-running operations
8. **Consistent UX** - Git-locked and folder-locked flows work identically

## UI Mockup

### Task Details - PR Creation in Progress

```
[Review ▼]  [Cancel PR]

Recent Activity:
  [gh] [pr] INFO  [1/6] Validating repository...
  [gh] [pr] INFO  [2/6] Checking for existing PR...
  [gh] [pr] INFO  [3/6] Switching to task branch...
  [gh] [pr] INFO  [4/6] Committing changes...
  [gh] [pr] INFO  [5/6] Pushing to remote... (attempt 1/3)
  [gh] [pr] INFO  [6/6] Creating pull request...
  [gh] [pr] INFO  PR: https://github.com/owner/repo/pull/123
```

### Task Details - PR Already Exists

```
[Review ▼]

Recent Activity:
  [gh] [pr] INFO  [1/6] Validating repository...
  [gh] [pr] INFO  [2/6] Checking for existing PR...
  [gh] [pr] INFO  Pull request already exists: https://github.com/owner/repo/pull/123
```

### Task Details - Validation Failed

```
[Review ▼]

Recent Activity:
  [gh] [pr] ERROR  GitHub CLI is not authenticated
  [gh] [pr] INFO   Run: gh auth login
```

## Related Files

### Dependencies
- `agents_runner/gh/task_plan.py` - Core PR creation
- `agents_runner/gh/gh_cli.py` - GitHub CLI wrapper
- `agents_runner/gh/git_ops.py` - Git operations
- `agents_runner/gh/errors.py` - Exception types

### Documentation
- `.agents/implementation/gh_management.md` - Git-locked feature
- `agents_runner/ui/pages/task_details.py` - UI integration

## Edge Cases

### 1. Branch Deleted on Remote
- Local branch exists, remote deleted
- Push will fail
- Clear message: "Remote branch was deleted, creating new one"

### 2. Force Push Needed
- Local and remote diverged
- Don't auto force-push (data loss risk)
- Error message: "Branch diverged, resolve manually"

### 3. Repository Moved/Renamed
- Remote URL changed
- Fetch will fail
- Error message: "Remote URL invalid, check repository settings"

### 4. Large Push (Many Commits)
- Push takes > 30 seconds
- Progress shown: "Pushing to remote... (still working)"
- Timeout increased for large repos

### 5. GitHub API Rate Limiting
- `gh pr create` hits rate limit
- Retry after delay doesn't help
- Error message: "GitHub API rate limited, try again in 1 hour"

## Performance Targets

- Validation: < 2 seconds
- Commit + Push: < 10 seconds (normal case)
- PR Creation: < 5 seconds (API call)
- Total: < 20 seconds for typical PR

## Notes

- Focus on user experience and error messaging
- Every error should tell user exactly what to do next
- Never leave repository in inconsistent state
- Log every step for debugging
- Consider adding telemetry for failure analysis (future)
- PR creation success rate should be > 95% after improvements
