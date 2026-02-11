1. Goal: standalone task engine; managed by Agents Runner GUI or task CLI.
2. State root: `~/.midoriai/agents-tasks/`.
3. Storage: per-task TOML (CLI-owned) in `planned/`, `active/`, `done/`.
4. Logs: never stored in task TOML; store separately (path referenced by task).
5. Security: encryption-at-rest for task + logs (TBD).
6. States (task CLI): `starting`, `pulling`, `paused`, `retrying`, `running`, `done`, `failed`, `cancelled`, `killed`.
7. Cleanup: callable only; uses `cleaning` while running; never automatic.
8. Task TOML: inputs (prompt/env/agent/workspace), runtime (container_id, timestamps), outputs (exit_code, error), metadata (attempt_history, gh/git).
9. Execution: runner interface + Docker runner; agent CLIs include codex/claude/copilot/gemini; plugins later.
10. Preflight: supported; settings + environment scripts run before agent starts (configurable).
11. Postflight: not automatic in task CLI; GUI owns finalization/artifacts; CLI exposes callable actions (ex: cleanup/finalize entrypoints) for the GUI.
12. Pause: Docker pause/unpause; if missing/fails -> `failed`.
13. Product: standalone `agents-tasks` system.
14. Runtime: long-running daemon owns scheduling + state transitions; GUI/CLI are clients.
15. IPC: CLI client talks to daemon (socket); daemon exposes event stream for live UI.
16. Service: optional system service install (systemd-like) but can run user-scoped.
17. Contract: daemon API stays stable so Agents Runner can be rebuilt around it later.
18. Data layout: `~/.midoriai/agents-tasks/{planned,active,done,logs,run}/`.
