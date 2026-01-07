# Run Supervisor Design & Implementation Guide

**Audit ID:** 03-run-supervisor-design  
**Date:** 2025-01-07  
**Auditor:** Auditor Mode  
**Purpose:** Detailed implementation guidance for Task 2 (Run Supervisor)  
**Related Documents:** 
- `.codex/audit/86f460ef-codebase-structure.audit.md` (Codebase structure)
- `.codex/audit/02-task-breakdown.md` (Overall refactor plan)

---

## Executive Summary

The Run Supervisor is a critical component that will add retry, fallback, and container restart capabilities to the task execution system.

**Key Findings:**
- Current execution is **single-shot, no retry** - failures are immediately terminal
- Agent selection UI **exists but unused** - data model complete, integration missing
- Error detection is **already comprehensive** - exit code, container state, process signals
- Container lifecycle management is **well-structured** - easy to add restart capability
- **NO hang detection exists** (and none should be added per requirements)

**Critical Constraints:**
- **NO timeout-based failure detection** - only explicit signals (exit codes, container crashes, user stop)
- **NO hang detection** - trust containers to exit or user to stop them
- **Task-scoped fallback** - fallback selection doesn't change environment defaults
- **Clean container restart** - always with fresh container, never reuse crashed container

---

## Current Execution Flow Analysis

### 1. Task Launch Flow (Non-Interactive)

```
User clicks "Run Agent"
    ↓
ui/pages/new_task.py::requested_run signal
    ↓
ui/main_window_tasks_agent.py::_start_task_from_ui() [lines 81-355]
    ├─ Validate inputs (Docker, prompt, environment)
    ├─ Generate task_id = uuid4().hex[:10]
    ├─ Check capacity
    ├─ Create DockerRunnerConfig
    ├─ Create Task model + TaskRunnerBridge + QThread
    └─ Start worker or queue
           ↓
docker/agent_worker.py::DockerAgentWorker::run() [lines 96-504]
    ├─ [IF gh_repo] prepare_github_repo_for_task()
    ├─ Pull Docker image (if needed)
    ├─ Build mounts (config, workspace, artifacts, extra, preflight, PR metadata)
    ├─ Build environment variables
    ├─ Build agent command (build_noninteractive_cmd)
    ├─ Build preflight clause (desktop, preflights)
    ├─ Launch container (docker run -d)
    ├─ Stream logs (docker logs -f)
    ├─ Poll container state every 0.75s
    ├─ Collect artifacts (collect_artifacts_from_container)
    ├─ Remove container (if auto_remove=True)
    └─ Call on_done(exit_code, error, artifacts)
           ↓
ui/main_window_task_events.py::_on_bridge_done() [lines 232-247]
    └─ _on_task_done() [lines 346-373]
          ├─ Set task.status = "done" | "failed" (based on exit_code)
          ├─ Update UI, save state, beep
          └─ _try_start_queued_tasks()
```

### 2. Current Error Detection (ALREADY IMPLEMENTED)

**Primary signals:**
1. **Process Exit Code** - `agent_worker.py:467` - `exit_code = int(final_state.get("ExitCode") or 0)`
2. **Container State** - Polled every 0.75s: `if status in {"exited", "dead"}: break`
3. **Python Exceptions** - Caught in try/except: `on_done(1, str(exc), [])`
4. **User Stop Signal** - `request_stop()` → `docker stop` or `docker kill`

**NOT Implemented (CORRECT per requirements):**
- ❌ Timeout detection
- ❌ Hang detection
- ❌ "No output" detection
- ❌ Resource exhaustion detection

### 3. Agent Selection Current State

**Data Model (COMPLETE):**
```python
# environments/model.py:48-66
@dataclass
class AgentInstance:
    agent_id: str           # Unique ID within environment
    agent_cli: str          # "codex", "claude", "copilot", "gemini"
    config_dir: str = ""
    cli_flags: str = ""

@dataclass
class AgentSelection:
    agents: list[AgentInstance] = []
    selection_mode: str = "round-robin"  # or "fallback"
    agent_fallbacks: dict[str, str] = {}  # Maps agent_id → fallback_agent_id
```

