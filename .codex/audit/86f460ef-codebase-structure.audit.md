# Agents-Runner Codebase Structure Audit

**Audit ID:** 86f460ef  
**Date:** 2025-01-07  
**Auditor:** Auditor Mode  
**Purpose:** Map current application structure for unstable refactor planning

---

## Executive Summary

The Agents-Runner is a PySide6-based desktop application that orchestrates AI agent execution in Docker containers. The codebase consists of ~15,268 lines of Python across 101 files, organized into logical modules. The application manages environments, tasks, GitHub integration, artifact collection, and interactive terminal sessions.

**Key Findings:**
- Modular architecture with clear separation of concerns
- Heavy use of mixin pattern for MainWindow (11 mixins)
- No current retry/fallback/rate-limit mechanisms for agent execution
- Agent selection system exists but appears unimplemented in execution flow
- PR metadata system only active for Copilot (gh_pr_metadata_enabled check)
- Environment locking distinguishes git repos (GitHub clone) vs local folders

**Critical for Refactor:**
- 6 files exceed 500 lines (hard limit concern)
- MainWindow coordination logic spread across 11 mixin files
- Docker execution in agent_worker.py is monolithic (504 lines)
- No centralized agent selection/scheduling logic

---

## Repository Structure

```
agents_runner/
├── Core Application
│   ├── app.py (62)                      - App initialization & Qt config
│   ├── main.py (11)                     - Entry point
│   └── persistence.py (448)             - State save/load (exceeds soft limit)
│
├── UI Layer
│   ├── ui/
│   │   ├── main_window.py (234)         - MainWindow orchestrator
│   │   ├── main_window_*.py (11 files)  - MainWindow mixins
│   │   ├── pages/ (10 files)            - Page implementations
│   │   ├── bridges.py (63)              - Qt↔Worker signal bridge
│   │   ├── task_model.py (158)          - Task data model
│   │   ├── graphics.py (410)            - Custom paint/graphics
│   │   ├── animations.py (204)          - UI animations
│   │   └── utils.py (116)               - UI utilities
│   │
│   ├── widgets/ (10 files)              - Custom Qt widgets
│   └── style/ (6 files)                 - Stylesheet generation
│
├── Agent Execution
│   ├── docker/
│   │   ├── agent_worker.py (504)        - Main agent runner (EXCEEDS LIMIT)
│   │   ├── preflight_worker.py (324)    - Preflight execution
│   │   ├── config.py (35)               - Docker config dataclass
│   │   ├── process.py (65)              - Docker CLI wrappers
│   │   └── utils.py (71)                - Mount resolution
│   │
│   ├── agent_cli.py (127)               - Agent CLI command building
│   ├── docker_runner.py (9)             - Public API exports
│   └── docker_platform.py (60)          - Platform detection (Rosetta)
│
├── Environment Management
│   ├── environments/
│   │   ├── model.py (94)                - Environment dataclass
│   │   ├── storage.py (161)             - Load/save environments
│   │   ├── serialize.py (354)           - JSON serialization (near limit)
│   │   ├── cleanup.py (243)             - Workspace cleanup
│   │   ├── parse.py (67)                - Env var/mount parsing
│   │   └── prompt_storage.py (87)       - Prompt file management
│   │
├── GitHub Integration
│   ├── gh/
│   │   ├── repo_clone.py (152)          - GitHub repo cloning
│   │   ├── task_plan.py (368)           - Branch planning & PR creation
│   │   ├── git_ops.py (123)             - Git operations
│   │   ├── gh_cli.py (5)                - gh CLI detection
│   │   └── process.py (64)              - Subprocess helpers
│   │
│   ├── gh_management.py (130)           - High-level GH orchestration
│   ├── pr_metadata.py (93)              - PR metadata JSON handling
│   └── github_token.py (49)             - Token resolution
│
├── Artifacts
│   └── artifacts.py (328)               - Encryption/collection (near limit)
│
├── Prompts
│   ├── prompts/ (7 markdown files)      - Prompt templates
│   └── prompts/loader.py (102)          - Template loading
│
└── Utilities
    ├── terminal_apps.py (241)           - Terminal detection
    ├── log_format.py (64)               - Log formatting
    ├── prompt_sanitizer.py (11)         - Prompt cleanup
    └── agent_display.py (38)            - Agent display helpers

Configuration:
├── pyproject.toml                       - Project metadata
├── uv.lock                              - Dependency lock
└── AGENTS.md                            - Contributor guide
```

**Line Count Distribution:**
- Total: 15,268 lines
- Files > 500 lines: 6 (agent_worker.py 504, task_details.py 503, main_window_settings.py 512, environments_agents.py 529, main_window_tasks_interactive_docker.py 596)
- Files > 300 lines: 14
- Avg lines per file: ~151

---

## Application Flow Diagrams

### 1. Home → New Task → Run → Task View Flow

