# Workspace Type Refactor: Replace `gh_management_mode` with `workspace_type` (cloned vs mounted)

## Problem

The code currently conflates two different concepts:

1) **Environment kind** (GitHub repo clone vs local folder workspace)
2) **“Locked”** (a general boolean used for multiple meanings)

On/after 2026-01-09, `env.gh_management_locked` began being copied onto `task.gh_management_locked` and reused as “git locked”. Since folder-locked environments also have `gh_management_locked=True`, tasks from folder envs get misclassified as “git locked” and git-only behaviors (PR UI/actions, git metadata paths, etc.) leak into folder envs.

Related regression commits (for context):
- `780ef97` (2026-01-09): copied `env.gh_management_locked` onto tasks as `task.gh_management_locked`
- `5d9a1e3` (2026-01-09): partially corrected UI filtering to use mode instead of bool in one spot

## Goal

- Remove `gh_management_mode` entirely.
- Replace it with a single, explicit environment type:
  - `cloned`: a repo cloned fresh per task (sandboxed runs; PR-based extraction)
  - `mounted`: a host folder bind-mounted into the container (user-owned workspace)
- Ensure PR/git-only behaviors are keyed off `workspace_type == "cloned"` (not off any “locked” boolean).
- Fix terminology consistently across the repo (identifiers, UI labels/tooltips, and internal docs) to use `cloned`/`mounted` instead of “git/folder locked” or “gh management mode”.
- Keep diffs focused (no drive-by refactors).

## Confirmed Product Semantics (must enforce)

- `mounted` environments:
  - Use a host path mounted into the container (non-sandboxed / user-owned workspace).
  - Never create PRs (no PR UI/actions).
  - May optionally *detect* git for context injection (read-only), but must not behave like `git` envs.
- `cloned` environments:
  - Clone fresh on each task (fully sandboxed runs).
  - Must support “push work back to user” via PR (primary extraction path).

## Naming (recommended)

Internals:
- `workspace_type: Literal["cloned", "mounted", "none"]`
  - `cloned` means “repo cloned per task”, NOT “a mounted folder that happens to contain a .git directory”.
  - `mounted` means “host folder path mounted into container”.
  - `none` reserved for `_system` or special environments.

UI labels (avoid “locked” wording if desired):
- `git` → “GitHub Repo”
- `folder` → “Local Folder”

If “git” vs “folder” remains confusing, alternatives:
- `repo` vs `folder`
- `clone` vs `folder`
- `github_repo` vs `folder`

## Terminology Sweep (required)

Update names and UI text across the repo so the concepts are consistent:

- Code identifiers:
  - Replace `gh_management_mode` references with `workspace_type`.
  - Replace `gh_management_target` with `workspace_target`.
  - Replace “git locked” / “folder locked” naming in variables and helper methods:
    - Examples: `_gh_locked_envs` → `_cloned_envs` (or `_cloned_workspace_envs`), `is_git_locked` → `is_cloned_workspace`.
- UI labels / tooltips / messages:
  - Prefer “Cloned Repo” / “Mounted Folder” (or similar) and avoid “locked”.
  - PR gating messages should say PR is “only available for cloned environments” (or “cloned repo environments”).
- Internal docs:
  - Update `.agents/implementation/*` and other relevant markdowns that mention “gh management mode”, “git locked”, or “folder locked”.

Suggested search strings:
- `rg -n \"gh_management_mode|GH_MANAGEMENT_|normalize_gh_management_mode|git locked|folder locked|gh_locked|_gh_locked\"`

## Data Model Changes

Environment (`agents_runner/environments/model.py`)
- Remove:
  - `GH_MANAGEMENT_*` constants
  - `normalize_gh_management_mode`
  - `Environment.gh_management_mode`
- Add:
  - `WORKSPACE_NONE = "none"`
  - `WORKSPACE_MOUNTED = "mounted"`
  - `WORKSPACE_CLONED = "cloned"`
  - `normalize_workspace_type(value: str) -> str`
  - `Environment.workspace_type: str = WORKSPACE_NONE`
- Keep (renaming optional but recommended for clarity):
  - `gh_management_target` → rename to `workspace_target`
    - For `workspace_type=="cloned"`: repo slug/URL
    - For `workspace_type=="mounted"`: absolute folder path

