# GitHub Context

A GitHub context file is available at: `{GITHUB_CONTEXT_FILE}`

This file contains repository information to help you understand the context of your task:
- Repository URL, owner, and name
- Current branch and commit SHA
- Base branch (if applicable)
- Task branch (if working in a cloned repo environment)

You can read this file to understand the GitHub context. The file is in JSON format with the following structure:

```json
{{
  "version": 2,
  "task_id": "...",
  "github": {{
    "repo_url": "https://github.com/owner/repo",
    "repo_owner": "owner",
    "repo_name": "repo",
    "base_branch": "main",
    "task_branch": "task-abc123",
    "head_commit": "abc123..."
  }},
  "title": "",
  "body": ""
}}
```

## Updating GitHub Context

If you make changes that should be represented in a pull request or issue:
- Update the GitHub context file with valid JSON containing:
  - "title": short title describing your changes (<= 72 chars)
  - "body": detailed description of changes (markdown format)
- Keep it as strict JSON (no trailing commas).
- REMINDER: Don't forget to commit your code changes with `git commit`!

Use `gh` CLI commands to interact with GitHub if needed (e.g., creating PRs, managing issues).
