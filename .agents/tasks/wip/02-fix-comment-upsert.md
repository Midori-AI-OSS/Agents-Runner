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

Identifying the bot comment: filter comments where `user.type === 'Bot'` or check `user.login` against `github.actor` (the comment workflow runs as `github-actions[bot]`). A simple approach: match comments whose body starts with `## CI Results`.

## Done when
- On first trigger, a single comment is created.
- On subsequent triggers, the existing comment is updated in-place instead of creating a new one.
- No duplicate comments appear in the PR.
