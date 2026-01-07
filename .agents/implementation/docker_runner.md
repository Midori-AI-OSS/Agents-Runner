# Docker Runner Split

- `agents_runner/docker_runner.py` is now a thin shim that re-exports the prior public surface.
- Implementation lives under `agents_runner/docker/` (focused modules, each under the size limits).
- Worker classes and config objects keep the same names to preserve imports from older call sites.
- Workspace mounting prefers a detected project root (`.git/` or `pyproject.toml`) so tools that search parent directories work even when a user-selected workdir is a subfolder.
