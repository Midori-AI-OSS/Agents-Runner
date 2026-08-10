# GH PR-Create Retry on Rate Limits

**Scope:** `agents_runner/gh/task_plan.py` `commit_push_and_pr` and new helper in `agents_runner/gh/pr_retry.py`.
**Dependencies:** #0092 (reuses rate-limit detection logic from error-output parsing)

## Outcome
If `gh pr create` fails specifically due to a rate limit (after the push already succeeded), the app enters a dedicated retry loop: retry every 5 minutes for up to 1 hour (both configurable), displaying "Waiting for GitHub" feedback. This is the **only** rate-limit retry loop — other `gh` calls return errors immediately and let the scheduler handle backoff.

## Acceptance Criteria

1. **Config keys** (top-level keys in `_settings` dict alongside `github_poll_interval_s`, `github_polling_enabled`, etc.):
    - `github_pr_retry_interval_minutes`: default `5`, valid range `0`–`60`
    - `github_pr_retry_max_minutes`: default `60`, valid range `0`–`360`
   - When `github_pr_retry_interval_minutes` is `0`, the retry loop is disabled.

2. **Retry logic in `commit_push_and_pr`:**
   - After `git push` succeeds (step already exists), if `gh pr create` exits non-zero AND the error output matches a rate-limit pattern (reuse #0092 parsing), do NOT raise immediately.
   - Instead:
     a. Log "[gh-pr-retry] rate-limited: retrying every N minutes for up to M minutes"
     b. Sleep `github_pr_retry_interval_minutes` minutes
     c. Retry `gh pr create`
     d. Repeat until success, or until cumulative elapsed time exceeds `github_pr_retry_max_minutes`.
      e. If the retry loop exhausts, raise `GhManagementError` with the original rate-limit message.
    - If the error is NOT a rate limit, let the existing `with_retry` path handle it (current behavior: `GhManagementError`, `OSError`, and `TimeoutError` trigger `with_retry`'s exponential backoff).

3. **UI feedback:**
   - During the retry loop, emit a signal or call the existing `on_log` callback with a message like `"[gh-pr-retry] Waiting for GitHub — will retry gh pr create in N minutes"`.
   - The caller (e.g. MCP `handle_github_pr_create` in `tools_github.py`) should propagate or surface this state.

4. **No change to existing `with_retry` in `pr_retry.py`** — this is a distinct, rate-limit-specific loop, not the transient-network retry.

## Implementation Notes
- The push already uses `with_retry` from `pr_retry.py`. Keep that independent.
- The PR create call in `commit_push_and_pr` (lines 589-593) currently wraps `_create_pr_with_retry` in `with_retry(retry_on=(OSError, TimeoutError, GhManagementError))`. Rate limits currently hit `require_ok` → `GhManagementError` → caught by `with_retry`. Change: detect rate limit inside `_create_pr_with_retry` BEFORE `require_ok` would raise, then enter the configurable retry loop. Only fall through to `with_retry` for non-rate-limit failures.
- Reuse the rate-limit detection logic from #0092 (parse error output). Factor into a shared helper if needed, but keep it minimal.
