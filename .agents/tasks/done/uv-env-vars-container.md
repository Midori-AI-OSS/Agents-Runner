# Auto-set UV_PROJECT_ENVIRONMENT and UV_PYTHON_INSTALL_DIR in containers

**Status:** wip

Add auto-set of `UV_PROJECT_ENVIRONMENT=/tmp/.uv-venv` and `UV_PYTHON_INSTALL_DIR=/tmp/.uv-python` environment variables in all container launches, with user-override guard.

## Files changed
- `agents_runner/docker/agent_worker_container.py` — `ContainerExecutor._build_env_args()`
- `agents_runner/ui/main_window_tasks_interactive_docker.py` — `launch_docker_terminal_task()`
