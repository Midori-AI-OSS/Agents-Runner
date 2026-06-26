# 06 — MCP Log & Artifact Access Tools

## What
Implement MCP tools for accessing task logs and artifacts. Wire into the existing `agents_runner.artifacts` module and persistence (for logs stored in task payloads).

## Why
The feature request explicitly asks for log and artifact access through MCP. These are read-only informational tools.

## Where
- Write into: `agents_runner/mcp/tools.py` (append to the tools module) or a separate `agents_runner/mcp/tools_artifacts.py`

## Key imports (verified to exist)
```python
from agents_runner.persistence import default_state_path, load_task_payload
from agents_runner.artifacts import list_artifacts, list_staging_artifacts
from agents_runner.artifacts import decrypt_artifact, get_staging_artifact_path
```
Note: `load_task_payload(state_path, task_id, *, archived)` — the `archived` keyword is REQUIRED.
Note: `decrypt_artifact(task_dict, env_name, artifact_uuid, dest_path)` — `task_dict` needs at minimum `task_id` or `id` key.

### Tools to implement

#### `task_logs`
- **Input:** `task_id: str`, optional `limit: int` (default 100), optional `offset: int` (default 0)
- **Logic:**
  1. Try active first: `load_task_payload(default_state_path(), task_id, archived=False)`
  2. Fall back to done: `load_task_payload(default_state_path(), task_id, archived=True)`
  3. Extract `logs` field (list of strings; note: `serialize_task` stores only the last 2000 log entries)
  4. Return slice `logs[offset:offset+limit]`
- **Returns:** `{task_id, log_count: len(logs), logs: [...]}`

#### `artifact_list`
- **Input:** `task_id: str`
- **Logic:**
  1. Call `list_artifacts(task_id)` for encrypted/permanent artifacts — returns `list[ArtifactMeta]`
  2. Call `list_staging_artifacts(task_id)` for staging artifacts — returns `list[StagingArtifactMeta]`
  3. Merge and return both lists, serialized to dicts
- **Returns:** `{task_id, artifacts: [{uuid, original_filename, mime_type, size_bytes, encrypted_at}], staging: [{filename, size_bytes, modified_at, mime_type}]}`

#### `artifact_get`
- **Input:** `task_id: str`, `artifact_uuid: str`, optional `dest_path: str` (defaults to temp file)
- **Logic:**
  1. Create a temp path via `tempfile.mktemp()` if `dest_path` not provided
  2. Construct `task_dict` with at minimum `{"task_id": task_id}`
  3. Derive `env_name` from the task's `environment_id` field (load task payload first)
  4. Call `decrypt_artifact(task_dict, env_name, artifact_uuid, dest_path)` — returns `bool`
  5. Read the decrypted content from `dest_path`
  6. Return as text content (for text files) or indicate binary with base64 for non-text
- **Returns:** `{artifact_uuid, original_filename, mime_type, content, content_encoding: "text" | "base64"}`

#### `artifact_staging_get`
- **Input:** `task_id: str`, `filename: str`
- **Logic:**
  1. Call `get_staging_artifact_path(task_id, filename)` — returns `Path | None`
  2. If path exists, read the file content
  3. Return as text or base64 based on MIME type
- **Returns:** `{filename, mime_type, content, content_encoding: "text" | "base64"}`

### Constraints
- All handlers async, same pattern as 05
- Read-only operations (no modification)
- For binary files, auto-detect via mime type: if mime starts with `text/` or is `application/json`, use text; otherwise base64-encode
- Do NOT import Qt / ui
- Use `from __future__ import annotations`
- Use `midori_ai_logger` for logging

### Registration
- Export `register_artifact_tools(server: MCPServer) -> None`

## Dependencies
- Requires 01 (scaffold), 02 (types), 03 (transport), 04 (server core) completed first.
- Independent of task 05 (can be done in parallel with 05).

## Done Criteria
- `uv run ruff check` clean.
- `uv run basedpyright` clean.
- Import smoke test passes.
- grep confirms no Qt imports.
