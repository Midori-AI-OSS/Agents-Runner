# Runtime Config Resolution — Resolver + Update All Consumers

## Files to modify
- `agents_runner/agent_configs/storage.py` (add resolver)
- `agents_runner/execution/supervisor.py`
- `agents_runner/docker/agent_worker_container.py`
- `agents_runner/docker/agent_worker_prompt.py`
- `agents_runner/docker/agent_worker_helpers.py`
- `agents_runner/ui/main_window_settings.py`
- `agents_runner/ui/main_window_tasks_agent.py`
- `agents_runner/ui/pages/new_task.py`
- `agents_runner/tests/test_opencode_env_cli_flags.py`

## Actions

### 1. Add resolver to `agent_configs/storage.py`
- Add function:
  ```python
  def resolve_agent_config(state_path: str, config_id: str) -> AgentConfig | None:
      """Look up config_id → AgentConfig from state."""
  ```
- Load configs and find by `config_id`. Return None if not found.

### 2. Add helper in `agent_configs/storage.py` to get AgentConfig fields for an AgentInstance
- Add function:
  ```python
  def resolve_agent_instance(
      state_path: str, agent_instance: AgentInstance
  ) -> tuple[str, str, str] | None:
      """Resolve agent_cli, config_dir, cli_flags from an AgentInstance's config_id.
      Returns (agent_cli, config_dir, cli_flags) if config_id is non-empty and found.
      Returns None if config_id is empty (caller should use global defaults).
      Raises KeyError if config_id is non-empty but not found in state.
      """
  ```

### 3. Update `execution/supervisor.py`
- `_build_agent_config()` (line ~509): Instead of reading `agent.agent_cli`, `agent.cli_flags`, `agent.config_dir` directly from AgentInstance, call `resolve_agent_instance()` to get these values.
- `_resolve_host_config_dir()` (line ~577): Same — resolve via config_id first.
- `_attempt_key()` (line ~620): Same.
- `_effective_agent_cli_args()` (line ~631): Same.
- All other references to `agent.agent_cli`, `agent.config_dir`, `agent.cli_flags`: resolve through config.

### 4. Update `docker/agent_worker_container.py` (line ~76)
- The dict comprehension `{agent.agent_id: agent.agent_cli for agent in env.agent_selection.agents}` needs to resolve `agent_cli` via config lookup.
- Pass `state_path` or resolved configs to the function context.

### 5. Update `docker/agent_worker_prompt.py` (line ~160)
- Same pattern: resolve `agent.agent_cli` via config_id.

### 6. Update `docker/agent_worker_helpers.py` (line ~49)
- Same pattern: resolve `agent.agent_cli` via config_id.

### 7. Update `ui/main_window_settings.py`
- Lines ~534, 629–650, 690–741, 894–950, 1042–1050: All code that reads `agent.agent_cli`, `agent.config_dir`, etc. from AgentInstance.
- Resolve via `load_agent_configs()` + config_id lookup.

### 8. Update `ui/main_window_tasks_agent.py`
- Lines ~257, 264, 277, 302, 312: All references to `agent.agent_cli`, `agent.agent_id` in fallback/agent selection logic.
- Resolve via config_id.

### 9. Update `ui/pages/new_task.py`
- Lines ~1392, 1405, 1409: `AgentInstance` usage in `_format_env_agent_entry_label` and related methods.
- Resolve via config_id.

### 10. Update `tests/test_opencode_env_cli_flags.py`
- Tests create `AgentInstance` with 4 fields → update to use `config_id` and set up mock agent configs via the resolver.
- Update assertions accordingly.

## Success criteria
- `uv run basedpyright` passes.
- All runtime paths that were reading agent_cli/config_dir/cli_flags from AgentInstance now resolve through config_id → AgentConfig lookup.
- No direct field access on AgentInstance for agent_cli/config_dir/cli_flags remains (those fields no longer exist on the dataclass).
