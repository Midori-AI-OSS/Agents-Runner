"""Tool registration and dispatch for MCP server — task lifecycle tools."""

from __future__ import annotations

import json
import os
import shlex
import threading
import time

from dataclasses import asdict
from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
from typing import Any
from typing import cast
from uuid import uuid4

from rich.console import Console

from midori_ai_logger import MidoriAiLogger

from agents_runner.agent_cli import default_host_config_dir
from agents_runner.agent_cli import normalize_agent
from agents_runner.agent_configs.model import AgentConfig
from agents_runner.agent_configs.storage import load_agent_configs
from agents_runner.agent_configs.storage import resolve_agent_config
from agents_runner.artifacts import collect_artifacts_from_container_with_timeout
from agents_runner.docker.config import DockerRunnerConfig
from agents_runner.environments.model import WORKSPACE_CLONED
from agents_runner.environments.model import WORKSPACE_MOUNTED
from agents_runner.environments.model import AgentInstance
from agents_runner.environments.model import AgentSelection
from agents_runner.environments.model import Environment
from agents_runner.environments.model import normalize_gpu_override_mode
from agents_runner.environments.model import normalize_workspace_type
from agents_runner.environments.paths import managed_repo_checkout_path
from agents_runner.environments.storage import load_environments
from agents_runner.execution.supervisor import TaskSupervisor
from agents_runner.execution.supervisor_types import SupervisorConfig
from agents_runner.execution.supervisor_types import SupervisorResult
from agents_runner.log_format import format_log
from agents_runner.mcp.server import MCPServer
from agents_runner.mcp.types import (
    TextContent,
    ToolCallResult,
    ToolDefinition,
)
from agents_runner.mcp.worker_tracker import WorkerTracker
from agents_runner.mcp.worker_tracker import get_worker_tracker
from agents_runner.persistence import (
    default_state_path,
    load_active_task_payloads,
    load_done_task_payloads,
    load_state,
    load_task_payload,
    load_watch_state,
    save_task_payload,
)

logger = MidoriAiLogger(channel=None, name=__name__)
logger.console = Console(stderr=True)

PIXELARCH_EMERALD_IMAGE = "lunamidori5/pixelarch:emerald"
Payload = dict[str, Any]

_worker_tracker: WorkerTracker | None = None
_payload_locks_guard = threading.Lock()
_payload_locks: dict[str, threading.Lock] = {}


def _active_worker_tracker() -> WorkerTracker:
    global _worker_tracker
    if _worker_tracker is None:
        _worker_tracker = get_worker_tracker()
    return _worker_tracker


def _task_payload_lock(task_id: str) -> threading.Lock:
    task_id = str(task_id or "").strip()
    with _payload_locks_guard:
        lock = _payload_locks.get(task_id)
        if lock is None:
            lock = threading.Lock()
            _payload_locks[task_id] = lock
        return lock


def _json_result(payload: Any, *, is_error: bool = False) -> ToolCallResult:
    return ToolCallResult(content=[TextContent(text=json.dumps(payload))], isError=is_error or None)


def _error_result(message: str) -> ToolCallResult:
    logger.error(message)
    return _json_result({"error": message}, is_error=True)


def _utc_now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def _runner_config_payload(task_payload: dict[str, Any]) -> dict[str, Any]:
    raw = task_payload.get("runner_config")
    if not isinstance(raw, dict):
        return {}
    raw_dict = cast("dict[object, object]", raw)
    return {str(key): value for key, value in raw_dict.items()}


def _config_value(task_payload: dict[str, Any], runner_config: dict[str, Any], key: str, default: Any = None) -> Any:
    if key in runner_config:
        return runner_config.get(key)
    return task_payload.get(key, default)


def _as_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _as_optional_text(value: Any) -> str | None:
    text = _as_text(value)
    return text or None


def _as_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    return bool(value)


def _as_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_float(value: Any, default: float) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_text_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    raw_items = cast("list[object]", value)
    return [text for item in raw_items if (text := str(item).strip())]


