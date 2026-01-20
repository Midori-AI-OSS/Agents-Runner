# Task 001: Add Completion Marker Writing to Interactive Container

## Objective
Write a JSON completion marker to `/tmp/agents-artifacts/interactive-exit.json` inside the interactive container before it exits.

## Context
- Interactive containers are auto-removed on exit, so we need a host-visible completion signal
- The marker should be written to the mounted staging directory so it survives container removal
- Host path: `~/.midoriai/agents-runner/artifacts/<task_id>/staging/interactive-exit.json`

## Requirements
1. Modify the interactive container script to include an `EXIT` trap
2. The trap should write a JSON file with this structure:
```json
{
  "task_id": "<task_id>",
  "container_name": "agents-runner-tui-it-<task_id>",
  "exit_code": <exit_code>,
  "started_at": "<ISO8601_timestamp>",
  "finished_at": "<ISO8601_timestamp>",
  "reason": "process_exit"
}
```

## Location to Change
- File: `agents_runner/ui/main_window_tasks_interactive_docker.py`
- Function: `_build_host_shell_script` or container entrypoint generation

## Acceptance Criteria
- [x] Container script includes a shell trap that writes the completion marker on EXIT
- [x] Marker is written to `/tmp/agents-artifacts/interactive-exit.json` in-container
- [x] JSON includes all required fields: task_id, container_name, exit_code, started_at, finished_at, reason
- [x] Marker file persists on host after container is removed
- [ ] **Consumer code reads and processes the completion marker**
- [ ] **Tests verify marker is written and consumed correctly**
- [ ] **Integration with task completion workflow**

## Notes
- Use shell trap: `trap 'write_completion_marker' EXIT`
- Capture `$?` for exit_code in the trap
- Use `date -u +"%Y-%m-%dT%H:%M:%SZ"` for ISO8601 timestamps

## Completion Note (Previous)
Implemented in commit fe8c195. Added:
- `_build_completion_marker_script()` function to generate EXIT trap shell code
- Staging directory creation and mount at `/tmp/agents-artifacts`
- Completion marker writes all required JSON fields
- Marker persists on host after container auto-removal

---

## AUDIT FEEDBACK - 2026-01-20 (Audit ID: 0ce91628)

**Status:** RETURNED TO WIP - Implementation Incomplete

### Critical Issue
The marker **writing** is correctly implemented, but there is **no consumer code** to read or process the marker file. The completion signal is written but never used by the application.

### Required Actions Before Completion
1. **Implement Consumer Code**
   - Add code to read `interactive-exit.json` after container exit
   - Parse and validate the JSON marker
   - Use the marker data (exit_code, timestamps) in task completion logic
   - Integrate with the existing task finish workflow

2. **Testing**
   - Test that marker is written correctly in real container execution
   - Verify marker persists after container auto-removal
   - Validate JSON parsing and error handling

3. **Clarify Architecture**
   - Document why both `interactive-finish-*.txt` and `interactive-exit.json` exist
   - Explain the relationship between these two mechanisms
   - Consider consolidating if redundant

4. **Update Documentation**
   - Add comments explaining marker consumption flow
   - Document where marker is read and processed
   - Update task acceptance criteria to include consumer implementation

### Reference
See full audit report: `/tmp/agents-artifacts/0ce91628-audit-task-001.audit.md`
