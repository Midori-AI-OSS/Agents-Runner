# GitHub Context System Design

**Document ID:** 05-github-context-design  
**Created:** 2025-01-07  
**Auditor:** Auditor Mode  
**Purpose:** Detailed design for Task 4 - GitHub Context for ALL Agents

---

## Executive Summary

This document provides comprehensive analysis and implementation guidance for making GitHub context available to ALL agents (not just Copilot). The current system only works for GitHub-managed (git locked) environments. This design extends support to folder-managed (folder locked) environments that happen to be git repositories, while making the feature toggleable per-environment and respecting user privacy regarding credential mounting.

**Key Design Principles:**
1. **Agent-Agnostic** - Works for Codex, Claude, Copilot, Gemini equally
2. **Environment-Type Agnostic** - Works for both git-locked and folder-locked
3. **Privacy-First** - Credentials never mounted automatically, explicit opt-in required
4. **Graceful Degradation** - Missing git context does not break tasks
5. **Backward Compatible** - Existing environments continue working

---

## Current State Analysis

### 1. Environment Types: Git Locked vs Folder Locked

**Definition in Code:** `agents_runner/environments/model.py:28-30`

```python
GH_MANAGEMENT_NONE = "none"     # No workspace management
GH_MANAGEMENT_LOCAL = "local"   # Folder locked
GH_MANAGEMENT_GITHUB = "github" # Git locked
```

#### Git Locked (GH_MANAGEMENT_GITHUB)

**Characteristics:**
- `gh_management_mode = "github"`
- `gh_management_target` contains repo spec: `"owner/repo"`
- `gh_management_locked = True` (target cannot be changed)
- Created via: "Lock to GitHub repo (clone)" option

**Behavior:**
- App clones repo to temporary workspace per task
- Workspace path: `~/.midoriai/agents-runner/workspaces/{env_id}/{task_id}/`
- Creates task branch: `task/{task_id}`
- Commits and pushes changes after task completes
- Supports PR creation
- Workspace deleted after task (unless failed, kept for debugging)

**GitHub Integration:**
- Full GitHub lifecycle: clone → branch → commit → push → PR
- Uses `gh` CLI or `git` CLI
- Requires authentication (host gh CLI credentials)
- PR metadata already supported (if enabled)

#### Folder Locked (GH_MANAGEMENT_LOCAL)

**Characteristics:**
- `gh_management_mode = "local"`
- `gh_management_target` contains file path: `"/path/to/folder"`
- `gh_management_locked = True` (target cannot be changed)
- Created via: "Lock to local folder" option

**Behavior:**
- App mounts folder directly into container
- No cloning, no branch creation
- User manages git operations manually (if folder is a git repo)
- No PR creation, no GitHub orchestration
- Folder persists after task (it's the user's folder)

**GitHub Integration:**
- NONE currently
- Folder MAY be a git repo (user-managed)
- No automatic detection of git context
- No PR metadata support

#### Workspace Type Comparison

| Aspect | Git Locked (GITHUB) | Folder Locked (LOCAL) | None (NONE) |
|--------|---------------------|----------------------|-------------|
| **Mode** | `"github"` | `"local"` | `"none"` |
| **Target** | `owner/repo` | `/path/to/folder` | N/A |
| **Workspace** | Temp clone per task | Direct folder mount | Settings workdir |
| **Git Detection** | Always git repo | Maybe git repo | Unknown |
| **Branch UI** | Base branch selector | Hidden | Hidden |
| **Git Ops** | Automatic (clone, branch, commit, push) | None (user-managed) | None |
| **PR Creation** | Supported | Not supported | Not supported |
| **Cleanup** | Delete workspace after task | Never deleted | Never deleted |
| **Current GH Context** | Supported (if enabled) | NOT SUPPORTED | NOT SUPPORTED |

### 2. Current PR Metadata Implementation

**Location:** `agents_runner/pr_metadata.py` (94 lines)

**Current Scope:** ONLY GitHub-managed (git locked) environments

**Data Schema (v1):**
```json
{
  "version": 1,
  "task_id": "abc123",
  "title": "",
  "body": ""
}
```

**File Locations:**
- **Host:** `~/.midoriai/agents-runner/pr-metadata/pr-metadata-{task_id}.json`
- **Container:** `/tmp/codex-pr-metadata-{task_id}.json`

**Mounting Logic:** `ui/main_window_tasks_agent.py:334-358`
```python
if (
    env
    and gh_mode == GH_MANAGEMENT_GITHUB
    and bool(getattr(env, "gh_pr_metadata_enabled", False))
):
    # Create metadata file, mount into container
    # Add prompt instructions
    # Set env var: CODEX_PR_METADATA_PATH
```

**Restriction:** Hardcoded to `GH_MANAGEMENT_GITHUB` mode only

**UI Label:** `ui/pages/environments.py:167-169`
```python
self._gh_pr_metadata_enabled = QCheckBox(
    "Allow agent to set PR title/body (non-interactive only)"
)
```

**Prompt Template:** `prompts/pr_metadata.md`
- Generic instructions (not Copilot-specific)
- Instructs agent to write JSON with title/body fields
- Used when PR metadata enabled

**Limitations:**
1. Only works for git-locked environments
2. Doesn't include repo context (URL, branch, commit)
3. File created empty at task start
4. Populated by agent during execution
5. Read when creating PR (if task succeeds)

### 3. Why Is It Currently Copilot-Only?

**ANSWER: IT'S NOT.**

The checkbox label is misleading. Analysis of the code shows:

**UI Label (environments.py:167-169):**
```python
self._gh_pr_metadata_enabled = QCheckBox(
    "Allow agent to set PR title/body (non-interactive only)"
)
```

**Actual Implementation (main_window_tasks_agent.py:334-358):**
- No agent-specific checks
- Works for ANY agent CLI
- Prompt instructions are generic (prompts/pr_metadata.md)
- Container path uses "codex-pr-metadata" name (legacy naming)

**Conclusion:**
- Feature ALREADY works for all agents
- UI label is generic (no Copilot mention in latest code)
- Previous audit (86f460ef) mentioned Copilot restriction (line 168) but appears to have been updated
- Container path naming is legacy but doesn't affect functionality

