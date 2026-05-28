# Update Serialization for Simplified AgentInstance

## Files to modify
- `agents_runner/environments/serialize.py`

## Actions

### 1. Deserialization (`environment_from_payload`)
- Lines ~398–422: Currently building `AgentInstance(agent_id=..., agent_cli=..., config_dir=..., cli_flags=...)`.
- Change to: `AgentInstance(agent_id=..., config_id=str(raw_dict.get("config_id") or "").strip())`
- Remove reading of `agent_cli`, `config_dir`, `cli_flags` from the payload.
- Remove the `if not agent_cli: continue` guard. All entries with a valid `agent_id` are kept (even if `config_id` is empty — empty means "use default config").
- The `_unique_agent_id(seen_ids, agent_id, fallback_prefix=agent_cli.lower())` call will break since `agent_cli` is removed. Change the fallback_prefix to use `config_id.lower()` instead.

### 2. Serialization (`serialize_environment`)
- Lines ~516–530: Currently serializing `agent_id`, `agent_cli`, `config_dir`, `cli_flags`.
- Change to serialize only: `agent_id` and `config_id`.
  ```python
  agents_list = [
      {"agent_id": a.agent_id, "config_id": a.config_id}
      for a in (env.agent_selection.agents or [])
  ]
  ```

### 3. Cross-agent allowlist validation (`_validate_cross_agent_allowlist`)
- Lines ~66–132: Currently references `agent.agent_cli` to enforce max 1 per CLI.
- Since `AgentInstance` no longer has `agent_cli`, remove the CLI-based uniqueness check.
- Simplify to just filter by known `agent_id`s and deduplicate.
- Update the docstring.

## Success criteria
- `uv run basedpyright` passes.
- Serialization round-trip works: environment with agent_selection → `serialize_environment` → `environment_from_payload` preserves the agent list.
