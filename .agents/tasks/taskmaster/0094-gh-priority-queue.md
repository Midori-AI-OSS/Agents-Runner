# GH Priority Queue: Manual Refresh & PR Creation

**Scope:** `agents_runner/gh/rate_limiter.py` (scheduler), `agents_runner/ui/pages/github_work_coordinator.py`.
**Dependencies:** #0091 (modifies the scheduler's `acquire` method; must coordinate on priority-passing mechanism)

## Outcome
Manual refresh requests and PR creation get priority treatment in the rate-limit scheduler: they execute immediately after the currently in-flight `gh` call completes, jumping ahead of any queued background poll work.

## Acceptance Criteria

1. **Priority levels in the scheduler:**
   - Define two priority tiers: `HIGH` (manual refresh, PR creation) and `LOW` (background polling, auto-reactions, other automated work).
   - `HIGH` permits are always served before `LOW` when both are waiting.
   - Within the same tier, FIFO order.

2. **Integration points — `HIGH` tier:**
    - `GitHubWorkCoordinator.request_refresh(force=True)` → `HIGH`
    - `commit_push_and_pr` (`gh pr create` call path) → `HIGH`
    - Any call from UI-triggered actions (e.g. manual refresh button) → `HIGH`

3. **Integration points — `LOW` tier:**
    - `GitHubWorkCoordinator._poll_environment_bundle_worker` → `LOW`
    - `GitHubWorkCoordinator.request_refresh(force=False)` → `LOW`
    - Background auto-review reaction checks (in `work_items.py` `sync_github_work_items`, which calls `run_gh`) → `LOW`
    - All other automated `run_gh` calls (default) → `LOW`

4. **In-flight work handling:**
   - A `LOW` permit that is currently executing is NOT preempted.
   - When that in-flight `LOW` call finishes, the scheduler checks the queue and serves all waiting `HIGH` permits before resuming `LOW`.

5. **No starvation:**
   - If `HIGH` requests keep arriving, impose no cap — this is intentional: user actions always beat background work.

## Implementation Notes
- Modify the scheduler's `acquire` to accept a `priority` parameter (default `LOW`).
- **Priority passing mechanism:** Since #0091 requires `run_gh` signature not to change, add a thread-local or context-variable stack so callers can push a priority before calling `run_gh`:
  - `rate_limiter.push_priority(Priority.HIGH)` / `pop_priority()` context manager.
  - The wrapper inside `run_gh` reads the current thread priority from this context.
  - Callers at the listed integration points wrap their calls with the context manager.
- The polling coordinator's `_run_poll_cycle` already uses a `threading.Semaphore(2)` for parallelism. The scheduler is below that — each worker thread calls `run_gh` and blocks on the scheduler.
- Do not change the polling coordinator's existing semaphore/concurrency model.
