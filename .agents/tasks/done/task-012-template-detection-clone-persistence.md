# Task 012: Template Detection Persistence in Cloned Environments

## Problem
When a Midori AI template is detected after cloning in a 'cloned' environment, the `midoriai_template_likelihood` is not set in the environment, but the prompt injection still occurs. The likelihood needs to be recorded and saved based on the cloned copy, then updated only when the clone happens again.

## Location
- `agents_runner/docker/preflight_worker.py`
- `agents_runner/docker/agent_worker.py`
- `agents_runner/ui/main_window_tasks_interactive.py`
- `agents_runner/environments/serialize.py`
- `agents_runner/midoriai_template.py`

## Acceptance Criteria
- [ ] Verify current behavior: template detection runs in cloned environments but likelihood is not persisted
- [ ] After template detection in a cloned environment, save `midoriai_template_likelihood` to the environment state
- [ ] On subsequent runs with the same cloned environment (no re-clone), use the saved likelihood value
- [ ] When re-cloning occurs, re-run template detection and update the saved likelihood
- [ ] Test with cloned environment to confirm likelihood persists across runs without re-clone
- [ ] Test with cloned environment re-clone to confirm likelihood updates

## Notes
- Template detection already sets `env.midoriai_template_likelihood` in preflight_worker.py:142-143, agent_worker.py:218-219, and main_window_tasks_interactive.py:98
- Serialization already handles the field in serialize.py:160-161 and 408-409
- Need to ensure detection runs and persists for cloned workspaces specifically
