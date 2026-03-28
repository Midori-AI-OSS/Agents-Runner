# Pull Request Review Template

Build a task prompt for reviewing a GitHub pull request from the Tasks -> Pull Requests workflow.

## Prompt
PR title: {PR_TITLE}
PR URL: {PR_URL}

Helpful info:
1. Read and follow this repository's standards first, especially AGENTS.md and any repo-specific contribution/review instructions.
2. Prefer using `gh` to review and manage PR context (PR details, changed files, commits, and discussion), unless this repository explicitly asks for a different method.
3. Reminder: When posting `gh` comments, avoid wrapping routine status updates or file paths in backticks; use fenced code blocks only for actual code snippets to keep comments easy to parse.
4. Commit your changes as you work (don't just draft a commit message).
5. Review the pull request against repository standards and expected behavior.
6. Run relevant local verification/tests as required by repository rules.
7. Produce your review in the repository's expected format.
8. If standards are missing or unclear, choose a clear review format and proceed.
9. At the end, update GitHub so the user is informed: post the appropriate issue / PR / comment update with review outcome, key findings, and current status.

-----
{PRIMARY_REQUEST}
