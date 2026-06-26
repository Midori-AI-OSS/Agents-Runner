"""MCP tool handlers for environment CRUD operations."""

from __future__ import annotations

import json
from dataclasses import fields
from dataclasses import replace
from typing import Any

from midori_ai_logger import MidoriAiLogger

from agents_runner.environments.model import Environment
from agents_runner.environments.serialize import serialize_environment
from agents_runner.environments.storage import delete_environment
from agents_runner.environments.storage import load_environments
from agents_runner.environments.storage import save_environment
from agents_runner.mcp.server import MCPServer
from agents_runner.mcp.types import TextContent
from agents_runner.mcp.types import ToolCallResult
from agents_runner.mcp.types import ToolDefinition

logger = MidoriAiLogger(channel=None, name=__name__)


# ── Helpers ──────────────────────────────────────────────────────────────────

_ENVIRONMENT_FIELDS = {f.name for f in fields(Environment)}


# ── Handlers ──────────────────────────────────────────────────────────────────


async def handle_environment_list() -> ToolCallResult:
    """List all configured environments with summary information."""
    envs = load_environments()
    summaries: list[dict[str, Any]] = []
    for env_id, env in envs.items():
        agent_count = len(env.agent_selection.agents) if env.agent_selection is not None else 0
        summaries.append(
            {
                "env_id": env_id,
                "name": env.name,
                "color": env.color,
                "workspace_type": env.workspace_type,
                "agent_count": agent_count,
            }
        )
    return ToolCallResult(
        content=[TextContent(text=json.dumps({"environments": summaries}))],
    )


async def handle_environment_get(env_id: str) -> ToolCallResult:
    """Get the full serialized configuration of a single environment by ID."""
    envs = load_environments()
    env = envs.get(env_id)
    if env is None:
        error_msg = f"Environment '{env_id}' not found"
        logger.error(error_msg)
        return ToolCallResult(
            content=[TextContent(text=json.dumps({"error": error_msg}))],
            isError=True,
        )
    serialized = serialize_environment(env)
    return ToolCallResult(
        content=[TextContent(text=json.dumps(serialized))],
    )


async def handle_environment_create(**kwargs: Any) -> ToolCallResult:
    """Create a new environment with the given fields."""
    env_id = kwargs.pop("env_id", None)
    name = kwargs.pop("name", None)
    if not env_id or not name:
        error_msg = "env_id and name are required"
        logger.error(error_msg)
        return ToolCallResult(
            content=[TextContent(text=json.dumps({"error": error_msg}))],
            isError=True,
        )
    filtered = {k: v for k, v in kwargs.items() if k in _ENVIRONMENT_FIELDS and v is not None}
    env = Environment(env_id=env_id, name=name, **filtered)
    save_environment(env)
    logger.info(f"Environment '{env_id}' created")
    return ToolCallResult(
        content=[TextContent(text=json.dumps({"env_id": env.env_id, "name": env.name, "status": "created"}))],
    )


async def handle_environment_update(env_id: str, **kwargs: Any) -> ToolCallResult:
    """Update an existing environment — only provided fields are changed."""
    envs = load_environments()
    env = envs.get(env_id)
    if env is None:
        error_msg = f"Environment '{env_id}' not found"
        logger.error(error_msg)
        return ToolCallResult(
            content=[TextContent(text=json.dumps({"error": error_msg}))],
            isError=True,
        )
    kwargs.pop("env_id", None)
    filtered = {k: v for k, v in kwargs.items() if k in _ENVIRONMENT_FIELDS and v is not None}
    updated = replace(env, **filtered)
    save_environment(updated)
    logger.info(f"Environment '{env_id}' updated")
    return ToolCallResult(
        content=[
            TextContent(
                text=json.dumps({"env_id": updated.env_id, "name": updated.name, "status": "updated"}),
            )
        ],
    )


async def handle_environment_delete(env_id: str) -> ToolCallResult:
    """Delete an environment by ID."""
    delete_environment(env_id)
    logger.info(f"Environment '{env_id}' deleted")
    return ToolCallResult(
        content=[TextContent(text=json.dumps({"env_id": env_id, "status": "deleted"}))],
    )


# ── Registration ──────────────────────────────────────────────────────────────


