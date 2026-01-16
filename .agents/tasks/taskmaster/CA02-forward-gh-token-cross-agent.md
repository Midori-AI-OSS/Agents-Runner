# CA02: Forward GH_TOKEN for Cross-Agent Copilot

## Status: COMPLETED

Implementation was already present in agent_worker.py at line 666. Updated the conditional to include explicit `and agent_cli != "copilot"` check per task specification for improved code clarity.

All acceptance criteria met:
- Token forwarding logic present after primary agent token forwarding (line 666)
- Only triggers if copilot in cross_agent_allowlist AND primary != copilot (explicit check added)
- Uses resolve_github_token() to get token
- Sets both GH_TOKEN and GITHUB_TOKEN in docker_env
- Adds -e flags for both env vars to env_args
- Logs when forwarding for cross-agent
- Does not duplicate token forwarding if copilot is primary

Commit: e20d2c1

## Context
When copilot is used as a cross-agent (not the primary agent), it needs GitHub authentication via GH_TOKEN/GITHUB_TOKEN environment variables. Currently, these are only forwarded for the primary agent.

The primary agent's CLI is already available in the `agent_cli` variable (normalized at line 193, used at line 616).

## Objective
Modify the docker environment setup in agent_worker.py to forward GitHub tokens when copilot is in the cross-agent allowlist.

## Scope
Update `agents_runner/docker/agent_worker.py` in the `run()` method:
- After line 629 (existing copilot token forwarding for primary agent)
- Add conditional check using helper from CA01: `if _needs_cross_agent_gh_token(self._config.environment_id) and agent_cli != "copilot"`
- The helper loads the environment, checks agent_selection.agents, and returns True if copilot is in cross_agent_allowlist
- Forward GH_TOKEN and GITHUB_TOKEN to container environment (same pattern as lines 626-629)
- Log the action: "[auth] forwarding GitHub token for cross-agent copilot"

## Acceptance Criteria
- [ ] Token forwarding logic added after primary agent token forwarding
- [ ] Only triggers if copilot in cross_agent_allowlist AND primary != copilot
- [ ] Uses resolve_github_token() to get token
- [ ] Sets both GH_TOKEN and GITHUB_TOKEN in docker_env
- [ ] Adds -e flags for both env vars to env_args
- [ ] Logs when forwarding for cross-agent
- [ ] Does not duplicate token forwarding if copilot is primary

## Files to Modify
- `agents_runner/docker/agent_worker.py` (around line 630)

## Dependencies
- CA01 (helper function must exist first)

## Notes
- Mirror the existing token forwarding pattern (lines 616-629)
- Ensure no duplicate forwarding when copilot is both primary and cross-agent
- Follow existing logging conventions
- The `agent_cli` variable contains the primary agent's normalized CLI name
- The conditional `agent_cli != "copilot"` ensures we don't duplicate token forwarding

## Example Structure
```python
# After line 629, add:
if _needs_cross_agent_gh_token(self._config.environment_id) and agent_cli != "copilot":
    # Reuse the token from resolve_github_token() call above, or call again
    token = resolve_github_token()
    if token and "GH_TOKEN" not in (self._config.env_vars or {}):
        self._on_log("[auth] forwarding GitHub token for cross-agent copilot")
        # Ensure docker_env is initialized (it should be from line 626)
        if docker_env is None:
            docker_env = dict(os.environ)
        docker_env["GH_TOKEN"] = token
        docker_env["GITHUB_TOKEN"] = token
        env_args.extend(["-e", "GH_TOKEN", "-e", "GITHUB_TOKEN"])
```