**UI (COMPLETE):** `ui/pages/environments_agents.py` - 529 lines, full table UI

**Execution (MISSING):**
```python
# main_window_tasks_agent.py:154-165
agent_cli = "codex"
if env and env.agent_selection:
    # TODO: Implement agent selection logic
    pass
agent_cli = normalize_agent(self._settings_data.get("use", "codex"))
```

**This is where the supervisor will integrate!**

---

## Proposed Supervisor State Machine

### State Machine Diagram

```
                     ┌────────────────┐
                     │   INITIALIZE   │
                     └────────┬───────┘
                              │ Build agent chain from agent_selection
                              │ Initialize retry counters
                              ↓
                     ┌────────────────┐
                     │     LAUNCH     │◄─────────┐
                     └────────┬───────┘          │
                              │                  │ RETRY
                              │ Create container │ (max 3x per agent)
                              ↓                  │
                     ┌────────────────┐          │
                     │      RUN       │          │
                     └────────┬───────┘          │
                              │                  │
                              │ Wait for exit    │
                              ↓                  │
                     ┌────────────────┐          │
                     │  DETECT EXIT   │          │
                     └────────┬───────┘          │
          ┌──────────────────┼──────────────────┼──────┐
          ↓                  ↓                  ↓      │
    ┌──────────┐      ┌──────────────┐    ┌──────────┐│
    │  EXIT=0  │      │ EXIT != 0    │    │CONTAINER ││
    │ SUCCESS  │      │   (ERROR)    │    │  CRASH   ││
    └────┬─────┘      └──────┬───────┘    └──────┬───┘│
         │                   │                   │    │
         │                   ↓                   │    │
         │          ┌──────────────────┐         │    │
         │          │ CLASSIFY ERROR   │◄────────┘    │
         │          └────────┬─────────┘              │
         │    ┌──────────────┼──────────────┐         │
         │    ↓              ↓              ↓         │
         │  RETRYABLE    RATE_LIMIT    AGENT_FAILURE │
         │    │              │              │         │
         │    │ retry_count[agent] < 3?    │         │
         │    │     YES ─────────────────────┘ RETRY  │
         │    │     NO ↓                               │
         │    └────────┼─► Has fallback agent?        │
         │             │      YES ↓                    │
         │             │    ┌──────────────────┐       │
         │             │    │  SWITCH AGENT    │       │
         │             │    └────────┬─────────┘       │
         │             │             │                 │
         │             │             └─► LAUNCH (fallback agent)
         │             │      NO ↓
         │             ↓         ↓
         │       ┌─────────────────┐
         │       │  TERMINAL FAIL  │
         │       └────────┬────────┘
         ↓                ↓
    ┌────────────────────────┐
    │      COMPLETE          │
    └────────┬───────────────┘
             │
             └─► Return (exit_code, error, artifacts, metadata)
```

### State Definitions

**INITIALIZE**
- Parse agent_selection, build agent chain [primary, fallback1, fallback2, ...]
- Initialize retry_count = {} (dict[agent_id, int])

**LAUNCH**
- Get current agent from chain
- Create DockerRunnerConfig with agent's CLI and flags
- Start DockerAgentWorker

**RUN**
- Stream logs to UI
- Wait for completion

**DETECT EXIT**
- Inspect exit_code and container state
- Transitions: exit_code==0 → SUCCESS | exit_code!=0 → CLASSIFY ERROR

**CLASSIFY ERROR**
- Scan logs for error patterns
- Return: RETRYABLE | RATE_LIMIT | AGENT_FAILURE | FATAL | CONTAINER_CRASH
- Logic: Check retry_count < 3 → RETRY | else check fallback → SWITCH or FAIL

