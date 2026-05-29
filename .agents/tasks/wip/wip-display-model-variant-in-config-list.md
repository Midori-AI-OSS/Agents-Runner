# Task: Display agent/model/variant in agent config list row

**File:** `agents_runner/ui/pages/settings_form.py`

**Depends on:** `wip-model-variant-agentconfig-dataclass.md`

**Goal:** Update `_create_agent_config_row_widget()` to show the `agent`, `model`, and `variant` fields when they are set on an `AgentConfig`, so the config list in Settings > Agent Configs displays the selected agent, model, and variant alongside existing fields.

**Steps:**
1. In `_create_agent_config_row_widget()` (around line 1037), read `agent = str(getattr(config, "agent", "") or "").strip()`, `model = str(getattr(config, "model", "") or "").strip()`, and `variant = str(getattr(config, "variant", "") or "").strip()`.
2. After the existing `cli_flags` line, add agent display if non-empty: `if agent:` → `parts.append(f"Agent: {agent}")`.
3. Add model display if non-empty: `if model:` → `parts.append(f"Model: {model}")`.
4. Add variant display if non-empty: `if variant:` → `parts.append(f"Variant: {variant}")`.

**Done criteria:**
- When a config has agent set, the row shows `Agent: worker`.
- When a config has model set, the row shows `Model: opencode/deepseek-v4-flash-free`.
- When a config has variant set, the row shows `Variant: high`.
- When none are set, no extra lines appear.
