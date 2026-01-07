# Task 5: First-Run Setup - Quick Reference

**Full Design:** [06-first-run-setup-design.md](./06-first-run-setup-design.md)  
**Status:** Ready for Implementation (Research Required for Claude/Gemini)

---

## Critical Requirements

### 1. Sequential Setup Flow (NON-NEGOTIABLE)
```
Open terminal 1 → Wait for exit → Delay 1-3s → Open terminal 2 → ...
```

- **One terminal at a time**
- **Wait for process exit** (blocking)
- **1-3 second delay** between agents
- **Clean cancellation** (no orphaned processes)

### 2. No Rerunnable Wizard
- First-run setup shown **once**
- After that: **per-agent actions** in Settings
- **NO "Run Setup Wizard"** button

### 3. User Can Skip
- "Skip Setup" button always available
- App remains fully usable if setup skipped
- Can configure agents later via Settings

---

## Detection Strategies

### Agent Installation
```python
check_agent_installed(agent) -> bool
    return shutil.which(agent) is not None
```

### Login Status

| Agent | Method | Command | Status |
|-------|--------|---------|--------|
| Codex | CLI command | `codex login status` | ✅ Ready |
| Claude | Config files | Check `~/.claude/` | ⚠️ Research needed |
| Copilot | GitHub CLI | `gh auth status` | ✅ Ready |
| Gemini | Settings/env | Check `~/.gemini/settings.json` | ⚠️ Research needed |

---

## Implementation Overview

### New Modules (5 files, ~1200 lines)
```
agents_runner/setup/
  ├── orchestrator.py      (250-300 lines) - Sequential setup flow
  ├── agent_status.py      (200-250 lines) - Install/login detection
  └── commands.py          (100-150 lines) - Agent-specific commands

agents_runner/ui/dialogs/
  └── first_run_setup.py   (250-300 lines) - First-run dialog + progress

agents_runner/ui/pages/
  └── agent_management.py  (200-250 lines) - Settings page section
```

### Modified Files (3 files, ~90 lines)
```
agents_runner/app.py               (~20 lines) - Check setup on launch
agents_runner/ui/pages/settings.py (~30 lines) - Add management section
agents_runner/terminal_apps.py     (~40 lines) - Add blocking terminal launch
```

### Config Files
```
~/.midoriai/agents-runner/setup_state.json
{
  "first_run_complete": true,
  "agents_setup": {"codex": true, "claude": true, ...},
  "setup_date": "2025-01-07T18:30:00Z"
}
```

---

## First-Run Dialog Flow

```
┌─────────────────────────────────────┐
│ First-Time Setup                    │
├─────────────────────────────────────┤
│ Detected agents:                    │
│ ☑ Codex    ✓ Installed ✗ Not logged│
│ ☑ Claude   ✓ Installed ? Unknown   │
│ ☐ Copilot  ✓ Installed ✓ Logged in │
│ ☐ Gemini   ✗ Not installed         │
│                                     │
│ [Skip Setup]    [Begin Setup]      │
└─────────────────────────────────────┘
         ↓ (User clicks Begin)
┌─────────────────────────────────────┐
│ Setup Progress (1 of 2)             │
│ Current: Codex                      │
│ Status: Waiting for terminal...     │
│ [Cancel]                            │
└─────────────────────────────────────┘
         ↓ (Terminal closes)
         ↓ (Wait 2 seconds)
┌─────────────────────────────────────┐
│ Setup Progress (2 of 2)             │
│ Current: Claude                     │
│ Status: Starting in 1s...           │
│ [Cancel]                            │
└─────────────────────────────────────┘
```

---

## Agent Management (Settings)

```
┌──────────────────────────────────────────────────┐
│ Agent Management                                 │
├──────────────────────────────────────────────────┤
│ Agent     Status              Actions            │
│ Codex     ✗ Not logged in     [Login] [Config]  │
│ Claude    ✓ Logged in         [Login] [Config]  │
│ Copilot   ✓ Logged in         [Login] [Config]  │
│ Gemini    ✗ Not installed     [Install Info]    │
│ GitHub    ✓ Logged in (user)  [Login] [Config]  │
└──────────────────────────────────────────────────┘
```

**Actions:**
- **Login:** Opens terminal with `agent login` command (non-blocking)
- **Config:** Opens config file/directory in editor
- **Install Info:** Shows installation instructions for missing agents

**Status Auto-Refresh:** Every 10 seconds

---

## Key Functions

### Setup Orchestration
```python
async def run_sequential_setup(
    agents: list[str],
    progress_callback: Callable
) -> dict[str, bool]:
    """Run setup for multiple agents sequentially."""
    for agent in agents:
        # Launch terminal and WAIT (blocking)
        success = launch_agent_setup_terminal(agent)
        
        # Delay before next (except last)
        await asyncio.sleep(delay_seconds)
    
    return results
```