```
┌─────────────┐
│  Dashboard  │  (ui/pages/dashboard.py)
│   (Home)    │  - Shows running/queued tasks
└──────┬──────┘  - Shows past tasks (paginated)
       │
       │ Click "New task" button
       ↓
┌─────────────────┐
│   New Task      │  (ui/pages/new_task.py:31-497)
│   Page          │
├─────────────────┤
│ • Environment ◄─┼─ QComboBox (line 49)
│   selector      │   Data: env_id, displays env.name
│                 │
│ • Prompt  ◄─────┼─ QPlainTextEdit (line 86) ← **SPELLCHECK TARGET**
│   editor        │   setPlaceholderText(), setTabChangesFocus(True)
│                 │
│ • Terminal      │   For interactive mode
│   selector      │
│                 │
│ • Command args  │   Agent CLI flags
│                 │
│ • Base branch ◄─┼─ Only shown if env in _gh_locked_envs (line 306)
│   selector      │   (GitHub-managed environments)
│                 │
│ • [Run Agent] ──┼─ requested_run signal → _start_task_from_ui
│ • [Interactive]─┼─ requested_launch signal → _start_interactive_task_from_ui
└────────┬────────┘
         │
         │ Run Agent clicked
         ↓
┌──────────────────────────────────────────────────────────────┐
│  main_window_tasks_agent.py::_start_task_from_ui            │
│  (lines 81-355)                                              │
├──────────────────────────────────────────────────────────────┤
│  1. Validate Docker, prompt, environment                     │
│  2. Generate task_id = uuid4().hex[:10]                      │
│  3. Determine workspace path (GitHub or local)               │
│  4. Check capacity (_can_start_new_agent_for_env)            │
│  5. Append environment prompts if enabled                    │
│  6. Prepare PR metadata file if gh_pr_metadata_enabled       │
│  7. Create DockerRunnerConfig                                │
│  8. Create Task model object                                 │
│  9. Create TaskRunnerBridge + QThread                        │
│ 10. Start worker or queue if at capacity                     │
└──────────────────┬───────────────────────────────────────────┘
                   │
                   ↓
         ┌─────────────────────┐
         │  DockerAgentWorker  │  (docker/agent_worker.py:48-504)
         │       .run()        │
         ├─────────────────────┤
         │ 1. GitHub clone     │  prepare_github_repo_for_task()
         │    (if enabled)     │  → gh_management.py:63-131
         │                     │
         │ 2. Pull image       │  _pull_image() if needed
         │                     │
         │ 3. Build mounts     │  - Config dir mount
         │                     │  - Workspace mount
         │                     │  - Artifact staging mount (/tmp/agents-artifacts)
         │                     │  - Extra mounts (env.extra_mounts)
         │                     │  - Preflight script mounts (if enabled)
         │                     │  - PR metadata mount (if gh_pr_metadata_enabled)
         │                     │
         │ 4. Build command    │  build_noninteractive_cmd()
         │                     │  → agent_cli.py:58-123
         │                     │
         │ 5. docker run       │  Detached, stream logs
         │                     │
         │ 6. Stream logs      │  subprocess.Popen + selectors
         │                     │
         │ 7. Wait for exit    │
         │                     │
         │ 8. Collect          │  collect_artifacts_from_container()
         │    artifacts        │  → artifacts.py:257-328
         │                     │
         │ 9. Signal done      │  _on_done callback
         └─────────┬───────────┘
                   │
                   ↓
         ┌─────────────────────┐
         │  TaskRunnerBridge   │  (ui/bridges.py)
         │  signals back to    │  - done signal
         │  MainWindow         │  - log signal
         │                     │  - state signal
         └─────────┬───────────┘
                   │
                   ↓
┌──────────────────────────────────────┐
│  main_window_task_events.py         │
│  ::_on_bridge_done                   │
├──────────────────────────────────────┤
│  1. Update task status               │
│  2. Save gh_branch if available      │
│  3. Persist to state.json            │
│  4. Try starting queued tasks        │
└──────────┬───────────────────────────┘
           │
           │ User clicks task in dashboard
           ↓
┌─────────────────────────────┐
│  Task Details Page          │  (ui/pages/task_details.py)
├─────────────────────────────┤
│  Tabs:                      │
│  • Task ─ Status, logs      │  QPlainTextEdit with LogHighlighter
│  • Desktop ─ noVNC viewer   │  QWebEngineView (if headless_desktop)
│  • Artifacts ─ List/view    │  artifacts_tab.py:7-301
│                             │
│  Actions (top-right menu):  │
│  • Create PR ───────────────┼─ Uses gh_repo_root, gh_branch from task
│  • Restart container        │  (for interactive debugging)
│  • Stop container           │
│  • Remove container         │
└─────────────────────────────┘
```

### 2. Environments Editor Flow

