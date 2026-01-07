# Unstable Refactor Task Breakdown

**Project:** Agents-Runner Unstable Refactor  
**Document ID:** 02-task-breakdown  
**Created:** 2025-01-07  
**Based on Audit:** 86f460ef-codebase-structure.audit.md  

---

## Executive Summary

This document provides a detailed breakdown of the unstable refactor into 9 primary tasks, with sub-task assignments for specialized agents (auditor, coder, qa). The refactor addresses critical gaps in reliability, user experience, and architectural clarity while maintaining the existing modular structure.

**Key Objectives:**
1. Implement reliable retry/fallback/container restart mechanisms
2. Build generalized usage/rate-limit watch system with consistent cooldown UX
3. Create sequential first-run setup + per-agent management interface
4. Enable live artifact browsing/editing during runtime (no encryption while running)
5. Add spell checker to New Task prompt editor
6. Show Desktop/Artifacts tabs only when usable
7. Provide GitHub context for ALL agents (both git-locked and folder-locked environments)

**Timeline Estimate:** 4-6 weeks for full implementation  
**Risk Level:** MEDIUM (requires careful coordination, no breaking UI changes)

---

## Overall Refactor Strategy

### Architectural Approach

**Keep:**
- Existing modular file structure
- PySide6 UI framework
- Docker-based agent execution
- Environment/task data models
- Mixin pattern for MainWindow (simplify where possible)

**Add:**
- Service layer for task/agent coordination
- Agent selection/retry/fallback system
- Rate limit detection and cooldown management
- Setup orchestration system
- Live artifact access (bypass encryption during runtime)
- Spell checker integration
- GitHub context system for all agents

**Refactor:**
- `docker/agent_worker.py` - Split run supervision from execution
- MainWindow mixins - Extract task/agent services
- Artifact system - Add runtime bypass mode
- Tab visibility - Conditional rendering based on state

### Design Principles

1. **No Hang Detection** - Only react to explicit signals (process exit, container stop, error codes)
2. **Sequential Setup** - One agent setup terminal at a time, with delays between
3. **Cooldown at Launch** - Check cooldown when user clicks Run Agent, not before
4. **Task-Scoped Fallback** - Fallback selection for single task only, don't change defaults
5. **No Breaking Changes** - All existing functionality must continue working
6. **File Size Discipline** - Soft limit 300 lines, hard limit 600 lines

---

## Task Dependency Graph

```
                    ┌─────────────┐
                    │   Task 1    │
                    │ Refactor    │
                    │  Plan & UI  │
                    │     Map     │
                    └──────┬──────┘
                           │
           ┌───────────────┼───────────────┐
           │               │               │
           ↓               ↓               ↓
    ┌──────────┐    ┌──────────┐    ┌──────────┐
    │  Task 2  │    │  Task 3  │    │  Task 5  │
    │   Run    │    │  Usage/  │    │  Setup   │
    │Supervisor│    │Rate Limit│    │  System  │
    └────┬─────┘    └────┬─────┘    └────┬─────┘
         │               │               │
         │               │               └───────┐
         │               └───────────┐           │
         │                           │           │
         ↓                           ↓           ↓
    ┌──────────┐              ┌──────────┐ ┌──────────┐
    │  Task 4  │              │  Task 6  │ │  Task 7  │
    │  GitHub  │              │Envs UI   │ │Spellcheck│
    │ Context  │              │ Clarity  │ └──────────┘
    └────┬─────┘              └──────────┘
         │
         │
         ↓
    ┌──────────┐
    │  Task 8  │
    │   Task   │
    │View Tabs │
    └────┬─────┘
         │
         ↓
    ┌──────────┐
    │  Task 9  │
    │   Live   │
    │Artifacts │
    └──────────┘
```

**Critical Path:** Task 1 → Task 2 → Task 4 → Task 9  
**Parallel Tracks:** 
- Track A (Agent System): Task 2 → Task 3 → Task 6
- Track B (Setup): Task 5 → Task 6
- Track C (UX Polish): Task 7, Task 8

---

## Task 1: Refactor Plan & UI Map

**Owner:** Auditor  
**Complexity:** Low  
**Estimated Time:** 2-3 days  
**Dependencies:** None  
**Status:** IN PROGRESS (this document)

### Objectives
- Create comprehensive task breakdown (this document)
- Map all UI touchpoints for new features
- Design service layer architecture
- Define agent selection/retry state machines
- Document critical implementation details

### Deliverables

1. **This Document** (`.codex/audit/02-task-breakdown.md`)
   - Complete task breakdown with sub-assignments
   - Dependency graph
   - Risk analysis

2. **Architecture Decision Records** (`.agents/notes/`)
   - `adr-001-agent-selection-strategy.md` - How agent selection/fallback works
   - `adr-002-cooldown-ux-flow.md` - Cooldown modal timing and flow
   - `adr-003-setup-orchestration.md` - First-run setup sequencing
   - `adr-004-live-artifacts.md` - Runtime artifact access design

3. **UI Wireframes** (`.agents/notes/`)
   - `ui-cooldown-modal.md` - Cooldown modal design
   - `ui-setup-wizard.md` - First-run setup flow
   - `ui-agent-management.md` - Per-agent settings UI

### Sub-Tasks

- [x] Review audit report (86f460ef)
- [x] Create task breakdown structure
- [ ] **Auditor:** Design agent selection state machine
- [ ] **Auditor:** Design cooldown detection/UX flow
- [ ] **Auditor:** Design setup orchestration system
- [ ] **Auditor:** Create UI wireframes for new components
- [ ] **QA:** Review architectural decisions for completeness

### Success Criteria
- All 9 tasks have clear deliverables and dependencies
- Architecture decisions documented with rationale
- Team consensus on approach before implementation begins

### Notes
- This task is primarily documentation, no code changes
- Output will guide all subsequent tasks
- Must get stakeholder approval before proceeding to Task 2

---

## Task 2: Run Supervisor (Retry + Fallback + Container Restart)

**Owner:** Coder  
**Complexity:** High  
**Estimated Time:** 7-10 days  
**Dependencies:** Task 1  
**Blocks:** Task 4, Task 8, Task 9

