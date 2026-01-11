# Git Metadata Requirements - Task Overview

## Summary

This document outlines three tasks for improving git metadata handling in git-locked environments. The tasks build on the existing GitHub context system (v2) and recent git metadata persistence work (commit ed8e55d).

## Background

### Current System State

**Git Metadata Persistence** (Implemented: Jan 11, 2026)
- Tasks have optional `git: dict[str, object] | None` field
- Populated by `derive_task_git_metadata()` at key lifecycle points
- Persisted in task JSON files
- Contains: repo_url, branches, PR info, commit SHA, etc.

**GitHub Context System** (Implemented: v2 schema)
- V2 JSON files with repository metadata
- Created for git-locked and folder-locked git repos
- Mounted at `/tmp/github-context-{task_id}.json`
- Updated after clone for git-locked tasks
- Source of truth for git metadata derivation

**PR Creation** (Existing)
- Auto PR for git-locked tasks after completion
- Manual override PR for folder-locked tasks
- Basic error handling via `GhManagementError`

### Gaps Identified

1. **No validation** - Git-locked tasks can complete without git metadata
2. **No repair** - Old tasks missing metadata are never backfilled
3. **Poor UX** - PR creation errors are unclear and not actionable

## Task Dependencies

```
Task 1 (Required Metadata)
    ↓
Task 2 (Backfill & Repair) ← depends on Task 1 validation
    ↓
Task 3 (Reliable PR Flow) ← can be done in parallel with 1 & 2
```

**Recommended Order:**
1. Start with Task 1 (foundation)
2. Then Task 2 (builds on validation)
3. Task 3 in parallel or after (independent improvement)

## Task 1: Make Git Metadata Required

**Goal:** Ensure all git-locked tasks have non-null git metadata

**Key Changes:**
- Add validation after `derive_task_git_metadata()` calls
- Log warnings for missing metadata
- Don't fail tasks, but mark status clearly
- Add helper method `Task.requires_git_metadata()`

**Files:**
- `agents_runner/ui/main_window_task_events.py` (validation)
- `agents_runner/ui/task_git_metadata.py` (validator function)
- `agents_runner/ui/task_model.py` (helper method)

**Effort:** Small (< 200 lines)
**Risk:** Low (validation only, no schema changes)

## Task 2: Backfill and Repair Git Metadata

**Goal:** Automatically detect and repair tasks missing metadata

**Key Changes:**
- Create `task_repair.py` module with repair function
- Repair strategies: GitHub context → task fields → environment repo
- Bulk repair on startup for all incomplete tasks
- Manual "Repair Metadata" command in UI

**Files:**
- `agents_runner/ui/task_repair.py` (new, core logic)
- `agents_runner/ui/main_window_persistence.py` (startup repair)
- `agents_runner/ui/pages/task_details.py` (manual repair UI)
- `agents_runner/ui/main_window.py` (wire up UI)

**Effort:** Medium (300-400 lines)
**Risk:** Medium (modifies task files, needs careful testing)

## Task 3: Reliable Create Pull Request Flow

**Goal:** Robust PR creation with validation, retries, and clear feedback

**Key Changes:**
- Pre-flight validation (repo, remote, gh CLI, existing PR)
- Progressive status updates (6 steps with logging)
- Enhanced error messages (user-friendly, actionable)
- Retry logic for network failures (3 attempts, exponential backoff)
- Cancel button for in-progress PR creation
- Detect and handle existing PRs gracefully

**Files:**
- `agents_runner/gh/pr_validation.py` (new, validation functions)
- `agents_runner/gh/pr_retry.py` (new, retry logic)
- `agents_runner/ui/main_window_tasks_interactive_finalize.py` (improved worker)
- `agents_runner/ui/main_window_task_review.py` (manual PR improvements)
- `agents_runner/gh/task_plan.py` (helper extraction)
- `agents_runner/ui/pages/task_details.py` (cancel button)

**Effort:** Large (500-600 lines)
**Risk:** Medium (changes critical PR flow, needs thorough testing)

## Architecture Notes

### Current File Structure

```
agents_runner/
├── gh/
│   ├── task_plan.py          # PR creation core (Task 3)
│   ├── git_ops.py            # Git operations
│   ├── gh_cli.py             # GitHub CLI wrapper
│   └── errors.py             # GhManagementError
├── environments/
│   ├── git_operations.py     # Git info extraction (Task 2)
│   └── model.py              # Environment with gh_management_locked
├── pr_metadata.py            # GitHub context v2 (used by Task 2)
├── persistence.py            # Task serialization (has git field)
└── ui/
    ├── task_model.py         # Task with git field (Task 1)
    ├── task_git_metadata.py  # derive_task_git_metadata (Task 1)
    ├── main_window_task_events.py      # Task lifecycle (Task 1)
    ├── main_window_persistence.py      # Load/save (Task 2)
    └── pages/
        └── task_details.py   # UI (Task 2, Task 3)
```

