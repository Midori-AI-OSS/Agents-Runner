# Task — Deduplicate main agent CLI template when it's in allowlist

## 1. Title (short)
Cross-agent context: dedupe main agent template

## 2. Summary (1–3 sentences)
When the main agent's CLI is also listed in the cross-agent allowlist, its CLI template gets appended twice (once in the allowlist loop, once in the "always append main CLI" step). Add deduplication logic to skip the main agent's CLI template during the allowlist loop.

## 3. Rationale / problem statement
Current flow (after task #1):
1. Iterate `cross_agent_allowlist`, append each agent's CLI template
2. Always append main agent's CLI template

**Bug scenario:** If `agent_cli="copilot"` and `cross_agent_allowlist=["copilot-1", "gemini-1"]` where `copilot-1` uses `copilot` CLI, the prompt will contain `templates/agentcli/copilot.md` twice.

**Fix:** Skip appending a CLI template in the allowlist loop if it matches the main agent's CLI (since it will be added in step 4 anyway).

## 4. Proposed design (minimal, reviewable)
In the allowlist loop (from task #1), add a check before loading each template:

```python
for agent_id in env.cross_agent_allowlist:
    allowlist_agent_cli = agent_cli_by_id.get(agent_id)
    if allowlist_agent_cli:
        normalized_cli = normalize_agent(allowlist_agent_cli)
        # Skip if this is the main agent (already added in step 4)
        if normalized_cli == agent_cli:
            continue
        try:
            # ... load and append template
```

**Key check:** `if normalized_cli == agent_cli: continue`

This ensures each CLI template appears exactly once in the final prompt.

## 5. Implementation notes / likely touch points
- File to modify: `agents_runner/docker/agent_worker.py`
- Location: Inside the allowlist loop (task #1)
- Add comparison: `if normalized_cli == agent_cli: continue`
- `agent_cli` is the normalized main agent CLI (set at line 229 via `normalize_agent(self._config.agent_cli)`)
- Both `normalized_cli` and `agent_cli` use the same `normalize_agent()` function, so direct string comparison is safe

## 6. Edge cases to cover
- Main agent is the only agent in allowlist: all entries skipped, only main CLI template added in step 4
- Main agent appears multiple times in allowlist (unusual but possible): all occurrences skipped
- Different agent ID but same CLI as main agent (e.g., `copilot-1` and `copilot-2` both use `copilot`): all skipped

## 7. Acceptance criteria (clear, testable statements)
- Each CLI template appears at most once in the final prompt
- If the main agent's CLI is in the allowlist, it's only added once (in step 4, not during allowlist loop)
- Other allowlist agent CLI templates are added as expected

## 8. Related references
- Depends on: task #1 (cross-agent-context-append-allowlist-templates.md)
- Current code: `agents_runner/docker/agent_worker.py` line ~229 (`agent_cli = normalize_agent(...)`)
- Helper: `agents_runner/agent_cli.py` (`normalize_agent()`)