```
┌────────────────────────────────────────────────────────────┐
│  Environments Page  (ui/pages/environments.py)             │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  ┌─────────────┐  [New] [Duplicate] [Delete]             │
│  │ Environment │                                           │
│  │  Selector   │  QComboBox - shows all saved environments│
│  └─────────────┘                                           │
│                                                            │
│  QTabWidget with 6 tabs:                                   │
│  ┌────────────────────────────────────────────────────┐   │
│  │ 1. General Tab                                      │   │
│  │    - Name                          QLineEdit        │   │
│  │    - Color/Stain                   QComboBox        │   │
│  │    - Workspace (workdir)           QLineEdit        │   │
│  │    - Max concurrent agents         QLineEdit        │   │
│  │    - Headless desktop              QCheckBox        │   │
│  │    - Workspace type:                                │   │
│  │      • Lock to local folder → gh_management_mode    │   │
│  │      • Lock to GitHub repo  → = "local" or "github" │   │
│  │                                                      │   │
│  │    GitHub Controls (if mode != "none"):             │   │
│  │    - Repository/path         QLineEdit              │   │
│  │    - Use host gh CLI         QCheckBox              │   │
│  │    - PR metadata enabled     QCheckBox (Copilot)    │   │
│  │    - Last base branch        QComboBox (dynamic)    │   │
│  └────────────────────────────────────────────────────┘   │
│  ┌────────────────────────────────────────────────────┐   │
│  │ 2. Agents Tab  (environments_agents.py)             │   │
│  │    QTableWidget with columns:                       │   │
│  │    Priority | Agent | ID | Config | CLI Flags |     │   │
│  │                                    Fallback | Remove│   │
│  │                                                      │   │
│  │    Data stored in Environment.agent_selection:      │   │
│  │      - agents: list[AgentInstance]                  │   │
│  │      - selection_mode: "round-robin"                │   │
│  │      - agent_fallbacks: dict[str, str]              │   │
│  │                                                      │   │
│  │    NOTE: This UI exists but agent selection is NOT  │   │
│  │          currently used in agent_worker.py. The     │   │
│  │          worker uses settings-level "use" field.    │   │
│  └────────────────────────────────────────────────────┘   │
│  ┌────────────────────────────────────────────────────┐   │
│  │ 3. Prompts Tab  (environments_prompts.py)           │   │
│  │    QTableWidget for custom environment prompts:     │   │
│  │    Enabled | Name | Source                          │   │
│  │                                                      │   │
│  │    Source options:                                  │   │
│  │    - Inline text                                    │   │
│  │    - External file path                             │   │
│  │                                                      │   │
│  │    Prompts appended to task prompt if enabled       │   │
│  │    (see main_window_tasks_agent.py:238-249)         │   │
│  └────────────────────────────────────────────────────┘   │
│  ┌────────────────────────────────────────────────────┐   │
│  │ 4. Env Vars Tab                                     │   │
│  │    QPlainTextEdit for KEY=VALUE pairs               │   │
│  │    Parsed by environments/parse.py:11-40            │   │
│  │    Injected via docker run -e KEY=VALUE             │   │
│  └────────────────────────────────────────────────────┘   │
│  ┌────────────────────────────────────────────────────┐   │
│  │ 5. Mounts Tab                                       │   │
│  │    QPlainTextEdit for docker volume mounts          │   │
│  │    Format: /host/path:/container/path:ro            │   │
│  │    Parsed by environments/parse.py:43-67            │   │
│  │    Injected via docker run -v <mount>               │   │
│  │                                                      │   │
│  │    Default mounts (always added):                   │   │
│  │    - Config dir (codex/claude/copilot/gemini)       │   │
│  │    - Workspace (workdir)                            │   │
│  │    - Artifact staging (/tmp/agents-artifacts)       │   │
│  └────────────────────────────────────────────────────┘   │
│  ┌────────────────────────────────────────────────────┐   │
│  │ 6. Preflight Tab                                    │   │
│  │    QCheckBox: Enable preflight script               │   │
│  │    QPlainTextEdit: Bash script                      │   │
│  │                                                      │   │
│  │    Executed before agent CLI in container           │   │
│  │    See docker/agent_worker.py:232-290               │   │
│  │    [Test Preflight] button runs in test container   │   │
│  └────────────────────────────────────────────────────┘   │
│                                                            │
│  [Save] [Cancel]                                           │
│                                                            │
│  Storage: environments/storage.py::save_environment        │
│  Location: ~/.midoriai/agents-runner/environments/        │
└────────────────────────────────────────────────────────────┘
```

### 3. Settings Screen Flow

```
┌────────────────────────────────────────────────────────────┐
│  Settings Page  (ui/pages/settings.py)                     │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  Agent Settings:                                           │
│  ┌──────────────────────────────────────────────────┐     │
│  │ Default Agent CLI      QComboBox                 │     │
│  │   Options: codex, claude, copilot, gemini        │     │
│  │   Stored in: settings_data["use"]                │     │
│  │                                                   │     │
│  │ Default Shell          QComboBox                 │     │
│  │   Options: bash, sh                              │     │
│  │   Stored in: settings_data["shell"]              │     │
│  │                                                   │     │
│  │ Interactive command args (per agent)             │     │
│  │   - codex:    --sandbox danger-full-access       │     │
│  │   - claude:   --add-dir /home/midori-ai/workspace│     │
│  │   - copilot:  --allow-all-tools --add-dir ...    │     │
│  │   - gemini:   --include-directories ...          │     │
│  └──────────────────────────────────────────────────┘     │
│                                                            │
│  Capacity:                                                 │
│  ┌──────────────────────────────────────────────────┐     │
│  │ Max concurrent agents    QLineEdit (int)         │     │
│  │   -1 = unlimited                                 │     │
│  │   Checked by: main_window_capacity.py:28-32      │     │
│  └──────────────────────────────────────────────────┘     │
│                                                            │
│  Paths:                                                    │
│  ┌──────────────────────────────────────────────────┐     │
│  │ Host Workdir           QLineEdit + Browse        │     │
│  │ Host Codex Dir         QLineEdit + Browse        │     │
│  │ Host Claude Dir        QLineEdit + Browse        │     │
│  │ Host Copilot Dir       QLineEdit + Browse        │     │
│  │ Host Gemini Dir        QLineEdit + Browse        │     │
│  └──────────────────────────────────────────────────┘     │
│                                                            │
│  Preflight:                                                │
│  ┌──────────────────────────────────────────────────┐     │
│  │ Enable global preflight    QCheckBox             │     │
│  │ Preflight script           QPlainTextEdit        │     │
│  │ [Test Preflight]           QPushButton           │     │
│  └──────────────────────────────────────────────────┘     │
│                                                            │
│  Experimental:                                             │
│  ┌──────────────────────────────────────────────────┐     │
│  │ Append PixelArch context   QCheckBox             │     │
│  │   (adds prompts/pixelarch_environment.md)        │     │
│  │                                                   │     │
│  │ Headless desktop           QCheckBox             │     │
│  │   (enables noVNC for GUI apps in container)      │     │
│  └──────────────────────────────────────────────────┘     │
│                                                            │
│  [Save]  [Cancel]                                          │
│                                                            │
│  Storage: persistence.py::save_state                       │
│  Location: ~/.midoriai/agents-runner/state.json           │
│            (settings_data dict)                            │
└────────────────────────────────────────────────────────────┘
```

