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
    from agents_runner.mcp.worker_tracker import get_worker_tracker

    transport = MCPTransport()
    server = MCPServer(transport)
    worker_tracker = get_worker_tracker()

    register_task_tools(server, worker_tracker=worker_tracker)
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

    # Run server until signalled or until the MCP transport closes.
    server_task = asyncio.create_task(server.run())
    stop_task = asyncio.create_task(stop_event.wait())
    try:
        done, pending = await asyncio.wait({server_task, stop_task}, return_when=asyncio.FIRST_COMPLETED)
        if stop_task in done and not server_task.done():
            server_task.cancel()
        for task in pending:
            task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            pass
    finally:
        stop_task.cancel()
        worker_tracker.cancel_all()
        worker_tracker.shutdown(wait=False)
