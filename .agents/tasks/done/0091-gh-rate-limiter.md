# GH Rate-Limit Scheduler

**Scope:** New module `agents_runner/gh/rate_limiter.py` — plus config integration and wiring.
**Dependencies:** none (foundational; blocks #0092, #0094)

## Outcome
All API-bearing `gh` CLI calls (those that hit `api.github.com`) are throttled by an account-wide, per-authenticated-account/host scheduler, so the app never exceeds a user-configurable global request rate.

## Acceptance Criteria

1. **Config key** `github_requests_per_second` added to app settings:
   - Default: `2`
   - Valid range: `1`–`10`
   - Loaded from `~/.midoriai/agents-runner/config.toml` under the appropriate TOML table (same settings namespace as `github_poll_interval_s` / `github_polling_enabled`).
   - Validated on load; out-of-range values clamp to the nearest bound with a log warning.

2. **Account-keyed scheduler** class in `agents_runner/gh/rate_limiter.py`:
   - Key = `(authenticated_login, host)` derived from `agents_runner.gh.auth.resolve_authenticated_login` and the `gh` config host (default `github.com`).
   - Thread-safe token-bucket or equivalent — no extra API call to read the host, infer it from `gh`'s known defaults.
   - Scheduler lifetime: module-level, cleared when `invalidate_gh_auth_cache` fires (invalidate wipes the cached account entry; a fresh login rebuilt on next `gh` call).
   - Rate = `github_requests_per_second` requests per second, global across all environments/tasks for that account.

3. **Wiring into existing `gh` calls:**
   - New thin wrapper around `run_gh` in `agents_runner/gh/process.py` that acquires a scheduler permit before every call except `gh auth status`, `gh auth login`, and git-only commands (`git ...`).
   - Git-only commands (those where `args[0]` is `git`) never go through the scheduler.
   - `gh pr create` (in `task_plan.py` `commit_push_and_pr`) goes through the scheduler.
   - All `gh api` calls in `work_items.py` go through the scheduler.
   - `gh pr list`, `gh issue list`, `gh pr view`, `gh issue view` go through the scheduler.

4. **Minimal diff**: do not refactor existing retry logic. The scheduler is a pre-flight gate, not a replacement for `with_retry` or `_is_retryable_read_error`.

5. **Tests not required** unless explicitly requested.

## Implementation Notes
- `agents_runner/gh/process.py` `run_gh` runs arbitrary subprocess commands (both `gh` and `git`). Args are passed directly to `subprocess.run` — `args[0]` is the executable name. Add the scheduler check as the first line before `subprocess.run`, skipping when `args[0]` is `"git"`.
- Polling coordinator (`github_work_coordinator.py`) already throttles poll cycles; the scheduler adds the next layer below it.
- The `run_gh` signature must not change — the wrapper must infer account/host internally.
- **Bootstrap ordering:** The wrapper calls `resolve_authenticated_login()` to derive the account key. That function itself calls `run_gh(["gh", "api", "user", ...])` — ensure the scheduler can handle this self-call without deadlock (e.g. skip rate-limiting when the account is unknown).
