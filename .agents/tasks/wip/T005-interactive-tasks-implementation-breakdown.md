# T005: Interactive Tasks Implementation Breakdown

**Priority:** MEDIUM  
**Type:** Task Master / Planning  
**Design Doc:** `.agents/design/interactive-task-lifecycle-redesign.md`

---

## Purpose

This file breaks down the comprehensive interactive tasks lifecycle redesign into actionable, focused implementation tasks. Each task is independently executable and properly scoped.

---

## Design Document Summary

The design document (`.agents/design/interactive-task-lifecycle-redesign.md`) proposes a complete redesign of interactive task lifecycle:

**Current Problem:** Interactive tasks use a host shell script that owns `docker run`, making restart recovery and finalization unreliable.

**Proposed Solution:** App owns container lifecycle, terminal only attaches for user interaction.

**Key Changes:**
1. App starts container (detached) with stable name
2. Terminal attaches to running container (not "runs" it)
3. Completion marker survives container auto-remove
4. Restart recovery reads marker from host staging directory
5. Finalization works without container (uses staging dir)

---

## Task Breakdown

**NOTE:** Task numbers below have been renumbered to T010-T023 to avoid conflicts with existing duplicate logs tasks T006-T009.

### T010: Container Launch Refactor (Core Infrastructure)
**(Previously numbered T006 in this document)**

**Priority:** HIGH  
**Estimated LOC:** 150-200  
**Files:** `agents_runner/ui/main_window_tasks_interactive_docker.py`

**Scope:**
- Refactor container launch to use `docker run --rm -dit` (detached, interactive, TTY)
- Generate and write `.container-entrypoint.sh` to staging directory before launch
- Mount host staging directory to `/tmp/agents-artifacts` in container
- Pass environment variables (API keys, task ID) via `docker run -e`
- Update container naming to use stable names: `agents-runner-tui-it-<task_id>`

**Acceptance Criteria:**
- Container starts successfully in detached mode
- Container has stable, predictable name
- Staging directory mounted and writable from container
- Entrypoint script executes correctly
- Container auto-removes on exit (--rm flag)

**Dependencies:** None (foundational task)

---

### T011: Entrypoint Script Generation
**(Previously numbered T007 in this document)**

**Priority:** HIGH  
**Estimated LOC:** 80-100  
**Files:** `agents_runner/ui/main_window_tasks_interactive_docker.py`

**Scope:**
- Create function to generate `.container-entrypoint.sh` bash script
- Script must write completion marker on EXIT trap
- Script records: task_id, exit_code, timestamps, container_name
- Script launches agent CLI and waits for completion
- Make script executable (`chmod +x`) after writing

**Completion Marker Format:**
```json
{
  "task_id": "abcd1234",
  "container_name": "agents-runner-tui-it-abcd1234",
  "exit_code": 0,
  "started_at": "2024-01-18T10:00:00Z",
  "finished_at": "2024-01-18T10:05:00Z",
  "reason": "process_exit"
}
```

**Acceptance Criteria:**
- Script generated correctly with proper bash syntax
- EXIT trap writes completion marker before exit
- Agent CLI launches and runs as expected
- Completion marker created in `/tmp/agents-artifacts/interactive-exit.json`

**Dependencies:** T010 (requires staging mount and entrypoint execution)

---

### T012: Terminal Attach Mechanism
**(Previously numbered T008 in this document)**

**Priority:** HIGH  
**Estimated LOC:** 100-120  
**Files:** `agents_runner/ui/main_window_tasks_interactive_docker.py`

**Scope:**
- Replace "terminal runs docker run" with "terminal attaches to container"
- Detect available terminal emulator (konsole, gnome-terminal, xfce4-terminal, xterm)
- Launch terminal with `docker attach <container_name>` command
- Add UI "Attach Terminal" button for interactive tasks in running state
- Handle terminal emulator not found (show manual attach command)

**Terminal Detection Priority:**
1. `konsole --hold -e` (KDE)
2. `gnome-terminal --wait --` (GNOME)
3. `xfce4-terminal --hold -e` (XFCE)
4. `xterm -hold -e` (Fallback)

**Acceptance Criteria:**
- Terminal opens with attached session to running container
- Closing terminal does NOT kill container
- User can reattach via "Attach Terminal" button
- Graceful fallback if no terminal emulator found

**Dependencies:** T010 (requires detached container)

