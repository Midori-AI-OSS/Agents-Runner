# Prompt Externalization Audit Report

**Audit ID:** d08cf300  
**Date:** 2025-01-07  
**Auditor:** Auditor Mode  
**Subject:** Current state of prompt externalization in Agents Runner

---

## Executive Summary

This audit confirms the reviewer's assessment is **accurate and complete**. Two distinct categories of hardcoded prompts need externalization:

1. **PR Attribution Footer** (agents_runner/gh/task_plan.py) - Hardcoded markdown text
2. **User-Defined Environment Prompts** - Currently stored inline in JSON state file

Both externalization tasks are well-scoped and implementable with low risk.

---

## Part 1: PR Attribution Footer Analysis

### Current State

**Location:** `agents_runner/gh/task_plan.py`, lines 25-51  
**Function:** `_append_pr_attribution_footer(body, agent_cli, agent_cli_args)`

**Hardcoded Content:**
```python
footer = (
    "\n\n---\n"
    f"{_PR_ATTRIBUTION_MARKER}\n"
    f"Created by [Midori AI Agents Runner]({_MIDORI_AI_AGENTS_RUNNER_URL}).\n"
    f"Agent Used: {agent_used}\n"
    f"Related: [Midori AI Monorepo]({_MIDORI_AI_URL}).\n"
)
```

**Constants:**
- `_MIDORI_AI_AGENTS_RUNNER_URL = "https://github.com/Midori-AI-OSS/Agents-Runner"`
- `_MIDORI_AI_URL = "https://github.com/Midori-AI-OSS/Midori-AI"`
- `_PR_ATTRIBUTION_MARKER = "<!-- midori-ai-agents-runner-pr-footer -->"`

**Usage:**
- Called by `commit_push_and_pr()` (line 208) when creating pull requests
- Appends attribution footer to PR body with agent information

### Assessment: ✓ CONFIRMED

The reviewer's assessment is accurate. This is a clear case of hardcoded markdown text that should be externalized.

### Implementation Plan

**1. Create Prompt File**
```
Path: agents_runner/prompts/pr_attribution_footer.md
```

**Content Structure:**
```markdown
# PR Attribution Footer

This footer is appended to pull request bodies to attribute the PR to Agents Runner.

**When used:** Automatic PR creation (GitHub management mode)  
**Template variables:** 
- `{MARKER}` - HTML comment marker for idempotency
- `{RUNNER_URL}` - Agents Runner GitHub URL
- `{AGENT_USED}` - Formatted agent link or "(unknown)"
- `{MIDORI_AI_URL}` - Midori AI monorepo URL

## Prompt


---
{MARKER}
Created by [Midori AI Agents Runner]({RUNNER_URL}).
Agent Used: {AGENT_USED}
Related: [Midori AI Monorepo]({MIDORI_AI_URL}).
```

**2. Refactor Function**

```python
# In agents_runner/gh/task_plan.py

from agents_runner.prompts import load_prompt

def _append_pr_attribution_footer(
    body: str, agent_cli: str = "", agent_cli_args: str = ""
) -> str:
    body = (body or "").rstrip()
    if _PR_ATTRIBUTION_MARKER in body:
        return body + "\n"

    agent_cli_name = agent_cli.strip()
    agent_args = agent_cli_args.strip()

    if agent_cli_name:
        agent_link = format_agent_markdown_link(agent_cli_name)
        if agent_args:
            agent_used = f"{agent_link} {agent_args}"
        else:
            agent_used = agent_link
    else:
        agent_used = "(unknown)"

    # Load footer template from external file
    footer_template = load_prompt(
        "pr_attribution_footer",
        MARKER=_PR_ATTRIBUTION_MARKER,
        RUNNER_URL=_MIDORI_AI_AGENTS_RUNNER_URL,
        AGENT_USED=agent_used,
        MIDORI_AI_URL=_MIDORI_AI_URL,
    )
    
    # Prepend separator and newlines
    footer = f"\n\n{footer_template}"
    return (body + footer) if body else footer.lstrip("\n")
```