### Objectives
- Implement reliable retry mechanism with exponential backoff
- Add agent fallback system (use existing AgentSelection UI)
- Handle container crashes gracefully with restart capability
- Detect non-zero exits and classify errors (retryable vs fatal)
- NO hang detection (no timeouts, no "no output" checks)

### Critical Implementation Details

**NO HANG DETECTION:**
- Only react to: process exit, container exit, user stop, known error signals
- Do NOT implement: timeouts, heartbeat checks, "no output" detection
- Trust that containers will exit eventually or user will stop them

**Error Classification:**
```python
class ErrorType(Enum):
    RETRYABLE = "retryable"      # Network, rate limit, transient
    FATAL = "fatal"              # Invalid prompt, auth failure
    AGENT_FAILURE = "agent"      # Try fallback agent
    CONTAINER_CRASH = "crash"    # Restart container
```

**Retry Strategy:**
- Max 3 retries per agent
- Exponential backoff: 5s, 15s, 45s
- Different backoff for rate limits (from Task 3)
- Log all retry attempts clearly

### Deliverables

1. **New Modules**
   - `agents_runner/execution/supervisor.py` (NEW, 250-300 lines)
     - `TaskSupervisor` class - Orchestrates retry/fallback
     - `run_with_supervision()` - Main entry point
     - `classify_error()` - Determines error type from logs/exit code
   
   - `agents_runner/core/agent/selector.py` (NEW, 150-200 lines)
     - `AgentSelector` class - Implements selection logic
     - `select_next_agent()` - Round-robin or priority-based
     - `get_fallback_agent()` - Returns fallback from AgentSelection
   
   - `agents_runner/core/agent/retry.py` (NEW, 100-150 lines)
     - `RetryPolicy` dataclass - Defines retry behavior
     - `BackoffCalculator` - Exponential backoff logic
     - `should_retry()` - Decision function

2. **Modified Files**
   - `agents_runner/docker/agent_worker.py`
     - Extract run supervision to supervisor.py
     - Keep Docker execution logic only
     - Add container restart capability
   
   - `agents_runner/ui/main_window_tasks_agent.py`
     - Wire AgentSelector into task start flow
     - Use supervisor.run_with_supervision() instead of direct worker
   
   - `agents_runner/ui/bridges.py`
     - Add signals: retry_attempt, agent_switched, error_classified

3. **Tests** (if requested)
   - `tests/execution/test_supervisor.py`
   - `tests/core/agent/test_selector.py`
   - `tests/core/agent/test_retry.py`

### Sub-Tasks

1. **Coder:** Extract supervision logic from agent_worker.py to supervisor.py
   - Files: `agents_runner/execution/supervisor.py` (NEW)
   - Lines: ~250-300
   - Keep agent_worker.py focused on Docker execution only

2. **Coder:** Implement error classification system
   - Files: `agents_runner/execution/supervisor.py`
   - Parse exit codes, scan logs for known error patterns
   - Return ErrorType enum

3. **Coder:** Implement retry logic with exponential backoff
   - Files: `agents_runner/core/agent/retry.py` (NEW)
   - Backoff: 5s, 15s, 45s for normal retries
   - Max 3 retries per agent

4. **Coder:** Implement agent selection and fallback
   - Files: `agents_runner/core/agent/selector.py` (NEW)
   - Use existing Environment.agent_selection data
   - Respect agent_fallbacks dict

5. **Coder:** Add container restart capability
   - Files: `agents_runner/docker/agent_worker.py`
   - Detect container crashes (exit code, docker inspect)
   - Restart with same config

6. **Coder:** Wire supervisor into UI
   - Files: `agents_runner/ui/main_window_tasks_agent.py`
   - Replace direct worker calls with supervisor
   - Add UI feedback for retries/fallbacks

7. **QA:** Test retry scenarios
   - Manual tests: kill container, simulate rate limit, invalid prompt
   - Verify retry counts, backoff timing, fallback selection

8. **QA:** Test container restart
   - Simulate container crash (docker kill)
   - Verify restart with same mounts/env vars

9. **Auditor:** Code review for error handling completeness
   - Check all error paths covered
   - Verify no hang detection implemented
   - Confirm retry limits enforced

### Success Criteria
- Tasks can retry up to 3 times with exponential backoff
- Agent fallback works when primary agent fails
- Container crashes trigger automatic restart
- No hang detection or timeout mechanisms
- Clear UI feedback for all retry/fallback actions
- Existing functionality unchanged (backward compatible)

### Risk Mitigation
- **Risk:** Breaking existing task execution
  - **Mitigation:** Keep agent_worker.py stable, add supervisor as wrapper
- **Risk:** Retry loops causing infinite execution
  - **Mitigation:** Hard limit of 3 retries, track retry count in task state
- **Risk:** Container restart failing
  - **Mitigation:** Fallback to marking task failed after 1 restart attempt

---

## Task 3: Usage / Rate Limit Watch System

**Owner:** Coder  
**Complexity:** Medium  
**Estimated Time:** 5-7 days  
**Dependencies:** Task 1  
**Blocks:** Task 6