---

### T013: Restart Recovery for Interactive Tasks
**(Previously numbered T009 in this document)**

**Priority:** HIGH  
**Estimated LOC:** 120-150  
**Files:** `agents_runner/ui/main_window_task_recovery.py`, `agents_runner/ui/main_window_persistence.py`

**Scope:**
- On app startup, check for completion marker in staging directory
- If marker exists: parse exit code, set task status, queue finalization
- If no marker but container running: resume log tail, show "Attach" button
- If no marker and no container: mark as "unknown" with clear error

**Recovery Logic:**
```python
def _recover_interactive_v2_task(task: Task):
    marker_path = staging_dir / "interactive-exit.json"
    if marker_path.exists():
        # Read marker, set status, finalize
    elif container_exists_and_running(task.container_id):
        # Resume log tail, enable reattach
    else:
        # Mark unknown, best-effort finalization
```

**Acceptance Criteria:**
- Task completed while UI closed → reopening finalizes correctly
- Task still running → shows as running with reattach option
- Task container missing → marked as unknown with helpful error

**Dependencies:** T010, T011 (requires completion marker)

---

### T014: Docker Wait Monitor (Completion Detection)
**(Previously numbered T010 in this document)**

**Priority:** HIGH  
**Estimated LOC:** 80-100  
**Files:** `agents_runner/ui/main_window_tasks_interactive_docker.py`

**Scope:**
- Start background thread running `docker wait <container_name>` after container launch
- Thread blocks until container exits, then reads completion marker
- If marker exists, use it; else use `docker wait` exit code as fallback
- Emit signal to UI with completion status
- Handle SIGKILL case (exit_code=137, no marker)

**Thread Logic:**
```python
def _wait_for_container_exit(container_name: str, task_id: str):
    result = subprocess.run(["docker", "wait", container_name], capture_output=True)
    exit_code = int(result.stdout.strip())
    
    # Try to read completion marker
    marker = read_marker_if_exists(task_id)
    if marker:
        emit_completion(task_id, marker)
    else:
        emit_completion_fallback(task_id, exit_code)
```

**Acceptance Criteria:**
- Container exit detected immediately (no polling delay)
- Completion marker read and parsed correctly
- Fallback to `docker wait` exit code if marker missing
- No resource leaks (thread terminates cleanly)

**Dependencies:** T011 (requires completion marker)

---

### T015: Log Tail Integration for Interactive Tasks
**(Previously numbered T011 in this document)**

**Priority:** MEDIUM  
**Estimated LOC:** 60-80  
**Files:** `agents_runner/ui/main_window_task_recovery.py`

**Scope:**
- Start `docker logs -f` for interactive tasks immediately after container launch
- Integrate with existing `_ensure_recovery_log_tail` mechanism
- Stop log tail when container exits
- Handle restart scenario: resume log tail if container still running

**Acceptance Criteria:**
- Logs appear in UI for interactive tasks
- Log tail stops cleanly on container exit
- Restart recovery resumes log tail if container running
- No duplicate logs (coordinate with duplicate logs fix tasks T006-T009)

**Dependencies:** T010 (requires container launch), duplicate logs fix (T006-T009)

---

### T016: Finalization Without Container Dependency
**(Previously numbered T012 in this document)**

**Priority:** HIGH  
**Estimated LOC:** 100-120  
**Files:** `agents_runner/ui/main_window_task_recovery.py`

**Scope:**
- Update `_finalize_task_worker` to collect artifacts from HOST staging directory (not container)
- Remove dependency on `docker cp` for interactive tasks
- Encrypt and bundle files from staging directory
- Clean up staging directory after successful finalization
- Handle missing staging directory gracefully

**Finalization Steps:**
1. Check if staging directory exists
2. Read completion marker for metadata
3. Collect all files in staging directory
4. Encrypt and create artifact tarball
5. Optionally delete staging directory after 24h
6. Prompt for PR creation if enabled
7. Set `finalization_state="done"`

**Acceptance Criteria:**
- Finalization works even when container is removed
- Artifacts collected from host staging directory
- Encryption and bundling successful
- Staging directory cleaned up after finalization
- PR prompt appears if enabled

**Dependencies:** T011, T013 (requires completion marker and recovery logic)

---

### T017: Migration Plan for Existing Interactive Tasks
**(Previously numbered T013 in this document)**

