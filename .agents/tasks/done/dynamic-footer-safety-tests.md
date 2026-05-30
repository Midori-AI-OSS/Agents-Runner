Build dynamic per-line PR footer safety tests.

## Context

PR attribution footer template (4 lines + blank):
```
{marker}
Created by [Midori AI Agents Runner]({agents_runner_url})
Agent Used: {agent_used}
Related: [Midori AI Monorepo]({midori_ai_url})
```

The `_append_pr_attribution_footer(body, agent_cli=name, agent_display_name=...)` function in `agents_runner/gh/task_plan.py` renders this. We recently removed `agent_cli_args` to stop CLI flags like `--agent plan` from leaking into PRs. We need tests to ensure it stays that way for all agent systems.

## Requirements

1. **Dynamic agent discovery** — use `agents_runner.agent_systems.registry.available_agent_system_names()` and `get_agent_system()` to iterate over every registered agent. Do NOT hardcode agent names in the test logic. Filter out `smoke_agent` (internal_only).

2. **One test per footer line** — for each discovered agent system, test:
   - **Line 1** (marker): is `<!-- midori-ai-agents-runner-pr-footer -->`
   - **Line 2** (created by): contains `Created by [Midori AI Agents Runner](https://github.com/Midori-AI-OSS/Agents-Runner)`
   - **Line 3** (agent used): contains `Agent Used:` and a non-empty agent display; does NOT contain `--` (no CLI flags)
   - **Line 4** (related): contains `Related: [Midori AI Monorepo](https://github.com/Midori-AI-OSS/Midori-AI)`

3. **No CLI flags anywhere** — for every agent system, assert the entire rendered footer does not match the pattern `--\w+` (no `--agent`, `--model`, `--variant`, etc.)

4. **No placeholder leaks** — assert `{marker}`, `{agent_used}`, `{agents_runner_url}`, `{midori_ai_url}` do not appear in the rendered output.

5. **Parameterized/dynamic** — this should be a single parametrize-style test that catches any future agent added to the registry without manual test updates.

6. **Agent display name variants** — also test with `agent_display_name` parameter for at least one agent to ensure the override path is clean too.

## File to modify

`agents_runner/tests/test_pr_footer_attribution.py` — add new tests at the end. Do not remove existing tests unless they are now redundant.

## Import pattern

```python
from agents_runner.agent_systems import available_agent_system_names, get_agent_system
from agents_runner.agent_systems.registry import register_agent_system
```

## Verification

After writing, run: `uv run ruff format . && uv run ruff check . && uv run basedpyright`
Then run just the footer tests: `uv run .agents/scripts/test -- -k footer`

## Completion

Added dynamic parameterized PR footer safety coverage for public registered agent systems, including a display name override case.
