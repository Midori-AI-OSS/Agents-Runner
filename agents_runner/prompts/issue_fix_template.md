# Issue Fix Template

Build a task prompt for fixing a GitHub issue from the Tasks -> Issues workflow.

## Prompt
Issue URL: {ISSUE_URL}
Issue title: {ISSUE_TITLE}

Helpful info:
1. Read the full issue details (description, linked context, and comments) and restate the problem in your own words.
2. Prefer using `gh` to review and manage issue context (details, discussion, and relevant updates), unless this repository explicitly asks for a different method.
3. Reminder: When posting `gh` comments, avoid wrapping routine status updates or file paths in backticks; use fenced code blocks only for actual code snippets to keep comments easy to parse.
4. Commit your changes as you work (don't just draft a commit message).
5. Reproduce the issue or, if reproduction is not possible, explain exactly why and identify the most likely failure path from code inspection.
6. Identify root cause with file-level evidence before making changes.
7. Implement a minimal, focused fix that addresses root cause without unrelated refactors.
8. Verify behavior with the most relevant checks for the changed area and report concrete results.
9. Follow this repository's instructions (especially AGENTS.md and related docs) for workflow, formatting, and communication.
10. At the end, update GitHub so the user is informed: post the appropriate issue / PR / comment update with status, what changed, and current outcome.

-----
{PRIMARY_REQUEST}
