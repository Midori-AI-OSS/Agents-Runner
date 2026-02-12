# Pull Request Review Template

Build a task prompt for reviewing a GitHub pull request from the Tasks -> Pull Requests workflow.

## Prompt
Review GitHub pull request #{PR_NUMBER} for repository {REPO_OWNER}/{REPO_NAME}.

PR URL: {PR_URL}
PR title: {PR_TITLE}
Trigger source: {TRIGGER_SOURCE}
Mention comment ID: {MENTION_COMMENT_ID}

Required workflow:
1. Inspect the PR changes carefully for correctness, regressions, and missing tests.
2. Use a reviewer mindset: findings first, ordered by severity, with file references.
3. If no findings exist, explicitly say so and mention residual risks.
4. If this review was triggered by @agentsnova mention and Mention comment ID is present:
   - Add a +1 reaction to that comment when no issues are found.
   - Add a -1 reaction to that comment when issues are found, and include review comments.
