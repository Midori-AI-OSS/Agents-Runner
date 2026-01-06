# Git Task Isolation - Task Index

**Task ID:** `a7f3b291`  
**Title:** Git Task Isolation for Concurrent Operations  
**Status:** 📋 Ready for Implementation  
**Priority:** P1 (High)  
**Assignee:** (Pending - Ready for Coder pickup)  
**Created:** 2025-01-06  
**Estimated Effort:** 4-6 hours  

---

## 📄 Task Documents

This task has been broken down into multiple documents for different audiences:

### 1. [a7f3b291-summary.md](./a7f3b291-summary.md) ⭐ **START HERE**
**Audience:** Developers, Team Leads  
**Purpose:** Quick overview and implementation roadmap  
**Length:** ~5 minutes read  
**Contents:**
- Problem/Solution summary
- File changes required
- Testing checklist
- Rollout plan

### 2. [a7f3b291-git-task-isolation.md](./a7f3b291-git-task-isolation.md) 📖 **DETAILED PLAN**
**Audience:** Implementers (Coder Mode)  
**Purpose:** Complete implementation specification  
**Length:** ~20 minutes read  
**Contents:**
- Full problem statement
- Detailed requirements
- Phase-by-phase implementation steps
- Acceptance criteria for each task
- Testing scenarios
- Risk analysis

### 3. [a7f3b291-quick-reference.md](./a7f3b291-quick-reference.md) ⚡ **CHEAT SHEET**
**Audience:** Developers during implementation  
**Purpose:** Quick lookup during coding  
**Length:** ~2 minutes read  
**Contents:**
- Files to modify (checklist)
- Implementation order
- Quick testing commands
- Key decisions summary

### 4. [a7f3b291-architecture.md](./a7f3b291-architecture.md) 🏗️ **VISUAL GUIDE**
**Audience:** All stakeholders  
**Purpose:** Understand the architecture changes  
**Length:** ~10 minutes read  
**Contents:**
- Before/after diagrams
- Data flow visualization
- Code change examples
- Performance analysis
- Risk analysis

---

## 🎯 Problem Summary

**Current Issue:**
Multiple tasks using `GH_MANAGEMENT_GITHUB` mode share a single git working directory per environment, causing:
- `.git/index.lock` collisions
- Working tree contamination
- Branch conflicts
- Repository corruption risk

**Root Cause:**
```python
# All tasks in environment "abc123" use:
~/.midoriai/agents-runner/managed-repos/abc123/
```

**Solution:**
```python
# Each task gets isolated directory:
~/.midoriai/agents-runner/managed-repos/abc123/tasks/{task_id}/
```

---

## 📋 Implementation Phases

### ✅ Phase 0: Planning (Complete)
- [x] Analyze codebase
- [x] Document problem and solution
- [x] Create implementation plan
- [x] Create supporting documentation

### 🔲 Phase 1: Core Infrastructure (Critical)
- [ ] Modify `agents_runner/environments/paths.py`
- [ ] Update `agents_runner/ui/main_window_environment.py`
- [ ] Update `agents_runner/ui/main_window_tasks_agent.py`
- [ ] Verify `agents_runner/docker/agent_worker.py`
- [ ] Test concurrent task isolation

### 🔲 Phase 2: Cleanup & Resource Management (High)
- [ ] Create `agents_runner/environments/cleanup.py`
- [ ] Integrate cleanup in task lifecycle
- [ ] Test cleanup behavior
- [ ] Configure cleanup thresholds

### 🔲 Phase 3: Safety & Locking (Optional)
- [ ] Evaluate need for git locking
- [ ] If needed: Implement `agents_runner/gh/git_lock.py`
- [ ] If needed: Integrate with git operations

### 🔲 Phase 4: Testing & Validation (Required)
- [ ] Manual testing (6 test cases)
- [ ] Edge case testing (3 scenarios)
- [ ] Performance testing
- [ ] Backward compatibility validation

### 🔲 Phase 5: Documentation (Medium)
- [ ] Update `.codex/implementation/gh_management.md`
- [ ] Update README.md (if requested)
- [ ] Document configuration options

---

## 📊 Files Modified

### Core Changes (Phase 1)
```
agents_runner/environments/paths.py          [MODIFY] +15 lines
agents_runner/ui/main_window_environment.py  [MODIFY] +5 lines
agents_runner/ui/main_window_tasks_agent.py  [MODIFY] +10 lines
```

### New Files (Phase 2)
```
agents_runner/environments/cleanup.py        [CREATE] ~100 lines
```

### Optional (Phase 3)
```
agents_runner/gh/git_lock.py                 [CREATE] ~80 lines
```

**Total LOC:** ~210 lines (with optional locking)

---

## 🧪 Testing Strategy

### Automated Tests
- Unit tests for `managed_repo_checkout_path()`
- Unit tests for cleanup functions
- Integration test for concurrent tasks

### Manual Tests
1. **Concurrent Task Isolation** - Run 2+ tasks simultaneously
2. **Unique Checkout Directories** - Verify filesystem isolation
3. **Backward Compatibility** - Test local workspace mode
4. **Cleanup Functionality** - Verify task dir removal
5. **Branch Management** - Check unique branch creation
6. **PR Creation** - Validate PR workflow

### Performance Tests
- Clone time (should be <30s for typical repos)
- Disk usage (monitored, cleaned up)
- Lock collision rate (should be 0%)

