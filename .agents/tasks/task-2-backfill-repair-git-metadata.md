# Task 2: Backfill and Repair Git Metadata for Existing Tasks

## Objective
Automatically detect and repair task files that are missing git metadata. This ensures historical tasks have proper context and enables consistent auditing across all git-locked tasks, new and old.

## Current State

### Task Storage
- Active tasks: `~/.midoriai/agents-runner/tasks/*.json`
- Done tasks: `~/.midoriai/agents-runner/tasks/done/*.json`
- Loading: `persistence.py::load_active_task_payloads()` (line 194)
- Loading: `persistence.py::load_done_task_payloads()` (line 232)

### Existing Git Metadata
Implemented in commit `ed8e55d` (Jan 11, 2026):
- Tasks created before this commit lack `git` field
- Tasks created after may have incomplete metadata
- Validation from Task 1 will identify incomplete tasks

### Metadata Sources
When repairing, attempt to reconstruct from:
1. GitHub context file (v2): `~/.midoriai/agents-runner/github-context/github-context-{task_id}.json`
2. Task fields: `gh_pr_url`, `gh_base_branch`, `gh_branch`, `gh_pr_metadata_path`
3. Environment settings: If environment still exists, check `host_repo_root` or `host_folder`
4. Git repository: If repo still accessible, query current state

## Requirements

### 1. Repair Function

Create: `agents_runner/ui/task_repair.py`

```python
def repair_task_git_metadata(
    task: Task,
    *,
    state_path: str,
    environments: dict[str, Environment],
) -> tuple[bool, str]:
    """Attempt to repair missing git metadata for a task.
    
    Args:
        task: Task to repair
        state_path: Path to state.json for locating context files
        environments: Environment lookup dict
    
    Returns:
        (success, message) tuple
    """
```

### 2. Repair Strategy

#### Step 1: Check if Repair Needed
```python
is_git_locked = bool(getattr(task, "gh_management_locked", False))
has_metadata = task.git is not None and isinstance(task.git, dict) and task.git
if not is_git_locked or has_metadata:
    return (True, "no repair needed")
```

#### Step 2: Try GitHub Context File (v2)
```python
from agents_runner.pr_metadata import github_context_host_path, load_github_metadata

data_dir = os.path.dirname(state_path)
context_path = github_context_host_path(data_dir, task.task_id)

if os.path.exists(context_path):
    metadata = load_github_metadata(context_path)
    if metadata and metadata.github:
        # Extract git info from context
        task.git = {
            "repo_url": metadata.github.repo_url,
            "repo_owner": metadata.github.repo_owner,
            "repo_name": metadata.github.repo_name,
            "base_branch": metadata.github.base_branch,
            "target_branch": metadata.github.task_branch,
            "head_commit": metadata.github.head_commit,
        }
        return (True, "repaired from GitHub context file")
```

#### Step 3: Try Task Fields
```python
from agents_runner.ui.task_git_metadata import derive_task_git_metadata

derived = derive_task_git_metadata(task)
if derived:
    task.git = derived
    return (True, "repaired from task fields")
```

#### Step 4: Try Environment Repository
```python
env = environments.get(task.environment_id)
if env:
    repo_path = getattr(env, "host_repo_root", None) or getattr(env, "host_folder", None)
    if repo_path and os.path.isdir(repo_path):
        from agents_runner.environments.git_operations import get_git_info
        
        try:
            git_info = get_git_info(repo_path)
            if git_info:
                task.git = {
                    "repo_url": git_info.repo_url,
                    "repo_owner": git_info.repo_owner,
                    "repo_name": git_info.repo_name,
                    "base_branch": git_info.branch,
                    "target_branch": task.gh_branch or None,
                    "head_commit": git_info.commit_sha,
                }
                return (True, "repaired from environment repository")
        except Exception as exc:
            pass  # Continue to next strategy
```

#### Step 5: Partial Metadata
If some fields exist but not all required:
```python
# At minimum, ensure base_branch is set
if not task.git:
    task.git = {}

if not task.git.get("base_branch"):
    task.git["base_branch"] = task.gh_base_branch or "main"

if not task.git.get("target_branch") and task.gh_branch:
    task.git["target_branch"] = task.gh_branch

if not task.git.get("pull_request_url") and task.gh_pr_url:
    task.git["pull_request_url"] = task.gh_pr_url

return (False, "partial metadata only")
```

### 3. Bulk Repair on Startup

Modify: `agents_runner/ui/main_window_persistence.py`

In `_load_state()` method (around line 158):

