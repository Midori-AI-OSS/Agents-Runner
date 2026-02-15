# Pull Request Review Template

Build a task prompt for reviewing a GitHub pull request from the Tasks -> Pull Requests workflow.

## Prompt
Review GitHub pull request #{PR_NUMBER} for repository {REPO_OWNER}/{REPO_NAME}.

PR title: {PR_TITLE}
PR URL: {PR_URL}

Suggested workflow:
1. Read and follow this repository's standards first, especially AGENTS.md and any repo-specific contribution/review instructions.
2. Prefer using `gh` to review and manage PR context (PR details, changed files, commits, and discussion), unless this repository explicitly asks for a different method.
3. Review the pull request against repository standards and expected behavior.
4. Run relevant local verification/tests as required by repository rules.
5. Produce your review in the repository's expected format.
6. If standards are missing or unclear, choose a clear review format and proceed.
7. At the end, update GitHub so the user is informed: post the appropriate issue / PR / comment update with review outcome, key findings, and current status.