---

## 📈 Success Metrics

| Metric | Target | Current | Post-Implementation |
|--------|--------|---------|---------------------|
| `.git/index.lock` errors | 0% | ~5-10% | 0% ✅ |
| Concurrent task failures | 0% | ~10-20% | 0% ✅ |
| Working tree contamination | 0 reports | Occasional | 0 ✅ |
| Disk usage per environment | <1GB | <500MB | <1GB (cleaned) ✅ |
| Task startup time | <30s | ~5s | ~5-10s ⚠️ |

---

## 🚀 How to Start Implementation

### For Coder Mode
```bash
# 1. Read the detailed plan
cat .codex/tasks/a7f3b291-git-task-isolation.md

# 2. Start with Phase 1, Task 1.1
# Modify: agents_runner/environments/paths.py
# Add task_id parameter to managed_repo_checkout_path()

# 3. Follow the phase sequence
# Phase 1 → Phase 2 → (Optional Phase 3) → Phase 4 → Phase 5

# 4. Test after each phase
# Run manual tests from Phase 4 checklist
```

### For Reviewer Mode
```bash
# Review documents in order:
1. a7f3b291-summary.md        (Overview)
2. a7f3b291-architecture.md   (Architecture)
3. a7f3b291-git-task-isolation.md  (Details)

# Verify:
- Requirements are clear ✅
- Solution is sound ✅
- Testing is comprehensive ✅
- Backward compatibility preserved ✅
```

---

## 💡 Key Design Decisions

1. **Full Clones vs Worktrees**
   - ✅ Chose: Full clones per task
   - Rationale: Simpler, more robust, avoids worktree edge cases
   - Trade-off: Higher disk usage (mitigated by cleanup)

2. **Cleanup Strategy**
   - ✅ Chose: Immediate cleanup on archive
   - Rationale: Prevent disk bloat, user doesn't need old task dirs
   - Trade-off: Failed tasks kept for debugging (configurable)

3. **Git Locking**
   - ⏸️ Deferred: File-based locking to Phase 3 (optional)
   - Rationale: Task isolation should eliminate need for locks
   - Trade-off: Can add later if edge cases discovered

4. **Backward Compatibility**
   - ✅ Chose: Optional `task_id` parameter
   - Rationale: No breaking changes, gradual migration
   - Trade-off: Slightly more complex API

---

## 📞 Questions & Support

### Open Questions
1. **Cleanup timing:** Immediate or delayed? (Recommend: Immediate)
2. **Failed task retention:** How long? (Recommend: 7 days with warning)
3. **Disk quota enforcement:** Yes/No? (Recommend: Monitor first)

### For Questions
- **Technical:** Refer to detailed plan (a7f3b291-git-task-isolation.md)
- **Architecture:** See architecture doc (a7f3b291-architecture.md)
- **Quick lookup:** Use quick reference (a7f3b291-quick-reference.md)

### Blockers
- None identified. Task is ready for implementation.

---

## 🏁 Completion Criteria

### Definition of Done
- ✅ All Phase 1 tasks completed and tested
- ✅ All Phase 2 tasks completed and tested
- ✅ Phase 3 decision made (implement or defer)
- ✅ All manual test cases pass
- ✅ No regressions in existing functionality
- ✅ Documentation updated
- ✅ Code review approved
- ✅ Deployed to production

### Exit Criteria
- Zero `.git/index.lock` errors in production
- Zero concurrent task failures
- Disk usage within acceptable limits
- User feedback positive

---

## 📅 Timeline

**Estimated Duration:** 4-6 hours of focused work

**Suggested Schedule:**
- **Day 1, Morning (2-3h):** Phase 1 implementation + testing
- **Day 1, Afternoon (1-2h):** Phase 2 implementation + testing
- **Day 2, Morning (1h):** Phase 3 decision + implementation (if needed)
- **Day 2, Afternoon (1h):** Phase 4 comprehensive testing
- **Day 2, End (30m):** Phase 5 documentation + handoff

---

## 🔗 Related Work

### Dependencies
- None (self-contained task)

### Related Issues
- Git lock detection warning (already exists)
- Environment workspace configuration (no changes needed)

### Future Enhancements
- Shared object store optimization
- Shallow clone support
- Disk usage monitoring UI

---

## 📦 Deliverables

### Code
- [ ] Modified `paths.py` with task isolation
- [ ] Updated UI components with task_id flow
- [ ] New `cleanup.py` module
- [ ] (Optional) New `git_lock.py` module

### Tests
- [ ] Unit tests for new functions
- [ ] Integration test for concurrent tasks
- [ ] Manual test results documented

### Documentation
- [ ] Updated `.codex/implementation/gh_management.md`
- [ ] Updated README.md (if requested)
- [ ] Configuration options documented

---

## ✅ Approval & Sign-off

**Task Master:** ✅ Plan approved (2025-01-06)  
**Reviewer:** ⏳ Pending review  
**Coder:** ⏳ Ready for pickup  
**Manager:** ⏳ Pending approval  

---

**Status:** 📋 Ready for Implementation  
**Next Action:** Assign to Coder Mode  
**Blocking:** None  
**Priority:** P1 (High)

---

*Last Updated: 2025-01-06*  
*Task Prefix: a7f3b291*  
*Category: Infrastructure / Git Management*
