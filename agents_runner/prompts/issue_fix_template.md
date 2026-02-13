# Issue Fix Template

Build a task prompt for fixing a GitHub issue from the Tasks -> Issues workflow.

## Prompt
Fix GitHub issue #{ISSUE_NUMBER} for repository {REPO_OWNER}/{REPO_NAME}.

Issue URL: {ISSUE_URL}
Issue title: {ISSUE_TITLE}

Required workflow:
1. Read the full issue details (description, linked context, and comments) and restate the problem in your own words.
2. Reproduce the issue or, if reproduction is not possible, explain exactly why and identify the most probable failure path from code inspection.
3. Identify root cause with file-level evidence before making changes.
4. Implement a minimal, focused fix that addresses root cause without unrelated refactors.
5. Verify behavior with the most relevant checks for the changed area and report concrete results.
6. Summarize what changed, why it solves the issue, and any remaining risks or follow-up checks.
