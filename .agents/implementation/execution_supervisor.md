# Execution Supervisor Implementation

## Overview

The execution supervisor adds safe fallback, error classification, and cooldown handling to task execution. It sits between the UI bridge and the Docker agent worker and ensures a task run never re-attempts the same agent+configuration.

## Architecture

```
TaskRunnerBridge
    ↓
TaskSupervisor (if use_supervisor=True)
    ↓
DockerAgentWorker (per attempt)
```

## Components

### ErrorType Enum

Classifies execution errors into 5 categories:

- **RETRYABLE**: Transient errors (network, temporary failures)
- **RATE_LIMIT**: API rate limits (needs longer backoff)
- **AGENT_FAILURE**: Agent not found or not executable
- **FATAL**: Unrecoverable (auth, permissions)
- **CONTAINER_CRASH**: OOMKilled, SIGKILL

### Error Classification

`classify_error(exit_code, container_state, logs)` uses pattern matching:

1. **Container crash detection** (highest priority):
   - OOMKilled flag in container state
   - Exit code 137 (SIGKILL)

2. **Rate limit detection**:
   - Patterns: "rate limit", "429", "too many requests", "quota exceeded"
   - Scans last 100 log lines

3. **Fatal error detection**:
   - Patterns: "authentication failed", "invalid api key", "permission denied"
   - Scans last 50 log lines

4. **Agent failure detection**:
   - Patterns: "command not found", "no such file.*codex"
   - Exit codes: 126, 127

5. **Default to RETRYABLE** for other non-zero exit codes

### Backoff Calculation

Backoff delays are intentionally not used for supervised retries. A failed attempt immediately switches to the next fallback agent+configuration.

### SupervisorConfig

```python
@dataclass
class SupervisorConfig:
    max_retries_per_agent: int = 0
    enable_fallback: bool = True
    backoff_base_seconds: float = 5.0
    rate_limit_backoff_base: float = 60.0
```

### SupervisorResult

```python
@dataclass
class SupervisorResult:
    exit_code: int
    error: str | None
    artifacts: list[str]
    metadata: dict[str, Any]  # agent_used, agent_id, retry_count, total_attempts
```

## TaskSupervisor Class

### Initialization

Accepts:
- `config`: DockerRunnerConfig (base configuration)
- `prompt`: Task prompt
- `agent_selection`: AgentSelection from environment (may be None)
- `supervisor_config`: Behavior configuration
- `on_state`, `on_log`: Standard callbacks
- `on_retry`: Callback for retry attempts (retry_count, agent, delay)
- `on_agent_switch`: Callback for agent switches (from_agent, to_agent)
- `on_done`: Completion callback (exit_code, error, artifacts, metadata)

### Agent Chain Building

`_initialize_agent_chain()`:

1. If no agent_selection or empty agents list:
   - Use default agent from config
   - Chain = [default_agent]

2. Otherwise:
   - Start with first agent in agents list
   - Follow agent_fallbacks mapping to build chain
   - Detect circular fallbacks (stop on cycle)
   - Validate fallback references (skip invalid)

Example:
```python
agents = [agent_a, agent_b, agent_c]
agent_fallbacks = {"agent_a": "agent_b", "agent_b": "agent_c"}
# Chain: [agent_a, agent_b, agent_c]
```

### Execution Loop

`run()` method:

1. **Initialize agent chain**
2. **For each agent+config in chain (once each)**:
   a. Skip entries on cooldown
   b. Try agent execution (`_try_agent`)
   c. If success (exit 0): return result
   d. Classify failure reason and record it on the attempt history
   e. If rate-limited/quota-exhausted: set a 1-hour cooldown for that agent+config
   f. Immediately switch to the next fallback agent+config (no delay)
   g. If none available: stop and report attempted + cooldown entries

### User Stop Handling (Stop/Kill)

User-initiated Stop/Kill is treated as a terminal outcome and bypasses retry/fallback:

- `request_user_cancel()` sets `user_stop=cancel`, stops the current worker, and logs `user_cancel requested`
- `request_user_kill()` sets `user_stop=kill`, force-kills the current worker/container, and logs `user_kill requested`
User-initiated Stop/Kill is terminal; no retry/fallback is scheduled afterward.

### Agent Execution

`_try_agent(agent)`:

1. Build agent-specific DockerRunnerConfig
2. Create new DockerAgentWorker
3. Set _current_worker (for properties)
4. Run worker (blocking)
5. Clear _current_worker
6. Return SupervisorResult with metadata

### Configuration Building

`_build_agent_config(agent)`:

- Copies all fields from base config
- Overrides:
  - `agent_cli` from agent.agent_cli
  - `host_codex_dir` from agent.config_dir (if set)
  - `agent_cli_args` from agent.cli_flags (parsed with shlex)

## UI Integration

