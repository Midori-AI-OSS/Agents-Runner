from __future__ import annotations

import os
import shlex
from pathlib import Path

from agents_runner.agent_cli import CONTAINER_HOME
from agents_runner.agent_cli import CONTAINER_WORKDIR
from agents_runner.agent_cli import SUPPORTED_AGENTS
from agents_runner.agent_cli import additional_config_mounts
from agents_runner.agent_cli import container_config_dir
from agents_runner.agent_cli import normalize_agent
from agents_runner.agent_cli import verify_cli_clause
from agents_runner.docker.utils import _write_preflight_script
from agents_runner.docker_platform import docker_platform_args_for_pixelarch
from agents_runner.environments import GH_MANAGEMENT_GITHUB


def build_interactive_container_command(
    *,
    agent_cli: str,
    prompt: str,
    env_agent_args: list[str],
    user_parts: list[str],
    full_cmd: list[str] | None,
    host_workdir: str,
    gh_mode: str,
) -> tuple[list[str], str | None]:
    agent_cli = normalize_agent(agent_cli)
    prompt = str(prompt or "").strip()

    if full_cmd:
        verify: str | None = None
        head = str(full_cmd[0] or "").strip().lower()
        if head in SUPPORTED_AGENTS:
            verify = head
        cmd = list(full_cmd)
        if prompt:
            if head == "copilot":
                if "-i" not in cmd and "--interactive" not in cmd:
                    cmd.extend(["-i", prompt])
            elif prompt not in cmd:
                cmd.append(prompt)
        return cmd, verify

    combined_args = list(env_agent_args or []) + list(user_parts or [])

    def _strip_noninteractive_args(agent: str, args: list[str]) -> list[str]:
        agent = normalize_agent(agent)
        if not args:
            return []
        if agent == "claude":
            # Interactive mode should not force non-interactive print output.
            print_only_with_value = {
                "--output-format",
                "--json-schema",
                "--input-format",
                "--max-budget-usd",
            }
            cleaned: list[str] = []
            skip_next = False
            for part in args:
                if skip_next:
                    skip_next = False
                    continue
                if part in {"-p", "--print"}:
                    continue
                if part in print_only_with_value:
                    skip_next = True
                    continue
                cleaned.append(part)
            return cleaned
        if agent == "copilot":
            # Interactive mode should not force prompt (non-interactive) mode.
            cleaned: list[str] = []
            skip_next = False
            for part in args:
                if skip_next:
                    skip_next = False
                    continue
                if part in {"-p", "--prompt"}:
                    skip_next = True
                    continue
                cleaned.append(part)
            return cleaned
        return args

    if agent_cli == "codex":
        if combined_args and combined_args[0] == "exec":
            combined_args = combined_args[1:]
        if gh_mode != GH_MANAGEMENT_GITHUB and not os.path.exists(os.path.join(host_workdir, ".git")):
            if "--skip-git-repo-check" not in combined_args:
                combined_args.append("--skip-git-repo-check")
        cmd = ["codex", *combined_args]
        if prompt:
            cmd.append(prompt)
        return cmd, "codex"

    if agent_cli == "claude":
        combined_args = _strip_noninteractive_args("claude", combined_args)
        cmd = ["claude", *combined_args]
        if prompt:
            cmd.append(prompt)
        return cmd, "claude"

    combined_args = _strip_noninteractive_args("copilot", combined_args)
    cmd = ["copilot", *combined_args]
    if (
        prompt
        and "-i" not in combined_args
        and "--interactive" not in combined_args
        and "-p" not in combined_args
        and "--prompt" not in combined_args
    ):
        cmd.extend(["-i", prompt])
    return cmd, "copilot"


