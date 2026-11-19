# Incremental GitHub thread fetches (phase 2 of polling overhead reduction)

Issue
- After the inactivity filter and persistent state land, active items (updated within the filter window) are still re-scanned every poll cycle, and issue-comment lists walk all pages of history before truncating to the newest 300.

Goal
- Add since= based incremental fetches and unchanged-parent skip, with safe semantics:
  - Per-endpoint watermarks advanced only after the entire relevant result range was consumed.
  - Overlapping windows and ID dedup to handle timestamp precision and races.
  - Keep an item dirty until every deferred candidate is evaluated (the current collector emits one candidate per item then breaks, and caps at three per fetch).
  - Periodic full resync with its own timestamp, independent of incremental scans.
  - Policy fingerprints per (env, repo) so a changed trusted-users list or auto-review toggle invalidates evaluation state.
  - Pending eyes anchors always use full scans (no since=) to preserve consent latency.
- Endpoint-specific pagination only: issues comments support since but not sort/direction; PR review comments support since + sort/direction; reviews support neither.

Constraints
- Do not implement a generic descending-sort switch.
- Parent updated_at must not be treated as a complete change sequence (reactions and some edits may not propagate).

Verify
- `uv sync --group ci`
- `uv run ruff check .`
- `uv run basedpyright`
- `.agents/scripts/test`
