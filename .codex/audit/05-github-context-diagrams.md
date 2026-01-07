# GitHub Context System - Visual Diagrams

**Related:** `05-github-context-design.md` (full design), `05-github-context-quick-ref.md` (summary)

---

## Diagram 1: Current vs Proposed State

### Current State (Before Task 4)

```
┌─────────────────────────────────────────────────────────┐
│              GITHUB PR METADATA (v1)                    │
│                                                         │
│  Scope: Git-locked environments only                   │
│  UI: "PR metadata (Copilot)" checkbox                  │
│  Field: gh_pr_metadata_enabled                         │
│                                                         │
│  ┌─────────────┐         ┌──────────────┐             │
│  │ Git Locked  │ ✅ YES  │ Folder Locked│ ❌ NO       │
│  │  (GITHUB)   │ ──────> │   (LOCAL)    │             │
│  └─────────────┘         └──────────────┘             │
│                                                         │
│  File: /tmp/codex-pr-metadata-{task}.json              │
│  Env Var: CODEX_PR_METADATA_PATH                       │
│  Schema: { task_id, title, body }                      │
└─────────────────────────────────────────────────────────┘
```

### Proposed State (After Task 4)

```
┌─────────────────────────────────────────────────────────┐
│              GITHUB CONTEXT (v2)                        │
│                                                         │
│  Scope: Git-locked + folder-locked git repos           │
│  UI: "Provide GitHub context" checkbox                 │
│  Field: gh_context_enabled                             │
│                                                         │
│  ┌─────────────┐         ┌──────────────┐             │
│  │ Git Locked  │ ✅ YES  │ Folder Locked│ ⚠️ IF GIT   │
│  │  (GITHUB)   │ ──────> │   (LOCAL)    │             │
│  └─────────────┘         └──────────────┘             │
│                                ↓                        │
│                      ┌──────────────────┐              │
│                      │  Git Detection   │              │
│                      │  • is git repo?  │              │
│                      │  • extract URL   │              │
│                      │  • extract branch│              │
│                      │  • extract commit│              │
│                      └──────────────────┘              │
│                                                         │
│  File: /tmp/github-context-{task}.json                 │
│  Env Var: GITHUB_CONTEXT_PATH                          │
│  Schema: { task_id, github: {...}, title, body }       │
└─────────────────────────────────────────────────────────┘
```

---

## Diagram 2: Environment Type Decision Tree

```
                    ┌────────────────────┐
                    │  User Creates or   │
                    │  Edits Environment │
                    └─────────┬──────────┘
                              │
                              ↓
                    ┌────────────────────┐
                    │ What workspace     │
                    │ type selected?     │
                    └─────────┬──────────┘
                              │
             ┌────────────────┼────────────────┐
             │                │                │
             ↓                ↓                ↓
    ┌────────────────┐ ┌─────────────┐ ┌─────────────┐
    │  Lock to       │ │  Lock to    │ │   No lock   │
    │  GitHub repo   │ │  local      │ │             │
    │  (clone)       │ │  folder     │ │             │
    └───────┬────────┘ └──────┬──────┘ └──────┬──────┘
            │                 │               │
            ↓                 ↓               ↓
    gh_management_mode   gh_management   gh_management
    = "github"           _mode = "local" _mode = "none"
            │                 │               │
            ↓                 ↓               ↓
    ┌───────────────┐   ┌───────────────┐   ┌──────────────┐
    │ GitHub        │   │ Git detection │   │ GitHub       │
    │ context:      │   │ on folder:    │   │ context:     │
    │ ✅ ALWAYS     │   │               │   │ ❌ NEVER     │
    │ AVAILABLE     │   │ is_git_repo() │   │ AVAILABLE    │
    │               │   └───────┬───────┘   │              │
    │ Checkbox:     │           │           │ Checkbox:    │
    │ ENABLED       │   ┌───────┴───────┐   │ DISABLED     │
    └───────────────┘   │               │   │ (grayed out) │
                        ↓               ↓   └──────────────┘
                  ┌──────────┐   ┌──────────┐
                  │ IS GIT   │   │ NOT GIT  │
                  │ REPO     │   │ REPO     │
                  └────┬─────┘   └────┬─────┘
                       │              │
                       ↓              ↓
                  ┌──────────┐   ┌──────────┐
                  │ Checkbox:│   │ Checkbox:│
                  │ ENABLED  │   │ DISABLED │
                  └──────────┘   └──────────┘
```

