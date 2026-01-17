# Task — Append CLI templates for all cross-agent allowlist entries

## 1. Title (short)
Cross-agent context: append allowlist agent CLI templates

## 2. Summary (1–3 sentences)
When cross-agents are enabled, the main agent receives the generic cross-agents template and its own CLI template, but it does NOT receive CLI-specific templates for the cross-agents in the allowlist (Codex/Copilot/Gemini/Claude). This prevents the main agent from knowing how to properly invoke and coordinate with those agents.

## 3. Rationale / problem statement
Currently in `agents_runner/docker/agent_worker.py`, the template injection logic (lines ~445-510) does:
1. Append base template
2. Append subagents template  
3. Conditionally append cross-agents template (if `use_cross_agents` is enabled)
4. Always append the main agent's CLI template (e.g., `templates/agentcli/codex.md`)

**Bug:** The main agent never receives the CLI templates for agents in `cross_agent_allowlist`. For example, if the main agent is Codex and the allowlist contains `["copilot-1", "gemini-1"]`, the prompt should include `templates/agentcli/copilot.md` and `templates/agentcli/gemini.md` so Codex knows how to invoke those agents properly.

## 4. Proposed design (minimal, reviewable)
After appending the cross-agents template (step 3), iterate through `env.cross_agent_allowlist` and append the CLI template for each agent in the allowlist:

```python
# 3.5. Append CLI templates for all cross-agents in allowlist
if cross_agents_enabled and env is not None:
    # Build agent_id → agent_cli mapping (reuse existing logic from _needs_cross_agent_gh_token)
    agent_cli_by_id: dict[str, str] = {}
    if env.agent_selection is not None and env.agent_selection.agents:
        agent_cli_by_id = {
            agent.agent_id: agent.agent_cli
            for agent in env.agent_selection.agents
        }
    
    for agent_id in env.cross_agent_allowlist:
        allowlist_agent_cli = agent_cli_by_id.get(agent_id)
        if allowlist_agent_cli:
            normalized_cli = normalize_agent(allowlist_agent_cli)
            # Skip if this is the main agent (already added in step 4)
            if normalized_cli != agent_cli:
                try:
                    allowlist_cli_prompt = load_prompt(f"templates/agentcli/{normalized_cli}").strip()
                    if allowlist_cli_prompt:
                        template_parts.append(allowlist_cli_prompt)
                except Exception as exc:
                    self._on_log(
                        format_log(
                            "env",
                            "template",
                            "WARN",
                            f"failed to load templates/agentcli/{normalized_cli} for allowlist: {exc}",
                        )
                    )
```

**Placement:** Insert this new section between step 3 (cross-agents template) and step 4 (main CLI template) in `agents_runner/docker/agent_worker.py` around line ~481.

## 5. Implementation notes / likely touch points
- File to modify: `agents_runner/docker/agent_worker.py`
- Location: After line ~480 (after cross-agents template append), before line ~482 (main CLI template append)
- Reuse existing helpers: `normalize_agent()` (from `agents_runner.agent_cli`, already imported at top), `load_prompt()`, `format_log()`
- Reuse existing pattern: The `agent_cli_by_id` mapping logic matches `_needs_cross_agent_gh_token()` at lines 49-82
- Add deduplication: skip appending a CLI template if it matches the main agent's CLI (to avoid duplicate sections)
- Variable scope: `env` is already loaded in the outer `try` block starting at line 449
- Variable `agent_cli` is the normalized main agent CLI (set at line 229)

## 6. Edge cases to cover
- Empty allowlist: no-op (already handled by `if cross_agents_enabled`)
- Agent ID in allowlist but not in `agent_selection.agents`: skip silently (agent_cli_by_id lookup returns None)
- Main agent is also in allowlist: skip its CLI template in this loop (it's added in step 4)
- Template file missing for an allowlist agent: log warning and continue

## 7. Acceptance criteria (clear, testable statements)
- When cross-agents are enabled, the main agent's prompt includes CLI templates for all agents in `cross_agent_allowlist` (except the main agent itself)
- Each allowlist agent's CLI template is appended exactly once
- Log messages clearly indicate which CLI templates were loaded for cross-agents
- If a CLI template fails to load, a warning is logged and execution continues

## 8. Related references
- Current code: `agents_runner/docker/agent_worker.py` lines ~445-510 (template injection logic)
- CLI templates: `agents_runner/prompts/templates/agentcli/{codex,copilot,gemini,claude}.md`
- Cross-agent detection: `agents_runner/docker/agent_worker.py` lines ~49-82 (`_needs_cross_agent_gh_token`)

## 9. Completion
- Implemented allowlist CLI template injection in `agents_runner/docker/agent_worker.py` (commit `b73721b`).