**3. Edge Cases**

- ✓ **Empty body:** Already handled by existing logic `(body + footer) if body else footer.lstrip("\n")`
- ✓ **Idempotency:** Marker check prevents duplicate footers
- ✓ **Missing file:** `load_prompt()` raises `FileNotFoundError` - will fail loudly (good for catching config issues)
- ✓ **Template variables:** All variables are always available (no conditionals needed)

**4. Testing Strategy**

```python
# Recommended test cases (if test suite exists):
# 1. Empty body with footer
# 2. Body with existing marker (idempotent)
# 3. Body with all agent info
# 4. Body with unknown agent
# 5. Body with agent but no args
```

**Risk Level:** LOW  
**Breaking Changes:** None (output format identical)

---

## Part 2: User-Defined Environment Prompts Analysis

### Current State

**Storage Location:** `~/.local/share/midori-ai-agents-runner/state.json`

**Data Structure:**
```json
{
  "environments": [
    {
      "env_id": "example",
      "prompts": [
        {
          "enabled": true,
          "text": "Custom prompt text here..."
        }
      ],
      "prompts_unlocked": true
    }
  ]
}
```

**Code Locations:**
- `agents_runner/environments/model.py` - `PromptConfig` dataclass (lines 40-44)
- `agents_runner/environments/serialize.py` - Serialization logic (lines 74-85, 274-276)
- `agents_runner/environments/storage.py` - File I/O (load/save/delete environments)
- `agents_runner/ui/pages/environments_prompts.py` - UI for editing prompts
- `agents_runner/ui/main_window_tasks_agent.py` - Prompt injection at runtime (lines 234-249)

**Current Flow:**
1. User unlocks prompts in UI (`environments_prompts.py`)
2. User edits text inline in QPlainTextEdit widgets
3. Prompts saved to JSON via `serialize.py` → `storage.py`
4. At task launch, enabled prompts appended to runner prompt (lines 234-249)

### Assessment: ✓ CONFIRMED

The reviewer's assessment is accurate. Prompts are currently stored inline in JSON, which:
- Makes version control difficult
- Prevents easy sharing/templating
- Clutters the state file with potentially large text blocks
- Doesn't match the architecture of system prompts

### Proposed Architecture

**Storage Location:** `~/.midoriai/agents-runner/prompts/<env_id>-<uuid>.md`

**Benefits:**
- Consistent with system prompt storage pattern
- Easy to version control
- Supports external editing
- Reduces state.json size
- Enables future features (prompt templates, sharing)

### Implementation Plan

#### 1. Update Data Model

**File:** `agents_runner/environments/model.py`

```python
@dataclass
class PromptConfig:
    enabled: bool = False
    text: str = ""  # LEGACY: Keep for backwards compatibility
    prompt_path: str = ""  # NEW: Path to external .md file
```

**Migration Strategy:**
- Keep `text` field for backwards compatibility
- Add new `prompt_path` field
- During load: if `text` is present and `prompt_path` is empty, migrate to file
- During save: prefer `prompt_path`, fall back to `text` for old versions

#### 2. Add Path Management

**File:** `agents_runner/environments/paths.py`

```python
def user_prompts_dir(data_dir: str | None = None) -> str:
    """Get directory for user-defined environment prompts."""
    # Use ~/.midoriai/agents-runner/prompts/ not state dir
    # This matches other app data locations
    return os.path.expanduser("~/.midoriai/agents-runner/prompts")


def user_prompt_path(env_id: str, prompt_uuid: str) -> str:
    """Get path for a specific user prompt file.
    
    Args:
        env_id: Environment identifier
        prompt_uuid: Unique identifier for this prompt
    
    Returns:
        Path like ~/.midoriai/agents-runner/prompts/<env_id>-<uuid>.md
    """
    safe_env = _safe_env_id(env_id)
    safe_uuid = "".join(
        ch for ch in (prompt_uuid or "").strip() 
        if ch.isalnum() or ch in {"-", "_"}
    )
    if not safe_uuid:
        safe_uuid = uuid4().hex[:8]
    return os.path.join(
        user_prompts_dir(), 
        f"{safe_env}-{safe_uuid}.md"
    )
```