---

## Diagram 3: Task Start Flow - Git Locked Environment

```
┌──────────────────────────────────────────────────────────────┐
│                    USER CLICKS "RUN AGENT"                   │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           ↓
              ┌────────────────────────┐
              │ Check environment:     │
              │ gh_context_enabled?    │
              └────────┬───────────────┘
                       │
                ┌──────┴──────┐
                │             │
                ↓             ↓
            ┌─────┐       ┌─────┐
            │ NO  │       │ YES │
            └──┬──┘       └──┬──┘
               │             │
               │             ↓
               │   ┌─────────────────────┐
               │   │ Environment type?   │
               │   │ gh_management_mode  │
               │   └──────────┬──────────┘
               │              │
               │              ↓
               │        GH_MANAGEMENT_GITHUB
               │              │
               │              ↓
               │   ┌─────────────────────────────┐
               │   │ Create empty metadata file  │
               │   │ - version: 2                │
               │   │ - task_id: abc123           │
               │   │ - github: null (for now)    │
               │   │ - title: ""                 │
               │   │ - body: ""                  │
               │   └──────────┬──────────────────┘
               │              │
               │              ↓
               │   ┌─────────────────────────────┐
               │   │ Mount into container:       │
               │   │ Host: ~/.midoriai/.../      │
               │   │   github-context-{task}.json│
               │   │ Container: /tmp/            │
               │   │   github-context-{task}.json│
               │   └──────────┬──────────────────┘
               │              │
               │              ↓
               │   ┌─────────────────────────────┐
               │   │ Set env var:                │
               │   │ GITHUB_CONTEXT_PATH=/tmp/...│
               │   └──────────┬──────────────────┘
               │              │
               │              ↓
               │   ┌─────────────────────────────┐
               │   │ Append GitHub context       │
               │   │ prompt instructions         │
               │   └──────────┬──────────────────┘
               │              │
               └──────────────┴────────────────────┐
                                                   │
                                                   ↓
                                        ┌──────────────────┐
                                        │ START TASK       │
                                        │ - Launch container│
                                        │ - Clone repo     │
                                        │ - Create branch  │
                                        └────────┬─────────┘
                                                 │
                                                 ↓
                                        ┌──────────────────────┐
                                        │ After clone:         │
                                        │ Populate github obj  │
                                        │ - repo_url           │
                                        │ - base_branch        │
                                        │ - task_branch        │
                                        │ - head_commit        │
                                        └────────┬─────────────┘
                                                 │
                                                 ↓
                                        ┌──────────────────────┐
                                        │ Agent runs with      │
                                        │ full GitHub context  │
                                        └──────────────────────┘
```

---

## Diagram 4: Task Start Flow - Folder Locked Environment

