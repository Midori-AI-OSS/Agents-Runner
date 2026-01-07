# Agents-Runner Audit Documentation Index

**Last Updated:** 2025-01-07

---

## Audit Reports

### Codebase Analysis
- **`86f460ef-codebase-structure.audit.md`** (1091 lines)
  - Complete codebase structure analysis
  - File size tracking
  - Technical debt identification
  - Module boundaries

### Task Planning
- **`02-task-breakdown.md`** (1414 lines)
  - Complete refactor task breakdown (Tasks 1-9)
  - Dependencies and critical path
  - Sub-task assignments
  - Risk analysis
  - Timeline estimates

### Task-Specific Designs

#### Task 3: Usage / Rate Limit Watch
- **`03-run-supervisor-design.md`** - Run supervision design
- **`04-usage-watch-design.md`** - Usage watch system design
- **`05-usage-watch-implementation-summary.md`** (302 lines) - Implementation summary

#### Task 4: GitHub Context System ⭐ NEW
- **`README-TASK-4.md`** (281 lines) - **START HERE** - Executive summary
- **`05-github-context-design.md`** (1541 lines) - Complete design specification
- **`05-github-context-quick-ref.md`** (256 lines) - Quick reference guide
- **`05-github-context-diagrams.md`** (623 lines) - Visual diagrams

---

## Quick Navigation by Role

### For Implementers (Coder Mode)
1. Start: `README-TASK-4.md` (overview)
2. Read: `05-github-context-design.md` (full design)
3. Reference: `05-github-context-diagrams.md` (visual flows)
4. Follow: Implementation Plan (Phase 1-7)

### For Reviewers (Auditor Mode)
1. Start: `README-TASK-4.md` (success criteria)
2. Review: `05-github-context-design.md` (section: Risk Analysis)
3. Check: `05-github-context-design.md` (section: File Structure)

### For Testers (QA Mode)
1. Start: `README-TASK-4.md` (success criteria)
2. Review: `05-github-context-design.md` (section: Phase 6 Testing)
3. Reference: `05-github-context-diagrams.md` (test scenarios)

### For Stakeholders
1. Start: `README-TASK-4.md` (key decisions)
2. Review: `05-github-context-quick-ref.md` (TL;DR)
3. Decide: Open Questions (need answers before Phase 2)

---

## Task 4 Document Overview

### Main Design (1541 lines)
**File:** `05-github-context-design.md`

**Sections:**
1. Executive Summary
2. Current State Analysis
   - Environment types (git locked vs folder locked)
   - PR metadata implementation
   - Why it's currently limited
3. Requirements Analysis
4. Proposed Design
   - Enhanced metadata schema (v2)
   - Git detection strategy
   - Environment toggle design
   - Global default setting
   - Metadata generation strategy
   - Auth mounting strategy
   - Gemini allowed-dirs integration
   - Error handling strategy
   - Prompt template updates
5. File Structure
   - New modules (3 files)
   - Modified files (11 files)
6. Implementation Plan
   - Phase 1: Infrastructure (2 days)
   - Phase 2: Data Model (1 day)
   - Phase 3: UI Updates (1.5 days)
   - Phase 4: Execution (2 days)
   - Phase 5: Prompts (0.5 days)
   - Phase 6: Testing (1 day)
   - Phase 7: Polish (1 day)
7. Risk Analysis
   - High/Medium/Low risks
   - Mitigation strategies
8. Success Criteria
9. Open Questions
10. Appendices
    - File naming standards
    - Example metadata files
    - Git detection flow chart

### Quick Reference (256 lines)
**File:** `05-github-context-quick-ref.md`

**Sections:**
- TL;DR
- Environment types explained
- Data schema evolution
- Implementation phases
- Critical design decisions
- Key files modified
- Risk mitigation
- Success criteria
- Open questions
- Quick start guide

### Visual Diagrams (623 lines)
**File:** `05-github-context-diagrams.md`

**Diagrams:**
1. Current vs proposed state
2. Environment type decision tree
3. Task start flow (git-locked)
4. Task start flow (folder-locked)
5. Git detection algorithm
6. Metadata file lifecycle
7. Gemini integration
8. Error handling flow
9. Migration path
10. Cache strategy

### Summary (281 lines)
**File:** `README-TASK-4.md`

