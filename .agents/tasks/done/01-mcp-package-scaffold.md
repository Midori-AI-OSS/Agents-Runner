# 01 — MCP Package Scaffold

## What
Create the `agents_runner/mcp/` Python package with an `__init__.py` and stubs for the core submodules: `types.py`, `transport.py`, `server.py`, `tools.py`, `cli.py`.

## Why
MCP server support needs a clean subsystem package following the existing `agents_runner/` conventions (one package per subsystem, exposing a CLI entry function, no Qt imports).

## Where
- New: `agents_runner/mcp/__init__.py`
- New: `agents_runner/mcp/types.py` (stub — Pydantic models in 02)
- New: `agents_runner/mcp/transport.py` (stub — stdio transport in 03)
- New: `agents_runner/mcp/server.py` (stub — lifecycle/dispatch in 04)
- New: `agents_runner/mcp/tools.py` (stub — tool registration in 05–08)
- New: `agents_runner/mcp/cli.py` (stub — CLI entry function in 09)

## Done Criteria
- `agents_runner/mcp/__init__.py` exists.
- Each stub file imports `from __future__ import annotations` and has a module docstring.
- `uv run ruff check agents_runner/mcp/` passes (no errors).
- `uv run basedpyright` passes (no errors) on the new files.

## Completion
Completed 2026-06-26: Created `agents_runner/mcp/` package with 6 stub files (`__init__.py`, `types.py`, `transport.py`, `server.py`, `tools.py`, `cli.py`). All files have module docstrings and `from __future__ import annotations`. Ruff and basedpyright pass clean.
