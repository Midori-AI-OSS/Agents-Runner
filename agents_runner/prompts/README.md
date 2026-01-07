# Agent Prompts Directory

This directory contains system-level prompts that are appended to agent instructions based on enabled features and settings.

## Overview

Rather than hard-coding prompts in Python source files, prompts are stored as markdown files for easier customization, version control, and maintenance.

## Available Prompts

### 1. `pixelarch_environment.md`
**Purpose:** Informs the agent about the PixelArch container environment  
**When used:** "Append PixelArch context" is enabled in Settings  
**Template variables:** None

Tells the agent about:
- Running inside PixelArch container
- Passwordless sudo access
- Package installation with `yay -Syu`
- Full container control

### 2. `github_version_control.md`
**Purpose:** Instructs agent on Git workflow and commit practices  
**When used:** GitHub management mode is enabled for environment  
**Template variables:** None

Guides the agent to:
- Use git and gh CLI tools
- Commit changes frequently
- Follow proper git workflow
- Understand automatic PR creation

### 3. `headless_desktop.md`
**Purpose:** Teaches agent how to automate GUI applications  
**When used:** Headless desktop is enabled  
**Template variables:** `{DISPLAY}` - X11 display identifier (default: ":1")

Explains:
- noVNC headless desktop session
- How to use wmctrl and xdotool for GUI automation
- Screenshot capture commands
- Artifact storage locations

### 4. `pr_metadata.md`
**Purpose:** Guides agent on creating PR metadata  
**When used:** GitHub management + PR metadata enabled  
**Template variables:** `{PR_METADATA_FILE}` - Container path to JSON file

Instructs on:
- Updating PR metadata JSON file
- Required JSON structure (title, body)
- JSON formatting requirements
- Reminder to commit code changes

### 5. `help_request_template.md`
**Purpose:** Structures Help Me feature conversations  
**When used:** User clicks "Help Me" button  
**Template variables:** `{USER_QUESTION}` - User's question

Provides context about:
- Agents Runner environment
- Available repositories
- How to assist effectively

## How It Works

### Loading Prompts

Prompts are loaded via the `load_prompt()` function from `loader.py`:

```python
from agents_runner.prompts import load_prompt

# Simple prompt without variables
prompt = load_prompt("pixelarch_environment", fallback="...")

# Prompt with template variables
prompt = load_prompt(
    "headless_desktop", 
    DISPLAY=":1",
    fallback="..."
)
```

### Template Variables

Template variables use Python's `str.format()` syntax with `{VARIABLE_NAME}`:

```markdown
X11 display: {DISPLAY}
JSON file at: {PR_METADATA_FILE}
```

When loading, pass variables as keyword arguments:

```python
load_prompt("headless_desktop", DISPLAY=":1")
```

### Fallback Behavior

If a prompt file is missing or cannot be loaded:
1. A warning is logged
2. The `fallback` parameter value is used
3. Application continues without errors

This ensures backward compatibility and prevents breakage if prompt files are accidentally deleted.

### Caching

Loaded prompts are cached in memory to avoid repeated file I/O. The cache can be cleared with:

```python
from agents_runner.prompts.loader import clear_cache
clear_cache()
```

## Customizing Prompts

### For Developers

1. **Edit the markdown files directly** in this directory
2. **Restart the application** to see changes (prompts are cached)
3. **Test thoroughly** to ensure agent behavior is correct
4. **Commit changes** with clear descriptions

### For Advanced Users

⚠️ **Warning:** Modifying system prompts can significantly affect agent behavior!

If you know what you're doing:
1. Edit the `.md` files in `agents_runner/prompts/`
2. Keep the `## Prompt` section header
3. Maintain template variable names exactly as shown
4. Restart Agents Runner to load changes

### Markdown Format

Each prompt file follows this structure:

```markdown
# Prompt Title

Description of what this prompt does.

**When used:** When this prompt is appended  
**Template variables:** List of variables (or None)

## Prompt

[The actual prompt text goes here]
[Template variables: {VARIABLE_NAME}]
```

The loader extracts everything after `## Prompt` as the actual prompt text.

## Prompt Concatenation Order

When multiple prompts are enabled, they are concatenated in this order:

1. User's main prompt/task description
2. PixelArch environment context (if enabled)
3. GitHub version control context (if enabled)
4. User's custom environment prompts (if unlocked)
5. PR metadata instructions (if enabled)
6. Headless desktop instructions (if enabled)

## Best Practices

### ✅ Do:
- Keep prompts clear and concise
- Use bullet points for instructions
- Test changes thoroughly
- Document why you made changes
- Keep template variables consistent

### ❌ Don't:
- Remove template variable placeholders
- Change variable names arbitrarily
- Make prompts excessively long
- Remove critical instructions
- Forget to test after editing

## Related Files

- **Loader implementation:** `loader.py`
- **Usage in constants:** `agents_runner/ui/constants.py`
- **Desktop instructions:** `agents_runner/docker/agent_worker.py`
- **PR metadata:** `agents_runner/pr_metadata.py`
- **Help Me feature:** `agents_runner/ui/pages/new_task.py`

## Future Enhancements

Potential improvements for this system:

- **Localization:** Directory structure like `prompts/en-US/`, `prompts/ja-JP/`
- **User environment prompts:** Move to UUID-based markdown files
- **Prompt versioning:** Track prompt changes over time
- **A/B testing:** Test different prompt variations
- **Community library:** Share and distribute prompt improvements

## Troubleshooting

### Prompt not loading
- Check file exists in `agents_runner/prompts/`
- Check file has `.md` extension
- Check logs for error messages
- Verify file encoding is UTF-8

### Template variables not substituting
- Check variable name matches exactly
- Check loader call passes correct kwargs
- Check for typos in variable names
- Review logs for substitution errors

### Agent behavior changed unexpectedly
- Review recent prompt edits
- Test with fallback values
- Compare with git history
- Restore from version control

## Support

For questions or issues:
- Check audit reports in `.codex/audit/574920b1-*.md`
- Review loader source code in `loader.py`
- Check main application logs
- Open an issue in the repository

---

**Directory Structure:**
```
agents_runner/prompts/
├── __init__.py                     # Module exports
├── loader.py                        # Prompt loading utility
├── README.md                        # This file
├── pixelarch_environment.md        # PixelArch context
├── github_version_control.md       # Git workflow
├── headless_desktop.md             # Desktop automation
├── pr_metadata.md                  # PR creation
└── help_request_template.md        # Help Me feature
```

**Last Updated:** 2025-01-20  
**Audit ID:** 574920b1
