# 02 — MCP Protocol Types (Pydantic Models)

## What
Define Pydantic models for the Model Context Protocol (MCP) JSON-RPC 2.0 messaging layer and core protocol types. These are headless data models only — no transport or server logic.

## Why
All inter-subsystem data must use Pydantic models per AGENTS.md convention. These types are the foundation every MCP tool and handler will build on.

## Where
- Write into: `agents_runner/mcp/types.py`

## Models to define

### JSON-RPC 2.0 primitives
- `JsonRpcRequest` — `jsonrpc`, `id`, `method`, `params` (optional dict)
- `JsonRpcResponse` — `jsonrpc`, `id`, `result` (optional Any)
- `JsonRpcError`  — `jsonrpc`, `id`, `error` with `code: int`, `message: str`, `data` (optional)
- `JsonRpcNotification` — `jsonrpc`, `method`, `params` (optional dict)

### MCP lifecycle messages
- `InitializeRequestParams` — `protocolVersion`, `capabilities`, `clientInfo`
- `InitializeResult` — `protocolVersion`, `capabilities` (server), `serverInfo`, optional `instructions`
- `ServerCapabilities` — `tools` (dict with optional `listChanged` bool), `resources` (optional), `prompts` (optional)
- `InitializedNotification` — empty params marker

### MCP tool-related types
- `ToolDefinition` — `name`, `description`, `inputSchema` (JSON Schema dict)
- `ListToolsResult` — `tools: list[ToolDefinition]`
- `ToolCallParams` — `name`, `arguments` (optional dict)
- `ToolCallResult` — `content: list[TextContent | ImageContent | EmbeddedResource]`, optional `isError`
- `TextContent` — `type: "text"`, `text: str`
- `ImageContent` — `type: "image"`, `data: str`, `mimeType: str`
- `EmbeddedResource` — `type: "resource"`, `resource` (dict)

### MCP resource types
- `ResourceDefinition` — `uri`, `name`, `description`, `mimeType`
- `ListResourcesResult` — `resources: list[ResourceDefinition]`
- `ReadResourceParams` — `uri`
- `ReadResourceResult` — `contents: list[TextResourceContent]`
- `TextResourceContent` — `uri`, `mimeType`, `text`

### Top-level union
- `MCPMessage` — discriminated union of request / response / error / notification

## Constraints
- Use `from pydantic import BaseModel, Field`
- Use `from __future__ import annotations`
- All fields must have type hints
- Use `ConfigDict(populate_by_name=True)` where param names differ from Python conventions
- Do NOT import Qt / ui. No side effects (no file I/O, no subprocess, no logger init at module scope).

## Done Criteria
- `uv run ruff check agents_runner/mcp/types.py` passes.
- `uv run basedpyright` passes (strict mode).
- All models instantiate without error: `uv run python -c "from agents_runner.mcp.types import JsonRpcRequest, ToolDefinition, ListToolsResult; assert isinstance(ToolDefinition(name='t', description='', inputSchema={}), ToolDefinition)"` exits 0.
