# TM-0154-02: Recursive artifact finalization (encrypt nested staging files)

Issue: https://github.com/Midori-AI-OSS/Agents-Runner/issues/154

## Goal
Ensure nested files under `/tmp/agents-artifacts` are collected/encrypted during finalization and show up in archived artifacts with their folder structure preserved.

## Scope
- Update finalization collection in `agents_runner/artifacts.py`.
- Minimal diffs; Python 3.13+ typing; do not touch `README.md`.

## Files to change
- `agents_runner/artifacts.py`
  - `collect_artifacts_from_container()`

## Implementation notes
- Replace top-level-only collection:
  - Current: `files = [f for f in artifacts_staging.iterdir() if f.is_file()]`
  - Desired: recursively find files under `artifacts_staging`.
- Preserve folder structure in metadata:
  - Call `encrypt_artifact(..., str(file_path), original_filename=relative_path.as_posix())`
  - Where `relative_path = file_path.relative_to(artifacts_staging)`
- Safety:
  - Skip symlinks (`is_symlink()`).
  - Before encrypting, ensure `file_path.resolve(strict=True)` is within `artifacts_staging.resolve(strict=True)`.

## Acceptance criteria
- A nested file `staging/reports/out.json` is encrypted and appears via `list_artifacts(task_id)` with `original_filename == "reports/out.json"`.
- Symlinks (and symlink escapes) are not encrypted.
- No exceptions when staging contains subdirectories.

## Quick manual checks
```bash
task_id="tm154-finalize"
root="$HOME/.midoriai/agents-runner/artifacts/$task_id/staging"
rm -rf "$root"
mkdir -p "$root/reports"
printf "{\\\"ok\\\": true}\\n" > "$root/reports/out.json"

uv run python - <<'PY'
from agents_runner.artifacts import collect_artifacts_from_container, list_artifacts
task_id = "tm154-finalize"
uuids = collect_artifacts_from_container("unused", {"task_id": task_id}, "default")
print("collected", uuids)
print([a.original_filename for a in list_artifacts(task_id)])
PY
```

