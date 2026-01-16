# Task 3 — Runtime wiring: mount allowlisted configs RW

## 1. Title (short)
Mount cross-agent config dirs (RW) for allowlisted CLIs

## 2. Summary (1–3 sentences)
When cross-agents are enabled for an environment, mount the config directories for allowlisted agent systems into the container read-write, in addition to the primary agent’s config. Apply this to both non-interactive worker runs and interactive Docker terminal runs.

## 3. Implementation notes (key decisions + constraints)
- Derive allowlisted instances from `env.cross_agent_allowlist` (agent IDs), and map them back to `AgentInstance`s in `env.agent_selection.agents`.
- Enforce “one per CLI” at runtime as a safety net (even if UI/model already enforce it).
- Resolve host config dir per allowlisted instance:
  - If the selected `AgentInstance.config_dir` is set, use it.
  - Else fall back to settings via existing config-dir resolution logic (`_resolve_config_dir_for_agent(...)` using the instance’s `agent_cli`).
- Ensure host dirs exist before mounting (reuse `_ensure_agent_config_dir(...)` for each allowlisted agent, abort run with a clear QMessageBox if a required config dir is missing/invalid).
- Build mounts using existing helpers (no hardcoded container paths):
  - Directory mount: `f"{host_dir}:{container_config_dir(agent_cli)}:rw"`
  - Extra mounts: extend with `additional_config_mounts(agent_cli, host_dir)` (e.g., Claude’s `~/.claude.json`).
- Avoid duplicate mounts (skip if it matches the primary agent’s config mount or if already present).
- Keep cross-agent logic separate from primary selection mode logic; do not treat allowlist as fallback or modify agent chain selection.

## 4. Acceptance criteria (clear, testable statements)
- With `Use cross agents` enabled and allowlist containing a different agent CLI than the primary, the container has that agent’s config dir mounted at `container_config_dir(...)` with RW semantics (visible in the constructed Docker `-v` args).
- With `Use cross agents` disabled, no additional agent-config mounts are added beyond the primary agent config (and existing user-defined `extra_mounts`).
- If allowlist includes Claude and the sibling `~/.claude.json` exists, it is also mounted into the container via `additional_config_mounts(...)`.
- If allowlist contains multiple IDs for the same CLI (shouldn’t happen), runtime mounts at most one config dir for that CLI.
- Missing/invalid allowlisted config dirs fail fast with a user-visible warning (consistent with primary agent config validation).

## 5. Expected files to modify (explicit paths)
- `agents_runner/ui/main_window_settings.py` (add a helper to compute cross-agent config mounts + validation)
- `agents_runner/ui/main_window_tasks_agent.py` (append computed mounts to `extra_mounts_for_task`)
- `agents_runner/ui/main_window_tasks_interactive.py` (compute and pass extra config mounts for interactive runs)
- `agents_runner/ui/main_window_tasks_interactive_docker.py` (ensure passed mounts are included in Docker `-v` args)

## 6. Out of scope (what not to do)
- Do not add new agent orchestration/prompting behavior (mounting only).
- Do not refactor DockerRunnerConfig broadly unless strictly required.
- No changes to `container_config_dir(...)` mapping rules.
- Do not update `README.md` or add tests.

