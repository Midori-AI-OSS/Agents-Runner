# Task: CLI Help and Behavior Alignment Audit

**Role:** QA  
**Estimated Time:** 1.5-2 hours  
**Dependencies:** None (can start immediately)

## Objective
Fresh review of all CLI `--help` outputs and system behaviors to ensure old vs new unified planner alignment.

## Context
- PR 193 migrated interactive/non-interactive execution to unified planner
- Old paths removed, new planner-based flow in place
- Need to verify CLI help text, error messages, and behavior match actual implementation
- Main entry point: `main.py` (thin dispatcher per AGENTS.md)

## Prerequisites
- Repository on branch `midoriaiagents/60d23c757d`
- UV environment set up (`uv sync` if needed)
- Access to run `uv run main.py` (with sudo if testing docker-based agent execution)

## Discovery Phase

### Step 1: Enumerate all CLI entry points
```bash
# Get main.py help (with timeout in case it hangs)
timeout 15 uv run python main.py --help > /tmp/agents-artifacts/<hex>-main-help.txt 2>&1 || echo "Help timed out"

# Identify subcommands from help output
grep -E "^  [a-z-]+" /tmp/agents-artifacts/<hex>-main-help.txt | awk '{print $1}'

# Or inspect main.py directly for argparse structure
grep -A 5 "subparsers\|add_subparsers\|add_parser" main.py

# Check for agent-specific CLI modules
find agents_runner -name "cli.py" -o -name "*_cli.py" | head -10
```

### Step 2: Capture all help outputs
```bash
# For each discovered subcommand (example: 'run', 'config', etc.)
timeout 10 uv run python main.py <subcommand> --help > /tmp/agents-artifacts/<hex>-<subcommand>-help.txt 2>&1

# If no subcommands, just main help is sufficient
# If GUI-only, document that and focus on error messages when run without GUI
```

## Acceptance Criteria

### 1. Help Text Audit
For each CLI entry point discovered:
- **Capture help output:** Save to `/tmp/agents-artifacts/<hex>-<name>-help.txt`
- **Check for accuracy:**
  - No references to removed code paths (e.g., old "interactive docker launch" module)
  - No mentions of deprecated flags or options
  - Help text matches actual behavior (options that are shown actually work)
- **Check terminology consistency:**
  - "planner/runner" vs old terms (if any were different)
  - Agent system names: codex, claude, copilot, gemini (consistent capitalization/spelling)
- **Verify examples (if provided in help text):**
  - Examples should be copy-paste runnable
  - Examples should succeed or fail with expected error message

### 2. Removed/Deprecated Options Check
Identify options that should have been removed:
```bash
# Search for old interactive docker launcher references
grep -r "interactive.*docker.*launch" agents_runner/ --exclude-dir=tests

# Check if old flags still exist in argparse
grep -r "add_argument.*--old-flag-name" main.py agents_runner/

# Verify removed module isn't imported anywhere
grep -r "main_window_tasks_interactive_docker" agents_runner/
```

### 3. Behavior Alignment Testing
Test 2-3 representative commands from help text:
- **Example 1: Basic agent invocation** (if shown in help)
  - Run the command exactly as documented
  - Verify it behaves as help text describes
  - Capture output to `/tmp/agents-artifacts/<hex>-behavior-test-1.txt`
  
- **Example 2: Error scenario** (invalid agent, missing required arg, etc.)
  - Trigger an expected error
  - Verify error message is clear and actionable
  - Check that error message matches what help text suggests
  - Capture to `/tmp/agents-artifacts/<hex>-behavior-test-error.txt`

- **Example 3: Config-related command** (if exists)
  - Test config viewing or validation
  - Verify output format matches expectations

### 4. Help Text Fixes (if needed)
If help text is inaccurate:
- **Identify where help text is defined:**
  ```bash
  # Argparse help strings in main.py
  grep -n "help=" main.py | head -20
  
  # Docstrings used as help text
  grep -A 3 '"""' main.py
  ```
- **Make corrections in this task:**
  - Edit the help strings in main.py or relevant CLI modules
  - Keep changes minimal (fix only what's wrong)
  - Commit with `[DOCS] Fix CLI help text: <what was fixed>`
- **Verify fixes:**
  - Run `--help` again and confirm corrections
  - Capture updated help to new artifact file for comparison

### 5. Behavior Issues (if found)
If actual behavior doesn't match help text:
- **Document the discrepancy** in the audit report
- **DO NOT fix code in this task** - file a separate bug task with:
  - Expected behavior (per help text)
  - Actual behavior (what happened)
  - Steps to reproduce
  - Suggested fix (if obvious)

### 6. Create audit report: `.agents/reviews/193-cli-audit.md`
Include:
- **List of all CLI entry points checked** (main + subcommands)
- **Help text accuracy summary** (accurate / needs fixes / fixed)
- **Removed options verification** (confirmed removed / still present)
- **Behavior test results** (3 tests: pass/fail, output references)
- **Fixes applied** (if any help text corrections were made)
- **Issues found** (discrepancies between help and behavior, with task recommendations)
- **Overall assessment** (ready for merge / needs follow-up / blocking issues)

## Where Help Text Lives
Common locations to check/edit:
- `main.py`: argparse setup, argument help strings
- `agents_runner/ui/`: UI-related CLI entry points (if any)
- `agents_runner/planner/`: Planner-related CLI (if exposed)
- Module docstrings: Sometimes used as subcommand descriptions

## Success Criteria
- ✅ All CLI entry points identified and help text captured
- ✅ Help text reviewed for accuracy (references to old paths removed, if any)
- ✅ Terminology consistent (planner/runner, agent system names)
- ✅ 2-3 behavior tests completed (success + error scenarios)
- ✅ Any inaccurate help text fixed and committed
- ✅ Any behavior mismatches documented with bug task recommendations
- ✅ Audit report created at `.agents/reviews/193-cli-audit.md`

## Notes
- Focus on user-facing correctness, not implementation details
- If help text is wrong, fix it in this task
- If behavior is wrong, file separate bug task
- Check both success and error paths
- If main.py is GUI-only (no CLI mode), document that and focus on error messages when run incorrectly
