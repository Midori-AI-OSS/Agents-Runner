"""Tool registration and dispatch for MCP server — task lifecycle tools."""

from __future__ import annotations

import json
import time
from typing import Any
from uuid import uuid4

from midori_ai_logger import MidoriAiLogger

from agents_runner.environments.storage import load_environments
from agents_runner.mcp.server import MCPServer
from agents_runner.mcp.types import (
    TextContent,
    ToolCallResult,
    ToolDefinition,
)
from agents_runner.persistence import (
    default_state_path,
    load_active_task_payloads,
    load_done_task_payloads,
    load_task_payload,
    save_task_payload,
)

logger = MidoriAiLogger(channel=None, name=__name__)


# ── Handlers ──────────────────────────────────────────────────────────────────


async def handle_task_create(
    env_id: str,
    prompt: str,
    image: str | None = None,
    agent_cli: str | None = None,
) -> ToolCallResult:
    """Create a new task in the specified environment and save it as an active payload."""
    envs = load_environments()
    env = envs.get(env_id)
    if env is None:
        error_msg = f"Environment '{env_id}' not found"
        logger.error(error_msg)
        return ToolCallResult(
            content=[TextContent(text=json.dumps({"error": error_msg}))],
            isError=True,
        )

    task_id = uuid4().hex[:12]
    now_s = time.time()
    payload: dict[str, Any] = {
        "task_id": task_id,
        "prompt": prompt,
        "image": image or "",
        "host_workdir": env.host_workdir,
        "host_config_dir": "",
        "environment_id": env_id,
        "created_at_s": now_s,
        "status": "queued",
        "exit_code": None,
        "error": None,
        "container_id": None,
        "started_at": None,
        "finished_at": None,
        "gh_use_host_cli": True,
        "workspace_type": "none",
        "gh_repo_root": "",
        "gh_base_branch": "",
        "gh_branch": "",
        "gh_pr_url": "",
        "gh_pr_metadata_path": "",
        "gh_pr_unavailable_reason": "",
        "gh_pr_unavailable_status": "",
        "gh_context_path": "",
        "git": None,
        "agent_cli": agent_cli or "",
        "agent_instance_id": "",
        "agent_cli_args": "",
        "launch_mode": "agent",
        "ide_system": "",
        "ide_display_target": "",
        "headless_desktop_enabled": False,
        "novnc_url": "",
        "opencode_web_url": "",
        "artifacts": [],
        "attempt_history": [],
        "finalization_state": "pending",
        "finalization_error": "",
        "runner_prompt": None,
        "runner_config": None,
        "logs": [],
    }

    save_task_payload(default_state_path(), payload, archived=False)
    logger.info(f"Task {task_id} created (env={env_id})")

    return ToolCallResult(
        content=[
            TextContent(
                text=json.dumps({"task_id": task_id, "status": payload["status"]}),
            ),
        ],
    )


async def handle_task_start(task_id: str) -> ToolCallResult:
    """Set a task's status to queued (searches active then archived storage)."""
    state_path = default_state_path()

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

    current_status = str(payload.get("status") or "")
    # Only change status if not already an active state (queued or running)
    if current_status not in ("queued", "running"):
        payload["status"] = "queued"
        # If the task was archived (done), save it as active to re-queue
        save_task_payload(state_path, payload, archived=False)
        logger.info(
            f"Task {task_id} status set to queued (was {current_status}"
            f"{', re-queued from archived' if found_archived else ''})",
        )
    else:
        logger.info(f"Task {task_id} already {current_status}, no change")

    return ToolCallResult(
        content=[
            TextContent(
                text=json.dumps(
                    {"task_id": task_id, "status": payload.get("status", "queued")},
                ),
            ),
        ],
    )


