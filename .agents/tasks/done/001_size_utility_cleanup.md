# Task 001: Add `get_workspace_tree_size()` directory-size utility in cleanup.py

**File:** `agents_runner/environments/cleanup.py`

**Dependencies:** None (foundational utility)

## Objective
Add a recursive directory size utility function that sums file sizes under a given directory path, handling errors gracefully.

## Requirements
1. Create function `get_workspace_tree_size(root: Path) -> int` that returns total bytes.
2. Use `os.scandir()` for efficient directory traversal. Since `os.scandir()` is non-recursive, implement recursion: for each entry, if it is a directory (and not a symlink), recurse into it; if it is a regular file, add its size.
3. Use `entry.stat(follow_symlinks=False)` to get file size without following symlinks. This avoids crashes on broken symlinks and prevents double-counting.
4. Sum `stat().st_size` only for regular files (`entry.is_file(follow_symlinks=False)`). Skip directories, symlinks, and special files.
5. Gracefully handle `OSError`, `PermissionError`, and similar — skip entries that cannot be read without crashing, and log a warning via `midori_ai_logger`.
6. Use `Path` objects throughout. Function must work for both `app_data` and `scratch_drive` workspace root directories.
7. No external dependencies beyond stdlib.

## Acceptance Criteria
- The function returns correct byte totals for a directory tree.
- Permissions errors, broken symlinks, or unreadable subdirectories do not crash the function.
- Result is an integer (total bytes).

## Notes
- `midori_ai_logger` is already imported in `cleanup.py`. Reuse the existing module-level `logger`.
- Follow existing code conventions in `cleanup.py` (imports, logging, type hints).
- Do not modify any other files.
