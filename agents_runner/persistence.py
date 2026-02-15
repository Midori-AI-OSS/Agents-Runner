import os
import tempfile
import time

import tomli
import tomli_w

from datetime import datetime
from typing import Any

from agents_runner.prompt_sanitizer import sanitize_prompt


STATE_VERSION = 4
TASKS_DIR_NAME = "tasks"
TASKS_DONE_DIR_NAME = "done"


def strip_none_for_toml(value: Any) -> Any:
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            if item is None:
                continue
            cleaned_item = strip_none_for_toml(item)
            if cleaned_item is None:
                continue
            cleaned[str(key)] = cleaned_item
        return cleaned
    if isinstance(value, (list, tuple)):
        cleaned_list: list[Any] = []
        for item in value:
            if item is None:
                continue
            cleaned_item = strip_none_for_toml(item)
            if cleaned_item is None:
                continue
            cleaned_list.append(cleaned_item)
        return cleaned_list
    return value


def default_state_path() -> str:
    override = str(os.environ.get("AGENTS_RUNNER_STATE_PATH") or "").strip()
    if override:
        override = os.path.expanduser(override)
        # Treat overrides as a directory unless the path clearly points to a TOML file.
        # This is intentionally permissive so callers can pass a non-existent directory path.
        if override.lower().endswith(".toml"):
            return override
        return os.path.join(override, "state.toml")
    base = os.path.expanduser("~/.midoriai/agents-runner")
    return os.path.join(base, "state.toml")