```python
# After loading tasks
from agents_runner.ui.task_repair import repair_task_git_metadata

repair_count = 0
for task in loaded:
    if getattr(task, "gh_management_locked", False) and not task.git:
        success, msg = repair_task_git_metadata(
            task,
            state_path=self._state_path,
            environments=self._environments,
        )
        if success:
            repair_count += 1
            # Save repaired task immediately
            save_task_payload(
                self._state_path,
                serialize_task(task),
                archived=self._should_archive_task(task),
            )

if repair_count > 0:
    logger.info(f"Repaired git metadata for {repair_count} tasks")
```

### 4. Manual Repair Command

Add UI action: "Repair Git Metadata" in task details context menu

File: `agents_runner/ui/pages/task_details.py`

```python
def _on_repair_metadata(self) -> None:
    """Manually trigger metadata repair for current task."""
    if not self._current_task:
        return
    
    from agents_runner.ui.task_repair import repair_task_git_metadata
    
    success, msg = repair_task_git_metadata(
        self._current_task,
        state_path=self._state_path,
        environments=self._environments,
    )
    
    if success:
        QMessageBox.information(self, "Repair Successful", f"Git metadata repaired: {msg}")
        self._save_callback()  # Trigger save
    else:
        QMessageBox.warning(self, "Repair Failed", f"Could not fully repair metadata: {msg}")
```

### 5. Logging

All repair attempts should log:
```python
import logging
logger = logging.getLogger(__name__)

logger.info(f"[repair] task {task_id}: {message}")
logger.warning(f"[repair] task {task_id}: partial repair only")
logger.error(f"[repair] task {task_id}: repair failed - {error}")
```

## Implementation Files

### New Files
1. `agents_runner/ui/task_repair.py`
   - `repair_task_git_metadata()` function
   - Helper functions for each repair strategy

### Modified Files
2. `agents_runner/ui/main_window_persistence.py`
   - Add bulk repair in `_load_state()` (line ~158)
   - Import and call repair function

3. `agents_runner/ui/pages/task_details.py`
   - Add "Repair Metadata" action to context menu
   - Add `_on_repair_metadata()` handler
   - Need `_state_path` and `_environments` references

4. `agents_runner/ui/main_window.py`
   - Pass `_state_path` and `_environments` to task details page
   - Wire up repair callback

## Testing Scenarios

### Scenario 1: Old Task from Before Git Metadata
- Locate task JSON file without `git` field
- Start application
- Verify automatic repair attempts
- Check task JSON file has `git` field added

### Scenario 2: Task with Deleted Context File
- Create task, then delete its GitHub context file
- Restart application
- Verify fallback to task fields
- Check partial metadata is created

### Scenario 3: Manual Repair
- Open task details for task missing metadata
- Click "Repair Metadata" menu item
- Verify repair succeeds or shows clear error

### Scenario 4: Task with Inaccessible Repository
- Task from deleted/moved repository
- Repair should create partial metadata
- Should not crash or fail startup

### Scenario 5: Bulk Repair Performance
- 100+ tasks in done folder
- Startup should complete in reasonable time (< 5 seconds)
- Only git-locked tasks without metadata are processed

## Success Criteria

1. Application startup automatically repairs missing metadata
2. Repair is fast and non-blocking (< 50ms per task)
3. Manual repair command works from task details
4. Repaired tasks are immediately persisted
5. Partial metadata is better than no metadata
6. Clear logging for each repair attempt
7. No crashes or errors for unrepairable tasks

## Related Files

### Dependencies
- `agents_runner/pr_metadata.py` - Load GitHub context files
- `agents_runner/environments/git_operations.py` - Query git repos
- `agents_runner/ui/task_git_metadata.py` - Derive metadata
- `agents_runner/persistence.py` - Save/load tasks

### Documentation
- `.agents/implementation/github_context.md` - Context file format
- `agents_runner/ui/task_model.py` - Task schema

## Edge Cases

### 1. Concurrent Repairs
If multiple tasks reference same repository:
- Each repair is independent
- No shared state to conflict
- Safe to run in parallel (future optimization)

### 2. Migration Path
Old tasks missing `gh_management_locked` field:
- Default to `False` in deserialization
- Won't trigger repair (correct behavior)

### 3. Corrupted Context Files
If `load_github_metadata()` returns `None`:
- Fallback to next strategy
- Log warning but continue

### 4. Repository State Changed
If repo has different branches/commits now:
- Use current state (best effort)
- Original state is lost (acceptable)
- Better than no metadata

## Notes

- Repair is best-effort, not guaranteed
- Focus on populating critical fields: `repo_url`, `base_branch`
- Optional fields like `pull_request_number` can remain None
- Repair does NOT modify source repository
- Repair is idempotent (safe to run multiple times)
- Consider rate-limiting if querying remote repos (future enhancement)