**SWITCH AGENT**
- current_agent_index += 1
- Reset retry_count for new agent
- Log agent switch event

**COMPLETE**
- Collect artifacts, cleanup container
- Return metadata: agent_used, retry_count, fallback_count

### Error Classification Logic

```python
class ErrorType(Enum):
    RETRYABLE = "retryable"          # Network errors, transient failures
    RATE_LIMIT = "rate_limit"        # API rate limit (special backoff)
    AGENT_FAILURE = "agent_failure"  # Agent-specific failure (try fallback)
    FATAL = "fatal"                  # Unrecoverable (bad prompt, auth)
    CONTAINER_CRASH = "container_crash"  # OOMKilled, segfault

def classify_error(exit_code: int, container_state: dict, logs: list[str]) -> ErrorType:
    # Container crash (high priority)
    if container_state.get("OOMKilled", False):
        return ErrorType.CONTAINER_CRASH
    
    # Rate limit detection (scan last 100 log lines)
    rate_limit_patterns = [r"rate.?limit", r"429", r"too.?many.?requests", r"quota.?exceeded"]
    for line in logs[-100:]:
        for pattern in rate_limit_patterns:
            if re.search(pattern, line, re.IGNORECASE):
                return ErrorType.RATE_LIMIT
    
    # Exit code analysis
    if exit_code == 1:
        # Scan for fatal vs agent_failure vs retryable
        fatal_patterns = [r"authentication.?failed", r"invalid.?api.?key", r"permission.?denied"]
        agent_failure_patterns = [r"command.?not.?found", r"no such file.*codex"]
        
        for line in logs[-50:]:
            for pattern in fatal_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    return ErrorType.FATAL
            for pattern in agent_failure_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    return ErrorType.AGENT_FAILURE
        
        return ErrorType.RETRYABLE
    
    elif exit_code == 137:  # SIGKILL
        return ErrorType.CONTAINER_CRASH
    elif exit_code in {126, 127}:  # Command not found
        return ErrorType.AGENT_FAILURE
    else:
        return ErrorType.RETRYABLE
```

### Retry Strategy

```python
def calculate_backoff(retry_count: int, error_type: ErrorType) -> float:
    """Calculate backoff delay in seconds."""
    if error_type == ErrorType.RATE_LIMIT:
        delays = [60.0, 120.0, 300.0]  # 1m, 2m, 5m
    else:
        delays = [5.0, 15.0, 45.0]  # 5s, 15s, 45s
    
    return delays[min(retry_count, len(delays)-1)]
```

**Limits:**
- Max 3 retries per agent
- After 3 retries, switch to fallback agent (if available)
- After all agents exhausted, terminal failure

---

## Integration Points

### 1. New File: `agents_runner/execution/supervisor.py` (~250-300 lines)

