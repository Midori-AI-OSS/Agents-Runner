# Task: Cleanup and PR Metadata Update

**Role:** Coder  
**Estimated Time:** 1-2 hours  
**Dependencies:** **MUST complete tasks 193-01, 193-02, and 193-03 BEFORE starting this task**

## Objective
Audit and clean up folders, root documentation/text files, and update PR 193 metadata.

## Context
- PR 193 is a large refactor (+3543 -1435 lines)
- Need final cleanup before merge
- Verify all artifacts are in correct locations per AGENTS.md guidelines
- Versioning: 4-part `MAJOR.MINOR.BUILD.TASK` in `pyproject.toml` (see AGENTS.md line 48)

## Prerequisites
- Tasks 193-01, 193-02, and 193-03 completed and their artifacts available
- Repository on branch `midoriaiagents/60d23c757d`
- `gh` CLI authenticated (for PR metadata updates)
- Git configured for commits

## Part 1: Audit Folders

### 1.1 Check `.agents/` structure
```bash
# List all content in .agents subdirectories
find .agents -type f | sort

# Review each directory
ls -lah .agents/audit/
ls -lah .agents/reviews/
ls -lah .agents/temp/     # If exists
ls -lah .agents/notes/    # If exists
```

**Actions:**
- **`.agents/reviews/`**: Should contain reports from tasks 193-02 and 193-03
  - Keep: `193-agent-verification.md`, `193-cli-audit.md`, and any related reports
  - Archive obsolete reviews (from old work) to `.agents/notes/archive-<date>/` or delete if truly not needed
  
- **`.agents/temp/`**: Temporary work files
  - Delete anything related to completed work
  - Keep only active/in-progress temporary files
  
- **`.agents/notes/`**: Notes and scratch work
  - Archive or delete obsolete notes related to completed tasks
  - Keep only relevant, recent notes
  
- **`.agents/audit/`**: Should only contain `AGENTS.md` per its own rules

### 1.2 Check root directory
```bash
# List all markdown and text files at root
ls -lah *.md *.txt 2>/dev/null

# Check for temporary files
ls -lah *.tmp *.bak *.swp 2>/dev/null
find . -maxdepth 1 -type f -name "*.log" -o -name "*.cache"
```

**Actions:**
- **README.md**: Verify NOT modified (check `git diff README.md` - should be empty)
- **AGENTS.md**: Check if it needs updates (but no changes expected from PR 193)
- **Remove temporary files**: Any `.tmp`, `.bak`, `.swp`, `.log` files at root
- **Check for leftover artifacts**: Look for test outputs, debug files, editor cruft

### 1.3 Check `agents_runner/tests/`
```bash
# List test files added/modified in PR 193
git --no-pager diff origin/main --name-status | grep test

# Check for orphaned test files
find agents_runner -name "test_*.py" -o -name "*_test.py" | while read f; do
  echo "Test: $f"
  # Verify it's properly structured and imports work
done
```

**Actions:**
- Verify tests added in PR 193 are in correct locations (per AGENTS.md: prefer package-scoped tests)
- Check for unused test fixtures or test data files
- No orphaned test files (tests without corresponding module or vice versa)

## Part 2: PR Metadata Update

### 2.1 Update PR description
```bash
# View current PR description
gh pr view 193

# Edit PR description (opens editor)
gh pr edit 193 --body-file <(cat <<'EOF'
## Summary
Unified run planning and agent plugins. Migrated interactive and non-interactive execution to a headless planner/runner flow. Added agent-system plugin framework (Codex/Claude/Copilot/Gemini) to eliminate hardcoded branching.

## Key Changes
- New `agents_runner.planner` subsystem with Pydantic models, planner, runner, subprocess Docker adapter
- Migrated interactive UI to unified planner via `ui/interactive_planner.py`
- Removed legacy interactive docker launcher module
- Agent-system plugin discovery/registry for theming, display metadata, and capability checks
- Comprehensive test coverage for planner subsystem

## Verification Complete
- ✅ All PR reviewer comments addressed (see task 193-01 artifacts)
- ✅ All agent systems verified operational (see `.agents/reviews/193-agent-verification.md`)
- ✅ CLI help text audited and aligned (see `.agents/reviews/193-cli-audit.md`)

## Breaking Changes
None. Maintains backward compatibility with existing config files and user workflows.

## Ready for Review
All checks complete. Ready for final review and merge.
EOF
)
```

**Note:** Adjust the body content based on actual findings from tasks 193-01, 193-02, 193-03. Include links to verification reports and note any issues found.

### 2.2 Check PR labels and milestones
```bash
# View current labels
gh pr view 193 --json labels,milestone

# Add/update labels if needed (examples)
gh pr edit 193 --add-label "refactor" --add-label "ready-for-review"

# Set milestone if applicable
gh pr edit 193 --milestone "v0.2.0"  # Adjust as needed
```