### Bridge Signals

Added to TaskRunnerBridge:

```python
retry_attempt = Signal(int, str, float)  # attempt_number, agent, delay_seconds (always 0 for fallback)
agent_switched = Signal(str, str)  # from_agent, to_agent
done = Signal(int, object, list, dict)  # exit_code, error, artifacts, metadata
```

### Bridge Constructor

```python
TaskRunnerBridge(
    task_id: str,
    config: DockerRunnerConfig,
    prompt: str = "",
    mode: str = "codex",
    agent_selection: AgentSelection | None = None,
    use_supervisor: bool = True,
)
```

- If `mode == "preflight"`: use DockerPreflightWorker
- If `use_supervisor and mode != "preflight"`: use TaskSupervisor
- Otherwise: use DockerAgentWorker (legacy)

### Event Handlers

`_on_bridge_retry_attempt(attempt_number, agent, delay)`:
- Log attempt message
- Update task.status = "retrying (attempt N)"
- Refresh dashboard

`_on_bridge_agent_switched(from_agent, to_agent)`:
- Log switch message
- Update task.agent_cli = to_agent
- Refresh dashboard

`_on_bridge_done(exit_code, error, artifacts, metadata)`:
- Extract agent_used, agent_id, retry_count from metadata
- Update task.agent_cli, task.agent_instance_id
- Log completion with retry count if > 0
- Call _on_task_done

### Task Flow

1. User creates task in UI
2. `_start_task_from_ui`:
   - Store agent_selection in task._agent_selection
3. `_actually_start_task`:
   - Pass agent_selection to TaskRunnerBridge
   - Connect retry_attempt and agent_switched signals
4. Supervisor executes with retry/fallback
5. UI updates on retry/switch events
6. Completion metadata stored in task

## Properties

TaskSupervisor exposes properties for bridge compatibility:

- `container_id`: Current worker's container ID
- `gh_repo_root`: Current worker's GitHub repo root
- `gh_base_branch`: Current worker's base branch
- `gh_branch`: Current worker's branch

These properties delegate to `_current_worker` (set during execution).

## Stop Support

`request_stop()` method:
- Delegates to current worker's request_stop()
- Gracefully terminates running container

## Error Handling

All failures (including auth, tool errors, and unknown) advance to the next fallback agent+config. Rate limit / quota failures additionally place the failing agent+config on a one-hour cooldown.

### Agent Failures

Try fallback agent:
- Command not found
- Agent not installed
- Exit codes 126, 127

### Container Crashes

Try fallback agent:
- OOMKilled
- SIGKILL (exit 137)

## Testing

No dedicated automated tests are currently included for the supervisor behavior.

## Configuration

Default configuration:
```python
SupervisorConfig(
    max_retries_per_agent=0,
    enable_fallback=True,
)
```

Can be customized per task if needed.

## Limitations

### What Supervisor Does NOT Do

- **No timeout detection**: Tasks can run indefinitely
- **No hang detection**: No "no output" checks
- **No resource monitoring**: No CPU/memory thresholds
- **Task-scoped only**: Fallback doesn't change environment defaults

### Why These Limits

Per design requirements:
- Trust containers to exit or user to stop
- Rely on explicit signals (exit codes, crashes, user stop)
- Avoid false positives from timeout/hang detection

## Future Enhancements

Possible additions (not in current scope):

1. **User controls**:
   - "Force Fallback" button (skip to next agent)

2. **Advanced metrics**:
   - Track success rate per agent
   - Suggest fallback order based on history
   - Detect patterns in failures

3. **Configurable patterns**:
   - User-defined error patterns
   - Per-environment error classification
   - Optional retry delays (not recommended)

4. **Container restart**:
   - Explicit restart after crash (currently creates new)
   - Preserve container logs across restarts
   - Limit restart attempts

## Dependencies

- `agents_runner.docker.config.DockerRunnerConfig`
- `agents_runner.docker_runner.DockerAgentWorker`
- `agents_runner.environments.model.AgentInstance`
- `agents_runner.environments.model.AgentSelection`
- Python 3.13+ (type hints, dataclasses)

## Files Modified

- `agents_runner/execution/__init__.py` (new)
- `agents_runner/execution/supervisor.py` (new, ~450 lines)
- `agents_runner/ui/bridges.py` (modified, +30 lines)
- `agents_runner/ui/main_window_tasks_agent.py` (modified, +5 lines)
- `agents_runner/ui/main_window_task_events.py` (modified, +70 lines)
Supervisor changes are reflected in the runtime code and UI integration; no new test files are added.

## Code Style

Follows project conventions:
- Python 3.13+ with type hints
- Dataclasses for configuration
- Callable type hints for callbacks
- Docstrings on all public methods
- Under 600 lines per file (supervisor.py ~450 lines)
