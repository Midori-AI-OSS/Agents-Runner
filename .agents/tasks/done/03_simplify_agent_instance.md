# Simplify `AgentInstance` in `environments/model.py`

## Files to modify
- `agents_runner/environments/model.py`

## Actions

### Replace `AgentInstance` fields
Current (4 fields):
```python
@dataclass
class AgentInstance:
    agent_id: str
    agent_cli: str
    config_dir: str = ""
    cli_flags: str = ""
```

Change to:
```python
@dataclass
class AgentInstance:
    agent_id: str
    config_id: str = ""
```

- Remove `agent_cli`, `config_dir`, `cli_flags` fields.
- Add `config_id: str = ""`.
- Keep `agent_id` for uniqueness within an environment.
- Update the docstring to reflect that `config_id` references an `AgentConfig` from state.

### No migration
Clean break — no backward compatibility shim. Old serialized data with the 4-field format will break, and that is expected (the serialization task will handle the new format).

## Success criteria
- `uv run basedpyright` passes (no type errors from changed dataclass shape).
- Import still works: `from agents_runner.environments.model import AgentInstance`.
