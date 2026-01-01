# Split `codex_local_conatinerd/environments.py` into model + parsing + storage

## Context
`codex_local_conatinerd/environments.py` is at/above the soft limit and mixes:
- the `Environment` model and constants
- text parsing (mounts/env vars)
- filesystem persistence (load/save/delete)
- repo checkout path helpers

## Goal
Split environment management into clear layers while keeping the current behavior and serialized format.

## Proposed module layout
- `codex_local_conatinerd/environments.py`: compatibility shim for public API/constants
- `codex_local_conatinerd/environments/` package:
  - `model.py`: `Environment`, constants (including stain options), GH management mode constants
  - `parse.py`: `parse_env_vars_text`, `parse_mounts_text`, normalization helpers
  - `storage.py`: `load_environments`, `save_environment`, `delete_environment`
  - `paths.py`: `managed_repos_dir`, `managed_repo_checkout_path`
  - `serialize.py`: `serialize_environment` and versioning if needed

## Acceptance criteria
- Existing behavior and on-disk formats remain unchanged.
- No file exceeds 600 lines; prefer ≤ 300.
- Existing imports used by `codex_local_conatinerd/app.py` remain valid (via re-exports).

