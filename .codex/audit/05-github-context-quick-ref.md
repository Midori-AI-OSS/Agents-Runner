# GitHub Context Design - Quick Reference

**Full Design:** See `05-github-context-design.md` (1541 lines)  
**Task:** Task 4 - GitHub Context for ALL Agents  
**Status:** Design Complete, Ready for Implementation

---

## TL;DR

Make GitHub PR metadata available to ALL agents (not just Copilot) and extend support to folder-locked environments that are git repositories.

**Key Changes:**
- ✅ Rename: `gh_pr_metadata_enabled` → `gh_context_enabled`
- ✅ Add: v2 metadata schema with github object (repo_url, branch, commit)
- ✅ Add: Git detection for folder-locked environments
- ✅ Add: Per-environment toggle + global default setting
- ✅ Fix: Gemini allowed directories to include `/tmp`

---

## Environment Types Explained

| Type | Mode | Example Target | Git Context? |
|------|------|----------------|--------------|
| **Git Locked** | `"github"` | `owner/repo` | ✅ Always |
| **Folder Locked** | `"local"` | `/path/to/folder` | ⚠️ If git repo |
| **None** | `"none"` | N/A | ❌ Never |

**Key Insight:** Folder-locked environments CAN be git repos (user-managed). We need to detect this.

---

## Data Schema Evolution

### Current (v1) - Copilot-era
```json
{
  "version": 1,
  "task_id": "abc123",
  "title": "",
  "body": ""
}
```

### Proposed (v2) - Agent-agnostic
```json
{
  "version": 2,
  "task_id": "abc123",
  "github": {
    "repo_url": "https://github.com/owner/repo",
    "repo_owner": "owner",
    "repo_name": "repo",
    "base_branch": "main",
    "task_branch": "task/abc123",
    "head_commit": "sha..."
  },
  "title": "",
  "body": ""
}
```

**Backward Compatible:** v1 files still work, PR creation unchanged.

---

## Implementation Phases

### Phase 1: Infrastructure (2 days)
- Add git operations: `git_head_commit()`, `git_remote_url()`, `parse_github_url()`
- Create `gh/context.py` with git detection and caching
- Update `pr_metadata.py` for v2 schema

### Phase 2: Data Model (1 day)
- Rename field: `gh_pr_metadata_enabled` → `gh_context_enabled`
- Add migration logic
- Update Task model

### Phase 3: UI Updates (1.5 days)
- Update Environment editor checkbox
- Add Settings global default
- Wire git detection on folder change

### Phase 4: Execution (2 days)
- Update task start logic (both git-locked and folder-locked)
- Populate github object after clone (git-locked)
- Update agent CLI for Gemini allowed-dirs

### Phase 5: Prompts (0.5 days)
- Create `prompts/github_context.md`
- Keep `pr_metadata.md` for v1 backward compat

### Phase 6: Testing (1 day)
- Test all agent types × all environment types
- Test error handling (not git repo, git fails, etc)
- Test migration

### Phase 7: Polish (1 day)
- Edge cases (detached HEAD, no remote, etc)
- Performance testing
- Documentation

**Total Estimate:** 9 days

---

## Critical Design Decisions

### 1. Git Detection for Folder-Locked

**Decision:** Detect git context at task start, cache result.

**Algorithm:**
1. Check if folder is git repo (`git rev-parse --is-inside-work-tree`)
2. Get repo root (`git rev-parse --show-toplevel`)
3. Get current branch (`git rev-parse --abbrev-ref HEAD`)
4. Get HEAD commit (`git rev-parse HEAD`)
5. Get remote URL (`git remote get-url origin`)
6. Parse owner/repo from URL

**Error Handling:** If ANY step fails, silently skip GitHub context, log reason, continue task.

### 2. Metadata Generation Timing

| Environment Type | When Created | When Populated |
|------------------|--------------|----------------|
| Git-locked | Before clone | After clone completes |
| Folder-locked | Before task | Before task (git detected) |

**Why Different?** Git-locked workspace doesn't exist until clone completes.

### 3. Gemini Allowed Directories

**Current:**
```python
--include-directories /home/midori-ai/workspace
```

**Proposed:**
```python
--include-directories /home/midori-ai/workspace
--include-directories /tmp  # When GitHub context enabled
```

