"""MCP tool handlers for task log and artifact access."""

from __future__ import annotations

import base64
import json
import mimetypes
import os
import tempfile
from pathlib import Path
from typing import Any, cast

from rich.console import Console

from midori_ai_logger import MidoriAiLogger

from agents_runner.artifacts import (
    decrypt_artifact,
    get_staging_artifact_path,
    list_artifacts,
    list_staging_artifacts,
)
from agents_runner.mcp.server import MCPServer
from agents_runner.mcp.types import TextContent, ToolCallResult, ToolDefinition
from agents_runner.persistence import default_state_path, load_task_payload

logger = MidoriAiLogger(channel=None, name=__name__)
logger.console = Console(stderr=True)


# ── Helpers ────────────────────────────────────────────────────────────────────


def _detect_content_encoding(mime_type: str) -> str:
    """Determine content encoding from a MIME type.

    Returns ``"text"`` for text-based types, ``"base64"`` for binary types.
    """
    mt = mime_type.lower().strip()
    if mt.startswith("text/") or mt == "application/json":
        return "text"
    return "base64"


# ── Handlers ──────────────────────────────────────────────────────────────────


async def handle_task_logs(
    task_id: str,
    limit: int = 100,
    offset: int = 0,
) -> ToolCallResult:
    """Retrieve log entries for a task (active first, then archived)."""
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

    logs_raw: Any = payload.get("logs")
    if not isinstance(logs_raw, list):
        logs_raw = []
    log_entries: list[str] = cast("list[str]", logs_raw)

    sliced = log_entries[offset : offset + limit]

    return ToolCallResult(
        content=[
            TextContent(
                text=json.dumps(
                    {
                        "task_id": task_id,
                        "log_count": len(sliced),
                        "logs": sliced,
                    },
                ),
            ),
        ],
    )


async def handle_artifact_list(task_id: str) -> ToolCallResult:
    """List all artifacts (encrypted permanent + staging) for a task."""
    artifacts = list_artifacts(task_id)
    staging = list_staging_artifacts(task_id)

    return ToolCallResult(
        content=[
            TextContent(
                text=json.dumps(
                    {
                        "task_id": task_id,
                        "artifacts": [
                            {
                                "uuid": a.uuid,
                                "original_filename": a.original_filename,
                                "mime_type": a.mime_type,
                                "size_bytes": a.size_bytes,
                                "encrypted_at": a.encrypted_at,
                            }
                            for a in artifacts
                        ],
                        "staging": [
                            {
                                "filename": s.filename,
                                "size_bytes": s.size_bytes,
                                "modified_at": s.modified_at.isoformat(),
                                "mime_type": s.mime_type,
                            }
                            for s in staging
                        ],
                    },
                ),
            ),
        ],
    )


async def handle_artifact_get(
    task_id: str,
    artifact_uuid: str,
    dest_path: str | None = None,
) -> ToolCallResult:
    """Decrypt and retrieve an encrypted artifact for a task."""
    # Load task payload to derive env_name
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

    env_name: str = str(payload.get("environment_id") or "")

    if not dest_path:
        fd, dest_path = tempfile.mkstemp()
        os.close(fd)

    task_dict: dict[str, Any] = {"task_id": task_id}

    success = decrypt_artifact(task_dict, env_name, artifact_uuid, dest_path)
    if not success:
        error_msg = f"Failed to decrypt artifact '{artifact_uuid}' for task '{task_id}'"
        logger.error(error_msg)
        return ToolCallResult(
            content=[TextContent(text=json.dumps({"error": error_msg}))],
            isError=True,
        )

    # Look up artifact metadata for filename and mime type
    meta_list = list_artifacts(task_id)
    artifact_meta = next((a for a in meta_list if a.uuid == artifact_uuid), None)

    original_filename: str = artifact_meta.original_filename if artifact_meta else artifact_uuid
    mime_type: str = artifact_meta.mime_type if artifact_meta else "application/octet-stream"

    # Read decrypted content
    content_bytes = Path(dest_path).read_bytes()

    content_encoding = _detect_content_encoding(mime_type)
    if content_encoding == "text":
        content = content_bytes.decode("utf-8", errors="replace")
    else:
        content = base64.b64encode(content_bytes).decode("ascii")

    return ToolCallResult(
        content=[
            TextContent(
                text=json.dumps(
                    {
                        "artifact_uuid": artifact_uuid,
                        "original_filename": original_filename,
                        "mime_type": mime_type,
                        "content": content,
                        "content_encoding": content_encoding,
                    },
                ),
            ),
        ],
    )


async def handle_artifact_staging_get(task_id: str, filename: str) -> ToolCallResult:
    """Retrieve a staging (unencrypted) artifact for a task."""
    path = get_staging_artifact_path(task_id, filename)
    if path is None:
        error_msg = f"Staging artifact '{filename}' not found for task '{task_id}'"
        logger.error(error_msg)
        return ToolCallResult(
            content=[TextContent(text=json.dumps({"error": error_msg}))],
            isError=True,
        )

    content_bytes = path.read_bytes()

    mime_type, _ = mimetypes.guess_type(filename)
    if mime_type is None:
        mime_type = "application/octet-stream"

    content_encoding = _detect_content_encoding(mime_type)
    if content_encoding == "text":
        content = content_bytes.decode("utf-8", errors="replace")
    else:
        content = base64.b64encode(content_bytes).decode("ascii")

    return ToolCallResult(
        content=[
            TextContent(
                text=json.dumps(
                    {
                        "filename": filename,
                        "mime_type": mime_type,
                        "content": content,
                        "content_encoding": content_encoding,
                    },
                ),
            ),
        ],
    )


# ── Registration ──────────────────────────────────────────────────────────────


def register_artifact_tools(server: MCPServer) -> None:
    """Register all artifact and log access tools with an MCP server instance.

    Args:
        server: An ``MCPServer`` instance.
    """
    server.register_tool(
        "task_logs",
        handle_task_logs,
        ToolDefinition(
            name="task_logs",
            description="Retrieve log entries for a task. Searches active then archived storage.",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "Task identifier",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum log entries to return (default 100)",
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Number of log entries to skip (default 0)",
                    },
                },
                "required": ["task_id"],
            },
        ),
    )

    server.register_tool(
        "artifact_list",
        handle_artifact_list,
        ToolDefinition(
            name="artifact_list",
            description="List all artifacts (encrypted permanent and staging) for a task.",
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
        "artifact_get",
        handle_artifact_get,
        ToolDefinition(
            name="artifact_get",
            description="Decrypt and retrieve an encrypted artifact for a task.",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "Task identifier",
                    },
                    "artifact_uuid": {
                        "type": "string",
                        "description": "UUID of the artifact to retrieve",
                    },
                    "dest_path": {
                        "type": "string",
                        "description": "Override destination path for decrypted file (optional)",
                    },
                },
                "required": ["task_id", "artifact_uuid"],
            },
        ),
    )

    server.register_tool(
        "artifact_staging_get",
        handle_artifact_staging_get,
        ToolDefinition(
            name="artifact_staging_get",
            description="Retrieve a staging (unencrypted) artifact for a task.",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "Task identifier",
                    },
                    "filename": {
                        "type": "string",
                        "description": "Artifact filename relative to staging directory",
                    },
                },
                "required": ["task_id", "filename"],
            },
        ),
    )

    logger.info("Registered 4 artifact/log access tools")
