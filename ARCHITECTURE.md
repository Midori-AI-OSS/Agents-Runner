# Agents Runner Architecture

This document describes the major architectural changes made during the unstable refactor to improve reliability, agent usability, and day-to-day workflow.

## Overview

The refactor introduced several new systems to make Agents Runner more robust and user-friendly:

1. **Run Supervisor** - Automatic retry and fallback for failed tasks
2. **Usage/Rate Limit Watch** - Cooldown system to prevent rate-limit cascades
3. **GitHub Context** - Cross-agent GitHub integration for all environment types
4. **First-Run Setup** - One-time setup wizard with per-agent management
5. **UI Improvements** - Spellcheck, conditional tabs, agent chain clarity
6. **Live Artifacts** - Real-time artifact viewing/editing during task execution

---

## 1. Run Supervisor

**Location:** `agents_runner/execution/supervisor.py`

### Purpose
Automatically retry failed tasks and fall back to alternative agents, improving reliability without user intervention.

### Key Components

- **TaskSupervisor class**: State machine that manages task lifecycle
- **Error classification**: Categorizes failures into 5 types (RETRYABLE, RATE_LIMIT, AGENT_FAILURE, FATAL, CONTAINER_CRASH)
- **Exponential backoff**: Smart delay calculation between retries (5s→15s→45s for standard, 60s→120s→300s for rate limits)
- **Agent chain management**: Builds ordered fallback chains from environment configuration

### How It Works

1. Task starts with primary agent
2. If task fails, supervisor classifies the error
3. For retryable errors, retry up to 3 times with clean container each time
4. After retries exhausted, switch to fallback agent (if configured)
5. Fallback agent tries with same retry logic
6. Continue through chain until success or exhaustion

### Integration Points

- **Bridge**: `agents_runner/ui/bridges.py` - New signals for retry/switch events
- **Task Events**: `agents_runner/ui/main_window_task_events.py` - Event handlers for UI updates
- **Task Model**: `agents_runner/ui/task_model.py` - Added retry_count and fallback_used fields
- **Worker**: `agents_runner/docker/agent_worker.py` - Restart container support

### Key Constraints

- **NO timeout-based failure detection** - Only reacts to process exit, container exit, user cancel
- **Task-scoped fallback** - Fallback selection doesn't change environment's default agent
- **Clean container per retry** - Always fresh, never reuse

---

## 2. Usage/Rate Limit Watch System

**Location:** `agents_runner/core/agent/`

### Purpose
Detect rate-limit events and enforce cooldowns to prevent cascading failures and wasted retries.

### Key Components

- **RateLimitDetector** (`rate_limit.py`): Pattern-based detection from logs, exit codes, exceptions
- **CooldownManager** (`cooldown_manager.py`): Per-agent cooldown tracking with persistence
- **CooldownModal** (`ui/dialogs/cooldown_modal.py`): User dialog with fallback/bypass options
- **AgentWatchState** (`watch_state.py`): Data model for agent status

### Cooldown Triggers

Cooldown is triggered (1 hour default) when ANY occur:
- Watcher confirms remaining_percent is 0 / quota exhausted
- CLI output/exit indicates rate-limit (429 / "rate limit" / "quota exceeded" patterns)
- Watcher call itself gets 429 or explicit quota/rate-limit error

### Cooldown UX

**Timing (CRITICAL):** Cooldown check happens when user presses "Run Agent" button (NOT earlier)

When user tries to start a task with an agent under cooldown:
- Modal shows: agent name, cooldown expiry time, remaining duration
- Three buttons:
  - **Use Fallback**: Run with next agent in chain (task-scoped only)
  - **Bypass**: Clear cooldown and proceed with selected agent
  - **Cancel**: Don't start task

### Integration Points

- **Supervisor**: `execution/supervisor.py` - Records cooldowns after rate-limit errors
- **Task Launch**: `ui/main_window_tasks_agent.py` - Checks cooldown before starting
- **Persistence**: `persistence.py` - Saves cooldown state to `~/.midoriai/agents-runner/watch_state.json`

### Future Enhancement: Proactive Watchers