```python
@dataclass
class SupervisorConfig:
    max_retries_per_agent: int = 3
    enable_fallback: bool = True
    backoff_base_seconds: float = 5.0
    rate_limit_backoff_base: float = 60.0

@dataclass
class SupervisorResult:
    exit_code: int
    error: str | None
    artifacts: list[str]
    metadata: dict[str, Any]  # agent_used, retry_count, fallback_count

class TaskSupervisor:
    """Supervises task execution with retry and fallback."""
    
    def __init__(
        self,
        config: DockerRunnerConfig,
        prompt: str,
        agent_selection: AgentSelection | None,
        supervisor_config: SupervisorConfig,
        on_state: Callable,
        on_log: Callable,
        on_retry: Callable[[int, str, float], None],
        on_agent_switch: Callable[[str, str], None],
    ):
        # Initialize agent chain, retry counters, stop event
        ...
    
    def run(self) -> SupervisorResult:
        """Run task with supervision."""
        self._initialize_agent_chain()
        
        while self._current_agent_index < len(self._agent_chain):
            agent = self._agent_chain[self._current_agent_index]
            result = self._try_agent(agent)
            
            if result.exit_code == 0:
                return result  # Success!
            
            error_type = classify_error(...)
            
            if error_type == ErrorType.FATAL:
                return result  # Unrecoverable
            
            retry_count = self._retry_counts.get(agent.agent_id, 0)
            if retry_count < self._supervisor_config.max_retries_per_agent:
                # Retry with backoff
                self._retry_counts[agent.agent_id] = retry_count + 1
                delay = calculate_backoff(retry_count, error_type)
                self._on_retry(retry_count + 1, agent.agent_cli, delay)
                self._wait_with_skip(delay)
                continue
            
            # Try fallback
            if self._current_agent_index + 1 < len(self._agent_chain):
                old_agent = agent.agent_cli
                self._current_agent_index += 1
                new_agent = self._agent_chain[self._current_agent_index].agent_cli
                self._on_agent_switch(old_agent, new_agent)
                continue
            
            # No fallback available
            return result
    
    def _initialize_agent_chain(self) -> None:
        """Build agent chain from agent_selection."""
        if not self._agent_selection or not self._agent_selection.agents:
            # Use default agent from config
            default_agent = AgentInstance(
                agent_id="default",
                agent_cli=self._config.agent_cli,
            )
            self._agent_chain = [default_agent]
            return
        
        # Build chain: [primary, fallback1, fallback2, ...]
        agents = list(self._agent_selection.agents)
        fallbacks = self._agent_selection.agent_fallbacks or {}
        
        chain = [agents[0]]  # Start with first agent
        current_id = agents[0].agent_id
        visited = {current_id}
        
        # Follow fallback chain
        while current_id in fallbacks:
            next_id = fallbacks[current_id]
            if next_id in visited:
                break  # Circular fallback
            next_agent = next((a for a in agents if a.agent_id == next_id), None)
            if not next_agent:
                break  # Invalid fallback
            chain.append(next_agent)
            visited.add(next_id)
            current_id = next_id
        
        self._agent_chain = chain
    
    def _try_agent(self, agent: AgentInstance) -> SupervisorResult:
        """Try executing task with given agent."""
        agent_config = self._build_agent_config(agent)
        
        worker = DockerAgentWorker(
            config=agent_config,
            prompt=self._prompt,
            on_state=self._on_state,
            on_log=self._on_log,
            on_done=self._on_worker_done,
        )
        
        worker.run()  # Blocking
        
        return SupervisorResult(
            exit_code=self._last_exit_code,
            error=self._last_error,
            artifacts=self._last_artifacts,
            metadata={
                "agent_used": agent.agent_cli,
                "agent_id": agent.agent_id,
                "retry_count": self._retry_counts.get(agent.agent_id, 0),
            },
        )
```

### 2. Modified File: `agents_runner/ui/bridges.py` (~20 lines changed)

```python
class TaskRunnerBridge(QObject):
    state = Signal(dict)
    log = Signal(str)
    done = Signal(int, object, list, dict)  # Added dict for metadata
    retry_attempt = Signal(int, str, float)  # retry_count, agent, delay
    agent_switched = Signal(str, str)  # from_agent, to_agent
    
    def __init__(
        self,
        task_id: str,
        config: DockerRunnerConfig,
        prompt: str = "",
        agent_selection: AgentSelection | None = None,
        mode: str = "codex",
    ) -> None:
        super().__init__()
        self.task_id = task_id
        
        if mode == "preflight":
            self._worker = DockerPreflightWorker(...)
        else:
            # Use supervisor for agent runs
            supervisor_config = SupervisorConfig(max_retries_per_agent=3)
            self._worker = TaskSupervisor(
                config=config,
                prompt=prompt,
                agent_selection=agent_selection,
                supervisor_config=supervisor_config,
                on_state=self.state.emit,
                on_log=self.log.emit,
                on_done=self._emit_done_with_metadata,
                on_retry=self.retry_attempt.emit,
                on_agent_switch=self.agent_switched.emit,
            )
    
    def _emit_done_with_metadata(self, exit_code: int, error: object, artifacts: list, metadata: dict) -> None:
        self.done.emit(exit_code, error, artifacts, metadata)
```

