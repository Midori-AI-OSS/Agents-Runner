# App-Wide GitHub Prefetch, RAM Cache, and Auto-Review Dedup

## Goal
Implement app-wide background prefetch for GitHub Issues/PRs across repo-enabled environments, keep results in RAM for instant UI load, and preserve safe ping/auto-review behavior without duplicate emits.

## Current Behavior (verified)
- GitHub Issues/PR polling is active only when that pane is active.
- Each fetch targets only the currently active environment.
- Poll interval defaults to 30s and clamps to a minimum of 5s.
- Initial loading skeleton is shown once per `(item_type, env_id)`.
- Mention reactions: `eyes` for PR comment mention; `rocket` for issue comment mention.
- Task finalization and PR flow already has background dedupe/safety guards.

## Required Outcome
1. Poll repo-enabled environments app-wide, not only when PR/Issues pane is visible.
2. Cache per `(item_type, env_id)` in RAM with TTL `45s` and stale-while-refresh behavior.
3. Use `2` concurrent workers and a `2s` stagger between environment starts.
4. Keep current active-pane UX, but serve cached data instantly when user opens PR/Issues panes or switches environments.
5. Keep reaction semantics and queue-time ping marking behavior.
6. Prevent duplicate `auto_review_requested` emits across overlapping background/foreground refreshes.

## In Scope
- `agents_runner/ui/pages/github_work_list.py`
- `agents_runner/ui/pages/tasks.py`
- New shared prefetch/cache coordinator module under `agents_runner/ui/pages/` (or equivalent UI package location)
- Wiring/settings flow for poll interval and environments

## Out of Scope
- No changes to GitHub CLI API wrappers in `agents_runner/gh/work_items.py` unless strictly required by implementation details.
- No changes to PR creation logic in finalization flows.
- No persistence cache on disk (RAM only).

## Implementation Requirements
1. Add a shared coordinator to own:
- environment filtering (`resolve_environment_github_repo(...)` only)
- background polling scheduler
- per-key in-flight tracking
- RAM cache entries
- auto-review dedupe state

2. Cache key/value model:
- Key: `(item_type, env_id)`
- Value includes:
  - `items`
  - `repo_context`
  - `error`
  - `fetched_at`
  - `expires_at`
  - `refreshing` flag

3. Polling model:
- App-wide timer-driven cycles.
- Respect existing settings interval (`github_poll_interval_s`) with min `5s`.
- Each cycle scans repo-enabled environments only.
- Process with max 2 concurrent workers.
- Start each environment fetch with 2s spacing to reduce burst pressure.
- Fetch issue/pr streams in deterministic order per env.

4. Stale-while-refresh behavior:
- Fresh cache: return immediately.
- Expired cache: return stale immediately and schedule refresh if not already in-flight.
- Missing cache: show current loading behavior and fetch.

5. Auto-review and ping safety:
- Keep existing reaction policy:
  - PR mention -> `eyes`
  - Issue mention -> `rocket`
- Keep queue-accepted semantics for marking/emit flow.
- Add idempotency guard key to avoid duplicate emits across races:
  - `{repo_owner}/{repo_name}:{item_type}:{number}:{trigger_source}:{mention_comment_id}`
- Ensure state mutation + emit decision is atomic under synchronization.

6. UI integration:
- `TasksPage` owns one coordinator instance shared by PR and Issues pages.
- PR/Issues pages render cache immediately on pane/env activation.
- Preserve existing one-time initial skeleton behavior per `(item_type, env_id)`.

## Guardrails
- Never run duplicate fetches for the same cache key concurrently.
- Do not clear last known good cache on transient failures.
- Keep warning/error logs deduplicated to avoid repeated spam for same failure text.
- Ensure background polling does not emit duplicate prompt events when user also triggers manual refresh.

## Acceptance Criteria
1. With multiple repo-enabled environments, data refreshes app-wide without needing PR/Issues pane open.
2. Non-repo environments are skipped.
3. Switching to PR/Issues pane displays cached rows instantly if present.
4. Polling concurrency and staggering respect:
- max two environments in progress at once
- roughly 2s spacing between env fetch starts
5. No duplicate `auto_review_requested` emissions for the same mention/trigger under concurrent refresh conditions.
6. Reactions remain correct (`eyes` PR, `rocket` issue) and are not repeatedly re-applied.
7. Existing active-pane behavior remains functional (no regression).

## Verification Checklist
- Manual:
  - open app with at least 3 repo-enabled environments
  - observe background refresh while not on PR/Issues pane
  - switch panes/environments and confirm instant cache render
  - confirm dedupe by repeating manual refresh during auto-poll cycle
- Logs/diagnostics:
  - verify in-flight dedupe behavior
  - verify stagger timing in fetch start logs
  - verify single emit per idempotency key

## References
- `agents_runner/ui/pages/tasks.py`
- `agents_runner/ui/pages/github_work_list.py`
- `agents_runner/ui/main_window_task_events.py`
- `agents_runner/ui/main_window_task_recovery.py`
- `agents_runner/ui/main_window_tasks_interactive_finalize.py`
