from __future__ import annotations

import os
import shlex

from PySide6.QtWidgets import QMessageBox

from codex_local_conatinerd.agent_cli import container_config_dir
from codex_local_conatinerd.agent_cli import normalize_agent
from codex_local_conatinerd.agent_cli import verify_cli_clause
from codex_local_conatinerd.ui.utils import _looks_like_agent_help_command
from codex_local_conatinerd.environments import Environment


class _MainWindowSettingsMixin:
    def _apply_settings_to_pages(self) -> None:
        self._settings.set_settings(self._settings_data)
        self._apply_active_environment_to_new_task()


    def _apply_settings(self, settings: dict) -> None:
        merged = dict(self._settings_data)
        merged.update(settings or {})
        merged["use"] = normalize_agent(str(merged.get("use") or "codex"))

        shell_value = str(merged.get("shell") or "bash").lower()
        if shell_value not in {"bash", "sh", "zsh", "fish", "tmux"}:
            shell_value = "bash"
        merged["shell"] = shell_value

        host_codex_dir = os.path.expanduser(str(merged.get("host_codex_dir") or "").strip())
        if not host_codex_dir:
            host_codex_dir = os.path.expanduser("~/.codex")
        merged["host_codex_dir"] = host_codex_dir

        merged["host_claude_dir"] = os.path.expanduser(str(merged.get("host_claude_dir") or "").strip())
        merged["host_copilot_dir"] = os.path.expanduser(str(merged.get("host_copilot_dir") or "").strip())

        merged["preflight_enabled"] = bool(merged.get("preflight_enabled") or False)
        merged["preflight_script"] = str(merged.get("preflight_script") or "")
        merged["interactive_command"] = str(merged.get("interactive_command") or "--sandbox danger-full-access")
        merged["interactive_command_claude"] = str(merged.get("interactive_command_claude") or "")
        merged["interactive_command_copilot"] = str(merged.get("interactive_command_copilot") or "")
        for key in ("interactive_command", "interactive_command_claude", "interactive_command_copilot"):
            merged[key] = self._sanitize_interactive_command_value(key, merged.get(key))
        merged["append_pixelarch_context"] = bool(merged.get("append_pixelarch_context") or False)

        try:
            merged["max_agents_running"] = int(str(merged.get("max_agents_running", -1)).strip())
        except Exception:
            merged["max_agents_running"] = -1
        self._settings_data = merged
        self._apply_settings_to_pages()
        self._schedule_save()


    def _interactive_command_key(self, agent_cli: str) -> str:
        agent_cli = normalize_agent(agent_cli)
        if agent_cli == "claude":
            return "interactive_command_claude"
        if agent_cli == "copilot":
            return "interactive_command_copilot"
        return "interactive_command"


    def _host_config_dir_key(self, agent_cli: str) -> str:
        agent_cli = normalize_agent(agent_cli)
        if agent_cli == "claude":
            return "host_claude_dir"
        if agent_cli == "copilot":
            return "host_copilot_dir"
        return "host_codex_dir"


    def _default_interactive_command(self, agent_cli: str) -> str:
        agent_cli = normalize_agent(agent_cli)
        if agent_cli == "claude":
            return "--add-dir /home/midori-ai/workspace"
        if agent_cli == "copilot":
            return "--add-dir /home/midori-ai/workspace"
        return "--sandbox danger-full-access"


    def _sanitize_interactive_command_value(self, key: str, raw: object) -> str:
        value = str(raw or "").strip()
        if not value:
            return ""

        try:
            cmd_parts = shlex.split(value)
        except ValueError:
            cmd_parts = []
        if cmd_parts and cmd_parts[0] in {"codex", "claude", "copilot"}:
            head = cmd_parts.pop(0)
            if head == "codex" and cmd_parts and cmd_parts[0] == "exec":
                cmd_parts.pop(0)
            value = " ".join(shlex.quote(part) for part in cmd_parts)

        if _looks_like_agent_help_command(value):
            agent_cli = "codex"
            if str(key or "").endswith("_claude"):
                agent_cli = "claude"
            elif str(key or "").endswith("_copilot"):
                agent_cli = "copilot"
            return self._default_interactive_command(agent_cli)

        return value


    @staticmethod
    def _is_agent_help_interactive_launch(prompt: str, command: str) -> bool:
        prompt = str(prompt or "").strip().lower()
        if prompt.startswith("get agent help"):
            return True
        return _looks_like_agent_help_command(command)


    def _effective_host_config_dir(
        self,
        *,
        agent_cli: str,
        env: Environment | None,
        settings: dict[str, object] | None = None,
    ) -> str:
        agent_cli = normalize_agent(agent_cli)
        settings = settings or self._settings_data

        config_dir = ""
        if agent_cli == "claude":
            config_dir = str(settings.get("host_claude_dir") or "")
        elif agent_cli == "copilot":
            config_dir = str(settings.get("host_copilot_dir") or "")
        else:
            config_dir = str(
                settings.get("host_codex_dir")
                or os.environ.get("CODEX_HOST_CODEX_DIR", os.path.expanduser("~/.codex"))
            )
        if env and env.host_codex_dir:
            config_dir = env.host_codex_dir
        return os.path.expanduser(str(config_dir or "").strip())


    def _ensure_agent_config_dir(self, agent_cli: str, host_config_dir: str) -> bool:
        agent_cli = normalize_agent(agent_cli)
        host_config_dir = os.path.expanduser(str(host_config_dir or "").strip())
        if agent_cli in {"claude", "copilot"} and not host_config_dir:
            agent_label = "Claude" if agent_cli == "claude" else "Copilot"
            QMessageBox.warning(
                self,
                "Missing config folder",
                f"Set the {agent_label} Config folder in Settings (or override it per-environment).",
            )
            return False
        if not host_config_dir:
            return False
        if os.path.exists(host_config_dir) and not os.path.isdir(host_config_dir):
            QMessageBox.warning(self, "Invalid config folder", "Config folder path is not a directory.")
            return False
        try:
            os.makedirs(host_config_dir, exist_ok=True)
        except Exception as exc:
            QMessageBox.warning(self, "Invalid config folder", str(exc))
            return False
        return True
