# Create `agents_runner/agent_configs/` Package

## Files to create
- `agents_runner/agent_configs/__init__.py`
- `agents_runner/agent_configs/model.py`
- `agents_runner/agent_configs/storage.py`

## Actions

### 1. `agents_runner/agent_configs/__init__.py`
- Empty or minimal `__init__.py` so the subpackage is importable.

### 2. `agents_runner/agent_configs/model.py`
- Define `AgentConfig` dataclass with fields:
  - `config_id: str` — unique identifier
  - `agent_cli: str` — agent system name (e.g. "codex", "opencode")
  - `config_dir: str = ""` — host config directory path
  - `cli_flags: str = ""` — CLI flags string
- Use `@dataclass` from `dataclasses` (follows existing project conventions).

### 3. `agents_runner/agent_configs/storage.py`
- Use `tomli` / `tomli_w` for TOML I/O (same libraries already in project).
- Atomic writes via `tempfile.mkstemp` + `os.replace` (follow pattern in `agents_runner/persistence.py`).
- Implement functions:

  **`load_agent_configs(state_path: str) -> list[AgentConfig]`**
  - Load state.toml, read `[[agent_configs]]` array-of-tables.
  - Deserialize each entry into `AgentConfig`.
  - If key is missing, return empty list.

  **`save_agent_config(state_path: str, config: AgentConfig) -> None`**
  - Load state, update the `[[agent_configs]]` array (upsert by `config_id`), atomic write back.

  **`delete_agent_config(state_path: str, config_id: str) -> None`**
  - Load state, remove entry with matching `config_id`, atomic write back.

  **`find_envs_referencing_config(state_path: str, config_id: str) -> list[str]`**
  - Load state, scan all environments' `agent_selection.agents` for entries where `config_id` matches.
  - Return list of env_id strings that reference this config_id.
  - Also check `agent_fallbacks`, `pinned_agent_id`, and `cross_agent_allowlist`.

## Success criteria
- `uv run python -c "from agents_runner.agent_configs.model import AgentConfig"` succeeds.
- `uv run python -c "from agents_runner.agent_configs.storage import load_agent_configs, save_agent_config, delete_agent_config, find_envs_referencing_config"` succeeds.
- Atomic write pattern matches `persistence.py` style (tempfile + os.replace).
