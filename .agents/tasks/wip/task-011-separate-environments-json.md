# Task 011: Save Environments to `environments.json` (separate from `state.json`)

## Goal

Environments must be stored in their **own** JSON file in the same directory as `state.json`:

- `~/.midoriai/agents-runner/state.json` (settings, watch state, etc.)
- `~/.midoriai/agents-runner/environments.json` (environments only)

This is a **breaking change**. Do **not** implement “safe migrations” or backups from the old location(s).

## Requirements

### A) Environment persistence moves to `environments.json`

- Implement environment load/save/delete to use `environments.json` instead of embedding environments in `state.json`.
- File path must be derived from the directory containing `state.json` (respect `AGENTS_RUNNER_STATE_PATH` override via `default_state_path()`).

Suggested format (flexible, but keep simple):
- Either a list of serialized environments, or a dict with a top-level `environments` list.
- Keep ordering stable (preserve insertion order when saving).

### B) No compatibility fallbacks

- Do not load environments from:
  - `state.json` `["environments"]`
  - legacy `environment-*.json` files
- Do not create backups of old files.
- Do not attempt to “migrate” or “import” old environments.

### C) Update writers/readers

Update all code paths that write/read environments:

- `agents_runner/environments/storage.py` (primary load/save/delete)
- `agents_runner/ui/main_window_persistence.py`
  - `_save_state()` must stop writing `"environments": [...]` into `state.json`.
  - `_load_state()` should not expect environments in `state.json`.

### D) UI strings (small)

Update any user-facing strings that say environments are saved in `state.json`:
- `agents_runner/ui/pages/environments.py`
- (optionally) any settings/help text

### E) Validation

- Launch app: `uv run main.py` (should not crash).
- Create/edit/delete environments in UI; restart app; environments persist via `environments.json`.

## Notes

- Keep changes minimal; do not modify `README.md`.
- Do not add tests unless asked.

