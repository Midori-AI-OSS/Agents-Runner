# Fix: Add tooltip explaining why PR button is disabled for base-branch tasks

## Issue
GitHub issue #376: "Past tasks can not be pred" — secondary UX problem.

When a killed/cancelled task has `gh_branch == gh_base_branch` (e.g., the task was
killed before creating a feature branch, or `gh_branch_work_mode == "direct_base"`),
the Review -> Create PR button is **disabled** with no explanation:

`_sync_review_menu` in `agents_runner/ui/pages/task_details.py:356-365`:

```python
branch_matches_base = bool(
    str(task.gh_branch or "").strip() and str(task.gh_branch or "").strip() == str(task.gh_base_branch or "").strip()
)
self._review_pr.setEnabled(can_pr and not task.is_active() and (pr_url.startswith("http") or not branch_matches_base))
```

The user sees a greyed-out button with no indication of why.

## What To Do

In `_sync_review_menu` in `agents_runner/ui/pages/task_details.py`:

1. When the PR button is disabled because `branch_matches_base` is True, set a tooltip
   on `self._review_pr` explaining: "This task worked directly on the base branch,
   so there is no separate PR branch to create."
2. The tooltip should be cleared when the button is enabled for other reasons.
3. Use `self._review_pr.setToolTip(...)`.

## Verification

- Open a killed/cancelled task where `gh_branch == gh_base_branch`
- Hover over the disabled "Create PR" button
- The tooltip should explain why PR creation is unavailable

## Review Notes (2026-08-04)

**Status: PASS (no updates needed)** — Well-scoped, all details present, correct
line references, clear verification steps.

**Verified:**
- `_sync_review_menu` at `task_details.py:353-369`: confirmed no existing tooltip.
  `self._review_pr` is a `QAction` (line 78), and `QAction.setToolTip()` is a valid
  Qt API call.
- Only the `branch_matches_base` case needs explanation. The other disabled conditions
  (`can_pr == False` hides the button entirely, `is_active() == True` is self-evident
  because the task would show as "running").
- No import changes needed; all context is already available in the method.

**Independent task:** No dependency on the other three 376 tasks. Can be completed in
any order.
