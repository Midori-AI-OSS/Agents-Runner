# First-Run Setup Experience and Per-Agent Management Design

**Document ID:** 06-first-run-setup-design  
**Task:** Task 5 - First-Run Setup + Per-Agent Management  
**Auditor:** AI Assistant (Auditor Mode)  
**Created:** 2025-01-07  
**Status:** DESIGN AUDIT

---

## Executive Summary

This document provides a comprehensive design for the first-run setup experience and per-agent management system. The design emphasizes **sequential setup** (CRITICAL requirement), clean cancellation, and non-intrusive per-agent management without a rerunnable wizard.

**Key Design Principles:**
1. **Sequential Setup:** One agent terminal at a time, wait for process exit, then 1-3s delay
2. **No Wizard Re-run:** Per-agent management via individual action buttons, not a full wizard
3. **Clean Cancellation:** User can cancel at any point without leaving orphaned processes
4. **Non-Blocking:** First-run setup can be skipped entirely
5. **Persistence:** Setup state tracked in `~/.midoriai/agents-runner/setup_state.json`

---

## 1. Detection Mechanisms

### 1.1 CLI Installation Detection

**Strategy:** Check if CLI is present in PATH using `shutil.which()`

**Implementation:**
```python
def check_agent_installed(agent: str) -> bool:
    """Check if agent CLI is installed (present in PATH)."""
    agent = normalize_agent(agent)
    return shutil.which(agent) is not None
```

**Detection Results:**
- `True`: CLI is in PATH
- `False`: CLI not found in PATH

**Note:** This does NOT verify the CLI works or is properly configured, only that it exists.

---

### 1.2 Login State Detection

Each agent has different login detection mechanisms:

#### 1.2.1 Codex Login Detection

**Method:** Run `codex login status`

**Expected Output:**
- Logged in: Exit code 0, outputs user info
- Not logged in: Exit code 1, outputs "Not logged in"

**Implementation:**
```python
def check_codex_login() -> tuple[bool, str]:
    """Check codex login status.
    
    Returns:
        (logged_in: bool, status_message: str)
    """
    try:
        result = subprocess.run(
            ["codex", "login", "status"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            return (True, "Logged in")
        return (False, "Not logged in")
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return (False, "Unknown (command failed)")
```

**Configuration Location:** `~/.codex/` (may contain auth.json or similar)

**Login Command:** `codex login` (interactive terminal)

---

#### 1.2.2 Claude Login Detection

**RESEARCH NEEDED:** Claude Code does not have a simple auth status command.

**Current Knowledge:**
- CLI launches interactive setup on first run
- Config stored in `~/.claude/`
- Has `claude setup-token` command for authentication
- No obvious `whoami` or `status` command

**Proposed Detection Strategy:**
```python
def check_claude_login() -> tuple[bool, str]:
    """Check claude login status.
    
    Returns:
        (logged_in: bool, status_message: str)
    """
    # APPROACH 1: Check for config files
    config_dir = Path.home() / ".claude"
    if not config_dir.exists():
        return (False, "Not logged in (no config)")
    
    # APPROACH 2: Try running a simple command and check output
    # If not logged in, Claude shows interactive setup
    # This is RISKY - may trigger interactive prompt
    
    # APPROACH 3: Parse config files (brittle, depends on Claude internals)
    # Look for authentication token or session data
    
    # RECOMMENDATION: For now, check if ~/.claude/ exists and is non-empty
    # Mark as "Unknown" if we can't verify
    if config_dir.exists() and any(config_dir.iterdir()):
        return (True, "Possibly logged in (config exists)")
    return (False, "Not logged in")
```

**RESEARCH ACTION REQUIRED:**
1. Test `claude --version` behavior when not logged in
2. Test `claude setup-token --help` to see if there's a status flag
3. Document expected config file structure in `~/.claude/`
4. Determine if running `claude` without auth triggers interactive prompt (blocking)

**Login Command:** `claude setup-token` (opens browser for auth)

---

#### 1.2.3 GitHub Copilot Login Detection

**Method:** Use `gh auth status` (Copilot uses GitHub CLI for auth)

**Expected Output:**
```
github.com
  ✓ Logged in to github.com account USERNAME (GH_TOKEN)
  - Active account: true
  ...
```

**Implementation:**
```python
def check_copilot_login() -> tuple[bool, str]:
    """Check copilot login status via gh CLI.
    
    Returns:
        (logged_in: bool, status_message: str)
    """
    try:
        result = subprocess.run(
            ["gh", "auth", "status"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0 and "Logged in" in result.stdout:
            # Extract username if possible
            for line in result.stdout.split('\n'):
                if "Logged in to github.com account" in line:
                    # Parse: "Logged in to github.com account USERNAME (GH_TOKEN)"
                    parts = line.split("account")
                    if len(parts) > 1:
                        username = parts[1].split("(")[0].strip()
                        return (True, f"Logged in as {username}")
            return (True, "Logged in")
        return (False, "Not logged in to GitHub")
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return (False, "Unknown (gh CLI not found)")
```

**Configuration Location:** `~/.copilot/` (Copilot session state) + GitHub token from gh CLI

**Login Command:** `gh auth login` (interactive terminal) + `gh copilot install` (if needed)

**Note:** Copilot requires BOTH GitHub auth AND Copilot subscription. The gh CLI handles auth, but we can't easily detect if user has Copilot subscription without trying to use it.

---

#### 1.2.4 Gemini Login Detection

**Method:** Check for auth config in `~/.gemini/settings.json` or environment variables

**Expected Auth Methods:**
- `GEMINI_API_KEY` environment variable
- `GOOGLE_GENAI_USE_VERTEXAI` environment variable
- `GOOGLE_GENAI_USE_GCA` environment variable
- `~/.gemini/settings.json` with auth configuration

**Implementation:**
```python
def check_gemini_login() -> tuple[bool, str]:
    """Check gemini login status.
    
    Returns:
        (logged_in: bool, status_message: str)
    """
    # Check environment variables
    if os.environ.get("GEMINI_API_KEY"):
        return (True, "Logged in (GEMINI_API_KEY)")
    if os.environ.get("GOOGLE_GENAI_USE_VERTEXAI"):
        return (True, "Logged in (VERTEXAI)")
    if os.environ.get("GOOGLE_GENAI_USE_GCA"):
        return (True, "Logged in (GCA)")
    
    # Check settings.json
    settings_path = Path.home() / ".gemini" / "settings.json"
    if settings_path.exists():
        try:
            with open(settings_path, "r") as f:
                settings = json.load(f)
                # Look for any auth-related keys
                auth_keys = ["apiKey", "api_key", "vertexai", "gca", "auth"]
                if any(key in settings for key in auth_keys):
                    return (True, "Logged in (settings.json)")
        except (json.JSONDecodeError, OSError):
            pass
    
    return (False, "Not logged in (no auth method found)")
```