---

## Key Integration Points

### 1. New Task Prompt Editor Widget (Spellcheck Integration Target)

**Location:** `agents_runner/ui/pages/new_task.py:86`

```python
self._prompt = QPlainTextEdit()
self._prompt.setPlaceholderText("Describe what you want the agent to do…")
self._prompt.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
self._prompt.setTabChangesFocus(True)
```

**Integration Strategy for Spellcheck:**
1. Replace `QPlainTextEdit` with custom subclass or set spell checker
2. PySide6 does not have built-in spell checking
3. Options:
   - Use `QSyntaxHighlighter` subclass to underline misspelled words
   - Integrate with external spell checker (enchant, aspell)
   - Use Qt WebEngine with contentEditable + browser spellcheck
4. Current widget is simple, no custom painting/events

**Related Code:**
- Widget accessed via `self._prompt.toPlainText()` at lines 246, 311
- Value passed to `sanitize_prompt()` before use (prompt_sanitizer.py:11)

### 2. Mount Definition and Container Injection

**Mount Definition:** `agents_runner/ui/pages/environments.py:145-158` (Mounts tab)
- User enters mounts as text in QPlainTextEdit
- Format: `/host/path:/container/path[:ro|rw]`
- Parsed by `parse_mounts_text()` in `environments/parse.py:43-67`
- Stored in `Environment.extra_mounts: list[str]`

**Mount Injection:** `agents_runner/docker/agent_worker.py:338-363`
```python
extra_mount_args: list[str] = []
for mount in self._config.extra_mounts or []:
    m = str(mount).strip()
    if not m:
        continue
    extra_mount_args.extend(["-v", m])
for mount in config_extra_mounts:  # From additional_config_mounts()
    m = str(mount).strip()
    if not m:
        continue
    extra_mount_args.extend(["-v", m])

args = [
    "run",
    ...
    "-v", f"{self._config.host_codex_dir}:{config_container_dir}",
    "-v", f"{host_mount}:{self._config.container_workdir}",
    "-v", f"{artifacts_staging_dir}:/tmp/agents-artifacts",
    *extra_mount_args,
    *preflight_mounts,
    ...
]
```

**Mount Resolution:**
- Workspace mount: `docker/utils.py::_resolve_workspace_mount()` (lines 8-40)
  - Walks up directory tree to find git root if available
  - Returns (host_mount, container_cwd) tuple
- Additional config mounts: `agent_cli.py::additional_config_mounts()` (lines 28-43)
  - Claude: Mounts `~/.claude.json` if exists

### 3. Artifact Collection & Encryption

**Collection Flow:**

1. **Staging Directory Created:** `agent_worker.py:100-113`
   ```python
   artifacts_staging_dir = (
       Path.home() / ".midoriai" / "agents-runner" / "artifacts" 
       / self._config.task_id / "staging"
   )
   artifacts_staging_dir.mkdir(parents=True, exist_ok=True)
   ```

2. **Mounted to Container:** `agent_worker.py:361`
   ```python
   "-v", f"{artifacts_staging_dir}:/tmp/agents-artifacts",
   ```

3. **Agent Writes Files:** Agent CLIs can write to `/tmp/agents-artifacts/` in container

4. **Post-Run Collection:** `agent_worker.py:472-487`
   ```python
   self._collected_artifacts = collect_artifacts_from_container(
       self._container_id, task_dict, self._config.environment_id
   )
   ```

5. **Encryption:** `artifacts.py::collect_artifacts_from_container()` (lines 257-328)
   - Reads files from staging directory
   - Encrypts each with Fernet (key = sha256(task_id + env_name))
   - Saves to `~/.midoriai/agents-runner/artifacts/{task_id}/{uuid}.enc`
   - Creates `{uuid}.meta` JSON file
   - Deletes staging files