```
┌──────────────────────────────────────────────────────────────┐
│                    USER CLICKS "RUN AGENT"                   │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           ↓
              ┌────────────────────────┐
              │ Check environment:     │
              │ gh_context_enabled?    │
              └────────┬───────────────┘
                       │
                ┌──────┴──────┐
                │             │
                ↓             ↓
            ┌─────┐       ┌─────┐
            │ NO  │       │ YES │
            └──┬──┘       └──┬──┘
               │             │
               │             ↓
               │   ┌─────────────────────┐
               │   │ Environment type?   │
               │   │ gh_management_mode  │
               │   └──────────┬──────────┘
               │              │
               │              ↓
               │        GH_MANAGEMENT_LOCAL
               │              │
               │              ↓
               │   ┌─────────────────────────────┐
               │   │ Detect git context:         │
               │   │ - is_git_repo(folder)?      │
               │   └──────────┬──────────────────┘
               │              │
               │       ┌──────┴──────┐
               │       │             │
               │       ↓             ↓
               │   ┌──────┐      ┌──────┐
               │   │ YES  │      │  NO  │
               │   └───┬──┘      └───┬──┘
               │       │             │
               │       │             ↓
               │       │   ┌─────────────────────┐
               │       │   │ Log: not a git repo │
               │       │   │ Skip GitHub context │
               │       │   └──────────┬──────────┘
               │       │              │
               │       ↓              │
               │   ┌─────────────────────────────┐
               │   │ Extract git context:        │
               │   │ - git_repo_root()           │
               │   │ - git_current_branch()      │
               │   │ - git_head_commit()         │
               │   │ - git_remote_url("origin")  │
               │   │ - parse_github_url()        │
               │   └──────────┬──────────────────┘
               │              │
               │              ↓
               │   ┌─────────────────────────────┐
               │   │ Create metadata file with   │
               │   │ full github object:         │
               │   │ - version: 2                │
               │   │ - task_id: abc123           │
               │   │ - github: {                 │
               │   │     repo_url, repo_owner,   │
               │   │     repo_name, base_branch, │
               │   │     task_branch: null,      │
               │   │     head_commit             │
               │   │   }                         │
               │   │ - title: ""                 │
               │   │ - body: ""                  │
               │   └──────────┬──────────────────┘
               │              │
               │              ↓
               │   ┌─────────────────────────────┐
               │   │ Mount into container        │
               │   └──────────┬──────────────────┘
               │              │
               │              ↓
               │   ┌─────────────────────────────┐
               │   │ Set env var + append prompt │
               │   └──────────┬──────────────────┘
               │              │
               └──────────────┴────────────────────┐
                                                   │
                                                   ↓
                                        ┌──────────────────┐
                                        │ START TASK       │
                                        │ - Mount folder   │
                                        │   (no clone)     │
                                        └────────┬─────────┘
                                                 │
                                                 ↓
                                        ┌──────────────────────┐
                                        │ Agent runs with      │
                                        │ GitHub context       │
                                        │ (context pre-filled) │
                                        └──────────────────────┘
```

---

## Diagram 5: Git Detection Algorithm

```
┌─────────────────────────────────────────────────────┐
│           detect_git_context(folder_path)           │
└──────────────────────┬──────────────────────────────┘
                       │
                       ↓
        ┌──────────────────────────────┐
        │ Step 1: is_git_repo()?       │
        │ git rev-parse --is-inside-   │
        │   work-tree                  │
        └──────────┬───────────────────┘
                   │
            ┌──────┴──────┐
            │             │
            ↓             ↓
        ┌──────┐      ┌──────┐
        │ YES  │      │  NO  │
        └───┬──┘      └───┬──┘
            │             │
            │             ↓
            │         return None
            │
            ↓
        ┌──────────────────────────────┐
        │ Step 2: git_repo_root()      │
        │ git rev-parse --show-toplevel│
        └──────────┬───────────────────┘
                   │
                   ↓
        ┌──────────────────────────────┐
        │ Step 3: git_current_branch() │
        │ git rev-parse --abbrev-ref   │
        │   HEAD                       │
        └──────────┬───────────────────┘
                   │
                   ↓
        ┌──────────────────────────────┐
        │ Step 4: git_head_commit()    │
        │ git rev-parse HEAD           │
        └──────────┬───────────────────┘
                   │
                   ↓
        ┌──────────────────────────────┐
        │ Step 5: git_remote_url()     │
        │ git remote get-url origin    │
        └──────────┬───────────────────┘
                   │
            ┌──────┴──────┐
            │             │
            ↓             ↓
        ┌──────┐      ┌──────┐
        │ HAS  │      │  NO  │
        │REMOTE│      │REMOTE│
        └───┬──┘      └───┬──┘
            │             │
            │             ↓
            │         return None
            │
            ↓
        ┌──────────────────────────────┐
        │ Step 6: parse_github_url()   │
        │ Extract owner/repo from URL  │
        │ - HTTPS: github.com/o/r      │
        │ - SSH: git@github.com:o/r    │
        └──────────┬───────────────────┘
                   │
                   ↓
        ┌──────────────────────────────┐
        │ Return GitContext:           │
        │ - repo_root                  │
        │ - repo_url                   │
        │ - repo_owner (may be None)   │
        │ - repo_name (may be None)    │
        │ - current_branch             │
        │ - head_commit                │
        └──────────────────────────────┘

TIMEOUT: 8 seconds per git operation
ERROR HANDLING: Any failure → return None
CACHING: Result cached per environment
```

---

## Diagram 6: Metadata File Lifecycle

### Git-Locked Environment

