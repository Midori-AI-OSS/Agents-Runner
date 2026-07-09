# 03 — Upload pyright/basedpyright stats as workflow artifact

## File
`.github/workflows/ci-type.yml`

## Problem
`ci-type.yml` parses pyright and basedpyright JSON output and writes counts (errors, warnings, diagnostics) to `$GITHUB_ENV`. Those env vars are local to this workflow run and invisible to `ci-pr-comment.yml`. The comment workflow currently falls back to `annotations_count`, which lumps errors + warnings together and does not match the per-severity breakdown.

## What to do
Add a step after pyright and basedpyright parsing that uploads a stats JSON file as a workflow artifact:

1. In addition to the existing `$GITHUB_ENV` writes, also write a small JSON file, e.g. `/tmp/type-stats.json`:
   ```json
   {
     "pyright": { "errors": N, "warnings": M },
     "basedpyright": { "errors": N, "warnings": M, "diagnostics": K }
   }
   ```
2. Use `actions/upload-artifact@v4` to upload `/tmp/type-stats.json` with a name like `type-stats`.

## Done when
- A `type-stats` artifact containing the parsed stats JSON is uploaded.
- The existing `$GITHUB_ENV` writes can stay or be removed (either is fine — the artifact is the new source of truth for the comment workflow).
