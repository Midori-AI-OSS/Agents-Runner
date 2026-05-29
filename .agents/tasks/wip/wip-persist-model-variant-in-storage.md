# Task: Persist agent/model/variant fields in agent config storage

**File:** `agents_runner/agent_configs/storage.py`

**Depends on:** `wip-model-variant-agentconfig-dataclass.md`

**Goal:** Update `save_agent_config()` and `load_agent_configs()` to serialize/deserialize the new `agent`, `model`, and `variant` fields on `AgentConfig`.

**Steps:**
1. In `load_agent_configs()`: when building `AgentConfig` from dict items, read `agent` from `item_dict.get("agent")` with default `""`, `model` from `item_dict.get("model")` with default `""`, and `variant` from `item_dict.get("variant")` with default `""`. Pass them to the `AgentConfig(...)` constructor.
2. In `save_agent_config()`: when building the serialized dict for each config, include `"agent": str(getattr(config, "agent", "") or "").strip()`, `"model": str(getattr(config, "model", "") or "").strip()`, and `"variant": str(getattr(config, "variant", "") or "").strip()`.

**Done criteria:**
- Existing saved configs without `agent`/`model`/`variant` keys load correctly (default to empty strings).
- Creating/saving a config with agent/model/variant set persists and round-trips correctly.
