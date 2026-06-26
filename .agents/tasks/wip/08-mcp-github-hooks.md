# 08 — MCP GitHub Task Flow Hooks (Optional)

## What
Implement optional MCP tools that expose GitHub task flow operations: create PR for a task, check PR status, and retrieve git metadata for a task. Wire into the existing `agents_runner.gh` and `agents_runner.gh_management` modules.

## Why
The feature request specifies "Optional GitHub task flow hooks where appropriate." These enable external automation to manage GitHub PR workflows for completed tasks.

## Where
- Write into: `agents_runner/mcp/tools.py` (append) or `agents_runner/mcp/tools_github.py`

## Key imports (verified to exist)
```python
from agents_runner.gh_management import plan_repo_task, commit_push_and_pr, prepare_branch_for_task
from agents_runner.gh.permissions import check_pr_creation_capability_for_repo_ref
from agents_runner.gh.git_ops import is_git_repo, git_repo_root
from agents_runner.persistence import default_state_path, load_task_payload
```
Note: `check_pr_creation_capability_for_repo_ref(repo_ref, *, use_gh: bool, timeout_s: float = 15.0)` — `use_gh` is REQUIRED.
Note: `plan_repo_task(workdir, *, task_id, base_branch=None, branch_work_mode, task_branch_naming_style, task_branch_custom_template)` — all args after `*` are keyword-only.
Note: `commit_push_and_pr(repo_root, *, branch, base_branch, title, body, use_gh=True, agent_cli="", agent_display_name=None)` — `branch`, `base_branch`, `title`, `body` are REQUIRED keyword args.

### Tools to implement

#### `github_pr_create`
- **Input:** `task_id: str`, optional `commit_message: str`, optional `pr_title: str`, optional `pr_body: str`
- **Logic:**
  1. Load task from persistence: `load_task_payload(default_state_path(), task_id, archived=False)` (fall back to `archived=True` if not found active)
  2. Verify `workspace_type == "cloned"` and `gh_repo_root` is set; if not, return error
  3. Call `plan_repo_task(gh_repo_root, task_id=task_id)` to get `RepoPlan`
  4. Call `commit_push_and_pr(repo_root=plan.repo_root, branch=plan.branch, base_branch=plan.base_branch, title=pr_title or "Task {task_id}", body=pr_body or "Automated PR from MCP", use_gh=True, agent_cli=task.get("agent_cli", ""))`
  5. Update task payload with PR URL and save
- **Returns:** `{task_id, gh_pr_url, gh_branch, status: "pr_created" | "error"}`

#### `github_pr_status`
- **Input:** `task_id: str`
- **Logic:**
  1. Load task from persistence (active and done)
  2. Extract `gh_pr_url`, `gh_branch`, `gh_pr_unavailable_reason`, `gh_pr_unavailable_status`
  3. Optionally check PR capability: `check_pr_creation_capability_for_repo_ref(gh_repo_root, use_gh=True)` — note `use_gh` is a REQUIRED keyword arg
- **Returns:** `{task_id, gh_pr_url, gh_branch, gh_base_branch, pr_status, gh_pr_unavailable_reason}`

#### `github_task_metadata`
- **Input:** `task_id: str`
- **Logic:**
  1. Load task; extract all GitHub-related fields from the payload: `gh_repo_root`, `gh_base_branch`, `gh_branch`, `gh_pr_url`, `gh_context_path`, `workspace_type`, `git` (full dict)
  2. Return structured metadata
- **Returns:** full git/GitHub metadata dict for the task

### Constraints
- Mark these tools as optional: if `gh` CLI is not available (`is_gh_available()` returns False) or task has no GitHub integration (no `gh_repo_root`), return a descriptive error (do not crash server)
- Some git operations may be slow — use `asyncio.to_thread()` for subprocess calls
- Do NOT import Qt / ui
- Use `midori_ai_logger` for operational logging
- Use `from __future__ import annotations`

### Registration
- Export `register_github_tools(server: MCPServer) -> None`
- Registration should be wrapped in try/except in the CLI entry point (task 09) so server starts even if gh CLI is unavailable.

## Dependencies
- Requires 01 (scaffold), 02 (types), 03 (transport), 04 (server core) completed first.
- Independent of tasks 05-07 (can be done in parallel).

## Done Criteria
- `uv run ruff check` clean.
- `uv run basedpyright` clean.
- Tools gracefully handle tasks without GitHub integration (no crash, meaningful error message).
- Import smoke test passes.
- grep confirms no Qt imports.
