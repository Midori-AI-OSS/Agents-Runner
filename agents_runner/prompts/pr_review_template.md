# Pull Request Review Template

Build a task prompt for reviewing a GitHub pull request from the Tasks -> Pull Requests workflow.

## Prompt
Review GitHub pull request #{PR_NUMBER} for repository {REPO_OWNER}/{REPO_NAME}.

PR title: {PR_TITLE}
PR URL: {PR_URL}

Required workflow:
1. Read and follow this repository's standards first, especially AGENTS.md and any repo-specific contribution/review instructions.
2. Review the pull request against those repository standards.
3. Run full local verification/tests.
4. You are running in a PixelArch container with passwordless sudo available.
5. Produce your review using the target repository's required format.
6. If repository standards are missing or unclear, choose a clear review format and proceed.