**Key Functions:**
- `get_artifact_key()` - artifacts.py:34-58 - Derives encryption key
- `encrypt_artifact()` - artifacts.py:68-130 - Encrypts single file
- `decrypt_artifact()` - artifacts.py:133-199 - Decrypts single file
- `list_artifacts()` - artifacts.py:202-254 - Lists encrypted artifacts

**Artifact Viewing:** `ui/pages/artifacts_tab.py:7-301`
- Lists artifacts with decrypt-on-demand
- Preview support for text/images
- Download decrypted files

### 4. GitHub PR Metadata JSON Creation/Mount/Usage

**PR Metadata System** (Currently Copilot-Only):

**Enable Location:** `ui/pages/environments.py:167-175, 403-406`
```python
self._gh_pr_metadata_enabled = QCheckBox("PR metadata (Copilot)")
# Only enabled when gh_management_mode == "github"
```

**File Creation:** `main_window_tasks_agent.py:253-285`
```python
if (
    env
    and gh_mode == GH_MANAGEMENT_GITHUB
    and bool(getattr(env, "gh_pr_metadata_enabled", False))
):
    host_path = pr_metadata_host_path(
        os.path.dirname(self._state_path), task_id
    )  # ~/.midoriai/agents-runner/pr-metadata/pr-metadata-{task_id}.json
    container_path = pr_metadata_container_path(task_id)  # /tmp/codex-pr-metadata-{task_id}.json
    
    ensure_pr_metadata_file(host_path, task_id=task_id)
    
    extra_mounts_for_task.append(f"{host_path}:{container_path}:rw")
    env_vars_for_task.setdefault("CODEX_PR_METADATA_PATH", container_path)
    runner_prompt = f"{runner_prompt}{pr_metadata_prompt_instructions(container_path)}"
```

**File Structure:** `pr_metadata.py:29-42`
```json
{
  "version": 1,
  "task_id": "abc123",
  "title": "",
  "body": ""
}
```

**Prompt Instructions:** `prompts/pr_metadata.md`
- Instructs agent to populate title/body fields
- Agent writes to /tmp/codex-pr-metadata-{task_id}.json

**PR Creation:** `main_window_tasks_interactive_finalize.py:110-155`
```python
pr_metadata_path = task.gh_pr_metadata_path
if pr_metadata_path and os.path.exists(pr_metadata_path):
    meta = load_pr_metadata(pr_metadata_path)
    title = normalize_pr_title(meta.title, fallback=task.prompt)
    body = meta.body or ""
else:
    title = normalize_pr_title(task.prompt, fallback="Task")
    body = ""

# Call gh CLI to create PR
```

**NOTE:** System is disabled for non-Copilot agents (checkbox label hardcoded "Copilot")

### 5. Git Locked vs Folder Locked Environments

**Distinction Mechanism:**

**Environment Model:** `environments/model.py:82-84`
```python
gh_management_mode: str = GH_MANAGEMENT_NONE  # "none" | "local" | "github"
gh_management_target: str = ""
gh_management_locked: bool = False
```

**Modes:**
- `GH_MANAGEMENT_NONE` ("none"): No workspace management
- `GH_MANAGEMENT_LOCAL` ("local"): Lock to local folder (folder locked)
- `GH_MANAGEMENT_GITHUB` ("github"): Lock to GitHub repo (git locked)

**Creation Flow:** `ui/pages/environments_actions.py:86-95`
```python
workspace_labels = ["Lock to local folder", "Lock to GitHub repo (clone)"]
selected_label, ok = QInputDialog.getItem(
    self, "Workspace", "Workspace type", workspace_labels, 0, False
)

if selected_label == "Lock to local folder":
    gh_management_mode = GH_MANAGEMENT_LOCAL
else:
    gh_management_mode = GH_MANAGEMENT_GITHUB
```

**Behavior Differences:**

| Aspect | Folder Locked (LOCAL) | Git Locked (GITHUB) |
|--------|----------------------|---------------------|
| **Mode** | GH_MANAGEMENT_LOCAL | GH_MANAGEMENT_GITHUB |
| **Target** | File path `/path/to/folder` | Repo spec `owner/repo` |
| **Clone** | No clone, direct mount | Clones to temp workspace |
| **Workspace Path** | Uses target directly | `~/.midoriai/agents-runner/workspaces/{env_id}/{task_id}` |
| **Branch UI** | No base branch selector | Base branch selector shown (line 306) |
| **Git Ops** | None | Creates task branch, commits, PR |
| **Cleanup** | None | Deletes workspace dir after task |
| **Locked** | Yes (cannot change target) | Yes (cannot change target) |

**Detection in New Task:** `ui/pages/new_task.py:306-308, 393-395`
```python
self._run_interactive.set_menu(
    self._run_interactive_menu
    if (env_id and env_id in self._gh_locked_envs)
    else None
)
```
- `_gh_locked_envs` set contains env IDs with `gh_management_mode == GH_MANAGEMENT_GITHUB`
- Used to show/hide base branch selector and interactive menu

**GitHub Clone Logic:** `gh_management.py::prepare_github_repo_for_task()` (lines 63-131)
- Only invoked when `gh_mode == GH_MANAGEMENT_GITHUB`
- Calls `gh/repo_clone.py::ensure_github_clone()`
- Creates task branch via `gh/task_plan.py::plan_repo_task()`

---

## Current Agent System

### Agent Launch/Management

