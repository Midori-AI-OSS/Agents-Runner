# GitHub Version Control Context

This prompt instructs the agent on proper Git workflow and commit practices when GitHub management mode is enabled.

**When used:** GitHub management is enabled for the environment  
**Template variables:** None

## Prompt


VERSION CONTROL
- The workspace is a git repository with a task branch already created.
- `git` and `gh` CLI are installed and available in PATH.
- IMPORTANT: Commit your changes as you work using:
  - `git add <files>` or `git add -A` to stage changes
  - `git commit -m 'Your descriptive message'` to commit
- Commit frequently - after each logical change or completed feature.
- Commits are preserved even if the task is interrupted.
- A pull request will be created automatically after task completion.