**Priority:** LOW  
**Estimated LOC:** 50-70  
**Files:** `agents_runner/ui/main_window_task_recovery.py`, `agents_runner/ui/task_model.py`

**Scope:**
- Add `interactive_version: int` field to Task model (1=old, 2=new)
- On app startup, reconcile old-style interactive tasks
- Mark old tasks as "unknown" with migration message if still running
- Leave completed old tasks as-is (historical data)
- New interactive tasks always use version 2

**Migration Logic:**
```python
def _migrate_interactive_task(task: Task):
    if task.interactive_version == 1 and task.is_active():
        task.status = "unknown"
        task.status_message = "Please restart task (old format, app updated)"
    # Leave completed v1 tasks alone
```

**Acceptance Criteria:**
- Old interactive tasks detected and marked appropriately
- User sees clear message about why task marked unknown
- New tasks always use version 2 lifecycle
- No crashes or errors during migration

**Dependencies:** T010-T016 (all core infrastructure must be complete)

---

### T018: Testing and Validation Script
**(Previously numbered T014 in this document)**

**Priority:** MEDIUM  
**Estimated LOC:** 150-200  
**Files:** `.agents/tests/test-interactive-lifecycle.sh` (new)

**Scope:**
- Create comprehensive test script covering all scenarios
- Test 1: Basic lifecycle (start, attach, exit, finalize)
- Test 2: Restart recovery (container running)
- Test 3: Restart recovery (container exited)
- Test 4: Edge case (SIGKILL)
- Test 5: Edge case (manual docker rm)

**Test Script Structure:**
```bash
#!/bin/bash
# Test 1: Basic lifecycle
echo "Test 1: Basic interactive task lifecycle"
# ... test steps

# Test 2: Restart recovery (running)
echo "Test 2: Restart recovery - container running"
# ... test steps

# etc.
```

**Acceptance Criteria:**
- All 5 test scenarios documented and executable
- Each test has clear pass/fail criteria
- Test output logged to `/tmp/agents-artifacts/interactive-tests.log`
- Tests can run independently or as suite

**Dependencies:** T010-T017 (requires complete implementation)

---

## Task Dependency Graph

```
T010 (Container Launch)
  ├─> T011 (Entrypoint Script)
  │     └─> T013 (Restart Recovery)
  │           └─> T016 (Finalization)
  ├─> T012 (Terminal Attach)
  ├─> T014 (Docker Wait Monitor)
  └─> T015 (Log Tail Integration)
            └─> T016 (Finalization)

T017 (Migration) depends on ALL above

T018 (Testing) depends on T010-T017 complete
```

**Suggested Execution Order:**
1. T010 (foundational)
2. T011 (enables completion detection)
3. T014 (completion detection)
4. T012 (user interaction)
5. T013 (restart recovery)
6. T015 (logging)
7. T016 (finalization)
8. T017 (migration)
9. T018 (testing)

---

## Rollback Plan

If issues arise during implementation:

**Phase 1 Rollback:** (T010-T012)
- Add feature flag: `interactive_tasks_use_app_lifecycle: bool = False`
- Revert to old script-based approach
- Users can toggle in settings

**Phase 2 Rollback:** (T013-T016)
- Keep new container launch but disable restart recovery
- Fall back to marking interactive as "unknown" on restart

**Phase 3 Rollback:** (All)
- Complete revert to old implementation
- Document known issues in release notes

---

## Success Metrics

After full implementation, these should be true:

1. **No stuck tasks:** Interactive tasks finalize correctly across app restarts
2. **No container leaks:** All interactive containers removed after exit
3. **No artifact loss:** All artifacts collected even if container removed
4. **Clear UX:** Users can reattach to running tasks via UI button
5. **Graceful degradation:** Missing terminal emulator doesn't crash app

---

## Notes

- Total estimated LOC: 900-1100 across all tasks
- Estimated implementation time: 3-4 full agent runs (if parallelized)
- High-priority tasks (T010-T014, T016) should be done first
- T018 (testing) should be done last to validate entire system
- **Task numbers updated:** Previous T006-T014 renumbered to T010-T018 to avoid conflicts with duplicate logs bug tasks (T006-T009)

---

**Task Master Action Required:**
1. Review this breakdown
2. Create individual task files (T010-T018) if approved
3. Assign priority and order
4. Move to appropriate queues based on dependencies
