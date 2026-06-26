# 07 — MCP Environment Management Tools

## What
Implement MCP tools for environment CRUD: list, get, create, update, delete. Wire into the existing `agents_runner.environments` subsystem.

## Why
The feature request calls for environment management operations through MCP. This lets external automation configure agent environments.

## Where
- Write into: `agents_runner/mcp/tools.py` (append) or `agents_runner/mcp/tools_environments.py`

## Key imports (verified to exist)
```python
from agents_runner.environments.model import Environment  # @dataclass, not Pydantic
from agents_runner.environments.serialize import serialize_environment, environment_from_payload
from agents_runner.environments.storage import load_environments, save_environment, delete_environment
```
Note: `load_environments()` returns `dict[str, Environment]` keyed by `env_id`.

### Tools to implement

#### `environment_list`
- **Input:** none
- **Logic:**
  1. Call `load_environments()` (no arg, uses default data dir)
  2. Extract summary from each `Environment`: `env_id`, `name`, `color`, `workspace_type`
  3. `agent_count`: if `env.agent_selection` is not None, `len(env.agent_selection.agents)`, else 0
- **Returns:** `{environments: [{env_id, name, color, workspace_type, agent_count}]}`

#### `environment_get`
- **Input:** `env_id: str`
- **Logic:**
  1. Load all environments, look up by `env_id` as dict key
  2. If not found, raise JSON-RPC InvalidParams error
  3. Serialize full environment: `serialize_environment(env)` — returns `dict[str, Any]`
- **Returns:** full serialized environment dict (all fields)

#### `environment_create`
- **Input:** `env_id: str`, `name: str`, optional: `color`, `host_workdir`, `workspace_type`, `gpu_override_mode`, `network_host_override_mode`, `headless_desktop_enabled`, `env_vars`, `extra_mounts`, `ports`, and any other `Environment` dataclass field
- **Logic:**
  1. Construct `Environment(env_id=env_id, name=name, color=color or "emerald", host_workdir=host_workdir or "", workspace_type=workspace_type or "none", ...)` with only the provided fields (all Environment fields have defaults except `env_id` and `name`)
  2. Call `save_environment(env)`
- **Returns:** `{env_id, name, status: "created"}`
- **Important:** `Environment` is a `@dataclass` (NOT Pydantic). All fields except `env_id` and `name` have defaults. See `agents_runner/environments/model.py:222` for the full field list.

#### `environment_update`
- **Input:** `env_id: str`, plus any optional fields to override (name, color, host_workdir, workspace_type, workspace_target, agent_cli_args, headless_desktop_enabled, etc.)
- **Logic:**
  1. Load existing environment by env_id from `load_environments()`
  2. Apply non-None overrides to the Environment dataclass fields using `dataclasses.replace(env, **overrides)`
  3. Save via `save_environment()`
- **Returns:** `{env_id, name, status: "updated"}`

#### `environment_delete`
- **Input:** `env_id: str`
- **Logic:**
  1. Call `delete_environment(env_id)`
  2. Confirm deletion
- **Returns:** `{env_id, status: "deleted"}`

### Constraints
- All handlers async
- Environment is a `@dataclass`, not Pydantic — use `dataclasses.replace()` for partial updates
- Do NOT import Qt / ui
- The `load_environments()` call is synchronous; it reads a JSON file and returns immediately
- Use `from __future__ import annotations`
- Use `midori_ai_logger` for logging

### Registration
- Export `register_environment_tools(server: MCPServer) -> None`

## Dependencies
- Requires 01 (scaffold), 02 (types), 03 (transport), 04 (server core) completed first.
- Independent of tasks 05 and 06 (can be done in parallel).

## Done Criteria
- `uv run ruff check` clean.
- `uv run basedpyright` clean.
- Import smoke test passes.
- grep confirms no Qt imports.