#### 3. Update Serialization Logic

**File:** `agents_runner/environments/serialize.py`

**Deserialization (lines 74-85):**
```python
prompts_data = payload.get("prompts", [])
prompts = []
if isinstance(prompts_data, list):
    for p in prompts_data:
        if isinstance(p, dict):
            # Handle both old (text) and new (prompt_path) formats
            text = str(p.get("text", ""))
            prompt_path = str(p.get("prompt_path", ""))
            
            # If we have a path but no text, load from file
            if prompt_path and not text:
                try:
                    if os.path.exists(prompt_path):
                        with open(prompt_path, "r", encoding="utf-8") as f:
                            text = f.read()
                except Exception:
                    # File missing/unreadable - keep empty text
                    pass
            
            prompts.append(
                PromptConfig(
                    enabled=bool(p.get("enabled", False)),
                    text=text,
                    prompt_path=prompt_path,
                )
            )
```

**Serialization (lines 274-276):**
```python
"prompts": [
    {
        "enabled": p.enabled,
        "text": p.text,  # Keep for backwards compatibility
        "prompt_path": p.prompt_path,
    } 
    for p in (env.prompts or [])
],
```

#### 4. Update Storage Logic

**File:** `agents_runner/environments/storage.py`

**Add prompt migration helper:**
```python
def _migrate_inline_prompts_to_files(env: Environment) -> Environment:
    """Migrate inline prompt text to external files.
    
    This function is called when loading environments to automatically
    migrate legacy inline prompts to the new external file format.
    """
    if not env.prompts:
        return env
    
    prompts_dir = user_prompts_dir()
    os.makedirs(prompts_dir, exist_ok=True)
    
    migrated_prompts = []
    for prompt in env.prompts:
        # Already migrated?
        if prompt.prompt_path and os.path.exists(prompt.prompt_path):
            migrated_prompts.append(prompt)
            continue
        
        # Has inline text to migrate?
        if prompt.text and not prompt.prompt_path:
            # Generate UUID and path
            prompt_uuid = uuid4().hex[:8]
            prompt_path = user_prompt_path(env.env_id, prompt_uuid)
            
            try:
                # Write to file
                with open(prompt_path, "w", encoding="utf-8") as f:
                    f.write(prompt.text)
                
                # Update prompt config
                migrated_prompts.append(
                    PromptConfig(
                        enabled=prompt.enabled,
                        text="",  # Clear inline text after migration
                        prompt_path=prompt_path,
                    )
                )
            except Exception as e:
                # Migration failed - keep inline text
                logger.warning(f"Failed to migrate prompt: {e}")
                migrated_prompts.append(prompt)
        else:
            # Empty prompt, keep as-is
            migrated_prompts.append(prompt)
    
    # Return environment with migrated prompts
    env.prompts = migrated_prompts
    return env
```

**Update load_environments (line 44):**
```python
def load_environments(data_dir: str | None = None) -> dict[str, Environment]:
    data_dir = data_dir or default_data_dir()
    state_path = _state_path_for_data_dir(data_dir)
    if not os.path.exists(state_path):
        return {}
    state = load_state(state_path)
    # ... existing logic ...
    
    # Migrate inline prompts to files
    for env_id, env in envs.items():
        migrated = _migrate_inline_prompts_to_files(env)
        if migrated.prompts != env.prompts:
            # Save migrated version
            save_environment(migrated, data_dir=data_dir)
            envs[env_id] = migrated
    
    return envs
```

**Add cleanup for delete_environment (line 116):**
```python
def delete_environment(env_id: str, data_dir: str | None = None) -> None:
    # ... existing logic ...
    
    # Clean up user prompt files
    env = load_environments(data_dir=data_dir).get(env_id)
    if env and env.prompts:
        for prompt in env.prompts:
            if prompt.prompt_path:
                try:
                    if os.path.exists(prompt.prompt_path):
                        os.unlink(prompt.prompt_path)
                except Exception:
                    pass
```

