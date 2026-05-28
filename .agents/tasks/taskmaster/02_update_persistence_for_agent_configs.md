# Update `agents_runner/persistence.py` to Load/Save agent_configs

## Files to modify
- `agents_runner/persistence.py`

## Actions

### 1. `load_state()` — add `agent_configs` key
- In the `load_state()` function, alongside `version`, `settings`, `environments`, `tasks`, add:
  ```python
  payload.setdefault("agent_configs", [])
  ```
- Validate it is a list (same pattern as `tasks` and `environments`).

### 2. `save_state()` — already generic
- No changes needed. `save_state` already writes the full payload dict. Since `load_state` now includes `agent_configs`, it will be saved automatically.

### 3. `STATE_VERSION` — bump if needed
- If the new key represents a format change that older code cannot handle, bump `STATE_VERSION` and add version-gated migration logic. Otherwise, just add the default key (preferred — this is additive, not breaking).

## Success criteria
- After fresh start (no state.toml), `load_state()` returns a dict containing `"agent_configs": []`.
- After saving state with an `agent_configs` key present, it persists across reload.
