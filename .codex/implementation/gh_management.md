# GitHub Management Split

- `agents_runner/gh_management.py` is now a shim over `agents_runner/gh/`.
- `__all__` preserves the expected public API from the original module.
- Task planning/branch prep/PR creation behavior should be unchanged; the split is organizational.
- PR finalization tolerates dirty worktrees when switching to the task branch by checkpointing changes on a temporary branch and cherry-picking onto the task branch (avoids brittle stash apply conflicts).
