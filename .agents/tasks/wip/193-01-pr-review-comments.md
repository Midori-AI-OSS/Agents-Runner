# Task: Deep PR 193 Review and Comment Resolution

**Role:** Coder  
**Estimated Time:** 2-3 hours  
**Dependencies:** None (can start immediately)

## Objective
Review PR #193 (Unify run planning and agent plugins) in depth and verify all copilot-pull-request-reviewer comments are addressed.

## Context
- PR: https://github.com/Midori-AI-OSS/Agents-Runner/pull/193
- Branch: `midoriaiagents/60d23c757d`
- Status: Open, 18 comments from copilot-pull-request-reviewer (accessed via `gh pr view 193 --comments`)
- Key comment (low confidence): `requires_github_token()` depends on plugin registry being populated but docker worker code doesn't appear to call `discover_plugins()` at `agents_runner/docker/preflight_worker.py:364`
- Comment count as of last check: 18 total (1 suppressed due to low confidence, shown in details)

## Prerequisites
- `gh` CLI installed and authenticated (verify with `gh auth status`)
- Repository cloned and on branch `midoriaiagents/60d23c757d`
- Ability to push commits to the branch

## How to Access Comments
```bash
# View all PR comments in terminal
gh pr view 193 --comments

# View PR in web browser (if detailed review needed)
gh pr view 193 --web
```

## Acceptance Criteria
1. **Read and inventory all comments:**
   - Run `gh pr view 193 --comments` to see all 18 reviewer comments
   - Create a checklist in `/tmp/agents-artifacts/<hex>-pr193-comments-checklist.md` with each comment
   - For each comment, note: file path, line number, concern raised, initial assessment (valid/not applicable)

2. **For each actionable comment:**
   - **Code inspection:** Read the flagged code and surrounding context
   - **Verification method:** Determine how to verify (code trace, runtime test, or both)
   - **If valid and not fixed:** 
     - Implement the fix in code
     - Add a comment in the checklist explaining the fix
     - Commit with format: `[FIX] Address PR comment: <short summary>` (reference file:line if helpful)
   - **If not applicable:**
     - Document in checklist why it's not applicable
     - Consider adding a reply comment on GitHub (via `gh pr comment 193 --body "..."`) to clarify for reviewers

3. **Special focus: `requires_github_token()` plugin discovery issue:**
   - File: `agents_runner/docker/preflight_worker.py:364`
   - Concern: `requires_github_token(agent_cli)` may return False if plugins not discovered
   - Investigation steps:
     a. Search for all calls to `discover_plugins()` in the codebase: `grep -r "discover_plugins" agents_runner/`
     b. Trace execution path from docker worker startup to `requires_github_token()` call
     c. Verify if plugin discovery happens before the check (code inspection)
     d. If missing, add `discover_plugins()` call at appropriate point in worker initialization
     e. Verify similar issue doesn't exist in `agents_runner/docker/agent_worker_helpers.py` or `agents_runner/docker/agent_worker_container.py`

4. **Verify plugin discovery in all execution paths:**
   - Interactive path: Check `agents_runner/ui/runtime/app.py` (should trigger discovery)
   - Non-interactive path: Check `agents_runner/docker/agent_worker_container.py` and related worker modules
   - Create a mapping document showing where `discover_plugins()` is called for each path

5. **Final verification:**
   - Run `ruff format .` and `ruff check .` to ensure code style compliance
   - Run `git --no-pager diff` to review all changes before committing
   - Push all fix commits to the branch: `git push origin midoriaiagents/60d23c757d`

## Success Criteria
- ✅ All 18 comments reviewed and documented in checklist
- ✅ All valid, actionable comments either fixed or explained
- ✅ Plugin discovery verified in all execution paths (with mapping document)
- ✅ Commits pushed with clear `[FIX]` messages
- ✅ Checklist saved to `/tmp/agents-artifacts/<hex>-pr193-comments-checklist.md` for audit trail

## Notes
- Do not suppress or dismiss comments without investigation
- Prefer code fixes over "working as designed" responses unless truly justified
- Check if similar issues exist in other files not flagged by the reviewer
- If you find a comment that requires significant refactoring (>200 lines change), note it in checklist and consider filing a separate task
