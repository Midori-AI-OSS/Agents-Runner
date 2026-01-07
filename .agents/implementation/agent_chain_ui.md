# Agent Chain Status UI

## Overview
Enhanced the Environments UI to make agent fallback chains visually obvious and testable.

## Components

### 1. Agent Chain Status Widget (`agents_runner/widgets/agent_chain_status.py`)

**AgentStatusIndicator:**
- Displays a single agent with status icons
- Shows position in chain (1., 2., 3., etc.)
- Status indicators:
  - ✓ Installed (green)
  - ✕ Not installed (red)
  - ✓ Logged in (green)
  - ⚠ Not logged in (yellow)
  - ❄ On cooldown (blue)
  - ✓ Available (green)
  - ? Unknown (gray)

**AgentChainStatusWidget:**
- Displays full agent chain with status for each agent
- Shows "Agent Chain (Primary → Fallbacks):" header
- "Test Chain" button to verify availability
- Updates dynamically when agents are added/removed/reordered

### 2. Test Chain Dialog (`agents_runner/ui/dialogs/test_chain_dialog.py`)

**TestChainDialog:**
- Modal dialog for testing agent chain availability
- Background thread checks agent installation and login status
- Does NOT expose authentication secrets
- Shows availability summary with color coding:
  - Green: Agents available
  - Yellow: No agents available
- Uses `detect_all_agents()` from `agent_status.py`
- Integrates with cooldown manager if available

### 3. Environment Agents Page Integration (`agents_runner/ui/pages/environments_agents.py`)

**Added:**
- Agent chain status display below agent table
- Updates chain display whenever agents change:
  - Adding/removing agents
  - Reordering agents (Up/Down)
  - Changing selection mode
  - Modifying fallback mappings
- "Test Chain" button opens test dialog
- Chain display logic:
  - **Fallback mode**: Shows primary agent → fallback chain
  - **Round-robin/Least-used**: Shows all agents in priority order

**Methods:**
- `_update_chain_status()`: Builds and updates chain display
- `_on_test_chain()`: Opens test dialog with current agent list

### 4. New Task Page Integration (`agents_runner/ui/pages/new_task.py`)

**Added:**
- "Agent chain" field in configuration section
- Shows agents that will be used for new tasks: "Codex → Claude → Copilot"
- Tooltip shows detailed chain with position labels
- Updates when environment changes

**Methods:**
- `set_agent_chain(agents)`: Updates chain display for selected environment

### 5. Main Window Integration (`agents_runner/ui/main_window_environment.py`)

**Added:**
- `_update_new_task_agent_chain(env)`: Builds agent chain from environment config
- Handles different selection modes:
  - **Fallback mode**: Builds chain following fallback mappings
  - **Round-robin/Least-used**: Lists all agents in priority order
  - **No custom config**: Shows default agent from settings
- Called from `_apply_active_environment_to_new_task()`

## User Workflow

### Environment Configuration
1. User opens Environments page
2. Clicks on environment to edit
3. Goes to Agents tab
4. Sees agent chain status display below table:
   ```
   Agent Chain (Primary → Fallbacks):
   1. Codex        [✓ Installed] [✓ Logged in] [✓ Available]
   2. Claude       [✓ Installed] [⚠ Not logged in]
   3. Copilot      [⚠ Not installed]
   
   [Test Chain]
   ```
5. Clicks "Test Chain" to verify availability
6. Dialog shows status check results with color-coded summary

### New Task Creation
1. User opens New Task page
2. Selects environment
3. Sees agent chain in configuration section:
   ```
   Agent chain: Codex → Claude → Copilot
   ```
4. Hover for tooltip showing detailed chain
5. User knows which agents will be tried in order

## Status Detection

Uses existing `agents_runner/setup/agent_status.py`:
- `detect_all_agents()`: Check all supported agents
- `AgentStatus`: Contains installed, logged_in flags
- `StatusType`: LOGGED_IN, NOT_LOGGED_IN, NOT_INSTALLED, UNKNOWN

Cooldown status from `agents_runner/core/agent/cooldown_manager.py`:
- `is_on_cooldown(agent_name)`: Check if agent is rate-limited
- Does NOT expose rate limit duration or reason in UI (privacy)

## Security Considerations

1. **No Secret Leakage:**
   - Test chain only checks installation and login status
   - Does NOT display API keys, tokens, or credentials
   - Does NOT show specific error messages that might contain secrets

2. **Background Checks:**
   - Status checks run in background thread (AgentStatusCheckThread)
   - UI remains responsive during checks
   - Timeout protection prevents hanging

3. **Cooldown Privacy:**
   - Shows cooldown status (❄ icon)
   - Does NOT show remaining time or rate limit details
   - Does NOT show error messages that triggered cooldown

## Design Constraints

Following project guidelines from AGENTS.md:
- Sharp corners (no border-radius)
- Catppuccin color palette for status indicators
- Minimal line count (all files under 300 lines)
- Type hints throughout
- No emoticons in code or docs

## Future Enhancements

Potential improvements (not implemented):
1. Real-time cooldown countdown in UI
2. Watcher support indicators (full vs best-effort)
3. Quota remaining display for agents with API quotas
4. Test individual agents (not just full chain)
5. Agent health history/statistics
6. Auto-refresh status on timer
