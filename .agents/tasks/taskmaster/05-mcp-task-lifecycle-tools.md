# 05 — MCP Task Lifecycle Tools

## What
Implement MCP tools for task lifecycle: create, start, list, get status, and cancel tasks. These tools wire into the existing `agents_runner.persistence` module to read/write task payloads via TOML files.

## Why
This is the primary feature request — external agents and tools need to manage task lifecycles through MCP.

## Where
- Write into: `agents_runner/mcp/tools.py` (or a new `agents_runner/mcp/tools_tasks.py` if the file grows too large)

## Critical constraint: Do NOT import from `agents_runner.ui`
The MCP subsystem must remain headless. The `agents_runner.ui.task_model` module pulls in Qt. Instead, work with the task payload dicts directly through the persistence module. The `serialize_task`/`deserialize_task` functions operate on payload dicts; use those dicts as the internal representation. If you need a Task-like object for `serialize_task`, define a minimal `@dataclass` inside the MCP tools module (or just construct the payload dict manually matching the keys in `persistence.serialize_task`).

## Key imports (verified to exist)
```python
from agents_runner.persistence import default_state_path, serialize_task, deserialize_task
from agents_runner.persistence import save_task_payload, load_task_payload
from agents_runner.persistence import load_active_task_payloads, load_done_task_payloads
from agents_runner.environments.storage import load_environments  # returns dict[str, Environment]
```
Note: `load_environments()` returns `dict[str, Environment]` — look up environments by `env_id` as dict key.

### Tools to implement

#### `task_create`
- **Input:** `env_id: str`, `prompt: str`, optional `image: str`, optional `agent_cli: str`
- **Logic:**
  1. Look up `Environment` by `env_id` using `load_environments()` (returns `dict[str, Environment]`, use `env_id` as key)
  2. Generate a unique `task_id` (e.g. `uuid4().hex[:12]`)
  3. Build a task payload dict with keys matching `serialize_task()` output: `task_id`, `prompt`, `image`, `host_workdir` (from env), `environment_id`, `status="queued"`, `created_at_s`, `logs=[]`, `artifacts=[]`, plus defaults for all other fields
  4. Save via `save_task_payload(default_state_path(), payload, archived=False)`
- **Returns:** `{task_id, status: "queued"}`

#### `task_start`
- **Input:** `task_id: str`
- **Logic:**
  1. Load task: `load_task_payload(default_state_path(), task_id, archived=False)`
  2. If not found, try `archived=True` (task may already be done)
  3. Set `payload["status"] = "queued"` if not already active
  4. Save via `save_task_payload(default_state_path(), payload, archived=False)`
  5. Triggering actual Docker execution from the MCP server process is out of scope. Only update the task state. The actual runner is a separate concern.
- **Returns:** `{task_id, status}`

#### `task_list`
- **Input:** optional `status: str` filter, optional `limit: int` (default 20)
- **Logic:**
  1. Load active: `load_active_task_payloads(default_state_path())`
  2. Load done: `load_done_task_payloads(default_state_path(), offset=0, limit=limit)`
  3. Merge lists, optionally filter by `status` field
  4. Extract summary fields: `task_id`, `status`, `prompt` (first 80 chars), `created_at_s`, `exit_code`
- **Returns:** list of `{task_id, status, prompt_first_line, created_at, exit_code}`

#### `task_status`
- **Input:** `task_id: str`
- **Logic:**
  1. Load from active then done persistence (try `archived=False` first, then `archived=True`)
  2. Return full public fields: `status`, `exit_code`, `error`, `started_at`, `finished_at`, `container_id`, `gh_pr_url`, `artifacts` count (len), `logs` count (len)
- **Returns:** detailed status dict

#### `task_cancel`
- **Input:** `task_id: str`
- **Logic:**
  1. Load task: `load_task_payload(default_state_path(), task_id, archived=False)`
  2. If not found, raise error (already done/archived tasks cannot be cancelled)
  3. Set `payload["status"] = "cancelled"`
  4. Save: `save_task_payload(default_state_path(), payload, archived=False)`
- **Returns:** `{task_id, status: "cancelled"}`

### Constraints
- All handlers are `async def handler(params: dict[str, Any]) -> dict[str, Any]` (or raise)
- Use `from __future__ import annotations`
- Use `midori_ai_logger` for logging
- Do NOT import Qt / ui — this is the most critical constraint
- Use `default_state_path()` from persistence for the state file path
- All file I/O is sync TOML reads/writes — call directly (they are fast)

### Registration pattern
- Export a function `register_task_tools(server: MCPServer) -> None` that registers each tool with its handler and `ToolDefinition`

### Task payload key reference (from `persistence.serialize_task`)
Key fields: `task_id`, `prompt`, `image`, `host_workdir`, `host_config_dir`, `environment_id`, `created_at_s`, `status`, `exit_code`, `error`, `container_id`, `started_at`, `finished_at`, `workspace_type`, `gh_repo_root`, `gh_base_branch`, `gh_branch`, `gh_pr_url`, `agent_cli`, `agent_instance_id`, `agent_cli_args`, `launch_mode`, `logs`, `artifacts`, `attempt_history`, `finalization_state` (and more — see `serialize_task` in `persistence.py:345`).

## Dependencies
- Requires 01 (package scaffold), 02 (types), 03 (transport), 04 (server core) completed first.

## Done Criteria
- `uv run ruff check agents_runner/mcp/tools.py` passes.
- `uv run basedpyright` passes.
- Import smoke test: `uv run python -c "from agents_runner.mcp.tools import register_task_tools"` exits 0.
- grep confirms no Qt imports: `rg -l 'agents_runner.ui' agents_runner/mcp/tools.py` returns empty.
