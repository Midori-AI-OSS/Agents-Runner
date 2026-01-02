# Issue: Cleanup tasks show no logs / never progress

## Summary
Clicking **Settings → Clean Docker** (and **Clean Git Folders / Clean All**) creates a task that shows **Running** but the **Logs** panel remains completely empty and the task appears stuck.

Screenshot from reporter: task is `Running`, `Container ID` is `—`, and logs box is empty.

## Repro
1. Launch GUI: `uv run main.py`
2. Go to **Settings**
3. Click **Clean Docker** (or **Clean All**)
4. Open the created task details

## Expected
- Task behaves like normal tasks: logs stream immediately (at least a `"$ …"` line), then completes `Done/Failed`.
- **Clean All**: Docker runs first, Git is queued after Docker, both show logs and progress.

## Actual
- Task status shows `Running`, but there are **zero log lines** (not even the initial queue/command line).
- Task appears stuck.

## Relevant code / recent changes
- Cleanup orchestration: `codex_local_conatinerd/ui/main_window_cleanup.py`
  - Uses `HostCleanupBridge` + `QThread` and routes logs into `self._on_task_log(...)`.
  - Cleanup runners were moved to shell scripts for verbose output:
    - `scripts/clean-docker.sh`
    - `scripts/clean-git-managed-repos.sh`
  - Runner uses a streaming subprocess helper (`_stream_cmd`) which logs `"$ …"` before spawning the process. Even a missing script should log an error line.
- Bridge implementation: `codex_local_conatinerd/ui/bridges.py` (`HostCleanupBridge`)

## What seems wrong (hypotheses)
- `HostCleanupBridge.run()` may not be invoked (QThread started but `thread.started.connect(bridge.run)` not firing / not running).
- Or `bridge.log` emissions aren’t reaching `_on_cleanup_bridge_log` / `_on_task_log`.
- If `_on_cleanup_bridge_log` is being called but `self.sender()` is `None` or not a `HostCleanupBridge`, the slot returns early and drops logs.

## Suggested next debugging steps
1. Add a temporary log line from GUI thread right after starting the cleanup thread (e.g. `self._on_task_log(task_id, "[debug] cleanup thread started")`) to prove UI path works.
2. Remove reliance on `sender()` for routing:
   - Change `HostCleanupBridge.log` / `done` to include `task_id` (and `kind`) in the signal payload, OR
   - Connect with a closure using `Qt.QueuedConnection`:
     - `bridge.log.connect(lambda line, tid=task_id: self._on_task_log(tid, line), Qt.QueuedConnection)`
3. Verify `scripts/clean-docker.sh` exists at runtime and is being invoked (`_script_path(...)`).

