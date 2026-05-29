# Task: Prepend agent/model/variant as CLI flags in executor and settings resolver

**Files:** `agents_runner/execution/supervisor.py`, `agents_runner/ui/main_window_settings.py`

**Depends on:** `wip-model-variant-agentconfig-dataclass.md`

**Goal:** When `AgentConfig.agent`, `AgentConfig.model`, or `AgentConfig.variant` is set, prepend `--agent X --model X --variant Y` to the resolved `cli_flags` string so they flow through the existing `shlex.split()` → `extra_cli_args` → plugin pipeline without changing the plugin signature.

**Steps:**
1. In `execution/supervisor.py` → `_resolved_agent_cli_flags_text()`: after getting `cli_flags`, also read `config.agent`, `config.model`, and `config.variant`. Prepend `--agent {agent}` (if non-empty), `--model {model}` (if non-empty), and `--variant {variant}` (if non-empty) before the existing `cli_flags`. Return the combined string.
2. In `ui/main_window_settings.py` → `_resolve_agent_instance_runtime()` and `_resolve_override_agent_runtime()`: when reading `cli_flags` from config, also read `config.agent`, `config.model`, and `config.variant`. Prepend them as CLI flags. Use same pattern as supervisor.
3. Use `shlex.quote()` when constructing flag + value pairs to handle values that may contain special characters (like `/` in `opencode/deepseek-v4-flash-free`). Note: since these are added before `shlex.split()` processes them, ensure the combined string is splittable. If `shlex.split()` is used downstream, construct the prepended string with proper quoting.

**Done criteria:**
- When a config has `agent="worker"`, `model="opencode/deepseek-v4-flash-free"`, and `variant="high"`, `_resolved_agent_cli_flags_text()` returns `"--agent worker --model opencode/deepseek-v4-flash-free --variant high <existing cli_flags>"`.
- The combined string is properly splittable by `shlex.split()` downstream.
- Empty agent/model/variant fields produce no corresponding flag in the output.
- The change applies to both non-interactive (supervisor) and interactive (main_window_settings) paths.
