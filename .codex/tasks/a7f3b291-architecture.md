# Git Task Isolation - Architecture Diagram

## Current Architecture (Problem)

```
Environment: "my-project" (env_id: abc123)
├── Workspace: GH_MANAGEMENT_GITHUB
└── GitHub Repo: "owner/repo"

Tasks using this environment:
┌─────────────────────────────────────────────────────────┐
│ Task A (task_id: f1e2d3c4b5)                            │
│ Task B (task_id: a9b8c7d6e5)  ← PROBLEM: Both share    │
│ Task C (task_id: 1a2b3c4d5e)            same directory! │
└─────────────────────────────────────────────────────────┘
                        ↓
              Shared Checkout Path:
  ~/.midoriai/agents-runner/managed-repos/abc123/
                        ↓
                    .git/
                    ├── index         ← Race condition!
                    ├── index.lock    ← Collision!
                    └── refs/
                        └── heads/
                            ├── midoriaiagents/f1e2d3c4b5
                            ├── midoriaiagents/a9b8c7d6e5
                            └── midoriaiagents/1a2b3c4d5e
                    
                    Working Tree (Contamination!)
                    ├── file-from-task-A.txt
                    ├── file-from-task-B.txt
                    └── file-from-task-C.txt
```

**Issues:**
- ❌ All tasks compete for `.git/index.lock`
- ❌ Working tree shows files from all tasks
- ❌ Checkout operations conflict
- ❌ Risk of repository corruption

---

## New Architecture (Solution)

```
Environment: "my-project" (env_id: abc123)
├── Workspace: GH_MANAGEMENT_GITHUB
└── GitHub Repo: "owner/repo"

Base Path: ~/.midoriai/agents-runner/managed-repos/abc123/
└── tasks/
    ├── f1e2d3c4b5/  ← Task A isolated
    │   ├── .git/
    │   │   ├── index
    │   │   └── refs/heads/
    │   │       └── midoriaiagents/f1e2d3c4b5
    │   └── file-from-task-A.txt
    │
    ├── a9b8c7d6e5/  ← Task B isolated
    │   ├── .git/
    │   │   ├── index
    │   │   └── refs/heads/
    │   │       └── midoriaiagents/a9b8c7d6e5
    │   └── file-from-task-B.txt
    │
    └── 1a2b3c4d5e/  ← Task C isolated
        ├── .git/
        │   ├── index
        │   └── refs/heads/
        │       └── midoriaiagents/1a2b3c4d5e
        └── file-from-task-C.txt
```

**Benefits:**
- ✅ Each task has its own `.git/index` (no locks)
- ✅ Working trees are isolated
- ✅ Concurrent git operations safe
- ✅ Clean task lifecycle management

---

## Data Flow

### Task Creation
```
1. User: Create task with prompt
          ↓
2. UI: Generate task_id = uuid4().hex[:10]
          ↓
3. UI: Calculate workspace path
       managed_repo_checkout_path(env_id, task_id)
          ↓
4. UI: Pass to DockerRunnerConfig
       config.host_workdir = workspace_path
          ↓
5. Worker: Clone repo to task-specific path
           prepare_github_repo_for_task(
               repo, 
               dest_dir=config.host_workdir,  ← Task-specific
               task_id=task_id
           )
          ↓
6. Worker: Create branch midoriaiagents/{task_id}
          ↓
7. Agent: Work in isolated directory
```

### Task Completion
```
1. Agent: Complete work, commit changes
          ↓
2. Worker: Push branch, create PR
          ↓
3. UI: Mark task as done
          ↓
4. Cleanup: Remove task checkout directory
            cleanup_on_task_completion(task_id, env_id)
          ↓
5. Result: Disk space recovered
```

---

## Code Path Changes

### Before (Shared)
```python
# agents_runner/environments/paths.py
def managed_repo_checkout_path(env_id: str) -> str:
    return f"~/.midoriai/agents-runner/managed-repos/{env_id}"
    #                                                  ^^^^^^^^
    #                                          Same for all tasks!

# Result: All tasks share ~/.../managed-repos/abc123/
```

### After (Isolated)
```python
# agents_runner/environments/paths.py
def managed_repo_checkout_path(
    env_id: str, 
    task_id: str | None = None
) -> str:
    base = f"~/.midoriai/agents-runner/managed-repos/{env_id}"
    if task_id:
        return f"{base}/tasks/{task_id}"
        #              ^^^^^^^^^^^^^^^ Unique per task!
    return base  # Backward compatible

# Result: Tasks get ~/.../managed-repos/abc123/tasks/f1e2d3c4b5/
```

---