### Terminal Launch (Blocking)
```python
def launch_terminal_and_wait(
    terminal: TerminalOption,
    command: str
) -> subprocess.CompletedProcess:
    """Launch terminal and WAIT for it to close."""
    args = build_terminal_args(terminal, command)
    return subprocess.run(args)  # Blocks until terminal closes
```

### Status Detection
```python
def check_agent_status(agent: str) -> AgentStatus:
    """Check agent installation and login status."""
    installed = check_agent_installed(agent)
    if not installed:
        return AgentStatus(installed=False, ...)
    
    logged_in, message = check_agent_login(agent)
    return AgentStatus(installed=True, logged_in=logged_in, ...)
```

---

## Setup Commands

```python
AGENT_LOGIN_COMMANDS = {
    "codex": "codex login; read -p 'Press Enter to close...'",
    "claude": "claude setup-token; read -p 'Press Enter...'",
    "copilot": "gh auth login && gh copilot install; read -p 'Press Enter...'",
    "gemini": None,  # RESEARCH NEEDED
}
```

**Why `read -p` at the end?**
- Prevents terminal from auto-closing
- Gives user time to read output/errors
- Clear "I'm done" signal (press Enter)

---

## Research Tasks

### Claude Code
**Questions:**
1. How to detect login status?
   - `claude whoami` launches interactive setup (not suitable)
   - Check config files in `~/.claude/`?
   - Is there a `--check-auth` flag?

2. What files exist when logged in?
   - Auth tokens or session data in `~/.claude/`?

3. Is `claude setup-token` the correct login command?

**Actions:**
- [ ] Test `claude --help` for auth commands
- [ ] Examine `~/.claude/` structure (logged in vs not)
- [ ] Test `claude setup-token` flow
- [ ] Document findings

### Gemini CLI
**Questions:**
1. How to detect login status?
   - Is there a `gemini auth status`?
   - How to validate `GEMINI_API_KEY`?

2. What is `~/.gemini/settings.json` structure?
   - Which fields indicate auth?

3. What is the login command?
   - `gemini auth login`?
   - Manual env var setup only?

**Actions:**
- [ ] Test `gemini --help` for auth commands
- [ ] Examine `~/.gemini/settings.json` structure
- [ ] Check Gemini documentation
- [ ] Document login procedure

---

## Risk Mitigation

### High-Risk: Terminal blocking indefinitely
**Mitigation:**
- Cancel button kills subprocess
- Clear instructions: "Press Enter to close"
- Consider 30-minute timeout

### High-Risk: First-run dialog shows repeatedly
**Mitigation:**
- Write `first_run_complete=true` immediately
- Atomic writes (temp file + rename)
- Thorough testing

### Medium-Risk: Claude/Gemini detection unreliable
**Mitigation:**
- Default to "Unknown" status
- Allow Login action anyway
- Document limitations

---

## Implementation Timeline

| Phase | Duration | Deliverables |
|-------|----------|--------------|
| 1. Detection | 2-3 days | agent_status.py, commands.py |
| 2. Terminal | 1-2 days | terminal_apps.py changes |
| 3. Orchestration | 2-3 days | orchestrator.py |
| 4. First-Run UI | 2-3 days | first_run_setup.py |
| 5. Management UI | 1-2 days | agent_management.py |
| 6. Integration | 1 day | app.py changes |
| 7. Research & Polish | 2-3 days | Claude/Gemini, docs |
| **TOTAL** | **7-10 days** | Matches task breakdown |

---

## Success Criteria

**First-Run Setup:**
- [ ] Dialog appears on fresh install
- [ ] Sequential setup (one at a time, with delays)
- [ ] Clean cancellation
- [ ] Skip button works
- [ ] Doesn't show again after completion

**Per-Agent Management:**
- [ ] Status display with auto-refresh
- [ ] Login/Configure actions work
- [ ] No "Setup Wizard" button

**Error Handling:**
- [ ] Graceful when no terminal available
- [ ] Warning when agent not found
- [ ] Fallback to "Unknown" on detection failure

---

## Integration with Other Tasks

### Task 3: Rate Limit / Cooldown
- Show cooldown status in Agent Management table
- Add cooldown icon: `⏸ On cooldown (42s)`
- Import `AgentWatchState` for status

### Task 6: Environment UI
- Per-agent setup enhances Environment page
- Show agent status in Agents tab

---

## File Size Compliance

All new modules within soft limit (300 lines):
- orchestrator.py: 250-300 ✅
- agent_status.py: 200-250 ✅
- commands.py: 100-150 ✅
- first_run_setup.py: 250-300 ✅
- agent_management.py: 200-250 ✅

Modified files stay well under 600 line hard limit.

---

## Next Steps

1. **Review full design document** (06-first-run-setup-design.md)
2. **Complete research tasks** (Claude, Gemini auth)
3. **Get stakeholder approval**
4. **Begin Phase 1 implementation** (Detection)

---

**Document Version:** 1.0  
**Last Updated:** 2025-01-07  
**Status:** Ready for Review
