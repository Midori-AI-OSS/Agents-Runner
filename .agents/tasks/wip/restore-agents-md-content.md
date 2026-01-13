# Restore .agents/audit/AGENTS.md Content

## Objective
Restore the content of `.agents/audit/AGENTS.md` which was blanked, to prevent agents from reintroducing audit artifacts into the repo.

## Files to Modify
- `.agents/audit/AGENTS.md`

## Context
- File was confirmed empty (0 bytes) during audit on 2025-01-13
- Original spec mentions it was "blanked" during refactor work
- This file provides instructions to agents about proper audit artifact handling

## Expected Content Structure

The `.agents/audit/AGENTS.md` file should contain:

1. **Purpose Statement** - What the audit directory is for
2. **Agent Instructions** - Guidelines on audit file handling
3. **Storage Rules** - Where audit artifacts should/shouldn't be stored
4. **Examples** - Correct vs incorrect audit artifact placement

## Recovery Steps

### Step 1: Check Git History
```bash
git log --all --full-history -- .agents/audit/AGENTS.md
git show <commit-sha>:.agents/audit/AGENTS.md
```

### Step 2: Restore or Create Content
If git history has the content:
- Restore from most recent non-empty version

If no history exists, create new content following this template:
```markdown
# Audit Artifacts Directory

This directory is for storing audit reports and reviews generated during agent workflows.

## For Agents

When creating audit artifacts:
- ✅ Store audit files in `.agents/audit/`
- ✅ Use descriptive filenames with dates
- ❌ Do NOT create audit files in project root
- ❌ Do NOT commit audit files to unexpected locations

## Purpose

Audit artifacts help track:
- Task completion reviews
- Code quality checks
- Implementation verification
- Workflow compliance

## File Naming Convention

- `audit-<feature>-<date>.md` for general audits
- `review-<task-id>-<date>.md` for task reviews
- `<descriptive-name>-audit.md` for specific audits
```

### Step 3: Verify
- Confirm file has content (not empty)
- Validate markdown formatting
- Ensure instructions are clear

## Tasks
1. Run git history check to find previous content
2. If found, restore the most recent non-empty version
3. If not found, create new content using template above
4. Verify content is appropriate and clear
5. Commit the restored/created file

## Acceptance Criteria
- `.agents/audit/AGENTS.md` has proper content (not blank)
- File contains clear instructions for agents about audit handling
- Content prevents audit artifact creation in wrong locations
- File is committed and tracked in git
- Content follows markdown best practices
