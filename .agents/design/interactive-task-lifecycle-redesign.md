# Design Document — Interactive Tasks Lifecycle Redesign

**Type:** Design Document (not an executable task)  
**Status:** Complete  
**Implementation Tasks:** See `.agents/tasks/wip/T005-interactive-tasks-implementation-breakdown.md`

---


**Type:** Design Document (not an executable task)  
**Status:** Complete  
**Implementation Tasks:** See `.agents/tasks/wip/T005-interactive-tasks-implementation-breakdown.md`

---

## Problem

Interactive tasks are not fully lifecycle-managed by the app (the “run” is owned by a host terminal script). This makes restart recovery and post-run cleanup/finalization unreliable and contributes to tasks getting stuck, losing exit information, and losing post-run automation (artifact collection / PR / cleanup).

User direction: Interactive should behave like a normal task (same lifecycle + finalization), but the user interacts with the agent in the container via a terminal window that the app opens.

## Scope (design + notes)

- Capture requirements and propose an app-owned lifecycle for interactive tasks (detach/reattach, cleanup, terminal outcome recording).
- This document is meant to help other agents implement the redesign.

## Requirements (what we want)

- App owns lifecycle (start/stop/kill/status/exit code) and post-run finalization (cleanup, PR policy, artifacts).
- User interacts via a host terminal window attached to the running container.
- Detach/reattach must work across UI restarts.
- Keep `auto_remove` behavior on container shutdown (container should be removed once it exits).

## What the code does today (why it’s janky)

Key points from current implementation:

- Interactive is launched via a generated host shell script that runs `docker run -it --name <name> ...` in the user’s terminal.
  - Code: `agents_runner/ui/main_window_tasks_interactive_docker.py`
- That host script writes a plaintext finish file to `~/.midoriai/agents-runner/interactive-finish-<task_id>.txt`, then removes the container with `docker rm -f` in an `EXIT` trap.
  - Code: `agents_runner/ui/main_window_tasks_interactive_docker.py:_build_host_shell_script`
- The UI only discovers completion by polling for that finish file in-process, during the same app session that launched it.
  - Code: `agents_runner/ui/main_window_tasks_interactive.py:_start_interactive_finish_watch`
  - On success it calls `agents_runner/ui/main_window_tasks_interactive_finalize.py:_on_interactive_finished`

Why this fails in practice:

- If the UI restarts, there is no watcher thread, so a completed interactive task can sit in “running/unknown” indefinitely.
- On restart, task recovery uses `docker inspect` (`_try_sync_container_state`) but the interactive container is often already removed by the host script, so “inspect” fails and the task becomes generic “failed (exit_code=1)”.
  - Code: `agents_runner/ui/main_window_persistence.py:_try_sync_container_state`
- Finalization currently tries to collect artifacts “from the container”, but the container might not exist anymore, so finalization can error and never reach `finalization_state="done"`.
  - Code: `agents_runner/ui/main_window_task_recovery.py:_finalize_task_worker`

## Naming (current conventions)

As of the latest naming cleanup:

- Normal task containers: `agents-runner-<random>` (example: `agents-runner-a1b2c3d4e5`)
- Preflight containers: `agents-runner-preflight-<random>`
- Interactive task containers: `agents-runner-tui-it-<task_id>`

Note: `Task.container_id` often stores a container *name* (not an ID). Recovery paths currently pass it to Docker commands as an identifier (Docker accepts names).

## Implications of keeping auto-remove

If the container is removed on exit, restart recovery cannot depend on `docker inspect` finding an `exited` container later. The design needs a host-visible completion signal that survives container removal.

## Proposed design: app-owned container + terminal attach UX

The simplest “acts like a normal task, but interactive in a terminal” model is:

1) App starts the container (detached) and records its identity in the persisted task payload.
2) App opens a terminal window that attaches to the already-running container for user interaction.
3) App monitors container state and logs (and can be restarted to resume monitoring).
4) On exit, container is auto-removed, but a host-visible completion marker remains so restart recovery can finalize.

This removes the split ownership (terminal script no longer does `docker run` or `docker rm`).

### Container launch shape

Use the normal-task shape as a template (it already mounts artifact staging and tails logs):

