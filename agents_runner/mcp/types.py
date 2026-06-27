"""Pydantic models for the Model Context Protocol (MCP) JSON-RPC 2.0 messaging layer."""

from __future__ import annotations

from typing import Any, Literal, Union

from pydantic import BaseModel, ConfigDict


# ── JSON-RPC 2.0 primitives ──────────────────────────────────────────────────


class JsonRpcErrorEntry(BaseModel):
    """Error object per JSON-RPC 2.0 specification (code, message, optional data)."""

    model_config = ConfigDict(extra="forbid")

    code: int
    message: str
    data: Any = None


class JsonRpcRequest(BaseModel):
    """JSON-RPC 2.0 request object."""

    model_config = ConfigDict(extra="forbid")

    jsonrpc: str = "2.0"
    id: str | int
    method: str
    params: dict[str, Any] | None = None


class JsonRpcResponse(BaseModel):
    """JSON-RPC 2.0 success response object."""

    model_config = ConfigDict(extra="forbid")

    jsonrpc: str = "2.0"
    id: str | int
    result: Any = None


class JsonRpcError(BaseModel):
    """JSON-RPC 2.0 error response object."""

    model_config = ConfigDict(extra="forbid")

    jsonrpc: str = "2.0"
    id: str | int
    error: JsonRpcErrorEntry


class JsonRpcNotification(BaseModel):
    """JSON-RPC 2.0 notification object (no id)."""

    model_config = ConfigDict(extra="forbid")

    jsonrpc: str = "2.0"
    method: str
    params: dict[str, Any] | None = None


# ── MCP lifecycle messages ──────────────────────────────────────────────────


class InitializeRequestParams(BaseModel):
    """Parameters for the initialize request lifecycle message."""

    model_config = ConfigDict(extra="forbid")

    protocolVersion: str
    capabilities: dict[str, Any]
    clientInfo: dict[str, Any]


class ServerCapabilities(BaseModel):
    """Server capabilities advertised during initialization."""

    model_config = ConfigDict(extra="forbid")

    tools: dict[str, Any] | None = None
    resources: dict[str, Any] | None = None
    prompts: dict[str, Any] | None = None


class InitializeResult(BaseModel):
    """Result payload for the initialize response."""

    model_config = ConfigDict(extra="forbid")

    protocolVersion: str
    capabilities: ServerCapabilities
    serverInfo: dict[str, Any]
    instructions: str | None = None


class InitializedNotification(BaseModel):
    """Empty marker for the initialized notification."""

    model_config = ConfigDict(extra="forbid")


# ── MCP tool-related types ──────────────────────────────────────────────────


class ToolDefinition(BaseModel):
    """Definition of a tool exposed by the server."""

    model_config = ConfigDict(extra="forbid")

    name: str
    description: str
    inputSchema: dict[str, Any]


class ListToolsResult(BaseModel):
    """Result payload for tools/list."""

    model_config = ConfigDict(extra="forbid")

    tools: list[ToolDefinition]


class ToolCallParams(BaseModel):
    """Parameters for a tools/call request."""

    model_config = ConfigDict(extra="forbid")

    name: str
    arguments: dict[str, Any] | None = None


class TextContent(BaseModel):
    """Text content part in a tool call result."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["text"] = "text"
    text: str


class ImageContent(BaseModel):
    """Image content part in a tool call result."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["image"] = "image"
    data: str
    mimeType: str


class EmbeddedResource(BaseModel):
    """Embedded resource content part in a tool call result."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["resource"] = "resource"
    resource: dict[str, Any]


class ToolCallResult(BaseModel):
    """Result payload for a tools/call response."""

    model_config = ConfigDict(extra="forbid")

    content: list[TextContent | ImageContent | EmbeddedResource]
    isError: bool | None = None


# ── MCP resource types ──────────────────────────────────────────────────────


class ResourceDefinition(BaseModel):
    """Definition of a resource exposed by the server."""

    model_config = ConfigDict(extra="forbid")

    uri: str
    name: str
    description: str
    mimeType: str


class ListResourcesResult(BaseModel):
    """Result payload for resources/list."""

    model_config = ConfigDict(extra="forbid")

    resources: list[ResourceDefinition]


class ReadResourceParams(BaseModel):
    """Parameters for a resources/read request."""

    model_config = ConfigDict(extra="forbid")

    uri: str


class TextResourceContent(BaseModel):
    """Text content of a resource."""

    model_config = ConfigDict(extra="forbid")

    uri: str
    mimeType: str
    text: str


class ReadResourceResult(BaseModel):
    """Result payload for a resources/read response."""

    model_config = ConfigDict(extra="forbid")

    contents: list[TextResourceContent]


# ── Top-level message union ─────────────────────────────────────────────────


MCPMessage = Union[
    JsonRpcRequest,
    JsonRpcResponse,
    JsonRpcError,
    JsonRpcNotification,
]
