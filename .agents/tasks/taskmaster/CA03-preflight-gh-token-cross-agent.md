# CA03: Forward GH_TOKEN for Cross-Agent Copilot in Preflight

## Context
Preflight worker has similar docker environment setup logic as agent_worker. It also needs to forward GitHub tokens for cross-agent copilot.

The primary agent's CLI is available via `normalize_agent(self._config.agent_cli)` (called inline or stored in a variable).

## Objective
Apply the same token forwarding logic to preflight_worker.py that was implemented in agent_worker.py.

## Code Reuse Decision
Since this is a small check (one helper function), **inline the helper function** in preflight_worker.py rather than extracting to a shared module. This keeps the change localized and avoids premature abstraction.

## Scope
Update `agents_runner/docker/preflight_worker.py` in the `run()` method:
1. Add the `_needs_cross_agent_gh_token()` helper function near the top of the file (same implementation as CA01)
2. After line 294 (existing copilot token forwarding for primary agent)
3. Get agent_cli via `agent_cli = normalize_agent(self._config.agent_cli)`
4. Add conditional check: `if _needs_cross_agent_gh_token(self._config.environment_id) and agent_cli != "copilot"`
5. Forward GH_TOKEN and GITHUB_TOKEN to container environment
6. Log the action: "[auth] forwarding GitHub token for cross-agent copilot"

## Acceptance Criteria
- [ ] Token forwarding logic added after primary agent token forwarding
- [ ] Only triggers if copilot in cross_agent_allowlist AND primary != copilot
- [ ] Uses resolve_github_token() to get token
- [ ] Sets both GH_TOKEN and GITHUB_TOKEN in docker_env
- [ ] Adds -e flags for both env vars to env_args
- [ ] Logs when forwarding for cross-agent
- [ ] Does not duplicate token forwarding if copilot is primary

## Files to Modify
- `agents_runner/docker/preflight_worker.py` (around line 295)

## Dependencies
- CA01 (helper function pattern)
- CA02 (same logic pattern)

## Notes
- Mirror the implementation from agent_worker.py (CA02)
- Inline the `_needs_cross_agent_gh_token()` helper rather than extracting to shared module
- Follow existing logging conventions in preflight_worker.py
- Ensure agent_cli variable is available in scope (may need to call `normalize_agent()`)
- The copilot check is at lines 284-294, so add the cross-agent check immediately after line 294

## Example Structure
```python
# After line 294, add:
agent_cli = normalize_agent(self._config.agent_cli)
if _needs_cross_agent_gh_token(self._config.environment_id) and agent_cli != "copilot":
    token = resolve_github_token()
    if token and "GH_TOKEN" not in (self._config.env_vars or {}):
        self._on_log("[auth] forwarding GitHub token for cross-agent copilot")
        if docker_env is None:
            docker_env = dict(os.environ)
        docker_env["GH_TOKEN"] = token
        docker_env["GITHUB_TOKEN"] = token
        env_args.extend(["-e", "GH_TOKEN", "-e", "GITHUB_TOKEN"])
```