- Normal task runner mounts a host staging dir to `/tmp/agents-artifacts` in-container.
  - Code: `agents_runner/docker/agent_worker.py` includes `-v <artifacts_staging_dir>:/tmp/agents-artifacts`
- Normal tasks already tail logs via `docker logs -f`.
  - Code: `agents_runner/docker/agent_worker.py` and restart recovery tail `agents_runner/ui/main_window_task_recovery.py:_ensure_recovery_log_tail`

Interactive variant should:

- Start the container with a stable name (already done): `agents-runner-tui-it-<task_id>`
- Start detached but with a TTY so `docker attach` works well: `docker run --rm -dit --name <name> ...`
- Mount the task’s host staging directory to `/tmp/agents-artifacts` (same as normal tasks)
- Run the agent as the main process so the container exits when the agent exits (so auto-remove triggers cleanly)

#### Complete Docker command template

```bash
docker run \
  --rm \
  -dit \
  --name "agents-runner-tui-it-${TASK_ID}" \
  -v "${HOST_ARTIFACTS_STAGING}:/tmp/agents-artifacts" \
  -v "${HOST_CODEX_DIR}:/root/.codex" \
  -v "${HOST_WORKDIR}:/workspace" \
  -e TASK_ID="${TASK_ID}" \
  -e OPENAI_API_KEY="${OPENAI_API_KEY}" \
  -e ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY}" \
  -e GITHUB_TOKEN="${GITHUB_TOKEN}" \
  --workdir /workspace \
  "${IMAGE}" \
  /bin/bash -c '/tmp/agents-artifacts/.container-entrypoint.sh'
```

Key points:
- `-dit`: detached, interactive, pseudo-TTY (required for `docker attach`)
- `--rm`: auto-remove on exit (keep existing behavior)
- Volume mounts match normal task pattern (artifacts, codex config, workspace)
- Environment variables passed through (agent needs API keys)
- Entrypoint script written by app to staging dir before `docker run`

#### Container entrypoint script (`.container-entrypoint.sh`)

The app should write this script to `${HOST_ARTIFACTS_STAGING}/.container-entrypoint.sh` before launching:

```bash
#!/bin/bash
set -euo pipefail

# Trap EXIT to write completion marker even on normal exit
write_completion_marker() {
    local exit_code=$?
    cat > /tmp/agents-artifacts/interactive-exit.json <<EOF
{
  "task_id": "${TASK_ID}",
  "container_name": "$(hostname)",
  "exit_code": ${exit_code},
  "started_at": "${STARTED_AT}",
  "finished_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "reason": "process_exit"
}
EOF
    exit ${exit_code}
}

trap write_completion_marker EXIT

# Record start time
STARTED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)

# Launch the agent CLI (replace with actual agent command)
exec ${AGENT_CLI} ${AGENT_CLI_ARGS}
```

Notes:
- `trap` ensures completion marker is written on normal exit
- `SIGKILL` will bypass the trap (app should use `docker wait` as backup)
- Script is executable: app must `chmod +x` before `docker run`
- Environment variables (`TASK_ID`, `AGENT_CLI`, etc.) passed via `docker run -e`

### Terminal attach/detach

Terminal command should be “attach to existing container” (not “run the container”):

- `docker attach <container_name>`

Expected behavior:

- Closing the terminal window should not destroy the container; the container continues to run and the UI still controls stop/kill.
- Reattach is just opening another terminal and running the same attach command.

(If we want detach without killing the agent, document `Ctrl-p` then `Ctrl-q`, and/or provide a UI “Reattach” button that just opens a new terminal.)

## Completion marker (survives auto-remove)

Write a completion marker into the mounted `/tmp/agents-artifacts` dir before the container exits:

- Path (host-visible): `~/.midoriai/agents-runner/artifacts/<task_id>/staging/interactive-exit.json`
  - This is the host path behind the container’s `/tmp/agents-artifacts/interactive-exit.json`

Contents (keep minimal; avoid secrets):

```json
{
  "task_id": "abcd1234ef",
  "container_name": "agents-runner-tui-it-abcd1234ef",
  "exit_code": 0,
  "started_at": "2026-01-18T10:00:00Z",
  "finished_at": "2026-01-18T10:05:00Z",
  "reason": "process_exit"
}
```