“Locked” boolean
- Stop using `gh_management_locked` to mean “git locked”.
- Either:
  A) delete `gh_management_locked` and derive “locked-ness” from `env_type != "none"` (plus special-case `_system`), or
  B) rename it to `env_locked` and restrict usage to “environment fields are immutable / UI editing gated”

Task model (`agents_runner/ui/task_model.py`)
- Remove `Task.gh_management_mode` and `Task.gh_management_locked`.
- Add `Task.workspace_type: str = WORKSPACE_NONE`
- Any “requires git metadata” checks should become:
  - `return task.workspace_type == WORKSPACE_CLONED`

## Serialization / Migration Plan (must-have)

Environment serialization (`agents_runner/environments/serialize.py`)
- Read path:
  - Prefer new key `workspace_type`.
  - Migrate from old key `gh_management_mode`:
    - `"github"` → `workspace_type="cloned"`
    - `"local"` → `workspace_type="mounted"`
    - missing/unknown → `workspace_type="none"`
- Write path:
  - Write `workspace_type` + `workspace_target`.
  - Optionally continue writing `gh_management_mode` for one release if external tools depend on it (recommended only if needed).

Task persistence (`agents_runner/persistence.py`)
- Migrate old saved tasks:
  - If task has `gh_management_mode`:
    - `"github"` → `workspace_type="cloned"`
    - `"local"` → `workspace_type="mounted"`
  - If task has `gh_management_locked=True` but no mode:
    - Do NOT assume git; prefer deriving from environment if possible, otherwise default to `env_type="none"` and hide git-only UI.

## Behavior Rules (make these explicit in code)

- GitHub repo clone env:
  - `workspace_type == "cloned"`
  - PR creation allowed
  - Base-branch dropdown shown
  - Git context injection always enabled if `gh_context_enabled`
- Folder env:
  - `workspace_type == "mounted"`
  - PR creation hidden/disabled (no override)
  - Git context injection only if `gh_context_enabled` AND folder contains a git repo (detected)
  - Never treat folder env as “git locked” based on a shared bool

## High-Impact Call Sites To Update (non-exhaustive)

Environment selection / UI gating:
- `agents_runner/ui/main_window_environment.py`
  - `set_gh_locked_envs(...)` should become `set_git_envs(...)` (or similar) and use `env.env_type == "git"`.
- `agents_runner/ui/pages/new_task.py`
  - Any `env_id in _gh_locked_envs` checks should be replaced with `env_id in _git_envs` (or derived from env map).
- `agents_runner/ui/main_window_task_review.py`
  - PR availability checks must use `task.env_type == "git"` (or env lookup), never `gh_management_locked`.

Task creation / runner config:
- `agents_runner/ui/main_window_tasks_agent.py`
- `agents_runner/ui/main_window_tasks_interactive.py`
- `agents_runner/ui/main_window_preflight.py`
  - Stop setting `task.gh_management_locked = env.gh_management_locked`.
  - Set `task.env_type = env.env_type`.
  - Configure `gh_repo` only when `env_type == "git"`.

Environment creation/edit flows:
- `agents_runner/ui/pages/environments_actions.py`
- `agents_runner/ui/main_window_environment.py` (default env generation)
- `agents_runner/ui/dialogs/new_environment_wizard.py` (exists on unstable branch)

## Implementation Strategy (recommended, low-risk)

1) Introduce new `workspace_type` alongside existing `gh_management_mode` (temporary overlap).
2) Add migration in serializers (env + task) so existing users don’t lose environments/tasks.
3) Update all gating and runner logic to use `workspace_type` only.
4) Remove references to `gh_management_mode` and delete it from the model.
5) Rename/remove `gh_management_locked` to eliminate future semantic misuse.

## Acceptance Checks (manual, no tests required)

- Create a `mounted` env: no PR controls, no “cloned” behaviors, workspace path shows as expected.
- Create a `cloned` env: PR controls appear, base-branch selection works, PR creation uses repo clone.
- Existing saved environments load correctly (old fields migrate).
- Existing tasks do not incorrectly show PR/review controls after migration.
