# GH Rate-Limit Capture from Failing Command

**Scope:** `agents_runner/gh/rate_limiter.py` (same module as #0091) — error-output parsing.
**Dependencies:** #0091 (extends the rate_limiter module; blocks #0093)

## Outcome
When a `gh` command fails with a rate-limit error, the scheduler extracts `X-RateLimit-Reset` and/or `Retry-After` directly from the command's stderr/stdout (not a separate API request), and pauses that account's scheduler until the reset window. If no header is found, fall back to a five-minute pause. The paused state is **temporary** — it never logs out the user or invalidates the auth cache.

## Acceptance Criteria

1. **Parse rate-limit signals from `gh` error output:**
   - After `run_gh` returns a non-zero exit code, inspect `proc.stderr` + `proc.stdout` for known rate-limit markers (case-insensitive):
     - `rate limit exceeded`
     - `API rate limit exceeded`
     - `secondary rate limit`
     - `abuse detection`
   - Extract timing hints from the same output:
     - `Retry-After: <seconds>` → exact seconds
     - `X-RateLimit-Reset: <epoch>` → seconds until reset
     - Any ISO timestamp or relative duration mentioned in the error body
   - Fallback: if nothing parsable is found, use **300 seconds** (5 minutes).

2. **Temporary scheduler pause:**
   - When a rate-limit is detected on a particular account key, set the scheduler's permit availability to zero for the extracted duration.
   - After the duration passes, the scheduler resumes at the normal configured rate — **no manual intervention needed**.
   - The auth cache (`GhAuthSnapshot`) is **never** touched — this is a rate-limit state, not an auth state. No false logout.

3. **Logging:**
    - Emit a single `[gh-rate-limit]` structured log entry with the account, host, pause duration, and parsed source (e.g. `retry-after=47s`, `fallback=300s`).
    - Do not log repeatedly; once per rate-limit event per account. Track the last-logged rate-limit event and suppress duplicates until either the pause expires or a new rate-limit with a different reset timestamp arrives.

4. **Integration:**
   - This parsing happens inside or immediately after the rate-limit scheduler's permit acquisition in `run_gh`.
   - The capture logic is a private helper; the public API of the scheduler module remains: `acquire(account_key) -> None` with blocking behaviour.

## Implementation Notes
- `gh` CLI sometimes prints headers in stderr (e.g. `HTTP 403: API rate limit exceeded ...`). Parse both stderr and stdout.
- The `Retry-After` header from the GitHub API v3 response is seconds; `X-RateLimit-Reset` is a Unix epoch.
- Even though the `gh` CLI may not always forward raw response headers in its text output, check common patterns first. The fallback is the safety net.
