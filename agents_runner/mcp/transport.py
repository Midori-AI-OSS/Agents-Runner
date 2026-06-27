"""Transport layer for MCP server communication using stdio with Content-Length framing."""

from __future__ import annotations

import asyncio
import json
import sys

from typing import Any

from rich.console import Console

from midori_ai_logger import MidoriAiLogger

logger = MidoriAiLogger(channel=None, name=__name__)
logger.console = Console(stderr=True)


class MCPTransport:
    """MCP stdio transport using Content-Length header framing (MCP spec).

    Reads JSON-RPC messages from stdin and writes JSON-RPC messages to stdout.
    Logs are directed to stderr to avoid mixing with the stdout transport.
    """

    def __init__(
        self,
        stdin: Any = None,
        stdout: Any = None,
        stderr: Any = None,
    ) -> None:
        """Initialize the transport with optional custom IO streams.

        Args:
            stdin: Binary input stream (defaults to sys.stdin.buffer).
            stdout: Binary output stream (defaults to sys.stdout.buffer).
            stderr: Binary error stream (defaults to sys.stderr).
        """
        self._stdin = stdin if stdin is not None else sys.stdin.buffer
        self._stdout = stdout if stdout is not None else sys.stdout.buffer
        self._stderr = stderr if stderr is not None else sys.stderr
        self._buffer = bytearray()
        self._closed = False

    async def _read_n_bytes(self, n: int) -> bytes:
        """Read exactly *n* bytes from stdin, buffering partial reads."""
        loop = asyncio.get_running_loop()
        while len(self._buffer) < n:
            bytes_needed = n - len(self._buffer)
            chunk = await loop.run_in_executor(None, self._stdin.read, bytes_needed)
            if not chunk:
                msg = "stdin closed while reading message body"
                raise ConnectionError(msg)
            self._buffer.extend(chunk)
        result = bytes(self._buffer[:n])
        del self._buffer[:n]
        return result

    async def _read_line(self) -> bytes:
        """Read one line (terminated by \\n) from stdin into the internal buffer."""
        loop = asyncio.get_running_loop()
        while b"\n" not in self._buffer:
            chunk = await loop.run_in_executor(None, self._stdin.read, 4096)
            if not chunk:
                msg = "stdin closed while reading line"
                raise ConnectionError(msg)
            self._buffer.extend(chunk)
        idx = self._buffer.index(b"\n") + 1
        result = bytes(self._buffer[:idx])
        del self._buffer[:idx]
        return result

    async def read_message(self) -> dict[str, Any]:
        """Read and parse one JSON-RPC message from stdin.

        Returns:
            The parsed JSON-RPC message as a dictionary.

        Raises:
            RuntimeError: If the transport has been closed.
            ConnectionError: If stdin is closed unexpectedly.
            ValueError: If the Content-Length header is missing or invalid.
        """
        if self._closed:
            msg = "Transport is closed"
            raise RuntimeError(msg)

        content_length = -1
        while True:
            line = await self._read_line()
            line_str = line.decode("utf-8", errors="replace").strip()
            if not line_str:
                break  # Empty line marks end of headers
            lower = line_str.lower()
            if lower.startswith("content-length:"):
                try:
                    raw_value = line_str.split(":", 1)[1].strip()
                    content_length = int(raw_value)
                except (ValueError, IndexError):
                    logger.error(f"Malformed Content-Length header: {line_str}")

        if content_length < 0:
            msg = "No Content-Length header found in MCP message"
            raise ValueError(msg)

        body = await self._read_n_bytes(content_length)

        try:
            return dict(json.loads(body))
        except json.JSONDecodeError as exc:
            logger.error(f"Failed to parse JSON-RPC message body: {exc}")
            raise

    async def write_message(self, message: dict[str, Any]) -> None:
        """Serialize and write one JSON-RPC message to stdout with framing.

        Args:
            message: The JSON-RPC message to write.

        Raises:
            RuntimeError: If the transport has been closed.
        """
        if self._closed:
            msg = "Transport is closed"
            raise RuntimeError(msg)

        body = json.dumps(message, ensure_ascii=False).encode("utf-8")
        header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._stdout.write, header + body)
        await loop.run_in_executor(None, self._stdout.flush)

    async def close(self) -> None:
        """Flush pending writes and mark the transport as closed."""
        if self._closed:
            return
        self._closed = True
        try:
            await asyncio.get_running_loop().run_in_executor(
                None,
                self._stdout.flush,
            )
        except Exception:
            pass
