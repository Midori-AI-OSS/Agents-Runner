# 04 — Consume stats artifact in PR comment workflow

## File
`.github/workflows/ci-pr-comment.yml`

## Problem
The comment workflow builds the pyright/basedpyright rows using `annotations_count` for every column (errors, warnings, diagnostics). This is the wrong data — it doesn't match what `ci-type.yml` actually computed.

## What to do
1. When the triggering event is `workflow_run` and the triggering workflow is `CI Type`, download the `type-stats` artifact from task #03.
   - Use `dawidd6/action-download-artifact@v6` or `actions/download-artifact@v4` with `run-id: ${{ github.event.workflow_run.id }}`.
2. Read the JSON stats and use actual `pyright.errors`, `pyright.warnings`, etc. in the markdown table instead of `annotations_count`.
3. When the triggering event is *not* `CI Type` (e.g. triggered by `CI Format` completing), the artifact is unavailable. In that case, fall back to showing the check status only (pass/fail/pending) without per-severity breakdown, or query the checks API status only.

## Done when
- When triggered by `CI Type` completing, the comment shows real pyright error/warning counts and basedpyright error/warning/diagnostic counts from the artifact.
- When triggered by other workflows completing, the comment still renders the type-check section (status-only fallback).
- The comment body no longer uses `annotations_count` for the per-severity columns.
