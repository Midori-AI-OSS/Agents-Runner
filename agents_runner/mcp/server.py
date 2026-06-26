"""MCP server lifecycle and dispatch."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import ValidationError

from midori_ai_logger import MidoriAiLogger

from agents_runner.mcp.transport import MCPTransport
from agents_runner.mcp.types import (
    InitializeRequestParams,
    InitializeResult,
    JsonRpcError,
    JsonRpcErrorEntry,
    JsonRpcRequest,
    JsonRpcResponse,
    ListResourcesResult,
    ListToolsResult,
    ReadResourceParams,
    ReadResourceResult,
    ResourceDefinition,
    ServerCapabilities,
    ToolCallParams,
    ToolCallResult,
    ToolDefinition,
)

logger = MidoriAiLogger(channel=None, name=__name__)


class MCPServer:
    """MCP server that manages protocol lifecycle, tool/resource registries, and JSON-RPC dispatch.

    The server follows the MCP initialization sequence (initialize request,
    initialized notification) then enters a main loop reading JSON-RPC messages
    from the transport, dispatching them to registered handlers, and writing
    responses back.
    """

    def __init__(
        self,
        transport: MCPTransport,
        server_name: str = "midori-ai-agents-runner",
        server_version: str = "0.1.0",
    ) -> None:
        """Initialise the MCP server.

        Args:
            transport: The transport layer used for message I/O.
            server_name: Human-readable server name advertised during handshake.
            server_version: Server version advertised during handshake.
        """
        self._transport = transport
        self._server_name = server_name
        self._server_version = server_version
        self._initialized = False
        self._closed = False

        # Registries (public for runtime inspection / extension).
        self.tool_registry: dict[str, Callable[..., Any]] = {}
        self.resource_registry: dict[str, Callable[..., Any]] = {}

        # Server capability advertisement.
        self._capabilities = ServerCapabilities(
            tools={"listChanged": False},
            resources={"listChanged": False},
        )

        # Internal stores for definitions returned via list methods.
        self._tool_definitions: dict[str, ToolDefinition] = {}
        self._resource_definitions: dict[str, ResourceDefinition] = {}

    # ── Registration ─────────────────────────────────────────────────────────

    def register_tool(self, name: str, handler: Callable[..., Any], definition: ToolDefinition) -> None:
        """Register a tool handler with the server.

        Args:
            name: The tool name (used by clients in ``tools/call``).
            handler: An async callable that receives keyword arguments and
                returns a ``ToolCallResult`` (or a dict).
            definition: A ``ToolDefinition`` describing the tool's schema.
        """
        self.tool_registry[name] = handler
        self._tool_definitions[name] = definition

    def register_resource(self, definition: ResourceDefinition, handler: Callable[..., Any]) -> None:
        """Register a resource handler with the server.

        The handler is matched by URI prefix (longest prefix wins).

        Args:
            definition: A ``ResourceDefinition`` describing the resource.
            handler: An async callable that receives ``(uri: str)`` and
                returns a ``ReadResourceResult`` (or a dict).
        """
        self.resource_registry[definition.uri] = handler
        self._resource_definitions[definition.uri] = definition

    # ── Lifecycle ────────────────────────────────────────────────────────────

    async def run(self) -> None:
        """Run the MCP server lifecycle.

        Phases:
        1. Read the ``initialize`` request, validate, respond with
           ``InitializeResult`` + capabilities.
        2. Read the ``notifications/initialized`` notification.
        3. Enter the main dispatch loop – read messages, route to handlers,
           write responses.

        The method returns when the transport raises ``ConnectionError``
        (client disconnect) or any unrecoverable error occurs.
        """
        try:
            # Phase 1: Initialize
            msg = await self._transport.read_message()
            request = JsonRpcRequest(**msg)
            response = await self._dispatch(request)
            await self._transport.write_message(response.model_dump())

            # Phase 2: Initialized notification
            msg = await self._transport.read_message()
            if msg.get("method") == "notifications/initialized" and "id" not in msg:
                self._initialized = True
            elif "id" in msg:
                # The peer sent a request before sending the expected notification
                request = JsonRpcRequest(**msg)
                response = await self._dispatch(request)
                await self._transport.write_message(response.model_dump())

            # Phase 3: Main dispatch loop
            while not self._closed:
                msg = await self._transport.read_message()
                if "id" not in msg:
                    self._handle_notification(msg)
                    continue
                request = JsonRpcRequest(**msg)
                response = await self._dispatch(request)
                await self._transport.write_message(response.model_dump())

        except ConnectionError:
            logger.info("MCP server: client disconnected")
        except Exception:
            logger.exception("MCP server encountered an unrecoverable error")
        finally:
            await self._transport.close()
            self._closed = True

    def _handle_notification(self, msg: dict[str, Any]) -> None:
        """Process an incoming JSON-RPC notification (no ``id`` field)."""
        method = msg.get("method", "")
        if method == "notifications/initialized":
            self._initialized = True

    # ── Dispatch ─────────────────────────────────────────────────────────────

    async def _dispatch(self, request: JsonRpcRequest) -> JsonRpcResponse | JsonRpcError:
        """Route a JSON-RPC request to the appropriate handler.

        Args:
            request: The parsed JSON-RPC request.

        Returns:
            A ``JsonRpcResponse`` on success or a ``JsonRpcError`` on failure.
        """
        try:
            if request.method == "initialize":
                return await self._handle_initialize(request)
            if request.method == "tools/list":
                return await self._handle_list_tools(request)
            if request.method == "tools/call":
                return await self._handle_tool_call(request)
            if request.method == "resources/list":
                return await self._handle_list_resources(request)
            if request.method == "resources/read":
                return await self._handle_read_resource(request)
            if request.method == "ping":
                return JsonRpcResponse(id=request.id, result={})
            return JsonRpcError(
                id=request.id,
                error=JsonRpcErrorEntry(code=-32601, message="Method not found"),
            )
        except ValidationError as exc:
            return JsonRpcError(
                id=request.id,
                error=JsonRpcErrorEntry(
                    code=-32602,
                    message=f"Invalid params: {exc}",
                ),
            )
        except Exception as exc:
            logger.exception(f"Error handling method '{request.method}'")
            return JsonRpcError(
                id=request.id,
                error=JsonRpcErrorEntry(
                    code=-32603,
                    message=f"Internal error: {exc}",
                ),
            )

    # ── Handler implementations ──────────────────────────────────────────────

    async def _handle_initialize(self, request: JsonRpcRequest) -> JsonRpcResponse | JsonRpcError:
        """Handle the ``initialize`` lifecycle request."""
        if request.params is None:
            return JsonRpcError(
                id=request.id,
                error=JsonRpcErrorEntry(
                    code=-32602,
                    message="Invalid params: initialize requires params",
                ),
            )
        params = InitializeRequestParams(**request.params)
        result = InitializeResult(
            protocolVersion=params.protocolVersion,
            capabilities=self._capabilities,
            serverInfo={
                "name": self._server_name,
                "version": self._server_version,
            },
        )
        return JsonRpcResponse(id=request.id, result=result.model_dump())

    async def _handle_list_tools(self, request: JsonRpcRequest) -> JsonRpcResponse:
        """Handle the ``tools/list`` request."""
        result = ListToolsResult(tools=list(self._tool_definitions.values()))
        return JsonRpcResponse(id=request.id, result=result.model_dump())

    async def _handle_tool_call(self, request: JsonRpcRequest) -> JsonRpcResponse | JsonRpcError:
        """Handle the ``tools/call`` request."""
        if request.params is None:
            return JsonRpcError(
                id=request.id,
                error=JsonRpcErrorEntry(
                    code=-32602,
                    message="Invalid params: tool name required",
                ),
            )
        params = ToolCallParams(**request.params)
        handler = self.tool_registry.get(params.name)
        if handler is None:
            return JsonRpcError(
                id=request.id,
                error=JsonRpcErrorEntry(
                    code=-32602,
                    message=f"Unknown tool: {params.name}",
                ),
            )
        arguments = params.arguments or {}
        raw = await handler(**arguments)
        if isinstance(raw, ToolCallResult):
            return JsonRpcResponse(id=request.id, result=raw.model_dump())
        return JsonRpcResponse(id=request.id, result=raw)

    async def _handle_list_resources(self, request: JsonRpcRequest) -> JsonRpcResponse:
        """Handle the ``resources/list`` request."""
        result = ListResourcesResult(
            resources=list(self._resource_definitions.values()),
        )
        return JsonRpcResponse(id=request.id, result=result.model_dump())

    async def _handle_read_resource(self, request: JsonRpcRequest) -> JsonRpcResponse | JsonRpcError:
        """Handle the ``resources/read`` request.

        Resource lookup uses longest-prefix matching against registered URIs.
        """
        if request.params is None:
            return JsonRpcError(
                id=request.id,
                error=JsonRpcErrorEntry(
                    code=-32602,
                    message="Invalid params: URI required",
                ),
            )
        params = ReadResourceParams(**request.params)

        # Longest-prefix match against registered resource URIs
        handler: Callable[..., Any] | None = None
        matched_prefix = ""
        for uri_prefix in self.resource_registry:
            if params.uri.startswith(uri_prefix) and len(uri_prefix) > len(matched_prefix):
                handler = self.resource_registry[uri_prefix]
                matched_prefix = uri_prefix

        if handler is None:
            return JsonRpcError(
                id=request.id,
                error=JsonRpcErrorEntry(
                    code=-32602,
                    message=f"Unknown resource: {params.uri}",
                ),
            )
        raw = await handler(params.uri)
        if isinstance(raw, ReadResourceResult):
            return JsonRpcResponse(id=request.id, result=raw.model_dump())
        return JsonRpcResponse(id=request.id, result=raw)
