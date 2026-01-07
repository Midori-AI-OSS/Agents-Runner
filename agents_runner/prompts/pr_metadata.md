# PR Metadata Instructions

This prompt guides the agent on how to create and update the PR metadata JSON file for automatic pull request creation.

**When used:** GitHub management + PR metadata enabled for environment  
**Template variables:** `{PR_METADATA_FILE}` - Container path to JSON file (default: "/tmp/codex-pr-metadata.json")

## Prompt


PR METADATA (non-interactive only)
- A JSON file is mounted at: {PR_METADATA_FILE}
- If you make changes intended for a PR, update that file with valid JSON containing:
  - "title": short PR title (<= 72 chars)
  - "body": PR description (markdown)
- Keep it as strict JSON (no trailing commas).
- REMINDER: Don't forget to commit your code changes with `git commit`!
