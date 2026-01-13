# Task 018: Force Git Identity for Agents

## Problem
Agents name themselves whatever they want for git commits. Need to force git identity to `Midori AI Agent <contact-us@midori-ai.xyz>`.

## Location
- Container initialization scripts
- `agents_runner/docker/preflight_worker.py` (preflight script creation)
- `agents_runner/docker/utils.py` (_write_preflight_script)
- Any location that sets up git in containers

## Acceptance Criteria
- [ ] Identify where git is configured in containers (preflight scripts, container setup)
- [ ] Add git config commands to set `user.name` to "Midori AI Agent"
- [ ] Add git config commands to set `user.email` to "contact-us@midori-ai.xyz"
- [ ] Ensure git identity is set before any agent code runs
- [ ] Test by running an agent that makes git commits
- [ ] Verify commit author is "Midori AI Agent <contact-us@midori-ai.xyz>"
- [ ] Test with multiple agent types to ensure consistent identity

## Notes
- Git identity should be forced at the container level before agent execution
- Use `git config --global user.name` and `git config --global user.email`
- This ensures all agent commits have consistent identity
