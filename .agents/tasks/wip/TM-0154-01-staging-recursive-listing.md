# TM-0154-01: Recursive staging artifacts support (live viewer + visibility)

Issue: https://github.com/Midori-AI-OSS/Agents-Runner/issues/154

## Goal
Make the live artifacts viewer treat nested folders under `/tmp/agents-artifacts` as first-class by listing and counting files recursively (without flattening on disk).

## Scope
- Update staging listing/counting/security in `agents_runner/artifacts.py`.
- Minimal diffs; Python 3.13+ typing; do not touch `README.md`.

## Files to change
- `agents_runner/artifacts.py`
  - `list_staging_artifacts()`
  - `get_artifact_info()`
  - `get_staging_artifact_path()`

## Implementation notes
- Replace `staging_dir.iterdir()` usage with a recursive walk of the staging tree.
  - Prefer `os.walk(staging_dir, followlinks=False)` (or equivalent) so symlinked dirs are not traversed.
- Emit `StagingArtifactMeta.filename` as a *relative path* from staging root (example: `reports/out.json`).
  - Keep `StagingArtifactMeta.path` as the actual on-disk `Path`.
- Security:
  - Skip symlinks (`Path.is_symlink()`).
  - Before including a file, verify `file_path.resolve(strict=True)` stays under `staging_root.resolve(strict=True)` (guard against escape).
  - Update `get_staging_artifact_path(task_id, filename)` to allow nested relative paths while still preventing traversal/escape.

## Acceptance criteria
- Creating `~/.midoriai/agents-runner/artifacts/<task_id>/staging/sub/a.txt` makes `list_staging_artifacts(<task_id>)` include `sub/a.txt`.
- `get_artifact_info(<task_id>).file_count` counts nested files so the Artifacts tab becomes visible for nested-only outputs.
- `get_staging_artifact_path(<task_id>, "../x")` and any path-escape attempt returns `None`.

## Quick manual checks
```bash
task_id="tm154-staging"
root="$HOME/.midoriai/agents-runner/artifacts/$task_id/staging"
rm -rf "$root"
mkdir -p "$root/sub"
printf "hi\n" > "$root/sub/a.txt"
uv run python -c 'from agents_runner.artifacts import list_staging_artifacts; print([a.filename for a in list_staging_artifacts("tm154-staging")])'
uv run python -c 'from agents_runner.artifacts import get_artifact_info; print(get_artifact_info("tm154-staging").file_count)'
```

