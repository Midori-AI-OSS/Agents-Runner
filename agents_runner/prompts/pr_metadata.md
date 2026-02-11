# PR Metadata Instructions

This prompt guides the agent on how to create and update the PR metadata TOML file for automatic pull request creation.

**When used:** GitHub management + PR metadata enabled for environment  
**Template variables:** `{PR_METADATA_FILE}` - Container path to TOML file (default: "/tmp/agent-pr-metadata.toml")

## Prompt


PR METADATA (non-interactive only)
- A TOML file is mounted at: {PR_METADATA_FILE}
- Update it as soon as you know the PR intent (and again before finishing).
- Keep it valid TOML containing ONLY:
  - `title` (<= 72 chars)
  - `body` (markdown)
- Do not add any other keys.

Example:
```toml
title = "Fix: ..."
body = """
Summary...
"""
```

GIT WORKFLOW (cloned repo environments)
- A task/work branch is already created and checked out for you.
- You do NOT need to create or submit a pull request yourself.
- Commit your changes as you work (don't just draft a commit message).
- Do not push changes to the remote repository.
- The pull request will be created automatically at the end of the run.
