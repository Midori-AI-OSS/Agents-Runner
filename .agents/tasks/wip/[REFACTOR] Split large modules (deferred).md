# Task: Split Large Modules (Deferred - Low Priority)

## Goal

Address soft limit (300 lines) violations in large modules. This is a lower priority refactoring task focused on maintainability.

## Rule Reference

**AGENTS.MD Section:** "Development Basics"
> "Avoid monolith files: **soft max 300 lines per file**, **hard max 600 lines per file** (split modules/classes when approaching the soft limit)."

**Status:** 8 files exceed soft limit but are under hard limit (600 lines).

## Scope

Review and potentially split these large modules:

1. `agents_runner/execution/supervisor.py`: 958 lines
2. `agents_runner/ui/main_window_task_events.py`: 785 lines
3. `agents_runner/ui/main_window_tasks_agent.py`: 744 lines
4. `agents_runner/ui/main_window_tasks_interactive_docker.py`: 707 lines
5. `agents_runner/ui/main_window_settings.py`: 643 lines
6. `agents_runner/ui/main_window_task_recovery.py`: 637 lines
7. `agents_runner/docker/preflight_worker.py`: 512 lines
8. `agents_runner/environments/serialize.py`: 511 lines

## Non-Goals

- This is NOT an immediate priority (all files under hard limit)
- Do not split files unless it improves maintainability
- Do not split cohesive UI modules if it reduces readability
- Do not change business logic

## Acceptance Criteria

- [ ] Review each file for natural split boundaries
- [ ] Determine if splitting improves or hurts maintainability
- [ ] For files to split: create focused sub-modules
- [ ] Each new module under 600 lines (hard limit)
- [ ] Each new module ideally under 300 lines (soft limit)
- [ ] All functionality preserved
- [ ] `uv run ruff format .` and `uv run ruff check .` pass
- [ ] `uv build` succeeds

## Priority Order

### High Priority (Close to Hard Limit)

1. **`execution/supervisor.py` (958 lines)**
   - **Impact:** High (core orchestration)
   - **Suggested split:**
     - `supervisor_core.py`: Main class and lifecycle
     - `supervisor_events.py`: Event handling
     - `supervisor_tasks.py`: Task management

### Medium Priority (Large but Cohesive)

2. **`ui/main_window_task_events.py` (785 lines)**
   - **Assessment needed:** May be cohesive event handler
   - **Split if:** Distinct event categories can be separated

3. **`ui/main_window_tasks_agent.py` (744 lines)**
   - **Assessment needed:** Agent task handling
   - **Split if:** Natural boundaries between agent operations

4. **`ui/main_window_tasks_interactive_docker.py` (707 lines)**
   - **Assessment needed:** Docker-specific UI logic
   - **Split if:** Can separate Docker operations from UI updates

### Low Priority (Just Over Soft Limit)

5. **`ui/main_window_settings.py` (643 lines)**
6. **`ui/main_window_task_recovery.py` (637 lines)**
7. **`docker/preflight_worker.py` (512 lines)**
8. **`environments/serialize.py` (511 lines)**

## Verification Commands

**Check file sizes:**
```bash
wc -l agents_runner/**/*.py | sort -n | awk '$1 > 300 {print}' | tail -n 15
# Shows files over soft limit

wc -l agents_runner/**/*.py | sort -n | awk '$1 > 600 {print}'
# Should return: ZERO (all under hard limit)
```

**After splitting:**
```bash
# Verify no files over hard limit
wc -l agents_runner/**/*.py | sort -n | awk '$1 > 600 {print}'
# Expected: NO OUTPUT

# Count files over soft limit (should decrease)
wc -l agents_runner/**/*.py | sort -n | awk '$1 > 300 {print}' | wc -l
# Expected: Fewer than 8
```

## Deferral Justification

**Why Low Priority:**
- All files under hard limit (600 lines) ✅
- Many are cohesive UI modules where splitting may hurt readability
- No immediate functional impact
- Other compliance issues are higher priority

**When to Prioritize:**
- When actively modifying these modules
- If modules continue growing toward hard limit
- If maintainability issues emerge

## Definition of Done

**For Deferred Status:**
- Task documented and filed in wip/
- Clear acceptance criteria established
- Can be picked up when prioritized

**For Completion (if executed):**
- Selected modules split per acceptance criteria
- All verification commands pass
- Committed with message: `[REFACTOR] Split large modules to improve maintainability`
- Version bumped in `pyproject.toml` (TASK +1)

---

**Current Status:** DEFERRED - Address higher priority compliance issues first.
