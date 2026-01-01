# Docker Runner Split

- `codex_local_conatinerd/docker_runner.py` is now a thin shim that re-exports the prior public surface.
- Implementation lives under `codex_local_conatinerd/docker/` (focused modules, each under the size limits).
- Worker classes and config objects keep the same names to preserve imports from older call sites.
- Behavior is intended to remain stable; changes are structural (module boundaries) only.

