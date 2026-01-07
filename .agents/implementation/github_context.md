# GitHub Context System

## Overview

The GitHub Context system provides agents with repository metadata to help them understand the codebase context. It uses a v2 JSON schema that extends the legacy PR metadata system.

## Architecture

### File Structure

```
agents_runner/
├── pr_metadata.py              # Core context file generation
├── environments/
│   ├── model.py               # Environment with gh_context_enabled flag
│   └── git_operations.py      # Git detection and info extraction
├── docker/
│   ├── agent_worker.py        # Updates context after git clone
│   └── config.py              # Passes context file path to worker
├── prompts/
│   └── github_context.md      # Prompt template for agents
└── ui/
    └── main_window_tasks_agent.py  # Task creation integration
```

### v2 Schema

```json
{
  "version": 2,
  "task_id": "abc123",
  "github": {
    "repo_url": "https://github.com/owner/repo",
    "repo_owner": "owner",
    "repo_name": "repo",
    "base_branch": "main",
    "task_branch": "task-abc123",
    "head_commit": "sha..."
  },
  "title": "",
  "body": ""
}
```

**Fields:**
- `version`: Always 2 for GitHub context schema
- `task_id`: Unique task identifier
- `github`: Repository context (null if not available)
  - `repo_url`: Full repository URL
  - `repo_owner`: GitHub owner/org (null for non-GitHub remotes)
  - `repo_name`: Repository name (null for non-GitHub remotes)
  - `base_branch`: Base branch name
  - `task_branch`: Task-specific branch (null for folder-locked)
  - `head_commit`: Current HEAD commit SHA
- `title`: Reserved for PR title (future use)
- `body`: Reserved for PR body (future use)

## Environment Modes

### 1. Git-Locked (GH_MANAGEMENT_GITHUB)

**Workflow:**
1. Task creation: Create empty context file with `github: null`
2. Docker worker: Clone repository
3. After clone: Populate context with `get_git_info()` + `update_github_context_after_clone()`
4. Agent: Reads fully populated context file

**Example:**
```json
{
  "version": 2,
  "task_id": "abc123",
  "github": {
    "repo_url": "https://github.com/owner/repo",
    "repo_owner": "owner",
    "repo_name": "repo",
    "base_branch": "main",
    "task_branch": "task-abc123",
    "head_commit": "def456..."
  }
}
```

### 2. Folder-Locked Git Repo (GH_MANAGEMENT_LOCAL + git detected)

**Workflow:**
1. Task creation: Call `get_git_info(folder_path)`
2. If git detected: Create context file with full GitHub object
3. Agent: Reads context immediately

**Example:**
```json
{
  "version": 2,
  "task_id": "xyz789",
  "github": {
    "repo_url": "https://github.com/owner/repo",
    "repo_owner": "owner",
    "repo_name": "repo",
    "base_branch": "feature-branch",
    "task_branch": null,
    "head_commit": "abc123..."
  }
}
```

### 3. Folder-Locked Non-Git (GH_MANAGEMENT_LOCAL + no git)

**Workflow:**
1. Task creation: Call `get_git_info(folder_path)` returns None
2. Log: "folder is not a git repository; skipping context"
3. No context file created
4. Task proceeds normally

### 4. Context Disabled (gh_context_enabled = False)

**Workflow:**
1. Context system skipped entirely
2. No context file created
3. Task proceeds as before

## Error Handling

**Core Principle: Never fail a task due to context issues**

### Git Detection Failures

```python
try:
    git_info = get_git_info(folder_path)
except Exception as exc:
    logger.warning(f"[gh] git detection failed: {exc}")
    self._on_task_log(task_id, f"[gh] git detection failed: {exc}; continuing without context")
    # Task continues
```

### Context File Creation Failures

```python
try:
    ensure_github_context_file(host_path, task_id=task_id, github_context=context)
except Exception as exc:
    logger.error(f"[gh] failed to create GitHub context file: {exc}")
    self._on_task_log(task_id, f"[gh] failed to create GitHub context file: {exc}; continuing without context")
    # Task continues without context file
```

### Context Update Failures (After Clone)

```python
try:
    update_github_context_after_clone(path, github_context=context)
except Exception as exc:
    self._on_log(f"[gh] failed to update GitHub context: {exc}")
    # Don't fail the task
```

## Edge Cases

### Detached HEAD State

- `git_current_branch()` returns None
- Fallback: Use "HEAD" as branch name
- Context still generated with commit SHA

### Empty Repository (No Commits)

- `git_head_commit()` returns None
- `get_git_info()` returns None
- Context gracefully skipped

### No Remote Configured

- `git_remote_url()` returns None
- `get_git_info()` returns None
- Context gracefully skipped

### Non-GitHub Remote (GitLab, Bitbucket)

- `parse_github_url()` returns (None, None)
- Context still generated with:
  - `repo_url`: Full remote URL
  - `repo_owner`: None
  - `repo_name`: None
- Agents can still use the URL

## Agent Usage

### Reading the Context

