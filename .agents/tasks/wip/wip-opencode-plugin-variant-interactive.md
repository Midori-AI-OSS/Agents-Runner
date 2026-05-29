# Task: Handle --variant flag in OpenCode plugin interactive command building

**File:** `agents_runner/agent_systems/opencode/plugin.py`

**Goal:** Ensure `--variant` is properly handled when building interactive commands for opencode. Currently the `_TOP_LEVEL_VALUE_OPTIONS` set and `_has_top_level_project()` helper don't know about `--variant`. Since `--variant` is a `run` subcommand flag (not top-level), it should be treated as a generic flag when `run` is the subcommand and ignored/repositioned when it's not.

**Steps:**
1. `--variant` is a `run` subcommand flag, not a top-level option. In `build_interactive_command_parts()`, when `subcommand != "run"` and `--variant` appears in `agent_cli_args`, it should still be passed through (best-effort) since the user explicitly chose it. Do NOT add `--variant` to `_TOP_LEVEL_VALUE_OPTIONS` — that set is for top-level flags recognized during subcommand/project detection.
2. In `build_interactive_command_parts()`, the `agent_cli_args` are already extended to `parts` before subcommand/project detection. No additional change needed for `--variant` handling since it flows through as an extra arg.
3. Verify the `plan()` method (non-interactive) already handles `--variant` correctly: since `plan()` always uses `["opencode", "run", ...]`, any `--variant` in `extra_cli_args` will be passed after `--dir` and before the prompt, which is correct for `opencode run`.
4. Add `--variant` to the `_TOP_LEVEL_VALUE_OPTIONS` set so `_has_top_level_project()` recognizes it as a flag-with-value rather than a project name (defensive fix for when users manually type `opencode --variant high --model x project`).

**Done criteria:**
- `--variant` is in `_TOP_LEVEL_VALUE_OPTIONS` so the project-detection helper doesn't mistake it for a project path.
- Non-interactive `plan()` correctly passes `--variant X` through `extra_cli_args`.
- Interactive `build_interactive_command_parts()` passes through `--variant` from `agent_cli_args` without error.