### 2.3 Add closing comment
```bash
gh pr comment 193 --body "## Verification Complete

All reviewer comments have been addressed:
- Plugin discovery verified in all execution paths (fixes preflight_worker.py:364 concern)
- All 18 comments reviewed and resolved (see /tmp/agents-artifacts for checklist)

Agent systems tested and operational:
- Codex: ✅ Verified
- Claude: ✅ Auth error handling verified
- Copilot: ✅ Verified
- Gemini: ✅ Verified
(Full report: .agents/reviews/193-agent-verification.md)

CLI help text audited and aligned with new planner flow.
(Full report: .agents/reviews/193-cli-audit.md)

Ready for final review and merge."
```

**Note:** Adjust based on actual results. If any issues found, list them and note status (fixed / tracking task filed / not blocking).

## Part 3: Version and Changelog

### 3.1 Check current version
```bash
# Get current version from pyproject.toml
grep "^version = " pyproject.toml
```

### 3.2 Determine version bump
Per AGENTS.md line 48: "use 4-part `MAJOR.MINOR.BUILD.TASK`"

**Versioning rules (from AGENTS.md):**
- When task files move from `.agents/tasks/wip/` to `.agents/tasks/done/`, bump `TASK` by +1 per file moved
- If multiple tasks completed at once, bump `TASK` by that count
- If no task file moved, do not bump version (unless explicitly instructed)
- When `TASK` reaches 100000, reset to 0 and bump `BUILD` by +1
- Only bump `MINOR`/`MAJOR` intentionally, resetting lower fields to 0

**For this task:**
- Check if tasks 193-01, 193-02, 193-03 have been moved to `.agents/tasks/done/`
- If so, bump `TASK` by the count of moved files (e.g., if 3 files moved, +3)
- If not moved yet (still in wip), do not bump yet

```bash
# Count task files in done/
ls -1 .agents/tasks/done/*.md 2>/dev/null | wc -l

# Check if our tasks are there
ls -1 .agents/tasks/done/193-*.md 2>/dev/null
```

### 3.3 Update version if applicable
```bash
# If tasks moved to done, update pyproject.toml
# Example: 0.1.12.345 → 0.1.12.348 (if 3 tasks moved)

# Edit pyproject.toml
# Find: version = "0.1.12.345"
# Replace with: version = "0.1.12.348" (or appropriate new version)

# Commit version bump
git add pyproject.toml
git commit -m "[CHORE] Bump version to 0.1.12.348 (3 tasks completed)"
```

**Note:** If tasks haven't moved to done/ yet, document current version and note that bump will happen when tasks are moved (by Taskmaster or Auditor role, per mode guidelines).

## Acceptance Criteria
- ✅ `.agents/` folders reviewed, obsolete content archived or removed
- ✅ Root directory clean (no temp files, README.md untouched, confirmed with `git diff README.md`)
- ✅ `agents_runner/tests/` reviewed for orphaned or misplaced tests
- ✅ PR 193 description updated with summary, verification links, and ready-for-review status
- ✅ PR labels and milestone verified/updated
- ✅ Closing comment added to PR with verification summary
- ✅ Version number checked and bumped if tasks moved to done (or documented for later bump)
- ✅ All cleanup committed with `[CLEANUP]` or `[CHORE]` prefix
- ✅ Changes pushed to branch: `git push origin midoriaiagents/60d23c757d`

## Commit Strategy
Group related changes:
1. Cleanup commit: `[CLEANUP] Remove obsolete temp files and archive old notes`
2. PR metadata commit: `[CHORE] Update PR 193 metadata and verification summary` (if PR description is tracked in repo - usually it's not, so just via gh CLI)
3. Version bump commit (if applicable): `[CHORE] Bump version to X.Y.Z.N (M tasks completed)`

## Success Criteria Checklist
```markdown
- [ ] .agents/audit/ - contains only AGENTS.md
- [ ] .agents/reviews/ - contains 193-02 and 193-03 reports, obsolete reviews archived
- [ ] .agents/temp/ - cleaned up
- [ ] .agents/notes/ - obsolete notes archived or deleted
- [ ] Root directory - no temp files (.tmp, .bak, .swp, .log)
- [ ] README.md - not modified (git diff empty)
- [ ] agents_runner/tests/ - no orphaned tests
- [ ] PR description - updated with summary and verification links
- [ ] PR labels - appropriate (e.g., "refactor", "ready-for-review")
- [ ] PR milestone - set if applicable
- [ ] PR closing comment - added with verification summary
- [ ] Version - checked and bumped if tasks moved to done
- [ ] All changes committed with clear messages
- [ ] All commits pushed to branch
```

## Notes
- Do not delete content that might be referenced later (archive to `.agents/notes/archive-<date>/` if unsure)
- Keep commit messages concise and clear (follow [TYPE] format from AGENTS.md)
- This task should be done AFTER tasks 193-01, 193-02, and 193-03 are complete
- If you need to create `.agents/notes/archive-<date>/`, use current date in YYYY-MM-DD format
- PR description and comments are updated via `gh pr` commands, not by editing files in repo (GitHub PR metadata is not version controlled)