**Agent Selection UI:** Exists but not used in execution
- `ui/pages/environments_agents.py` - Full UI for configuring agent priority/fallbacks
- `environments/model.py:48-66` - AgentInstance, AgentSelection dataclasses
- Stored in `Environment.agent_selection: AgentSelection | None`

**Actual Agent Used:** Settings-level fallback
- `main_window_tasks_agent.py:154-165`
  ```python
  agent_cli = "codex"
  if env and env.agent_selection:
      # TODO: Implement agent selection logic
      # For now, always use settings-level agent
      pass
  
  agent_cli = normalize_agent(self._settings_data.get("use", "codex"))
  ```

**Agent CLI Invocation:** `agent_cli.py::build_noninteractive_cmd()` (lines 58-123)
- Codex: `codex exec --sandbox danger-full-access [--skip-git-repo-check] <prompt>`
- Claude: `claude --print --output-format text --permission-mode bypassPermissions --add-dir <workdir> <prompt>`
- Copilot: `copilot --allow-all-tools --allow-all-paths --add-dir <workdir> -p <prompt>`
- Gemini: `gemini --no-sandbox --approval-mode yolo --include-directories <workdir> <prompt>`

**Container Execution:** `docker/agent_worker.py::run()` (lines 96-504)
- Single-shot execution, no retry on failure
- Logs streamed via `docker logs -f`
- Exit code determines success/failure

### Current Retry/Fallback Mechanisms

**Result: NONE IMPLEMENTED**

**Searched for:**
- `retry`, `fallback`, `rate.*limit` patterns
- Agent fallback infrastructure exists in data model but unused

**Agent Selection System:**
- **UI exists:** `environments_agents.py` - Full table for priority/fallbacks
- **Data model exists:** `AgentSelection` with `agent_fallbacks: dict[str, str]`
- **Selection modes defined:** "round-robin" (stored in model)
- **NOT IMPLEMENTED IN EXECUTION:** `main_window_tasks_agent.py:154-165` - TODO comment

**Error Handling:**
- Container failures: Exit code captured, task marked "failed"
- No automatic retry
- No fallback to alternate agent
- No rate-limit detection/backoff

**Capacity Management:**
- `main_window_capacity.py` - Queues tasks if max_agents_running exceeded
- Tasks remain queued until capacity available
- No timeout, no retry, no failure

### Current Rate-Limit Handling

**Result: NONE IMPLEMENTED**

No rate-limit detection or handling exists. Agents that hit rate limits will:
1. Likely return non-zero exit code
2. Task marked as "failed"
3. User must manually retry

**No mechanisms for:**
- Detecting rate limit errors in logs
- Exponential backoff
- Queue delay based on rate limit
- Agent switching on rate limit

---

## Technical Debt & Architectural Issues

### 1. Files Exceeding Hard Limit (600 lines)

**None currently exceed 600 lines.** 6 files exceed 500 lines (soft limit):

| File | Lines | Issue |
|------|-------|-------|
| `docker/agent_worker.py` | 504 | Monolithic run() method (lines 96-504), needs decomposition |
| `ui/pages/task_details.py` | 503 | Complex tab management, could split tabs into separate files |
| `ui/main_window_settings.py` | 512 | Large settings form, consider splitting into sections |
| `ui/pages/environments_agents.py` | 529 | Agent table UI, reasonable for complex widget |
| `ui/main_window_tasks_interactive_docker.py` | 596 | Docker terminal launch, needs refactoring |
| `persistence.py` | 448 | State serialization, approaching limit |

### 2. MainWindow Mixin Explosion

**Problem:** MainWindow uses 11 mixins, spreading logic across files

```python
class MainWindow(
    QMainWindow,
    _MainWindowCapacityMixin,           # 44 lines
    _MainWindowNavigationMixin,         # 130 lines
    _MainWindowSettingsMixin,           # 512 lines
    _MainWindowEnvironmentMixin,        # 312 lines
    _MainWindowDashboardMixin,          # 68 lines
    _MainWindowTasksAgentMixin,         # 355 lines
    _MainWindowTasksInteractiveMixin,   # 288 lines
    _MainWindowTasksInteractiveFinalizeMixin,  # 196 lines
    _MainWindowPreflightMixin,          # 249 lines
    _MainWindowTaskReviewMixin,         # 85 lines
    _MainWindowTaskEventsMixin,         # 401 lines
    _MainWindowPersistenceMixin,        # 174 lines
):
```

**Issues:**
- Hard to follow control flow across 12 files
- Shared state via `self._*` attributes across mixins
- Tight coupling between mixins
- Difficult to test in isolation

**Recommendation:** Consider coordinator pattern or service layer

### 3. Agent Selection System Incomplete

**Problem:** Full UI and data model for agent selection/fallbacks, but not implemented

**Evidence:**
- `environments_agents.py:529` lines - Complete UI for agent priority/fallbacks
- `AgentSelection` dataclass with selection_mode, fallbacks
- `main_window_tasks_agent.py:154-165` - TODO comment, always uses settings agent

**Impact:**
- Dead code in UI
- User confusion (UI suggests feature exists)
- Technical debt for future implementation

**Recommendation:** Either implement or remove UI

### 4. PR Metadata Hardcoded to Copilot

**Problem:** PR metadata system only enabled for Copilot