### Objectives
- Implement rate limit detection from agent logs
- Create cooldown tracking system per agent type
- Build cooldown modal UI with "Use Fallback" and "Bypass" buttons
- Show cooldown check when user clicks "Run Agent" or "Run Interactive"
- Cooldown is task-scoped (doesn't change default agent selection)

### Critical Implementation Details

**COOLDOWN TIMING (CRITICAL):**
- Check cooldown WHEN USER PRESSES "Run Agent" button
- NOT during environment selection
- NOT during page load
- Modal appears AFTER button click, BEFORE task starts

**MODAL BEHAVIOR:**
- Show agent name, cooldown time remaining
- Buttons:
  - "Use Fallback" - Select fallback agent for THIS TASK ONLY
  - "Bypass" - Continue with original agent (user override)
  - "Cancel" - Don't start task
- Fallback selection is temporary, doesn't change environment defaults

**RATE LIMIT DETECTION:**
- Scan agent logs for known patterns:
  - Codex: "rate limit exceeded", "429"
  - Claude: "rate_limit_error", "too_many_requests"
  - Copilot: "rate limit", "wait"
  - Gemini: "quota exceeded", "rate limit"
- Extract cooldown duration if available
- Default cooldown: 60 seconds

### Deliverables

1. **New Modules**
   - `agents_runner/core/agent/rate_limit.py` (NEW, 200-250 lines)
     - `RateLimitDetector` class - Scans logs for rate limit errors
     - `CooldownTracker` class - Tracks cooldown per agent
     - `get_rate_limit_patterns()` - Returns regex patterns per agent
     - `extract_cooldown_duration()` - Parses cooldown from error message
   
   - `agents_runner/ui/dialogs/cooldown_modal.py` (NEW, 150-200 lines)
     - `CooldownModal` QDialog subclass
     - Shows agent, time remaining, fallback options
     - Returns: CooldownAction enum (USE_FALLBACK, BYPASS, CANCEL)

2. **Modified Files**
   - `agents_runner/execution/supervisor.py`
     - Integrate RateLimitDetector into error classification
     - Record cooldown when rate limit detected
   
   - `agents_runner/ui/main_window_tasks_agent.py`
     - Add cooldown check before starting task (lines 150-160)
     - Show CooldownModal if cooldown active
     - Handle fallback selection (task-scoped only)
   
   - `agents_runner/ui/pages/new_task.py`
     - No changes to environment selector
     - Button click handlers check cooldown
   
   - `agents_runner/persistence.py`
     - Add cooldown_tracker to state (dict[str, float])
     - Format: {"codex": timestamp, "claude": timestamp}

3. **Tests** (if requested)
   - `tests/core/agent/test_rate_limit.py`
   - `tests/ui/dialogs/test_cooldown_modal.py`

### Sub-Tasks

1. **Coder:** Implement rate limit detection
   - Files: `agents_runner/core/agent/rate_limit.py` (NEW)
   - Regex patterns for each agent's rate limit errors
   - Extract cooldown duration from error messages

2. **Coder:** Implement cooldown tracking system
   - Files: `agents_runner/core/agent/rate_limit.py`
   - Store cooldown timestamps in state
   - `is_on_cooldown(agent: str) -> tuple[bool, float]`

3. **Coder:** Create cooldown modal dialog
   - Files: `agents_runner/ui/dialogs/cooldown_modal.py` (NEW)
   - PySide6 QDialog with custom styling
   - Sharp corners (no border-radius per design constraints)
   - Show time remaining with countdown

4. **Coder:** Wire cooldown check into Run Agent button
   - Files: `agents_runner/ui/main_window_tasks_agent.py`
   - Check cooldown AFTER button click, BEFORE task start
   - Show modal, handle user choice

5. **Coder:** Implement task-scoped fallback selection
   - Files: `agents_runner/ui/main_window_tasks_agent.py`
   - Override agent for single task
   - Don't modify environment defaults
   - Pass override to supervisor

6. **Coder:** Integrate with supervisor retry logic
   - Files: `agents_runner/execution/supervisor.py`
   - Different backoff for rate limits: 60s, 120s, 300s
   - Mark rate limit retries clearly in logs

7. **QA:** Test cooldown timing
   - Verify modal only appears on button click
   - Verify countdown accuracy
   - Verify fallback doesn't change defaults

8. **QA:** Test rate limit detection
   - Simulate rate limit responses for each agent
   - Verify cooldown recorded correctly
   - Verify cooldown expires properly

9. **Auditor:** Review regex patterns for accuracy
   - Test against real rate limit error messages
   - Ensure all agent types covered

### Success Criteria
- Rate limits detected automatically from logs
- Cooldown modal appears when user clicks Run Agent while on cooldown
- Fallback selection works for single task only
- Cooldown persists across app restarts
- Different backoff for rate limits vs normal retries
- Clear UX feedback for cooldown state

### Risk Mitigation
- **Risk:** False positive rate limit detection
  - **Mitigation:** Require high-confidence regex patterns, allow user bypass
- **Risk:** Cooldown not expiring correctly
  - **Mitigation:** Store timestamps, not durations; check on every run
- **Risk:** Fallback changing defaults unexpectedly
  - **Mitigation:** Clear separation between task-scoped and environment defaults

---

## Task 4: GitHub Context for ALL Agents

**Owner:** Coder  
**Complexity:** Medium  
**Estimated Time:** 4-6 days  
**Dependencies:** Task 1, Task 2  
**Blocks:** Task 6

### Objectives
- Provide GitHub PR metadata for ALL agents (not just Copilot)
- Support both git-locked (GitHub clone) and folder-locked (local folder) environments
- Make GitHub context toggleable per environment
- Remove "Copilot" restriction from PR metadata UI

### Critical Implementation Details

**ENVIRONMENT TYPES:**
- **Git-locked (GH_MANAGEMENT_GITHUB):** GitHub repo clone
  - Full GitHub integration: clone, branch, commit, PR
  - PR metadata file with repo context
- **Folder-locked (GH_MANAGEMENT_LOCAL):** Local folder
  - If folder is git repo: extract repo URL, branch, commit
  - If not git repo: no GitHub context
  - PR metadata optional

**PR METADATA FORMAT (Enhanced):**
```json
{
  "version": 2,
  "task_id": "abc123",
  "title": "",
  "body": "",
  "github": {
    "repo_url": "https://github.com/owner/repo",
    "base_branch": "main",
    "task_branch": "task/abc123",
    "commit_sha": "abc123def456"
  }
}
```

**TOGGLEABLE CONTEXT:**
- Environment setting: `gh_context_enabled` (checkbox)
- When enabled:
  - Create PR metadata file for git-locked envs (always)
  - Create PR metadata file for folder-locked envs (if git repo detected)
  - Append GitHub context prompt
- When disabled:
  - No PR metadata file
  - No GitHub context prompt

### Deliverables

1. **New Modules**
   - `agents_runner/gh/context.py` (NEW, 150-200 lines)
     - `detect_git_repo()` - Check if folder is git repo
     - `extract_repo_info()` - Get URL, branch, commit from local repo
     - `should_enable_github_context()` - Decision logic
     - `build_github_context_prompt()` - Agent-agnostic context prompt

2. **Modified Files**
   - `agents_runner/pr_metadata.py`
     - Update schema to version 2 (add github object)
     - Add `ensure_pr_metadata_file_v2()` with repo info
     - Keep backward compatibility with v1
   
   - `agents_runner/ui/pages/environments.py`
     - Rename checkbox: "PR metadata (Copilot)" → "GitHub context"
     - Enable for all environments with GitHub management
     - Add tooltip explaining feature
   
   - `agents_runner/ui/main_window_tasks_agent.py`
     - Remove Copilot-specific check (line 516-520)
     - Use `gh_context_enabled` instead of `gh_pr_metadata_enabled`
     - Call `gh/context.py` to build context
   
   - `agents_runner/environments/model.py`
     - Rename: `gh_pr_metadata_enabled` → `gh_context_enabled`
     - Add migration for existing environments

3. **Prompt Template Updates**
   - `agents_runner/prompts/github_context.md` (NEW)
     - Agent-agnostic GitHub context instructions
     - Replaces Copilot-specific pr_metadata.md
     - Works for all agents

4. **Tests** (if requested)
   - `tests/gh/test_context.py`

### Sub-Tasks

1. **Coder:** Implement git repo detection for folder-locked envs
   - Files: `agents_runner/gh/context.py` (NEW)
   - Detect git repo in local folder
   - Extract repo URL, branch, commit SHA

2. **Coder:** Update PR metadata schema to v2
   - Files: `agents_runner/pr_metadata.py`
   - Add github object with repo info
   - Maintain backward compatibility with v1

3. **Coder:** Remove Copilot restriction from UI
   - Files: `agents_runner/ui/pages/environments.py`
   - Rename checkbox, update label
   - Enable for all agent types

4. **Coder:** Implement GitHub context decision logic
   - Files: `agents_runner/gh/context.py`
   - should_enable_github_context() checks:
     - Environment has gh_context_enabled
     - Git-locked: always true
     - Folder-locked: only if git repo detected

5. **Coder:** Create agent-agnostic GitHub context prompt
   - Files: `agents_runner/prompts/github_context.md` (NEW)
   - Generic instructions for PR metadata
   - Works with all agents

6. **Coder:** Wire GitHub context into task start
   - Files: `agents_runner/ui/main_window_tasks_agent.py`
   - Use gh_context_enabled instead of gh_pr_metadata_enabled
   - Create metadata file for all agents

7. **Coder:** Add environment model migration
   - Files: `agents_runner/environments/model.py`
   - Rename field: gh_pr_metadata_enabled → gh_context_enabled
   - Auto-migrate existing environments

8. **QA:** Test with all agent types
   - Verify Codex, Claude, Copilot, Gemini can use GitHub context
   - Verify folder-locked git repos work
   - Verify folder-locked non-git folders skip GitHub context

9. **Auditor:** Review PR metadata v2 schema
   - Ensure backward compatibility
   - Verify all required fields present

### Success Criteria
- All agent types can use GitHub context (not just Copilot)
- Folder-locked git repos provide GitHub context
- Folder-locked non-git folders gracefully skip GitHub context
- PR metadata schema v2 with backward compatibility
- UI no longer references Copilot specifically
- Existing functionality unchanged

### Risk Mitigation
- **Risk:** Breaking existing PR creation
  - **Mitigation:** Maintain v1 schema support, test with existing environments
- **Risk:** Git detection false positives
  - **Mitigation:** Strict validation (check for .git directory, git command works)
- **Risk:** Performance impact of git operations
  - **Mitigation:** Cache repo info, only detect once per task

---

## Task 5: First-Run Setup + Per-Agent Management

**Owner:** Coder  
**Complexity:** High  
**Estimated Time:** 7-10 days  
**Dependencies:** Task 1  
**Blocks:** Task 6

### Objectives
- Create first-run setup popup (shown once on app launch)
- Sequential agent setup: one terminal at a time, wait for close
- Add 1-3 second delay between agent setups
- Implement per-agent management UI (NOT rerunnable wizard)
- Clean cancellation handling (stop setup if user cancels)

### Critical Implementation Details

**SEQUENTIAL SETUP (CRITICAL):**
1. First launch: check `~/.midoriai/agents-runner/setup_complete` flag
2. If missing, show setup dialog
3. User selects which agents to set up (checkboxes)
4. For each selected agent:
   - Open terminal with agent login command
   - Wait for terminal process to exit
   - Wait 1-3 seconds (configurable)
   - Continue to next agent
5. User can cancel at any time (kills current terminal, stops setup)
6. On completion: write setup_complete flag

**TERMINAL LAUNCH:**
- Use existing `terminal_apps.py` detection
- Commands:
  - Codex: `codex login` or `codex --version` (check if logged in)
  - Claude: `claude login`
  - Copilot: `gh auth login` then `gh copilot install`
  - Gemini: `gemini login`
- Wait for process exit (subprocess.wait())
- No timeout, trust user to complete or cancel

**PER-AGENT MANAGEMENT:**
- Settings page: add "Agents" section
- Table with columns: Agent | Status | Actions
- Status: Logged In / Not Logged In / Unknown
- Actions: [Configure] [Login] [Logout]
- [Configure] opens terminal with agent config command
- NOT a wizard, just individual actions

### Deliverables

1. **New Modules**
   - `agents_runner/setup/orchestrator.py` (NEW, 250-300 lines)
     - `SetupOrchestrator` class - Manages setup flow
     - `run_agent_setup(agent: str)` - Launch terminal, wait for exit
     - `check_setup_complete()` - Check if setup done
     - `mark_setup_complete()` - Write flag file
   
   - `agents_runner/setup/agent_status.py` (NEW, 150-200 lines)
     - `check_agent_status(agent: str)` - Returns logged in status
     - Runs agent commands: `codex --version`, `claude whoami`, etc.
     - Parses output to determine login state
   
   - `agents_runner/ui/dialogs/first_run_setup.py` (NEW, 200-250 lines)
     - `FirstRunSetupDialog` QDialog subclass
     - Checkbox list of agents
     - Progress display during setup
     - Cancel button
     - Handles sequential setup flow

2. **Modified Files**
   - `agents_runner/app.py`
     - Check for setup_complete on launch
     - Show FirstRunSetupDialog if needed
     - Don't show MainWindow until setup done (or skipped)
   
   - `agents_runner/ui/pages/settings.py`
     - Add "Agents" section with status table
     - [Configure] [Login] [Logout] buttons per agent
     - Use agent_status.py to check status
   
   - `agents_runner/terminal_apps.py`
     - Add `launch_terminal_and_wait(command: str)` helper
     - Launches terminal, returns when process exits

3. **Config Files**
   - `~/.midoriai/agents-runner/setup_complete` (flag file)
   - `~/.midoriai/agents-runner/setup_config.json` (optional, for delays)

4. **Tests** (if requested)
   - `tests/setup/test_orchestrator.py`
   - `tests/setup/test_agent_status.py`

### Sub-Tasks

1. **Coder:** Implement setup completion flag
   - Files: `agents_runner/setup/orchestrator.py` (NEW)
   - Check/write `~/.midoriai/agents-runner/setup_complete`
   - Simple file presence check

2. **Coder:** Implement agent status detection
   - Files: `agents_runner/setup/agent_status.py` (NEW)
   - Run agent CLI commands to check login status
   - Parse output, return status enum

3. **Coder:** Create first-run setup dialog
   - Files: `agents_runner/ui/dialogs/first_run_setup.py` (NEW)
   - PySide6 QDialog with agent checkboxes
   - Progress indicator
   - Cancel handling

4. **Coder:** Implement sequential setup orchestration
   - Files: `agents_runner/setup/orchestrator.py`
   - Loop through selected agents
   - Launch terminal, wait for exit
   - Add 1-3s delay between agents
   - Handle cancellation cleanly

5. **Coder:** Add terminal launch helper
   - Files: `agents_runner/terminal_apps.py`
   - launch_terminal_and_wait(command: str)
   - Use existing terminal detection
   - Return when process exits

6. **Coder:** Wire first-run setup into app launch
   - Files: `agents_runner/app.py`
   - Check setup flag on startup
   - Show dialog if needed
   - Block main window until done

7. **Coder:** Add per-agent management to Settings
   - Files: `agents_runner/ui/pages/settings.py`
   - New section: "Agent Management"
   - Table with status and action buttons
   - Wire to terminal launch for config/login

8. **QA:** Test first-run setup flow
   - Fresh install, verify setup dialog appears
   - Test sequential setup with multiple agents
   - Verify delays between setups
   - Test cancellation

9. **QA:** Test per-agent management
   - Verify status detection accuracy
   - Test [Configure] [Login] [Logout] buttons
   - Verify terminal launches correctly

10. **Auditor:** Review setup safety
    - Check cancellation handling (no orphaned processes)
    - Verify setup flag prevents re-run
    - Confirm no data loss on cancel

### Success Criteria
- First-run setup appears once on fresh install
- Agents set up sequentially, one at a time
- 1-3 second delay between setups
- User can cancel cleanly at any time
- Per-agent management in Settings works
- Setup never blocks app after initial completion
- Existing users don't see setup dialog (flag already exists)

### Risk Mitigation
- **Risk:** Setup dialog blocking normal usage
  - **Mitigation:** Write flag immediately after user clicks "Skip" or completes setup
- **Risk:** Terminal processes not exiting
  - **Mitigation:** Show cancel button, user can force quit
- **Risk:** Agent status detection unreliable
  - **Mitigation:** Graceful fallback to "Unknown" status, allow manual actions

---

## Task 6: Environments UI - Agent Chain Clarity

**Owner:** Coder  
**Complexity:** Low  
**Estimated Time:** 2-3 days  
**Dependencies:** Task 2, Task 3, Task 4, Task 5  
**Blocks:** None

### Objectives
- Improve clarity in Environments page Agents tab
- Show which agent will be selected first, second, third, etc.
- Display cooldown status next to each agent
- Show fallback chain clearly
- Add "Test Agent" button to verify agent works

### Deliverables

1. **Modified Files**
   - `agents_runner/ui/pages/environments_agents.py`
     - Add "Order" column to agent table
     - Add "Cooldown Status" column
     - Add "Test" button per agent row
     - Update on cooldown changes (live)
   
   - `agents_runner/ui/pages/environments.py`
     - Wire cooldown tracker into Agents tab
     - Refresh cooldown status periodically

2. **Visual Enhancements**
   - Order badges: "1st", "2nd", "3rd", etc.
   - Cooldown status: "Ready" / "On cooldown (42s)" / "Unknown"
   - Fallback arrows: "Agent A → Agent B → Agent C"

### Sub-Tasks

1. **Coder:** Add order column to agent table
   - Files: `agents_runner/ui/pages/environments_agents.py`
   - Show selection order based on priority
   - Visual indicator for first agent

2. **Coder:** Add cooldown status column
   - Files: `agents_runner/ui/pages/environments_agents.py`
   - Pull from cooldown tracker
   - Update every 5 seconds

3. **Coder:** Add test button per agent
   - Files: `agents_runner/ui/pages/environments_agents.py`
   - Runs simple agent command: `agent --version`
   - Shows result in modal

4. **Coder:** Visualize fallback chain
   - Files: `agents_runner/ui/pages/environments_agents.py`
   - Draw arrows between agents
   - Or show as text: "Fallback: AgentB"

5. **QA:** Test UI updates
   - Verify order displays correctly
   - Verify cooldown status updates
   - Test agent test button

### Success Criteria
- Clear visual indication of agent selection order
- Real-time cooldown status display
- Test button verifies agent functionality
- Fallback relationships clear

---

## Task 7: New Task Prompt Spell Checker

**Owner:** Coder  
**Complexity:** Medium  
**Estimated Time:** 4-5 days  
**Dependencies:** Task 1  
**Blocks:** None

### Objectives
- Add spell checking to New Task prompt editor
- Underline misspelled words
- Right-click context menu for suggestions
- No external dependencies (use Qt-based solution)

### Critical Implementation Details

**APPROACH:**
- Use `QSyntaxHighlighter` to underline misspelled words
- Integrate with Python `enchant` library (or `pyspellchecker`)
- No Qt WebEngine (keep existing QPlainTextEdit)
- Cache dictionary for performance
- User can add words to personal dictionary

**VISUAL STYLE:**
- Red wavy underline for misspelled words
- Tooltip shows suggestions on hover
- Right-click menu: "Ignore", "Add to dictionary", suggestions

### Deliverables

1. **New Modules**
   - `agents_runner/ui/spell_checker.py` (NEW, 200-250 lines)
     - `SpellChecker` class - Wrapper around enchant/pyspellchecker
     - `SpellCheckHighlighter` QSyntaxHighlighter subclass
     - `check_word(word: str)` - Returns is_correct, suggestions
     - Personal dictionary management
   
   - `agents_runner/ui/widgets/spell_checked_text_edit.py` (NEW, 150-200 lines)
     - Custom QPlainTextEdit subclass
     - Integrates SpellCheckHighlighter
     - Context menu for corrections

2. **Modified Files**
   - `agents_runner/ui/pages/new_task.py`
     - Replace QPlainTextEdit with SpellCheckedTextEdit (line 86)
     - Pass spell checker instance
   
   - `pyproject.toml`
     - Add dependency: `pyenchant` or `pyspellchecker`

3. **Config Files**
   - `~/.midoriai/agents-runner/personal_dictionary.txt`
     - User-added words

### Sub-Tasks

1. **Coder:** Research spell checker library
   - Evaluate pyenchant vs pyspellchecker
   - Choose based on: no external dependencies, performance, licensing

2. **Coder:** Implement spell checker wrapper
   - Files: `agents_runner/ui/spell_checker.py` (NEW)
   - Wrap chosen library
   - Cache dictionary for performance

3. **Coder:** Implement syntax highlighter
   - Files: `agents_runner/ui/spell_checker.py`
   - QSyntaxHighlighter subclass
   - Underline misspelled words in red

4. **Coder:** Create custom text edit widget
   - Files: `agents_runner/ui/widgets/spell_checked_text_edit.py` (NEW)
   - Extends QPlainTextEdit
   - Context menu with suggestions

5. **Coder:** Add personal dictionary management
   - Files: `agents_runner/ui/spell_checker.py`
   - Load/save personal dictionary
   - "Add to dictionary" functionality

6. **Coder:** Integrate into New Task page
   - Files: `agents_runner/ui/pages/new_task.py`
   - Replace existing QPlainTextEdit

7. **QA:** Test spell checking accuracy
   - Verify common misspellings caught
   - Verify suggestions relevant
   - Test personal dictionary

8. **QA:** Test performance
   - Large prompts (1000+ words)
   - Verify no UI lag

### Success Criteria
- Misspelled words underlined in red
- Right-click shows suggestions
- User can add words to personal dictionary
- No performance impact on prompt editing
- Works offline (no network calls)

### Risk Mitigation
- **Risk:** External dependency installation issues
  - **Mitigation:** Choose pure-Python library, document installation
- **Risk:** False positives for technical terms
  - **Mitigation:** Robust personal dictionary, easy to add words

---

## Task 8: Task View Tabs - Conditional Visibility

**Owner:** Coder  
**Complexity:** Low  
**Estimated Time:** 2-3 days  
**Dependencies:** Task 1, Task 2  
**Blocks:** None

### Objectives
- Show Desktop tab only when headless_desktop enabled
- Show Artifacts tab only when artifacts exist
- Hide tabs cleanly (don't show empty tabs)
- Update tab visibility as state changes

### Deliverables

1. **Modified Files**
   - `agents_runner/ui/pages/task_details.py`
     - Add `_update_tab_visibility()` method
     - Show/hide Desktop tab based on task.headless_desktop
     - Show/hide Artifacts tab based on artifact count
     - Call on task state changes

2. **Tests** (if requested)
   - `tests/ui/pages/test_task_details_tabs.py`

### Sub-Tasks

1. **Coder:** Implement tab visibility logic
   - Files: `agents_runner/ui/pages/task_details.py`
   - Check task.headless_desktop for Desktop tab
   - Check artifact count for Artifacts tab

2. **Coder:** Wire visibility updates to state changes
   - Files: `agents_runner/ui/pages/task_details.py`
   - Update when task status changes
   - Update when artifacts collected

3. **QA:** Test tab visibility
   - Verify Desktop tab hidden when not enabled
   - Verify Artifacts tab hidden when none collected
   - Verify tabs appear when applicable

### Success Criteria
- Desktop tab only visible when headless_desktop enabled
- Artifacts tab only visible when artifacts exist
- Tab visibility updates dynamically
- No empty or useless tabs shown

---

## Task 9: Live Artifacts During Runtime

**Owner:** Coder  
**Complexity:** High  
**Estimated Time:** 6-8 days  
**Dependencies:** Task 1, Task 2  
**Blocks:** None

### Objectives
- Allow browsing/editing artifacts while task is running
- NO encryption during runtime
- Encrypt only after task completes
- Watch staging directory for new files
- Live preview in Artifacts tab

### Critical Implementation Details

**ENCRYPTION BYPASS:**
- While task running: access staging directory directly
- After task completes: encrypt files, delete staging
- Artifacts tab checks task status:
  - Running: read from staging (unencrypted)
  - Completed: read from encrypted storage
- No mixed mode (either all staging or all encrypted)

**FILE WATCHING:**
- Use QFileSystemWatcher on staging directory
- Emit signal when files added/modified
- Update Artifacts tab UI automatically

**EDITING:**
- For text files: open in external editor
- Watch for changes, refresh preview
- Don't encrypt while editing

### Deliverables

1. **Modified Files**
   - `agents_runner/artifacts.py`
     - Add `list_staging_artifacts(task_id: str)`
     - Add `read_staging_artifact(task_id: str, filename: str)`
     - Keep encryption logic for completed tasks
   
   - `agents_runner/ui/pages/artifacts_tab.py`
     - Check task status to decide: staging vs encrypted
     - Add file watcher for staging directory
     - Add [Edit] button for text files
     - Refresh UI on file changes
   
   - `agents_runner/docker/agent_worker.py`
     - Don't encrypt staging until run() completes
     - Keep staging directory until encryption done

2. **New Modules**
   - `agents_runner/ui/file_watcher.py` (NEW, 100-150 lines)
     - Wrapper around QFileSystemWatcher
     - Emits signals for file add/modify/delete

### Sub-Tasks

1. **Coder:** Add staging directory access functions
   - Files: `agents_runner/artifacts.py`
   - list_staging_artifacts()
   - read_staging_artifact()

2. **Coder:** Implement file watcher
   - Files: `agents_runner/ui/file_watcher.py` (NEW)
   - QFileSystemWatcher wrapper
   - Emit signals on changes

3. **Coder:** Update Artifacts tab for live access
   - Files: `agents_runner/ui/pages/artifacts_tab.py`
   - Check task.status to decide source
   - Show staging files if running
   - Add file watcher

4. **Coder:** Add edit functionality
   - Files: `agents_runner/ui/pages/artifacts_tab.py`
   - [Edit] button for text files
   - Launch external editor (xdg-open, etc.)

5. **Coder:** Defer encryption until task completes
   - Files: `agents_runner/docker/agent_worker.py`
   - Keep staging directory during run
   - Encrypt in cleanup, after done signal

6. **QA:** Test live artifact viewing
   - Start task, generate artifacts
   - Verify files appear in real-time
   - Verify editing works

7. **QA:** Test encryption timing
   - Verify no encryption during runtime
   - Verify encryption after completion
   - Verify staging directory deleted after encryption

8. **Auditor:** Review security implications
   - Verify no sensitive data leakage
   - Confirm staging directory permissions
   - Check cleanup completeness

### Success Criteria
- Artifacts visible while task running
- No encryption during runtime
- File watcher updates UI automatically
- Edit functionality works for text files
- Encryption happens after task completes
- Staging directory cleaned up after encryption

### Risk Mitigation
- **Risk:** Staging directory not cleaned up
  - **Mitigation:** Ensure cleanup in finally block, track cleanup state
- **Risk:** File watcher performance issues
  - **Mitigation:** Debounce updates, limit refresh rate
- **Risk:** Concurrent access to staging files
  - **Mitigation:** Read-only access during runtime, exclusive lock for encryption

---

## Critical Path Analysis

**Longest Path:** Task 1 → Task 2 → Task 4 → Task 9 (22-28 days)

**Parallel Opportunities:**
- Task 3, Task 5, Task 7 can run parallel to Task 2
- Task 6 requires most tasks to complete (coordination task)
- Task 8 can run parallel to Task 9

**Recommended Execution Order:**

**Phase 1 (Weeks 1-2):**
- Task 1: Planning and architecture (CURRENT)
- Task 7: Spell checker (independent, can start immediately)

**Phase 2 (Weeks 2-3):**
- Task 2: Run supervisor (critical path, highest priority)
- Task 3: Rate limit system (supports Task 2)
- Task 5: Setup system (independent, can parallelize)

**Phase 3 (Weeks 3-4):**
- Task 4: GitHub context (depends on Task 2)
- Task 8: Tab visibility (depends on Task 2)

**Phase 4 (Weeks 4-5):**
- Task 9: Live artifacts (depends on Task 2, Task 4)

**Phase 5 (Week 5-6):**
- Task 6: Environment UI polish (depends on everything)
- Integration testing
- Documentation updates

---

## Risk Areas and Mitigation Strategies

### High-Risk Areas

#### 1. Run Supervisor Stability (Task 2)
**Risk:** Retry/fallback logic breaks existing task execution  
**Impact:** Critical - would block all agent runs  
**Mitigation:**
- Implement supervisor as wrapper, keep agent_worker.py stable
- Extensive testing with manual failures
- Rollback plan: disable supervisor, fall back to direct execution
- Phased rollout: opt-in flag for supervisor initially

#### 2. Container Restart Reliability (Task 2)
**Risk:** Container restart fails, leaving tasks in bad state  
**Impact:** High - would require manual intervention  
**Mitigation:**
- Limit to 1 restart attempt per task
- Clear task state tracking (restart_count)
- Fallback: mark task failed after restart failure
- Log all restart attempts for debugging

#### 3. Rate Limit Detection Accuracy (Task 3)
**Risk:** False positives cause unnecessary cooldowns  
**Impact:** Medium - user can bypass, but annoying  
**Mitigation:**
- Conservative regex patterns (high confidence)
- User bypass option in modal
- Telemetry to track false positive rate
- Tunable patterns per agent

#### 4. Setup Orchestration Reliability (Task 5)
**Risk:** Setup hangs or fails, blocks app usage  
**Impact:** High - first impressions matter  
**Mitigation:**
- User can skip setup entirely
- Cancel button always available
- Setup flag written immediately on completion or skip
- No timeout, trust user to complete or cancel

#### 5. Live Artifact Security (Task 9)
**Risk:** Unencrypted artifacts exposed  
**Impact:** Medium - security concern  
**Mitigation:**
- Staging directory with restricted permissions (0700)
- Clear documentation that artifacts are unencrypted during runtime
- Encryption happens in finally block (guaranteed)
- Audit logging for staging directory access

### Medium-Risk Areas

#### 6. Spell Checker Performance (Task 7)
**Risk:** Large prompts cause UI lag  
**Impact:** Medium - UX degradation  
**Mitigation:**
- Dictionary caching
- Async spell checking (background thread)
- Debounce checks (only on pause, not every keystroke)
- Performance testing with 1000+ word prompts

#### 7. Cooldown Modal Timing (Task 3)
**Risk:** Modal appears at wrong time or not at all  
**Impact:** Medium - user confusion  
**Mitigation:**
- Clear state machine for modal display
- Unit tests for timing logic
- User feedback: "checking cooldown..." message
- Always allow bypass

#### 8. GitHub Context Detection (Task 4)
**Risk:** Git detection fails or misidentifies repos  
**Impact:** Low - feature gracefully disabled  
**Mitigation:**
- Strict validation: check .git directory AND git command works
- Cache detection results
- Fallback: disable GitHub context if uncertain
- Clear error messages

### Low-Risk Areas

#### 9. Tab Visibility Logic (Task 8)
**Risk:** Tabs hidden incorrectly  
**Impact:** Low - easy to fix, low severity  
**Mitigation:**
- Simple boolean logic
- Unit tests for visibility conditions
- Quick to patch if issues arise

#### 10. Environment UI Polish (Task 6)
**Risk:** UI changes confuse users  
**Impact:** Low - visual only  
**Mitigation:**
- Preserve existing workflow
- Add tooltips for new elements
- User testing before release

### Rollback Strategies

**Per-Task Rollback:**
- Each task isolated in feature branch
- Keep existing code paths functional
- Use feature flags where appropriate

**Global Rollback:**
- Tag stable version before refactor
- Document rollback procedure
- Keep dependencies backward compatible

---

## Sub-Agent Assignment Summary

### Auditor Tasks (3-4 tasks)
- **Task 1:** Architecture planning, ADRs, UI wireframes
- **Task 2:** Code review for error handling completeness
- **Task 3:** Review regex patterns for rate limit detection
- **Task 4:** Review PR metadata v2 schema
- **Task 5:** Review setup safety and cancellation handling
- **Task 9:** Security review for live artifacts

**Focus:** Architecture, security, data integrity, error handling

### Coder Tasks (All implementation work)
- **Task 2-9:** All implementation sub-tasks
- Primary executor for all code changes
- Module creation, file modifications, integration

**Focus:** Implementation, integration, code quality

### QA Tasks (Per-task testing)
- **Task 2:** Test retry/fallback scenarios, container restart
- **Task 3:** Test cooldown timing, rate limit detection
- **Task 4:** Test GitHub context with all agents
- **Task 5:** Test first-run setup flow, per-agent management
- **Task 6:** Test environment UI updates
- **Task 7:** Test spell checker accuracy and performance
- **Task 8:** Test tab visibility logic
- **Task 9:** Test live artifact viewing, encryption timing

**Focus:** Functional testing, edge cases, UX validation

---

## Success Metrics

### Reliability Metrics
- **Retry Success Rate:** % of tasks that succeed after retry
- **Fallback Usage:** % of tasks using fallback agents
- **Container Restart Rate:** % of tasks requiring container restart
- **Rate Limit Hit Rate:** % of tasks hitting rate limits

### UX Metrics
- **Setup Completion Rate:** % of users completing first-run setup
- **Spell Checker Usage:** % of prompts with corrections made
- **Live Artifact Access:** % of running tasks with artifact views
- **Cooldown Bypass Rate:** % of cooldown prompts bypassed

### Code Quality Metrics
- **File Size Compliance:** 100% of files under 600 lines (hard limit)
- **Test Coverage:** >70% for new modules
- **Code Review Approval:** 100% of PRs reviewed by auditor
- **Documentation Completeness:** All new features documented

---

## Open Questions

1. **Spell Checker Library:** pyenchant vs pyspellchecker - which is better?
   - **Decision needed by:** End of Task 1
   - **Owner:** Coder (research task)

2. **Cooldown Default Duration:** What default cooldown for agents without explicit duration?
   - **Proposed:** 60 seconds
   - **Decision needed by:** Task 3 start
   - **Owner:** Auditor

3. **Setup Skip Behavior:** Should skipped setup show a reminder later?
   - **Proposed:** Show banner in Settings page
   - **Decision needed by:** Task 5 start
   - **Owner:** Auditor

4. **Live Artifacts Editor:** Use external editor or built-in?
   - **Proposed:** External editor (xdg-open)
   - **Decision needed by:** Task 9 start
   - **Owner:** Coder

5. **Agent Selection UI:** Keep existing Agents tab or redesign?
   - **Proposed:** Keep existing, enhance with Task 6
   - **Decision needed by:** Task 6 start
   - **Owner:** Auditor

---

## Appendix: Gemini Allowed Directories Research

**TODO:** Research correct Gemini CLI flags for allowed directories

**Current Knowledge:**
- Gemini uses `--include-directories` flag
- Format: `gemini --include-directories /path1 /path2`
- Multiple directories supported

**Research Tasks:**
1. Verify flag name in latest Gemini CLI
2. Check if paths must be absolute
3. Test with workspace, artifacts, GitHub metadata, custom mounts
4. Document in `agents_runner/agent_cli.py`

**Assignee:** Coder (during Task 2 implementation)  
**Deadline:** Before Task 2 completion

---

## Appendix: File Size Tracking

**Files Currently Exceeding Soft Limit (300 lines):**

| File | Current Lines | Target | Action |
|------|--------------|---------|---------|
| `docker/agent_worker.py` | 504 | <300 | Split in Task 2 |
| `ui/pages/task_details.py` | 503 | <300 | Consider split in Task 8 |
| `ui/main_window_settings.py` | 512 | <300 | Consider split in Task 5 |
| `ui/pages/environments_agents.py` | 529 | <300 | Acceptable for complex UI |
| `ui/main_window_tasks_interactive_docker.py` | 596 | <300 | Consider split in Task 2 |
| `persistence.py` | 448 | <300 | Defer to future work |

**New Files Created (Estimated Lines):**

| File | Est. Lines | Notes |
|------|-----------|-------|
| `execution/supervisor.py` | 250-300 | Task 2 |
| `core/agent/selector.py` | 150-200 | Task 2 |
| `core/agent/retry.py` | 100-150 | Task 2 |
| `core/agent/rate_limit.py` | 200-250 | Task 3 |
| `ui/dialogs/cooldown_modal.py` | 150-200 | Task 3 |
| `gh/context.py` | 150-200 | Task 4 |
| `setup/orchestrator.py` | 250-300 | Task 5 |
| `setup/agent_status.py` | 150-200 | Task 5 |
| `ui/dialogs/first_run_setup.py` | 200-250 | Task 5 |
| `ui/spell_checker.py` | 200-250 | Task 7 |
| `ui/widgets/spell_checked_text_edit.py` | 150-200 | Task 7 |
| `ui/file_watcher.py` | 100-150 | Task 9 |

**Total New Lines:** ~2,000-2,600  
**Compliance:** All new files within soft limit (300 lines)

---

**End of Task Breakdown**

**Next Steps:**
1. Review this document with stakeholders
2. Get approval on architectural decisions
3. Create ADRs for open questions
4. Begin Task 2 (Run Supervisor) implementation

**Document Status:** DRAFT - Awaiting Review  
**Last Updated:** 2025-01-07  
**Author:** Task Master (AI)