**What Needs Changing:**
1. Container path naming: `/tmp/codex-pr-metadata-{task_id}.json` → `/tmp/github-pr-metadata-{task_id}.json`
2. Env var naming: `CODEX_PR_METADATA_PATH` → `GITHUB_PR_METADATA_PATH`
3. Field name: `gh_pr_metadata_enabled` → `gh_context_enabled` (broader scope)
4. Extend to folder-locked environments with git detection

---

## Requirements Analysis

### Functional Requirements

**FR1: Git Detection for Folder-Locked Environments**
- When environment is folder-locked (`GH_MANAGEMENT_LOCAL`)
- Detect if target folder is a git repository
- Extract repo URL, current branch, HEAD commit SHA
- Cache detection results to avoid repeated git operations

**FR2: Enhanced Metadata Schema**
- Extend PR metadata JSON to include repo context
- Version 2 schema with backward compatibility
- Include: repo_url, base_branch, task_branch, commit_sha
- Maintain existing title/body fields

**FR3: Per-Environment Toggle**
- Checkbox in Environment editor (General tab)
- Label: "Provide GitHub context to agent"
- Enabled for: git-locked (always) and folder-locked (if git detected)
- Disabled for: folder-locked non-git folders, environments with mode=none
- Default: OFF (user must explicitly enable)

**FR4: Global Default Setting**
- Settings page: "Enable GitHub context by default for new environments"
- Applied when creating new environments
- Does not affect existing environments
- Default: OFF

**FR5: Agent-Agnostic Context**
- Works for all supported agents: codex, claude, copilot, gemini
- Generic prompt template (not agent-specific)
- Standard env var: `GITHUB_CONTEXT_PATH`
- Standard container path: `/tmp/github-context-{task_id}.json`

**FR6: Graceful Degradation**
- If git detection fails, silently skip GitHub context
- Log reason for skipping (not a git repo, git command failed)
- Task continues normally without GitHub context
- No errors shown to user

**FR7: Privacy-Preserving**
- GitHub context NEVER includes credentials
- Only non-secret data: repo URL, branch names, commit SHA
- Auth mounting is SEPARATE feature (not part of this task)
- Document: GitHub context != GitHub authentication

### Non-Functional Requirements

**NFR1: Performance**
- Git detection cached per environment per session
- Maximum 1 git detection per task start
- Git operations timeout after 8 seconds
- No blocking UI during detection

**NFR2: Security**
- No credentials in JSON file
- No tokens, no auth headers, no API keys
- File permissions: 0666 (readable by container user)
- File location: user's data directory (secure)

**NFR3: Backward Compatibility**
- Existing environments with `gh_pr_metadata_enabled=True` migrate automatically
- New field name: `gh_context_enabled`
- V1 metadata schema still readable
- PR creation logic unchanged

**NFR4: Gemini Integration**
- Gemini requires `--include-directories` for file access
- Auto-include GitHub context file directory in allowed paths
- Add to agent CLI args when GitHub context enabled
- Format: `--include-directories /tmp` (parent directory)

---

## Proposed Design

### 1. Enhanced Metadata Schema (Version 2)

**File Format:**
```json
{
  "version": 2,
  "task_id": "abc123def456",
  "github": {
    "repo_url": "https://github.com/owner/repo",
    "repo_owner": "owner",
    "repo_name": "repo",
    "base_branch": "main",
    "task_branch": "task/abc123def456",
    "head_commit": "abc123def456789012345678901234567890abcd"
  },
  "title": "",
  "body": ""
}
```

**Fields:**

| Field | Type | Source | Required | Description |
|-------|------|--------|----------|-------------|
| `version` | int | Static | Yes | Schema version (2) |
| `task_id` | str | Task | Yes | Unique task identifier |
| `github.repo_url` | str | Git remote | No | Full HTTPS URL to repo |
| `github.repo_owner` | str | Parsed URL | No | Repository owner/org |
| `github.repo_name` | str | Parsed URL | No | Repository name |
| `github.base_branch` | str | Git/user | No | Base branch (main, develop, etc) |
| `github.task_branch` | str | Generated | No | Task branch name |
| `github.head_commit` | str | Git HEAD | No | Current commit SHA |
| `title` | str | Agent | No | PR title (agent-populated) |
| `body` | str | Agent | No | PR body (agent-populated) |

**Schema Evolution:**
- V1 (current): Only task_id, title, body
- V2 (proposed): Add github object with repo context
- Backward compatibility: V1 files still readable
- Migration: Existing files remain V1, new files use V2

### 2. Git Detection Strategy

**When to Detect:**
- Environment type: `GH_MANAGEMENT_LOCAL` (folder-locked)
- User enabled: `gh_context_enabled = True`
- Cache miss: No cached detection result for this environment

**Detection Algorithm:**

```python
def detect_git_context(folder_path: str) -> GitContext | None:
    """Detect git repository context for a local folder.
    
    Returns GitContext if folder is a git repo, else None.
    """
    # Step 1: Check if git repo
    if not is_git_repo(folder_path):
        return None
    
    # Step 2: Get repo root
    repo_root = git_repo_root(folder_path)
    if not repo_root:
        return None
    
    # Step 3: Get current branch
    branch = git_current_branch(repo_root)
    if not branch:
        branch = "HEAD"  # Detached HEAD state
    
    # Step 4: Get HEAD commit
    commit = git_head_commit(repo_root)
    if not commit:
        return None
    
    # Step 5: Get remote URL
    repo_url = git_remote_url(repo_root, remote="origin")
    if not repo_url:
        return None
    
    # Step 6: Parse owner/repo from URL
    owner, repo_name = parse_github_url(repo_url)
    
    return GitContext(
        repo_root=repo_root,
        repo_url=repo_url,
        repo_owner=owner,
        repo_name=repo_name,
        current_branch=branch,
        head_commit=commit,
    )
```

**New Git Operations Needed:**