### New Files to Create

```
agents_runner/
├── gh/
│   ├── pr_validation.py      # Task 3
│   └── pr_retry.py           # Task 3
└── ui/
    └── task_repair.py        # Task 2
```

## Testing Strategy

### Unit Tests (Not Required per AGENTS.md)
- Task metadata validation logic
- Repair strategies
- PR pre-flight checks
- Retry logic

### Integration Tests
- End-to-end PR creation flow
- Startup with missing metadata
- Manual repair command

### Manual Testing
Each task spec includes detailed testing scenarios covering:
- Happy paths
- Error conditions
- Edge cases
- Performance

## Success Metrics

### Task 1
- [ ] 100% of git-locked tasks have non-null `task.git` after completion
- [ ] Validation logs appear for missing metadata
- [ ] No tasks fail due to metadata issues

### Task 2
- [ ] Startup repairs all repairable tasks automatically
- [ ] Manual repair command works
- [ ] < 50ms per task repair time
- [ ] Partial metadata better than nothing

### Task 3
- [ ] PR creation success rate > 95%
- [ ] All errors are actionable
- [ ] Existing PRs detected and shown (not errors)
- [ ] Network failures retry automatically
- [ ] User can cancel in-progress operations

## Related Documentation

### Existing Docs
- `.agents/implementation/github_context.md` - Context system v2
- `.agents/implementation/gh_management.md` - Git-locked environments
- `AGENTS.md` - Contributor guidelines

### Code References
- Commit `ed8e55d` - Git metadata persistence implementation
- Commit `e6861a9` - Auto-merge system (removed, but PR flow remains)

## Timeline Estimate

Assuming one developer working sequentially:

- **Task 1:** 4-6 hours
  - 2 hours implementation
  - 2 hours testing
  - 1 hour documentation

- **Task 2:** 8-12 hours
  - 4 hours implementation (repair logic)
  - 2 hours UI integration
  - 3 hours testing (includes bulk repair)
  - 1 hour documentation

- **Task 3:** 12-16 hours
  - 6 hours implementation (validation, retry, errors)
  - 3 hours UI changes (progress, cancel)
  - 4 hours testing (network failures, edge cases)
  - 2 hours documentation

**Total:** 24-34 hours (3-4 days)

## Risks and Mitigations

### Risk 1: Task Repair Modifies Files During Startup
**Mitigation:**
- Only repair tasks that need it (git-locked + missing metadata)
- Use atomic file writes (already in persistence.py)
- Test with large task histories (100+ tasks)

### Risk 2: PR Creation Changes Break Existing Flow
**Mitigation:**
- Keep existing code paths initially
- Add validation as optional first
- Test with both git-locked and folder-locked
- Rollback plan: revert commits individually

### Risk 3: Performance Impact on Startup
**Mitigation:**
- Repair only active tasks initially
- Defer done tasks to background
- Add repair count logging for monitoring
- Set time budget: < 5 seconds for 100 tasks

## Open Questions

1. **Should repair be mandatory or optional?**
   - Recommendation: Mandatory for new tasks, best-effort for old tasks

2. **What about tasks from non-GitHub remotes?**
   - Current: `repo_owner` and `repo_name` can be None (acceptable)
   - No changes needed

3. **Should we migrate v1 PR metadata files to v2?**
   - Not required - `load_pr_metadata()` supports both
   - Can be future enhancement

4. **Add telemetry for PR creation failures?**
   - Out of scope for initial implementation
   - Log analysis can provide insights

## Next Steps

1. **Review task specifications** (this document + 3 task files)
2. **Prioritize tasks** (recommended: 1 → 2 → 3)
3. **Assign to coder** or implement in auditor mode
4. **Create feature branch** per task
5. **Test thoroughly** per testing scenarios
6. **Submit PR** with clear commit messages
7. **Update documentation** in `.agents/implementation/`

## Notes

- All tasks build on existing infrastructure (no architectural changes)
- Backward compatible (old tasks continue to work)
- Focus on reliability and user experience
- Clear logging and error messages throughout
- No breaking changes to public APIs
