import json
import os
import tempfile
import time

from datetime import datetime
from typing import Any

from agents_runner.prompt_sanitizer import sanitize_prompt


STATE_VERSION = 3
TASKS_DIR_NAME = "tasks"
TASKS_DONE_DIR_NAME = "done"


def default_state_path() -> str:
    override = str(os.environ.get("AGENTS_RUNNER_STATE_PATH") or "").strip()
    if override:
        override = os.path.expanduser(override)
        if os.path.isdir(override):
            return os.path.join(override, "state.json")
        return override
    base = os.path.expanduser("~/.midoriai/agents-runner")
    return os.path.join(base, "state.json")


def _dt_to_str(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _dt_from_str(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip()
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
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        return {
            "version": STATE_VERSION,
            "tasks": [],
            "settings": {},
            "environments": [],
        }
    version = payload.get("version")
    if isinstance(version, int) and version != STATE_VERSION:
        backup_path = f"{path}.bak-{time.time_ns()}"
        try:
            os.replace(path, backup_path)
        except OSError:
            pass
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
        prefix="state-", suffix=".json", dir=os.path.dirname(path)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=True)
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
    return f"{cleaned}.json"


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
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=True)
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
            f"{os.path.splitext(os.path.basename(done_path))[0]}.dup-{time.time_ns()}.json",
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
        if not name.endswith(".json"):
            continue
        path = os.path.join(root, name)
        if not os.path.isfile(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                payload = json.load(f)
        except Exception:
            continue
        if isinstance(payload, dict):
            payloads.append(payload)
    return payloads


def serialize_task(task) -> dict[str, Any]:
    runner_config = getattr(task, "_runner_config", None)
    runner_config_payload: dict[str, Any] | None = None
    if runner_config is not None:
        try:
            from dataclasses import asdict

            runner_config_payload = asdict(runner_config)
        except Exception:
            runner_config_payload = None
    runner_prompt = getattr(task, "_runner_prompt", None)
    return {
        "task_id": task.task_id,
        "prompt": task.prompt,
        "image": task.image,
        "host_workdir": task.host_workdir,
        "host_codex_dir": task.host_codex_dir,
        "environment_id": getattr(task, "environment_id", ""),
        "created_at_s": task.created_at_s,
        "status": task.status,
        "exit_code": task.exit_code,
        "error": task.error,
        "container_id": task.container_id,
        "started_at": _dt_to_str(task.started_at),
        "finished_at": _dt_to_str(task.finished_at),
        "gh_management_mode": getattr(task, "gh_management_mode", ""),
        "gh_use_host_cli": bool(getattr(task, "gh_use_host_cli", True)),
        "gh_repo_root": getattr(task, "gh_repo_root", ""),
        "gh_base_branch": getattr(task, "gh_base_branch", ""),
        "gh_branch": getattr(task, "gh_branch", ""),
        "gh_pr_url": getattr(task, "gh_pr_url", ""),
        "gh_pr_metadata_path": getattr(task, "gh_pr_metadata_path", ""),
        "agent_cli": getattr(task, "agent_cli", ""),
        "agent_instance_id": getattr(task, "agent_instance_id", ""),
        "agent_cli_args": getattr(task, "agent_cli_args", ""),
        "runner_prompt": runner_prompt,
        "runner_config": runner_config_payload,
        "logs": list(task.logs[-2000:]),
    }


def deserialize_task(task_cls, data: dict[str, Any]):
    task = task_cls(
        task_id=str(data.get("task_id") or ""),
        prompt=sanitize_prompt(str(data.get("prompt") or "")),
        image=str(data.get("image") or ""),
        host_workdir=str(data.get("host_workdir") or ""),
        host_codex_dir=str(data.get("host_codex_dir") or ""),
        environment_id=str(data.get("environment_id") or ""),
        created_at_s=float(data.get("created_at_s") or 0.0),
        status=str(data.get("status") or "queued"),
        exit_code=data.get("exit_code"),
        error=data.get("error"),
        container_id=data.get("container_id"),
        started_at=_dt_from_str(data.get("started_at")),
        finished_at=_dt_from_str(data.get("finished_at")),
        gh_management_mode=str(data.get("gh_management_mode") or ""),
        gh_use_host_cli=bool(
            data.get("gh_use_host_cli") if "gh_use_host_cli" in data else True
        ),
        gh_repo_root=str(data.get("gh_repo_root") or ""),
        gh_base_branch=str(data.get("gh_base_branch") or ""),
        gh_branch=str(data.get("gh_branch") or ""),
        gh_pr_url=str(data.get("gh_pr_url") or ""),
        gh_pr_metadata_path=str(data.get("gh_pr_metadata_path") or ""),
        agent_cli=str(data.get("agent_cli") or ""),
        agent_instance_id=str(data.get("agent_instance_id") or ""),
        agent_cli_args=str(data.get("agent_cli_args") or ""),
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


def _deserialize_runner_config(
    payload: dict[str, Any], *, task_id: str
) -> object | None:
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

        agent_cli_args: list[str] = []
        raw_args = payload.get("agent_cli_args")
        if isinstance(raw_args, list):
            agent_cli_args = [str(item) for item in raw_args if str(item).strip()]

        return DockerRunnerConfig(
            task_id=str(payload.get("task_id") or task_id),
            image=str(payload.get("image") or ""),
            host_codex_dir=str(payload.get("host_codex_dir") or ""),
            host_workdir=str(payload.get("host_workdir") or ""),
            agent_cli=str(payload.get("agent_cli") or "codex"),
            container_codex_dir=str(
                payload.get("container_codex_dir") or "/home/midori-ai/.codex"
            ),
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
            agent_cli_args=agent_cli_args,
        )
    except Exception:
        return None
