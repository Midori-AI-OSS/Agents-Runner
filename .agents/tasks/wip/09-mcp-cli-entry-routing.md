# 09 — MCP CLI Entry Point + main.py Routing

## What
Wire up the MCP server as a runnable CLI mode. Add a `--mcp-server` argument handling to `agents_runner/cli.py` (where the `main()` function lives) and create the entry function in `agents_runner/mcp/cli.py` that assembles transport, server, registers all tools, and starts the async event loop.

## Why
Every subsystem must expose a CLI entry function routed from `main.py`. The MCP server must be startable via `uv run main.py --mcp-server` without importing Qt.

## File anatomy
- `main.py` (5 lines): thin dispatcher — `from agents_runner.cli import main; main()`. Do NOT modify `main.py`; it already routes everything through `cli.main()`.
- `agents_runner/cli.py`: the real `main()` function. The `--desktop-viewer` flag is already checked here before Qt imports (line 85). Add `--mcp-server` check in the same pattern.
- `agents_runner/mcp/cli.py`: stub from task 01. Implement `run_mcp_server()` here.

## Where
- Modify: `agents_runner/cli.py` — add `--mcp-server` argument routing BEFORE any Qt imports (before the `from agents_runner.ui.runtime.app import run_app` import at line 93)
- Modify: `agents_runner/mcp/cli.py` — implement `run_mcp_server()` entry function
- May update: `agents_runner/mcp/__init__.py` — optionally re-export `run_mcp_server`
- Do NOT modify: `main.py` (already a correct thin dispatcher)

### `agents_runner/cli.py` modification
In the `main()` function, BEFORE the Qt import block (before line 93 `from agents_runner.ui.runtime.app import run_app`), add:
```python
if len(sys.argv) > 1 and sys.argv[1] == "--mcp-server":
    import asyncio
    from agents_runner.mcp.cli import run_mcp_server
    try:
        asyncio.run(run_mcp_server())
    except KeyboardInterrupt:
        pass
    return
```
Follow the same pattern as the existing `--desktop-viewer` check at line 85.

### `agents_runner/mcp/cli.py` implementation
```python
"""MCP server CLI entry point."""

from __future__ import annotations

import asyncio
import signal


async def run_mcp_server() -> None:
    from agents_runner.mcp.server import MCPServer
    from agents_runner.mcp.transport import MCPTransport
    from agents_runner.mcp.tools import register_artifact_tools
    from agents_runner.mcp.tools import register_environment_tools
    from agents_runner.mcp.tools import register_task_tools

    transport = MCPTransport()
    server = MCPServer(transport)

    register_task_tools(server)
    register_artifact_tools(server)
    register_environment_tools(server)

    # GitHub tools are optional — wrap in try/except
    try:
        from agents_runner.mcp.tools import register_github_tools  # or tools_github
        register_github_tools(server)
    except Exception:
        pass

    # Set up graceful shutdown on SIGINT/SIGTERM
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _signal_handler() -> None:
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _signal_handler)
        except NotImplementedError:
            pass  # Windows doesn't support add_signal_handler

    # Run server until signalled
    server_task = asyncio.create_task(server.run())
    await stop_event.wait()
    server_task.cancel()
    try:
        await server_task
    except asyncio.CancelledError:
        pass
```

### Constraints
- The `--mcp-server` check must happen **before** any Qt imports or PySide6 initialization
- The MCP server runs in an asyncio event loop on the main thread
- Must handle graceful shutdown on SIGINT/SIGTERM
- Do NOT import Qt in any MCP module (verified by `rg -l 'agents_runner.ui' agents_runner/mcp/`)
- Use `from __future__ import annotations`
- Use `midori_ai_logger` for logging in `cli.py`

### Graceful shutdown
- Use `asyncio` signal handlers for `SIGINT` and `SIGTERM`
- On signal, cancel the server's main task and await cleanup

## Dependencies
- Requires ALL tasks 01-08 to be completed first (this is the final integration task).
- Tasks 05-07 can be done in parallel with each other, but all must be done before 09.

## Done Criteria
- The `--mcp-server` flag routes to the MCP server without importing Qt: `uv run python -c "import sys; sys.argv = ['main.py', '--mcp-server']; from agents_runner.cli import main; main()"` starts the MCP server (and blocks until signal)
- Pipe test: `echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}' | timeout 5 uv run main.py --mcp-server || true` should produce a valid `InitializeResult` JSON-RPC response on stdout (allow exit code from timeout)
- `uv run ruff check agents_runner/cli.py agents_runner/mcp/cli.py` passes.
- `uv run basedpyright` passes.
- The MCP modules (`mcp/`) never import from `agents_runner.ui` (verify with `rg -l 'agents_runner.ui' agents_runner/mcp/` returns empty).