async def handle_task_list(status: str | None = None, limit: int = 20) -> ToolCallResult:
    """List tasks with optional status filter. Merges active and done tasks."""
    state_path = default_state_path()

    active = load_active_task_payloads(state_path)
    done = load_done_task_payloads(state_path, offset=0, limit=limit)

    merged = active + done
    if status:
        merged = [t for t in merged if str(t.get("status") or "").lower() == status.lower()]

    limited = merged[:limit]

    summaries: list[dict[str, Any]] = []
    for task in limited:
        prompt_raw = str(task.get("prompt") or "")
        if len(prompt_raw) > 80:
            prompt_raw = prompt_raw[:80] + "..."
        summaries.append(
            {
                "task_id": task.get("task_id", ""),
                "status": task.get("status", ""),
                "prompt_first_line": prompt_raw,
                "created_at": task.get("created_at_s"),
                "exit_code": task.get("exit_code"),
            }
        )

    return ToolCallResult(
        content=[TextContent(text=json.dumps(summaries))],
    )


async def handle_task_status(task_id: str) -> ToolCallResult:
    """Get detailed status of a task by ID (searches active then archived)."""
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

    raw_artifacts: Any = payload.get("artifacts")
    raw_logs: Any = payload.get("logs")

    detail: dict[str, Any] = {
        "task_id": payload.get("task_id"),
        "status": payload.get("status"),
        "exit_code": payload.get("exit_code"),
        "error": payload.get("error"),
        "started_at": payload.get("started_at"),
        "finished_at": payload.get("finished_at"),
        "container_id": payload.get("container_id"),
        "gh_pr_url": payload.get("gh_pr_url"),
        "artifacts_count": len(raw_artifacts) if isinstance(raw_artifacts, list) else 0,  # pyright: ignore[reportUnknownArgumentType]
        "logs_count": len(raw_logs) if isinstance(raw_logs, list) else 0,  # pyright: ignore[reportUnknownArgumentType]
    }

    return ToolCallResult(
        content=[TextContent(text=json.dumps(detail))],
    )


async def handle_task_cancel(task_id: str) -> ToolCallResult:
    """Cancel an active task. Archived (done) tasks cannot be cancelled."""
    state_path = default_state_path()

    payload = load_task_payload(state_path, task_id, archived=False)
    if payload is None:
        error_msg = f"Active task '{task_id}' not found (already done/archived tasks cannot be cancelled)"
        logger.error(error_msg)
        return ToolCallResult(
            content=[TextContent(text=json.dumps({"error": error_msg}))],
            isError=True,
        )

    payload["status"] = "cancelled"
    save_task_payload(state_path, payload, archived=False)
    logger.info(f"Task {task_id} cancelled")

    return ToolCallResult(
        content=[
            TextContent(
                text=json.dumps({"task_id": task_id, "status": "cancelled"}),
            ),
        ],
    )


# ── Registration ──────────────────────────────────────────────────────────────


def register_task_tools(server: MCPServer) -> None:
    """Register all task lifecycle tools with an MCP server instance.

    Args:
        server: An ``MCPServer`` instance.
    """
    server.register_tool(
        "task_create",
        handle_task_create,
        ToolDefinition(
            name="task_create",
            description="Create a new task in the specified environment and save it as an active payload.",
            inputSchema={
                "type": "object",
                "properties": {
                    "env_id": {
                        "type": "string",
                        "description": "Environment identifier",
                    },
                    "prompt": {
                        "type": "string",
                        "description": "Task prompt",
                    },
                    "image": {
                        "type": "string",
                        "description": "Container image (optional)",
                    },
                    "agent_cli": {
                        "type": "string",
                        "description": "Agent CLI to use (optional)",
                    },
                },
                "required": ["env_id", "prompt"],
            },
        ),
    )

    server.register_tool(
        "task_start",
        handle_task_start,
        ToolDefinition(
            name="task_start",
            description="Set a task's status to queued. Searches active then archived storage.",
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
        "task_list",
        handle_task_list,
        ToolDefinition(
            name="task_list",
            description="List tasks with optional status filter. Returns merged active and done tasks.",
            inputSchema={
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "description": "Filter by status (optional)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum tasks to return (default 20)",
                    },
                },
            },
        ),
    )

    server.register_tool(
        "task_status",
        handle_task_status,
        ToolDefinition(
            name="task_status",
            description="Get detailed status of a task by ID. Searches active then archived storage.",
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
        "task_cancel",
        handle_task_cancel,
        ToolDefinition(
            name="task_cancel",
            description="Cancel an active task. Already done/archived tasks cannot be cancelled.",
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

    logger.info("Registered 5 task lifecycle tools")