**RESEARCH NEEDED:**
1. What is the exact structure of `~/.gemini/settings.json`?
2. Is there a `gemini auth status` or `gemini whoami` command?
3. How does Gemini CLI guide users through first-time auth?
4. Can we trigger auth programmatically or must it be interactive?

**Login Command:** **RESEARCH NEEDED** - likely one of:
- `gemini auth login`
- Manual editing of `~/.gemini/settings.json`
- Setting `GEMINI_API_KEY` environment variable

---

### 1.3 GitHub CLI Detection

**Method:** Check `gh auth status`

**Already Implemented Above:** See section 1.2.3

**Importance:** GitHub integration is cross-agent (used by all agents for PR metadata), so we need to detect gh CLI separately from Copilot.

---

### 1.4 Summary Table

| Agent | Install Check | Login Check | Login Command | Config Location | Research Status |
|-------|--------------|-------------|---------------|-----------------|-----------------|
| Codex | `which codex` | `codex login status` | `codex login` | `~/.codex/` | ✅ Complete |
| Claude | `which claude` | Config file check | `claude setup-token` | `~/.claude/` | ⚠️ Needs research |
| Copilot | `which copilot` | `gh auth status` | `gh auth login` | `~/.copilot/` + gh | ✅ Complete |
| Gemini | `which gemini` | Settings/env check | **UNKNOWN** | `~/.gemini/` | ⚠️ Needs research |
| GitHub | `which gh` | `gh auth status` | `gh auth login` | gh CLI config | ✅ Complete |

---

## 2. First-Run Setup Popup Design

### 2.1 When to Show

**Trigger:** App launch, BEFORE showing main window

**Condition:** `~/.midoriai/agents-runner/setup_state.json` does not exist OR `"first_run_complete": false`

**Flow:**
```
App Launch
    ↓
Check setup_state.json
    ↓
    ├─ File exists + first_run_complete=true → Skip setup, show main window
    ├─ File missing OR first_run_complete=false → Show first-run dialog
    └─ User clicks "Skip" → Write first_run_complete=true, show main window
```

---

### 2.2 UI Mockup

```
┌───────────────────────────────────────────────────────────┐
│  Agents Runner - First-Time Setup                         │
├───────────────────────────────────────────────────────────┤
│                                                            │
│  Welcome to Agents Runner!                                │
│                                                            │
│  We detected the following AI agent CLIs on your system:  │
│                                                            │
│  ┌────────────────────────────────────────────────────┐  │
│  │ Agent          Status                    Setup      │  │
│  ├────────────────────────────────────────────────────┤  │
│  │ ☑ Codex        ✓ Installed  ✗ Not logged in       │  │
│  │ ☑ Claude       ✓ Installed  ? Unknown             │  │
│  │ ☑ Copilot      ✓ Installed  ✓ Logged in           │  │
│  │ ☐ Gemini       ✗ Not installed                     │  │
│  │ ☑ GitHub CLI   ✓ Installed  ✓ Logged in           │  │
│  └────────────────────────────────────────────────────┘  │
│                                                            │
│  Select which agents you'd like to set up now:            │
│  (You can configure individual agents later in Settings)  │
│                                                            │
│  ┌────────────────────────────────────────────────────┐  │
│  │ ☑ Run Codex login                                  │  │
│  │ ☑ Run Claude setup                                 │  │
│  │ ☐ Run Copilot login (already logged in)           │  │
│  │ ☐ Run Gemini setup (not installed)                │  │
│  │ ☐ Run GitHub login (already logged in)            │  │
│  └────────────────────────────────────────────────────┘  │
│                                                            │
│  Setup will open one terminal at a time. Complete each    │
│  agent's setup before moving to the next.                 │
│                                                            │
│  [Skip Setup]          [Begin Setup]                      │
└───────────────────────────────────────────────────────────┘
```

---

### 2.3 Dialog Behavior

