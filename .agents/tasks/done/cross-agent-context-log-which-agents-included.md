# Task — Log which cross-agent CLI templates were included in prompt

## 1. Title (short)
Cross-agent context: log included agent CLIs

## 2. Summary (1–3 sentences)
After appending cross-agent CLI templates to the prompt, add a single log statement that lists which agent CLIs were included. This helps with debugging and makes it clear what context the main agent received.

## 3. Rationale / problem statement
Currently, the code logs when individual templates fail to load, but there's no single log statement that summarizes what was successfully included. When debugging cross-agent coordination issues, it's helpful to see a single line like:

```
[env/template/INFO] cross-agent CLI context: copilot, gemini
```

## 4. Proposed design (minimal, reviewable)
After the loop that appends allowlist agent CLI templates (from task #1), collect the successfully loaded CLI names and log them in a single statement:

```python
# 3.5. Append CLI templates for all cross-agents in allowlist
if cross_agents_enabled and env is not None:
    # Build agent_id → agent_cli mapping
    agent_cli_by_id: dict[str, str] = {}
    if env.agent_selection is not None and env.agent_selection.agents:
        agent_cli_by_id = {
            agent.agent_id: agent.agent_cli
            for agent in env.agent_selection.agents
        }
    
    cross_agents_included_clis: list[str] = []  # Initialize tracking list
    
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
                        cross_agents_included_clis.append(normalized_cli)  # Track successful load
                except Exception as exc:
                    self._on_log(
                        format_log(
                            "env",
                            "template",
                            "WARN",
                            f"failed to load templates/agentcli/{normalized_cli} for allowlist: {exc}",
                        )
                    )
    
    # Log summary after loop
    if cross_agents_included_clis:
        self._on_log(
            format_log(
                "env",
                "template",
                "INFO",
                f"cross-agent CLI context: {', '.join(sorted(cross_agents_included_clis))}",
            )
        )
```

**Implementation details:**
- Initialize `cross_agents_included_clis: list[str] = []` immediately after building `agent_cli_by_id`
- After successfully loading and appending each allowlist agent's CLI template, append the `normalized_cli` to the tracking list
- After the loop completes, if the list is non-empty, log a single INFO statement
- Sort the list for deterministic output

## 5. Implementation notes / likely touch points
- File to modify: `agents_runner/docker/agent_worker.py`
- Location: Same section as task #1 (after cross-agents template, before main CLI template)
- Add list initialization: `cross_agents_included_clis: list[str] = []` immediately after `agent_cli_by_id` dict is built
- Add append: `cross_agents_included_clis.append(normalized_cli)` after `template_parts.append(allowlist_cli_prompt)` (inside the successful load path)
- Add log statement after the `for` loop completes
- The log statement should only fire when the list is non-empty (use `if cross_agents_included_clis:`)

## 6. Edge cases to cover
- Empty list (no cross-agents or all failed to load): skip log statement
- Single agent: log shows one name (e.g., `copilot`)
- Multiple agents: log shows comma-separated list (e.g., `codex, gemini`)

## 7. Acceptance criteria (clear, testable statements)
- When cross-agent CLI templates are successfully loaded, a single INFO log lists all included CLI names
- The list is sorted alphabetically for consistency
- If no cross-agent CLI templates are loaded, no log statement is emitted (to avoid clutter)

## 8. Related references
- Depends on: task #1 (cross-agent-context-append-allowlist-templates.md)
- Current code: `agents_runner/docker/agent_worker.py` lines ~445-510
- Logging helper: `agents_runner/log_format.py` (`format_log()`)