def _dt_to_str(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _dt_from_str(value: str | None) -> datetime | None:
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def load_state(path: str) -> dict[str, Any]:
    if not os.path.exists(path):
        return {
            "version": STATE_VERSION,
            "tasks": [],
            "settings": {},
            "environments": [],
        }
    with open(path, "rb") as f:
        payload = tomli.load(f)
    if not isinstance(payload, dict):
        return {
            "version": STATE_VERSION,
            "tasks": [],
            "settings": {},
            "environments": [],
        }
    version = payload.get("version")
    if version != STATE_VERSION:
        return {
            "version": STATE_VERSION,
            "tasks": [],
            "settings": {},
            "environments": [],
        }
    payload.setdefault("version", STATE_VERSION)
    payload.setdefault("tasks", [])
    payload.setdefault("settings", {})
    payload.setdefault("environments", [])
    if not isinstance(payload["tasks"], list):
        payload["tasks"] = []
    if not isinstance(payload["settings"], dict):
        payload["settings"] = {}
    if not isinstance(payload["environments"], list):
        payload["environments"] = []
    return payload


def save_state(path: str, payload: dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    payload = dict(payload)
    payload["version"] = STATE_VERSION

    fd, tmp_path = tempfile.mkstemp(
        prefix="state-", suffix=".toml", dir=os.path.dirname(path)
    )
    try:
        with os.fdopen(fd, "wb") as f:
            tomli_w.dump(strip_none_for_toml(payload), f)
        os.replace(tmp_path, path)
    finally:
        try:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
        except Exception:
            pass


def tasks_root_dir(state_path: str) -> str:
    return os.path.join(os.path.dirname(state_path), TASKS_DIR_NAME)


def tasks_done_dir(state_path: str) -> str:
    return os.path.join(tasks_root_dir(state_path), TASKS_DONE_DIR_NAME)


def ensure_task_dirs(state_path: str) -> tuple[str, str]:
    root = tasks_root_dir(state_path)
    done = tasks_done_dir(state_path)
    os.makedirs(root, exist_ok=True)
    os.makedirs(done, exist_ok=True)
    return root, done


def _safe_task_filename(task_id: str) -> str:
    cleaned = "".join(
        ch for ch in str(task_id or "") if ch.isalnum() or ch in {"-", "_"}
    ).strip()
    if not cleaned:
        cleaned = f"task-{time.time_ns()}"
    return f"{cleaned}.toml"


def task_path(state_path: str, task_id: str, *, archived: bool = False) -> str:
    folder = tasks_done_dir(state_path) if archived else tasks_root_dir(state_path)
    return os.path.join(folder, _safe_task_filename(task_id))


def _atomic_write_json(path: str, payload: dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        prefix=f"{os.path.basename(path)}.",
        suffix=".tmp",
        dir=os.path.dirname(path),
    )
    try:
        with os.fdopen(fd, "wb") as f:
            tomli_w.dump(strip_none_for_toml(payload), f)
        os.replace(tmp_path, path)
    finally:
        try:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
        except Exception:
            pass


def _archive_active_task_file_if_present(state_path: str, task_id: str) -> None:
    active_path = task_path(state_path, task_id, archived=False)
    if not os.path.exists(active_path):
        return
    ensure_task_dirs(state_path)
    done_path = task_path(state_path, task_id, archived=True)
    if os.path.exists(done_path):
        dedup_path = os.path.join(
            tasks_done_dir(state_path),
            f"{os.path.splitext(os.path.basename(done_path))[0]}.dup-{time.time_ns()}.toml",
        )
        try:
            os.replace(active_path, dedup_path)
        except OSError:
            pass
        return
    try:
        os.replace(active_path, done_path)
    except OSError:
        pass


def save_task_payload(
    state_path: str, payload: dict[str, Any], *, archived: bool
) -> None:
    task_id = str(payload.get("task_id") or "").strip()
    if not task_id:
        return
    ensure_task_dirs(state_path)
    if archived:
        _archive_active_task_file_if_present(state_path, task_id)
    _atomic_write_json(task_path(state_path, task_id, archived=archived), payload)


def load_active_task_payloads(state_path: str) -> list[dict[str, Any]]:
    root = tasks_root_dir(state_path)
    if not os.path.isdir(root):
        return []
    payloads: list[dict[str, Any]] = []
    for name in sorted(os.listdir(root)):
        if not name.endswith(".toml"):
            continue
        path = os.path.join(root, name)
        if not os.path.isfile(path):
            continue
        try:
            with open(path, "rb") as f:
                payload = tomli.load(f)
        except Exception:
            continue
        if isinstance(payload, dict):
            payloads.append(payload)
    return payloads


def load_task_payload(
    state_path: str, task_id: str, *, archived: bool
) -> dict[str, Any] | None:
    task_id = str(task_id or "").strip()
    if not task_id:
        return None
    path = task_path(state_path, task_id, archived=archived)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "rb") as f:
            payload = tomli.load(f)
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def load_done_task_payloads(
    state_path: str, *, offset: int = 0, limit: int = 10
) -> list[dict[str, Any]]:
    try:
        offset = max(0, int(offset))
    except Exception:
        offset = 0
    try:
        limit = max(1, int(limit))
    except Exception:
        limit = 10

    done = tasks_done_dir(state_path)
    if not os.path.isdir(done):
        return []

    names: list[str] = []
    try:
        for name in os.listdir(done):
            if name.endswith(".toml"):
                names.append(name)
    except OSError:
        return []

    def _mtime(name: str) -> float:
        try:
            return float(os.path.getmtime(os.path.join(done, name)))
        except OSError:
            return 0.0

    names.sort(key=_mtime, reverse=True)

    payloads: list[dict[str, Any]] = []
    for name in names[offset : offset + limit]:
        path = os.path.join(done, name)
        if not os.path.isfile(path):
            continue
        try:
            with open(path, "rb") as f:
                payload = tomli.load(f)
        except Exception:
            continue
        if isinstance(payload, dict):
            payloads.append(payload)
    return payloads


def serialize_task(task: Any) -> dict[str, Any]:
    runner_config = getattr(task, "_runner_config", None)
    runner_config_payload: dict[str, Any] | None = None
    if runner_config is not None:
        try:
            from dataclasses import asdict

            runner_config_payload = asdict(runner_config)
        except Exception:
            runner_config_payload = None
    runner_prompt = getattr(task, "_runner_prompt", None)
    git_payload: dict[str, Any] | None = None
    raw_git = getattr(task, "git", None)
    if isinstance(raw_git, dict) and raw_git:
        git_payload = dict(raw_git)
    return {
        "task_id": task.task_id,
        "prompt": task.prompt,
        "image": task.image,
        "host_workdir": task.host_workdir,
        "host_config_dir": task.host_config_dir,
        "environment_id": getattr(task, "environment_id", ""),
        "created_at_s": task.created_at_s,
        "status": task.status,
        "exit_code": task.exit_code,
        "error": task.error,
        "container_id": task.container_id,
        "started_at": _dt_to_str(task.started_at),
        "finished_at": _dt_to_str(task.finished_at),
        "gh_use_host_cli": bool(getattr(task, "gh_use_host_cli", True)),
        "workspace_type": getattr(task, "workspace_type", "none"),
        "gh_repo_root": getattr(task, "gh_repo_root", ""),
        "gh_base_branch": getattr(task, "gh_base_branch", ""),
        "gh_branch": getattr(task, "gh_branch", ""),
        "gh_pr_url": getattr(task, "gh_pr_url", ""),
        "gh_pr_metadata_path": getattr(task, "gh_pr_metadata_path", ""),
        "gh_context_path": getattr(task, "gh_context_path", ""),
        "git": git_payload,
        "agent_cli": getattr(task, "agent_cli", ""),
        "agent_instance_id": getattr(task, "agent_instance_id", ""),
        "agent_cli_args": getattr(task, "agent_cli_args", ""),
        "headless_desktop_enabled": bool(
            getattr(task, "headless_desktop_enabled", False)
        ),
        "novnc_url": getattr(task, "novnc_url", ""),
        "desktop_display": getattr(task, "desktop_display", ""),
        "artifacts": list(getattr(task, "artifacts", [])),
        "attempt_history": list(getattr(task, "attempt_history", [])),
        "finalization_state": str(
            getattr(task, "finalization_state", "pending") or "pending"
        ),
        "finalization_error": str(getattr(task, "finalization_error", "") or ""),
        "runner_prompt": runner_prompt,
        "runner_config": runner_config_payload,
        "logs": list(task.logs[-2000:]),
    }


def deserialize_task(task_cls: type, data: dict[str, Any]) -> Any:
    git_payload = data.get("git")
    if not isinstance(git_payload, dict) or not git_payload:
        git_payload = None

    # Migration: workspace_type from gh_management_mode
    # Prefer new key, fallback to old key
    workspace_type = data.get("workspace_type")
    if not workspace_type and "gh_management_mode" in data:
        old_mode = data["gh_management_mode"]
        if old_mode == "github":
            workspace_type = "cloned"
        elif old_mode == "local":
            workspace_type = "mounted"
        else:
            workspace_type = "none"

    workspace_type = workspace_type or "none"

    task = task_cls(
        task_id=str(data.get("task_id") or ""),
        prompt=sanitize_prompt(str(data.get("prompt") or "")),
        image=str(data.get("image") or ""),
        host_workdir=str(data.get("host_workdir") or ""),
        host_config_dir=str(
            data.get("host_config_dir") or data.get("host_codex_dir") or ""
        ),
        environment_id=str(data.get("environment_id") or ""),
        created_at_s=float(data.get("created_at_s") or 0.0),
        status=str(data.get("status") or "queued"),
        exit_code=data.get("exit_code"),
        error=data.get("error"),
        container_id=data.get("container_id"),
        started_at=_dt_from_str(data.get("started_at")),
        finished_at=_dt_from_str(data.get("finished_at")),
        gh_use_host_cli=bool(
            data.get("gh_use_host_cli") if "gh_use_host_cli" in data else True
        ),
        workspace_type=workspace_type,
        gh_repo_root=str(data.get("gh_repo_root") or ""),
        gh_base_branch=str(data.get("gh_base_branch") or ""),
        gh_branch=str(data.get("gh_branch") or ""),
        gh_pr_url=str(data.get("gh_pr_url") or ""),
        gh_pr_metadata_path=str(data.get("gh_pr_metadata_path") or ""),
        gh_context_path=str(data.get("gh_context_path") or ""),
        git=git_payload,
        agent_cli=str(data.get("agent_cli") or ""),
        agent_instance_id=str(data.get("agent_instance_id") or ""),
        agent_cli_args=str(data.get("agent_cli_args") or ""),
        headless_desktop_enabled=bool(data.get("headless_desktop_enabled") or False),
        novnc_url=str(data.get("novnc_url") or ""),
        vnc_password="",
        desktop_display=str(data.get("desktop_display") or ""),
        artifacts=list(data.get("artifacts") or []),
        attempt_history=list(data.get("attempt_history") or []),
        finalization_state=str(data.get("finalization_state") or "pending"),
        finalization_error=str(data.get("finalization_error") or ""),
        logs=list(data.get("logs") or []),
    )
    runner_prompt = data.get("runner_prompt")
    if isinstance(runner_prompt, str) and runner_prompt.strip():
        try:
            task._runner_prompt = runner_prompt
        except Exception:
            pass
    raw_runner_config = data.get("runner_config")
    if isinstance(raw_runner_config, dict):
        runner_config = _deserialize_runner_config(
            raw_runner_config, task_id=str(task.task_id or "")
        )
        if runner_config is not None:
            try:
                task._runner_config = runner_config
            except Exception:
                pass
    return task


def _deserialize_runner_config(payload: dict[str, Any], *, task_id: str) -> Any:
    try:
        from agents_runner.docker_runner import DockerRunnerConfig
    except Exception:
        return None
    try:
        env_vars: dict[str, str] = {}
        raw_env = payload.get("env_vars")
        if isinstance(raw_env, dict):
            for key, value in raw_env.items():
                k = str(key).strip()
                if not k:
                    continue
                env_vars[k] = str(value)

        extra_mounts: list[str] = []
        raw_mounts = payload.get("extra_mounts")
        if isinstance(raw_mounts, list):
            extra_mounts = [str(item) for item in raw_mounts if str(item).strip()]

        ports: list[str] = []
        raw_ports = payload.get("ports")
        if isinstance(raw_ports, list):
            ports = [str(item) for item in raw_ports if str(item).strip()]

        agent_cli_args: list[str] = []
        raw_args = payload.get("agent_cli_args")
        if isinstance(raw_args, list):
            agent_cli_args = [str(item) for item in raw_args if str(item).strip()]

        artifact_collection_timeout_s = 30.0
        raw_timeout = payload.get("artifact_collection_timeout_s")
        if raw_timeout is not None:
            try:
                artifact_collection_timeout_s = float(raw_timeout)
            except Exception:
                artifact_collection_timeout_s = 30.0
        if artifact_collection_timeout_s <= 0.0:
            artifact_collection_timeout_s = 30.0

        agent_cli = str(payload.get("agent_cli") or "codex")
        agent_cli_lower = agent_cli.strip().lower()
        container_config_dir = str(payload.get("container_config_dir") or "").strip()
        if not container_config_dir and agent_cli_lower == "codex":
            container_config_dir = str(payload.get("container_codex_dir") or "").strip()

        return DockerRunnerConfig(
            task_id=str(payload.get("task_id") or task_id),
            image=str(payload.get("image") or ""),
            host_config_dir=str(
                payload.get("host_config_dir") or payload.get("host_codex_dir") or ""
            ),
            host_workdir=str(payload.get("host_workdir") or ""),
            agent_cli=agent_cli,
            container_config_dir=container_config_dir,
            container_workdir=str(
                payload.get("container_workdir") or "/home/midori-ai/workspace"
            ),
            auto_remove=bool(
                payload.get("auto_remove") if "auto_remove" in payload else True
            ),
            pull_before_run=bool(
                payload.get("pull_before_run") if "pull_before_run" in payload else True
            ),
            settings_preflight_script=str(
                payload.get("settings_preflight_script") or ""
            ).strip()
            or None,
            environment_preflight_script=str(
                payload.get("environment_preflight_script") or ""
            ).strip()
            or None,
            headless_desktop_enabled=bool(
                payload.get("headless_desktop_enabled") or False
            ),
            desktop_cache_enabled=bool(payload.get("desktop_cache_enabled") or False),
            container_caching_enabled=bool(
                payload.get("container_caching_enabled") or False
            ),
            cache_system_preflight_enabled=bool(
                payload.get("cache_system_preflight_enabled") or False
            ),
            cache_settings_preflight_enabled=bool(
                payload.get("cache_settings_preflight_enabled") or False
            ),
            container_settings_preflight_path=str(
                payload.get("container_settings_preflight_path")
                or "/tmp/agents-runner-preflight-settings-{task_id}.sh"
            ),
            container_environment_preflight_path=str(
                payload.get("container_environment_preflight_path")
                or "/tmp/agents-runner-preflight-environment-{task_id}.sh"
            ),
            env_vars=env_vars,
            extra_mounts=extra_mounts,
            ports=ports,
            agent_cli_args=agent_cli_args,
            artifact_collection_timeout_s=artifact_collection_timeout_s,
        )
    except Exception:
        return None


def load_watch_state(state: dict[str, Any]) -> dict[str, Any]:
    """Load agent watch state from persistence.

    Args:
        state: State dictionary loaded from JSON

    Returns:
        Dict mapping provider_name -> AgentWatchState data
    """
    from agents_runner.core.agent.watch_state import (
        AgentStatus,
        AgentWatchState,
        SupportLevel,
        UsageWindow,
    )

    watch_data = state.get("agent_watch", {})
    if not isinstance(watch_data, dict):
        return {}

    result = {}
    for provider_name, data in watch_data.items():
        if not isinstance(data, dict):
            continue

        # Deserialize cooldown timestamps
        last_rate_limited_at = None
        if data.get("last_rate_limited_at"):
            last_rate_limited_at = _dt_from_str(data["last_rate_limited_at"])

        cooldown_until = None
        if data.get("cooldown_until"):
            cooldown_until = _dt_from_str(data["cooldown_until"])

        last_checked_at = None
        if data.get("last_checked_at"):
            last_checked_at = _dt_from_str(data["last_checked_at"])

        # Deserialize windows
        windows = []
        for w_data in data.get("windows", []):
            if not isinstance(w_data, dict):
                continue
            reset_at = None
            if w_data.get("reset_at"):
                reset_at = _dt_from_str(w_data["reset_at"])
            windows.append(
                UsageWindow(
                    name=w_data.get("name", ""),
                    used=w_data.get("used", 0),
                    limit=w_data.get("limit", 0),
                    remaining=w_data.get("remaining", 0),
                    remaining_percent=w_data.get("remaining_percent", 0.0),
                    reset_at=reset_at,
                )
            )

        result[provider_name] = AgentWatchState(
            provider_name=provider_name,
            support_level=SupportLevel(data.get("support_level", "unknown")),
            status=AgentStatus(data.get("status", "ready")),
            windows=windows,
            last_rate_limited_at=last_rate_limited_at,
            cooldown_until=cooldown_until,
            cooldown_reason=data.get("cooldown_reason", ""),
            last_checked_at=last_checked_at,
            last_error=data.get("last_error", ""),
            raw_data=data.get("raw_data", {}),
        )

    return result


def save_watch_state(state: dict[str, Any], watch_states: dict[str, Any]) -> None:
    """Save agent watch state to persistence.

    Args:
        state: State dictionary to update
        watch_states: Dict mapping provider_name -> AgentWatchState
    """
    watch_data = {}

    for provider_name, ws in watch_states.items():
        watch_data[provider_name] = {
            "provider_name": ws.provider_name,
            "support_level": ws.support_level.value,
            "status": ws.status.value,
            "windows": [
                {
                    "name": w.name,
                    "used": w.used,
                    "limit": w.limit,
                    "remaining": w.remaining,
                    "remaining_percent": w.remaining_percent,
                    "reset_at": _dt_to_str(w.reset_at),
                }
                for w in ws.windows
            ],
            "last_rate_limited_at": _dt_to_str(ws.last_rate_limited_at),
            "cooldown_until": _dt_to_str(ws.cooldown_until),
            "cooldown_reason": ws.cooldown_reason,
            "last_checked_at": _dt_to_str(ws.last_checked_at),
            "last_error": ws.last_error,
            "raw_data": ws.raw_data,
        }

    state["agent_watch"] = watch_data