**Initial Display:**
1. Detect all agent CLIs (installed/not installed)
2. Detect login status for each installed agent
3. Pre-check only agents that are: installed + not logged in
4. Gray out/disable agents that are: not installed OR already logged in
5. Show GitHub CLI separately (it's not an agent, but needed for GH integration)

**User Actions:**
- **Select/Deselect Agents:** Check/uncheck which agents to set up
- **Skip Setup:** Close dialog, write `first_run_complete=true`, continue to main window
- **Begin Setup:** Start sequential setup flow (see section 3)

**After Setup Completes:**
- Write `first_run_complete=true`
- Write which agents were set up: `{"codex": true, "claude": true, ...}`
- Close dialog
- Show main window

---

## 3. Sequential Setup Flow (CRITICAL REQUIREMENT)

### 3.1 Timing Requirements

**CRITICAL:** This is a KEY requirement from the task breakdown:

> If user chooses to run setup/login from first-run popup:
> - Open ONE agent's setup/login in a terminal session
> - **Wait until that terminal/process closes**
> - **Then wait 1-3 seconds before opening the next**
> - Stop cleanly if user cancels mid-sequence

**Why This Matters:**
- Prevents overwhelming the user with multiple terminals
- Allows user to focus on one setup at a time
- Prevents race conditions with auth state
- Provides clear feedback on progress

---

### 3.2 Sequential Flow Diagram

```
User clicks "Begin Setup"
        ↓
Get list of selected agents: [codex, claude]
        ↓
┌──────────────────────────────┐
│  Progress Dialog             │
│  Setting up 1 of 2: Codex    │
│  [Cancel]                    │
└──────────────────────────────┘
        ↓
Launch terminal: `codex login`
        ↓
Wait for terminal process to exit
        ↓
Terminal closes (user completed login)
        ↓
Update progress: "Setup 1 of 2 complete"
        ↓
Wait 1-3 seconds (configurable delay)
        ↓
┌──────────────────────────────┐
│  Progress Dialog             │
│  Setting up 2 of 2: Claude   │
│  [Cancel]                    │
└──────────────────────────────┘
        ↓
Launch terminal: `claude setup-token`
        ↓
Wait for terminal process to exit
        ↓
Terminal closes (user completed setup)
        ↓
Update progress: "Setup 2 of 2 complete"
        ↓
Wait 1 second
        ↓
All agents set up!
        ↓
Write first_run_complete=true
        ↓
Close dialog, show main window
```

---

### 3.3 Progress Dialog UI

```
┌───────────────────────────────────────────┐
│  Agent Setup Progress                     │
├───────────────────────────────────────────┤
│                                            │
│  Setting up agent 1 of 2                  │
│                                            │
│  Current: Codex                           │
│  Status: Waiting for terminal to close... │
│                                            │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│  50%                                      │
│                                            │
│  Completed: None                          │
│  Remaining: Claude                        │
│                                            │
│  [Cancel Setup]                           │
└───────────────────────────────────────────┘
```

**After First Agent Completes:**

```
┌───────────────────────────────────────────┐
│  Agent Setup Progress                     │
├───────────────────────────────────────────┤
│                                            │
│  Setting up agent 2 of 2                  │
│                                            │
│  Current: Claude                          │
│  Status: Starting in 2 seconds...         │
│                                            │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│  75%                                      │
│                                            │
│  Completed: Codex ✓                       │
│  Remaining: None                          │
│                                            │
│  [Cancel Setup]                           │
└───────────────────────────────────────────┘
```

---

### 3.4 Cancellation Handling

**User clicks "Cancel" during setup:**

1. If terminal is open: Kill terminal process (subprocess.terminate())
2. Stop iteration through agent list
3. Write partial completion state to `setup_state.json`:
   ```json
   {
     "first_run_complete": true,
     "agents_setup": {
       "codex": true,
       "claude": false,
       "copilot": false,
       "gemini": false
     },
     "setup_cancelled": true,
     "setup_date": "2025-01-07T18:30:00Z"
   }
   ```
4. Close progress dialog
5. Show main window (app still usable even if setup incomplete)

**Important:** No orphaned processes! Always track subprocess and ensure it's terminated on cancel.

---

### 3.5 Terminal Launch Implementation

**Approach:** Use existing `terminal_apps.py` infrastructure

**Key Requirements:**
1. Launch terminal with agent login command
2. **Wait for process to exit** (blocking)
3. Capture exit code to detect success/failure
4. Return control to orchestrator after terminal closes

**Implementation:**

```python
def launch_agent_setup_terminal(agent: str) -> bool:
    """Launch terminal for agent setup, wait for completion.
    
    Returns:
        True if terminal exited successfully (exit code 0)
        False if terminal exited with error or was killed
    """
    # Get agent-specific setup command
    command = get_agent_setup_command(agent)
    if not command:
        return False
    
    # Detect terminal
    options = detect_terminal_options()
    if not options:
        # Fallback: show error dialog
        return False
    
    terminal = options[0]  # Use first available terminal
    
    # Launch terminal with command
    # CRITICAL: This must BLOCK until terminal closes
    process = launch_terminal_and_wait(
        terminal=terminal,
        command=command,
        cwd=None
    )
    
    # Check exit code
    if process.returncode == 0:
        return True
    return False


def launch_terminal_and_wait(
    terminal: TerminalOption,
    command: str,
    cwd: str | None
) -> subprocess.CompletedProcess:
    """Launch terminal and WAIT for it to close.
    
    This is a BLOCKING call that won't return until the terminal
    window is closed by the user.
    
    Returns:
        CompletedProcess with returncode
    """
    # Build terminal launch args
    args = _linux_terminal_args(
        terminal.terminal_id,
        terminal.exe or terminal.terminal_id,
        command,
        cwd=cwd
    )
    
    # Launch and WAIT
    # Note: We use wait() not Popen to block until completion
    result = subprocess.run(
        args,
        capture_output=False,  # Terminal shows output
        stdin=subprocess.DEVNULL,
        start_new_session=True
    )
    
    return result


def get_agent_setup_command(agent: str) -> str | None:
    """Get the setup command for an agent.
    
    Returns:
        Shell command string, or None if agent doesn't support setup
    """
    agent = normalize_agent(agent)
    
    if agent == "codex":
        return "codex login; read -p 'Press Enter to close...'"
    
    if agent == "claude":
        # RESEARCH NEEDED: Verify this is correct
        return "claude setup-token; read -p 'Press Enter to close...'"
    
    if agent == "copilot":
        # Copilot requires gh auth first
        return "gh auth login && gh copilot install; read -p 'Press Enter to close...'"
    
    if agent == "gemini":
        # RESEARCH NEEDED: Unknown setup command
        return None
    
    return None
```

**Why `read -p` at the end?**
- Prevents terminal from closing immediately after command completes
- Gives user a chance to read output/errors
- User presses Enter to explicitly close terminal
- Provides clear "I'm done" signal

---

### 3.6 Delay Between Setups

**Configuration:** 1-3 second delay (configurable)

**Default:** 2 seconds

**Implementation:**

```python
class SetupOrchestrator:
    def __init__(self):
        self.delay_between_agents = 2.0  # seconds
    
    async def run_sequential_setup(
        self,
        agents: list[str],
        progress_callback: Callable[[str, int, int], None]
    ) -> dict[str, bool]:
        """Run setup for multiple agents sequentially.
        
        Args:
            agents: List of agent names to set up
            progress_callback: Called with (agent, current, total) after each agent
        
        Returns:
            Dict mapping agent name to success status
        """
        results = {}
        total = len(agents)
        
        for idx, agent in enumerate(agents):
            current = idx + 1
            
            # Update progress
            progress_callback(agent, current, total)
            
            # Launch terminal and wait
            success = launch_agent_setup_terminal(agent)
            results[agent] = success
            
            # Wait before next agent (except after last one)
            if current < total:
                # Show countdown
                for remaining in range(int(self.delay_between_agents), 0, -1):
                    progress_callback(
                        f"Next: {agents[idx + 1]}",
                        current,
                        total,
                        status=f"Starting in {remaining} seconds..."
                    )
                    await asyncio.sleep(1.0)
        
        return results
```

**Why the delay?**
1. Prevents jarring UX (terminal closes, immediately another opens)
2. Gives user a moment to process what just happened
3. Allows file system / auth state to settle
4. Provides clear "next agent coming up" feedback

---

## 4. Per-Agent Management (NOT a Wizard)

### 4.1 Design Philosophy

**Key Principle:** Do NOT provide a "Run Setup Wizard" button.

**Why?**
- First-run setup is a one-time experience
- After that, users manage agents individually
- Full wizard is overwhelming for single-agent tasks
- Individual actions are more flexible and clear

**Instead:** Provide per-agent action buttons in Settings page.

---

### 4.2 Agent Management UI (Settings Page)

**Location:** Settings page, new "Agent Management" section

**UI Mockup:**

```
Settings > Agent Management
─────────────────────────────────────────────────────────────

Manage AI Agent CLIs

Each agent requires its CLI to be installed and authenticated.
You can configure individual agents below.

┌─────────────────────────────────────────────────────────┐
│ Agent     Status                  Actions               │
├─────────────────────────────────────────────────────────┤
│ Codex     ✗ Not logged in         [Login] [Configure]  │
│ Claude    ✓ Logged in             [Login] [Configure]  │
│ Copilot   ✓ Logged in             [Login] [Configure]  │
│ Gemini    ✗ Not installed         [Install Info]       │
│ ─────────────────────────────────────────────────────── │
│ GitHub    ✓ Logged in (user123)   [Login] [Configure]  │
└─────────────────────────────────────────────────────────┘

Notes:
- Login: Opens terminal to run agent's login command
- Configure: Opens terminal to run agent's config command
- Status refreshes automatically every 10 seconds
```

---

### 4.3 Action Definitions

#### 4.3.1 Login Action

**Behavior:**
1. Opens terminal with agent's login command
2. Does NOT wait for completion (user closes when done)
3. Refreshes status after 5 seconds

**Commands:**
- Codex: `codex login`
- Claude: `claude setup-token`
- Copilot: `gh auth login`
- Gemini: **RESEARCH NEEDED**
- GitHub: `gh auth login`

**Implementation:**

```python
def open_agent_login_terminal(agent: str) -> None:
    """Open terminal for agent login (non-blocking)."""
    command = get_agent_login_command(agent)
    if not command:
        # Show error dialog
        return
    
    terminal = detect_terminal_options()[0]
    launch_in_terminal(
        option=terminal,
        bash_script=command,
        cwd=None
    )
    # Returns immediately, terminal runs in background
```

---

#### 4.3.2 Configure Action

**Purpose:** Open agent's configuration/settings

**Behavior:**
1. Opens terminal with agent's config command OR
2. Opens config file in default editor OR
3. Shows info dialog with instructions

**Commands:**
- Codex: `codex config edit` or open `~/.codex/config.toml`
- Claude: `claude` (interactive) or open `~/.claude/` settings
- Copilot: `copilot config` or open `~/.copilot/config.json`
- Gemini: Open `~/.gemini/settings.json` in editor
- GitHub: `gh config`

**Implementation:**

```python
def open_agent_config(agent: str) -> None:
    """Open agent configuration."""
    agent = normalize_agent(agent)
    
    if agent == "codex":
        # Option 1: CLI command
        terminal = detect_terminal_options()[0]
        launch_in_terminal(
            option=terminal,
            bash_script="codex --help; read -p 'Press Enter to close...'",
            cwd=None
        )
        return
    
    if agent == "claude":
        # Option 2: Open config directory in file manager
        config_dir = Path.home() / ".claude"
        subprocess.Popen(["xdg-open", str(config_dir)])
        return
    
    # ... similar for other agents
```

---

#### 4.3.3 Verify Action (Optional)

**Purpose:** Test if agent works without logging in

**Behavior:**
1. Runs `agent --version` in background
2. Shows result in modal dialog

**Implementation:**

```python
def verify_agent(agent: str) -> tuple[bool, str]:
    """Verify agent CLI works.
    
    Returns:
        (success: bool, message: str)
    """
    try:
        result = subprocess.run(
            [agent, "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            version = result.stdout.strip()
            return (True, f"{agent} {version}")
        return (False, f"Failed: {result.stderr}")
    except Exception as e:
        return (False, f"Error: {str(e)}")
```

---

#### 4.3.4 Install Info Action

**Purpose:** Show installation instructions for missing agents

**Behavior:**
1. Show modal dialog with installation instructions
2. Include links to official docs
3. Provide platform-specific install commands

**Example Modal:**

```
┌─────────────────────────────────────────────┐
│  Gemini CLI Installation                    │
├─────────────────────────────────────────────┤
│                                              │
│  Gemini CLI is not installed.               │
│                                              │
│  To install:                                │
│                                              │
│  1. Visit: https://gemini.example.com       │
│  2. Download CLI for your platform          │
│  3. Follow installation instructions        │
│                                              │
│  Or use package manager (if available):     │
│                                              │
│  $ npm install -g @google/gemini-cli        │
│                                              │
│  After installation, refresh this page.     │
│                                              │
│  [Copy Install Command]  [Close]            │
└─────────────────────────────────────────────┘
```

---

### 4.4 Status Display

**Status Types:**

| Status | Icon | Meaning | Color |
|--------|------|---------|-------|
| Logged In | ✓ | Agent is authenticated and ready | Green |
| Not Logged In | ✗ | Agent is installed but not authenticated | Yellow |
| Not Installed | ✗ | Agent CLI not found in PATH | Red |
| Unknown | ? | Cannot determine login status | Gray |
| On Cooldown | ⏸ | Agent is rate-limited (from Task 3) | Orange |

**Status Refresh:**
- Automatically refresh every 10 seconds (background check)
- Manual refresh button
- Refresh immediately after Login action (5 second delay)

**Implementation:**

```python
class AgentManagementWidget(QWidget):
    def __init__(self):
        super().__init__()
        self._timer = QTimer()
        self._timer.timeout.connect(self._refresh_status)
        self._timer.start(10000)  # 10 seconds
    
    def _refresh_status(self):
        """Refresh status for all agents."""
        for agent in SUPPORTED_AGENTS:
            status = check_agent_status(agent)
            self._update_row(agent, status)
```

---

## 5. Persistence Design

### 5.1 Setup State File

**Location:** `~/.midoriai/agents-runner/setup_state.json`

**Schema:**

```json
{
  "version": 1,
  "first_run_complete": true,
  "setup_date": "2025-01-07T18:30:00Z",
  "setup_cancelled": false,
  "agents_setup": {
    "codex": true,
    "claude": true,
    "copilot": true,
    "gemini": false
  },
  "agents_enabled": {
    "codex": true,
    "claude": true,
    "copilot": true,
    "gemini": false
  },
  "last_status_check": "2025-01-07T19:00:00Z",
  "setup_delay_seconds": 2.0
}
```

**Fields:**
- `version`: Schema version (for future migrations)
- `first_run_complete`: If true, don't show first-run dialog
- `setup_date`: When first-run setup was completed/skipped
- `setup_cancelled`: If true, user cancelled mid-setup
- `agents_setup`: Which agents were successfully set up during first-run
- `agents_enabled`: Which agents user wants to use (selected in first-run dialog)
- `last_status_check`: Last time agent statuses were checked
- `setup_delay_seconds`: Configurable delay between agent setups

---

### 5.2 Integration with Existing state.json

**Approach:** Keep setup state separate from main state.json

**Why?**
1. Setup state is rarely modified
2. Main state.json is frequently written (tasks, environments)
3. Separation prevents conflicts
4. Easier to reset setup state if needed

**Alternative:** Could add `"setup": {...}` key to existing state.json, but this adds complexity to state migrations.

**Recommendation:** Use separate `setup_state.json` file.

---

## 6. Error Handling Strategy

### 6.1 Terminal Launch Failures

**Scenario:** No terminal emulator detected

**Handling:**
```python
def handle_no_terminal():
    # Show error dialog
    dialog = QMessageBox()
    dialog.setIcon(QMessageBox.Warning)
    dialog.setText("No terminal emulator found")
    dialog.setInformativeText(
        "Agents Runner requires a terminal emulator to run agent setup.\n\n"
        "Please install one of: konsole, gnome-terminal, xterm, ...\n\n"
        "You can also set the TERMINAL environment variable."
    )
    dialog.exec()
```

---

### 6.2 Agent CLI Not Found

**Scenario:** User selects agent for setup, but CLI is not in PATH

**Handling:**
```python
def validate_agent_selection(agents: list[str]) -> list[str]:
    """Filter out agents that aren't installed.
    
    Shows warning for any removed agents.
    """
    valid = []
    invalid = []
    
    for agent in agents:
        if check_agent_installed(agent):
            valid.append(agent)
        else:
            invalid.append(agent)
    
    if invalid:
        # Show warning
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Warning)
        msg.setText(f"Some agents are not installed: {', '.join(invalid)}")
        msg.setInformativeText("These agents will be skipped.")
        msg.exec()
    
    return valid
```

---

### 6.3 Login Command Failure

**Scenario:** Agent login command exits with non-zero code

**Handling:**
```python
def handle_login_failure(agent: str, exit_code: int):
    """Handle failed login attempt."""
    # Show error dialog with exit code
    dialog = QMessageBox()
    dialog.setIcon(QMessageBox.Warning)
    dialog.setText(f"{agent} login failed (exit code {exit_code})")
    dialog.setInformativeText(
        f"The {agent} login command did not complete successfully.\n\n"
        "You can try again from Settings > Agent Management."
    )
    dialog.setDetailedText(
        f"Command: {get_agent_login_command(agent)}\n"
        f"Exit code: {exit_code}"
    )
    dialog.exec()
```

---

### 6.4 Cancellation Mid-Setup

**Handling:** See section 3.4 (Cancellation Handling)

**Key Points:**
- Always terminate subprocess cleanly
- Write partial state to setup_state.json
- Don't block app usage
- Allow user to resume setup later via Settings

---

### 6.5 Status Detection Failures

**Scenario:** Cannot determine if agent is logged in

**Handling:**
```python
def check_agent_status(agent: str) -> AgentStatus:
    """Check agent status with fallback to Unknown."""
    installed = check_agent_installed(agent)
    if not installed:
        return AgentStatus(
            agent=agent,
            installed=False,
            logged_in=False,
            status_text="Not installed",
            status_type=StatusType.NOT_INSTALLED
        )
    
    # Try to check login status
    try:
        logged_in, message = check_agent_login(agent)
        return AgentStatus(
            agent=agent,
            installed=True,
            logged_in=logged_in,
            status_text=message,
            status_type=StatusType.LOGGED_IN if logged_in else StatusType.NOT_LOGGED_IN
        )
    except Exception:
        # Fallback to Unknown
        return AgentStatus(
            agent=agent,
            installed=True,
            logged_in=False,
            status_text="Unknown (check failed)",
            status_type=StatusType.UNKNOWN
        )
```

---

## 7. File Structure and Implementation Plan

### 7.1 New Modules

#### 7.1.1 `agents_runner/setup/orchestrator.py` (250-300 lines)

**Purpose:** Orchestrate sequential setup flow

**Key Classes:**
- `SetupOrchestrator`: Main orchestration logic
- `SetupProgress`: Progress tracking

**Key Functions:**
- `run_sequential_setup()`: Main entry point
- `launch_agent_setup_terminal()`: Launch single agent terminal
- `check_setup_complete()`: Check if first-run done
- `mark_setup_complete()`: Write setup_state.json

**Dependencies:**
- `terminal_apps.py`: Terminal detection and launch
- `setup/agent_status.py`: Status detection
- `agent_cli.py`: Agent normalization

---

#### 7.1.2 `agents_runner/setup/agent_status.py` (200-250 lines)

**Purpose:** Detect agent installation and login status

**Key Functions:**
- `check_agent_installed(agent: str) -> bool`
- `check_agent_login(agent: str) -> tuple[bool, str]`
- `check_codex_login() -> tuple[bool, str]`
- `check_claude_login() -> tuple[bool, str]`
- `check_copilot_login() -> tuple[bool, str]`
- `check_gemini_login() -> tuple[bool, str]`
- `check_github_cli_login() -> tuple[bool, str]`
- `check_agent_status(agent: str) -> AgentStatus`

**Data Classes:**
```python
@dataclass
class AgentStatus:
    agent: str
    installed: bool
    logged_in: bool
    status_text: str
    status_type: StatusType  # Enum: LOGGED_IN, NOT_LOGGED_IN, etc.
    username: str | None = None  # For display
    last_checked: datetime | None = None
```

---

#### 7.1.3 `agents_runner/setup/commands.py` (100-150 lines)

**Purpose:** Agent-specific setup commands

**Key Functions:**
- `get_agent_login_command(agent: str) -> str | None`
- `get_agent_config_command(agent: str) -> str | None`
- `get_agent_verify_command(agent: str) -> str`

**Command Definitions:**
```python
AGENT_LOGIN_COMMANDS = {
    "codex": "codex login; read -p 'Press Enter to close...'",
    "claude": "claude setup-token; read -p 'Press Enter to close...'",
    "copilot": "gh auth login && gh copilot install; read -p 'Press Enter...'",
    "gemini": None,  # RESEARCH NEEDED
}

AGENT_CONFIG_COMMANDS = {
    "codex": "codex --help",
    "claude": None,  # Open config dir instead
    "copilot": "gh config list",
    "gemini": None,  # Open settings.json instead
}
```

---

#### 7.1.4 `agents_runner/ui/dialogs/first_run_setup.py` (250-300 lines)

**Purpose:** First-run setup dialog UI

**Key Classes:**
- `FirstRunSetupDialog(QDialog)`: Main dialog
- `AgentSelectionWidget(QWidget)`: Agent checkbox list
- `SetupProgressDialog(QDialog)`: Progress during setup

**Key Signals:**
- `setup_started(agents: list[str])`
- `setup_completed(results: dict[str, bool])`
- `setup_cancelled()`

**UI Components:**
- Agent status table with checkboxes
- "Skip Setup" and "Begin Setup" buttons
- Instructions text

---

#### 7.1.5 `agents_runner/ui/pages/agent_management.py` (200-250 lines)

**Purpose:** Agent management section in Settings page

**Key Classes:**
- `AgentManagementWidget(QWidget)`: Main widget
- `AgentRow(QWidget)`: Single agent row with status and buttons

**Key Features:**
- Status display with auto-refresh
- Login, Configure, Verify buttons per agent
- Status color coding
- Manual refresh button

---

### 7.2 Modified Files

#### 7.2.1 `agents_runner/app.py`

**Changes:**
- Check `setup_state.json` on app launch
- Show `FirstRunSetupDialog` if needed
- Block main window until setup complete/skipped

**New Code:**
```python
def run_app(argv: list[str]) -> None:
    _configure_qtwebengine_runtime()
    
    from PySide6.QtWidgets import QApplication
    from agents_runner.ui.main_window import MainWindow
    from agents_runner.setup.orchestrator import check_setup_complete
    from agents_runner.ui.dialogs.first_run_setup import FirstRunSetupDialog
    
    app = QApplication(argv)
    # ... setup app ...
    
    # Check if first-run setup needed
    if not check_setup_complete():
        dialog = FirstRunSetupDialog(parent=None)
        result = dialog.exec()
        # Dialog handles writing setup_state.json
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
```

**Lines Changed:** ~10-20 lines added

---

#### 7.2.2 `agents_runner/ui/pages/settings.py`

**Changes:**
- Add "Agent Management" section
- Import and embed `AgentManagementWidget`
- Add section after existing settings

**New Code:**
```python
# In SettingsPage.__init__()

# Add Agent Management section
agent_mgmt_label = QLabel("Agent Management")
agent_mgmt_label.setStyleSheet("font-size: 16px; font-weight: 700;")
layout.addWidget(agent_mgmt_label)

from agents_runner.ui.pages.agent_management import AgentManagementWidget
self._agent_mgmt = AgentManagementWidget()
layout.addWidget(self._agent_mgmt)
```

**Lines Changed:** ~20-30 lines added

---

#### 7.2.3 `agents_runner/terminal_apps.py`

**Changes:**
- Add `launch_terminal_and_wait()` function (blocking version)
- Keep existing `launch_in_terminal()` (non-blocking)

**New Function:**
```python
def launch_terminal_and_wait(
    option: TerminalOption,
    bash_script: str,
    cwd: str | None = None
) -> subprocess.CompletedProcess:
    """Launch terminal and WAIT for it to close (blocking).
    
    This is used for sequential setup where we need to wait
    for one terminal to close before opening the next.
    
    Returns:
        CompletedProcess with returncode
    """
    cwd = os.path.abspath(os.path.expanduser(cwd)) if cwd else None
    
    if option.kind == "linux-exe":
        args = _linux_terminal_args(
            option.terminal_id,
            option.exe or option.terminal_id,
            bash_script,
            cwd=cwd
        )
        return subprocess.run(args, start_new_session=True)
    
    # ... handle mac terminals similarly ...
    
    raise RuntimeError(f"Unsupported terminal kind: {option.kind}")
```

**Lines Changed:** ~30-40 lines added

---

### 7.3 New Config Files

#### 7.3.1 `~/.midoriai/agents-runner/setup_state.json`

**Created by:** `setup/orchestrator.py`

**Schema:** See section 5.1

**Permissions:** 0600 (readable/writable by user only)

---

### 7.4 Implementation Task Breakdown

**Phase 1: Detection Infrastructure (2-3 days)**

1. Create `agents_runner/setup/agent_status.py`
   - Implement `check_agent_installed()`
   - Implement `check_codex_login()`
   - Implement `check_copilot_login()` (using gh CLI)
   - Stub `check_claude_login()` (mark as RESEARCH NEEDED)
   - Stub `check_gemini_login()` (mark as RESEARCH NEEDED)
   - Create `AgentStatus` dataclass
   - Write unit tests

2. Create `agents_runner/setup/commands.py`
   - Define login commands for each agent
   - Define config commands for each agent
   - Document RESEARCH NEEDED items

3. Test detection manually on development machine

**Phase 2: Terminal Launch (1-2 days)**

4. Modify `agents_runner/terminal_apps.py`
   - Add `launch_terminal_and_wait()` function
   - Test blocking behavior
   - Ensure clean process termination

5. Write integration test for terminal launch

**Phase 3: Setup Orchestration (2-3 days)**

6. Create `agents_runner/setup/orchestrator.py`
   - Implement `SetupOrchestrator` class
   - Implement `run_sequential_setup()` with delays
   - Implement `check_setup_complete()`
   - Implement `mark_setup_complete()`
   - Add cancellation handling
   - Write unit tests

7. Create `~/.midoriai/agents-runner/setup_state.json` schema
   - Define schema
   - Add migration logic (if needed)
   - Test persistence

**Phase 4: First-Run Dialog UI (2-3 days)**

8. Create `agents_runner/ui/dialogs/first_run_setup.py`
   - Design dialog layout
   - Implement agent selection table
   - Wire up status detection
   - Add "Skip" and "Begin Setup" buttons
   - Create progress dialog
   - Connect to orchestrator

9. Test first-run dialog flow end-to-end

**Phase 5: Agent Management UI (1-2 days)**

10. Create `agents_runner/ui/pages/agent_management.py`
    - Design management widget layout
    - Implement status table with auto-refresh
    - Add Login/Configure/Verify buttons
    - Wire up terminal launch (non-blocking)
    - Test status refresh

11. Modify `agents_runner/ui/pages/settings.py`
    - Add Agent Management section
    - Embed management widget

**Phase 6: App Integration (1 day)**

12. Modify `agents_runner/app.py`
    - Add setup check on app launch
    - Show first-run dialog if needed
    - Ensure main window doesn't show until setup complete

13. End-to-end integration testing

**Phase 7: Research and Polish (2-3 days)**

14. **RESEARCH:** Claude authentication detection
    - Test `claude whoami` behavior
    - Document config file structure
    - Update `check_claude_login()`
    - Update login command if needed

15. **RESEARCH:** Gemini authentication and setup
    - Find proper auth status command
    - Document settings.json structure
    - Update `check_gemini_login()`
    - Find proper login/setup command
    - Update `get_agent_login_command()`

16. Add error handling and edge cases
    - Test with no terminal available
    - Test with missing agents
    - Test cancellation at various points
    - Test rapid status checks

17. Documentation updates
    - Update README with setup info
    - Add troubleshooting guide
    - Document manual setup process

**Total Estimated Time:** 7-10 days (matches task breakdown estimate)

---

## 8. Success Criteria

### 8.1 First-Run Setup

- [ ] First-run dialog appears on fresh install
- [ ] All installed agents detected correctly
- [ ] Login status shown accurately for each agent
- [ ] User can select which agents to set up
- [ ] Setup runs sequentially (one terminal at a time)
- [ ] 1-3 second delay between agent setups
- [ ] Progress dialog shows current agent and countdown
- [ ] User can cancel at any time without leaving orphaned processes
- [ ] Setup completion state persisted correctly
- [ ] "Skip Setup" works and doesn't show dialog again
- [ ] Main window doesn't appear until setup complete/skipped
- [ ] Existing users don't see first-run dialog

### 8.2 Per-Agent Management

- [ ] Agent Management section visible in Settings page
- [ ] Status displays correctly for all agents
- [ ] Status refreshes automatically every 10 seconds
- [ ] Login button opens terminal with correct command
- [ ] Configure button opens correct config location
- [ ] Verify button tests agent and shows result
- [ ] Status updates after login action (with delay)
- [ ] No "Setup Wizard" button (individual actions only)
- [ ] Install Info shown for missing agents

### 8.3 Error Handling

- [ ] Graceful handling when no terminal available
- [ ] Warning when agent CLI not found
- [ ] Error dialog when login fails
- [ ] Partial state saved on cancellation
- [ ] Status detection falls back to "Unknown" on failure

### 8.4 UX Quality

- [ ] UI is responsive during terminal wait (use QTimer/async)
- [ ] Clear feedback on what's happening at each step
- [ ] No jarring transitions between agents
- [ ] Terminal windows have clear close instructions
- [ ] Status icons and colors are intuitive

---

## 9. Open Questions and Research Tasks

### 9.1 Claude Code

**Questions:**
1. What is the correct command to check Claude login status?
   - `claude whoami` launches interactive setup, not suitable
   - Is there a `--check-auth` or similar flag?
   - Should we just check for config files?

2. What files exist in `~/.claude/` when logged in?
   - Are there auth tokens or session files we can check?
   - What's the structure of these files?

3. What is the correct setup/login command?
   - `claude setup-token` opens browser, is this correct?
   - Are there any flags to make it non-interactive?

4. Does running `claude` without auth block waiting for input?
   - If yes, we can't use it for status detection
   - Need to find alternative

**Research Actions:**
- [ ] Test `claude --help` for auth-related commands
- [ ] Test `claude setup-token` flow
- [ ] Examine `~/.claude/` structure when logged in vs not logged in
- [ ] Check Claude Code documentation for auth detection

---

### 9.2 Gemini CLI

**Questions:**
1. What is the correct command to check Gemini login status?
   - Is there a `gemini auth status` command?
   - How do we detect if GEMINI_API_KEY is valid?

2. What is the structure of `~/.gemini/settings.json`?
   - What fields indicate authentication?
   - Can we safely parse this file?

3. What is the correct login/setup command?
   - Is there a `gemini auth login`?
   - Do users manually edit settings.json?
   - Is setup via environment variables only?

4. Can we trigger auth programmatically?
   - Or must it be manual (env vars or file editing)?

**Research Actions:**
- [ ] Test `gemini --help` for auth-related commands
- [ ] Examine `~/.gemini/settings.json` structure
- [ ] Check Gemini CLI documentation for auth setup
- [ ] Test if `gemini whoami` or similar exists

---

### 9.3 Terminal Launch on macOS

**Questions:**
1. Does `subprocess.run()` block on macOS when launching Terminal.app?
   - macOS uses AppleScript for terminal launch
   - Does the script return immediately or wait?

2. How to detect when macOS terminal window closes?
   - May need different approach than Linux

**Research Actions:**
- [ ] Test terminal launch on macOS
- [ ] Find way to track terminal process on macOS
- [ ] Consider using terminal-notifier or similar

---

### 9.4 Cooldown Integration

**Question:**
- How does agent cooldown status from Task 3 integrate with agent management?
- Should we show cooldown in status display?
- Should Login button be disabled during cooldown?

**Answer:**
- Yes, show cooldown status in Agent Management table
- Don't disable Login button (user may want to try anyway)
- Add cooldown icon to status: `⏸ On cooldown (42s)`

**Implementation:**
- Import `AgentWatchState` from Task 3
- Check cooldown in `check_agent_status()`
- Update status display to show cooldown

---

## 10. Risk Analysis

### 10.1 High-Risk Areas

#### Risk: Terminal launch blocking indefinitely

**Scenario:** User doesn't close terminal, setup hangs forever

**Mitigation:**
- Add "Cancel" button that kills subprocess
- Show clear instructions in terminal: "Press Enter to close"
- Consider timeout (30 minutes?) to auto-cancel
- Log warning if terminal open >5 minutes

**Impact:** High (blocks app usage)

---

#### Risk: Claude/Gemini detection unreliable

**Scenario:** Can't determine login status, show incorrect status

**Mitigation:**
- Default to "Unknown" status if detection fails
- Allow user to proceed with Login action anyway
- Add manual "Mark as Logged In" option (advanced users)
- Document detection limitations

**Impact:** Medium (UX degradation, but not blocking)

---

#### Risk: Setup state corruption

**Scenario:** setup_state.json corrupted or invalid

**Mitigation:**
- Validate JSON on load
- Fallback to default state if invalid
- Backup old state before writing
- Use atomic writes (temp file + rename)

**Impact:** Medium (can reset, user must re-run setup)

---

#### Risk: First-run dialog shows repeatedly

**Scenario:** setup_state.json not written correctly

**Mitigation:**
- Write flag immediately on "Skip" or completion
- Use fsync to ensure write completes
- Test file write in unit tests
- Add logging for debug

**Impact:** High (very annoying UX)

---

### 10.2 Medium-Risk Areas

#### Risk: Terminal not detected on some systems

**Scenario:** User on obscure Linux distro, no terminal found

**Mitigation:**
- Provide fallback instructions (set $TERMINAL env var)
- Show helpful error dialog with suggestions
- Allow manual command specification in settings
- Document supported terminals

**Impact:** Medium (affects small subset of users)

---

#### Risk: Agent login fails silently

**Scenario:** Login command exits 0 but auth didn't work

**Mitigation:**
- Always re-check status after login (5s delay)
- Show status in progress dialog: "Verifying..."
- If still not logged in, show warning
- Provide retry option

**Impact:** Medium (user may not notice, will fail on first task run)

---

### 10.3 Low-Risk Areas

#### Risk: Delay too short/long between setups

**Scenario:** User annoyed by 3-second delays (or wants longer)

**Mitigation:**
- Make delay configurable in setup_state.json
- Default 2 seconds (reasonable for most)
- Advanced users can edit config
- Could add UI slider in future

**Impact:** Low (minor UX preference)

---

## 11. Future Enhancements

**Not in scope for initial implementation, but consider for future:**

1. **Agent Status Dashboard:**
   - Dedicated page showing all agent statuses
   - Real-time cooldown countdowns
   - Recent error messages
   - Usage statistics

2. **Automated Agent Updates:**
   - Detect when agent CLI updates available
   - Prompt user to update
   - Show changelog

3. **Multi-Agent Setup Profiles:**
   - Save different agent configurations
   - "Work" vs "Personal" agent setups
   - Quick switch between profiles

4. **Setup Templates:**
   - Pre-configured setups for common use cases
   - "Development," "Research," "Writing" templates
   - Share templates with team

5. **Advanced Status Detection:**
   - Detect agent subscription status (e.g., Copilot subscription)
   - Detect rate limit quotas remaining
   - Show model availability

6. **Agent Health Monitoring:**
   - Periodic background checks
   - Alert if agent stops working
   - Auto-retry on transient failures

---

## 12. Documentation Updates Required

### 12.1 User Documentation

**File:** `README.md` (or separate setup guide)

**New Sections:**
- Getting Started with Agents Runner
- First-Time Setup Guide
- Managing Agent Authentication
- Troubleshooting Agent Login Issues
- Supported AI Agent CLIs

---

### 12.2 Developer Documentation

**File:** `.agents/notes/setup-system-architecture.md`

**Content:**
- Setup orchestration design
- Agent status detection methods
- Terminal launch mechanisms
- Sequential setup timing
- Cancellation handling

---

### 12.3 Agent-Specific Guides

**Files:** (new directory)
- `.agents/notes/agents/codex-setup.md`
- `.agents/notes/agents/claude-setup.md`
- `.agents/notes/agents/copilot-setup.md`
- `.agents/notes/agents/gemini-setup.md`

**Content for Each:**
- How to install CLI
- How to authenticate
- How to verify setup
- Common issues and solutions
- Configuration options

---

## 13. Testing Strategy

### 13.1 Unit Tests

**Module:** `tests/setup/test_agent_status.py`

- Test `check_agent_installed()` with mocked `shutil.which()`
- Test `check_codex_login()` with mocked subprocess
- Test `check_copilot_login()` with mocked gh CLI
- Test fallback to "Unknown" on failures
- Test AgentStatus dataclass serialization

**Module:** `tests/setup/test_orchestrator.py`

- Test `check_setup_complete()` with mock filesystem
- Test `mark_setup_complete()` writes correct JSON
- Test `run_sequential_setup()` calls agents in order
- Test cancellation mid-setup
- Test delay timing (with mocked sleep)

**Module:** `tests/setup/test_commands.py`

- Test `get_agent_login_command()` returns correct commands
- Test handling of unknown agents
- Test command string formatting

---

### 13.2 Integration Tests

**Test:** First-Run Flow
1. Delete setup_state.json
2. Launch app
3. Verify first-run dialog appears
4. Mock terminal launch
5. Verify sequential calls with delays
6. Verify setup_state.json written

**Test:** Skip Setup
1. Delete setup_state.json
2. Launch app
3. Click "Skip Setup"
4. Verify setup_state.json written with first_run_complete=true
5. Relaunch app
6. Verify first-run dialog doesn't appear

**Test:** Cancellation
1. Start setup with multiple agents
2. Cancel after first agent
3. Verify subprocess terminated
4. Verify partial state written
5. Verify app still usable

---

### 13.3 Manual Testing Checklist

**First-Run Setup:**
- [ ] Fresh install shows first-run dialog
- [ ] All installed agents detected
- [ ] Login status accurate
- [ ] Select multiple agents for setup
- [ ] Terminals open one at a time
- [ ] Delay visible between agents
- [ ] Progress updates correctly
- [ ] Cancel button works at each stage
- [ ] Skip button works
- [ ] Subsequent launches don't show dialog

**Agent Management:**
- [ ] Settings page shows Agent Management section
- [ ] All agents listed with correct status
- [ ] Login button opens terminal
- [ ] Terminal has correct command
- [ ] Status refreshes after login
- [ ] Configure button works
- [ ] Verify button shows correct result
- [ ] Install Info shown for missing agents

**Edge Cases:**
- [ ] No terminal available (show error)
- [ ] Agent CLI missing (show warning)
- [ ] Login fails (show error, allow retry)
- [ ] Rapid button clicks (debounce)
- [ ] Multiple instances running (lock file?)

---

## 14. Conclusion

This design provides a comprehensive, user-friendly approach to first-run setup and per-agent management. The key innovation is the **sequential setup flow** with explicit timing requirements, which prevents user overwhelm and ensures a smooth onboarding experience.

**Critical Success Factors:**
1. **Sequential timing must work correctly** - This is non-negotiable
2. **Cancellation must be clean** - No orphaned processes
3. **Status detection must be reliable** - Or gracefully degrade to "Unknown"
4. **Research tasks must be completed** - Claude and Gemini need investigation

**Next Steps:**
1. **Review this document** with stakeholders
2. **Complete research tasks** (Claude, Gemini auth detection)
3. **Begin implementation** following the 7-phase plan in section 7.4
4. **Iterate based on testing** and user feedback

---

**Document Status:** DRAFT - Ready for Review  
**Requires Research:** Claude login detection, Gemini setup commands  
**Estimated Implementation Time:** 7-10 days (matches task breakdown)  
**Dependencies:** Task 1 complete (this task), terminal_apps.py stable  
**Blocks:** Task 6 (Environment UI enhancements)

---

**End of First-Run Setup Design Audit**