```
Task Start
    ↓
┌─────────────────────┐
│ Create empty file:  │
│ {                   │
│   version: 2,       │
│   task_id: "...",   │
│   github: null,     │ ← Empty, will populate after clone
│   title: "",        │
│   body: ""          │
│ }                   │
└──────┬──────────────┘
       │
       ↓
┌─────────────────────┐
│ Mount to container  │
└──────┬──────────────┘
       │
       ↓
┌─────────────────────┐
│ Start container     │
│ Clone repo          │
│ Create branch       │
└──────┬──────────────┘
       │
       ↓
┌─────────────────────┐
│ AFTER CLONE:        │
│ Populate github obj │
│ {                   │
│   github: {         │ ← NOW FILLED
│     repo_url,       │
│     base_branch,    │
│     task_branch,    │
│     head_commit     │
│   }                 │
│ }                   │
└──────┬──────────────┘
       │
       ↓
┌─────────────────────┐
│ Agent executes      │
│ - Reads context     │
│ - Writes title/body │
└──────┬──────────────┘
       │
       ↓
┌─────────────────────┐
│ Task completes      │
│ - title/body set    │
│ - Used for PR       │
└─────────────────────┘
```

### Folder-Locked Environment

```
Task Start
    ↓
┌─────────────────────┐
│ Detect git context  │
└──────┬──────────────┘
       │
       ↓
┌─────────────────────┐
│ Create file with    │
│ FULL context:       │
│ {                   │
│   version: 2,       │
│   task_id: "...",   │
│   github: {         │ ← ALREADY FILLED
│     repo_url,       │
│     base_branch,    │
│     task_branch:null│ ← No task branch
│     head_commit     │
│   },                │
│   title: "",        │
│   body: ""          │
│ }                   │
└──────┬──────────────┘
       │
       ↓
┌─────────────────────┐
│ Mount to container  │
└──────┬──────────────┘
       │
       ↓
┌─────────────────────┐
│ Start container     │
│ Mount folder (no    │
│   clone needed)     │
└──────┬──────────────┘
       │
       ↓
┌─────────────────────┐
│ Agent executes      │
│ - Reads context     │
│ - Writes title/body │
└──────┬──────────────┘
       │
       ↓
┌─────────────────────┐
│ Task completes      │
│ - title/body set    │
│ - NOT used for PR   │ ← User manages git
│   (no PR created)   │
└─────────────────────┘
```

---

## Diagram 7: Gemini Integration

### Current Gemini Command (Without GitHub Context)

```
┌────────────────────────────────────────────────────┐
│ gemini                                             │
│   --no-sandbox                                     │
│   --approval-mode yolo                             │
│   --include-directories /home/midori-ai/workspace  │ ← Only workspace
│   <prompt>                                         │
└────────────────────────────────────────────────────┘

Agent can access:
  ✅ /home/midori-ai/workspace/
  ❌ /tmp/github-context-{task}.json  ← DENIED!
```

### Proposed Gemini Command (With GitHub Context)

```
┌────────────────────────────────────────────────────┐
│ gemini                                             │
│   --no-sandbox                                     │
│   --approval-mode yolo                             │
│   --include-directories /home/midori-ai/workspace  │
│   --include-directories /tmp                       │ ← ADD THIS
│   <prompt>                                         │
└────────────────────────────────────────────────────┘

Agent can access:
  ✅ /home/midori-ai/workspace/
  ✅ /tmp/github-context-{task}.json  ← NOW ALLOWED!
```

### Alternative: Always Include /tmp

```python
if agent == "gemini":
    # Always include /tmp (simpler, no security risk)
    args = [
        "gemini",
        "--no-sandbox",
        "--approval-mode", "yolo",
        "--include-directories", container_workdir,
        "--include-directories", "/tmp",  # Always included
        *extra_args,
    ]
```

**Rationale:**
- `/tmp` contains no persistent user data
- GitHub context file only present when feature enabled
- Simpler code (no conditional logic)
- **RECOMMENDED APPROACH**

---

## Diagram 8: Error Handling Flow

