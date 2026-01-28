# TM-0154-03: Recursive live watcher for nested staging folders

Issue: https://github.com/Midori-AI-OSS/Agents-Runner/issues/154

## Goal
Make the live artifacts UI update reliably when files are created/modified/deleted inside nested folders under the staging directory.

## Scope
- Update watcher behavior only; do not redesign the UI.
- Minimal diffs; Python 3.13+ typing; do not touch `README.md`.

## Files to change
- `agents_runner/docker/artifact_file_watcher.py`
  - `_start_impl()`
  - `_refresh_watched_files()` (may rename to reflect watching dirs+files)

## Implementation notes
- `QFileSystemWatcher` is not recursive; explicitly watch:
  - the staging root directory, and
  - all nested directories (so new files/dirs are discovered), and
  - all nested files (so modifications trigger `fileChanged`).
- On any `directoryChanged`, rescan and update watched directories/files (add new, remove deleted).
- Skip symlinks; do not follow symlinked directories (`followlinks=False` if using `os.walk`).
- Keep existing debounce behavior and thread-safety design intact.

## Acceptance criteria
- With the app running in Live Artifacts mode, creating a nested file like `sub/a.txt` under the staging dir shows up in the artifacts list without restarting the UI.
- Modifying `sub/a.txt` triggers a refresh (mtime/text preview updates after debounce).
- Creating a new nested directory after watcher start results in that directory being watched (subsequent file changes under it are detected).

## Manual verification steps
1) Run `uv run main.py`, start a task, open its Artifacts tab (Live Artifacts).
2) In another terminal, write nested files into the task staging dir (from the UI empty-state “Watching:” path):
   - `mkdir -p <staging>/sub && printf "x\\n" > <staging>/sub/a.txt`
   - Edit the file a few times and confirm the list/preview updates.

