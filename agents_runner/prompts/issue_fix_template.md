# Issue Fix Template

Build a task prompt for fixing a GitHub issue from the Tasks -> Issues workflow.

## Prompt
Fix GitHub issue #{ISSUE_NUMBER} for repository {REPO_OWNER}/{REPO_NAME}.

Issue URL: {ISSUE_URL}
Issue title: {ISSUE_TITLE}

Required workflow:
1. Read the full issue details and reproduce the problem.
2. Implement the fix with minimal, focused edits.
3. Run relevant verification commands.
4. Summarize what changed and why.
5. If anything is still uncertain, list concrete follow-up checks.