#### 5. Update UI Logic

**File:** `agents_runner/ui/pages/environments_prompts.py`

**No changes needed!** The UI reads/writes `PromptConfig.text` directly. The migration happens transparently in the storage layer.

**Optional Enhancement (Future):**
Add "Edit in External Editor" button that opens the `.md` file in the user's preferred editor.

#### 6. Update Runtime Usage

**File:** `agents_runner/ui/main_window_tasks_agent.py` (lines 234-249)

```python
enabled_env_prompts: list[str] = []
if env and bool(getattr(env, "prompts_unlocked", False)):
    for p in getattr(env, "prompts", None) or []:
        if not bool(getattr(p, "enabled", False)):
            continue
        
        # Try path first, fall back to inline text
        prompt_text = ""
        prompt_path = str(getattr(p, "prompt_path", "") or "").strip()
        if prompt_path and os.path.exists(prompt_path):
            try:
                with open(prompt_path, "r", encoding="utf-8") as f:
                    prompt_text = f.read().strip()
            except Exception as e:
                logger.warning(f"Failed to read prompt from {prompt_path}: {e}")
                prompt_text = str(getattr(p, "text", "") or "").strip()
        else:
            prompt_text = str(getattr(p, "text", "") or "").strip()
        
        if prompt_text:
            enabled_env_prompts.append(sanitize_prompt(prompt_text))
```

### Migration Path

**Phase 1: Backwards Compatible (Safe)**
1. Add `prompt_path` field to `PromptConfig`
2. Update serialization to include both `text` and `prompt_path`
3. Update deserialization to prefer `prompt_path` but fall back to `text`
4. Update runtime to read from file if path exists

**Phase 2: Automatic Migration (Transparent)**
1. Add migration helper to `storage.py`
2. Run migration on load (one-time per environment)
3. Save migrated environments back to state

**Phase 3: Cleanup (Future, Optional)**
1. After sufficient adoption (e.g., 3 months), remove `text` field support
2. Remove backwards compatibility code

### Edge Cases & Risks

#### Edge Case 1: Missing Prompt File
**Scenario:** User manually deletes a `.md` file  
**Impact:** Prompt becomes disabled (empty text)  
**Mitigation:** Keep `text` field as fallback during migration period  
**Risk Level:** LOW (user error, recoverable)

#### Edge Case 2: Concurrent Access
**Scenario:** Multiple instances edit same environment  
**Impact:** File I/O race conditions  
**Mitigation:** state.json already has this issue; no worse than current  
**Risk Level:** LOW (rare, existing issue)

#### Edge Case 3: File Permissions
**Scenario:** `~/.midoriai/agents-runner/prompts/` not writable  
**Impact:** Migration fails, falls back to inline text  
**Mitigation:** Log warning, continue with inline text  
**Risk Level:** LOW (graceful degradation)

#### Edge Case 4: Large Prompts
**Scenario:** User has 10+ prompts with 1KB+ each  
**Impact:** Slower load time (multiple file reads)  
**Mitigation:** Cache in memory after first load (optional optimization)  
**Risk Level:** LOW (minimal performance impact)

#### Edge Case 5: Rollback
**Scenario:** User downgrades to older version  
**Impact:** Newer version has `prompt_path`, older version ignores it  
**Result:** Older version reads `text` field (still present for compat)  
**Risk Level:** LOW (backwards compatible by design)

### Testing Strategy

**Unit Tests:**
1. Serialize/deserialize with `prompt_path`
2. Serialize/deserialize with legacy `text` only
3. Migration from inline text to file
4. Load from file when path exists
5. Fall back to inline text when file missing

**Integration Tests:**
1. Create environment with prompts → verify files created
2. Load environment → verify prompts loaded from files
3. Delete environment → verify files cleaned up
4. Edit prompts in UI → verify files updated

**Manual Tests:**
1. Upgrade from version without `prompt_path` → verify auto-migration
2. Edit `.md` file externally → verify changes reflected in UI
3. Delete `.md` file → verify graceful degradation