How to ensure it’s written:

- Wrap the agent launch in a shell `trap` inside the container script so `EXIT` writes the JSON.
- Note: `SIGKILL` can bypass traps; if the UI is alive, it can also record `docker wait` exit code as a backup.

## Artifact strategy (no container dependency after exit)

Because the container is auto-removed on exit, finalization must not require `docker cp` from the container after-the-fact.

Make the staging directory mount the source of truth:

- Mount host staging dir to `/tmp/agents-artifacts` in the interactive container.
- Anything we care about after exit (logs, completion marker, screenshots, PR metadata) should be written into `/tmp/agents-artifacts`.
- Finalization can then encrypt/collect from the host staging dir even when the container is gone.

This matches the “artifact info” model already in code:

- `agents_runner/artifacts.py:get_artifact_info()` defines the container artifacts dir as `/tmp/agents-artifacts/`.

## Relevant existing machinery (reuse it)

There is already a restart recovery loop and a background finalizer for normal tasks:

- Startup reconciliation calls `_reconcile_tasks_after_restart()`:
  - `agents_runner/ui/main_window_persistence.py:_load_state`
  - Implementation: `agents_runner/ui/main_window_task_recovery.py:_reconcile_tasks_after_restart`
- When a task is active, recovery can tail logs via `docker logs -f`:
  - `agents_runner/ui/main_window_task_recovery.py:_ensure_recovery_log_tail`
- Finalization is tracked via `Task.finalization_state` and runs in a worker thread:
  - `agents_runner/ui/main_window_task_recovery.py:_queue_task_finalization`
  - `agents_runner/ui/main_window_task_recovery.py:_finalize_task_worker`

The interactive redesign should plug into those same mechanisms, but must avoid any “needs the container after exit” assumptions because interactive containers are expected to be auto-removed.

## Restart recovery behavior (interactive-specific)

On startup, for each interactive task that is not finalized:

1) If the completion marker exists in staging:
   - Set status `done/failed` based on `exit_code`
   - Set `finished_at`
   - Queue finalization (host-staging based)
2) Else if the container exists and is running:
   - Set status `running`
   - Start log tail (`docker logs -f`) so UI has logs
   - Show UI affordance to “Attach” (open terminal)
3) Else (no marker, no container):
   - Mark `status="unknown"` or “failed (unrecoverable)” with a clear error
   - Still run best-effort finalization/cleanup that does not require the container (user preference: try finalization even when missing container)

## Implementation mapping (where to change)

Likely touch points for an implementation agent:

- Replace “terminal owns `docker run`” with “app starts container + terminal attaches”:
  - `agents_runner/ui/main_window_tasks_interactive_docker.py`
- Store and use the same staging dir mount as normal tasks:
  - Mirror normal runner behavior from `agents_runner/docker/agent_worker.py`
- Teach recovery to look for the interactive completion marker:
  - `agents_runner/ui/main_window_task_recovery.py` and/or `agents_runner/ui/main_window_persistence.py`
- Avoid container-dependent artifact collection when container is auto-removed:
  - `agents_runner/ui/main_window_task_recovery.py:_finalize_task_worker` (collect from host staging if container missing)

## Acceptance checks (what “fixed” looks like)

- Interactive tasks show logs in the UI while running (tailing `docker logs -f`).
- If the UI is closed mid-run, reopening the app shows the task as running and allows reattach to the same container.
- If the container exits while the UI is closed, reopening the app finalizes the task using the completion marker + host staging (no stuck “unknown” and no missed cleanup/PR prompts).
- Containers do not remain on disk after interactive exit (auto-remove still effective).

## Notes

- This is intentionally separate from “normal task state recovery + finalization across restarts”, but it should reuse the same recovery/finalization primitives where possible.

---

## Additional Implementation Details (Added by Auditor)

### Terminal Window Launch Mechanism

Platform detection (Linux terminal emulators in priority order):