def _as_text_dict(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    raw_items = cast("dict[object, object]", value)
    return {str(key).strip(): str(item) for key, item in raw_items.items() if str(key).strip()}


def _parse_cli_args(value: Any) -> list[str]:
    if isinstance(value, list):
        return _as_text_list(value)
    text = _as_text(value)
    if not text:
        return []
    return shlex.split(text)


def _load_settings_data(state_path: str) -> dict[str, Any]:
    try:
        settings = load_state(state_path).get("settings")
    except Exception:
        return {}
    if not isinstance(settings, dict):
        return {}
    settings_dict = cast("dict[object, object]", settings)
    return {str(key): value for key, value in settings_dict.items()}


def _load_agent_configs_by_id(state_path: str) -> dict[str, AgentConfig]:
    configs: dict[str, AgentConfig] = {}
    try:
        loaded = load_agent_configs(state_path)
    except Exception:
        return configs
    for config in loaded:
        config_id = _as_text(getattr(config, "config_id", ""))
        if config_id:
            configs[config_id] = config
    return configs


def _effective_gpu_enabled(env: Environment, settings: dict[str, Any]) -> bool:
    global_enabled = _as_bool(settings.get("gpu_enabled"), False)
    mode = normalize_gpu_override_mode(_as_text(getattr(env, "gpu_override_mode", "inherit"), "inherit"))
    if mode == "enabled":
        return True
    if mode == "disabled":
        return False
    return global_enabled


def _effective_network_host(env: Environment, settings: dict[str, Any]) -> bool:
    global_enabled = _as_bool(settings.get("network_host"), False)
    mode = normalize_gpu_override_mode(_as_text(getattr(env, "network_host_override_mode", "inherit"), "inherit"))
    if mode == "enabled":
        return True
    if mode == "disabled":
        return False
    return global_enabled


def _build_agent_chain(env: Environment, task_payload: dict[str, Any]) -> list[AgentInstance]:
    selection = getattr(env, "agent_selection", None)
    if selection is None or not getattr(selection, "agents", None):
        return []

    selection_mode = _as_text(getattr(selection, "selection_mode", "round-robin"), "round-robin").lower()
    pinned_agent_id = _as_text(getattr(selection, "pinned_agent_id", ""))
    selected_agent_id = _as_text(task_payload.get("agent_instance_id"))
    pinned_target = selected_agent_id or pinned_agent_id
    pinned_target_lower = pinned_target.lower()

    agents: list[AgentInstance] = []
    for inst in list(selection.agents or []):
        inst_id = _as_text(getattr(inst, "agent_id", ""))
        config_id = _as_text(getattr(inst, "config_id", ""))
        if selection_mode == "pinned" and pinned_target:
            if inst_id != pinned_target and inst_id.lower() != pinned_target_lower:
                continue
        agents.append(AgentInstance(agent_id=inst_id or config_id or f"agent-{len(agents) + 1}", config_id=config_id))

    if selected_agent_id and selection_mode in {"round-robin", "least-used"}:
        selected_lower = selected_agent_id.lower()
        selected_index: int | None = None
        for index, inst in enumerate(agents):
            inst_id = _as_text(getattr(inst, "agent_id", ""))
            if inst_id == selected_agent_id or inst_id.lower() == selected_lower:
                selected_index = index
                break
        if selected_index is not None and selected_index > 0:
            selected_inst = agents.pop(selected_index)
            agents.insert(0, selected_inst)

    return agents


def _build_agent_selection(env: Environment, task_payload: dict[str, Any]) -> AgentSelection | None:
    selection = getattr(env, "agent_selection", None)
    if selection is None:
        return None
    agents = _build_agent_chain(env, task_payload)
    if not agents:
        return None
    selection_mode = _as_text(getattr(selection, "selection_mode", "round-robin"), "round-robin")
    return AgentSelection(
        agents=agents,
        selection_mode=selection_mode,
        agent_fallbacks={}
        if selection_mode.lower() == "pinned"
        else dict(getattr(selection, "agent_fallbacks", {}) or {}),
        pinned_agent_id=_as_text(getattr(selection, "pinned_agent_id", "")),
    )


def _primary_agent_cli(payload: Payload, env: Environment, cfg: Payload, settings: Payload, state_path: str) -> str:
    agent_configs = _load_agent_configs_by_id(state_path)
    agent_chain = _build_agent_chain(env, payload)
    if agent_chain:
        config = resolve_agent_config(_as_text(getattr(agent_chain[0], "config_id", "")), agent_configs)
        if config is not None and _as_text(getattr(config, "agent_cli", "")):
            return _as_text(getattr(config, "agent_cli", "")).lower()
    configured = _as_text(_config_value(payload, cfg, "agent_cli", ""))
    if configured:
        return configured.lower()
    return normalize_agent(_as_text(settings.get("use"), "codex"))


def _resolve_host_config_dir(task_payload: dict[str, Any], runner_config: dict[str, Any], agent_cli: str) -> str:
    configured = _as_text(_config_value(task_payload, runner_config, "host_config_dir", ""))
    if configured:
        return os.path.abspath(os.path.expanduser(configured))
    return os.path.abspath(os.path.expanduser(default_host_config_dir(agent_cli)))


def _configured_workspace_type(task_payload: dict[str, Any], runner_config: dict[str, Any], env: Environment) -> str:
    if "workspace_type" in runner_config:
        return normalize_workspace_type(_as_text(runner_config.get("workspace_type"), env.workspace_type))
    payload_workspace_type = normalize_workspace_type(_as_text(task_payload.get("workspace_type")))
    if payload_workspace_type != "none":
        return payload_workspace_type
    return normalize_workspace_type(_as_text(getattr(env, "workspace_type", "none"), "none"))


def _resolve_host_workdir(payload: Payload, env: Environment, cfg: Payload, settings: Payload, state_path: str) -> str:
    configured = _as_text(_config_value(payload, cfg, "host_workdir", ""))
    if configured and configured != "—":
        return os.path.abspath(os.path.expanduser(configured))

    task_id = _as_text(payload.get("task_id"))
    workspace_type = _configured_workspace_type(payload, cfg, env)
    if workspace_type == WORKSPACE_MOUNTED:
        return os.path.abspath(os.path.expanduser(_as_text(getattr(env, "workspace_target", ""))))
    if workspace_type == WORKSPACE_CLONED:
        return managed_repo_checkout_path(
            env.env_id,
            data_dir=os.path.dirname(state_path),
            task_id=task_id,
            workspace_location=settings.get("task_workspace_location"),
        )

    fallback = _as_text(getattr(env, "host_workdir", ""))
    return os.path.abspath(os.path.expanduser(fallback)) if fallback else ""


def _build_runner_config(task_payload: dict[str, Any], env: Environment) -> DockerRunnerConfig:
    state_path = default_state_path()
    settings = _load_settings_data(state_path)
    runner_config = _runner_config_payload(task_payload)
    task_id = _as_text(task_payload.get("task_id"))
    agent_cli = _primary_agent_cli(task_payload, env, runner_config, settings, state_path)
    host_workdir = _resolve_host_workdir(task_payload, env, runner_config, settings, state_path)
    workspace_type = _configured_workspace_type(task_payload, runner_config, env)
    workspace_target = _as_text(
        _config_value(task_payload, runner_config, "workspace_target", getattr(env, "workspace_target", ""))
    )
    settings_preflight_script = _as_optional_text(
        _config_value(task_payload, runner_config, "settings_preflight_script")
    )
    if settings_preflight_script is None and _as_bool(settings.get("preflight_enabled"), False):
        settings_preflight_script = _as_optional_text(settings.get("preflight_script"))

    headless_desktop_enabled = _as_bool(
        _config_value(task_payload, runner_config, "headless_desktop_enabled", None),
        _as_bool(settings.get("headless_desktop_enabled"), False)
        or _as_bool(getattr(env, "headless_desktop_enabled", False), False),
    )
    desktop_cache_enabled = _as_bool(
        _config_value(task_payload, runner_config, "desktop_cache_enabled", None),
        _as_bool(getattr(env, "cache_desktop_build", False), False) and headless_desktop_enabled,
    )
    gpu_enabled = _as_bool(
        _config_value(task_payload, runner_config, "gpu_enabled", None), _effective_gpu_enabled(env, settings)
    )
    network_host = _as_bool(
        _config_value(task_payload, runner_config, "network_host", None),
        _effective_network_host(env, settings),
    )
    extra_mounts = (
        _as_text_list(runner_config.get("extra_mounts"))
        if "extra_mounts" in runner_config
        else list(getattr(env, "extra_mounts", []) or [])
    )
    if "extra_mounts" not in runner_config and _as_bool(settings.get("mount_host_cache"), False):
        extra_mounts.append(f"{os.path.expanduser('~/.cache')}:/home/midori-ai/.cache:rw")
    ports = (
        _as_text_list(runner_config.get("ports"))
        if "ports" in runner_config
        else ([] if network_host else list(getattr(env, "ports", []) or []))
    )
    agent_cli_args_source = _config_value(
        task_payload, runner_config, "agent_cli_args", getattr(env, "agent_cli_args", "")
    )
    agent_cli_args = _parse_cli_args(agent_cli_args_source)
    gh_repo = _as_optional_text(_config_value(task_payload, runner_config, "gh_repo"))
    if gh_repo is None and workspace_type == WORKSPACE_CLONED:
        gh_repo = _as_optional_text(getattr(env, "workspace_target", ""))
    gh_base_branch = _as_optional_text(_config_value(task_payload, runner_config, "gh_base_branch"))
    if gh_base_branch is None:
        gh_base_branch = _as_optional_text(getattr(env, "gh_last_base_branch", ""))
    artifact_collection_timeout_s = _as_float(
        _config_value(task_payload, runner_config, "artifact_collection_timeout_s", None), 30.0
    )
    if artifact_collection_timeout_s <= 0.0:
        artifact_collection_timeout_s = 30.0

    return DockerRunnerConfig(
        task_id=task_id,
        image=_as_text(_config_value(task_payload, runner_config, "image", ""), PIXELARCH_EMERALD_IMAGE),
        host_config_dir=_resolve_host_config_dir(task_payload, runner_config, agent_cli),
        host_workdir=host_workdir,
        state_path=state_path,
        agent_cli=agent_cli,
        container_config_dir=_as_text(_config_value(task_payload, runner_config, "container_config_dir", "")),
        container_workdir=_as_text(
            _config_value(task_payload, runner_config, "container_workdir", "/home/midori-ai/workspace"),
            "/home/midori-ai/workspace",
        ),
        auto_remove=_as_bool(_config_value(task_payload, runner_config, "auto_remove", None), True),
        pull_before_run=_as_bool(_config_value(task_payload, runner_config, "pull_before_run", None), True),
        settings_preflight_script=settings_preflight_script,
        headless_desktop_enabled=headless_desktop_enabled,
        desktop_cache_enabled=desktop_cache_enabled,
        container_caching_enabled=_as_bool(
            _config_value(task_payload, runner_config, "container_caching_enabled", None),
            _as_bool(getattr(env, "container_caching_enabled", False), False),
        ),
        cache_system_preflight_enabled=_as_bool(
            _config_value(task_payload, runner_config, "cache_system_preflight_enabled", None),
            _as_bool(getattr(env, "cache_system_preflight_enabled", False), False),
        ),
        cache_settings_preflight_enabled=_as_bool(
            _config_value(task_payload, runner_config, "cache_settings_preflight_enabled", None),
            _as_bool(getattr(env, "cache_settings_preflight_enabled", False), False),
        ),
        gpu_enabled=gpu_enabled,
        network_host=network_host,
        setup_agents_missing_prompt_enabled=_as_bool(
            _config_value(task_payload, runner_config, "setup_agents_missing_prompt_enabled", None),
            _as_bool(getattr(env, "setup_agents_missing_prompt_enabled", False), False),
        ),
        environment_id=_as_text(_config_value(task_payload, runner_config, "environment_id", env.env_id), env.env_id),
        workspace_type=workspace_type,
        workspace_target=workspace_target,
        container_settings_preflight_path=_as_text(
            _config_value(
                task_payload,
                runner_config,
                "container_settings_preflight_path",
                "/tmp/agents-runner-preflight-settings-{task_id}.sh",
            ),
            "/tmp/agents-runner-preflight-settings-{task_id}.sh",
        ),
        container_setup_agents_preflight_path=_as_text(
            _config_value(
                task_payload,
                runner_config,
                "container_setup_agents_preflight_path",
                "/tmp/agents-runner-preflight-setup-agents-{task_id}.sh",
            ),
            "/tmp/agents-runner-preflight-setup-agents-{task_id}.sh",
        ),
        env_vars=_as_text_dict(runner_config.get("env_vars"))
        if "env_vars" in runner_config
        else dict(getattr(env, "env_vars", {}) or {}),
        extra_mounts=extra_mounts,
        ports=ports,
        agent_cli_args=agent_cli_args,
        launch_mode=_as_text(_config_value(task_payload, runner_config, "launch_mode", "agent"), "agent"),
        custom_command_argv=_as_text_list(_config_value(task_payload, runner_config, "custom_command_argv", [])),
        custom_verify_executable=_as_text(_config_value(task_payload, runner_config, "custom_verify_executable", "")),
        gh_repo=gh_repo,
        gh_prefer_gh_cli=_as_bool(
            _config_value(task_payload, runner_config, "gh_prefer_gh_cli", task_payload.get("gh_use_host_cli")),
            _as_bool(getattr(env, "gh_use_host_cli", True), True),
        ),
        gh_recreate_if_needed=_as_bool(_config_value(task_payload, runner_config, "gh_recreate_if_needed", None), True),
        gh_base_branch=gh_base_branch,
        gh_branch_work_mode=_as_text(
            _config_value(
                task_payload, runner_config, "gh_branch_work_mode", getattr(env, "gh_branch_work_mode", "task_branch")
            ),
            "task_branch",
        ),
        gh_task_branch_naming_style=_as_text(
            _config_value(
                task_payload,
                runner_config,
                "gh_task_branch_naming_style",
                getattr(env, "gh_task_branch_naming_style", "standard"),
            ),
            "standard",
        ),
        gh_task_branch_custom_template=_as_text(
            _config_value(
                task_payload,
                runner_config,
                "gh_task_branch_custom_template",
                getattr(env, "gh_task_branch_custom_template", "{task_id}"),
            ),
            "{task_id}",
        ),
        gh_pr_head_ref=_as_optional_text(_config_value(task_payload, runner_config, "gh_pr_head_ref")),
        gh_pr_base_ref=_as_optional_text(_config_value(task_payload, runner_config, "gh_pr_base_ref")),
        gh_context_file_path=_as_optional_text(
            _config_value(task_payload, runner_config, "gh_context_file_path", task_payload.get("gh_context_path"))
        ),
        artifact_collection_timeout_s=artifact_collection_timeout_s,
        container_name=_as_optional_text(_config_value(task_payload, runner_config, "container_name")),
    )


def _validate_runner_config(config: DockerRunnerConfig) -> str | None:
    host_workdir = _as_text(config.host_workdir)
    if not host_workdir:
        return "Task workspace is not configured"
    if config.workspace_type == WORKSPACE_CLONED:
        try:
            os.makedirs(host_workdir, exist_ok=True)
        except OSError as exc:
            return f"Failed to create workspace directory '{host_workdir}': {exc}"
        return None
    if not os.path.isdir(host_workdir):
        return f"Task workspace does not exist: {host_workdir}"
    return None


def _build_supervisor_config(overrides: dict[str, Any]) -> SupervisorConfig:
    return SupervisorConfig(
        max_retries_per_agent=_as_int(overrides.get("max_retries_per_agent"), 0),
        enable_fallback=_as_bool(overrides.get("enable_fallback"), True),
        backoff_base_seconds=_as_float(overrides.get("backoff_base_seconds"), 5.0),
        rate_limit_backoff_base=_as_float(overrides.get("rate_limit_backoff_base"), 60.0),
    )


@dataclass
class _ExecutionContext:
    state_path: str
    task_id: str
    payload: dict[str, Any]
    payload_lock: threading.Lock
    config: DockerRunnerConfig
    env: Environment
    supervisor: TaskSupervisor
    result: SupervisorResult | None = None
    done_metadata: dict[str, Any] | None = None
    last_save_s: float = 0.0


def _payload_logs(payload: dict[str, Any]) -> list[str]:
    raw_logs = payload.get("logs")
    logs = [str(item) for item in cast("list[object]", raw_logs)] if isinstance(raw_logs, list) else []
    payload["logs"] = logs
    return logs


def _persist_execution_payload(context: _ExecutionContext, *, force: bool = False) -> None:
    now_s = time.monotonic()
    if not force and now_s - context.last_save_s < 0.5:
        return
    context.last_save_s = now_s
    save_task_payload(context.state_path, context.payload, archived=False)


def _append_execution_log(context: _ExecutionContext, line: str, *, force: bool = False) -> None:
    parts = str(line or "").splitlines() or [str(line or "")]
    with context.payload_lock:
        logs = _payload_logs(context.payload)
        for part in parts:
            cleaned = part.rstrip("\r")
            if cleaned:
                logs.append(cleaned)
        if len(logs) > 6000:
            context.payload["logs"] = logs[-5000:]
        _persist_execution_payload(context, force=force)


def _apply_execution_state(context: _ExecutionContext, state: dict[str, Any]) -> None:
    with context.payload_lock:
        status = _as_text(state.get("Status"))
        exit_code_raw = state.get("ExitCode")
        if exit_code_raw is not None:
            context.payload["exit_code"] = _as_int(exit_code_raw, 0)
        if status:
            status_lower = status.lower()
            if status_lower in {"exited", "dead"} and context.payload.get("exit_code") is not None:
                context.payload["status"] = (
                    "done" if status_lower == "exited" and context.payload.get("exit_code") == 0 else "failed"
                )
                context.payload["finished_at"] = context.payload.get("finished_at") or _utc_now_iso()
            else:
                context.payload["status"] = status_lower
        container_id = _as_optional_text(context.supervisor.container_id)
        if container_id is not None:
            context.payload["container_id"] = container_id
        started_at = _as_optional_text(state.get("StartedAt"))
        finished_at = _as_optional_text(state.get("FinishedAt"))
        if started_at is not None:
            context.payload["started_at"] = started_at
        if finished_at is not None:
            context.payload["finished_at"] = finished_at
        if "DesktopEnabled" in state:
            context.payload["headless_desktop_enabled"] = _as_bool(state.get("DesktopEnabled"), False)
        novnc_url = _as_optional_text(state.get("NoVncUrl"))
        if novnc_url is not None:
            context.payload["novnc_url"] = novnc_url
        _persist_execution_payload(context)


def _collect_execution_artifacts(context: _ExecutionContext) -> list[str]:
    task_dict = {
        "task_id": context.task_id,
        "image": _as_text(context.payload.get("image")),
        "agent_cli": _as_text(context.payload.get("agent_cli")),
        "created_at": _as_float(context.payload.get("created_at_s"), 0.0),
    }
    try:
        return collect_artifacts_from_container_with_timeout(
            _as_text(context.supervisor.container_id, _as_text(context.payload.get("container_id"))),
            task_dict,
            _as_text(context.payload.get("environment_id"), context.env.env_id),
            timeout_s=context.config.artifact_collection_timeout_s,
        )
    except Exception as exc:
        _append_execution_log(
            context, format_log("host", "artifacts", "ERROR", f"artifact collection failed: {exc}"), force=True
        )
        return []


def _finalize_execution_payload(context: _ExecutionContext) -> None:
    result = context.result or SupervisorResult(
        exit_code=1, error="Task supervisor did not return a result", artifacts=[]
    )
    metadata = dict(result.metadata)
    if context.done_metadata:
        metadata.update(context.done_metadata)

    artifacts = list(result.artifacts or [])
    collected_artifacts = _collect_execution_artifacts(context)
    if collected_artifacts:
        artifacts.extend(collected_artifacts)

    with context.payload_lock:
        context.payload["exit_code"] = int(result.exit_code)
        context.payload["error"] = result.error
        context.payload["finished_at"] = context.payload.get("finished_at") or _utc_now_iso()
        context.payload["container_id"] = _as_optional_text(context.supervisor.container_id) or context.payload.get(
            "container_id"
        )
        context.payload["gh_repo_root"] = _as_text(
            context.supervisor.gh_repo_root, _as_text(context.payload.get("gh_repo_root"))
        )
        context.payload["gh_base_branch"] = _as_text(
            context.supervisor.gh_base_branch, _as_text(context.payload.get("gh_base_branch"))
        )
        context.payload["gh_branch"] = _as_text(
            context.supervisor.gh_branch, _as_text(context.payload.get("gh_branch"))
        )
        if artifacts:
            context.payload["artifacts"] = artifacts

        agent_used = metadata.get("agent_used")
        agent_id = metadata.get("agent_id")
        attempt_history = metadata.get("attempt_history")
        if agent_used:
            context.payload["agent_cli"] = str(agent_used)
        if agent_id:
            context.payload["agent_instance_id"] = str(agent_id)
        if isinstance(attempt_history, list):
            context.payload["attempt_history"] = attempt_history

        user_stop = _as_text(metadata.get("user_stop")).lower()
        if user_stop == "kill":
            context.payload["status"] = "killed"
            context.payload["error"] = None
        elif user_stop == "cancel":
            context.payload["status"] = "cancelled"
            context.payload["error"] = None
        elif result.error:
            context.payload["status"] = "failed"
        else:
            context.payload["status"] = "done" if int(result.exit_code) == 0 else "failed"

        _persist_execution_payload(context, force=True)


def _run_supervised_task(context: _ExecutionContext) -> None:
    try:
        context.result = context.supervisor.run()
    except Exception as exc:
        _append_execution_log(
            context, format_log("host", "task", "ERROR", f"supervisor execution failed: {exc}"), force=True
        )
        context.result = SupervisorResult(exit_code=1, error=str(exc), artifacts=[])
    finally:
        try:
            _finalize_execution_payload(context)
        finally:
            _active_worker_tracker().unregister(context.task_id)


# ── Handlers ──────────────────────────────────────────────────────────────────


async def handle_task_create(
    env_id: str,
    prompt: str,
    image: str | None = None,
    agent_cli: str | None = None,
) -> ToolCallResult:
    """Create a new task in the specified environment and save it as an active payload."""
    envs = load_environments()
    env = envs.get(env_id)
    if env is None:
        error_msg = f"Environment '{env_id}' not found"
        logger.error(error_msg)
        return ToolCallResult(
            content=[TextContent(text=json.dumps({"error": error_msg}))],
            isError=True,
        )

    task_id = uuid4().hex[:12]
    now_s = time.time()
    workspace_type = normalize_workspace_type(_as_text(getattr(env, "workspace_type", "none"), "none"))
    host_workdir = _as_text(getattr(env, "host_workdir", ""))
    if workspace_type == WORKSPACE_MOUNTED:
        host_workdir = _as_text(getattr(env, "workspace_target", ""))
    payload: dict[str, Any] = {
        "task_id": task_id,
        "prompt": prompt,
        "image": image or "",
        "host_workdir": host_workdir,
        "host_config_dir": "",
        "environment_id": env_id,
        "created_at_s": now_s,
        "status": "queued",
        "exit_code": None,
        "error": None,
        "container_id": None,
        "started_at": None,
        "finished_at": None,
        "gh_use_host_cli": bool(getattr(env, "gh_use_host_cli", True)),
        "workspace_type": workspace_type,
        "workspace_target": _as_text(getattr(env, "workspace_target", "")),
        "gh_repo_root": "",
        "gh_base_branch": _as_text(getattr(env, "gh_last_base_branch", "")),
        "gh_branch": "",
        "gh_pr_url": "",
        "gh_pr_metadata_path": "",
        "gh_pr_unavailable_reason": "",
        "gh_pr_unavailable_status": "",
        "gh_context_path": "",
        "git": None,
        "agent_cli": agent_cli or "",
        "agent_instance_id": "",
        "agent_cli_args": "",
        "launch_mode": "agent",
        "ide_system": "",
        "ide_display_target": "",
        "headless_desktop_enabled": False,
        "novnc_url": "",
        "opencode_web_url": "",
        "artifacts": [],
        "attempt_history": [],
        "finalization_state": "pending",
        "finalization_error": "",
        "runner_prompt": None,
        "runner_config": None,
        "logs": [],
    }

    save_task_payload(default_state_path(), payload, archived=False)
    logger.info(f"Task {task_id} created (env={env_id})")

    return ToolCallResult(
        content=[
            TextContent(
                text=json.dumps({"task_id": task_id, "status": payload["status"]}),
            ),
        ],
    )


async def handle_task_requeue(task_id: str) -> ToolCallResult:
    """Set a task's status back to queued (searches active then archived storage)."""
    state_path = default_state_path()

    payload = load_task_payload(state_path, task_id, archived=False)
    found_archived = False
    if payload is None:
        payload = load_task_payload(state_path, task_id, archived=True)
        found_archived = True

    if payload is None:
        error_msg = f"Task '{task_id}' not found"
        logger.error(error_msg)
        return ToolCallResult(
            content=[TextContent(text=json.dumps({"error": error_msg}))],
            isError=True,
        )

    current_status = str(payload.get("status") or "")
    # Only change status if not already an active state (queued or running)
    if current_status not in ("queued", "running"):
        payload["status"] = "queued"
        # If the task was archived (done), save it as active to re-queue
        save_task_payload(state_path, payload, archived=False)
        logger.info(
            f"Task {task_id} status set to queued (was {current_status}"
            f"{', re-queued from archived' if found_archived else ''})",
        )
    else:
        logger.info(f"Task {task_id} already {current_status}, no change")

    return ToolCallResult(
        content=[
            TextContent(
                text=json.dumps(
                    {"task_id": task_id, "status": payload.get("status", "queued")},
                ),
            ),
        ],
    )


handle_task_start = handle_task_requeue


async def handle_task_execute(task_id: str, **kwargs: Any) -> ToolCallResult:
    """Execute a persisted task in the background through the Docker task supervisor."""
    task_id = _as_text(task_id)
    if not task_id:
        return _error_result("task_id is required")

    worker_tracker = _active_worker_tracker()
    existing = worker_tracker.get(task_id)
    if existing is not None and not existing.future.done():
        return _json_result({"task_id": task_id, "status": "running"})

    state_path = default_state_path()
    payload = load_task_payload(state_path, task_id, archived=False)
    found_archived = False
    if payload is None:
        payload = load_task_payload(state_path, task_id, archived=True)
        found_archived = payload is not None
    if payload is None:
        return _error_result(f"Task '{task_id}' not found")

    env_id = _as_text(payload.get("environment_id") or payload.get("env_id"))
    env = load_environments().get(env_id)
    if env is None:
        return _error_result(f"Environment '{env_id}' not found for task '{task_id}'")

    try:
        config = _build_runner_config(payload, env)
    except ValueError as exc:
        return _error_result(f"Invalid task runner configuration for '{task_id}': {exc}")

    workspace_error = _validate_runner_config(config)
    if workspace_error is not None:
        return _error_result(workspace_error)

    agent_selection = _build_agent_selection(env, payload)
    if (
        getattr(env, "agent_selection", None) is not None
        and getattr(env.agent_selection, "agents", None)
        and agent_selection is None
    ):
        return _error_result(f"No runnable agent selection resolved for task '{task_id}'")

    prompt = _as_text(payload.get("runner_prompt"), _as_text(payload.get("prompt")))
    if not prompt:
        return _error_result(f"Task '{task_id}' has no prompt to execute")

    payload_lock = _task_payload_lock(task_id)
    with payload_lock:
        payload["task_id"] = task_id
        payload["environment_id"] = env.env_id
        payload["image"] = config.image
        payload["host_workdir"] = config.host_workdir
        payload["host_config_dir"] = config.host_config_dir
        payload["workspace_type"] = config.workspace_type
        payload["status"] = "running"
        payload["exit_code"] = None
        payload["error"] = None
        payload["started_at"] = payload.get("started_at") or _utc_now_iso()
        payload["finished_at"] = None
        payload["runner_prompt"] = prompt
        payload["runner_config"] = asdict(config)
        _payload_logs(payload)
        save_task_payload(state_path, payload, archived=False)

    context_ref: dict[str, _ExecutionContext] = {}

    def _on_done(exit_code: int, error: str | None, artifacts: list[str], metadata: dict[str, Any]) -> None:
        del exit_code, error, artifacts
        context = context_ref.get("context")
        if context is not None:
            context.done_metadata = dict(metadata)

    def _on_state(state: dict[str, Any]) -> None:
        context = context_ref.get("context")
        if context is None:
            return
        _apply_execution_state(context, state)

    def _on_log(line: str) -> None:
        context = context_ref.get("context")
        if context is None:
            return
        _append_execution_log(context, line)

    def _on_retry(attempt_number: int, agent: str, delay: float) -> None:
        del delay
        _on_log(format_log("supervisor", "retry", "INFO", f"starting attempt {attempt_number} with {agent} (fallback)"))

    def _on_agent_switch(from_agent: str, to_agent: str) -> None:
        _on_log(format_log("supervisor", "fallback", "INFO", f"switching from {from_agent} to {to_agent} (fallback)"))
        with payload_lock:
            payload["agent_cli"] = to_agent
            save_task_payload(state_path, payload, archived=False)

    supervisor_config = _build_supervisor_config(kwargs)
    watch_states = load_watch_state(load_state(state_path))
    agent_configs = _load_agent_configs_by_id(state_path)
    supervisor = TaskSupervisor(
        config=config,
        prompt=prompt,
        agent_selection=agent_selection,
        supervisor_config=supervisor_config,
        on_state=_on_state,
        on_log=_on_log,
        on_retry=_on_retry,
        on_agent_switch=_on_agent_switch,
        on_done=_on_done,
        watch_states=watch_states,
        agent_configs=agent_configs,
    )
    context = _ExecutionContext(
        state_path=state_path,
        task_id=task_id,
        payload=payload,
        payload_lock=payload_lock,
        config=config,
        env=env,
        supervisor=supervisor,
    )
    context_ref["context"] = context

    def _runner() -> None:
        _run_supervised_task(context)

    worker_tracker.submit(task_id, supervisor, _runner)
    logger.info(f"Task {task_id} execution started via MCP{' (re-queued from archived)' if found_archived else ''}")
    return _json_result({"task_id": task_id, "status": "running"})


async def handle_task_list(status: str | None = None, limit: int = 20) -> ToolCallResult:
    """List tasks with optional status filter. Merges active and done tasks."""
    state_path = default_state_path()

    active = load_active_task_payloads(state_path)
    done = load_done_task_payloads(state_path, offset=0, limit=limit)

    merged = active + done
    if status:
        merged = [t for t in merged if str(t.get("status") or "").lower() == status.lower()]

    limited = merged[:limit]

    summaries: list[dict[str, Any]] = []
    for task in limited:
        prompt_raw = str(task.get("prompt") or "")
        if len(prompt_raw) > 80:
            prompt_raw = prompt_raw[:80] + "..."
        summaries.append(
            {
                "task_id": task.get("task_id", ""),
                "status": task.get("status", ""),
                "prompt_first_line": prompt_raw,
                "created_at": task.get("created_at_s"),
                "exit_code": task.get("exit_code"),
            }
        )

    return ToolCallResult(
        content=[TextContent(text=json.dumps(summaries))],
    )


async def handle_task_status(task_id: str) -> ToolCallResult:
    """Get detailed status of a task by ID (searches active then archived)."""
    state_path = default_state_path()

    payload = load_task_payload(state_path, task_id, archived=False)
    if payload is None:
        payload = load_task_payload(state_path, task_id, archived=True)

    if payload is None:
        error_msg = f"Task '{task_id}' not found"
        logger.error(error_msg)
        return ToolCallResult(
            content=[TextContent(text=json.dumps({"error": error_msg}))],
            isError=True,
        )

    raw_artifacts: Any = payload.get("artifacts")
    raw_logs: Any = payload.get("logs")

    detail: dict[str, Any] = {
        "task_id": payload.get("task_id"),
        "status": payload.get("status"),
        "exit_code": payload.get("exit_code"),
        "error": payload.get("error"),
        "started_at": payload.get("started_at"),
        "finished_at": payload.get("finished_at"),
        "container_id": payload.get("container_id"),
        "gh_pr_url": payload.get("gh_pr_url"),
        "artifacts_count": len(raw_artifacts) if isinstance(raw_artifacts, list) else 0,  # pyright: ignore[reportUnknownArgumentType]
        "logs_count": len(raw_logs) if isinstance(raw_logs, list) else 0,  # pyright: ignore[reportUnknownArgumentType]
    }

    return ToolCallResult(
        content=[TextContent(text=json.dumps(detail))],
    )


async def handle_task_cancel(task_id: str) -> ToolCallResult:
    """Cancel an active task. Archived (done) tasks cannot be cancelled."""
    state_path = default_state_path()

    payload = load_task_payload(state_path, task_id, archived=False)
    if payload is None:
        error_msg = f"Active task '{task_id}' not found (already done/archived tasks cannot be cancelled)"
        logger.error(error_msg)
        return ToolCallResult(
            content=[TextContent(text=json.dumps({"error": error_msg}))],
            isError=True,
        )

    stop_requested = _active_worker_tracker().cancel(task_id)
    with _task_payload_lock(task_id):
        payload["status"] = "cancelled"
        save_task_payload(state_path, payload, archived=False)
    logger.info(f"Task {task_id} cancelled (stop_requested={stop_requested})")

    return ToolCallResult(
        content=[
            TextContent(
                text=json.dumps({"task_id": task_id, "status": "cancelled", "stop_requested": stop_requested}),
            ),
        ],
    )


# ── Registration ──────────────────────────────────────────────────────────────


def register_task_tools(server: MCPServer, worker_tracker: WorkerTracker | None = None) -> None:
    """Register all task lifecycle tools with an MCP server instance.

    Args:
        server: An ``MCPServer`` instance.
    """
    global _worker_tracker
    if worker_tracker is not None:
        _worker_tracker = worker_tracker

    server.register_tool(
        "task_create",
        handle_task_create,
        ToolDefinition(
            name="task_create",
            description="Create a new task in the specified environment and save it as an active payload.",
            inputSchema={
                "type": "object",
                "properties": {
                    "env_id": {
                        "type": "string",
                        "description": "Environment identifier",
                    },
                    "prompt": {
                        "type": "string",
                        "description": "Task prompt",
                    },
                    "image": {
                        "type": "string",
                        "description": "Container image (optional)",
                    },
                    "agent_cli": {
                        "type": "string",
                        "description": "Agent CLI to use (optional)",
                    },
                },
                "required": ["env_id", "prompt"],
            },
        ),
    )

    server.register_tool(
        "task_execute",
        handle_task_execute,
        ToolDefinition(
            name="task_execute",
            description="Start actual Docker-backed agent execution for a queued task and return immediately while it runs.",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "Task identifier",
                    },
                    "max_retries_per_agent": {
                        "type": "integer",
                        "description": "Override maximum retries per agent (optional)",
                    },
                    "enable_fallback": {
                        "type": "boolean",
                        "description": "Enable supervisor fallback to alternate configured agents (optional)",
                    },
                    "backoff_base_seconds": {
                        "type": "number",
                        "description": "Base retry backoff in seconds (optional)",
                    },
                    "rate_limit_backoff_base": {
                        "type": "number",
                        "description": "Base rate-limit backoff in seconds (optional)",
                    },
                },
                "required": ["task_id"],
            },
        ),
    )

    server.register_tool(
        "task_requeue",
        handle_task_requeue,
        ToolDefinition(
            name="task_requeue",
            description="Set a task's status back to queued. This does not execute the task; call task_execute to run it.",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "Task identifier",
                    },
                },
                "required": ["task_id"],
            },
        ),
    )

    server.register_tool(
        "task_start",
        handle_task_start,
        ToolDefinition(
            name="task_start",
            description="Deprecated alias for task_requeue. Sets a task's status to queued but does not execute it.",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "Task identifier",
                    },
                },
                "required": ["task_id"],
            },
        ),
    )

    server.register_tool(
        "task_list",
        handle_task_list,
        ToolDefinition(
            name="task_list",
            description="List tasks with optional status filter. Returns merged active and done tasks.",
            inputSchema={
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "description": "Filter by status (optional)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum tasks to return (default 20)",
                    },
                },
            },
        ),
    )

    server.register_tool(
        "task_status",
        handle_task_status,
        ToolDefinition(
            name="task_status",
            description="Get detailed status of a task by ID. Searches active then archived storage.",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "Task identifier",
                    },
                },
                "required": ["task_id"],
            },
        ),
    )

    server.register_tool(
        "task_cancel",
        handle_task_cancel,
        ToolDefinition(
            name="task_cancel",
            description="Cancel an active task. Already done/archived tasks cannot be cancelled.",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "Task identifier",
                    },
                },
                "required": ["task_id"],
            },
        ),
    )

    logger.info("Registered 7 task lifecycle tools")
