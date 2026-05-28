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
- Import works: `from agents_runner.environments.model import AgentInstance`.
- `AgentInstance` has only `agent_id` + `config_id` — removed `agent_cli`, `config_dir`, `cli_flags`.
- ~52 type errors are expected; consumers will be fixed by tasks 04 (serialization), 07 (env agents tab), 08 (runtime resolution).

## AUDIT FINDINGS (2026-05-28) — MODEL CORRECT, CONSUMERS DEFERRED

Model change is done. The 52 type errors across 6 consumer files are expected — these consumers will be fixed in subsequent tasks (04, 07, 08). This task only changes the model shape.
