# GH Background Poll Coalescing per Environment

**Scope:** `agents_runner/ui/pages/github_work_coordinator.py`.
**Dependencies:** none (independent refinement of poll cycle logic)

## Outcome
Background poll cycles do not launch duplicate concurrent fetches for the same (item_type, env_id) key. If a poll cycle wants to refresh an environment that already has an in-flight fetch, it coalesces — waiting for the in-flight result instead of starting a new request.

## Acceptance Criteria

1. **Coalescing per (item_type, env_id) key:**
   - `_begin_fetch` already returns `False` when a key is in `_inflight_keys`. This is correct behavior.
   - Add: when `_begin_fetch` returns `False`, register a lightweight "waiter" so the **poll cycle caller** can block until that in-flight fetch completes, then use the fresh cache result without duplicating the API call.
   - The waiter must not hold the state lock while sleeping; use a `threading.Event` per key.

2. **Poll cycle integration:**
   - In `_run_poll_cycle`, before launching each `_poll_environment_bundle_worker`, check if either the `pr` or `issue` key for that env is already inflight. If so, wait for it (with configurable timeout) instead of spawning a redundant worker.
   - If the timeout expires (e.g. 30 seconds), log a warning and skip that environment for this cycle.

3. **No change to cache TTL or expiry:**
   - Cache entries still expire at `_CACHE_TTL_S` (45s). The coalescing just avoids duplicate API calls within the same window.

4. **Existing behavior preserved:**
   - `request_refresh` with `force=True` (manual refresh) still fetches fresh — coalescing only applies to background poll cycles.
   - The semaphore(2) parallelism in `_run_poll_cycle` is preserved; coalescing just avoids wasteful worker launches.

## Implementation Notes
- The key insight: `_inflight_keys` (type `set[tuple[str, str]]`) already tracks in-flight fetches. Extend it with a companion `dict[tuple[str, str], threading.Event]` (`_inflight_events`) that gets set in `_on_fetch_completed`.
- Do not change `_begin_fetch`'s existing semantics — it still returns `False` for already-inflight keys.
- Add a `_wait_for_inflight(key, timeout_s)` helper used by the poll cycle only.