```
┌─────────────────────────────────────────────────────┐
│          GitHub Context Feature Enabled             │
└──────────────────────┬──────────────────────────────┘
                       │
                       ↓
        ┌──────────────────────────┐
        │ Try to detect/create     │
        │ GitHub context           │
        └──────┬───────────────────┘
               │
               ↓
        ┌──────────────┐
        │ Success?     │
        └──┬────────┬──┘
           │        │
       YES │        │ NO
           │        │
           ↓        ↓
    ┌──────────┐   ┌─────────────────────────────┐
    │ Continue │   │ What kind of error?         │
    │ with GH  │   └──────┬──────────────────────┘
    │ context  │          │
    └──────────┘          │
                   ┌──────┴──────┬──────────────┬──────────────┐
                   │             │              │              │
                   ↓             ↓              ↓              ↓
           ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐
           │ Not a git  │ │ Git cmd    │ │ Write      │ │ Parse      │
           │ repo       │ │ failed     │ │ failed     │ │ URL failed │
           └──────┬─────┘ └──────┬─────┘ └──────┬─────┘ └──────┬─────┘
                  │              │              │              │
                  ↓              ↓              ↓              ↓
         ┌────────────────────────────────────────────────────────┐
         │ Log reason:                                            │
         │ - "[gh] folder not a git repo, skipping context"      │
         │ - "[gh] git detection failed: {error}"                │
         │ - "[gh] failed to create context file: {error}"       │
         │ - "[gh] could not parse repo URL"                     │
         └────────────────────────┬───────────────────────────────┘
                                  │
                                  ↓
                      ┌───────────────────────┐
                      │ Continue task WITHOUT │
                      │ GitHub context        │
                      └───────────────────────┘
                                  │
                                  ↓
                      ┌───────────────────────┐
                      │ Task executes normally│
                      │ Agent has no GH context│
                      └───────────────────────┘

PRINCIPLE: NEVER FAIL TASK DUE TO GITHUB CONTEXT ERROR
```

---

## Diagram 9: Migration Path

### Existing Environment File (v1)

```json
{
  "env_id": "env-abc123",
  "name": "My Environment",
  "gh_management_mode": "github",
  "gh_pr_metadata_enabled": true,    ← OLD FIELD NAME
  ...
}
```

**Load Process:**

```
┌────────────────────────────────────┐
│ deserialize_environment(data)      │
└────────────┬───────────────────────┘
             │
             ↓
┌────────────────────────────────────┐
│ Check for old field:               │
│ if "gh_pr_metadata_enabled" in data│
└────────────┬───────────────────────┘
             │
             ↓
┌────────────────────────────────────┐
│ Rename field:                      │
│ data["gh_context_enabled"] =       │
│   data.pop("gh_pr_metadata_enabled")│
└────────────┬───────────────────────┘
             │
             ↓
┌────────────────────────────────────┐
│ Continue normal deserialization    │
└────────────────────────────────────┘
```

### Updated Environment File (v2)

```json
{
  "env_id": "env-abc123",
  "name": "My Environment",
  "gh_management_mode": "github",
  "gh_context_enabled": true,        ← NEW FIELD NAME
  ...
}
```

**Result:** Seamless migration, user sees no difference, feature keeps working.

---

## Diagram 10: Cache Strategy

```
┌─────────────────────────────────────────────────────┐
│             Git Context Detection Cache             │
├─────────────────────────────────────────────────────┤
│                                                     │
│  Storage: In-memory dict (MainWindow instance)      │
│  Key: env_id                                        │
│  Value: GitContext | None | False                   │
│    - GitContext: Detection succeeded, context found│
│    - None: Detection succeeded, not a git repo     │
│    - False: Detection failed (error)               │
│                                                     │
│  ┌───────────────────────────────────────────┐     │
│  │ Cache Entry Lifecycle                     │     │
│  └───────────────────────────────────────────┘     │
│                                                     │
│  1. INITIAL STATE                                   │
│     cache = {}                                      │
│                                                     │
│  2. FIRST DETECTION                                 │
│     if env_id not in cache:                         │
│       result = detect_git_context(folder)           │
│       cache[env_id] = result                        │
│                                                     │
│  3. SUBSEQUENT ACCESSES                             │
│     if env_id in cache:                             │
│       return cache[env_id]  # Fast!                 │
│                                                     │
│  4. INVALIDATION EVENTS                             │
│     - User edits environment → delete cache[env_id] │
│     - User changes folder path → detect again       │
│     - App restarts → cache cleared                  │
│                                                     │
└─────────────────────────────────────────────────────┘

Performance Impact:
  First detection: ~100-500ms (git operations)
  Cached access: <1ms (dict lookup)
  Cache hit rate: >95% (most tasks reuse same environment)
```

---

**End of Diagrams**

These diagrams complement the full design document and provide visual references for implementation.