```python
# agents_runner/gh/git_ops.py additions

def git_head_commit(repo_root: str) -> str | None:
    """Get HEAD commit SHA."""
    proc = _run(["git", "-C", repo_root, "rev-parse", "HEAD"], timeout_s=8.0)
    if proc.returncode != 0:
        return None
    return (proc.stdout or "").strip() or None

def git_remote_url(repo_root: str, remote: str = "origin") -> str | None:
    """Get remote URL for a given remote name."""
    proc = _run(
        ["git", "-C", repo_root, "remote", "get-url", remote],
        timeout_s=8.0
    )
    if proc.returncode != 0:
        return None
    return (proc.stdout or "").strip() or None

def parse_github_url(url: str) -> tuple[str, str] | tuple[None, None]:
    """Parse owner and repo name from GitHub URL.
    
    Examples:
        https://github.com/owner/repo → (owner, repo)
        https://github.com/owner/repo.git → (owner, repo)
        git@github.com:owner/repo.git → (owner, repo)
        ssh://git@github.com/owner/repo → (owner, repo)
    """
    import re
    
    # HTTPS pattern
    https_match = re.search(r'github\.com[:/]([^/]+)/([^/\.]+)', url)
    if https_match:
        return https_match.group(1), https_match.group(2)
    
    # SSH pattern
    ssh_match = re.search(r'github\.com:([^/]+)/([^/\.]+)', url)
    if ssh_match:
        return ssh_match.group(1), ssh_match.group(2)
    
    return None, None
```

**Caching Strategy:**
- Cache key: `(env_id, folder_path, mtime)`
- Cache location: In-memory dict (MainWindow instance)
- Cache invalidation: On environment edit, on app restart
- Cache entry: `GitContext | None | False` (False = detection failed)

### 3. Environment Toggle Design

**Location:** Environments Editor → General Tab

**UI Placement:** After headless desktop checkbox (line ~170)

**Checkbox Configuration:**
```python
self._gh_context_enabled = QCheckBox("Provide GitHub context to agent")
self._gh_context_enabled.setToolTip(
    "When enabled, a JSON file with repository context (URL, branch, commit) "
    "is mounted into the container.\n\n"
    "For GitHub-managed environments: Always includes repo context.\n"
    "For folder-managed environments: Only if folder is a git repository.\n\n"
    "Agents can use this context to provide better PR descriptions and commits.\n"
    "Note: This does NOT provide GitHub authentication - that is separate."
)
self._gh_context_enabled.setEnabled(False)  # Initially disabled
self._gh_context_enabled.setVisible(True)
```

**Enable/Disable Logic:**

| Condition | Enabled | Reason |
|-----------|---------|--------|
| `gh_management_mode == "none"` | No | No workspace management |
| `gh_management_mode == "github"` | Yes | Always has git context |
| `gh_management_mode == "local"` and git detected | Yes | Folder is git repo |
| `gh_management_mode == "local"` and NOT git | No | Folder is not git repo |
| Workspace selection changes | Re-evaluate | May change git detection |

