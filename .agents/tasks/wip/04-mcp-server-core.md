# 04 — MCP Server Core (Lifecycle + Tool Registry + Dispatch)

## What
Implement the core MCP server: protocol handshake (initialize), tool/resource registration, and the main JSON-RPC dispatch loop that routes method calls to registered handlers.

## Why
The server core is the central orchestrator that ties transport, types, and tools together. Every tool registration and every client request flows through this module.

## Where
- Write into: `agents_runner/mcp/server.py`

## Implementation details

### `MCPServer` class
- `__init__(self, transport: MCPTransport, server_name: str = "midori-ai-agents-runner", server_version: str = "0.1.0")`
- `tool_registry: dict[str, Callable]` — maps tool name → async handler function
- `resource_registry: dict[str, Callable]` — maps URI prefix → async handler
- `_capabilities: ServerCapabilities` — server capability advertisement

### Protocol lifecycle (entry point: `async def run()`)
1. Wait for `initialize` request → validate protocol version → respond with `InitializeResult` + capabilities
2. Wait for `notifications/initialized` notification → server is ready
3. Enter main dispatch loop: read messages, route to handlers, write responses

### JSON-RPC dispatch
- `async _dispatch(request: JsonRpcRequest) -> JsonRpcResponse | JsonRpcError`
- Route table:
  - `initialize` → `_handle_initialize`
  - `tools/list` → `_handle_list_tools`
  - `tools/call` → `_handle_tool_call` (lookup tool in registry, invoke)
  - `resources/list` → `_handle_list_resources`
  - `resources/read` → `_handle_read_resource`
  - `ping` → respond with empty `{}`
- Unknown methods → JSON-RPC MethodNotFound error (-32601)
- Invalid params → JSON-RPC InvalidParams error (-32602)
- Internal errors → JSON-RPC InternalError (-32603)

### Tool registration
- `register_tool(name: str, handler: Callable, definition: ToolDefinition) -> None`
- Stores handler in `tool_registry` and definition for `tools/list`

### Resource registration
- `register_resource(definition: ResourceDefinition, handler: Callable) -> None`

### Constraints
- Use `asyncio` for the event loop
- Use `from __future__ import annotations`
- Type hints throughout
- Do NOT import Qt / ui
- Use `midori_ai_logger` for logging
- No side effects at module import

## Dependencies
- Requires 01 (package scaffold), 02 (types), 03 (transport) to be completed first.

## Done Criteria
- `uv run ruff check agents_runner/mcp/server.py` passes.
- `uv run basedpyright` passes.
- Import smoke test: `uv run python -c "from agents_runner.mcp.server import MCPServer; print(type(MCPServer))"` exits 0 (do NOT pass None — use a proper MCPTransport instance from task 03).
- The server module must import from `agents_runner.mcp.types` and `agents_runner.mcp.transport` (the stubs from 01–03).
