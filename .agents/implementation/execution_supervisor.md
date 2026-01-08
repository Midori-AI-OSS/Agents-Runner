# Execution Supervisor Implementation

## Overview

The execution supervisor adds retry, fallback, and error classification capabilities to task execution. It sits between the UI bridge and the Docker agent worker, managing the execution lifecycle with automatic recovery.

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

`calculate_backoff(retry_count, error_type)` returns delay in seconds:

- **Standard backoff**: 5s, 15s, 45s (exponential)
- **Rate limit backoff**: 60s, 120s, 300s (longer delays)

### SupervisorConfig

```python
@dataclass
class SupervisorConfig:
    max_retries_per_agent: int = 3
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
2. **For each agent in chain**:
   a. Try agent execution (`_try_agent`)
   b. If success (exit 0): return result
   c. Classify error
   d. If FATAL: return result (no retry)
   e. If retry_count < max_retries:
      - Increment retry_count
      - Calculate backoff
      - Emit retry signal
      - Sleep backoff duration
      - Continue loop (retry same agent)
   f. If more agents in chain:
      - Switch to next agent
      - Emit agent_switch signal
      - Continue loop (try fallback)
   g. Otherwise: return result (exhausted)

### User Stop Handling (Stop/Kill)

User-initiated Stop/Kill is treated as a terminal outcome and bypasses retry/fallback:

- `request_user_cancel()` sets `user_stop=cancel`, stops the current worker, and logs `user_cancel requested`
- `request_user_kill()` sets `user_stop=kill`, force-kills the current worker/container, and logs `user_kill requested`
- Retry backoff sleep is interruptible; if a user stop is requested during backoff, the supervisor exits early and logs `retry skipped due to user stop`

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
retry_attempt = Signal(int, str, float)  # retry_count, agent, delay
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

`_on_bridge_retry_attempt(retry_count, agent, delay)`:
- Log retry message
- Update task.status = "retrying (X/3)"
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

### Fatal Errors

No retry, immediate failure:
- Authentication failures
- Invalid API keys
- Permission denied

### Retryable Errors

Up to 3 retries per agent:
- Network errors
- Temporary failures
- Generic exit code 1

### Rate Limits

Up to 3 retries with longer backoff:
- 60s, 120s, 300s delays
- Detected from HTTP 429, "rate limit" in logs

### Agent Failures

Try fallback agent:
- Command not found
- Agent not installed
- Exit codes 126, 127

### Container Crashes

Retry with clean container:
- OOMKilled
- SIGKILL (exit 137)

## Testing

Unit tests in `test_supervisor.py`:

- Error classification for all types
- Priority ordering (crash > rate limit > fatal > agent > retryable)
- Case-insensitive pattern matching
- Backoff calculation (standard and rate limit)
- Edge cases (multiple patterns, priority)

## Configuration

Default configuration:
```python
SupervisorConfig(
    max_retries_per_agent=3,
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
   - "Retry Now" button (skip backoff delay)
   - "Cancel Retry" button (stop retry loop)
   - "Force Fallback" button (skip to next agent)

2. **Advanced metrics**:
   - Track success rate per agent
   - Suggest fallback order based on history
   - Detect patterns in failures

3. **Configurable patterns**:
   - User-defined error patterns
   - Per-environment error classification
   - Custom backoff strategies

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
- `test_supervisor.py` (new, 14 tests)

## Code Style

Follows project conventions:
- Python 3.13+ with type hints
- Dataclasses for configuration
- Callable type hints for callbacks
- Docstrings on all public methods
- Under 600 lines per file (supervisor.py ~450 lines)