The architecture supports (but doesn't yet implement) proactive usage monitoring:
- Poll agent APIs every 30 minutes
- Show quota percentages in UI
- Agent-specific watchers: Codex (documented), Claude/Copilot/Gemini (research needed)

---

## 3. GitHub Context System

**Location:** `agents_runner/environments/git_operations.py`, `agents_runner/docker/pr_metadata.py`

### Purpose
Provide GitHub context (repo, branch, PR number) to ALL agents, not just Copilot, for both git-locked and folder-locked environments.

### Key Components

- **Git operations** (`git_operations.py`): Detection and metadata extraction with 8-second timeout
- **GitHub context v2** (`pr_metadata.py`): Enhanced schema with repo_url, branch, commit_sha
- **Environment model**: Added `detect_git_if_folder_locked()` method with caching

### Environment Types

**Git-locked (`git`):**
- Repo is cloned fresh for each task
- Context file created empty, populated after clone
- Always has context when enabled

**Folder-locked (`folder`):**
- User's existing directory mounted read-write
- Git detection runs at task start (if context enabled)
- Context generated if `.git` directory found

### Context File Format (v2)

JSON mounted at `/tmp/codex-pr-metadata-{task_id}.json`:
```json
{
  "schema_version": 2,
  "repo_url": "https://github.com/owner/repo",
  "repo_owner": "owner",
  "repo_name": "repo",
  "branch": "main",
  "commit_sha": "abc123...",
  "pr_number": 42,
  "issue_number": null
}
```

### Integration Points

- **Environment editor**: `ui/pages/environments_general.py` - Toggle checkbox
- **Settings**: `ui/pages/settings.py` - Global default
- **Task creation**: `ui/main_window_tasks_agent.py` - Detects git and generates context
- **Agent CLI**: `agent_cli.py` - Gemini gets `/tmp` in allowed directories
- **Worker**: `docker/agent_worker.py` - Populates context after git clone

### Error Handling Philosophy

**NEVER fail a task** due to GitHub context errors:
- All git operations have 8-second timeout
- All failures logged with clear reasons
- Silent degradation (task continues without context)

---

## 4. First-Run Setup System

**Location:** `agents_runner/setup/`

### Purpose
One-time setup experience to detect and configure agent CLIs, with ongoing per-agent management (NOT a rerunnable wizard).

### Key Components

- **Agent detection** (`agent_status.py`): Check installation and login state for all agents
- **Setup commands** (`commands.py`): Interactive setup/login commands per agent
- **Setup orchestrator** (`orchestrator.py`): Sequential terminal execution with delays
- **First-run dialog** (`ui/dialogs/first_run_setup.py`): One-time setup wizard
- **Agent management**: Per-agent actions in Settings (install, login, verify)

### Sequential Setup Flow (CRITICAL)

When user chooses to run setup from first-run popup:
1. Open ONE agent's setup terminal
2. **Wait until that terminal/process closes** (blocking)
3. **Then wait 1-3 seconds before opening next**
4. Stop cleanly if user cancels mid-sequence

This is NON-NEGOTIABLE - prevents terminal/auth confusion.

### Agent Detection Status

| Agent | Install Check | Login Check |
|-------|--------------|-------------|
| Codex | `which codex` | `codex login status` (exit 0 = logged in) |
| Claude | `which claude` | Unknown (research needed) |
| Copilot | Depends on `gh` | `gh auth status` |
| Gemini | `which gemini` | Unknown (research needed) |
| GitHub | `which gh` | `gh auth status` |

### Persistence

State saved to `~/.midoriai/agents-runner/setup_state.json`:
- `first_run_complete`: bool
- `enabled_agents`: List[str]

### NO Rerunnable Wizard

Do NOT provide a "Run Setup Wizard" button. Instead:
- First-run shows once
- Per-agent management via Settings page with individual actions
- GH integration setup as separate item

---

## 5. UI Improvements

### Spellcheck (Task 7)

**Location:** `agents_runner/widgets/spell_highlighter.py`, `agents_runner/widgets/spell_text_edit.py`

- Real-time spell checking in New Task prompt editor
- Red wavy underlines for misspelled words
- Right-click suggestions (up to 5)
- Toggle in Settings (default: ON)
- Privacy-focused: 100% local dictionary (pyspellchecker), no network requests

**Integration:** `ui/pages/new_task.py` uses `SpellTextEdit` instead of `QPlainTextEdit`

### Conditional Tab Visibility (Task 8)

**Location:** `agents_runner/ui/pages/task_details.py`

- Hide (not disable) Desktop/Artifacts tabs when not usable
- Desktop tab: Only when `headless_desktop_enabled` is true
- Artifacts tab: Only when artifacts exist
- Dynamic show/hide based on task state

### Agent Chain Clarity (Task 6)

**Location:** `agents_runner/ui/widgets/agent_chain_status.py`, `agents_runner/ui/dialogs/test_chain_dialog.py`

- Visual agent chain display with status indicators
- Per-agent status: ✓ Installed, ✓ Logged in, ✓ Available, ⚠ Not logged in, ✕ Not installed, ❄ On cooldown
- "Test Chain" button to verify availability
- Agent chain shown in New Task page: "Using: codex → claude → copilot"
- Color-coded using Catppuccin palette

---

## 6. Live Artifacts System

**Location:** `agents_runner/docker/artifact_file_watcher.py`, `agents_runner/artifacts.py`

### Purpose
Real-time artifact viewing/editing during task execution, with post-run encryption preserved.

### Key Components

- **ArtifactFileWatcher** (`artifact_file_watcher.py`): QFileSystemWatcher with 500ms debouncing
- **Staging functions** (`artifacts.py`): Direct access to unencrypted staging directory
- **Dual-mode UI** (`ui/pages/artifacts_tab.py`): Switches between "staging" (live) and "encrypted" (archived)

### How It Works

**During Task Execution (STAGING mode):**
- File watcher monitors staging directory (`/tmp/agents-runner-{task_id}/artifacts`)
- UI updates within 1 second of file changes
- Files are NOT encrypted
- User can open/edit files directly
- Changes reflect immediately in UI

**After Task Completion (ENCRYPTED mode):**
- Staging directory is encrypted to archive
- UI switches to encrypted mode (current behavior)
- Staging directory cleaned up
- Archived artifacts remain viewable

### Finalization Flow

1. Task completes
2. `_finalize_artifacts()` called in worker
3. Staging directory encrypted to archive
4. Staging directory deleted
5. Artifacts tab automatically switches to encrypted mode

### Path Traversal Protection

All staging access functions validate paths to prevent escaping staging directory.

---

## Module Structure

### New Modules

```
agents_runner/
├── execution/
│   ├── __init__.py
│   └── supervisor.py                   # Run supervisor (513 lines)
├── core/
│   └── agent/
│       ├── watch_state.py              # Watch state data models (104 lines)
│       ├── rate_limit.py               # Rate-limit detection (120 lines)
│       └── cooldown_manager.py         # Cooldown tracking (99 lines)
├── setup/
│   ├── agent_status.py                 # Agent detection (349 lines)
│   ├── commands.py                     # Setup commands (90 lines)
│   └── orchestrator.py                 # Sequential setup (307 lines)
├── environments/
│   └── git_operations.py               # Git detection/metadata (116 lines)
├── docker/
│   └── artifact_file_watcher.py        # Live artifact watcher (121 lines)
├── ui/
│   ├── dialogs/
│   │   ├── cooldown_modal.py           # Cooldown dialog (204 lines)
│   │   ├── first_run_setup.py          # First-run wizard (339 lines)
│   │   └── test_chain_dialog.py        # Chain test dialog (136 lines)
│   └── widgets/
│       ├── spell_highlighter.py        # Spellcheck highlighter (124 lines)
│       ├── spell_text_edit.py          # Spellcheck editor (126 lines)
│       └── agent_chain_status.py       # Chain status widget (252 lines)
└── prompts/
    └── github_context.md               # GH context instructions
```

### Modified Modules (Major)

- `agents_runner/ui/bridges.py` - Supervisor integration signals
- `agents_runner/ui/main_window_tasks_agent.py` - Cooldown checks, GH context, agent chain
- `agents_runner/docker/agent_worker.py` - Retry/restart support, artifact finalization
- `agents_runner/docker/pr_metadata.py` - GitHub context v2 schema
- `agents_runner/artifacts.py` - Staging artifact access functions
- `agents_runner/ui/pages/task_details.py` - Conditional tabs, watcher integration
- `agents_runner/ui/pages/environments_agents.py` - Agent chain status display
- `agents_runner/ui/pages/environments_general.py` - GH context toggle
- `agents_runner/ui/pages/settings.py` - Spellcheck and GH context defaults
- `agents_runner/persistence.py` - Watch state and cooldown persistence

---

## Design Principles

### Non-Negotiable Constraints

1. **No hang detection** - Only react to explicit signals (exit, crash, cancel)
2. **Task-scoped fallback** - Never change environment's default agent
3. **Privacy-first** - Spellcheck is local, never send prompts over network
4. **Never fail tasks** - All new systems degrade gracefully
5. **Clean architecture** - Minimal diffs, clear module boundaries
6. **File size limits** - 300-line soft limit, 600-line hard limit

### Backward Compatibility

- Existing environments/tasks continue to work
- New features are opt-in or non-breaking
- Field migrations handle old data formats
- UI gracefully handles missing features

### Error Handling Philosophy

- **Fail open, not closed** - Errors shouldn't block execution
- **Log everything clearly** - Users can debug issues
- **No secret leakage** - Never log tokens or auth details
- **Graceful degradation** - Missing features don't break app

---

## Testing Strategy

### Unit Tests Created

- `test_supervisor.py` - Error classification, backoff, agent chains (19 tests)
- `test_cooldown_system.py` - Rate-limit detection, cooldown manager (4 tests)
- `test_first_run_setup.py` - Agent detection, orchestrator (tests)

### Manual Testing Required

1. **Run supervisor**: Task fails → retries → fallback
2. **Cooldown**: Rate-limit error → cooldown triggered → modal appears → bypass/fallback works
3. **GitHub context**: Git-locked and folder-locked environments both get context
4. **First-run setup**: Sequential terminals open with delays, clean cancellation
5. **Spellcheck**: Red underlines, suggestions, add to dictionary
6. **Conditional tabs**: Tabs hidden when not available
7. **Agent chain**: Status display accurate, test chain works
8. **Live artifacts**: Files appear in real-time, editing works, encryption post-run

---

## Performance Considerations

- **File watcher debouncing**: 500ms to avoid UI spam
- **Git operations timeout**: 8 seconds max to prevent hangs
- **Cooldown check timing**: Only when user clicks "Run Agent" button
- **Exponential backoff**: Prevents rapid retry storms
- **Background status checks**: Non-blocking UI threads

---

## Security Considerations

- **No secret logging**: Tokens never appear in logs or UI
- **Path traversal protection**: Staging artifact access validates paths
- **Cooldown bypass**: User control to override false positives
- **Sequential setup**: Prevents auth token confusion between agents
- **Explicit auth mounting**: GH auth mounting is separate opt-in toggle

---

## Future Enhancements

### Proactive Usage Watchers (Phase 3 of Task 3)

- Poll agent APIs every 30 minutes
- Show quota percentages in UI (e.g., "5h: 78% left • weekly: 92% left")
- Agent-specific implementations:
  - **Codex**: GET /wham/usage endpoint (documented, ready to implement)
  - **Claude**: Research needed for API
  - **Copilot**: Research GitHub API rate limits
  - **Gemini**: Research GCP quota APIs

### User Controls for Supervisor

- Cancel retry button
- Force fallback button (skip remaining retries)
- Telemetry: success rates per agent
- Custom retry counts per environment

### Agent Management UI

- Settings page with per-agent actions:
  - Install/Setup <Agent>
  - Login/Relogin <Agent>
  - Verify <Agent>
  - Show status: installed, logged in, watcher support, cooldown

Currently partially implemented (detection exists, UI TBD).

---

## Migration Notes

### For Users

- Existing environments will continue to work
- New features are opt-in (GH context, spellcheck)
- First-run setup appears once (can be skipped)
- Agent chains can be configured in environment editor

### For Developers

- Follow existing code style (Python 3.13+, type hints)
- Keep files under 300 lines (soft limit) / 600 lines (hard)
- Add docstrings to all public methods
- Use structured commit messages: `[TYPE] Description`
- Test with all 4 agents (codex, claude, copilot, gemini)

---

## Commit Summary

Total: 37 commits over 9 major tasks

**Task 2 (Run Supervisor):**
- `747081d` Phase 1: Foundation - error classification and backoff
- `217fea7` Phase 2-5: Agent chain, supervision, retry, and fallback
- `8dd88ca` Phase 7: Documentation, tests, and polish

**Task 3 (Rate Limit Watch):**
- `f3aa4cf` Phase 1: Add rate-limit detection and cooldown manager
- `b1b5c58` Phase 2: Add cooldown modal UI and task launch integration
- `3115368` Phase 3: Add cooldown system tests

**Task 4 (GitHub Context):**
- `cda7b9e` Phase 1: Add git operations and detection
- `f891a42` Phase 2: Add GitHub context v2 schema
- `7d27e01` Phase 3: Add UI toggles for GitHub context
- `b8468ea` Phase 4-5: Integrate GitHub context into task execution
- `4a6e43e` Phase 7: Polish and documentation

**Task 5 (First-Run Setup):**
- `a506245` Phase 1-2: Add agent detection and setup commands
- `666147d` Phase 3-4: Implementation docs and tests

**Task 6 (Agent Chain UI):**
- `8bbe359` Improve agent chain clarity in environments editor

**Task 7 (Spellcheck):**
- `83bb78f` Add spellcheck to prompt editor

**Task 8 (Conditional Tabs):**
- `47bc33a` Hide Desktop/Artifacts tabs when not available

**Task 9 (Live Artifacts):**
- `142911a` Phase 1: Add artifact file watcher and staging functions
- `f331974` Phase 2-3: Add dual-mode artifacts UI with live viewing
- `3552f28` Phase 4: Add post-run artifact finalization

**Cleanup:**
- `fc43868` Remove audit files and temporary documentation

---

## Acknowledgments

This refactor was designed to be an "unstable refactor" - prioritizing a cleaner architecture and better UX over strict backward compatibility. Breaking changes are acceptable and expected.

The implementation follows the Agents Runner Contributor Guide (AGENTS.md) and adheres to the project's design constraints:
- Sharp corners (no rounded borders)
- Python 3.13+ with type hints
- Minimal diffs (surgical changes)
- Clear module boundaries
- Comprehensive documentation

All new systems are designed to fail gracefully and never block core functionality.
