# CA01: Add Helper Function to Check Cross-Agent Copilot Presence

## Context
Copilot cross-agents need GH_TOKEN environment variables forwarded to authenticate properly. Currently, only the primary agent gets token forwarding.

The `cross_agent_allowlist` in the Environment model contains **agent_id** strings (e.g., "copilot-1", "claude-main"), not CLI names. To determine if copilot is in the cross-agents, we must:
1. Load the environment configuration
2. Access the `agent_selection.agents` list (if available)
3. For each agent_id in `cross_agent_allowlist`, look up the corresponding AgentInstance
4. Check if any have `agent_cli == "copilot"`

## Objective
Create a reusable helper function to check if copilot is present in the cross-agent allowlist.

## Scope
Add a new helper function in `agents_runner/docker/agent_worker.py`:
- Function name: `_needs_cross_agent_gh_token()`
- Parameters: `environment_id: str | None`
- Returns: `bool` (True if any cross-agent uses copilot CLI)
- Logic:
  1. If environment_id is None, return False
  2. Load environment via `load_environments().get(str(environment_id))`
  3. If env is None or `cross_agent_allowlist` is empty, return False
  4. If `env.agent_selection` is None or `env.agent_selection.agents` is empty, return False
  5. Build a dict mapping agent_id → agent_cli for quick lookup
  6. For each agent_id in `cross_agent_allowlist`:
     - Look up the agent_cli from the dict
     - Use `normalize_agent(agent_cli)` to get canonical name
     - If it equals "copilot", return True
  7. Return False if no copilot found

## Acceptance Criteria
- [x] Helper function added to agent_worker.py
- [x] Function checks cross_agent_allowlist for copilot agents
- [x] Returns True if copilot is in the allowlist, False otherwise
- [x] Function handles None/empty allowlist gracefully
- [x] Function uses normalize_agent() for CLI comparison

## Completion Notes
- Helper function `_needs_cross_agent_gh_token()` implemented in agent_worker.py at lines 49-82
- Function placed after imports and before DockerAgentWorker class as specified
- All acceptance criteria met
- Committed as e806fa8 with message "[FEAT] Add helper function to check cross-agent copilot presence"

## Files to Modify
- `agents_runner/docker/agent_worker.py`

## Dependencies
None

## Notes
- Keep function simple and focused on one task
- Follow existing code style in agent_worker.py
- Place helper function near the top of the file (after imports, before DockerAgentWorker class)
- Import `from agents_runner.environments import load_environments` if not already present
- Import `from agents_runner.environments.model import AgentInstance` if needed for type hints

## Example Structure
```python
def _needs_cross_agent_gh_token(environment_id: str | None) -> bool:
    """Check if copilot is in the cross-agent allowlist.
    
    Returns True if any agent in cross_agent_allowlist uses copilot CLI.
    """
    if not environment_id:
        return False
    
    # Load environment and validate structure
    # Build agent_id → agent_cli mapping
    # Check each allowlisted agent_id for copilot
    # Return True if found, False otherwise
```

---

## AUDITOR FEEDBACK (2026-01-16)

**Status:** RETURNED TO WIP - Integration Required

**Issue:** The helper function was implemented correctly but is never used in the codebase. Zero call sites found.

**What needs to be fixed:**
1. **Integrate the function** - The function must be called somewhere to actually solve the problem. Options:
   - Expand CA01 scope to include integration in agent_worker.py, OR
   - Move forward to CA02 which should use this helper function
   
2. **Add tests** (recommended) - Unit tests covering:
   - Returns False when environment_id is None
   - Returns False when environment doesn't exist  
   - Returns False when cross_agent_allowlist is empty
   - Returns True when copilot is in allowlist
   - Returns False when only non-copilot agents in allowlist

**Current state:** Function exists at `agent_worker.py:49-82` but provides no value without integration.

**Next steps:** 
- Clarify if CA01 should include integration or if that's CA02's scope
- If CA01 is "helper only", mark it complete and immediately start CA02
- If CA01 should include integration, implement the function call in agent_worker.py

**Audit report:** `/tmp/agents-artifacts/d15e7ae0-audit-ca01.audit.md`

---

## INTEGRATION COMPLETE (2026-01-16)

**Status:** COMPLETED

**Integration details:**
- Added `elif` clause in `agent_worker.py` after primary agent token forwarding (line 666)
- Calls `_needs_cross_agent_gh_token(self._config.environment_id)` to check for copilot in cross-agents
- Forwards GH_TOKEN and GITHUB_TOKEN when copilot is in cross_agent_allowlist
- Uses `elif` to prevent duplicate forwarding when copilot is the primary agent
- Logs "[auth] forwarding GitHub token for cross-agent copilot" for visibility
- Committed as 5b5363a with message "[FEAT] Integrate cross-agent GH token helper function"

**All acceptance criteria now met:**
- [x] Helper function added to agent_worker.py
- [x] Function checks cross_agent_allowlist for copilot agents
- [x] Returns True if copilot is in the allowlist, False otherwise
- [x] Function handles None/empty allowlist gracefully
- [x] Function uses normalize_agent() for CLI comparison
- [x] **Function is now integrated and called in agent_worker.py**

**Task complete - ready to move to done/**
