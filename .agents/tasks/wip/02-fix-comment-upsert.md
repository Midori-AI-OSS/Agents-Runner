# 02 — Fix comment upsert (find + update, not create)

## File
`.github/workflows/ci-pr-comment.yml`

## Problem
The `Post CI Results` step always calls `github.rest.issues.createComment`, creating a brand-new comment on every trigger. This floods the PR with duplicate comments.

## What to do
Replace the single `createComment` call with an upsert pattern:

1. Before posting, search for an existing comment from the bot (search by `context.actor` or the bot app ID) on the PR using `github.rest.issues.listComments`.
2. If a bot comment is found, update it with `github.rest.issues.updateComment`.
3. If no bot comment exists, create one with `github.rest.issues.createComment`.

Identifying the bot comment: match comments where `user.login === 'github-actions[bot]'`. (Do NOT use `user.type === 'Bot'` — that also matches Dependabot, Renovate, etc.) As a secondary filter, match comments whose body starts with `## CI Results`.

**Event context branching (critical):** The script block currently reads PR number and SHA from `context.payload.pull_request.*`. When triggered by `workflow_run` (per task 01), those fields are undefined. The script must extract the PR number and SHA conditionally:
- On `pull_request`: `context.payload.pull_request.number` and `context.payload.pull_request.head.sha`
- On `workflow_run`: `context.payload.workflow_run.pull_requests[0].number` and `context.payload.workflow_run.head_sha`
Check `context.eventName` to branch.

Also, `context.actor` is NOT a reliable bot identifier across event types — prefer the `user.login` match described above.

## Done when
- On first trigger, a single comment is created.
- On subsequent triggers, the existing comment is updated in-place instead of creating a new one.
- No duplicate comments appear in the PR.
