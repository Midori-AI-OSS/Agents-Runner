# Split `codex_local_conatinerd/docker_runner.py` into smaller modules

## Context
`codex_local_conatinerd/docker_runner.py` is over the hard limit (600+ lines) and mixes configuration, process execution, and Qt thread/worker logic.

## Goal
Break `docker_runner.py` into a small, testable set of modules without changing runtime behavior.

## Proposed module layout
- `codex_local_conatinerd/docker_runner.py`: compatibility shim that re-exports public API
- `codex_local_conatinerd/docker/` package:
  - `config.py`: `DockerRunnerConfig` and related normalization/validation
  - `workers.py`: `DockerCodexWorker`, `DockerPreflightWorker` (Qt/QThread/QObject worker classes)
  - `process.py`: subprocess invocation helpers, streaming log handling, time parsing
  - `paths.py`: host/container path and mount helpers (if present today)

## Acceptance criteria
- Existing imports keep working:
  - `from codex_local_conatinerd.docker_runner import DockerCodexWorker`
  - `from codex_local_conatinerd.docker_runner import DockerPreflightWorker`
  - `from codex_local_conatinerd.docker_runner import DockerRunnerConfig`
- No file exceeds 600 lines; prefer ≤ 300.
- `uv run main.py` still runs end-to-end docker flows that previously worked.

## Notes
- Keep process execution code free of Qt when possible; isolate Qt concerns in `workers.py`.

