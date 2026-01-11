# Task: Create task state collector module

## Description
Build a module that collects information about tasks known to the application, including their status, agent names, and failure information.

## Requirements
1. Create a task state collector module
2. Gather information about all known tasks:
   - Task identifier/name
   - Current status
   - Agent name used
   - Creation/start/end timestamps if available
3. For the most recently active task, collect additional details:
   - Last known status
   - Selected agent name
   - Last failure category (if task failed)
   - Any error messages (redacted)
4. Return data as structured dictionary or JSON
5. Handle cases where task information is unavailable

## Acceptance Criteria
- [ ] Collector gathers list of known tasks with status
- [ ] Most recent task details are included
- [ ] Failure information is captured when available
- [ ] Output is structured (dict or JSON)
- [ ] Handles missing/incomplete task data gracefully
- [ ] Code has type hints and error handling

## Related Tasks
- Depends on: None
- Blocks: c9e5d431

## Notes
- Explore `agents_runner/docker/` and `agents_runner/environments/` for task management
- Look for task tracking data structures or databases
- Check for task queue, history, or state files
- Consider both running and completed tasks
- Create module at: `agents_runner/diagnostics/task_collector.py`
- Task data source: 
  - Tasks are stored in state.json (see `agents_runner/persistence.py`)
  - State path: `~/.midoriai/agents-runner/state.json`
  - Also task files in `~/.midoriai/agents-runner/tasks/` directory
- Task model: `agents_runner/ui/task_model.py` - dataclass with fields:
  - `task_id`, `status`, `agent_cli`, `exit_code`, `error`
  - `created_at_s`, `started_at`, `finished_at`
  - `container_id`, `agent_instance_id`
  - `logs` (list of log lines)
  - `attempt_history` (list of previous attempts)
- Function signature: `def collect_task_state() -> dict[str, object]:`
- Return structure:
  ```python
  {
      "tasks": [{"task_id": "...", "status": "...", "agent": "...", ...}],
      "most_recent": {...},  # Full details of most recent task
  }
  ```
- Load tasks using functions from `agents_runner/persistence.py`
