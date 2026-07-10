# 002 — File a GitHub issue with recommended fix for the discovered bug

Issue
- Bug found by task 001 needs to be reported as a GitHub issue with a clear recommended fix.

Depends on: `001-scout-find-bug.md` (requires `/tmp/agents-artifacts/found-bug.md`).

Pre-check: Run `gh auth status` to confirm GitHub CLI is authenticated before creating the issue.

Goal
- Take the bug documented in `/tmp/agents-artifacts/found-bug.md` and create a GitHub issue using `gh issue create`.
- The issue body must include:
  - A clear title summarizing the bug
  - Steps to reproduce (or code location where the bug is visible)
  - Expected vs actual behavior
  - A concrete recommended fix (diff-level specificity)
  - File:line references

Completion
- A GitHub issue URL returned after successful creation.
- Reference the issue URL in the completion note when moving this task to `.agents/tasks/done/`.

Verify
- `gh issue list --state open` to confirm the issue exists.
- Re-read the issue body via `gh issue view <number>` to verify accuracy.
