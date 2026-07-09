# 01 — Fix ci-pr-comment.yml triggers

## File
`.github/workflows/ci-pr-comment.yml`

## Problem
The workflow triggers only on `pull_request: [opened, synchronize]`, which fires *before* the individual check workflows complete. The comment is created once with all checks showing "pending" and never updates.

## What to do
Change the `on` block:
1. Add `workflow_run` triggers for the four individual CI workflows:
   - `CI Type`
   - `CI Format`
   - `CI Lint`
   - `CI Tests`
   Each with `types: [completed]`.
2. Keep `pull_request: [opened]` for the initial comment on PR open.
3. Remove `synchronize` — pushing new commits will trigger new workflow runs, which in turn fire `workflow_run` completions.

Result: the comment workflow fires (a) when the PR opens (initial "pending" comment) and (b) each time any of the four checks completes (updating the comment with fresh results).

## Done when
- The `on` block contains `workflow_run` for all four workflows.
- `pull_request` is limited to `[opened]` (no `synchronize`).
- The file passes `yamllint` (or at minimum is valid YAML).