**Visibility Logic:**
- Always visible (don't hide based on mode)
- Tooltip explains when it works
- Disabled state shows it's not applicable

**State Transitions:**
```
User selects "Lock to GitHub repo":
  → gh_management_mode = "github"
  → Enable checkbox
  → Tooltip: "Always available for GitHub repos"

User selects "Lock to local folder":
  → gh_management_mode = "local"
  → Run git detection on target folder
  → If git repo: Enable checkbox
  → If not git: Disable checkbox, tooltip: "Folder is not a git repository"

User changes folder path:
  → Re-run git detection
  → Update checkbox enabled state
```

### 4. Global Default Setting

**Location:** Settings Page → Agent Settings section

**UI Placement:** After preflight settings, before experimental section

**Checkbox Configuration:**
```python
self._gh_context_default = QCheckBox(
    "Enable GitHub context by default for new environments"
)
self._gh_context_default.setToolTip(
    "When enabled, new environments will have GitHub context enabled by default.\n"
    "This only affects newly created environments, not existing ones.\n"
    "Users can still disable it per-environment in the Environments editor."
)
```

**Storage:** `settings_data["gh_context_default_enabled"] = bool`

**Application:**
- When creating new environment (environments_actions.py)
- Check global default setting
- Set `env.gh_context_enabled = settings_data.get("gh_context_default_enabled", False)`
- User can override in environment editor

### 5. Metadata Generation Strategy

**Decision Tree:**

```
Task Start
  ├─ Environment has gh_context_enabled == True?
  │   ├─ No → Skip GitHub context, continue task
  │   └─ Yes → Proceed to context generation
  │
  └─ Determine environment type
      ├─ GH_MANAGEMENT_GITHUB (git-locked)
      │   ├─ Workspace will be cloned by agent_worker.py
      │   ├─ After clone completes: Extract repo context
      │   ├─ Populate github object: repo_url, base_branch, task_branch, head_commit
      │   └─ Create metadata file with full context
      │
      ├─ GH_MANAGEMENT_LOCAL (folder-locked)
      │   ├─ Run git detection on target folder
      │   ├─ If NOT git repo:
      │   │   └─ Log warning, skip GitHub context, continue task
      │   ├─ If IS git repo:
      │   │   ├─ Extract current context: repo_url, branch, commit
      │   │   ├─ No task branch (user manages git)
      │   │   ├─ Populate github object with extracted data
      │   │   └─ Create metadata file with context
      │   └─
      │
      └─ GH_MANAGEMENT_NONE (no workspace management)
          └─ Skip GitHub context (cannot determine workspace)
```

**Timing Considerations:**

| Environment Type | Metadata Creation Time | GitHub Object Population |
|------------------|------------------------|--------------------------|
| Git-locked | BEFORE clone | AFTER clone completes |
| Folder-locked | BEFORE task starts | BEFORE task starts |
| None | N/A | N/A |

**Why Different Timing?**
- **Git-locked:** Workspace doesn't exist yet, must wait for clone
- **Folder-locked:** Workspace already exists, can detect immediately

**Implementation Strategy:**

```python
# For git-locked (in agent_worker.py after clone):
def _populate_github_context_after_clone(
    metadata_path: str,
    repo_root: str,
    base_branch: str,
    task_branch: str,
) -> None:
    """Update metadata file with post-clone git context."""
    # Extract repo URL, commit SHA
    context = extract_git_context(repo_root)
    
    # Load existing metadata (has task_id, empty title/body)
    meta = load_metadata(metadata_path)
    
    # Populate github object
    meta.github = GitHubContext(
        repo_url=context.repo_url,
        repo_owner=context.owner,
        repo_name=context.name,
        base_branch=base_branch,
        task_branch=task_branch,
        head_commit=context.commit,
    )
    
    # Save updated metadata
    save_metadata(metadata_path, meta)

# For folder-locked (in main_window_tasks_agent.py before task):
def _create_github_context_for_local(
    metadata_path: str,
    task_id: str,
    folder_path: str,
) -> bool:
    """Create metadata file with git context for local folder."""
    # Detect git context
    context = detect_git_context(folder_path)
    if not context:
        return False  # Not a git repo or detection failed
    
    # Create metadata with github object
    meta = GitHubMetadata(
        version=2,
        task_id=task_id,
        github=GitHubContext(
            repo_url=context.repo_url,
            repo_owner=context.owner,
            repo_name=context.name,
            base_branch=context.current_branch,
            task_branch=None,  # No task branch for local folders
            head_commit=context.head_commit,
        ),
        title="",
        body="",
    )
    
    # Save metadata
    save_metadata(metadata_path, meta)
    return True
```

### 6. Auth Mounting Strategy (Out of Scope, but Documented)

**IMPORTANT:** This task does NOT implement auth mounting. This section documents the design for clarity.

**Separation of Concerns:**
- **GitHub Context:** Non-secret metadata (repo URL, branch, commit)
- **GitHub Auth:** Credentials for API/git operations

**Future Auth Mounting Feature:**
- Separate checkbox: "Mount host GitHub credentials (gh, git config)"
- Mounts:
  - `~/.config/gh/` → `/home/midori-ai/.config/gh/:ro`
  - `~/.gitconfig` → `/home/midori-ai/.gitconfig:ro`
  - `~/.git-credentials` → `/home/midori-ai/.git-credentials:ro` (if exists)
- Security warning: "This provides full GitHub access to the agent"
- Default: OFF (must explicitly enable)
- Not implemented in this task

**Why Separate?**
- GitHub context is safe (no credentials)
- Auth mounting requires explicit user consent
- Different security profiles
- Auth needed for: pushing commits, creating PRs, accessing private repos
- Context needed for: better PR descriptions, understanding repo structure

### 7. Gemini Allowed-Dirs Integration

**Problem:** Gemini CLI requires `--include-directories` for file access outside workspace.

**Current Behavior:** `agent_cli.py:98-110`
```python
if agent == "gemini":
    args = [
        "gemini",
        "--no-sandbox",
        "--approval-mode",
        "yolo",
        "--include-directories",
        container_workdir,  # Only workspace
        *extra_args,
    ]
```

**Required Behavior:**
- When GitHub context enabled: Add `/tmp` to allowed directories
- Gemini needs access to `/tmp/github-context-{task_id}.json`
- Multiple `--include-directories` flags supported

**Implementation:**

```python
def build_noninteractive_cmd(
    *,
    agent: str,
    prompt: str,
    host_workdir: str,
    container_workdir: str = CONTAINER_WORKDIR,
    agent_cli_args: list[str] | None = None,
    github_context_enabled: bool = False,  # NEW parameter
) -> list[str]:
    # ... existing code ...
    
    if agent == "gemini":
        allowed_dirs = [container_workdir]
        
        # Add /tmp if GitHub context enabled
        if github_context_enabled:
            allowed_dirs.append("/tmp")
        
        args = [
            "gemini",
            "--no-sandbox",
            "--approval-mode",
            "yolo",
        ]
        
        # Add all allowed directories
        for dir_path in allowed_dirs:
            args.extend(["--include-directories", dir_path])
        
        args.extend(extra_args)
        if prompt:
            args.append(prompt)
        
        return args
```

**Alternative (Simpler):**
- Always add `/tmp` to Gemini allowed directories
- Doesn't leak anything sensitive
- Simpler implementation (no conditional logic)
- GitHub context file only present when enabled anyway

**Recommendation:** Always include `/tmp` for Gemini (simpler, no security risk)

### 8. Error Handling Strategy

**Principle:** Fail gracefully, never block task execution.

**Error Scenarios:**

| Scenario | Detection Point | Handling | User Feedback |
|----------|----------------|----------|---------------|
| Folder is not a git repo | Task start (local) | Skip GitHub context, continue task | Log: "[gh] folder not a git repo, skipping context" |
| Git command fails | Git detection | Skip GitHub context, continue task | Log: "[gh] git detection failed: {error}" |
| Git command times out | Git detection (8s timeout) | Skip GitHub context, continue task | Log: "[gh] git detection timed out" |
| Metadata file write fails | Metadata creation | Skip GitHub context, continue task | Log: "[gh] failed to create context file: {error}" |
| Git clone fails (git-locked) | Clone phase | Fail task (existing behavior) | Show clone error (unchanged) |
| Invalid repo URL | URL parsing | Skip GitHub context, populate with partial data | Log: "[gh] could not parse repo URL" |

**Logging Strategy:**
- Prefix all logs with `[gh]` for GitHub-related operations
- Use `logger.warning()` for expected failures (not git repo)
- Use `logger.error()` for unexpected failures (write error)
- Always log reason for skipping context
- Never throw exceptions that would block task

**User-Visible Errors:**
- No error dialogs for GitHub context failures
- Log messages visible in task details log
- Tooltip explains when context is not available
- Checkbox disabled state indicates not applicable

### 9. Prompt Template Updates

**Current Template:** `prompts/pr_metadata.md`

**Problems:**
- File path hardcoded: `/tmp/codex-pr-metadata-{task_id}.json`
- Instructions minimal (only title/body)
- No guidance on using github object

**New Template:** `prompts/github_context.md`

```markdown
# GitHub Context Instructions

This prompt provides GitHub repository context to help agents create better PRs and commits.

**When used:** GitHub context enabled for environment  
**Template variables:** `{GITHUB_CONTEXT_FILE}` - Container path to JSON file

## Prompt

GITHUB CONTEXT (for non-interactive tasks)
- A JSON file is mounted at: {GITHUB_CONTEXT_FILE}
- This file contains repository context (URL, branch, commit) and PR metadata
- Structure:
  ```json
  {
    "version": 2,
    "task_id": "abc123",
    "github": {
      "repo_url": "https://github.com/owner/repo",
      "base_branch": "main",
      "task_branch": "task/abc123",  # May be null for local folders
      "head_commit": "abc123..."
    },
    "title": "",
    "body": ""
  }
  ```

- If you make changes intended for a PR, update the "title" and "body" fields
- Title should be concise (<= 72 chars)
- Body should be markdown describing the changes
- Keep valid JSON (no trailing commas)
- The github object is read-only (provided for context)
- REMINDER: Don't forget to commit your code changes with `git commit`!
```

**Migration:**
- Keep `pr_metadata.md` for backward compatibility (v1 schema)
- Use `github_context.md` for v2 schema
- Check metadata version to determine which template to use

---

## File Structure

### New Modules

**1. `agents_runner/gh/context.py` (150-200 lines)**
- Git context detection and caching
- URL parsing
- Integration point for folder-locked environments

```python
@dataclass
class GitContext:
    repo_root: str
    repo_url: str
    repo_owner: str | None
    repo_name: str | None
    current_branch: str
    head_commit: str

def detect_git_context(folder_path: str) -> GitContext | None:
    """Detect git context for a local folder."""

def cache_git_context(env_id: str, context: GitContext | None) -> None:
    """Cache git context result."""

def get_cached_git_context(env_id: str) -> GitContext | None | False:
    """Get cached git context. False = detection failed previously."""

def should_enable_github_context(
    env: Environment,
    cached_context: GitContext | None | False,
) -> bool:
    """Determine if GitHub context should be enabled for this environment."""

def build_github_context_prompt(container_path: str) -> str:
    """Build prompt instructions for GitHub context."""
```

**2. `agents_runner/prompts/github_context.md` (NEW)**
- Agent-agnostic GitHub context instructions
- Replaces pr_metadata.md for v2 schema

### Modified Files

**1. `agents_runner/pr_metadata.py`**
- Add v2 schema support
- Add `GitHubContext` dataclass
- Update file naming (codex-pr-metadata → github-context)
- Maintain backward compatibility with v1

```python
@dataclass
class GitHubContext:
    repo_url: str
    repo_owner: str | None
    repo_name: str | None
    base_branch: str
    task_branch: str | None
    head_commit: str

@dataclass
class PrMetadataV2:
    version: int = 2
    task_id: str = ""
    github: GitHubContext | None = None
    title: str | None = None
    body: str | None = None

def ensure_github_context_file_v2(
    path: str,
    *,
    task_id: str,
    github_context: GitHubContext | None = None,
) -> None:
    """Create v2 metadata file with GitHub context."""

def load_github_context(path: str) -> PrMetadataV2:
    """Load metadata file (v1 or v2)."""
```

**2. `agents_runner/environments/model.py`**
- Rename field: `gh_pr_metadata_enabled` → `gh_context_enabled`
- Add migration logic for existing environments

```python
@dataclass
class Environment:
    # ... existing fields ...
    gh_context_enabled: bool = False  # Renamed from gh_pr_metadata_enabled
```

**3. `agents_runner/environments/serialize.py`**
- Handle field migration: `gh_pr_metadata_enabled` → `gh_context_enabled`
- Auto-migrate on load

```python
def deserialize_environment(data: dict) -> Environment:
    # ... existing code ...
    
    # Migrate old field name
    if "gh_pr_metadata_enabled" in data:
        data["gh_context_enabled"] = data.pop("gh_pr_metadata_enabled")
    
    # ... rest of deserialization ...
```

**4. `agents_runner/ui/pages/environments.py`**
- Update checkbox: `_gh_pr_metadata_enabled` → `_gh_context_enabled`
- Update label and tooltip
- Add enable/disable logic based on git detection
- Wire git detection for folder-locked environments

```python
# Line ~167-175
self._gh_context_enabled = QCheckBox("Provide GitHub context to agent")
self._gh_context_enabled.setToolTip(
    "When enabled, repository context (URL, branch, commit) is provided to the agent.\n"
    "For GitHub-managed environments: Always available.\n"
    "For folder-managed environments: Only if folder is a git repository."
)

# Add git detection on folder path change
def _on_workspace_target_changed(self) -> None:
    if self._gh_management_mode == GH_MANAGEMENT_LOCAL:
        folder_path = self._gh_management_target.text().strip()
        context = detect_git_context(folder_path)
        self._gh_context_enabled.setEnabled(context is not None)
        if context is None:
            self._gh_context_enabled.setToolTip(
                "Folder is not a git repository. GitHub context not available."
            )
```

**5. `agents_runner/ui/main_window_tasks_agent.py`**
- Replace `gh_pr_metadata_enabled` with `gh_context_enabled`
- Add folder-locked git detection
- Update file paths (codex-pr-metadata → github-context)
- Update env var name (CODEX_PR_METADATA_PATH → GITHUB_CONTEXT_PATH)
- Use v2 schema for new files

```python
# Line ~334-358
if env and bool(getattr(env, "gh_context_enabled", False)):
    # Determine if we should create context
    should_create = False
    github_context = None
    
    if gh_mode == GH_MANAGEMENT_GITHUB:
        # Git-locked: Create file now, populate after clone
        should_create = True
    elif gh_mode == GH_MANAGEMENT_LOCAL:
        # Folder-locked: Detect git context now
        folder_path = env.gh_management_target
        git_ctx = detect_git_context(folder_path)
        if git_ctx:
            should_create = True
            github_context = GitHubContext(
                repo_url=git_ctx.repo_url,
                repo_owner=git_ctx.repo_owner,
                repo_name=git_ctx.repo_name,
                base_branch=git_ctx.current_branch,
                task_branch=None,  # No task branch for local
                head_commit=git_ctx.head_commit,
            )
    
    if should_create:
        host_path = github_context_host_path(
            os.path.dirname(self._state_path), task_id
        )
        container_path = github_context_container_path(task_id)
        
        try:
            ensure_github_context_file_v2(
                host_path,
                task_id=task_id,
                github_context=github_context,
            )
        except Exception as exc:
            self._on_task_log(task_id, f"[gh] failed to create context file: {exc}")
        else:
            task.gh_context_path = host_path
            extra_mounts_for_task.append(f"{host_path}:{container_path}:rw")
            env_vars_for_task.setdefault("GITHUB_CONTEXT_PATH", container_path)
            runner_prompt = f"{runner_prompt}{build_github_context_prompt(container_path)}"
            self._on_task_log(task_id, f"[gh] GitHub context enabled; mounted -> {container_path}")
```

**6. `agents_runner/docker/agent_worker.py`**
- Update to populate github object after clone (git-locked only)
- Add call to populate_github_context_after_clone()

```python
# After successful clone (line ~200-250)
if self._config.github_context_enabled and self._config.github_context_path:
    # Populate github object with post-clone context
    try:
        populate_github_context_after_clone(
            metadata_path=self._config.github_context_path,
            repo_root=repo_root,
            base_branch=base_branch,
            task_branch=task_branch,
        )
        self._on_log("[gh] populated GitHub context with repo info")
    except Exception as exc:
        self._on_log(f"[gh] failed to populate context: {exc}")
```

**7. `agents_runner/agent_cli.py`**
- Add `github_context_enabled` parameter to `build_noninteractive_cmd()`
- Update Gemini to include `/tmp` in allowed directories when enabled

```python
def build_noninteractive_cmd(
    *,
    agent: str,
    prompt: str,
    host_workdir: str,
    container_workdir: str = CONTAINER_WORKDIR,
    agent_cli_args: list[str] | None = None,
    github_context_enabled: bool = False,  # NEW
) -> list[str]:
    # ... existing code ...
    
    if agent == "gemini":
        allowed_dirs = [container_workdir]
        if github_context_enabled:
            allowed_dirs.append("/tmp")
        
        args = ["gemini", "--no-sandbox", "--approval-mode", "yolo"]
        for dir_path in allowed_dirs:
            args.extend(["--include-directories", dir_path])
        args.extend(extra_args)
        if prompt:
            args.append(prompt)
        return args
    
    # ... rest of function ...
```

**8. `agents_runner/ui/task_model.py`**
- Rename field: `gh_pr_metadata_path` → `gh_context_path`

```python
@dataclass
class Task:
    # ... existing fields ...
    gh_context_path: str | None = None  # Renamed from gh_pr_metadata_path
```

**9. `agents_runner/ui/pages/settings.py`**
- Add global default checkbox for GitHub context

```python
# After preflight section (~line 250)
self._gh_context_default = QCheckBox(
    "Enable GitHub context by default for new environments"
)
self._gh_context_default.setToolTip(
    "When enabled, new environments will have GitHub context enabled by default."
)

# Wire to settings_data
def _load_settings(self):
    # ... existing code ...
    self._gh_context_default.setChecked(
        self._settings_data.get("gh_context_default_enabled", False)
    )

def _save_settings(self):
    # ... existing code ...
    self._settings_data["gh_context_default_enabled"] = (
        self._gh_context_default.isChecked()
    )
```

**10. `agents_runner/ui/pages/environments_actions.py`**
- Apply global default when creating new environment

```python
# Line ~120-130 (when creating new environment)
gh_context_default = self._settings_data.get("gh_context_default_enabled", False)
new_env = Environment(
    # ... existing fields ...
    gh_context_enabled=gh_context_default,
)
```

**11. `agents_runner/gh/git_ops.py`**
- Add new git operations: `git_head_commit()`, `git_remote_url()`, `parse_github_url()`

---

## Implementation Plan

### Phase 1: Infrastructure (2 days)

**Coder Tasks:**

1. **Add new git operations to git_ops.py**
   - Implement `git_head_commit()`
   - Implement `git_remote_url()`
   - Implement `parse_github_url()`
   - Test with various URL formats (HTTPS, SSH, etc)

2. **Create gh/context.py module**
   - Implement `GitContext` dataclass
   - Implement `detect_git_context()`
   - Implement caching functions
   - Implement `should_enable_github_context()`

3. **Update pr_metadata.py for v2 schema**
   - Add `GitHubContext` and `PrMetadataV2` dataclasses
   - Implement `ensure_github_context_file_v2()`
   - Implement `load_github_context()` with v1/v2 detection
   - Update file path functions (remove "codex" prefix)
   - Maintain backward compatibility

**QA Tasks:**
- Test git detection with various repo types (HTTPS, SSH, local)
- Test URL parsing with edge cases
- Test v1/v2 schema loading

### Phase 2: Data Model Migration (1 day)

**Coder Tasks:**

4. **Update Environment model**
   - Rename field: `gh_pr_metadata_enabled` → `gh_context_enabled`
   - Update serialize/deserialize with migration logic
   - Test migration with existing environment files

5. **Update Task model**
   - Rename field: `gh_pr_metadata_path` → `gh_context_path`
   - Update all references

**QA Tasks:**
- Test migration of existing environments
- Verify backward compatibility

### Phase 3: UI Updates (1.5 days)

**Coder Tasks:**

6. **Update Environments editor**
   - Rename checkbox to `_gh_context_enabled`
   - Update label and tooltip
   - Add git detection on folder path change
   - Implement enable/disable logic

7. **Update Settings page**
   - Add global default checkbox
   - Wire to settings_data
   - Test save/load

8. **Update environments_actions.py**
   - Apply global default when creating new environment
   - Test new environment creation

**QA Tasks:**
- Test checkbox enable/disable for different environment types
- Test global default application
- Test git detection on folder path change

### Phase 4: Task Execution Integration (2 days)

**Coder Tasks:**

9. **Update main_window_tasks_agent.py**
   - Replace `gh_pr_metadata_enabled` with `gh_context_enabled`
   - Add folder-locked git detection at task start
   - Use v2 schema for new files
   - Update file paths and env var names

10. **Update agent_worker.py**
    - Add github object population after clone (git-locked)
    - Call `populate_github_context_after_clone()`
    - Test with git-locked environments

11. **Update agent_cli.py**
    - Add `github_context_enabled` parameter
    - Update Gemini allowed directories
    - Test with all agent types

**QA Tasks:**
- Test task execution with git-locked + context enabled
- Test task execution with folder-locked + context enabled
- Test task execution with context disabled
- Test task execution with non-git folder
- Test Gemini file access to context file

### Phase 5: Prompt Templates (0.5 days)

**Coder Tasks:**

12. **Create github_context.md prompt template**
    - Agent-agnostic instructions
    - Document v2 schema
    - Template variable: GITHUB_CONTEXT_FILE

13. **Update prompt loading logic**
    - Use github_context.md for v2
    - Keep pr_metadata.md for v1 (backward compat)

**QA Tasks:**
- Test prompt rendering with v2 schema
- Test backward compatibility with v1

### Phase 6: Testing & Documentation (1 day)

**QA Tasks:**
- Full integration testing with all agent types (codex, claude, copilot, gemini)
- Test all environment types (git-locked, folder-locked, none)
- Test git detection edge cases (no remote, detached HEAD, etc)
- Test error handling (git failures, write errors)
- Test migration of existing environments
- Test global default application

**Coder Tasks:**
- Fix any bugs found in testing
- Update AGENTS.md if needed
- Update inline documentation

**Auditor Tasks:**
- Code review for security (no credentials in files)
- Code review for error handling (graceful degradation)
- Code review for backward compatibility

### Phase 7: Polish & Edge Cases (1 day)

**Coder Tasks:**
- Add loading indicators for git detection (if slow)
- Improve log messages for clarity
- Handle edge cases:
  - Detached HEAD state
  - No remote configured
  - Multiple remotes (prefer "origin")
  - Shallow clones
  - Submodules

**QA Tasks:**
- Test edge cases
- Test performance (git detection should be fast)

---

## Risk Analysis

### High Risk

**Risk 1: Breaking Existing PR Creation**
- **Impact:** HIGH - Users can't create PRs
- **Likelihood:** MEDIUM - Changing file paths and field names
- **Mitigation:**
  - Maintain v1 schema support
  - Test PR creation with existing environments
  - Provide rollback mechanism (revert field migration)

**Risk 2: Git Detection Performance Issues**
- **Impact:** MEDIUM - Slow task startup
- **Likelihood:** LOW - Git operations are fast
- **Mitigation:**
  - 8 second timeout on all git operations
  - Cache detection results
  - Run in background thread (future enhancement)

**Risk 3: Gemini Allowed-Dirs Not Working**
- **Impact:** MEDIUM - Gemini can't access context file
- **Likelihood:** LOW - Flag is documented
- **Mitigation:**
  - Test Gemini file access explicitly
  - Add logging when adding allowed directories
  - Fallback: Always include /tmp for Gemini

### Medium Risk

**Risk 4: URL Parsing Failures**
- **Impact:** LOW - Partial context, missing owner/repo
- **Likelihood:** MEDIUM - Many URL formats exist
- **Mitigation:**
  - Test with common formats (HTTPS, SSH, git://)
  - Log parsing failures
  - Graceful degradation (use raw URL if parsing fails)

**Risk 5: Migration Breaking Existing Environments**
- **Impact:** HIGH - Users lose environment configs
- **Likelihood:** LOW - Simple field rename
- **Mitigation:**
  - Test migration extensively
  - Keep backup (.bak) files
  - Auto-migration on load (no manual action)

**Risk 6: Cache Invalidation Issues**
- **Impact:** LOW - Stale git context
- **Likelihood:** LOW - Cache invalidated on edit
- **Mitigation:**
  - Clear cache on environment edit
  - Clear cache on app restart
  - Add "Refresh" button (future enhancement)

### Low Risk

**Risk 7: Folder-Locked Users Don't Understand Feature**
- **Impact:** LOW - Feature not used
- **Likelihood:** MEDIUM - Complex logic
- **Mitigation:**
  - Clear tooltips explaining when available
  - Disabled state when not applicable
  - Log messages explaining skipping

**Risk 8: Agent Not Using Context**
- **Impact:** LOW - Feature has no effect
- **Likelihood:** MEDIUM - Agent may ignore JSON
- **Mitigation:**
  - Clear prompt instructions
  - Test with each agent type
  - Document in agent-specific guides

---

## Success Criteria

### Functional Success

1. ✅ GitHub context works for git-locked environments (existing functionality preserved)
2. ✅ GitHub context works for folder-locked git repositories (NEW)
3. ✅ GitHub context disabled for non-git folder-locked environments
4. ✅ Per-environment toggle works correctly
5. ✅ Global default setting applies to new environments
6. ✅ All agent types (codex, claude, copilot, gemini) receive context
7. ✅ Gemini can access context file (allowed directories work)
8. ✅ Error handling graceful (no task failures from git detection)
9. ✅ Migration preserves existing environments
10. ✅ PR creation still works (backward compatibility)

### Non-Functional Success

11. ✅ Git detection completes in < 2 seconds (normal case)
12. ✅ Git detection times out after 8 seconds (worst case)
13. ✅ No credentials in context files (security audit)
14. ✅ UI responsive during git detection (no freezing)
15. ✅ Clear log messages for all paths (debugging)
16. ✅ All new files under 300 lines (code quality)
17. ✅ Test coverage for git detection (QA validation)

---

## Open Questions

### Question 1: Should We Auto-Enable for Existing Git-Locked Environments?

**Context:** Existing git-locked environments have `gh_pr_metadata_enabled=False` by default.

**Options:**
1. **Auto-enable:** Migrate to `gh_context_enabled=True` for all git-locked
2. **Preserve:** Keep existing setting (False), user must enable manually
3. **Prompt:** Ask user on first launch after upgrade

**Recommendation:** **Option 2 (Preserve)**
- Respects user choices
- No surprise behavior changes
- User can enable if desired
- Consistent with new environment behavior (default OFF)

**Decision Needed By:** Phase 2 (data model migration)

### Question 2: Should We Include Non-GitHub Git Repos?

**Context:** parse_github_url() only handles GitHub URLs. GitLab, Bitbucket, etc. won't be parsed.

**Options:**
1. **GitHub-only:** Fail to parse non-GitHub URLs, skip owner/repo
2. **Generic support:** Add parsers for GitLab, Bitbucket, generic git URLs
3. **Raw URL only:** Don't parse, just include raw URL

**Recommendation:** **Option 3 (Raw URL only)**
- Simpler implementation
- Works for all git hosting providers
- Owner/repo not critical (agents can parse if needed)
- Can add parsing later if needed

**Decision Needed By:** Phase 1 (infrastructure)

### Question 3: Should We Detect Git for Mode="none" Environments?

**Context:** Environments with `gh_management_mode="none"` use settings workdir.

**Options:**
1. **Detect:** Run git detection on settings workdir if context enabled
2. **Skip:** Only support git-locked and folder-locked
3. **Optional:** Add checkbox "Detect git in workdir"

**Recommendation:** **Option 2 (Skip)**
- Mode="none" is for non-workspace scenarios
- Workdir may not be consistent across tasks
- Adds complexity without clear benefit
- User can use folder-locked if they want git context

**Decision Needed By:** Phase 3 (UI updates)

### Question 4: Should Context File Be Writable by Agent?

**Context:** Current mount is `:rw` (read-write). Agent can modify entire file.

**Options:**
1. **Read-write (current):** Agent can modify all fields including github object
2. **Read-only:** Mount `:ro`, agent cannot modify (but can't set title/body)
3. **Copy:** Mount original as `:ro`, create writable copy for agent

**Recommendation:** **Option 1 (Read-write)**
- Agent needs to write title/body
- Trusting agent not to corrupt github object
- If corrupted, only affects single task (not persistent)
- Simpler implementation

**Decision Needed By:** Phase 4 (task execution)

---

## Appendix A: File Naming Standards

### Old (v1, Copilot-era)

- **Host:** `~/.midoriai/agents-runner/pr-metadata/pr-metadata-{task_id}.json`
- **Container:** `/tmp/codex-pr-metadata-{task_id}.json`
- **Env Var:** `CODEX_PR_METADATA_PATH`

### New (v2, Agent-agnostic)

- **Host:** `~/.midoriai/agents-runner/github-context/github-context-{task_id}.json`
- **Container:** `/tmp/github-context-{task_id}.json`
- **Env Var:** `GITHUB_CONTEXT_PATH`

### Migration Strategy

- Create new files with v2 naming
- Keep old files for backward compatibility (don't rename existing)
- PR creation code checks both paths (prefer new, fall back to old)
- Delete old files after 30 days (cleanup task, future enhancement)

---

## Appendix B: Example Metadata Files

### Git-Locked Environment (Post-Clone)

```json
{
  "version": 2,
  "task_id": "a1b2c3d4e5",
  "github": {
    "repo_url": "https://github.com/midori-ai/agents-runner",
    "repo_owner": "midori-ai",
    "repo_name": "agents-runner",
    "base_branch": "main",
    "task_branch": "task/a1b2c3d4e5",
    "head_commit": "abc123def456789012345678901234567890abcd"
  },
  "title": "",
  "body": ""
}
```

### Folder-Locked Environment (Git Repo)

```json
{
  "version": 2,
  "task_id": "f6g7h8i9j0",
  "github": {
    "repo_url": "https://github.com/user/project",
    "repo_owner": "user",
    "repo_name": "project",
    "base_branch": "develop",
    "task_branch": null,
    "head_commit": "def456abc789012345678901234567890abcdef"
  },
  "title": "",
  "body": ""
}
```

### Folder-Locked Environment (SSH URL)

```json
{
  "version": 2,
  "task_id": "k1l2m3n4o5",
  "github": {
    "repo_url": "git@github.com:org/repo.git",
    "repo_owner": "org",
    "repo_name": "repo",
    "base_branch": "master",
    "task_branch": null,
    "head_commit": "789012345678901234567890abcdef123456abc"
  },
  "title": "",
  "body": ""
}
```

### Agent-Populated (After Task)

```json
{
  "version": 2,
  "task_id": "a1b2c3d4e5",
  "github": {
    "repo_url": "https://github.com/midori-ai/agents-runner",
    "repo_owner": "midori-ai",
    "repo_name": "agents-runner",
    "base_branch": "main",
    "task_branch": "task/a1b2c3d4e5",
    "head_commit": "abc123def456789012345678901234567890abcd"
  },
  "title": "Add spell checker to prompt editor",
  "body": "Implements spell checking in the New Task prompt editor using QSyntaxHighlighter. Misspelled words are underlined in red, and suggestions are available via right-click context menu.\n\nChanges:\n- Add SpellChecker class using pyenchant\n- Create SpellCheckHighlighter for QPlainTextEdit\n- Integrate into New Task page\n- Add personal dictionary support"
}
```

---

## Appendix C: Git Detection Flow Chart

```
┌─────────────────────────────────────────────────────────────┐
│              User Enables GitHub Context Checkbox           │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ↓
              ┌───────────────────────┐
              │ What is env type?     │
              └───────┬───────────────┘
                      │
        ┌─────────────┼─────────────┬──────────────┐
        │             │             │              │
        ↓             ↓             ↓              ↓
  ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐
  │  NONE   │   │  LOCAL  │   │ GITHUB  │   │ Invalid │
  └────┬────┘   └────┬────┘   └────┬────┘   └────┬────┘
       │             │             │              │
       │             │             │              │
       ↓             ↓             ↓              ↓
  ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐
  │ Disable │   │ Detect  │   │ Enable  │   │ Disable │
  │ checkbox│   │ git in  │   │ checkbox│   │ checkbox│
  └─────────┘   │ folder  │   └─────────┘   └─────────┘
                └────┬────┘
                     │
           ┌─────────┴─────────┐
           │                   │
           ↓                   ↓
      ┌─────────┐         ┌─────────┐
      │Is git   │         │Not git  │
      │repo?    │         │repo     │
      └────┬────┘         └────┬────┘
           │                   │
           ↓                   ↓
      ┌─────────┐         ┌─────────┐
      │ Enable  │         │ Disable │
      │checkbox │         │ checkbox│
      │         │         │ + tooltip│
      └─────────┘         └─────────┘
```

---

**End of Design Document**

**Next Steps:**
1. Review this document with stakeholders
2. Get approval on design decisions
3. Answer open questions (Appendix)
4. Begin Phase 1 implementation

**Document Status:** READY FOR REVIEW  
**Last Updated:** 2025-01-07  
**Author:** Auditor Mode (AI)