### 3. Modified File: `agents_runner/ui/main_window_tasks_agent.py` (~30 lines)

**Change agent selection logic (lines 154-165):**
```python
# Build agent selection from environment or settings
agent_selection: AgentSelection | None = None
if env and env.agent_selection:
    agent_selection = env.agent_selection
    if agent_selection.agents:
        agent_cli = agent_selection.agents[0].agent_cli
    else:
        agent_cli = normalize_agent(self._settings_data.get("use", "codex"))
else:
    agent_cli = normalize_agent(self._settings_data.get("use", "codex"))

# Pass agent_selection to bridge
bridge = TaskRunnerBridge(
    task_id=task_id,
    config=config,
    prompt=runner_prompt,
    agent_selection=agent_selection,  # NEW
    mode="codex",
)

# Connect new signals
bridge.retry_attempt.connect(self._on_bridge_retry_attempt)
bridge.agent_switched.connect(self._on_bridge_agent_switched)
```

### 4. Modified File: `agents_runner/ui/main_window_task_events.py` (~80 lines)

**Add signal handlers:**
```python
def _on_bridge_retry_attempt(self, retry_count: int, agent: str, delay: float) -> None:
    """Handle retry attempt signal from supervisor."""
    bridge = self.sender()
    if not isinstance(bridge, TaskRunnerBridge):
        return
    
    task = self._tasks.get(bridge.task_id)
    if task is None:
        return
    
    self._on_task_log(bridge.task_id, f"[supervisor] retry {retry_count}/3 with {agent} in {delay:.0f}s")
    task.status = f"retrying ({retry_count}/3)"
    self._update_task_ui(task)

def _on_bridge_agent_switched(self, from_agent: str, to_agent: str) -> None:
    """Handle agent switch signal from supervisor."""
    bridge = self.sender()
    if not isinstance(bridge, TaskRunnerBridge):
        return
    
    task = self._tasks.get(bridge.task_id)
    if task is None:
        return
    
    self._on_task_log(bridge.task_id, f"[supervisor] switching from {from_agent} to {to_agent} (fallback)")
    task.agent_cli = to_agent
    self._update_task_ui(task)

def _on_bridge_done(self, exit_code: int, error: object, artifacts: list, metadata: dict) -> None:
    """Handle task completion with metadata."""
    bridge = self.sender()
    if not isinstance(bridge, TaskRunnerBridge):
        return
    
    task = self._tasks.get(bridge.task_id)
    if task is None:
        return
    
    # Capture metadata
    agent_used = metadata.get("agent_used", "unknown")
    agent_id = metadata.get("agent_id", "")
    retry_count = metadata.get("retry_count", 0)
    
    task.agent_cli = agent_used
    task.agent_instance_id = agent_id
    if artifacts:
        task.artifacts = list(artifacts)
    
    if retry_count > 0:
        self._on_task_log(bridge.task_id, f"[supervisor] completed after {retry_count} retries")
    
    # Existing logic
    if bridge.gh_repo_root:
        task.gh_repo_root = bridge.gh_repo_root
    # ... etc
    
    self._on_task_done(bridge.task_id, exit_code, error)
```

### 5. Modified File: `agents_runner/docker/agent_worker.py` (~30 lines)

**Add restart capability:**
```python
def restart_container(self) -> bool:
    """Restart crashed container with same config.
    
    Returns True if restart successful, False otherwise.
    """
    if not self._container_id:
        return False
    
    try:
        state = _inspect_state(self._container_id)
        exit_code = state.get("ExitCode", 0)
        
        self._on_log(f"[supervisor] container crashed (exit {exit_code}), restarting...")
        
        # Remove crashed container
        try:
            _run_docker(["rm", "-f", self._container_id], timeout_s=10.0)
        except Exception:
            pass
        
        # Run again (creates fresh container)
        self.run()
        return True
    
    except Exception as e:
        self._on_log(f"[supervisor] restart failed: {e}")
        return False
```