```python
import subprocess
import shutil

TERMINAL_EMULATORS = [
    ["konsole", "--hold", "-e"],           # KDE
    ["gnome-terminal", "--wait", "--"],    # GNOME
    ["xfce4-terminal", "--hold", "-e"],    # XFCE
    ["xterm", "-hold", "-e"],              # Fallback
]

def launch_terminal_attach(container_name: str) -> subprocess.Popen | None:
    """Launch terminal emulator with docker attach command."""
    attach_cmd = ["docker", "attach", container_name]
    
    for term_cmd in TERMINAL_EMULATORS:
        if shutil.which(term_cmd[0]):
            try:
                full_cmd = term_cmd + attach_cmd
                proc = subprocess.Popen(full_cmd, 
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL)
                return proc
            except Exception:
                continue
    
    # No terminal emulator found - notify user
    return None
```

UI integration:
- Add "Attach Terminal" button to task row for interactive tasks in `running` state  
- Button opens terminal via `launch_terminal_attach(task.container_id)`  
- If terminal launch fails, show error dialog with manual attach command  
- Do not track terminal PID (closing terminal does not affect container)

### Log Tailing Lifecycle

When to start log tail:
- **Container start:** Immediately after `docker run` succeeds, start `docker logs -f` in background thread
- **Restart recovery:** If container is running, call `_ensure_recovery_log_tail()` to resume tailing
- **No duplication:** Check if log tail thread already exists before starting

Integration with existing machinery:
- Use `agents_runner/ui/main_window_task_recovery.py:_ensure_recovery_log_tail`
- Store log tail thread reference in task metadata or UI state
- On task completion, stop log tail thread (container is auto-removed anyway)

### Error Recovery Scenarios

| Scenario | Detection | Recovery Action |
|----------|-----------|-----------------|
| Container crashes on start | `docker run` fails | Set `status="failed"`, `exit_code=1`, queue finalization |
| User kills container manually | `docker wait` returns early | Read completion marker if present, else mark `status="unknown"` |
| Completion marker malformed | JSON parse error | Use `docker wait` exit code as fallback, log warning |
| Staging directory deleted mid-run | File IO error during finalization | Mark `finalization_state="failed"`, log error, don't block UI |
| Container killed with SIGKILL | `docker wait` returns 137 | Mark `status="failed"`, `exit_code=137`, queue finalization |

Fallback strategy:
- Always attempt `docker wait <container_name>` in background to capture exit code
- If completion marker exists, prefer it (has timestamps)
- If only `docker wait` result available, use that
- If neither available (restart scenario), mark `status="unknown"`

### Migration Plan for Existing Tasks

**Deployment impact:** Users may have in-progress interactive tasks using old script-based approach.

**Strategy:**
1. Add version marker to `Task` model: `interactive_version: int = 1` (old) or `2` (new)
2. On app startup, reconcile old-style tasks:
   - If `interactive_version == 1` and task is `running`: mark as `unknown` with message "Please restart task (old format)"
   - If `interactive_version == 1` and task is `done`: leave as-is (historical data)
3. New interactive tasks always use `interactive_version = 2`
4. Document in release notes: "In-progress interactive tasks will be marked as unknown; please restart them"

**No automatic migration:** Old tasks use different container launch mechanism; safest to fail-fast and require restart.

### Performance and Resource Management

**Polling frequency:**
- No active polling for completion marker (wasteful)
- Use `docker wait` in background thread (blocks until container exits)
- On exit, `docker wait` thread checks for completion marker file

**Log tail buffer limits:**
- Reuse existing log tail implementation from `agent_worker.py`
- Existing code already handles line-by-line buffering
- No changes needed

**Staging directory cleanup:**
- After finalization completes, staging directory can be deleted
- Encrypted artifact bundle is the long-term storage
- Add cleanup step in `_finalize_task_worker` after encryption
- Keep staging for 24 hours in case of finalization retry (user preference)

### Testing Script (Step-by-Step)

#### Test 1: Basic interactive task lifecycle

```bash
# 1. Start interactive task via UI
# 2. Verify container exists: docker ps | grep agents-runner-tui-it
# 3. Verify staging dir exists: ls ~/.midoriai/agents-runner/artifacts/<task_id>/staging
# 4. Click "Attach Terminal" button
# 5. Verify terminal opens with agent prompt
# 6. Exit agent (type 'exit' or Ctrl-D)
# 7. Verify completion marker created: cat ~/.midoriai/agents-runner/artifacts/<task_id>/staging/interactive-exit.json
# 8. Verify UI shows task as "done" with correct exit code
# 9. Verify finalization runs (artifact encryption, PR prompt if enabled)
# 10. Verify container is removed: docker ps -a | grep agents-runner-tui-it (should be empty)
```