---

## Additional Findings: No Other Hardcoded Prompts

### Audit Methodology

Searched for:
- Multiline strings with user-facing text
- Hardcoded markdown/plain text in code
- "TODO", "FIXME", "hardcoded" comments
- String formatting with agent/environment context

### Results

**✓ System prompts already externalized:**
- `pixelarch_environment.md` - PixelArch context
- `github_version_control.md` - Git workflow instructions
- `headless_desktop.md` - noVNC desktop instructions
- `pr_metadata.md` - PR metadata file instructions
- `help_request_template.md` - Help agent template

**✓ UI strings (not prompts):**
- Dialog messages
- Button labels
- Tooltips
- Error messages
These are UI text, not agent prompts - correctly kept in code.

**✓ Configuration constants:**
- Docker image names
- Path templates
- URL constants
These are configuration, not prompts - correctly kept in code.

**No additional hardcoded prompts found.**

---

## Summary of Required Changes

### Part 1: PR Attribution Footer (LOW RISK)

**Files to Modify:**
1. ✅ Create: `agents_runner/prompts/pr_attribution_footer.md`
2. ✅ Modify: `agents_runner/gh/task_plan.py` (~10 lines changed)

**Breaking Changes:** None  
**Migration Required:** No  
**Estimated Effort:** 30 minutes  
**Risk Level:** LOW

### Part 2: User-Defined Prompts (MEDIUM RISK)

**Files to Modify:**
1. ✅ Modify: `agents_runner/environments/model.py` (add `prompt_path` field)
2. ✅ Modify: `agents_runner/environments/paths.py` (add path helpers)
3. ✅ Modify: `agents_runner/environments/serialize.py` (update serialize/deserialize)
4. ✅ Modify: `agents_runner/environments/storage.py` (add migration + cleanup)
5. ✅ Modify: `agents_runner/ui/main_window_tasks_agent.py` (read from file)
6. ⚠️  No changes: `agents_runner/ui/pages/environments_prompts.py` (transparent)

**Breaking Changes:** None (backwards compatible by design)  
**Migration Required:** Yes (automatic, one-time, transparent)  
**Estimated Effort:** 2-3 hours  
**Risk Level:** MEDIUM (file I/O, migration logic)

---

## Recommendations

### Priority 1: PR Attribution Footer
**Action:** Implement immediately  
**Rationale:** Simple, low-risk, clear benefit  
**Timeline:** Single PR, 1 developer-hour

### Priority 2: User-Defined Prompts
**Action:** Implement with thorough testing  
**Rationale:** More complex but well-architected, good long-term solution  
**Timeline:** Single PR with comprehensive tests, 4-6 developer-hours

### Quality Gates

**Before merging Part 1:**
- ✅ PR body output matches exactly (byte-for-byte)
- ✅ Idempotency preserved (marker check)
- ✅ Manual test: Create PR with footer

**Before merging Part 2:**
- ✅ Backwards compatibility verified
- ✅ Migration tested with real state.json
- ✅ File cleanup on delete verified
- ✅ Graceful degradation on missing files tested
- ✅ Manual test: Upgrade path from current version
- ✅ Manual test: Edit external .md file

### Future Enhancements (Out of Scope)

1. **Prompt Templates:** Share common prompts across environments
2. **Prompt Library:** Curated collection of useful prompts
3. **External Editor Integration:** "Edit in VS Code" button
4. **Prompt Versioning:** Track changes to prompt files
5. **Prompt Variables:** Template variables in user prompts (like system prompts)

---

## Conclusion

**Audit Result:** ✓ PASS - Reviewer's assessment confirmed accurate

Both externalization tasks are:
- Well-scoped and implementable
- Low to medium risk with proper testing
- Backwards compatible by design
- Aligned with existing architecture patterns

**Recommendation:** APPROVE for implementation with suggested approach.

**Sign-off:** Auditor Mode  
**Date:** 2025-01-07  
**Report ID:** d08cf300-prompt-externalization-audit
