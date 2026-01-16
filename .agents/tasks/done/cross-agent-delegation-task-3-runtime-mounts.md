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


---

## Auditor Review Note (2025-01-16)

**Status:** ⚠️ Implementation complete but NOT COMMITTED

### What needs to be done:
1. **Commit the working tree changes** with a clear commit message
2. **Add a completion note** to this task file (similar to tasks 1 and 2)
3. Move back to done/ after committing
4. Then taskmaster can move to taskmaster/

### Implementation Review:
✅ All acceptance criteria met
✅ Code quality excellent
✅ No security issues
✅ Follows project guidelines

**Files with uncommitted changes:**
- `agents_runner/ui/main_window_settings.py` (added `_compute_cross_agent_config_mounts` method)
- `agents_runner/ui/main_window_tasks_agent.py` (calls cross-agent mount helper)
- `agents_runner/ui/main_window_tasks_interactive.py` (calls cross-agent mount helper)

**Suggested commit message:**
```
[FEATURE] Add cross-agent config mounts for runtime delegation

Implements Task 3 of cross-agent delegation:
- Mounts allowlisted agent config dirs (RW) into containers
- Validates config dirs before mounting
- Enforces one-per-CLI constraint at runtime
- Applies to both worker and interactive runs
- Includes additional config mounts (e.g., ~/.claude.json)
```

**Audit report:** `/tmp/agents-artifacts/2da06b80-audit-summary.audit.md`

---

## Completion Note (2025-01-16)

**Status:** ✅ COMPLETED AND COMMITTED

### Implementation Summary:
Successfully implemented runtime mounting of cross-agent configuration directories:

1. **Added `_compute_cross_agent_config_mounts` method** to `main_window_settings.py`:
   - Computes additional config mounts for allowlisted agents
   - Validates config directories before mounting
   - Enforces one-per-CLI constraint at runtime
   - Avoids duplicate mounts with primary agent config

2. **Integrated cross-agent mounts in worker runs** (`main_window_tasks_agent.py`):
   - Calls the helper method to get cross-agent config mounts
   - Extends `extra_mounts_for_task` with computed mounts
   - Applies to all non-interactive agent task runs

3. **Integrated cross-agent mounts in interactive runs** (`main_window_tasks_interactive.py`):
   - Calls the helper method to get cross-agent config mounts
   - Extends `config_extra_mounts` for Docker terminal sessions
   - Ensures allowlisted agents have their config available in interactive mode

### Acceptance Criteria Verification:
✅ Cross-agent config dirs mounted RW when enabled with allowlist  
✅ No additional mounts when cross-agents disabled  
✅ Additional config files (e.g., ~/.claude.json) mounted via helper  
✅ One-per-CLI constraint enforced at runtime  
✅ Fast-fail validation for missing/invalid config dirs  

### Commit Details:
- **Commit SHA:** d788e49
- **Commit Message:** [FEATURE] Add cross-agent config mounts for runtime delegation
- **Files Modified:** 3 (main_window_settings.py, main_window_tasks_agent.py, main_window_tasks_interactive.py)
- **Lines Changed:** +141

**Task completed by:** coder agent  
**Date:** 2025-01-16

