# 03 — MCP Transport Layer (stdio)

## What
Implement the stdio transport for MCP: read JSON-RPC messages from stdin, write JSON-RPC messages to stdout, using the Content-Length header framing required by the MCP specification. This is headless — no Qt, no UI.

## Why
MCP clients (Claude Desktop, Codex, etc.) communicate with servers via stdio. The transport layer must correctly frame/unframe messages so the server core can dispatch them.

## Where
- Write into: `agents_runner/mcp/transport.py`

## Implementation details

### Message format (MCP spec)
- Read: parse `Content-Length: <N>\r\n\r\n<json-body>` from stdin
- Write: emit `Content-Length: <N>\r\n\r\n<json-body>` to stdout
- Logs/stderr go to stderr (do not mix with stdout transport)

### Classes/functions
- `MCPTransport` class (context manager or async context manager):
  - `__init__(self, stdin=None, stdout=None, stderr=None)` — defaults to `sys.stdin.buffer`, `sys.stdout.buffer`, `sys.stderr`
  - `async read_message() -> dict[str, Any]` — read one JSON-RPC message, return parsed dict
  - `async write_message(message: dict[str, Any]) -> None` — serialize and write one JSON-RPC message with framing
  - `async close() -> None` — flush and cleanup
- Helper `_read_n_bytes(n: int) -> bytes` for reading exact byte counts
- Handle partial reads (stdin may deliver data in chunks)
- Handle parse errors gracefully (log to stderr, skip malformed frames where possible)

### Constraints
- Use `asyncio` for async I/O (the server runs an event loop)
- Use `from __future__ import annotations`
- Type hints throughout
- Do NOT import Qt / ui
- Use `midori_ai_logger` for logging (to stderr): `from midori_ai_logger import MidoriAiLogger`
- No side effects at module import (logger can be module-level constant)

## Done Criteria
- `uv run ruff check agents_runner/mcp/transport.py` passes.
- `uv run basedpyright` passes.
- Manual smoke check: `uv run python -c "from agents_runner.mcp.transport import MCPTransport; t = MCPTransport(); print(type(t))"` exits 0.