**Evidence:**
- `environments.py:168` - Checkbox label: "PR metadata (Copilot)"
- `main_window_tasks_agent.py:264` - Check `gh_pr_metadata_enabled`
- No agent-specific logic, should work for all

**Impact:**
- Feature artificially limited
- Codex, Claude, Gemini could benefit from PR metadata
- Copy-paste code needed to add support for other agents

**Recommendation:** Remove Copilot restriction, make agent-agnostic

### 5. No Retry/Fallback/Rate-Limit Handling

**Problem:** Agents fail permanently on first error

**Missing:**
- Retry with exponential backoff
- Fallback to alternate agent (UI exists!)
- Rate-limit detection/handling
- Error classification (retryable vs fatal)

**Impact:**
- Poor user experience
- Manual intervention required for transient failures
- Rate limits cause permanent failures

**Recommendation:** HIGH PRIORITY for refactor

### 6. Docker Worker Monolith

**Problem:** `docker/agent_worker.py::run()` is 408 lines (lines 96-504)

**Responsibilities:**
- GitHub clone orchestration
- Image pulling
- Mount building (5 types)
- Command construction
- Preflight script handling
- Desktop setup
- Container launch
- Log streaming
- Artifact collection
- Cleanup

**Recommendation:** Split into:
- `GitHubPreparer` - Clone/branch setup
- `MountBuilder` - Mount list construction
- `CommandBuilder` - Agent CLI args
- `ContainerLauncher` - Docker run
- `LogStreamer` - Log collection
- `ArtifactCollector` - Post-run artifacts

### 7. State Persistence Fragility

**Problem:** `persistence.py:448` lines - Complex serialization logic

**Issues:**
- Version mismatch handling replaces state file
- Large state file can cause UI lag on save
- No incremental persistence
- No backup strategy beyond .bak files

**Recommendation:** Consider SQLite or append-only log

### 8. Terminal Detection Fragility

**Problem:** `terminal_apps.py:241` lines - Hardcoded terminal app detection

**Current approach:**
- Checks for specific terminal binaries
- Platform-specific heuristics
- May miss user-installed terminals

**Recommendation:** User-configurable terminal list

### 9. No Logging Infrastructure

**Problem:** Print statements instead of structured logging

**Evidence:**
- `logger = logging.getLogger(__name__)` in some files (artifacts.py, main_window_tasks_agent.py)
- But most logging via `self._on_log()` callbacks
- No log levels, no filtering, no log file

**Recommendation:** Unified logging system with levels/files

### 10. No Tests

**Problem:** No test infrastructure found

**Impact:**
- Refactoring risk
- Regression risk
- Hard to validate changes

**Recommendation:** Add pytest infrastructure, start with critical paths

---

## Recommended Module Boundaries for Refactor

### Proposed Structure

```
agents_runner/
├── core/                           # Core domain logic
│   ├── agent/                      # Agent management
│   │   ├── selector.py             # Agent selection/fallback (NEW)
│   │   ├── retry.py                # Retry/backoff logic (NEW)
│   │   ├── rate_limit.py           # Rate limit detection (NEW)
│   │   └── config.py               # Agent config (move from agent_cli.py)
│   ├── task/                       # Task lifecycle
│   │   ├── model.py                # Task dataclass
│   │   ├── scheduler.py            # Capacity/queuing (from capacity.py)
│   │   └── state_machine.py        # Task state transitions (NEW)
│   ├── environment/                # Environment management
│   │   └── (keep existing)
│   └── workspace/                  # Workspace management
│       ├── local.py                # Local folder workspace
│       └── github.py               # GitHub workspace (from gh/)
│
├── execution/                      # Docker execution
│   ├── docker/
│   │   ├── launcher.py             # Split from agent_worker.py
│   │   ├── mounts.py               # Mount building
│   │   ├── preflight.py            # Preflight handling
│   │   └── logs.py                 # Log streaming
│   └── artifacts/                  # Artifact handling
│       └── (keep existing)
│
├── services/                       # Application services
│   ├── task_service.py             # Task CRUD (NEW, from mixins)
│   ├── environment_service.py      # Environment CRUD (NEW, from mixins)
│   └── github_service.py           # GitHub operations (from gh/)
│
├── ui/                             # UI layer
│   ├── controllers/                # Page controllers (NEW)
│   │   ├── dashboard_controller.py
│   │   ├── new_task_controller.py
│   │   └── task_details_controller.py
│   ├── pages/                      # View components
│   │   └── (keep existing, simplify)
│   └── main_window.py              # Simplified coordinator
│
├── infrastructure/                 # Infrastructure concerns
│   ├── persistence/
│   │   ├── state_store.py          # Split from persistence.py
│   │   └── migrations.py           # Version migrations (NEW)
│   ├── logging/                    # Logging (NEW)
│   └── config/                     # App configuration (NEW)
│
└── utils/                          # Shared utilities
    └── (existing utilities)
```

### Key Principles

1. **Separation of Concerns**
   - Core domain logic separate from UI
   - Infrastructure separate from domain
   - Services as coordination layer

2. **Dependency Direction**
   - UI → Services → Core
   - No circular dependencies
   - Core has no UI knowledge

3. **Testability**
   - Pure functions where possible
   - Inject dependencies
   - Mock external systems (Docker, Git)

