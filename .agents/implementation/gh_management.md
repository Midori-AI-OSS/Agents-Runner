# GitHub Management Split

- `agents_runner/gh_management.py` is now a shim over `agents_runner/gh/`.
- `__all__` preserves the expected public API from the original module.
- Task planning/branch prep/PR creation behavior should be unchanged; the split is organizational.
- PR finalization tolerates dirty worktrees when switching to the task branch: it prefers resetting an unmodified task branch to the current base `HEAD`, otherwise it attempts a merge checkout and fails with a conflict-focused error.

## Git-Locked Environment PR Feature

The Review button in task details now appears for ALL `gh_management_locked` environments, not just those with `gh_mode == GH_MANAGEMENT_GITHUB`.

### Key Changes

1. **TaskDetailsPage** (`agents_runner/ui/pages/task_details.py`):
   - Added `_environments` dict reference for looking up environment properties
   - `_sync_review_menu()` checks for `gh_management_locked` flag and shows Review button for any git-locked environment
   - Added `set_environments()` method to inject the environments dict from main window

2. **MainWindow** (`agents_runner/ui/main_window.py`):
   - Calls `_details.set_environments(self._environments)` during initialization

3. **Task Review Handler** (`agents_runner/ui/main_window_task_review.py`):
   - `_on_task_pr_requested()` now handles non-GitHub management modes for git-locked environments:
     - Sets default branch name `midoriaiagents/{task_id}` if missing
     - Retrieves `repo_root` from environment `host_repo_root` or `host_folder` if not set on task
     - Passes `is_override` flag to the PR creation worker for non-GitHub modes

4. **PR Finalization Worker** (`agents_runner/ui/main_window_tasks_interactive_finalize.py`):
   - `_finalize_gh_management_worker()` accepts optional `is_override` parameter (default False)
   - When `is_override=True`, appends note to PR body: "This is an override PR created manually for a git-locked environment"

### Behavior

- Review button appears when task is in any done state (done, cancelled, killed, exited with code 0) for git-locked environments
- For folder-locked environments (non-GitHub management), clicking "Create PR" will:
  - Create branch `midoriaiagents/{task_id}` if one doesn't exist
  - Push the branch
  - Create a PR with override indication in the body
- Existing GitHub-managed environment behavior is unchanged