#### Test 2: Restart recovery (container still running)

```bash
# 1. Start interactive task via UI
# 2. Attach terminal and leave agent running
# 3. Close the UI app (not the terminal)
# 4. Reopen the UI app
# 5. Verify task shows as "running" in UI
# 6. Verify log tail resumes (new logs appear in UI)
# 7. Click "Attach Terminal" again (reattach)
# 8. Verify terminal attaches to same running container
# 9. Exit agent in terminal
# 10. Verify UI detects completion and finalizes
```

#### Test 3: Restart recovery (container exited while UI closed)

```bash
# 1. Start interactive task via UI
# 2. Attach terminal
# 3. Close the UI app
# 4. Exit agent in terminal (container exits and is removed)
# 5. Reopen the UI app
# 6. Verify UI reads completion marker
# 7. Verify task shows as "done" with correct exit code
# 8. Verify finalization runs (even though container is gone)
```

#### Test 4: Edge case - SIGKILL

```bash
# 1. Start interactive task via UI
# 2. Attach terminal
# 3. From another terminal: docker kill -s SIGKILL agents-runner-tui-it-<task_id>
# 4. Verify UI detects exit via docker wait
# 5. Verify task shows as "failed" with exit_code=137
# 6. Verify finalization still runs
```

#### Test 5: Edge case - manual docker rm

```bash
# 1. Start interactive task via UI
# 2. From another terminal: docker rm -f agents-runner-tui-it-<task_id>
# 3. Verify UI detects missing container
# 4. Verify task shows as "failed" or "unknown"
# 5. Verify finalization attempts best-effort cleanup
```

### Security Considerations

**Completion marker contents:**
- NEVER include secrets (API keys, tokens, passwords)
- Task ID is safe (already visible in UI)
- Container name is safe (derived from task ID)
- Exit code is safe (integer status)
- Timestamps are safe (metadata)

**Staging directory permissions:**
- Host staging directory: `~/.midoriai/agents-runner/artifacts/<task_id>/staging`
- Owned by user running the app (standard Linux permissions)
- No special permission hardening needed (user's home directory)
- Container runs as root inside, mounts staging directory (standard Docker pattern)

**Environment variable handling:**
- API keys passed via `docker run -e` (standard Docker pattern)
- Never log environment variables in completion marker or logs
- Environment variables not visible in `docker ps` (Docker obscures `-e` values)

### Artifact Collection Details

**Expected artifacts in staging directory:**
- `interactive-exit.json`: Completion marker (required)
- `agent-output.md`: Agent run log (if agent writes it)
- `.container-entrypoint.sh`: Launch script (cleanup after finalization)
- Any files the agent writes to `/tmp/agents-artifacts/` in-container

**Finalization steps:**
1. Check if staging directory exists (handle missing directory gracefully)
2. Read `interactive-exit.json` for metadata
3. Collect all files in staging directory
4. Encrypt and bundle into artifact tarball
5. Clean up staging directory (optional: keep for 24h for debugging)
6. Prompt for PR creation if enabled
7. Set `finalization_state="done"`

**Handling partial artifacts:**
- If agent crashes mid-run, staging directory may have incomplete files
- Finalization should collect whatever exists (best-effort)
- Missing `interactive-exit.json` is OK (use `docker wait` exit code instead)

### Rollback Plan

**Feature flag approach:**
- Add config option: `interactive_tasks_use_app_lifecycle: bool = True`
- Default to `True` for new deployments
- If issues arise, user can set to `False` to revert to old script-based approach
- Config stored in `~/.midoriai/agents-runner/config.json`

**Minimum viable implementation (MVP):**
- Phase 1: App-owned container launch + basic completion marker (no restart recovery yet)
- Phase 2: Add restart recovery + log tailing
- Phase 3: Full finalization integration + artifact collection

This allows incremental rollout with fallback at each phase.
