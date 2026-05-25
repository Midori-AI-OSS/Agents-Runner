# GitHub Recommendation-Only Context

Use this prompt when the repository is available for inspection, but automatic pull request creation is not available.

**Template variables:** `{REASON}`

## Prompt


READ-ONLY GITHUB WORKFLOW
- Automatic pull request creation is unavailable: {REASON}
- Do not edit files, stage changes, commit, push, or create a pull request.
- This overrides any later instruction to change code, commit, push, or rely on automatic PR creation.
- Inspect the repository and user request, then produce a recommendation with:
  - root cause or likely cause
  - files/functions that should change
  - the minimal fix to make
  - verification steps to run
- If this task came from a GitHub issue, pull request, or comment and `gh` can post a comment, reply there with the recommendation and current outcome.