def register_environment_tools(server: MCPServer) -> None:
    """Register all environment CRUD tools with an MCP server instance.

    Args:
        server: An ``MCPServer`` instance.
    """
    server.register_tool(
        "environment_list",
        handle_environment_list,
        ToolDefinition(
            name="environment_list",
            description="List all configured environments with summary information.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
    )

    server.register_tool(
        "environment_get",
        handle_environment_get,
        ToolDefinition(
            name="environment_get",
            description="Get the full serialized configuration of a single environment by ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "env_id": {
                        "type": "string",
                        "description": "Environment identifier",
                    },
                },
                "required": ["env_id"],
            },
        ),
    )

    server.register_tool(
        "environment_create",
        handle_environment_create,
        ToolDefinition(
            name="environment_create",
            description="Create a new environment. Only env_id and name are required; all other fields have defaults.",
            inputSchema={
                "type": "object",
                "properties": {
                    "env_id": {
                        "type": "string",
                        "description": "Unique environment identifier",
                    },
                    "name": {
                        "type": "string",
                        "description": "Human-readable environment name",
                    },
                    "color": {
                        "type": "string",
                        "description": "Theme color stain (e.g. emerald, slate, violet)",
                    },
                    "host_workdir": {
                        "type": "string",
                        "description": "Host working directory",
                    },
                    "workspace_type": {
                        "type": "string",
                        "description": "Workspace type (none, mounted, cloned)",
                    },
                    "workspace_target": {
                        "type": "string",
                        "description": "Workspace target path or URL",
                    },
                    "gpu_override_mode": {
                        "type": "string",
                        "description": "GPU override mode (inherit, enabled, disabled)",
                    },
                    "network_host_override_mode": {
                        "type": "string",
                        "description": "Network host override mode (inherit, enabled, disabled)",
                    },
                    "headless_desktop_enabled": {
                        "type": "boolean",
                        "description": "Enable headless desktop",
                    },
                    "agent_cli_args": {
                        "type": "string",
                        "description": "Default CLI arguments for agents",
                    },
                    "max_agents_running": {
                        "type": "integer",
                        "description": "Maximum concurrent agents (-1 for unlimited)",
                    },
                    "env_vars": {
                        "type": "object",
                        "description": "Environment variables as key-value pairs",
                    },
                    "extra_mounts": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Extra mount paths",
                    },
                    "ports": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Port mappings",
                    },
                },
                "required": ["env_id", "name"],
            },
        ),
    )

    server.register_tool(
        "environment_update",
        handle_environment_update,
        ToolDefinition(
            name="environment_update",
            description="Update an existing environment by ID. Only the provided fields are changed.",
            inputSchema={
                "type": "object",
                "properties": {
                    "env_id": {
                        "type": "string",
                        "description": "Environment identifier",
                    },
                    "name": {
                        "type": "string",
                        "description": "Human-readable environment name",
                    },
                    "color": {
                        "type": "string",
                        "description": "Theme color stain (e.g. emerald, slate, violet)",
                    },
                    "host_workdir": {
                        "type": "string",
                        "description": "Host working directory",
                    },
                    "workspace_type": {
                        "type": "string",
                        "description": "Workspace type (none, mounted, cloned)",
                    },
                    "workspace_target": {
                        "type": "string",
                        "description": "Workspace target path or URL",
                    },
                    "gpu_override_mode": {
                        "type": "string",
                        "description": "GPU override mode (inherit, enabled, disabled)",
                    },
                    "network_host_override_mode": {
                        "type": "string",
                        "description": "Network host override mode (inherit, enabled, disabled)",
                    },
                    "headless_desktop_enabled": {
                        "type": "boolean",
                        "description": "Enable headless desktop",
                    },
                    "agent_cli_args": {
                        "type": "string",
                        "description": "Default CLI arguments for agents",
                    },
                    "max_agents_running": {
                        "type": "integer",
                        "description": "Maximum concurrent agents (-1 for unlimited)",
                    },
                    "env_vars": {
                        "type": "object",
                        "description": "Environment variables as key-value pairs",
                    },
                    "extra_mounts": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Extra mount paths",
                    },
                    "ports": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Port mappings",
                    },
                },
                "required": ["env_id"],
            },
        ),
    )

    server.register_tool(
        "environment_delete",
        handle_environment_delete,
        ToolDefinition(
            name="environment_delete",
            description="Delete an environment by ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "env_id": {
                        "type": "string",
                        "description": "Environment identifier",
                    },
                },
                "required": ["env_id"],
            },
        ),
    )

    logger.info("Registered 5 environment CRUD tools")
