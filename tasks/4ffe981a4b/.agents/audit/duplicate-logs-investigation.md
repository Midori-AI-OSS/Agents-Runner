# Duplicate Task Logs Investigation

## Summary

Task logs are duplicated because the application streams the same container output via *two independent `docker logs -f` readers* at the same time:

1. The task runner (bridge/worker) streams `docker logs -f <container_id>` and forwards each line to the UI.
2. The “recovery” log tail (intended for post-restart recovery) also starts `docker logs -f --tail 200 <container_id>` for any active task and forwards those same lines to the UI.

Both streams ultimately call the same `_on_task_log(...)` path, which appends lines without deduplication, so each line appears twice (and is persisted twice).

## Where logs are written/displayed

- **Storage + UI append point**
  - `agents_runner/ui/main_window_task_events.py:399` (`_on_task_log`)
    - Appends to `task.logs` and updates the Task Details view via `self._details.append_log(...)`.

- **Task Details display widget**
  - `agents_runner/ui/pages/task_details.py:460` (`TaskDetailsPage.append_log`)
    - Appends the provided line to the log text widget.

## Root cause analysis (duplication mechanism)

### Stream A: Runner/bridge log stream (normal task execution)

- UI starts a worker thread and connects bridge log signals:
  - `agents_runner/ui/main_window_tasks_agent.py:573` (`TaskRunnerBridge(...)`)
  - `agents_runner/ui/main_window_tasks_agent.py:584-586` (`bridge.log.connect(self._on_bridge_log, ...)`)
- Bridge forwards worker logs to the UI:
  - `agents_runner/ui/bridges.py:15-21` (`TaskRunnerBridge.log = Signal(str, str)`)
  - `agents_runner/ui/bridges.py:49-56` (`on_log=lambda line: self.log.emit(self.task_id, line)`)
- The underlying Docker workers read container logs directly:
  - `agents_runner/docker/agent_worker.py:834-875`
    - Spawns `subprocess.Popen(["docker", "logs", "-f", self._container_id], ...)`
    - Forwards each line via `_on_log(wrap_container_log(...))`
  - `agents_runner/docker/preflight_worker.py:390-429`
    - Same pattern for preflight containers.

### Stream B: Recovery log tail stream (started for active tasks)

- Main window runs a periodic recovery ticker:
  - `agents_runner/ui/main_window.py:139-142` (`self._recovery_ticker.timeout.connect(self._tick_recovery)`)
- Recovery tick ensures a log tail for active tasks:
  - `agents_runner/ui/main_window_task_recovery.py:33-44` (`_tick_recovery_task` calls `_ensure_recovery_log_tail(task)` when active)
- Recovery tail starts a second `docker logs -f` reader:
  - `agents_runner/ui/main_window_task_recovery.py:62-116` (`_ensure_recovery_log_tail`)
    - Spawns `subprocess.Popen(["docker", "logs", "-f", "--tail", "200", container_id], ...)`
    - Emits each line via `self.host_log.emit(task_id, wrap_container_log(...))`

### Convergence: both streams feed the same appender

- Both signals ultimately call `_on_task_log(...)`:
  - `agents_runner/ui/main_window_task_events.py:278-280` (`_on_bridge_log -> _on_task_log`)
  - `agents_runner/ui/main_window.py:122` + `agents_runner/ui/main_window_task_events.py:366-368` (`host_log -> _on_host_log -> _on_task_log`)
  - `agents_runner/ui/main_window_task_events.py:399-425` (`_on_task_log` appends; no dedupe)

Because both streams wrap/emit the same container lines in the same canonical format, each container output line is appended twice, displayed twice, and saved twice.

## Why the duplication is visible as “two of everything”

- The runner stream follows the container from the time the worker starts reading logs.
- The recovery stream starts later (on a timer tick once the task is considered “active” and has a `container_id`), but it:
  - Immediately replays the last 200 lines (`--tail 200`), causing an initial burst of duplicates.
  - Continues to follow new lines (`-f`), duplicating live logs going forward.

## Affected files (primary)

- `agents_runner/ui/main_window_task_recovery.py:33-44` (recovery tick always enabling log tail)
- `agents_runner/ui/main_window_task_recovery.py:62-116` (second `docker logs -f` reader)
- `agents_runner/docker/agent_worker.py:834-875` (first `docker logs -f` reader)
- `agents_runner/docker/preflight_worker.py:390-429` (first `docker logs -f` reader for preflight)
- `agents_runner/ui/main_window_task_events.py:278-280` (bridge log routing)
- `agents_runner/ui/main_window_task_events.py:366-368` (host log routing)
- `agents_runner/ui/main_window_task_events.py:399-425` (single append point; no dedupe)
- `agents_runner/ui/main_window.py:122-142` (host_log connection + recovery ticker enabled)

## Recommended fix approach (no code changes in this audit)

1. **Single source of container log streaming per task**
   - Treat the recovery tail as a fallback for tasks that are *running without an in-process worker* (e.g., tasks recovered after app restart, or interactive tasks that do not use `TaskRunnerBridge`).
   - Concretely: gate `_ensure_recovery_log_tail(task)` so it does *not* run when a live bridge/worker thread is already streaming logs for that `task_id` (e.g., `task_id in self._bridges` and the thread is running).

2. **Optional safety net: lightweight dedupe at the append point**
   - If desired as defense-in-depth, dedupe in `_on_task_log` (e.g., ignore an identical line if it matches the immediately previous appended line for the same task). This should be secondary to fixing the double-stream root cause, because it can mask real repeated logs.

3. **Revisit recovery tail intent**
   - If the recovery system is meant only for “after restart”, consider triggering it only from `_reconcile_tasks_after_restart(...)` or only for tasks that were loaded from disk (no bridge/thread), rather than continuously for all active tasks.