**Sections:**
- Deliverables
- Key design decisions
- Implementation phases
- Files modified
- Success criteria
- Risk management
- Open questions
- Next steps by role
- Dependencies

---

## Key Findings from Task 4 Audit

### Current State
- PR metadata is NOT Copilot-only (works for all agents)
- Only works for git-locked environments
- Folder-locked environments CAN be git repos (user-managed)
- No git detection for folder-locked environments

### Proposed Changes
- Rename: `gh_pr_metadata_enabled` → `gh_context_enabled`
- Add: v2 metadata schema with github object
- Add: Git detection for folder-locked environments
- Add: Per-environment toggle + global default
- Fix: Gemini allowed directories

### Implementation Estimate
- **Original:** 4-6 days (from task breakdown)
- **Revised:** 9 days (from detailed design)
- **Reason:** Git detection complexity, caching, migration

### Risk Level
- **Overall:** MEDIUM
- **High risks:** Mitigated with backward compatibility
- **Medium risks:** Monitored with extensive testing
- **Low risks:** Acceptable with graceful degradation

---

## Reading Order Recommendations

### First Time Reading
1. `README-TASK-4.md` (10 min)
2. `05-github-context-quick-ref.md` (15 min)
3. `05-github-context-diagrams.md` (20 min, skim)
4. `05-github-context-design.md` (60 min, deep dive)

### Implementation Planning
1. `05-github-context-design.md` (section: Implementation Plan)
2. `05-github-context-design.md` (section: File Structure)
3. `05-github-context-diagrams.md` (relevant flows)
4. `README-TASK-4.md` (success criteria)

### Code Review
1. `05-github-context-design.md` (section: Risk Analysis)
2. `05-github-context-design.md` (section: Error Handling)
3. `05-github-context-diagrams.md` (diagram 8: Error handling)
4. `README-TASK-4.md` (success criteria)

---

## Document Statistics

| Document | Lines | Size | Purpose |
|----------|-------|------|---------|
| 05-github-context-design.md | 1541 | 50K | Complete design spec |
| 05-github-context-diagrams.md | 623 | 38K | Visual diagrams |
| 05-github-context-quick-ref.md | 256 | 7.8K | Quick reference |
| README-TASK-4.md | 281 | 8.9K | Executive summary |
| **Total** | **2701** | **~105K** | **Complete documentation** |

---

## Related Documents

- **`02-task-breakdown.md`** - Original Task 4 definition (lines 451-604)
- **`86f460ef-codebase-structure.audit.md`** - Current codebase state
- **`AGENTS.md`** (root) - Contributor guidelines

---

## Status Summary

| Task | Design | Implementation | Testing | Status |
|------|--------|----------------|---------|--------|
| Task 1 | ✅ Complete | ✅ This audit | N/A | ✅ DONE |
| Task 2 | ✅ Complete | ⏳ Pending | ⏳ Pending | 🔄 IN PROGRESS |
| Task 3 | ✅ Complete | ⏳ Pending | ⏳ Pending | 🔄 IN PROGRESS |
| Task 4 | ✅ **Complete** | ⏳ **Pending** | ⏳ **Pending** | ✅ **READY** |
| Task 5 | ⏳ Pending | ⏳ Pending | ⏳ Pending | 📋 PLANNED |
| Task 6 | ⏳ Pending | ⏳ Pending | ⏳ Pending | 📋 PLANNED |
| Task 7 | ⏳ Pending | ⏳ Pending | ⏳ Pending | 📋 PLANNED |
| Task 8 | ⏳ Pending | ⏳ Pending | ⏳ Pending | 📋 PLANNED |
| Task 9 | ⏳ Pending | ⏳ Pending | ⏳ Pending | 📋 PLANNED |

**Legend:**
- ✅ Complete
- 🔄 In Progress
- ⏳ Pending
- 📋 Planned

---

## Next Actions

### Immediate (Task 4)
1. **Stakeholders:** Review design, answer open questions
2. **Coder:** Begin Phase 1 implementation
3. **QA:** Prepare test environments

### Upcoming (Other Tasks)
1. **Task 2:** Begin implementation (Run Supervisor)
2. **Task 3:** Begin implementation (Usage Watch)
3. **Task 5:** Design first-run setup system

---

**Questions?** Refer to specific document sections or ask Auditor Mode.

**Document Maintenance:** This index should be updated as new audits are completed.