def build_interactive_terminal_script(
    *,
    task_id: str,
    container_name: str,
    image: str,
    config_agent_cli: str,
    verify_agent_cli: str | None,
    host_config_dir: str,
    host_workdir: str,
    extra_mounts: list[str],
    env_vars: dict[str, str],
    settings_preflight_script: str | None,
    environment_preflight_script: str | None,
    launch_preflight_script: str,
    gh_repo: str,
    gh_base_branch: str,
    gh_prefer_gh: bool,
    docker_inner_cmd: list[str],
    token: str | None,
) -> tuple[str, str]:
    repo_root = Path(__file__).resolve().parents[2]
    platform_args = docker_platform_args_for_pixelarch()

    preflight_tmp_paths: list[str] = []
    mounts: list[str] = []
    preflight_clause = ""

    def _add_preflight(label: str, script_text: str, container_path: str) -> None:
        nonlocal preflight_clause
        tmp_path = _write_preflight_script(script_text, label, task_id, preflight_tmp_paths)
        mounts.append(f"{tmp_path}:{container_path}:ro")
        preflight_clause += (
            f'PREFLIGHT_{label.upper()}={shlex.quote(container_path)}; '
            f'echo "[preflight] {label}: running"; '
            f'/bin/bash "${{PREFLIGHT_{label.upper()}}}"; '
            f'echo "[preflight] {label}: done"; '
        )

    if (settings_preflight_script or "").strip():
        _add_preflight("settings", str(settings_preflight_script), f"/tmp/agents-runner-preflight-settings-{task_id}.sh")
    if (environment_preflight_script or "").strip():
        _add_preflight(
            "environment",
            str(environment_preflight_script),
            f"/tmp/agents-runner-preflight-environment-{task_id}.sh",
        )
    if (launch_preflight_script or "").strip():
        _add_preflight("launch", str(launch_preflight_script), f"/tmp/agents-runner-preflight-launch-{task_id}.sh")

    cleanup_trap = ""
    if preflight_tmp_paths:
        cleanup_cmd = " ".join(f"rm -f {shlex.quote(p)};" for p in preflight_tmp_paths)
        cleanup_trap = f"cleanup() {{ {cleanup_cmd} }}; trap cleanup EXIT"

    config_agent_cli = normalize_agent(config_agent_cli)
    verify_agent_cli = normalize_agent(verify_agent_cli) if verify_agent_cli else None

    extra_mount_args: list[str] = []
    for mount in extra_mounts or []:
        m = str(mount or "").strip()
        if not m:
            continue
        extra_mount_args.extend(["-v", m])

    for mount in additional_config_mounts(config_agent_cli, host_config_dir):
        m = str(mount or "").strip()
        if not m:
            continue
        extra_mount_args.extend(["-v", m])

    if mounts:
        for m in mounts:
            extra_mount_args.extend(["-v", m])

    if (launch_preflight_script or "").strip():
        host_help_root = os.path.expanduser("~/.agent-help")
        try:
            os.makedirs(host_help_root, exist_ok=True)
        except Exception:
            pass
        extra_mount_args.extend(["-v", f"{host_help_root}:{CONTAINER_HOME}/.agent-help:rw"])

    env_args: list[str] = []
    for key, value in sorted((env_vars or {}).items()):
        k = str(key).strip()
        if not k:
            continue
        env_args.extend(["-e", f"{k}={value}"])

    # Ensure TUIs have the basic terminal+locale variables inside the container.
    for key in ("TERM", "COLORTERM", "LANG", "LC_ALL"):
        if key not in (env_vars or {}):
            env_args.extend(["-e", key])

    export_lines: list[str] = []
    if token and "GH_TOKEN" not in (env_vars or {}) and "GITHUB_TOKEN" not in (env_vars or {}):
        env_args.extend(["-e", "GH_TOKEN", "-e", "GITHUB_TOKEN"])
        export_lines.append(f"export GH_TOKEN={shlex.quote(token)}")
        export_lines.append(f"export GITHUB_TOKEN={shlex.quote(token)}")

    inner_clause = "set -euo pipefail; "
    inner_clause += preflight_clause
    if verify_agent_cli:
        inner_clause += verify_cli_clause(verify_agent_cli)
    inner_clause += "exec " + " ".join(shlex.quote(part) for part in docker_inner_cmd)

    docker_args = [
        "docker",
        "run",
        *platform_args,
        "-it",
        "--name",
        container_name,
        "-v",
        f"{host_config_dir}:{container_config_dir(config_agent_cli)}",
        "-v",
        f"{host_workdir}:{CONTAINER_WORKDIR}",
        *extra_mount_args,
        *env_args,
        "-w",
        CONTAINER_WORKDIR,
        image,
        "/bin/bash",
        "-lc",
        inner_clause,
    ]
    docker_cmd_line = " ".join(shlex.quote(part) for part in docker_args)
    pull_cmd = ["docker", "pull", *platform_args, image]
    docker_pull_line = " ".join(shlex.quote(part) for part in pull_cmd)

    gh_setup = ""
    if (gh_repo or "").strip():
        gh_setup = "\n".join(
            [
                'echo "[gh] preparing repo..."',
                f"export PYTHONPATH={shlex.quote(str(repo_root))}:\"${{PYTHONPATH:-}}\"",
                "python - <<'PY'",
                "from __future__ import annotations",
                "import json",
                "from agents_runner.gh_management import prepare_github_repo_for_task",
                "",
                f"repo = {gh_repo!r}",
                f"dest_dir = {host_workdir!r}",
                f"task_id = {task_id!r}",
                f"base_branch = {gh_base_branch!r} or None",
                f"prefer_gh = {bool(gh_prefer_gh)!r}",
                "",
                "def log(line: str) -> None:",
                "    print(str(line or ''), flush=True)",
                "",
                "result = prepare_github_repo_for_task(",
                "    repo,",
                "    dest_dir,",
                "    task_id=task_id,",
                "    base_branch=base_branch,",
                "    prefer_gh=prefer_gh,",
                "    recreate_if_needed=True,",
                "    on_log=log,",
                ")",
                "print('[gh] result: ' + json.dumps(result), flush=True)",
                "PY",
            ]
        )

    script_lines = [
        "set -euo pipefail",
        cleanup_trap,
        'export TERM="${TERM:-xterm-256color}"',
        f'echo "[host] Agents Runner: interactive task {task_id} ({container_name})"',
        *export_lines,
        gh_setup,
        f'echo "[host] {docker_pull_line}"',
        docker_pull_line,
        f'echo "[host] {docker_cmd_line}"',
        docker_cmd_line,
        'echo "[host] session ended"',
        "bash",
    ]
    script = "\n".join(line for line in script_lines if str(line).strip())
    return script, host_workdir