All agents receive the context file mounted at `/tmp/github-context-{task_id}.json`:

```bash
# Read with jq
jq '.github' /tmp/github-context-abc123.json

# Use in scripts
REPO_URL=$(jq -r '.github.repo_url' /tmp/github-context-abc123.json)
```

### Prompt Injection

Agents receive prompt instructions:

```markdown
# GitHub Context

A GitHub context file is available at: `/tmp/github-context-abc123.json`

This file contains repository information...
```

### CLI Access

Gemini CLI has `/tmp` explicitly allowed:

```python
args = [
    "gemini",
    "--include-directories", container_workdir,
    "--include-directories", "/tmp",
    ...
]
```

## File Paths

### Host Paths

```python
# Stored in: ~/.midoriai/agents-runner/github-context/
github_context_host_path(data_dir, task_id)
# Returns: {data_dir}/github-context/github-context-{task_id}.json
```

### Container Paths

```python
# Mounted at: /tmp/github-context-{task_id}.json
github_context_container_path(task_id)
# Returns: /tmp/github-context-{task_id}.json
```

### Mounting

```python
extra_mounts_for_task.append(f"{host_path}:{container_path}:rw")
```

## Backward Compatibility

### Legacy PR Metadata (v1)

The old PR metadata system is still supported:
- `ensure_pr_metadata_file()` - creates v1 files
- `pr_metadata_host_path()` - returns v1 paths
- `load_pr_metadata()` - reads v1 or v2 files (title/body only)

### Migration Path

No migration needed:
- New tasks use v2 schema automatically
- Old v1 files continue to work
- `load_pr_metadata()` supports both versions

## Configuration

### Environment Settings

```python
class Environment:
    gh_context_enabled: bool = False  # Enable GitHub context
    gh_management_mode: str = "none"  # "none", "local", "github"
    gh_management_target: str = ""    # Folder path or repo URL
```

### UI Toggle

Located in: `agents_runner/ui/pages/environments.py`
- Checkbox: "Enable GitHub Context"
- Only visible when `gh_management_mode != "none"`

## Testing Scenarios

### Manual Testing Checklist

1. **Git-Locked + Context Enabled**
   - Create environment with github mode
   - Enable context
   - Start task
   - Verify context file created empty
   - Verify populated after clone
   - Check logs for "[gh] updated GitHub context file"

2. **Folder-Locked Git + Context Enabled**
   - Create environment with local mode pointing to git repo
   - Enable context
   - Start task
   - Verify context file created immediately
   - Check logs for "[gh] detected git repo"

3. **Folder-Locked Non-Git + Context Enabled**
   - Create environment with local mode pointing to non-git folder
   - Enable context
   - Start task
   - Verify no context file created
   - Check logs for "[gh] folder is not a git repository"
   - Verify task completes successfully

4. **Context Disabled**
   - Any environment mode
   - Disable context
   - Start task
   - Verify no context file created
   - Task runs normally

5. **All 4 Agents**
   - Test with codex, claude, copilot, gemini
   - Verify all can read context file
   - Verify Gemini has /tmp access

## Implementation Notes

### Git Operations Timeout

All git operations in `git_operations.py` have 8-second timeouts:
- Never block indefinitely
- Return None on timeout
- Log warnings but don't fail

### File Permissions

Context files are created with 0o666 permissions:
```python
try:
    os.chmod(path, 0o666)
except OSError:
    pass  # Ignore chmod failures
```

### Caching

Folder-locked environments cache git detection:
```python
class Environment:
    _cached_is_git_repo: bool | None = None
    
    def detect_git_if_folder_locked(self) -> bool:
        if self._cached_is_git_repo is not None:
            return self._cached_is_git_repo
        # ... detect and cache
```

## Future Enhancements

### PR/Issue Metadata

The v2 schema reserves `title` and `body` fields for:
- PR title/description
- Issue title/description
- Could be populated from GitHub API in future

### Extended Context

Additional fields could be added to `github` object:
- `pr_number`: PR being worked on
- `issue_number`: Issue being addressed
- `default_branch`: Repository default branch
- `is_fork`: Whether repo is a fork

## Troubleshooting

### Context File Not Created

Check logs for:
- "[gh] folder is not a git repository" - Expected for non-git folders
- "[gh] git detection failed" - Git command issues
- "[gh] failed to create GitHub context file" - File system issues

### Context File Empty After Clone

Check logs for:
- "[gh] failed to update GitHub context" - Update failed
- "[gh] could not determine git repo root" - Git repo issue
- Verify `gh_context_file_path` is passed in config

### Agent Can't Read Context

- Verify file is mounted: Check `extra_mounts_for_task`
- Check container path: `/tmp/github-context-{task_id}.json`
- For Gemini: Verify `/tmp` in `--include-directories`

## References

- `agents_runner/pr_metadata.py` - Core implementation
- `agents_runner/environments/git_operations.py` - Git detection
- `agents_runner/prompts/github_context.md` - Prompt template
- `agents_runner/ui/pages/environments.py` - UI controls
