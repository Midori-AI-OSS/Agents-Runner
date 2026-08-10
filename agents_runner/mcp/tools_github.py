"""MCP tool handlers for GitHub task flow operations (optional)."""

from __future__ import annotations

import asyncio
import json
from functools import partial
from typing import Any

from rich.console import Console

from midori_ai_logger import MidoriAiLogger

from agents_runner.gh import (
    RepoPlan,
    check_pr_creation_capability_for_repo_ref,
    commit_push_and_pr,
    is_gh_available,
    plan_repo_task,
)
from agents_runner.mcp.server import MCPServer
from agents_runner.mcp.types import TextContent, ToolCallResult, ToolDefinition
from agents_runner.persistence import default_state_path, load_task_payload, save_task_payload

logger = MidoriAiLogger(channel=None, name=__name__)
logger.console = Console(stderr=True)


# ── Handlers ──────────────────────────────────────────────────────────────────


async def handle_github_pr_create(
    task_id: str,
    commit_message: str | None = None,
    pr_title: str | None = None,
    pr_body: str | None = None,
) -> ToolCallResult:
    """Create a GitHub PR for a task.

    Loads the task from persistence (active then archived), verifies GitHub
    integration, plans the repo branch, and runs commit/push/PR creation.

    Args:
        task_id: Task identifier.
        commit_message: Git commit message (falls back to pr_title then default).
        pr_title: Pull request title (defaults to "Task {task_id}").
        pr_body: Pull request body (defaults to "Automated PR from MCP").

    Returns:
        ToolCallResult with ``{task_id, gh_pr_url, gh_branch, status}``.
    """
    state_path = default_state_path()

    # 1. Load task from persistence (active then archived)
    payload = load_task_payload(state_path, task_id, archived=False)
    found_archived = False
    if payload is None:
        payload = load_task_payload(state_path, task_id, archived=True)
        found_archived = True

    if payload is None:
        error_msg = f"Task '{task_id}' not found"
        logger.error(error_msg)
        return ToolCallResult(
            content=[TextContent(text=json.dumps({"error": error_msg}))],
            isError=True,
        )

    # 2. Verify workspace_type == "cloned" and gh_repo_root is set
    workspace_type = str(payload.get("workspace_type") or "")
    gh_repo_root = str(payload.get("gh_repo_root") or "")

    if workspace_type != "cloned" or not gh_repo_root:
        error_msg = (
            f"Task '{task_id}' does not have GitHub integration "
            f"(workspace_type={workspace_type!r}, gh_repo_root={gh_repo_root!r})"
        )
        logger.error(error_msg)
        return ToolCallResult(
            content=[TextContent(text=json.dumps({"error": error_msg}))],
            isError=True,
        )

    # Guard: gh CLI availability
    if not is_gh_available():
        error_msg = "GitHub CLI ('gh') is not available on this host"
        logger.error(error_msg)
        return ToolCallResult(
            content=[TextContent(text=json.dumps({"error": error_msg}))],
            isError=True,
        )

    # 3. Plan the repo task (off-thread for subprocess)
    try:
        plan: RepoPlan | None = await asyncio.to_thread(
            partial(plan_repo_task, gh_repo_root, task_id=task_id),
        )
    except Exception as exc:
        error_msg = f"Failed to plan repo task: {exc}"
        logger.error(error_msg)
        return ToolCallResult(
            content=[TextContent(text=json.dumps({"error": error_msg}))],
            isError=True,
        )

    if plan is None:
        error_msg = f"Task '{task_id}' is not in a git repository at {gh_repo_root}"
        logger.error(error_msg)
        return ToolCallResult(
            content=[TextContent(text=json.dumps({"error": error_msg}))],
            isError=True,
        )

    # 4. Commit, push, and create PR (off-thread for subprocess)
    title = commit_message or pr_title or f"Task {task_id}"
    body = pr_body or "Automated PR from MCP"
    agent_cli = str(payload.get("agent_cli") or "")

    try:
        pr_url: str | None = await asyncio.to_thread(
            partial(
                commit_push_and_pr,
                repo_root=plan.repo_root,
                branch=plan.branch,
                base_branch=plan.base_branch,
                title=title,
                body=body,
                use_gh=True,
                agent_cli=agent_cli,
                pr_retry_interval_minutes=5,
                pr_retry_max_minutes=60,
                on_log=None,
            ),
        )
    except Exception as exc:
        error_msg = f"Failed to create PR: {exc}"
        logger.error(error_msg)
        return ToolCallResult(
            content=[TextContent(text=json.dumps({"error": error_msg}))],
            isError=True,
        )

    # 5. Update task payload with PR URL and save
    payload["gh_pr_url"] = pr_url or ""
    payload["gh_branch"] = plan.branch
    payload["gh_base_branch"] = plan.base_branch

    save_task_payload(state_path, payload, archived=found_archived)
    logger.info(f"Task {task_id}: PR {'created' if pr_url else 'no changes'} at branch {plan.branch}")

    status = "pr_created" if pr_url else "no_changes"

    return ToolCallResult(
        content=[
            TextContent(
                text=json.dumps(
                    {
                        "task_id": task_id,
                        "gh_pr_url": pr_url or "",
                        "gh_branch": plan.branch,
                        "status": status,
                    },
                ),
            ),
        ],
    )


