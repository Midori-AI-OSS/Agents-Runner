# CA04: Verify Cross-Agent Copilot Authentication

## Context
After implementing token forwarding for cross-agent copilot, we need to verify the fix works correctly in real scenarios.

## Objective
Manual testing and verification that copilot authenticates properly when used as a cross-agent.

## Test Scenarios

### Scenario 1: Codex primary + Copilot cross-agent
- [ ] Set primary agent to codex
- [ ] Add copilot to cross_agent_allowlist
- [ ] Run task that invokes copilot as cross-agent
- [ ] Verify copilot authentication succeeds
- [ ] Check logs for "[auth] forwarding GitHub token for cross-agent copilot"

### Scenario 2: Claude primary + Copilot cross-agent
- [ ] Set primary agent to claude
- [ ] Add copilot to cross_agent_allowlist
- [ ] Run task that invokes copilot as cross-agent
- [ ] Verify copilot authentication succeeds
- [ ] Check logs for token forwarding message

### Scenario 3: Copilot primary (no cross-agent)
- [ ] Set primary agent to copilot
- [ ] Do NOT add copilot to cross_agent_allowlist
- [ ] Run task
- [ ] Verify copilot authentication succeeds
- [ ] Check logs show primary agent token forwarding only

### Scenario 4: Copilot both primary and cross-agent (edge case)
- [ ] Set primary agent to copilot
- [ ] Add copilot to cross_agent_allowlist (unusual but possible)
- [ ] Run task
- [ ] Verify no duplicate token forwarding
- [ ] Verify authentication works

## Acceptance Criteria
- [ ] All test scenarios pass
- [ ] No authentication errors when copilot is cross-agent
- [ ] Logs show appropriate token forwarding messages
- [ ] No regression for primary copilot agent
- [ ] No duplicate token forwarding in edge cases

## Files to Check
- Container logs from docker run
- Application logs showing token forwarding
- Copilot CLI output (should not show auth errors)

## Dependencies
- CA01 (helper function)
- CA02 (agent_worker implementation)
- CA03 (preflight_worker implementation)

## Notes
- This is a verification task, not a coding task
- Document any issues found during testing
- If issues found, create new task files for fixes
- Test in both interactive and non-interactive modes if applicable