**Rationale:** Gemini needs explicit permission to access `/tmp/github-context-{task_id}.json`

### 4. Auth Mounting (Out of Scope)

**IMPORTANT:** This task does NOT mount GitHub credentials.

**GitHub Context:** Non-secret metadata (repo URL, branch, commit) ← THIS TASK  
**GitHub Auth:** Credentials for API/git operations ← FUTURE TASK (separate checkbox)

---

## Key Files Modified

### New Files (3)
1. `agents_runner/gh/context.py` (~200 lines) - Git detection and caching
2. `prompts/github_context.md` - Agent-agnostic instructions
3. `.codex/audit/05-github-context-design.md` - This design doc

### Modified Files (11)
1. `pr_metadata.py` - Add v2 schema, rename file paths
2. `environments/model.py` - Rename field
3. `environments/serialize.py` - Migration logic
4. `ui/pages/environments.py` - Update checkbox, git detection
5. `ui/main_window_tasks_agent.py` - Folder-locked git detection
6. `docker/agent_worker.py` - Populate github object post-clone
7. `agent_cli.py` - Gemini allowed-dirs
8. `ui/task_model.py` - Rename field
9. `ui/pages/settings.py` - Global default checkbox
10. `ui/pages/environments_actions.py` - Apply default
11. `gh/git_ops.py` - Add git operations

---

## Risk Mitigation

### High Risks
- **Breaking PR creation:** Maintain v1 support, test extensively
- **Git detection slow:** 8s timeout, cache results
- **Gemini can't access file:** Test explicitly, fallback to always include /tmp

### Medium Risks
- **URL parsing fails:** Graceful degradation, log failures
- **Migration breaks configs:** Auto-migrate, keep .bak files

### Low Risks
- **Cache stale:** Clear on edit and restart
- **Agent ignores context:** Clear prompts, test each agent

---

## Success Criteria

### Must Have
✅ GitHub context works for git-locked (existing preserved)  
✅ GitHub context works for folder-locked git repos (NEW)  
✅ Disabled for non-git folder-locked  
✅ Per-environment toggle works  
✅ Global default applies to new envs  
✅ All 4 agents receive context  
✅ Gemini can access file  
✅ Error handling graceful  
✅ Migration preserves existing  
✅ PR creation unchanged (backward compat)

### Performance
✅ Git detection < 2s (normal)  
✅ Git detection timeout 8s (worst)  
✅ No UI freezing

### Code Quality
✅ No credentials in files (security)  
✅ Clear log messages  
✅ All new files < 300 lines  
✅ Test coverage for git detection

---

## Open Questions (Need Decisions)

### Q1: Auto-enable for existing git-locked environments?
**Recommendation:** NO - preserve user choice, default OFF

### Q2: Support non-GitHub git repos (GitLab, Bitbucket)?
**Recommendation:** YES - include raw URL, don't require parsing

### Q3: Detect git for mode="none" environments?
**Recommendation:** NO - only git-locked and folder-locked

### Q4: Context file writable by agent?
**Recommendation:** YES (read-write) - agent needs to set title/body

---

## Quick Start for Implementation

### 1. Read Full Design
```bash
cat .codex/audit/05-github-context-design.md
```

### 2. Start with Phase 1
```bash
# Add git operations to gh/git_ops.py
# Create gh/context.py
# Update pr_metadata.py for v2
```

### 3. Test Early
```bash
# Test git detection with:
# - HTTPS URL: https://github.com/owner/repo
# - SSH URL: git@github.com:owner/repo.git
# - Non-GitHub: https://gitlab.com/owner/repo
# - No remote
# - Detached HEAD
```

### 4. Follow Implementation Plan
See full design document Section: "Implementation Plan"

---

## Document Navigation

- **Full Design:** `05-github-context-design.md` (1541 lines)
- **Task Breakdown:** `02-task-breakdown.md` (Task 4, lines 451-604)
- **Codebase Audit:** `86f460ef-codebase-structure.audit.md` (Current state)

**Questions?** Review full design document or ask Auditor.

---

**Status:** ✅ DESIGN COMPLETE - READY FOR CODER  
**Estimated Effort:** 9 days  
**Dependencies:** Task 1 complete, Task 2 (Run Supervisor) recommended but not blocking  
**Next Action:** Review with stakeholders, begin Phase 1 implementation
