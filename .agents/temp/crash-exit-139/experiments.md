# Crash exit 139 — experiments run so far (brainstorm)

## Startup warm-up navigation

- Change tested: `agents_runner/app.py:_initialize_qtwebengine()` navigates a hidden `QWebEngineView` to `https://www.google.com` at app startup (warm-up), then `deleteLater()` after ~5s.
- Runs: `timeout -k 1s 10s uv run main.py` x5
  - All exited `124` (timeout), no `139` observed in this “startup only” scenario.
  - Console output consistently included GBM/Vulkan fallback and repeated JS console messages (`defaults.json` / `mandatory.json`).

## Looped 10s runs (exit code sampling)

- Runs: `timeout -k 1s 10s env AGENTS_RUNNER_FAULTHANDLER=1 uv run main.py` x15
  - `139`: 0
  - `124` (timeout): 13
  - `0`: 2
- `~/.midoriai/agents-runner/faulthandler.log` remained empty (no segfault captured in these runs).
