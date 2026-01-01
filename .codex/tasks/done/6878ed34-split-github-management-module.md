# Split `codex_local_conatinerd/gh_management.py` into focused helpers

## Context
`codex_local_conatinerd/gh_management.py` is above the soft limit and contains mixed responsibilities: git operations, `gh` CLI interactions, planning, and error handling.

## Goal
Split GitHub/Git management into smaller modules with clear boundaries and stable public APIs.

## Proposed module layout
- `codex_local_conatinerd/gh_management.py`: compatibility shim for public API
- `codex_local_conatinerd/gh/` package:
  - `git_ops.py`: `is_git_repo`, `git_list_remote_heads`, small git helpers
  - `gh_cli.py`: `is_gh_available`, `gh` invocation and parsing
  - `repo_clone.py`: `ensure_github_clone` and checkout/update logic
  - `task_plan.py`: `plan_repo_task`, `prepare_branch_for_task`, `commit_push_and_pr`
  - `errors.py`: `GhManagementError` and related exceptions

## Acceptance criteria
- Existing call sites (especially `codex_local_conatinerd/app.py`) keep working without behavior changes.
- No file exceeds 600 lines; prefer ≤ 300.
- Errors remain user-friendly and actionable.