### 6. Task Model Updates: `agents_runner/ui/task_model.py` (~5 lines)

```python
@dataclass
class Task:
    # ... existing fields ...
    agent_instance_id: str = ""  # Which specific agent instance ran
    retry_count: int = 0          # How many retries were needed
    fallback_used: bool = False   # Whether fallback agent was used
```

---

## Implementation Strategy

### Phase 1: Supervisor Core (Days 1-3)

**Coder:**
1. Create `agents_runner/execution/supervisor.py`
2. Implement ErrorType enum, SupervisorConfig, SupervisorResult
3. Implement TaskSupervisor class skeleton
4. Implement classify_error() and calculate_backoff()

**QA:**
- Review error classification patterns
- Test backoff calculation

### Phase 2: Error Classification (Days 3-4)

**Coder:**
1. Add comprehensive error patterns for all agents
2. Add container crash detection
3. Test with real log samples

**QA:**
- Test with real rate limit errors
- Test with auth failures
- Verify false positive rate

### Phase 3: Retry Logic (Days 4-5)

**Coder:**
1. Implement retry loop in TaskSupervisor.run()
2. Implement wait_with_skip()
3. Add retry UI feedback

**QA:**
- Test max 3 retries per agent
- Test exponential backoff
- Test user skip functionality

### Phase 4: Fallback Logic (Days 5-6)

**Coder:**
1. Implement _initialize_agent_chain()
2. Implement agent switching
3. Add fallback UI feedback

**QA:**
- Test fallback chain following
- Verify task-scoped fallback
- Test exhausting all agents

### Phase 5: Container Restart (Days 6-7)

**Coder:**
1. Add restart_container() to DockerAgentWorker
2. Integrate with supervisor
3. Limit to 1 restart per task

**QA:**
- Test OOM crash restart
- Verify restart limit

### Phase 6: Integration (Days 7-9)

**Coder:**
1. Wire supervisor into UI (bridges, task_events, main_window_tasks_agent)
2. Update task model and persistence
3. Test end-to-end

**QA:**
- Test complete flow with all agents
- Test with different fallback configs
- Verify UI updates correctly

### Phase 7: Polish (Days 9-10)

**Coder:**
1. Add user controls ("Retry Now", "Cancel Retry")
2. Improve log messages
3. Add tooltips

**Auditor:**
- Final code review
- Security review
- Performance review

---

## Risk Analysis

### High Risk

**1. Breaking Existing Execution**
- Mitigation: Keep DockerAgentWorker unchanged, add feature flag for rollback
- Rollback: `AGENTS_RUNNER_USE_SUPERVISOR=false`

**2. Infinite Retry Loops**
- Mitigation: Hard limit 3 retries per agent, max 30 total attempts
- Implementation: Track `self._total_attempts`

**3. Agent Chain Configuration Errors**
- Mitigation: Validate chain during init, detect circular fallbacks, fallback to single agent

### Medium Risk

**4. Error Classification False Positives**
- Mitigation: Conservative patterns, user can cancel, telemetry tracking

**5. Container Restart Failing**
- Mitigation: Force remove crashed container, timeout on restart, fallback to terminal failure

**6. State Persistence Race Conditions**
- Mitigation: Existing throttled save mechanism, atomic writes

### Low Risk

**7. UI Responsiveness During Backoff**
- Mitigation: Show countdown, "Retry Now" button, "Cancel" button

**8. Memory Leaks**
- Mitigation: Workers are short-lived, Python GC handles cleanup

---

## File Modifications Summary

### New Files
| File | Lines | Purpose |
|------|-------|---------|
| `agents_runner/execution/supervisor.py` | 250-300 | Core supervisor logic |

