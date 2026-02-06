# Add agent systems plugin models and registry

**Parent Task:** 026-agent-system-plugins.md

## Scope
Create plugin infrastructure with Pydantic models and discovery/registration.

## Actions
1. Create `agents_runner/agent_systems/` package with `__init__.py`
2. Create `agents_runner/agent_systems/models.py` with Pydantic types:
   - `PromptDeliverySpec`
   - `CapabilitySpec`
   - `UiThemeSpec`
   - `MountSpec`
   - `ExecSpec`
   - `AgentSystemContext`
   - `AgentSystemRequest`
   - `AgentSystemPlan`
   - `AgentSystemPlugin` (base class with abstract `plan` method)
3. Create `agents_runner/agent_systems/registry.py`:
   - Auto-discover plugins from `agents_runner/agent_systems/*/plugin.py`
   - Register and select plugins by name
   - Safety: skip plugins with import failures (log error)
   - Validate unique names and valid capabilities
4. No Qt imports in this package
5. Run linters

## Acceptance
- All models defined per prototype in parent task
- Plugin discovery is safe (import failures don't crash app)
- Passes linting
- One focused commit: `[FEAT] Add agent system plugin models and registry`
