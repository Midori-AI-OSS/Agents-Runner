# Eyes Reaction Blocking & In-Memory Anchor Indexing

**Scope:** `agents_runner/ui/pages/github_work_coordinator.py`.
**Dependencies:** none (behavior refinement within the coordinator)
**Risk:** Task-completion signal for re-review gating does not currently exist — see implementation notes.

## Outcome
An `eyes` reaction on any mention anchor is **authoritative**: it permanently blocks automated processing for that mention. Removal of the `eyes` reaction triggers a re-review — but only on the **next** eligible poll cycle **after** the prior task for that work item finishes. In-memory anchor indexing tracks the state.

## Acceptance Criteria

1. **Eyes = block (no exceptions):**
    - In `_collect_auto_reviews`, the `_anchor_has_any_eyes` call (line 568-569 inside `_state_lock`) already skips candidates with eyes reactions. Each source type (issue_comment, review_comment, review_body) is checked differently — the method accepts keyword args (`repo_owner`, `repo_name`, `item_number`, `source`, `anchor_id`, `candidate_comment`), not a single anchor object. This is correct and must remain.
    - Add: if a previously-processed mention gets an `eyes` reaction **after** auto-review was already emitted, block any re-emission of that mention. An in-memory index records: "this mention_key is blocked by eyes".

2. **In-memory anchor index (new data structures):**
    - New `_eyes_blocked_anchors: dict[str, float]` mapping `mention_key` → timestamp when eyes were first detected.
    - Populated during `_collect_auto_reviews` when the `_anchor_has_any_eyes` check returns `True`.
    - When eyes **remain**, the mention stays blocked — never re-emitted, even across subsequent poll cycles. No expiry.

3. **Eyes removal → re-review eligibility:**
    - On the next poll cycle after eyes are **removed** from an anchor:
      - The anchor is no longer in the `eyes` check result.
      - Remove the entry from `_eyes_blocked_anchors`.
    - However: a re-reviewed mention is only emitted if the **prior task** for that same work item (item_key) is finished.
    - **New** `_active_task_by_item: dict[str, float]` → set when `auto_review_requested` is emitted for that item, cleared when the task completes.
    - Re-review emits only when `item_key` has no active task AND eyes are gone AND the mention is the next eligible (same FIFO/poll ordering as today).

4. **No new config keys** — this is behavior refinement, not a feature toggle.

5. **Existing behavior preserved:**
   - First-time detection (no prior eyes, no prior mention emission) still triggers auto-review immediately as it does today.
   - The ordering within a poll cycle (newest-first by `created_at_s` / `sort_id`) is unchanged.
   - The `_auto_review_seen_mentions` set is still the first gate; the new block index is a secondary gate checked after eyes removal.

## Implementation Notes
- Use `_state_lock` for all reads/writes to the new in-memory dicts.
- Do not persist the in-memory index — it lives for the process lifetime.
- `auto_review_requested` (signal at line 59, emitted at line 542 via `_emit_auto_reviews`) carries `(env_id, payload_dict)`. Derive `item_key` from the payload (it includes `item_type`, `number`, `repo_owner`, `repo_name`).
- **Gap: task-completion signal.** There is currently no signal from the task execution system back to the coordinator indicating a task has finished. Without this, the `_active_task_by_item` gate cannot be cleared. Options:
  - (a) Add a new signal `task_completed(str item_key)` and wire it from the task lifecycle.
  - (b) Implement this task without the active-task gate initially, and add it in a follow-up task when the completion signal exists.
  - If neither path is viable when the task is implemented, scope down: skip re-review on eyes removal entirely and only implement the permanent block.

## AUDIT FIX NOTES (2026-08-10)

**Verdict: FAIL** — Re-review path (AC 3) deadlocked. See `/tmp/agents-artifacts/6f9b3ed1-audit-summary.audit.md`.

### FIX 1 (BLOCKER): `_collect_auto_reviews` `queued_snapshot` gates out re-review candidates

`_collect_auto_reviews` line 641-642 takes `queued_snapshot = set(self._auto_review_seen_mentions)` and line 787-788 skips any mention in that snapshot. A mention previously emitted is ALWAYS in `_auto_review_seen_mentions`, so it can never re-enter the candidate queue. The re-review path in `_emit_auto_reviews` (lines 554-561) is unreachable dead code.

Fix: modify the `queued_snapshot` construction to exclude mentions that have `_eyes_blocked_anchors` entries:
```python
with self._state_lock:
    queued_snapshot = set(self._auto_review_seen_mentions) - set(self._eyes_blocked_anchors)
```
This allows blocked-then-unblocked mentions to re-enter when eyes are removed and the API check passes.

### FIX 2 (HIGH): `_auto_review_emit_keys` not cleared on re-review

`_emit_auto_reviews` re-review path (line 555-559) clears `_auto_review_seen_mentions` but NOT `_auto_review_emit_keys`. The dedup guard at line 566-567 (`if emit_key in self._auto_review_emit_keys: continue`) would block the re-review even after FIX 1.

Fix: after `self._auto_review_seen_mentions.discard(mention_key)` at line 559, also add:
```python
self._auto_review_emit_keys.discard(emit_key)
```

### FIX 3 (MEDIUM): `task_completed` Signal has no consumer

Emitted at line 177 but no `.connect()` anywhere. Either wire it or remove it for now.
