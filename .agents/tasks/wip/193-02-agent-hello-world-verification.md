# Task: Verify All Agent Systems Start and Respond

**Role:** QA  
**Estimated Time:** 1-2 hours  
**Dependencies:** None (can start immediately)

## Objective
Verify each agent system (Codex, Claude, Copilot, Gemini) can start and reply with "hello world" via the unified planner.

## Context
- Run program: `sudo uv run main.py` (requires sudo for docker socket access)
- Agent systems: codex, claude, copilot, gemini (in `agents_runner/agent_systems/`)
- Expected: Claude should surface an authentication error (no API key configured)
- Test both interactive and non-interactive execution paths
- Agent systems discovered: `/home/midori-ai/workspace/agents_runner/agent_systems/{codex,claude,copilot,gemini}`

## Prerequisites
- Docker installed and running (verify with `docker ps`)
- `sudo` access for docker socket
- UV environment set up (run `uv sync` if needed)
- API keys NOT configured for Claude (to verify auth error handling)
- API keys configured for other agents (Codex, Copilot, Gemini) or acceptable to see their auth errors too

## Test Commands

### Interactive Mode (if available)
```bash
# Check if interactive mode exists
sudo uv run main.py --help | grep -i interactive

# If interactive flag exists, test each agent:
sudo uv run main.py --interactive --agent codex --prompt "hello world"
sudo uv run main.py --interactive --agent claude --prompt "hello world"
sudo uv run main.py --interactive --agent copilot --prompt "hello world"
sudo uv run main.py --interactive --agent gemini --prompt "hello world"
```

### Non-Interactive Mode
```bash
# Test each agent system with simple prompt
# (Adjust flags based on actual CLI - check main.py --help first)
sudo uv run main.py --agent codex "hello world"
sudo uv run main.py --agent claude "hello world"
sudo uv run main.py --agent copilot "hello world"
sudo uv run main.py --agent gemini "hello world"
```

### Discovery Phase
Before running tests, determine actual CLI syntax:
```bash
# Get main.py help to understand flags
sudo uv run timeout 5 python main.py --help 2>&1 || echo "Help timed out or errored"

# Check for agent selection method
grep -r "argparse\|add_argument" main.py | head -20
grep -r "agent.*system\|--agent" agents_runner/
```

## Acceptance Criteria
1. **CLI Discovery:**
   - Document actual CLI syntax for agent selection (what flags/arguments exist?)
   - Identify if interactive mode exists and how to invoke it
   - Save CLI help output to `/tmp/agents-artifacts/<hex>-cli-help.txt`

2. **For each agent system (codex, claude, copilot, gemini):**
   - Launch with prompt "hello world" using discovered CLI syntax
   - Capture full output (stdout + stderr) to individual files: `/tmp/agents-artifacts/<hex>-<agent>-output.txt`
   - Verify container starts successfully:
     - Check `docker ps` during execution to see container
     - Check `docker logs <container-id>` if available
     - Note container behavior (starts, runs, exits cleanly or errors)
   - Document actual behavior vs expected:
     - Success: agent responds (any variation of greeting or acknowledgment)
     - Auth error: clear error message about missing API key (expected for Claude)
     - Other error: document unexpected behavior

3. **Claude-specific verification:**
   - Confirm it surfaces an auth error (missing API key) rather than silent failure
   - Error message should be clear and actionable (e.g., "Claude API key not found in config")
   - Verify error happens early (not after container start delay)
   - If Claude succeeds (key exists), document that and note for task 193-04 to verify config

4. **Create verification report at `.agents/reviews/193-agent-verification.md` with:**
   - Command used for each test (exact command line)
   - Actual output/behavior (summary + reference to artifact file)
   - Pass/fail status per agent:
     - ✅ Pass: Agent starts, responds appropriately OR shows expected auth error
     - ⚠️ Warn: Agent starts but unexpected behavior
     - ❌ Fail: Agent doesn't start, silent failure, or unclear error
   - Any issues discovered (with recommendation to file separate task if needed)
   - Container behavior observations (startup time, clean exit, resource usage if notable)

## Output Capture Method
```bash
# Capture stdout and stderr separately
sudo uv run main.py <agent-flags> "hello world" > /tmp/agents-artifacts/<hex>-<agent>-stdout.txt 2> /tmp/agents-artifacts/<hex>-<agent>-stderr.txt

# Or combined
sudo uv run main.py <agent-flags> "hello world" &> /tmp/agents-artifacts/<hex>-<agent>-output.txt

# Check docker during run (in another terminal)
docker ps | grep -E "codex|claude|copilot|gemini"
```

## Success Criteria
- ✅ All 4 agent systems tested with "hello world" prompt
- ✅ Output captured for each test
- ✅ Claude shows clear auth error (or documented why it didn't)
- ✅ Verification report created at `.agents/reviews/193-agent-verification.md`
- ✅ Pass/fail status determined for each agent
- ✅ Any bugs/issues documented with recommendation to file separate tasks

## Notes
- Use `sudo uv run main.py` for docker socket access
- If any agent fails to start or respond, file separate bug task
- Do not fix bugs in this task - only verify and document
- If interactive mode doesn't exist, document that (may be GUI-only)
- If main.py help hangs, use timeout (e.g., `timeout 10 sudo uv run main.py --help`)
