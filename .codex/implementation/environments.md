# Environments Split

- `agents_runner/environments/` is a package that centralizes environment model + parsing + persistence helpers.
- `agents_runner/environments/__init__.py` re-exports the stable import surface used by the GUI.
- No behavior change intended; refactor focuses on keeping modules small and cohesive.