### Modified Files
| File | Lines Changed | Modifications |
|------|---------------|---------------|
| `agents_runner/ui/bridges.py` | ~20 | Add signals, use supervisor |
| `agents_runner/ui/main_window_tasks_agent.py` | ~30 | Pass agent_selection |
| `agents_runner/ui/main_window_task_events.py` | ~80 | Add signal handlers |
| `agents_runner/ui/task_model.py` | ~5 | Add retry fields |
| `agents_runner/docker/agent_worker.py` | ~30 | Add restart method |
| `agents_runner/persistence.py` | ~10 | Serialize new fields |

**Total:** +250-300 new lines, ~175 modified lines

---

## Success Criteria

### Functional Requirements
- ✅ Tasks retry up to 3 times per agent on retryable errors
- ✅ Agent fallback works when primary exhausts retries
- ✅ Container crashes trigger restart (once)
- ✅ No hang detection or timeout mechanisms
- ✅ Task-scoped fallback (doesn't change defaults)
- ✅ Clear UI feedback for retry/fallback actions

### Non-Functional Requirements
- ✅ No breaking changes to existing functionality
- ✅ Backward compatible state persistence
- ✅ Supervisor adds <500ms overhead per attempt
- ✅ Memory usage stable (no leaks)
- ✅ All new code under 300 lines per file

---

## Implementation Checklist

### Coder Checklist
**Phase 1:**
- [ ] Create `agents_runner/execution/supervisor.py`
- [ ] Implement ErrorType, SupervisorConfig, SupervisorResult
- [ ] Implement TaskSupervisor skeleton
- [ ] Implement classify_error() and calculate_backoff()

**Phase 2:**
- [ ] Add error patterns for all agents
- [ ] Add container crash detection
- [ ] Test with real logs

**Phase 3:**
- [ ] Implement retry loop
- [ ] Implement wait_with_skip()
- [ ] Add retry UI

**Phase 4:**
- [ ] Implement agent chain building
- [ ] Implement agent switching
- [ ] Add fallback UI

**Phase 5:**
- [ ] Add restart_container()
- [ ] Integrate with supervisor
- [ ] Limit restart attempts

**Phase 6:**
- [ ] Wire supervisor into UI
- [ ] Update task model
- [ ] Update persistence
- [ ] Test end-to-end

**Phase 7:**
- [ ] Add user controls
- [ ] Improve log messages
- [ ] Add tooltips
- [ ] Final testing

### QA Checklist
- [ ] Test max 3 retries per agent
- [ ] Test exponential backoff
- [ ] Test fallback chain
- [ ] Test container restart
- [ ] Test error classification
- [ ] Integration testing
- [ ] Regression testing

### Auditor Checklist
- [ ] Code review
- [ ] Architecture review
- [ ] Security review
- [ ] Documentation review

---

## Next Steps for Coder

1. **Read this document thoroughly**
2. **Create supervisor.py skeleton** - Start with Phase 1
3. **Implement error classification first** - Foundation for all logic
4. **Test incrementally** - Don't wait until end
5. **Keep existing code stable** - Minimal changes to agent_worker.py
6. **Add feature flag for rollback** - `AGENTS_RUNNER_USE_SUPERVISOR=false`
7. **Log everything clearly** - Help debugging and user understanding

**Recommended Order:**
1. Error classification (classify_error, calculate_backoff)
2. Agent chain building (_initialize_agent_chain)
3. Basic supervision loop (run method, no retry)
4. Retry logic (with backoff)
5. Fallback logic (agent switching)
6. Container restart
7. UI integration
8. Polish

**Daily Milestones:**
- Day 1: Error classification complete
- Day 3: Supervision loop working (no retry)
- Day 5: Retry working
- Day 6: Fallback working
- Day 7: Container restart working
- Day 9: UI integration complete
- Day 10: Polish and testing

---

**Document Status:** READY FOR IMPLEMENTATION  
**Last Updated:** 2025-01-07  
**Author:** Auditor Mode (AI)  
**Next Action:** Coder begins Phase 1 (Supervisor Core)
