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

**Warning — downstream impact:** The script block at `ci-pr-comment.yml:26-27` reads `context.payload.pull_request.head.sha` and `context.payload.pull_request.number`. These fields do NOT exist in `workflow_run` event payloads. When triggered by `workflow_run`, the PR number lives at `context.payload.workflow_run.pull_requests[0].number` and the SHA at `context.payload.workflow_run.head_sha`. Task 02 (or a follow-up) must add conditional logic to extract these from the correct payload path based on `context.eventName`. This task alone does not close that gap.

**Depends on:** Task 02 (upsert) and Task 04 (artifact consumption) for the script block to handle the new trigger context.

## Done when
- The `on` block contains `workflow_run` for all four workflows.
- `pull_request` is limited to `[opened]` (no `synchronize`).
- The file passes `yamllint` (or at minimum is valid YAML).

---

**Completed 2026-07-09 by Coder**

Changes applied to `.github/workflows/ci-pr-comment.yml`:
- Added `workflow_run` trigger listening to `CI Type`, `CI Format`, `CI Lint`, `CI Tests` workflows on `completed` type.
- Changed `pull_request` types from `[opened, synchronize]` to `[opened]`.
- YAML validated as correct.
- Script payload path mismatch (downstream impact noted in Warning) is left for Task 02.
