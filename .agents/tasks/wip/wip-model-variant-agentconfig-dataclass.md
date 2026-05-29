# Task: Add agent/model/variant fields to AgentConfig dataclass

**File:** `agents_runner/agent_configs/model.py`

**Goal:** Add `agent`, `model`, and `variant` fields to the `AgentConfig` dataclass so the opencode agent config can carry agent name, model, and reasoning-effort selections natively.

**Background:**
Currently `AgentConfig` only has `cli_flags` as a flat string for all extra CLI arguments. For the opencode provider, users need to specify an agent name (e.g., `"worker"` or custom agents), pick a model (e.g., `opencode/deepseek-v4-flash-free`), and an optional reasoning-effort variant (e.g., `high`). These should be first-class fields rather than crammed into `cli_flags`.

**Steps:**
1. Add `agent: str = ""` field to the `AgentConfig` dataclass (default empty string). This is a freeform agent name, not a predefined enum; users type their agent name (e.g., `"worker"`).
2. Add `model: str = ""` field to the `AgentConfig` dataclass (default empty string).
3. Add `variant: str = ""` field to the `AgentConfig` dataclass (default empty string).
4. Keep existing fields (`config_id`, `agent_cli`, `config_dir`, `cli_flags`) unchanged.

**Done criteria:**
- `AgentConfig` has `agent`, `model`, and `variant` string fields with empty defaults.