4. **File Size**
   - Target: 200 lines average, 300 soft limit, 600 hard limit
   - Split large classes into collaborators

### Migration Strategy

**Phase 1: Extract Services (No UI Changes)**
1. Create `services/task_service.py` - Extract from task mixins
2. Create `services/environment_service.py` - Extract from environment mixin
3. MainWindow delegates to services instead of inline logic

**Phase 2: Split Agent Worker**
1. Extract `execution/docker/mounts.py` from agent_worker.py
2. Extract `execution/docker/launcher.py` from agent_worker.py
3. Extract `execution/docker/logs.py` from agent_worker.py
4. Agent worker becomes thin orchestrator

**Phase 3: Implement Agent Selection**
1. Create `core/agent/selector.py` - Implement selection logic
2. Create `core/agent/retry.py` - Add retry/backoff
3. Create `core/agent/rate_limit.py` - Add rate limit detection
4. Wire into task execution flow

**Phase 4: Refactor Persistence**
1. Extract `infrastructure/persistence/state_store.py`
2. Add incremental save
3. Add migrations for version changes

**Phase 5: Add Tests**
1. Unit tests for core logic
2. Integration tests for services
3. UI tests for critical paths

---

## Current Limitations & Pain Points

### For Users

1. **No Retry on Failure** - Transient errors require manual retry
2. **No Agent Fallback** - Rate limits/failures are permanent
3. **Limited PR Metadata** - Only works for Copilot
4. **No Spellcheck** - Typos in prompts common
5. **Cryptic Errors** - Docker/Git errors not user-friendly

### For Developers

1. **Mixin Hell** - MainWindow logic scattered across 12 files
2. **No Tests** - Refactoring is risky
3. **Monolithic Worker** - agent_worker.py hard to modify
4. **Dead Code** - Agent selection UI implemented but unused
5. **Tight Coupling** - Hard to change one part without affecting others

### For Operations

1. **No Structured Logs** - Debugging requires reading UI logs
2. **No Metrics** - Can't measure performance/reliability
3. **No Error Tracking** - Failures not aggregated
4. **State File Fragility** - Corruption requires manual fix

---

## Summary of Key Findings for Refactor

### Must Address

1. **Implement Agent Selection/Retry** - HIGH PRIORITY
   - Agent selection UI exists but not wired up
   - No retry/fallback/rate-limit handling
   - Critical for production use

2. **Split agent_worker.py** - MEDIUM PRIORITY
   - 504 lines, monolithic run() method
   - Hard to test, hard to modify
   - Split into launcher, mounts, logs, artifacts

3. **Extract Services from Mixins** - MEDIUM PRIORITY
   - 11 mixins make MainWindow hard to follow
   - Create task_service, environment_service
   - Simplify MainWindow to coordinator role

### Should Address

4. **Remove PR Metadata Copilot Restriction** - LOW PRIORITY
   - Feature works for all agents
   - Remove hardcoded "Copilot" label
   - Enable for codex, claude, gemini

5. **Add Spellcheck to Prompt Editor** - LOW PRIORITY
   - Target: `ui/pages/new_task.py:86` (QPlainTextEdit)
   - Use QSyntaxHighlighter + external spell checker
   - Or switch to QWebEngineView with contentEditable

6. **Add Logging Infrastructure** - LOW PRIORITY
   - Standardize on Python logging module
   - Add log levels, log file output
   - Remove ad-hoc print/callback logging

### Can Defer

7. **Refactor Persistence** - Future work
8. **Add Tests** - Start with new code, backfill gradually
9. **Terminal Detection** - User complaints needed first

---

## Appendix: File Inventory by Module

### Core Application (3 files, 521 lines)
- `app.py` (62) - App initialization
- `main.py` (11) - Entry point
- `persistence.py` (448) - State persistence

### UI Layer (38 files, 6,827 lines)
- `ui/main_window*.py` (12 files, 2,623 lines)
- `ui/pages/*.py` (10 files, 3,431 lines)
- `ui/*.py` (6 files, 773 lines)
- `widgets/*.py` (10 files, N/A lines)
- `style/*.py` (6 files, N/A lines)

### Agent Execution (11 files, 1,283 lines)
- `docker/*.py` (8 files, 1,067 lines)
- `agent_cli.py` (127)
- `docker_runner.py` (9)
- `docker_platform.py` (60)
- `terminal_apps.py` (241)

### Environment Management (8 files, 1,051 lines)
- `environments/*.py` (8 files, 1,051 lines)

### GitHub Integration (7 files, 891 lines)
- `gh/*.py` (6 files, 761 lines)
- `gh_management.py` (130)

### Artifacts (1 file, 328 lines)
- `artifacts.py` (328)

### Prompts (8 files, ~300 lines)
- `prompts/*.md` (7 files)
- `prompts/loader.py` (102)

### Utilities (5 files, 251 lines)
- `pr_metadata.py` (93)
- `github_token.py` (49)
- `log_format.py` (64)
- `prompt_sanitizer.py` (11)
- `agent_display.py` (38)

---

**End of Audit Report**

Generated: 2025-01-07  
Auditor: Auditor Mode (AI)  
Codebase Version: Current HEAD  
Lines Analyzed: 15,268  
Files Analyzed: 101
