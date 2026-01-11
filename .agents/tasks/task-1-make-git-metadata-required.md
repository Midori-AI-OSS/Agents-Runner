# Task 1: Make Git Metadata Required for Git-Locked Tasks

## Objective
Ensure that all git-locked tasks (tasks with `gh_management_locked=True`) have non-null `git` metadata populated before the task completes. This provides reliable repository context for debugging, auditing, and future automation.

## Current State

### Task Model
- File: `agents_runner/ui/task_model.py`
- Line 36: `git: dict[str, object] | None = None`
- Currently optional (can be `None`)

### Git Metadata Derivation
- File: `agents_runner/ui/task_git_metadata.py`
- Function: `derive_task_git_metadata(task)` (lines 25-91)
- Returns: `dict[str, object] | None`
- Sources data from:
  - `task.gh_pr_url` (PR URL)
  - `task.gh_pr_metadata_path` (GitHub context file v2)
  - `task.gh_base_branch` (fallback)
  - `task.gh_branch` (fallback)

### Current Call Sites
File: `agents_runner/ui/main_window_task_events.py`
- Line 83: After stop/kill action
- Line 205: After discard action
- Line 389: After PR URL update
- Line 548: After agent task finishes

File: `agents_runner/ui/main_window_tasks_interactive_finalize.py`
- Line 45: After interactive task finishes

### Persistence
- File: `agents_runner/persistence.py`
- Lines 290-293: Serialize `git` field from task
- Lines 334-336: Deserialize `git` field to task
- Stored in task JSON files under: `~/.midoriai/agents-runner/tasks/`

## Requirements

### 1. Make Git Metadata Required

For tasks where `task.gh_management_locked == True`:
- The `task.git` field MUST NOT be `None` when task reaches a terminal state
- Terminal states: `done`, `failed`, `cancelled`, `killed`, `exited`

### 2. Validation Point

Add validation in: `agents_runner/ui/main_window_task_events.py`
- Location: `_on_agent_done()` method (around line 541)
- After calling `derive_task_git_metadata(task)`
- Before updating UI and saving

### 3. Validation Logic

```python
# After: task.git = derive_task_git_metadata(task)

# Validate for git-locked environments
is_git_locked = bool(getattr(task, "gh_management_locked", False))
if is_git_locked and not task.git:
    # Log warning
    self.host_log.emit(
        task_id,
        format_log("host", "metadata", "WARN", 
                   "git metadata missing for git-locked task; triggering repair")
    )
    # Mark task as needing repair
    task.status = "metadata_incomplete"
    task.error = "Git metadata validation failed"
```

### 4. Required Git Metadata Fields

When `task.git` is populated, it should contain:
- `repo_url`: str (required for git-locked)
- `base_branch`: str (required)
- `target_branch`: str | None (optional, may be None for folder-locked)
- `pull_request_url`: str | None (optional)
- `pull_request_number`: int | None (optional)
- `head_commit`: str | None (optional but recommended)
- `repo_owner`: str | None (optional, None for non-GitHub remotes)
- `repo_name`: str | None (optional, None for non-GitHub remotes)

### 5. Error Handling

If metadata cannot be derived:
- Log detailed error explaining what's missing
- Check if `gh_pr_metadata_path` exists and is readable
- Check if GitHub context file (v2) is properly populated
- Set task status to indicate metadata issue
- DO NOT fail the task itself (code execution may have succeeded)

## Implementation Files

### Primary Changes
1. `agents_runner/ui/main_window_task_events.py`
   - Add validation in `_on_agent_done()` after line 548
   - Add validation in `_on_interactive_finished()` (in finalize mixin) after line 45

2. `agents_runner/ui/task_git_metadata.py`
   - Add `validate_git_metadata()` function
   - Returns: `tuple[bool, str]` (is_valid, error_message)

### Secondary Changes
3. `agents_runner/ui/task_model.py`
   - Add helper method: `requires_git_metadata() -> bool`
   - Returns True if `gh_management_locked == True`

## Testing Scenarios

### Scenario 1: Git-Locked Task with PR
- Create git-locked environment
- Run task to completion
- Verify `task.git` is populated
- Verify contains PR URL and number

### Scenario 2: Git-Locked Task Without PR
- Create git-locked environment
- Run task but don't create PR
- Verify `task.git` is still populated with repo info
- Verify base_branch and target_branch are present

### Scenario 3: Folder-Locked Task
- Create folder-locked environment with git repo
- Run task to completion
- Verify `task.git` is populated
- `target_branch` may be None (acceptable)

### Scenario 4: Non-Git Task
- Create environment without git management
- Run task to completion
- Verify `task.git` can be None (not required)

### Scenario 5: Missing Context File
- Create git-locked task
- Manually delete GitHub context file during execution
- Task should complete but log warning
- Metadata should attempt fallback to task fields

## Success Criteria

1. All git-locked tasks have `task.git != None` in terminal states
2. Validation logs clear warnings when metadata is missing
3. Tasks don't fail due to metadata issues (code execution is independent)
4. Existing non-git tasks are unaffected
5. Task JSON files contain populated `git` field for git-locked tasks

## Related Files

### Context System
- `agents_runner/pr_metadata.py` - GitHub context v2 schema
- `agents_runner/environments/git_operations.py` - Git info extraction
- `agents_runner/docker/agent_worker.py` - Updates context after clone

### Documentation
- `.agents/implementation/github_context.md` - Context system docs
- `.agents/implementation/gh_management.md` - Git-locked feature docs

## Notes

- This task focuses on validation and ensuring metadata exists
- Does NOT change the schema or add new fields
- Does NOT implement repair/backfill (see Task 2)
- Minimal code changes, mostly validation logic
- Should not break existing functionality