async def handle_github_pr_status(task_id: str) -> ToolCallResult:
    """Check the PR status for a task.

    Loads the task from persistence (active then archived), extracts GitHub
    fields, and optionally checks PR creation capability.

    Args:
        task_id: Task identifier.

    Returns:
        ToolCallResult with ``{task_id, gh_pr_url, gh_branch, gh_base_branch,
        pr_status, gh_pr_unavailable_reason, pr_capability_reason}``.
    """
    state_path = default_state_path()

    # 1. Load task from persistence (active then archived)
    payload = load_task_payload(state_path, task_id, archived=False)
    if payload is None:
        payload = load_task_payload(state_path, task_id, archived=True)

    if payload is None:
        error_msg = f"Task '{task_id}' not found"
        logger.error(error_msg)
        return ToolCallResult(
            content=[TextContent(text=json.dumps({"error": error_msg}))],
            isError=True,
        )

    # 2. Extract GitHub-related fields
    gh_pr_url: Any = payload.get("gh_pr_url")
    gh_branch = str(payload.get("gh_branch") or "")
    gh_base_branch = str(payload.get("gh_base_branch") or "")
    gh_pr_unavailable_reason = str(payload.get("gh_pr_unavailable_reason") or "")
    gh_pr_unavailable_status = str(payload.get("gh_pr_unavailable_status") or "")

    # Determine pr_status
    if gh_pr_url:
        pr_status = "created"
    elif gh_pr_unavailable_reason:
        pr_status = "unavailable"
    else:
        pr_status = "not_created"

    # 3. Optionally check PR capability (off-thread for subprocess)
    gh_repo_root = str(payload.get("gh_repo_root") or "")
    capability_reason = ""
    if gh_repo_root:
        try:
            capability = await asyncio.to_thread(
                partial(
                    check_pr_creation_capability_for_repo_ref,
                    gh_repo_root,
                    use_gh=True,
                    timeout_s=15.0,
                ),
            )
            if not capability.can_create_pr:
                capability_reason = capability.reason
        except Exception as exc:
            capability_reason = f"Could not check PR capability: {exc}"

    return ToolCallResult(
        content=[
            TextContent(
                text=json.dumps(
                    {
                        "task_id": task_id,
                        "gh_pr_url": str(gh_pr_url or ""),
                        "gh_branch": gh_branch,
                        "gh_base_branch": gh_base_branch,
                        "pr_status": pr_status,
                        "gh_pr_unavailable_reason": gh_pr_unavailable_reason,
                        "gh_pr_unavailable_status": gh_pr_unavailable_status,
                        "pr_capability_reason": capability_reason,
                    },
                ),
            ),
        ],
    )


async def handle_github_task_metadata(task_id: str) -> ToolCallResult:
    """Retrieve full GitHub/git metadata for a task.

    Args:
        task_id: Task identifier.

    Returns:
        ToolCallResult with all GitHub-related fields from the task payload.
    """
    state_path = default_state_path()

    payload = load_task_payload(state_path, task_id, archived=False)
    if payload is None:
        payload = load_task_payload(state_path, task_id, archived=True)

    if payload is None:
        error_msg = f"Task '{task_id}' not found"
        logger.error(error_msg)
        return ToolCallResult(
            content=[TextContent(text=json.dumps({"error": error_msg}))],
            isError=True,
        )

    metadata: dict[str, Any] = {
        "task_id": task_id,
        "gh_repo_root": str(payload.get("gh_repo_root") or ""),
        "gh_base_branch": str(payload.get("gh_base_branch") or ""),
        "gh_branch": str(payload.get("gh_branch") or ""),
        "gh_pr_url": str(payload.get("gh_pr_url") or ""),
        "gh_context_path": str(payload.get("gh_context_path") or ""),
        "workspace_type": str(payload.get("workspace_type") or ""),
        "git": payload.get("git"),
        "gh_pr_metadata_path": str(payload.get("gh_pr_metadata_path") or ""),
        "gh_pr_unavailable_reason": str(payload.get("gh_pr_unavailable_reason") or ""),
        "gh_pr_unavailable_status": str(payload.get("gh_pr_unavailable_status") or ""),
        "gh_use_host_cli": bool(payload.get("gh_use_host_cli", True)),
    }

    return ToolCallResult(
        content=[TextContent(text=json.dumps(metadata))],
    )


# ── Registration ──────────────────────────────────────────────────────────────


def register_github_tools(server: MCPServer) -> None:
    """Register all GitHub task flow hook tools with an MCP server instance.

    These tools are optional: registration should be wrapped in try/except in
    the CLI entry point so the server starts even if the ``gh`` CLI is
    unavailable.

    Args:
        server: An ``MCPServer`` instance.
    """
    server.register_tool(
        "github_pr_create",
        handle_github_pr_create,
        ToolDefinition(
            name="github_pr_create",
            description=(
                "Create a GitHub PR for a task. Requires a cloned workspace with GitHub integration and the ``gh`` CLI."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "Task identifier",
                    },
                    "commit_message": {
                        "type": "string",
                        "description": "Git commit message (optional, falls back to pr_title or default)",
                    },
                    "pr_title": {
                        "type": "string",
                        "description": "Pull request title (optional, defaults to 'Task {task_id}')",
                    },
                    "pr_body": {
                        "type": "string",
                        "description": "Pull request body (optional, defaults to 'Automated PR from MCP')",
                    },
                },
                "required": ["task_id"],
            },
        ),
    )

    server.register_tool(
        "github_pr_status",
        handle_github_pr_status,
        ToolDefinition(
            name="github_pr_status",
            description="Check the PR status for a task, including optional PR capability check.",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "Task identifier",
                    },
                },
                "required": ["task_id"],
            },
        ),
    )

    server.register_tool(
        "github_task_metadata",
        handle_github_task_metadata,
        ToolDefinition(
            name="github_task_metadata",
            description="Retrieve full GitHub/git metadata for a task.",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "Task identifier",
                    },
                },
                "required": ["task_id"],
            },
        ),
    )

    logger.info("Registered 3 GitHub task flow hook tools")
