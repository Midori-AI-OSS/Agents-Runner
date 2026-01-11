# Quick Start Guide for Git Metadata Implementation

## Overview

Three tasks to enhance git metadata handling in Agents Runner. All specifications are complete and ready for implementation.

## Task Files Location

```
.agents/tasks/
├── README.md                              # Overview and timeline
├── task-1-make-git-metadata-required.md   # Validation (4-6h)
├── task-2-backfill-repair-git-metadata.md # Repair (8-12h)
└── task-3-reliable-pr-creation-flow.md    # PR UX (12-16h)
```

## Quick Reference

### Task 1: Validation (START HERE)

**Goal:** Ensure git-locked tasks have metadata

**Key Files to Modify:**
- `agents_runner/ui/main_window_task_events.py` - Add validation after line 548
- `agents_runner/ui/task_git_metadata.py` - Add `validate_git_metadata()` function
- `agents_runner/ui/task_model.py` - Add `requires_git_metadata()` helper

**Testing:**
- Create git-locked task, verify metadata exists
- Create non-git task, verify validation skipped

### Task 2: Repair (AFTER TASK 1)

**Goal:** Auto-repair missing metadata

**Key Files to Create:**
- `agents_runner/ui/task_repair.py` - Main repair logic (new file)

**Key Files to Modify:**
- `agents_runner/ui/main_window_persistence.py` - Add startup repair
- `agents_runner/ui/pages/task_details.py` - Add manual repair button
- `agents_runner/ui/main_window.py` - Wire up UI

**Testing:**
- Startup with old tasks, verify automatic repair
- Use manual repair button, verify UI feedback

### Task 3: PR Flow (PARALLEL OR AFTER)

**Goal:** Robust PR creation

**Key Files to Create:**
- `agents_runner/gh/pr_validation.py` - Pre-flight checks (new file)
- `agents_runner/gh/pr_retry.py` - Retry logic (new file)

**Key Files to Modify:**
- `agents_runner/ui/main_window_tasks_interactive_finalize.py` - Enhanced worker
- `agents_runner/ui/main_window_task_review.py` - Manual PR improvements
- `agents_runner/gh/task_plan.py` - Helper extraction
- `agents_runner/ui/pages/task_details.py` - Cancel button

**Testing:**
- Create PR normally, verify 6-step progress
- Test with existing PR, verify detection
- Test network failure, verify retry

## Implementation Checklist

### Before Starting
- [ ] Read `AGENTS.md` for contributor guidelines
- [ ] Review `.agents/implementation/github_context.md` for context system
- [ ] Review `.agents/implementation/gh_management.md` for git-locked feature

### During Implementation (Per Task)
- [ ] Create feature branch: `midoriaiagents/task-{1,2,3}-{short-desc}`
- [ ] Implement with frequent small commits
- [ ] Use `[TYPE]` commit messages (e.g., `[FEAT] Add validation`)
- [ ] Test all scenarios from task spec
- [ ] Update documentation in `.agents/implementation/`

### Before Submitting PR
- [ ] All test scenarios pass
- [ ] No regressions in existing functionality
- [ ] Logs are clear and helpful
- [ ] Documentation updated
- [ ] Backward compatibility verified

## Key Codebase Concepts

### Task Model
```python
# agents_runner/ui/task_model.py
class Task:
    gh_management_locked: bool = False  # Git-locked flag
    git: dict[str, object] | None = None  # Metadata
```

### Git Metadata Schema
```python
task.git = {
    "repo_url": "https://github.com/owner/repo",
    "repo_owner": "owner",  # None for non-GitHub
    "repo_name": "repo",    # None for non-GitHub
    "base_branch": "main",
    "target_branch": "task-branch",  # None for folder-locked
    "pull_request_url": "https://...",  # Optional
    "pull_request_number": 123,  # Optional
    "head_commit": "sha...",  # Optional
}
```

### GitHub Context File (v2)
```json
{
  "version": 2,
  "task_id": "abc123",
  "github": {
    "repo_url": "...",
    "repo_owner": "...",
    "repo_name": "...",
    "base_branch": "main",
    "task_branch": "task-abc123",
    "head_commit": "sha..."
  },
  "title": "",
  "body": ""
}
```

### Key Functions

**Derive Metadata:**
```python
from agents_runner.ui.task_git_metadata import derive_task_git_metadata
metadata = derive_task_git_metadata(task)  # Returns dict or None
```

**Load Context File:**
```python
from agents_runner.pr_metadata import load_github_metadata, github_context_host_path
data_dir = os.path.dirname(state_path)
path = github_context_host_path(data_dir, task_id)
metadata = load_github_metadata(path)  # Returns GitHubMetadataV2 or None
```

**Get Git Info:**
```python
from agents_runner.environments.git_operations import get_git_info
git_info = get_git_info(repo_path)  # Returns GitRepoInfo or None
```

**Save Task:**
```python
from agents_runner.persistence import serialize_task, save_task_payload
save_task_payload(state_path, serialize_task(task), archived=False)
```

## Common Patterns

### Validation Pattern
```python
is_git_locked = bool(getattr(task, "gh_management_locked", False))
if is_git_locked and not task.git:
    # Log warning and handle
```

### Repair Pattern
```python
# Try strategies in order
if try_github_context_file():
    return (True, "repaired from context")
elif try_task_fields():
    return (True, "repaired from fields")
elif try_environment_repo():
    return (True, "repaired from repo")
else:
    return (False, "partial only")
```

### Error Logging Pattern
```python
from agents_runner.log_format import format_log
self.host_log.emit(
    task_id,
    format_log("gh", "pr", "ERROR", "user-friendly message")
)
```

## Testing Commands

### Run Application
```bash
uv run main.py
```

### Check Task Files
```bash
# Active tasks
ls -la ~/.midoriai/agents-runner/tasks/

# Done tasks
ls -la ~/.midoriai/agents-runner/tasks/done/

# View task JSON
cat ~/.midoriai/agents-runner/tasks/{task-id}.json | jq .git
```

### Check Context Files
```bash
ls -la ~/.midoriai/agents-runner/github-context/
cat ~/.midoriai/agents-runner/github-context/github-context-{task-id}.json | jq
```

### Test Git Operations
```bash
# In Python REPL
from agents_runner.environments.git_operations import get_git_info
info = get_git_info("/path/to/repo")
print(info)
```

## Support Resources

### Documentation
- `AGENTS.md` - Contributor guidelines
- `.agents/implementation/github_context.md` - Context system
- `.agents/implementation/gh_management.md` - Git-locked environments
- `.agents/tasks/README.md` - This overview

### Code References
- `agents_runner/ui/task_model.py` - Task schema
- `agents_runner/persistence.py` - Serialization
- `agents_runner/pr_metadata.py` - Context files
- `agents_runner/environments/git_operations.py` - Git queries

### Recent Commits
- `ed8e55d` - Git metadata persistence (Jan 11, 2026)
- See implementation for examples

## Questions?

If anything is unclear:
1. Check the detailed task spec file
2. Review related code files
3. Check implementation docs in `.agents/implementation/`
4. Look at recent commits for similar patterns

All specifications are complete. No additional context should be needed.

Good luck!
