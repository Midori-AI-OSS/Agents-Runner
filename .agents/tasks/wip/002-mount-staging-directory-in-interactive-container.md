# Task 002: Mount Staging Directory in Interactive Container

## Objective
Mount the host staging directory to `/tmp/agents-artifacts` in the interactive container (matching normal task behavior).

## Context
- Normal tasks already mount staging directory for artifact collection
- Interactive tasks need the same mount so completion markers and artifacts are host-visible
- This allows finalization to work even after container is auto-removed

## Requirements
1. Add `-v <artifacts_staging_dir>:/tmp/agents-artifacts` to the interactive container launch
2. Ensure the staging directory path is created on host before mounting
3. Use the same artifact staging path as normal tasks

## Location to Change
- File: `agents_runner/ui/main_window_tasks_interactive_docker.py`
- Function that builds the docker run command

## Reference Code
- Normal task staging mount: `agents_runner/docker/agent_worker.py`
- Artifact info: `agents_runner/artifacts.py:get_artifact_info()`

## Acceptance Criteria
- [ ] Interactive container includes `-v` mount for staging directory
- [ ] Mount point in container is `/tmp/agents-artifacts`
- [ ] Host staging directory is created before container launch
- [ ] Path matches pattern: `~/.midoriai/agents-runner/artifacts/<task_id>/staging/`

## Notes
- Ensure directory permissions allow writing from inside container
- This mount is required for task 001 (completion marker writing) to work