## Cleanup Strategy

```
Task Lifecycle:
┌──────────┐      ┌─────────┐      ┌──────┐      ┌──────────┐
│ Queued   │ ───> │ Running │ ───> │ Done │ ───> │ Archived │
└──────────┘      └─────────┘      └──────┘      └──────────┘
     │                 │                │              │
     │                 │                │              ↓
     │                 │                │         Cleanup triggers:
     │                 │                │         • Immediate (on archive)
     │                 │                │         • Age-based (7 days)
     │                 │                │         • Manual (cleanup button)
     ↓                 ↓                ↓
   Create           Clone &          Commit,
   task dir         branch           push, PR

Cleanup Actions:
• Success: Remove directory (default)
• Failed:  Keep for debugging (configurable)
• Error:   Keep for debugging (configurable)
```

---

## Backward Compatibility

### Scenario 1: Local Workspace (GH_MANAGEMENT_LOCAL)
```
Environment with local workspace:
└── host_workdir: "/path/to/local/repo"

Behavior: UNCHANGED
• Tasks use the configured local directory
• No task-specific isolation (user manages)
• No cleanup (user's responsibility)
```

### Scenario 2: Legacy Call (No task_id)
```python
# Old code calling without task_id
path = managed_repo_checkout_path(env_id)

# Returns: ~/.../managed-repos/{env_id}/
# Same behavior as before - backward compatible
```

### Scenario 3: New Call (With task_id)
```python
# New code with task_id
path = managed_repo_checkout_path(env_id, task_id="f1e2d3c4b5")

# Returns: ~/.../managed-repos/{env_id}/tasks/f1e2d3c4b5/
# Isolated directory for this task
```

---

## Performance Considerations

### Disk Usage
```
Before: 1 clone per environment
• managed-repos/env1/ ─────────> 100 MB

After: 1 clone per task
• managed-repos/env1/tasks/
  ├── task1/ ──────────────────> 100 MB
  ├── task2/ ──────────────────> 100 MB
  └── task3/ ──────────────────> 100 MB

Impact: 3x disk usage (mitigated by cleanup)
```

### Startup Time
```
Before: Clone once, reuse
• First task:  ~5s (clone)
• Second task: ~0.1s (reuse)

After: Clone per task
• First task:  ~5s (clone)
• Second task: ~5s (clone, parallel)

Impact: Slower per-task startup, but parallel!
```

### Network Usage
```
Before: 1 fetch per environment
After:  1 fetch per task (but parallel)

Mitigation: 
• Tasks clone in parallel
• Git uses compression
• Most projects <500 MB
```

---

## Risk Analysis

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Disk exhaustion | Medium | High | Aggressive cleanup, monitoring |
| Clone failures | Low | Medium | Retry logic, error handling |
| Broken backward compat | Low | High | Extensive testing, gradual rollout |
| Performance regression | Low | Low | Cloning is async, parallel |
| Cleanup bugs | Medium | Medium | Keep failed tasks, safe operations |

---

## Future Optimizations (Out of Scope)

### Option 1: Git Worktrees
```
Base: ~/.../managed-repos/{env_id}/
├── .git/          ← Shared git database
└── worktrees/
    ├── task1/     ← Lightweight worktree
    ├── task2/
    └── task3/

Pros: Less disk usage, faster clones
Cons: Complex, worktree bugs, harder cleanup
```

### Option 2: Shallow Clones
```
git clone --depth 1 --single-branch

Pros: Faster clones, less disk
Cons: Can't switch branches easily
```

### Option 3: Shared Object Store
```
git clone --reference /path/to/reference

Pros: Minimal disk usage
Cons: Complex setup, reference lifetime issues
```

**Decision:** Keep it simple. Full clones are robust and easy to manage.

---

## Monitoring Points

**Metrics to Track:**
- Disk usage per environment
- Number of active task directories
- Cleanup success/failure rate
- Clone time (p50, p95, p99)
- `.git/index.lock` error rate (should be 0)

**Alerts:**
- Disk usage >80% of available
- Cleanup failures >5%
- Clone time >30s (p95)
- Any `.git/index.lock` errors

---

## Summary

**Key Changes:**
1. Add `task_id` parameter to `managed_repo_checkout_path()`
2. Each task gets isolated directory: `managed-repos/{env_id}/tasks/{task_id}/`
3. Cleanup removes task directories after completion
4. Backward compatible with existing code

**Complexity:** Medium (mostly plumbing changes)
**Risk:** Low (isolated change, well-tested)
**Effort:** 4-6 hours

**Result:** Zero git lock conflicts, clean task isolation! 🎉
