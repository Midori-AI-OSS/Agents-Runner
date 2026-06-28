"""CLI entry point for MCP server."""

from __future__ import annotations

import asyncio
import signal

from rich.console import Console

from midori_ai_logger import MidoriAiLogger

logger = MidoriAiLogger(channel=None, name=__name__)
logger.console = Console(stderr=True)


async def run_mcp_server() -> None:
    """Start and run the MCP server lifecycle.

    Assembles transport, server, registers all tool groups (task, artifact,
    environment, and optional GitHub tools), then runs the server event loop
    until a SIGINT or SIGTERM is received.
    """
    from agents_runner.mcp.server import MCPServer
    from agents_runner.mcp.transport import MCPTransport
    from agents_runner.mcp.tools import register_task_tools
    from agents_runner.mcp.tools_artifacts import register_artifact_tools
    from agents_runner.mcp.tools_environments import register_environment_tools

    transport = MCPTransport()
    server = MCPServer(transport)

    register_task_tools(server)
    register_artifact_tools(server)
    register_environment_tools(server)

    # GitHub tools are optional — wrap in try/except
    try:
        from agents_runner.mcp.tools_github import register_github_tools

        register_github_tools(server)
    except Exception:
        logger.info("GitHub tools not available — skipping registration")

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
